# Sistema de Reservas de Hotel - Motta And Hotels

Este es un sistema web completo de reservación de habitaciones de hotel, desarrollado bajo el patrón cliente-servidor clásico, con un frontend dinámico y un panel administrativo seguro.

## 🚀 Características Principales

### Para el Cliente
- **Vista Muestral**: Catálogo de habitaciones destacadas y características del hotel.
- **Buscador de Disponibilidad**: Sistema para filtrar habitaciones por fecha de entrada, salida y cantidad de huéspedes.
- **Proceso de Reserva Seguro**: Formulario para recolectar información del huésped, acompañado de un calculador de costo dinámico y simulador de pagos interactivo.
- **Recibo de Confirmación**: Generación de un recibo virtual con todos los detalles de la estancia tras finalizar la reserva.

### Para el Administrador
- **Dashboard Estadístico**: Panel principal con métricas en tiempo real y gráficas auto-generadas sobre el rendimiento (reservas vs. inventario).
- **Gestor de Habitaciones (CRUD)**: Creación, lectura, actualización y control de disponibilidad del inventario de habitaciones.
- **Gestor de Reservas**: Visualizar cada registro de reservación y gestionar su estado (Pendiente, Confirmada, Cancelada).

## 🧰 Tecnologías Utilizadas

- **Backend**: Python 3.x, Flask
- **Base de Datos**: SQLite (`hotel.db`) - persistencia ligera y rápida.
- **Gráficos Generados en Servidor**: Matplotlib (despliegue de datos codificados en Base64).
- **Frontend**: HTML5, Vanilla CSS3 (diseño responsivo y lujoso), Vanilla JavaScript (simulador de pago, calculadoras en cliente).

## ⚙️ Instalación y Configuración

1. **Clonar o descargar el proyecto** en tu entorno local.
2. **Requisitos Previos**:
   Asegúrate de tener instalado Python 3.7 o superior y las siguientes dependencias:
   ```bash
   pip install Flask matplotlib
   ```
3. **Inicializar Servidor**:
   El sistema automáticamente creará y poblará la base de datos `hotel.db` en el primer arranque si no existe.
   ```bash
   python app.py
   ```
4. **Acceso al Sistema**:
   - **Sitio Web Cliente**: `http://127.0.0.1:5000/`
   - **Panel Administrativo**: `http://127.0.0.1:5000/admin/login`

## 🔐 Credenciales de Administrador (Por defecto)
- **Usuario/Correo**: `aaronmotta5@gmail.com`
- **Contraseña**: `motta2006`

## 📊 Notas Técnicas
* Todo el procesamiento de los cuadros estadísticos del *dashboard* de administrador se ejecuta utilizando generadores de `matplotlib` a nivel servidor usando el motor asíncrono e integrado *Agg* de matplotlib (para evitar colisiones de GUI con servidores).
* Los métodos de pago del sistema cliente están simulados puramente en frontend (JavaScript y Modales HTML/CSS) para no afectar lógicas externas e integrarse limpiamente a la estructura de la base de datos.
