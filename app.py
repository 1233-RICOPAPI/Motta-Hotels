import os
import sqlite3
from datetime import datetime

from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'motta_hotels_secret_v1')
DATABASE = 'hotel.db'

ADMIN_USER = os.environ.get('ADMIN_USER', 'aaronmotta5@gmail.com')
ADMIN_PASS = os.environ.get('ADMIN_PASS', 'motta2006')
VALID_ROOM_TYPES = {'estandar', 'ejecutiva', 'familiar', 'suite', 'suite_premium'}
VALID_RESERVATION_STATES = {'pendiente', 'confirmada', 'cancelada', 'completada'}


@app.context_processor
def inject_now():
    return {'now': datetime.now}


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def parse_date(value):
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return None


def parse_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def is_valid_stay(entrada, salida):
    entrada_date = parse_date(entrada)
    salida_date = parse_date(salida)
    if not entrada_date or not salida_date:
        return False
    return entrada_date < salida_date


def is_room_available(db, habitacion_id, entrada, salida, exclude_reserva_id=None):
    query = '''
        SELECT 1
        FROM reservas
        WHERE habitacion_id = ?
          AND estado != 'cancelada'
          AND fecha_entrada < ?
          AND fecha_salida > ?
    '''
    params = [str(habitacion_id), salida, entrada]

    if exclude_reserva_id is not None:
        query += ' AND id != ?'
        params.append(exclude_reserva_id)

    query += ' LIMIT 1'
    conflict = db.execute(query, params).fetchone()
    return conflict is None


def get_available_rooms(db, entrada=None, salida=None, huespedes=1):
    query = '''
        SELECT *
        FROM habitaciones
        WHERE disponible = 1
          AND capacidad >= ?
    '''
    params = [huespedes]

    if entrada and salida:
        query += '''
          AND id NOT IN (
              SELECT CAST(habitacion_id AS INTEGER)
              FROM reservas
              WHERE estado != 'cancelada'
                AND fecha_entrada < ?
                AND fecha_salida > ?
          )
        '''
        params.extend([salida, entrada])

    query += ' ORDER BY precio_noche ASC, id ASC'
    return db.execute(query, params).fetchall()


def get_room_stats(db):
    total = db.execute('SELECT COUNT(*) FROM habitaciones').fetchone()[0]
    disponibles = db.execute('SELECT COUNT(*) FROM habitaciones WHERE disponible = 1').fetchone()[0]
    return {
        'total': total,
        'disponibles': disponibles,
        'ocupadas': max(total - disponibles, 0)
    }


def get_room_choices(db):
    return db.execute(
        '''
        SELECT id, nombre, capacidad, disponible
        FROM habitaciones
        ORDER BY COALESCE(piso, 0), nombre, id
        '''
    ).fetchall()


def validate_room_form(form):
    nombre = (form.get('nombre') or '').strip()
    tipo = (form.get('tipo') or '').strip()
    capacidad = parse_int(form.get('capacidad'))
    precio_noche = parse_float(form.get('precio_noche'))
    disponible = 1 if str(form.get('disponible', '1')) == '1' else 0
    piso_raw = (form.get('piso') or '').strip()
    piso = parse_int(piso_raw) if piso_raw else None
    amenidades = (form.get('amenidades') or '').strip()
    descripcion = (form.get('descripcion') or '').strip()

    errors = []
    if not nombre:
        errors.append('El nombre de la habitacion es obligatorio.')
    if tipo not in VALID_ROOM_TYPES:
        errors.append('El tipo de habitacion no es valido.')
    if capacidad is None or capacidad < 1:
        errors.append('La capacidad debe ser un numero mayor o igual a 1.')
    if precio_noche is None or precio_noche <= 0:
        errors.append('El precio por noche debe ser mayor a 0.')
    if piso_raw and (piso is None or piso < 1):
        errors.append('El piso debe ser un numero valido.')

    return {
        'nombre': nombre,
        'tipo': tipo,
        'capacidad': capacidad,
        'precio_noche': precio_noche,
        'disponible': disponible,
        'piso': piso,
        'amenidades': amenidades,
        'descripcion': descripcion
    }, errors


def init_db():
    with app.app_context():
        db = get_db()
        db.execute(
            '''
            CREATE TABLE IF NOT EXISTS habitaciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                tipo TEXT NOT NULL,
                capacidad INTEGER NOT NULL,
                precio_noche REAL NOT NULL,
                disponible INTEGER DEFAULT 1,
                piso INTEGER,
                amenidades TEXT,
                descripcion TEXT
            )
            '''
        )
        db.execute(
            '''
            CREATE TABLE IF NOT EXISTS reservas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre_cliente TEXT NOT NULL,
                cedula TEXT,
                email TEXT,
                telefono TEXT,
                habitacion_id TEXT,
                fecha_entrada TEXT,
                fecha_salida TEXT,
                numero_huespedes INTEGER,
                estado TEXT DEFAULT 'pendiente',
                notas TEXT
            )
            '''
        )

        cursor = db.execute('SELECT COUNT(*) FROM habitaciones')
        if cursor.fetchone()[0] == 0:
            habitaciones_seed = [
                ('Habitacion Estandar', 'estandar', 2, 120.0, 1, 1, 'WiFi, A/C', 'Habitacion comoda para estancias cortas.'),
                ('Habitacion Ejecutiva', 'ejecutiva', 2, 220.0, 1, 2, 'WiFi 6, Minibar, Escritorio', 'Ideal para viajeros de negocios.'),
                ('Suite Familiar Deluxe', 'familiar', 4, 320.0, 1, 3, '2 Camas Dobles, Smart TV', 'Espacio y diversion para toda la familia.'),
                ('Suite Imperial', 'suite', 4, 450.0, 0, 4, 'Vista Mar, Hidromasaje', 'El lujo absoluto en Hotel Motta.')
            ]
            db.executemany(
                '''
                INSERT INTO habitaciones (nombre, tipo, capacidad, precio_noche, disponible, piso, amenidades, descripcion)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                habitaciones_seed
            )

        db.commit()
        db.close()


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/disponibles')
def disponibles():
    db = get_db()
    entrada = request.args.get('entrada', '')
    salida = request.args.get('salida', '')
    huespedes = request.args.get('huespedes', 1, type=int) or 1

    if entrada and salida and not is_valid_stay(entrada, salida):
        flash('Las fechas de reserva no son validas.', 'error')
        habitaciones = []
    else:
        habitaciones = get_available_rooms(db, entrada or None, salida or None, huespedes)

    db.close()
    return render_template(
        'disponibles.html',
        habitaciones=habitaciones,
        entrada=entrada,
        salida=salida,
        huespedes=huespedes
    )


@app.route('/reservar', methods=['GET', 'POST'])
def reservar():
    db = get_db()

    if request.method == 'POST':
        nombre = request.form.get('nombre')
        cedula = request.form.get('cedula')
        email = request.form.get('email')
        telefono = request.form.get('telefono')
        hab_id = request.form.get('habitacion_id')
        entrada = request.form.get('entrada')
        salida = request.form.get('salida')
        huespedes = request.form.get('huespedes', 1, type=int) or 1
        notas = request.form.get('notas')
        total_pago = request.form.get('total_pago', '0')

        habitacion = db.execute('SELECT * FROM habitaciones WHERE id = ?', (hab_id,)).fetchone()

        if not habitacion:
            db.close()
            flash('La habitacion seleccionada no existe.', 'error')
            return redirect(url_for('disponibles', entrada=entrada, salida=salida, huespedes=huespedes))

        if not is_valid_stay(entrada, salida):
            db.close()
            flash('Debes seleccionar fechas validas.', 'error')
            return redirect(url_for('reservar', hab=hab_id, entrada=entrada, salida=salida, huespedes=huespedes))

        if huespedes < 1:
            db.close()
            flash('La cantidad de huespedes es invalida.', 'error')
            return redirect(url_for('reservar', hab=hab_id, entrada=entrada, salida=salida, huespedes=1))

        if huespedes > habitacion['capacidad']:
            db.close()
            flash('La habitacion no soporta esa cantidad de huespedes.', 'error')
            return redirect(url_for('reservar', hab=hab_id, entrada=entrada, salida=salida, huespedes=huespedes))

        if not is_room_available(db, hab_id, entrada, salida):
            db.close()
            flash('La habitacion ya no esta disponible para esas fechas.', 'error')
            return redirect(url_for('disponibles', entrada=entrada, salida=salida, huespedes=huespedes))

        db.execute(
            '''
            INSERT INTO reservas (nombre_cliente, cedula, email, telefono, habitacion_id, fecha_entrada, fecha_salida, numero_huespedes, notas)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (nombre, cedula, email, telefono, hab_id, entrada, salida, huespedes, notas)
        )
        db.commit()
        db.close()
        return redirect(url_for('confirmacion', entrada=entrada, salida=salida, huespedes=huespedes, nombre=nombre, pago=total_pago))

    hab_id = request.args.get('hab')
    entrada = request.args.get('entrada', '')
    salida = request.args.get('salida', '')
    huespedes = request.args.get('huespedes', 1, type=int) or 1

    habitacion = None
    if hab_id:
        habitacion = db.execute('SELECT * FROM habitaciones WHERE id = ?', (hab_id,)).fetchone()
        if habitacion and entrada and salida and not is_room_available(db, hab_id, entrada, salida):
            habitacion = None
            flash('La habitacion no esta disponible para las fechas seleccionadas.', 'error')

    if not habitacion:
        db.close()
        flash('Selecciona una habitacion valida antes de continuar.', 'error')
        return redirect(url_for('disponibles', entrada=entrada, salida=salida, huespedes=huespedes))

    db.close()
    return render_template('reservar.html', habitacion=habitacion, entrada=entrada, salida=salida, huespedes=huespedes)


@app.route('/confirmacion')
def confirmacion():
    entrada = request.args.get('entrada')
    salida = request.args.get('salida')
    huespedes = request.args.get('huespedes')
    nombre = request.args.get('nombre', 'Estimado Cliente')
    pago = request.args.get('pago', '')
    return render_template('confirmacion.html', entrada=entrada, salida=salida, huespedes=huespedes, nombre=nombre, pago=pago)


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        user = request.form.get('usuario')
        pw = request.form.get('password')
        if user == ADMIN_USER and pw == ADMIN_PASS:
            session['admin_logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        flash('Usuario o contrasena incorrectos', 'error')
    return render_template('admin/login.html')


@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    db = get_db()
    reservas = db.execute(
        '''
        SELECT r.*, h.nombre AS habitacion_nombre
        FROM reservas r
        LEFT JOIN habitaciones h ON h.id = CAST(r.habitacion_id AS INTEGER)
        ORDER BY r.id DESC
        LIMIT 5
        '''
    ).fetchall()
    habitaciones = db.execute('SELECT * FROM habitaciones ORDER BY id ASC LIMIT 5').fetchall()
    room_stats = get_room_stats(db)
    stats = {
        'total_reservas': db.execute('SELECT COUNT(*) FROM reservas').fetchone()[0],
        'total_habitaciones': room_stats['total'],
        'disponibles': room_stats['disponibles']
    }

    habs = db.execute('SELECT nombre, precio_noche FROM habitaciones').fetchall()
    nombres = [h['nombre'][:15] + '...' if len(h['nombre']) > 15 else h['nombre'] for h in habs]
    precios = [h['precio_noche'] for h in habs]

    db.close()
    return render_template('admin/dashboard.html', reservas=reservas, habitaciones=habitaciones, stats=stats, nombres=nombres, precios=precios)


@app.route('/api/admin/stats')
def api_admin_stats():
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401

    db = get_db()
    stats = {
        'total_reservas': db.execute('SELECT COUNT(*) FROM reservas').fetchone()[0],
        'total_habitaciones': db.execute('SELECT COUNT(*) FROM habitaciones').fetchone()[0],
        'disponibles': db.execute('SELECT COUNT(*) FROM habitaciones WHERE disponible = 1').fetchone()[0]
    }

    habs = db.execute('SELECT nombre, precio_noche FROM habitaciones').fetchall()
    nombres = [h['nombre'][:15] + '...' if len(h['nombre']) > 15 else h['nombre'] for h in habs]
    precios = [h['precio_noche'] for h in habs]
    db.close()

    return jsonify({
        'stats': stats,
        'chart_data': {
            'labels': nombres,
            'values': precios
        }
    })


@app.route('/admin/habitaciones')
def admin_habitaciones():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    db = get_db()
    habitaciones = db.execute('SELECT * FROM habitaciones').fetchall()
    stats_habitaciones = get_room_stats(db)
    db.close()
    return render_template('admin/habitaciones.html', habitaciones=habitaciones, stats_habitaciones=stats_habitaciones)


@app.route('/admin/nueva_habitacion', methods=['GET', 'POST'])
def admin_nueva_habitacion():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    if request.method == 'POST':
        form_data, errors = validate_room_form(request.form)
        if errors:
            flash(errors[0], 'error')
            return render_template('admin/nueva_habitacion.html', form_data=form_data)

        db = get_db()
        db.execute(
            '''
            INSERT INTO habitaciones (nombre, tipo, capacidad, precio_noche, disponible, piso, amenidades, descripcion)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                form_data['nombre'],
                form_data['tipo'],
                form_data['capacidad'],
                form_data['precio_noche'],
                form_data['disponible'],
                form_data['piso'],
                form_data['amenidades'],
                form_data['descripcion']
            )
        )
        db.commit()
        db.close()
        flash('La habitacion fue creada correctamente.', 'success')
        return redirect(url_for('admin_habitaciones'))
    return render_template('admin/nueva_habitacion.html')


@app.route('/admin/editar_habitacion/<int:id>', methods=['GET', 'POST'])
def admin_editar_habitacion(id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    db = get_db()
    habitacion = db.execute('SELECT * FROM habitaciones WHERE id = ?', (id,)).fetchone()
    if not habitacion:
        db.close()
        flash('La habitacion solicitada no existe.', 'error')
        return redirect(url_for('admin_habitaciones'))

    if request.method == 'POST':
        form_data, errors = validate_room_form(request.form)
        if errors:
            db.close()
            flash(errors[0], 'error')
            return render_template('admin/editar_habitacion.html', id=id, habitacion=form_data)

        db.execute(
            '''
            UPDATE habitaciones
            SET nombre=?, tipo=?, capacidad=?, precio_noche=?, disponible=?, piso=?, amenidades=?, descripcion=?
            WHERE id=?
            ''',
            (
                form_data['nombre'],
                form_data['tipo'],
                form_data['capacidad'],
                form_data['precio_noche'],
                form_data['disponible'],
                form_data['piso'],
                form_data['amenidades'],
                form_data['descripcion'],
                id
            )
        )
        db.commit()
        db.close()
        flash('La habitacion fue actualizada.', 'success')
        return redirect(url_for('admin_habitaciones'))

    db.close()
    return render_template('admin/editar_habitacion.html', id=id, habitacion=habitacion)


@app.route('/admin/reservas')
def admin_reservas():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    db = get_db()
    q = (request.args.get('q') or '').strip()
    query = '''
        SELECT r.*, h.nombre AS habitacion_nombre
        FROM reservas r
        LEFT JOIN habitaciones h ON h.id = CAST(r.habitacion_id AS INTEGER)
    '''
    params = []

    if q:
        query += '''
            WHERE r.nombre_cliente LIKE ?
               OR COALESCE(r.email, '') LIKE ?
               OR COALESCE(r.cedula, '') LIKE ?
        '''
        like_value = f'%{q}%'
        params.extend([like_value, like_value, like_value])

    query += ' ORDER BY r.fecha_entrada DESC, r.id DESC'
    reservas = db.execute(query, params).fetchall()
    stats_reservas = {
        'total': len(reservas),
        'confirmadas': sum(1 for reserva in reservas if reserva['estado'] == 'confirmada'),
        'pendientes': sum(1 for reserva in reservas if reserva['estado'] == 'pendiente'),
        'canceladas': sum(1 for reserva in reservas if reserva['estado'] == 'cancelada')
    }
    db.close()
    return render_template('admin/reservas.html', reservas=reservas, stats_reservas=stats_reservas, query_text=q)


@app.route('/admin/editar_reserva/<int:id>', methods=['GET', 'POST'])
def admin_editar_reserva(id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    db = get_db()
    reserva = db.execute('SELECT * FROM reservas WHERE id = ?', (id,)).fetchone()
    if not reserva:
        db.close()
        flash('La reserva solicitada no existe.', 'error')
        return redirect(url_for('admin_reservas'))

    habitaciones = get_room_choices(db)
    if request.method == 'POST':
        nombre = (request.form.get('nombre') or '').strip()
        habitacion_id = parse_int(request.form.get('habitacion_id'))
        fecha_entrada = request.form.get('fecha_entrada')
        fecha_salida = request.form.get('fecha_salida')
        numero_huespedes = parse_int(request.form.get('numero_huespedes'))
        estado = (request.form.get('estado') or '').strip()
        notas = (request.form.get('notas') or '').strip()

        errors = []
        habitacion = None

        if not nombre:
            errors.append('El nombre del cliente es obligatorio.')
        if habitacion_id is None:
            errors.append('Debes seleccionar una habitacion.')
        else:
            habitacion = db.execute('SELECT * FROM habitaciones WHERE id = ?', (habitacion_id,)).fetchone()
            if not habitacion:
                errors.append('La habitacion seleccionada no existe.')

        if not is_valid_stay(fecha_entrada, fecha_salida):
            errors.append('Las fechas de la reserva no son validas.')
        if numero_huespedes is None or numero_huespedes < 1:
            errors.append('El numero de huespedes debe ser mayor o igual a 1.')
        if estado not in VALID_RESERVATION_STATES:
            errors.append('El estado de la reserva no es valido.')
        if habitacion and numero_huespedes and numero_huespedes > habitacion['capacidad']:
            errors.append('La cantidad de huespedes supera la capacidad de la habitacion.')
        if not errors and estado != 'cancelada' and not is_room_available(db, habitacion_id, fecha_entrada, fecha_salida, exclude_reserva_id=id):
            errors.append('La habitacion ya tiene una reserva activa en esas fechas.')

        if errors:
            db.close()
            flash(errors[0], 'error')
            draft_reserva = {
                'id': id,
                'nombre_cliente': nombre,
                'habitacion_id': habitacion_id,
                'fecha_entrada': fecha_entrada,
                'fecha_salida': fecha_salida,
                'numero_huespedes': numero_huespedes,
                'estado': estado or 'pendiente',
                'notas': notas
            }
            return render_template('admin/editar_reserva.html', id=id, reserva=draft_reserva, habitaciones=habitaciones)

        db.execute(
            '''
            UPDATE reservas
            SET nombre_cliente=?, habitacion_id=?, fecha_entrada=?, fecha_salida=?, numero_huespedes=?, estado=?, notas=?
            WHERE id=?
            ''',
            (
                nombre,
                habitacion_id,
                fecha_entrada,
                fecha_salida,
                numero_huespedes,
                estado,
                notas,
                id
            )
        )
        db.commit()
        db.close()
        flash('La reserva fue actualizada.', 'success')
        return redirect(url_for('admin_reservas'))

    db.close()
    return render_template('admin/editar_reserva.html', id=id, reserva=reserva, habitaciones=habitaciones)


@app.route('/admin/cancelar_reserva/<int:id>', methods=['POST'])
def admin_cancelar_reserva(id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    db = get_db()
    reserva = db.execute('SELECT id FROM reservas WHERE id = ?', (id,)).fetchone()
    if not reserva:
        db.close()
        flash('La reserva que intentas cancelar no existe.', 'error')
        return redirect(url_for('admin_reservas'))

    db.execute("UPDATE reservas SET estado = 'cancelada' WHERE id = ?", (id,))
    db.commit()
    db.close()
    flash('La reserva fue cancelada.', 'success')
    return redirect(url_for('admin_reservas'))


@app.route('/admin/eliminar_habitacion/<int:id>', methods=['POST'])
def admin_eliminar_habitacion(id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    db = get_db()
    habitacion = db.execute('SELECT id FROM habitaciones WHERE id = ?', (id,)).fetchone()
    if not habitacion:
        db.close()
        flash('La habitacion que intentas eliminar no existe.', 'error')
        return redirect(url_for('admin_habitaciones'))

    active_reservations = db.execute(
        '''
        SELECT COUNT(*)
        FROM reservas
        WHERE habitacion_id = ?
          AND estado != 'cancelada'
        ''',
        (str(id),)
    ).fetchone()[0]

    if active_reservations:
        db.close()
        flash('No puedes eliminar una habitacion con reservas activas.', 'error')
        return redirect(url_for('admin_habitaciones'))

    db.execute('DELETE FROM habitaciones WHERE id = ?', (id,))
    db.commit()
    db.close()
    flash('La habitacion fue eliminada.', 'success')
    return redirect(url_for('admin_habitaciones'))


@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))


if __name__ == '__main__':
    init_db()
    app.run(debug=True)
