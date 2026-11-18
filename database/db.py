
import sqlite3
import os
import math
from datetime import datetime


# =========================================================
# CONFIGURACIÓN
# =========================================================

RUTA_DB = os.path.join(
    os.path.dirname(__file__),
    "carniceria.db"
)


class ConexionCarniceria(sqlite3.Connection):
    """Conexión que también se cierra al salir de un bloque with."""

    def __exit__(self, tipo_error, error, traza):
        try:
            return super().__exit__(tipo_error, error, traza)
        finally:
            self.close()


def conectar():
    conexion = sqlite3.connect(
        RUTA_DB,
        factory=ConexionCarniceria,
        timeout=10
    )
    conexion.execute("PRAGMA foreign_keys = ON")
    return conexion


def numero_valido(valor):
    """Comprueba que sea un número finito y no un booleano."""
    return (
        isinstance(valor, (int, float))
        and not isinstance(valor, bool)
        and math.isfinite(valor)
    )


def ahora():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def fecha_hoy():
    return datetime.now().strftime("%Y-%m-%d")


# =========================================================
# CREACIÓN DE TABLAS
# =========================================================

def crear_tablas():

    with conectar() as conexion:

        cursor = conexion.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS productos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL UNIQUE,
                costo_kg REAL NOT NULL,
                precio_kg REAL NOT NULL,
                stock_kg REAL NOT NULL DEFAULT 0,
                stock_minimo REAL NOT NULL DEFAULT 0
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS clientes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                telefono TEXT,
                direccion TEXT,
                fecha_registro TEXT NOT NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ventas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha TEXT NOT NULL,
                producto_id INTEGER NOT NULL,
                producto_nombre TEXT NOT NULL,
                cantidad_kg REAL NOT NULL,
                precio_kg REAL NOT NULL,
                costo_kg REAL NOT NULL,
                total REAL NOT NULL,
                forma_pago TEXT NOT NULL,
                monto_cobrado REAL NOT NULL,
                cliente_id INTEGER,
                FOREIGN KEY (producto_id) REFERENCES productos(id),
                FOREIGN KEY (cliente_id) REFERENCES clientes(id)
            )
        """)

        # Compatibilidad con bases anteriores.
        cursor.execute("PRAGMA table_info(ventas)")
        columnas_ventas = [
            columna[1] for columna in cursor.fetchall()
        ]

        if "cliente_id" not in columnas_ventas:
            cursor.execute("""
                ALTER TABLE ventas
                ADD COLUMN cliente_id INTEGER
                REFERENCES clientes(id)
            """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pagos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                venta_id INTEGER NOT NULL,
                fecha TEXT NOT NULL,
                monto REAL NOT NULL CHECK(monto > 0),
                FOREIGN KEY (venta_id) REFERENCES ventas(id)
            )
        """)

        # Compatibilidad con pagos anteriores.
        cursor.execute("PRAGMA table_info(pagos)")
        columnas_pagos = [
            columna[1] for columna in cursor.fetchall()
        ]

        if "forma_pago" not in columnas_pagos:
            cursor.execute("""
                ALTER TABLE pagos
                ADD COLUMN forma_pago TEXT
            """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cajas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha_apertura TEXT NOT NULL,
                monto_inicial REAL NOT NULL,
                fecha_cierre TEXT,
                monto_contado REAL,
                diferencia REAL,
                estado TEXT NOT NULL DEFAULT 'Abierta'
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS movimientos_caja (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                caja_id INTEGER NOT NULL,
                fecha TEXT NOT NULL,
                tipo TEXT NOT NULL,
                concepto TEXT NOT NULL,
                monto REAL NOT NULL CHECK(monto > 0),
                FOREIGN KEY (caja_id) REFERENCES cajas(id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS gastos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha TEXT NOT NULL,
                concepto TEXT NOT NULL,
                categoria TEXT NOT NULL,
                monto REAL NOT NULL CHECK(monto > 0),
                forma_pago TEXT NOT NULL,
                caja_id INTEGER,
                FOREIGN KEY (caja_id) REFERENCES cajas(id)
            )
        """)

        # Índices para mejorar las consultas.
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ventas_fecha
            ON ventas(fecha)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ventas_cliente
            ON ventas(cliente_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_pagos_fecha
            ON pagos(fecha)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_pagos_venta
            ON pagos(venta_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_movimientos_caja
            ON movimientos_caja(caja_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_gastos_fecha
            ON gastos(fecha)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_gastos_caja
            ON gastos(caja_id)
        """)

        # Solo puede existir una caja abierta.
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_una_caja_abierta
            ON cajas(estado)
            WHERE estado = 'Abierta'
        """)


# =========================================================
# PRODUCTOS
# =========================================================

def registrar_producto(nombre, costo_kg, precio_kg, stock_kg, stock_minimo):
    nombre = nombre.strip() if isinstance(nombre, str) else ""

    if not nombre:
        return False

    valores = [costo_kg, precio_kg, stock_kg, stock_minimo]

    if not all(numero_valido(valor) for valor in valores):
        return False

    if any(valor < 0 for valor in valores):
        return False

    try:
        with conectar() as conexion:
            conexion.execute("""
                INSERT INTO productos
                (nombre, costo_kg, precio_kg, stock_kg, stock_minimo)
                VALUES (?, ?, ?, ?, ?)
            """, (nombre, costo_kg, precio_kg, stock_kg, stock_minimo))

        return True

    except sqlite3.IntegrityError:
        return False

def listar_productos():

    with conectar() as conexion:

        cursor = conexion.execute("""
            SELECT *
            FROM productos
            ORDER BY nombre
        """)

        return cursor.fetchall()


def actualizar_stock(producto_id, nueva_cantidad):

    if not numero_valido(nueva_cantidad) or nueva_cantidad < 0:
        return False

    with conectar() as conexion:

        cursor = conexion.execute("""
            UPDATE productos
            SET stock_kg = ?
            WHERE id = ?
        """, (nueva_cantidad, producto_id))

        return cursor.rowcount > 0


def agregar_stock(producto_id, cantidad):

    if not numero_valido(cantidad) or cantidad <= 0:
        return False

    with conectar() as conexion:

        cursor = conexion.execute("""
            UPDATE productos
            SET stock_kg = stock_kg + ?
            WHERE id = ?
        """, (cantidad, producto_id))

        return cursor.rowcount > 0


def editar_producto(id_producto, nombre, costo_kg, precio_kg, stock_minimo):
    nombre = nombre.strip() if isinstance(nombre, str) else ""

    if not nombre:
        return False

    valores = [costo_kg, precio_kg, stock_minimo]

    if not all(numero_valido(valor) for valor in valores):
        return False

    if any(valor < 0 for valor in valores):
        return False

    try:
        with conectar() as conexion:
            cursor = conexion.execute("""
                UPDATE productos
                SET nombre = ?,
                    costo_kg = ?,
                    precio_kg = ?,
                    stock_minimo = ?
                WHERE id = ?
            """, (nombre, costo_kg, precio_kg, stock_minimo, id_producto))

            return cursor.rowcount > 0

    except sqlite3.IntegrityError:
        return False

def eliminar_producto(producto_id):

    try:

        with conectar() as conexion:

            cursor = conexion.execute("""
                DELETE FROM productos
                WHERE id = ?
            """, (producto_id,))

            return cursor.rowcount > 0

    except sqlite3.IntegrityError:
        return False


# =========================================================
# CLIENTES
# =========================================================

def registrar_cliente(nombre, telefono="", direccion=""):

    nombre = nombre.strip()

    if not nombre:
        return None

    with conectar() as conexion:

        cursor = conexion.execute("""
            INSERT INTO clientes
            (nombre, telefono, direccion, fecha_registro)
            VALUES (?, ?, ?, ?)
        """, (
            nombre,
            telefono,
            direccion,
            ahora()
        ))

        return cursor.lastrowid


def listar_clientes():

    with conectar() as conexion:

        cursor = conexion.execute("""
            SELECT id, nombre, telefono, direccion
            FROM clientes
            ORDER BY nombre
        """)

        return cursor.fetchall()


# =========================================================
# CAJA: FUNCIONES INTERNAS
# =========================================================

MENSAJE_CAJA_VENCIDA = (
    "La caja abierta es de un día anterior. "
    "Cerrá la caja de ayer antes de continuar."
)


def _caja_abierta_en(cursor):

    cursor.execute("""
        SELECT id, fecha_apertura, monto_inicial
        FROM cajas
        WHERE estado = 'Abierta'
        ORDER BY id DESC
        LIMIT 1
    """)

    return cursor.fetchone()


def _es_vencida(caja):

    hoy = fecha_hoy()

    return caja[1][:10] < hoy


def _caja_para_efectivo(cursor, operacion):

    caja = _caja_abierta_en(cursor)

    if caja is None:
        return None, (
            f"Debés abrir la caja antes de registrar {operacion}."
        )

    if _es_vencida(caja):
        return None, MENSAJE_CAJA_VENCIDA

    return caja[0], None


def _saldo_caja_en(cursor, caja_id):

    cursor.execute("""
        SELECT monto_inicial
        FROM cajas
        WHERE id = ?
    """, (caja_id,))

    caja = cursor.fetchone()

    if caja is None:
        return None

    cursor.execute("""
        SELECT COALESCE(SUM(
            CASE
                WHEN tipo = 'Entrada' THEN monto
                WHEN tipo = 'Salida' THEN -monto
                ELSE 0
            END
        ), 0)
        FROM movimientos_caja
        WHERE caja_id = ?
    """, (caja_id,))

    movimientos = cursor.fetchone()[0]

    return caja[0] + movimientos


# =========================================================
# VENTAS
# =========================================================

def registrar_venta(
    producto_id,
    cantidad,
    forma_pago,
    cliente_id=None
):

    if not numero_valido(cantidad) or cantidad <= 0:
        return False, "La cantidad debe ser mayor que cero."

    if forma_pago not in (
        "Efectivo",
        "Transferencia",
        "Crédito"
    ):
        return False, "La forma de pago no es válida."

    if forma_pago == "Crédito" and cliente_id is None:
        return False, (
            "Debés seleccionar un cliente para la venta a crédito."
        )

    conexion = conectar()

    try:

        conexion.execute("BEGIN IMMEDIATE")

        cursor = conexion.cursor()

        cursor.execute("""
            SELECT nombre, costo_kg, precio_kg, stock_kg
            FROM productos
            WHERE id = ?
        """, (producto_id,))

        producto = cursor.fetchone()

        if producto is None:
            conexion.rollback()
            return False, "El producto no existe."

        nombre, costo_kg, precio_kg, stock_kg = producto

        if cantidad > stock_kg:
            conexion.rollback()
            return False, (
                f"Stock insuficiente. "
                f"Solo hay {stock_kg:g} kg disponibles."
            )

        if cliente_id is not None:

            cursor.execute("""
                SELECT id
                FROM clientes
                WHERE id = ?
            """, (cliente_id,))

            if cursor.fetchone() is None:
                conexion.rollback()
                return False, "El cliente seleccionado no existe."

        total = round(precio_kg * cantidad)

        if forma_pago == "Crédito":
            monto_cobrado = 0
        else:
            monto_cobrado = total

        fecha = ahora()
        caja_id = None

        if forma_pago == "Efectivo":

            caja_id, error = _caja_para_efectivo(
                cursor,
                "una venta en efectivo"
            )

            if error:
                conexion.rollback()
                return False, error

        cursor.execute("""
            UPDATE productos
            SET stock_kg = stock_kg - ?
            WHERE id = ?
            AND stock_kg >= ?
        """, (cantidad, producto_id, cantidad))

        if cursor.rowcount == 0:
            conexion.rollback()
            return False, (
                "Stock insuficiente. Revisá el stock disponible."
            )

        cursor.execute("""
            INSERT INTO ventas (
                fecha,
                producto_id,
                producto_nombre,
                cantidad_kg,
                precio_kg,
                costo_kg,
                total,
                forma_pago,
                monto_cobrado,
                cliente_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            fecha,
            producto_id,
            nombre,
            cantidad,
            precio_kg,
            costo_kg,
            total,
            forma_pago,
            monto_cobrado,
            cliente_id
        ))

        if forma_pago == "Efectivo":

            cursor.execute("""
                INSERT INTO movimientos_caja
                (caja_id, fecha, tipo, concepto, monto)
                VALUES (?, ?, ?, ?, ?)
            """, (
                caja_id,
                fecha,
                "Entrada",
                "Venta en efectivo",
                total
            ))

        conexion.commit()

        return True, total

    except sqlite3.Error as error:

        conexion.rollback()

        return False, f"Error al registrar la venta: {error}"

    finally:
        conexion.close()


def listar_ventas():

    with conectar() as conexion:

        cursor = conexion.execute("""
            SELECT
                ventas.fecha,
                ventas.producto_nombre,
                ventas.cantidad_kg,
                ventas.precio_kg,
                ventas.total,
                ventas.forma_pago,
                ventas.monto_cobrado,
                COALESCE(clientes.nombre, 'Sin cliente')
            FROM ventas
            LEFT JOIN clientes
                ON ventas.cliente_id = clientes.id
            ORDER BY ventas.id DESC
        """)

        return cursor.fetchall()


# =========================================================
# PAGOS Y DEUDAS
# =========================================================

def registrar_pago(venta_id, monto, forma_pago):

    if not numero_valido(monto) or monto <= 0:
        return False, "El pago debe ser mayor que cero."

    if forma_pago not in ("Efectivo", "Transferencia"):
        return False, "La forma de pago no es válida."

    conexion = conectar()

    try:

        conexion.execute("BEGIN IMMEDIATE")

        cursor = conexion.cursor()

        cursor.execute("""
            SELECT total, monto_cobrado, forma_pago
            FROM ventas
            WHERE id = ?
        """, (venta_id,))

        venta = cursor.fetchone()

        if venta is None:
            conexion.rollback()
            return False, "La venta no existe."

        total, monto_cobrado, tipo_venta = venta

        if tipo_venta != "Crédito":
            conexion.rollback()
            return False, "Esta venta no es a crédito."

        saldo = total - monto_cobrado

        if monto > saldo:
            conexion.rollback()
            return False, (
                f"El saldo pendiente es Gs. {saldo:,.0f}."
            )

        fecha = ahora()
        caja_id = None

        if forma_pago == "Efectivo":

            caja_id, error = _caja_para_efectivo(
                cursor,
                "un pago en efectivo"
            )

            if error:
                conexion.rollback()
                return False, error

        cursor.execute("""
            UPDATE ventas
            SET monto_cobrado = monto_cobrado + ?
            WHERE id = ?
            AND total - monto_cobrado >= ?
        """, (monto, venta_id, monto))

        if cursor.rowcount == 0:
            conexion.rollback()
            return False, (
                "El saldo cambió. Actualizá la página "
                "y revisá la deuda."
            )

        cursor.execute("""
            INSERT INTO pagos
            (venta_id, fecha, monto, forma_pago)
            VALUES (?, ?, ?, ?)
        """, (venta_id, fecha, monto, forma_pago))

        if forma_pago == "Efectivo":

            cursor.execute("""
                INSERT INTO movimientos_caja
                (caja_id, fecha, tipo, concepto, monto)
                VALUES (?, ?, ?, ?, ?)
            """, (
                caja_id,
                fecha,
                "Entrada",
                "Pago de deuda",
                monto
            ))

        conexion.commit()

        return True, monto_cobrado + monto

    except sqlite3.Error as error:

        conexion.rollback()

        return False, f"Error al registrar el pago: {error}"

    finally:
        conexion.close()


def listar_deudas():

    with conectar() as conexion:

        cursor = conexion.execute("""
            SELECT
                ventas.id,
                ventas.fecha,
                ventas.producto_nombre,
                ventas.total,
                ventas.monto_cobrado,
                ventas.total - ventas.monto_cobrado AS saldo,
                clientes.nombre
            FROM ventas
            LEFT JOIN clientes
                ON ventas.cliente_id = clientes.id
            WHERE ventas.forma_pago = 'Crédito'
            AND ventas.total > ventas.monto_cobrado
            ORDER BY ventas.fecha DESC
        """)

        return cursor.fetchall()


def listar_pagos():

    with conectar() as conexion:

        cursor = conexion.execute("""
            SELECT
                pagos.fecha,
                clientes.nombre,
                ventas.producto_nombre,
                pagos.monto,
                ventas.id,
                COALESCE(pagos.forma_pago, 'No especificado')
            FROM pagos
            INNER JOIN ventas
                ON pagos.venta_id = ventas.id
            LEFT JOIN clientes
                ON ventas.cliente_id = clientes.id
            ORDER BY pagos.id DESC
        """)

        return cursor.fetchall()


# =========================================================
# COBROS: FUNCIÓN INTERNA
# =========================================================

def _cobros_en_periodo(conexion, desde, hasta):
    """
    Calcula el dinero recibido entre dos fechas.

    Incluye:
    - Cobros iniciales de ventas realizadas en el período.
    - Pagos de deudas recibidos en el período,
      aunque la venta sea de una fecha anterior.
    """

    cobros_iniciales = conexion.execute("""
        SELECT COALESCE(SUM(
            v.monto_cobrado - COALESCE((
                SELECT SUM(p.monto)
                FROM pagos p
                WHERE p.venta_id = v.id
            ), 0)
        ), 0)
        FROM ventas v
        WHERE DATE(v.fecha) BETWEEN ? AND ?
    """, (desde, hasta)).fetchone()[0]

    pagos_recibidos = conexion.execute("""
        SELECT COALESCE(SUM(monto), 0)
        FROM pagos
        WHERE DATE(fecha) BETWEEN ? AND ?
    """, (desde, hasta)).fetchone()[0]

    return cobros_iniciales + pagos_recibidos


# =========================================================
# RESUMEN DEL PANEL PRINCIPAL
# =========================================================

def obtener_ventas_hoy():

    hoy = fecha_hoy()

    with conectar() as conexion:

        cursor = conexion.execute("""
            SELECT COALESCE(SUM(total), 0)
            FROM ventas
            WHERE DATE(fecha) = ?
        """, (hoy,))

        return cursor.fetchone()[0]


def obtener_dinero_cobrado_hoy():

    hoy = fecha_hoy()

    with conectar() as conexion:

        return _cobros_en_periodo(
            conexion,
            hoy,
            hoy
        )


def obtener_deudas_pendientes():

    with conectar() as conexion:

        cursor = conexion.execute("""
            SELECT COALESCE(SUM(total - monto_cobrado), 0)
            FROM ventas
            WHERE forma_pago = 'Crédito'
            AND total > monto_cobrado
        """)

        return cursor.fetchone()[0]


# =========================================================
# CONTROL DE CAJA
# =========================================================

def obtener_caja_abierta():

    with conectar() as conexion:

        return _caja_abierta_en(conexion.cursor())


def caja_vencida():

    caja = obtener_caja_abierta()

    if caja is None:
        return False

    return _es_vencida(caja)


def abrir_caja(monto_inicial):

    if not numero_valido(monto_inicial) or monto_inicial < 0:
        return False, "El monto inicial no es válido."

    try:

        with conectar() as conexion:

            conexion.execute("BEGIN IMMEDIATE")

            if _caja_abierta_en(conexion.cursor()):
                return False, "Ya existe una caja abierta."

            cursor = conexion.execute("""
                INSERT INTO cajas (fecha_apertura, monto_inicial)
                VALUES (?, ?)
            """, (ahora(), monto_inicial))

            return True, cursor.lastrowid

    except sqlite3.IntegrityError:
        return False, "Ya existe una caja abierta."

    except sqlite3.Error as error:
        return False, f"Error al abrir la caja: {error}"


def registrar_movimiento_caja(tipo, concepto, monto):

    if tipo not in ("Entrada", "Salida"):
        return False, "Tipo de movimiento no válido."

    if not isinstance(concepto, str) or not concepto.strip():
        return False, "El concepto es obligatorio."

    if not numero_valido(monto) or monto <= 0:
        return False, "El monto debe ser mayor que cero."

    try:

        with conectar() as conexion:

            conexion.execute("BEGIN IMMEDIATE")

            cursor = conexion.cursor()

            caja_id, error = _caja_para_efectivo(
                cursor,
                "un movimiento de caja"
            )

            if error:
                return False, error

            cursor.execute("""
                INSERT INTO movimientos_caja
                (caja_id, fecha, tipo, concepto, monto)
                VALUES (?, ?, ?, ?, ?)
            """, (
                caja_id,
                ahora(),
                tipo,
                concepto.strip(),
                monto
            ))

        return True, "Movimiento registrado correctamente."

    except sqlite3.Error as error:
        return False, f"Error al registrar el movimiento: {error}"


def obtener_movimientos_caja(caja_id):

    with conectar() as conexion:

        cursor = conexion.execute("""
            SELECT fecha, tipo, concepto, monto
            FROM movimientos_caja
            WHERE caja_id = ?
            ORDER BY id DESC
        """, (caja_id,))

        return cursor.fetchall()


def calcular_saldo_caja(caja_id):

    with conectar() as conexion:

        return _saldo_caja_en(conexion.cursor(), caja_id)


def cerrar_caja(monto_contado):

    if not numero_valido(monto_contado) or monto_contado < 0:
        return False, "El monto contado no es válido."

    try:

        with conectar() as conexion:

            conexion.execute("BEGIN IMMEDIATE")

            cursor = conexion.cursor()

            caja = _caja_abierta_en(cursor)

            if caja is None:
                return False, "No hay una caja abierta."

            saldo_esperado = _saldo_caja_en(cursor, caja[0])

            diferencia = monto_contado - saldo_esperado

            cursor.execute("""
                UPDATE cajas
                SET fecha_cierre = ?,
                    monto_contado = ?,
                    diferencia = ?,
                    estado = 'Cerrada'
                WHERE id = ?
                AND estado = 'Abierta'
            """, (
                ahora(),
                monto_contado,
                diferencia,
                caja[0]
            ))

            if cursor.rowcount == 0:
                return False, "La caja ya fue cerrada."

        return True, diferencia

    except sqlite3.Error as error:
        return False, f"Error al cerrar la caja: {error}"


def listar_cajas():

    with conectar() as conexion:

        cursor = conexion.execute("""
            SELECT
                id,
                fecha_apertura,
                monto_inicial,
                fecha_cierre,
                monto_contado,
                diferencia,
                estado
            FROM cajas
            ORDER BY id DESC
        """)

        return cursor.fetchall()


# =========================================================
# GASTOS
# =========================================================

CATEGORIAS_GASTO = (
    "Electricidad",
    "Agua",
    "Transporte",
    "Limpieza",
    "Otros"
)


def registrar_gasto(concepto, categoria, monto, forma_pago):

    if not isinstance(concepto, str):
        return False, "El concepto no es válido."

    concepto = concepto.strip()

    if not concepto:
        return False, "El concepto es obligatorio."

    if categoria not in CATEGORIAS_GASTO:
        return False, "La categoría no es válida."

    if not numero_valido(monto) or monto <= 0:
        return False, "El monto debe ser mayor que cero."

    if forma_pago not in ("Efectivo", "Transferencia"):
        return False, "La forma de pago no es válida."

    fecha = ahora()

    try:

        with conectar() as conexion:

            conexion.execute("BEGIN IMMEDIATE")

            caja_id = None

            if forma_pago == "Efectivo":

                caja_id, error = _caja_para_efectivo(
                    conexion.cursor(),
                    "un gasto en efectivo"
                )

                if error:
                    return False, error

            conexion.execute("""
                INSERT INTO gastos
                (fecha, concepto, categoria, monto, forma_pago, caja_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                fecha,
                concepto,
                categoria,
                monto,
                forma_pago,
                caja_id
            ))

            if forma_pago == "Efectivo":

                conexion.execute("""
                    INSERT INTO movimientos_caja
                    (caja_id, fecha, tipo, concepto, monto)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    caja_id,
                    fecha,
                    "Salida",
                    f"Gasto: {concepto}",
                    monto
                ))

        return True, "Gasto registrado correctamente."

    except sqlite3.Error as error:
        return False, f"Error al registrar el gasto: {error}"


def listar_gastos():

    with conectar() as conexion:

        cursor = conexion.execute("""
            SELECT fecha, concepto, categoria, monto, forma_pago
            FROM gastos
            ORDER BY id DESC
        """)

        return cursor.fetchall()


# =========================================================
# GANANCIAS
# =========================================================

def calcular_ganancias(desde, hasta):
    """
    Las ventas y sus costos se contabilizan por fecha de venta.
    Los cobros se contabilizan por fecha de recepción.
    Las deudas pendientes corresponden a las ventas del período.
    """

    with conectar() as conexion:

        ingresos, costo = conexion.execute("""
            SELECT
                COALESCE(SUM(total), 0),
                COALESCE(SUM(cantidad_kg * costo_kg), 0)
            FROM ventas
            WHERE DATE(fecha) BETWEEN ? AND ?
        """, (desde, hasta)).fetchone()

        gastos = conexion.execute("""
            SELECT COALESCE(SUM(monto), 0)
            FROM gastos
            WHERE DATE(fecha) BETWEEN ? AND ?
        """, (desde, hasta)).fetchone()[0]

        cobrado = _cobros_en_periodo(
            conexion,
            desde,
            hasta
        )

        pendiente = conexion.execute("""
            SELECT COALESCE(SUM(total - monto_cobrado), 0)
            FROM ventas
            WHERE DATE(fecha) BETWEEN ? AND ?
            AND forma_pago = 'Crédito'
        """, (desde, hasta)).fetchone()[0]

    ganancia_bruta = ingresos - costo
    ganancia_neta = ganancia_bruta - gastos

    return {
        "ingresos": ingresos,
        "costo": costo,
        "ganancia_bruta": ganancia_bruta,
        "gastos": gastos,
        "ganancia_neta": ganancia_neta,
        "cobrado": cobrado,
        "pendiente": pendiente
    }


# =========================================================
# REPORTES
# =========================================================

def reporte_ventas_diarias(desde, hasta):
    """
    Devuelve una fila por día con ventas o cobros.

    (dia, cantidad_ventas, kilos, total_vendido, total_cobrado)

    El dinero cobrado se agrupa por la fecha real de recepción.
    También aparecen días en los que hubo cobros pero no ventas.
    """

    with conectar() as conexion:

        cursor = conexion.execute("""
            WITH fechas AS (
                SELECT DATE(fecha) AS dia
                FROM ventas
                WHERE DATE(fecha) BETWEEN ? AND ?

                UNION

                SELECT DATE(fecha) AS dia
                FROM pagos
                WHERE DATE(fecha) BETWEEN ? AND ?
            ),

            ventas_dia AS (
                SELECT
                    DATE(fecha) AS dia,
                    COUNT(*) AS cantidad,
                    SUM(cantidad_kg) AS kilos,
                    SUM(total) AS vendido
                FROM ventas
                WHERE DATE(fecha) BETWEEN ? AND ?
                GROUP BY DATE(fecha)
            ),

            cobros_iniciales AS (
                SELECT
                    DATE(v.fecha) AS dia,
                    SUM(
                        v.monto_cobrado - COALESCE((
                            SELECT SUM(p.monto)
                            FROM pagos p
                            WHERE p.venta_id = v.id
                        ), 0)
                    ) AS cobrado
                FROM ventas v
                WHERE DATE(v.fecha) BETWEEN ? AND ?
                GROUP BY DATE(v.fecha)
            ),

            pagos_dia AS (
                SELECT
                    DATE(fecha) AS dia,
                    SUM(monto) AS cobrado
                FROM pagos
                WHERE DATE(fecha) BETWEEN ? AND ?
                GROUP BY DATE(fecha)
            )

            SELECT
                fechas.dia,
                COALESCE(ventas_dia.cantidad, 0),
                COALESCE(ventas_dia.kilos, 0),
                COALESCE(ventas_dia.vendido, 0),
                COALESCE(cobros_iniciales.cobrado, 0)
                    + COALESCE(pagos_dia.cobrado, 0)

            FROM fechas

            LEFT JOIN ventas_dia
                ON fechas.dia = ventas_dia.dia

            LEFT JOIN cobros_iniciales
                ON fechas.dia = cobros_iniciales.dia

            LEFT JOIN pagos_dia
                ON fechas.dia = pagos_dia.dia

            ORDER BY fechas.dia DESC
        """, (
            desde, hasta,
            desde, hasta,
            desde, hasta,
            desde, hasta,
            desde, hasta
        ))

        return cursor.fetchall()


def reporte_productos_vendidos(desde, hasta):
    """
    (producto, kilos, total_vendido, ganancia_bruta)
    """

    with conectar() as conexion:

        cursor = conexion.execute("""
            SELECT
                producto_nombre,
                SUM(cantidad_kg),
                SUM(total),
                SUM(total - cantidad_kg * costo_kg)
            FROM ventas
            WHERE DATE(fecha) BETWEEN ? AND ?
            GROUP BY producto_nombre
            ORDER BY SUM(cantidad_kg) DESC
        """, (desde, hasta))

        return cursor.fetchall()


def reporte_gastos_categoria(desde, hasta):
    """
    (categoria, cantidad_gastos, total)
    """

    with conectar() as conexion:

        cursor = conexion.execute("""
            SELECT
                categoria,
                COUNT(*),
                SUM(monto)
            FROM gastos
            WHERE DATE(fecha) BETWEEN ? AND ?
            GROUP BY categoria
            ORDER BY SUM(monto) DESC
        """, (desde, hasta))

        return cursor.fetchall()


def reporte_deudas_clientes():
    """
    (cliente, cantidad_deudas, total_adeudado)
    """

    with conectar() as conexion:

        cursor = conexion.execute("""
            SELECT
                COALESCE(clientes.nombre, 'Sin cliente'),
                COUNT(*),
                SUM(ventas.total - ventas.monto_cobrado)
            FROM ventas
            LEFT JOIN clientes
                ON ventas.cliente_id = clientes.id
            WHERE ventas.forma_pago = 'Crédito'
            AND ventas.total > ventas.monto_cobrado
            GROUP BY ventas.cliente_id
            ORDER BY SUM(
                ventas.total - ventas.monto_cobrado
            ) DESC
        """)

        return cursor.fetchall()


def reporte_ventas_mensuales():
    """
    Devuelve los últimos 12 meses con ventas o cobros.

    (mes, cantidad_ventas, kilos, total_vendido, total_cobrado)

    Los cobros se agrupan por el mes en que se recibieron.
    """

    with conectar() as conexion:

        cursor = conexion.execute("""
            WITH meses AS (
                SELECT strftime('%Y-%m', fecha) AS mes
                FROM ventas

                UNION

                SELECT strftime('%Y-%m', fecha) AS mes
                FROM pagos
            ),

            ultimos_meses AS (
                SELECT mes
                FROM meses
                ORDER BY mes DESC
                LIMIT 12
            ),

            ventas_mes AS (
                SELECT
                    strftime('%Y-%m', fecha) AS mes,
                    COUNT(*) AS cantidad,
                    SUM(cantidad_kg) AS kilos,
                    SUM(total) AS vendido
                FROM ventas
                GROUP BY strftime('%Y-%m', fecha)
            ),

            cobros_iniciales AS (
                SELECT
                    strftime('%Y-%m', v.fecha) AS mes,
                    SUM(
                        v.monto_cobrado - COALESCE((
                            SELECT SUM(p.monto)
                            FROM pagos p
                            WHERE p.venta_id = v.id
                        ), 0)
                    ) AS cobrado
                FROM ventas v
                GROUP BY strftime('%Y-%m', v.fecha)
            ),

            pagos_mes AS (
                SELECT
                    strftime('%Y-%m', fecha) AS mes,
                    SUM(monto) AS cobrado
                FROM pagos
                GROUP BY strftime('%Y-%m', fecha)
            )

            SELECT
                ultimos_meses.mes,
                COALESCE(ventas_mes.cantidad, 0),
                COALESCE(ventas_mes.kilos, 0),
                COALESCE(ventas_mes.vendido, 0),
                COALESCE(cobros_iniciales.cobrado, 0)
                    + COALESCE(pagos_mes.cobrado, 0)

            FROM ultimos_meses

            LEFT JOIN ventas_mes
                ON ultimos_meses.mes = ventas_mes.mes

            LEFT JOIN cobros_iniciales
                ON ultimos_meses.mes = cobros_iniciales.mes

            LEFT JOIN pagos_mes
                ON ultimos_meses.mes = pagos_mes.mes

            ORDER BY ultimos_meses.mes DESC
        """)

        return cursor.fetchall()
