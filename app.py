import sqlite3
import os
from flask import Flask, render_template, request, redirect, url_for, flash, session

app = Flask(__name__)
app.secret_key = 'motta_hotels_secret_v1'
DATABASE = 'hotel.db'

# Hardcoded Admin Credentials
ADMIN_USER = 'admin'
ADMIN_PASS = 'admin123'

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    if not os.path.exists(DATABASE):
        with app.app_context():
            db = get_db()
            # Create Habitaciones table
            db.execute('''
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
            ''')
            # Create Reservas table
            db.execute('''
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
            ''')
            
            # Seed initial rooms if empty
            cursor = db.execute('SELECT COUNT(*) FROM habitaciones')
            if cursor.fetchone()[0] == 0:
                habitaciones_seed = [
                    ('Habitación Estándar', 'estandar', 2, 120.0, 1, 1, 'WiFi, A/C', 'Habitación cómoda para estancias cortas.'),
                    ('Habitación Ejecutiva', 'ejecutiva', 2, 220.0, 1, 2, 'WiFi 6, Minibar, Escritorio', 'Ideal para viajeros de negocios.'),
                    ('Suite Familiar Deluxe', 'familiar', 4, 320.0, 1, 3, '2 Camas Dobles, Smart TV', 'Espacio y diversión para toda la familia.'),
                    ('Suite Imperial', 'suite', 4, 450.0, 0, 4, 'Vista Mar, Hidromasaje', 'El lujo absoluto en Hotel Motta.')
                ]
                db.executemany('''
                    INSERT INTO habitaciones (nombre, tipo, capacidad, precio_noche, disponible, piso, amenidades, descripcion)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', habitaciones_seed)
            
            db.commit()
            db.close()

# --- Public Routes ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/disponibles')
def disponibles():
    db = get_db()
    entrada = request.args.get('entrada', '')
    salida = request.args.get('salida', '')
    huespedes = request.args.get('huespedes', 1)
    
    habitaciones = db.execute('SELECT * FROM habitaciones WHERE disponible = 1').fetchall()
    db.close()
    return render_template('disponibles.html', habitaciones=habitaciones, entrada=entrada, salida=salida, huespedes=huespedes)

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
        huespedes = request.form.get('huespedes')
        notas = request.form.get('notas')
        
        db.execute('''
            INSERT INTO reservas (nombre_cliente, cedula, email, telefono, habitacion_id, fecha_entrada, fecha_salida, numero_huespedes, notas)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (nombre, cedula, email, telefono, hab_id, entrada, salida, huespedes, notas))
        db.commit()
        db.close()
        return redirect(url_for('confirmacion', entrada=entrada, salida=salida, huespedes=huespedes))
    
    hab_id = request.args.get('hab')
    entrada = request.args.get('entrada', '')
    salida = request.args.get('salida', '')
    huespedes = request.args.get('huespedes', 1)
    
    habitacion = None
    if hab_id:
        habitacion = db.execute('SELECT * FROM habitaciones WHERE id = ?', (hab_id,)).fetchone()
    
    db.close()
    return render_template('reservar.html', habitacion=habitacion, entrada=entrada, salida=salida, huespedes=huespedes)

@app.route('/confirmacion')
def confirmacion():
    entrada = request.args.get('entrada')
    salida = request.args.get('salida')
    huespedes = request.args.get('huespedes')
    return render_template('confirmacion.html', entrada=entrada, salida=salida, huespedes=huespedes)

# --- Admin Routes ---

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        user = request.form.get('usuario')
        pw = request.form.get('password')
        if user == ADMIN_USER and pw == ADMIN_PASS:
            session['admin_logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        flash('Usuario o contraseña incorrectos', 'error')
    return render_template('admin/login.html')

@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin_logged_in'): return redirect(url_for('admin_login'))
    db = get_db()
    reservas = db.execute('SELECT * FROM reservas ORDER BY id DESC LIMIT 5').fetchall()
    habitaciones = db.execute('SELECT * FROM habitaciones ORDER BY id ASC LIMIT 5').fetchall()
    stats = {
        'total_reservas': db.execute('SELECT COUNT(*) FROM reservas').fetchone()[0],
        'total_habitaciones': db.execute('SELECT COUNT(*) FROM habitaciones').fetchone()[0],
        'disponibles': db.execute('SELECT COUNT(*) FROM habitaciones WHERE disponible = 1').fetchone()[0]
    }
    db.close()
    return render_template('admin/dashboard.html', reservas=reservas, habitaciones=habitaciones, stats=stats)

@app.route('/admin/habitaciones')
def admin_habitaciones():
    if not session.get('admin_logged_in'): return redirect(url_for('admin_login'))
    db = get_db()
    habitaciones = db.execute('SELECT * FROM habitaciones').fetchall()
    db.close()
    return render_template('admin/habitaciones.html', habitaciones=habitaciones)

@app.route('/admin/nueva_habitacion', methods=['GET', 'POST'])
def admin_nueva_habitacion():
    if not session.get('admin_logged_in'): return redirect(url_for('admin_login'))
    if request.method == 'POST':
        db = get_db()
        db.execute('''
            INSERT INTO habitaciones (nombre, tipo, capacidad, precio_noche, disponible, piso, amenidades, descripcion)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (request.form.get('nombre'), request.form.get('tipo'), request.form.get('capacidad'), 
              request.form.get('precio_noche'), request.form.get('disponible'), request.form.get('piso'),
              request.form.get('amenidades'), request.form.get('descripcion')))
        db.commit()
        db.close()
        return redirect(url_for('admin_habitaciones'))
    return render_template('admin/nueva_habitacion.html')

@app.route('/admin/editar_habitacion/<int:id>', methods=['GET', 'POST'])
def admin_editar_habitacion(id):
    if not session.get('admin_logged_in'): return redirect(url_for('admin_login'))
    db = get_db()
    if request.method == 'POST':
        db.execute('''
            UPDATE habitaciones SET nombre=?, tipo=?, capacidad=?, precio_noche=?, disponible=?, piso=?, amenidades=?, descripcion=?
            WHERE id=?
        ''', (request.form.get('nombre'), request.form.get('tipo'), request.form.get('capacidad'), 
              request.form.get('precio_noche'), request.form.get('disponible'), request.form.get('piso'),
              request.form.get('amenidades'), request.form.get('descripcion'), id))
        db.commit()
        db.close()
        return redirect(url_for('admin_habitaciones'))
    
    habitacion = db.execute('SELECT * FROM habitaciones WHERE id = ?', (id,)).fetchone()
    db.close()
    return render_template('admin/editar_habitacion.html', id=id, habitacion=habitacion)

@app.route('/admin/reservas')
def admin_reservas():
    if not session.get('admin_logged_in'): return redirect(url_for('admin_login'))
    db = get_db()
    reservas = db.execute('SELECT * FROM reservas').fetchall()
    db.close()
    return render_template('admin/reservas.html', reservas=reservas)

@app.route('/admin/editar_reserva/<int:id>', methods=['GET', 'POST'])
def admin_editar_reserva(id):
    if not session.get('admin_logged_in'): return redirect(url_for('admin_login'))
    db = get_db()
    if request.method == 'POST':
        db.execute('''
            UPDATE reservas SET nombre_cliente=?, habitacion_id=?, fecha_entrada=?, fecha_salida=?, numero_huespedes=?, estado=?
            WHERE id=?
        ''', (request.form.get('nombre'), request.form.get('habitacion_id'), request.form.get('fecha_entrada'),
              request.form.get('fecha_salida'), request.form.get('numero_huespedes'), request.form.get('estado'), id))
        db.commit()
        db.close()
        return redirect(url_for('admin_reservas'))
    
    reserva = db.execute('SELECT * FROM reservas WHERE id = ?', (id,)).fetchone()
    db.close()
    return render_template('admin/editar_reserva.html', id=id, reserva=reserva)

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
