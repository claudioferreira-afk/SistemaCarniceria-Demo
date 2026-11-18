
import logging
import os
import time
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

from flask import (
    Flask, render_template, request, redirect, url_for, flash, session
)
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash

from database.db import (
    crear_tablas,

    # Productos
    registrar_producto,
    listar_productos,
    agregar_stock,
    editar_producto,
    eliminar_producto,

    # Ventas
    registrar_venta,
    listar_ventas,

    # Clientes
    registrar_cliente,
    listar_clientes,

    # Deudas y pagos
    listar_deudas,
    registrar_pago,
    listar_pagos,

    # Panel principal
    obtener_ventas_hoy,
    obtener_dinero_cobrado_hoy,
    obtener_deudas_pendientes,

    # Control de caja
    obtener_caja_abierta,
    abrir_caja,
    registrar_movimiento_caja,
    obtener_movimientos_caja,
    calcular_saldo_caja,
    cerrar_caja,
    listar_cajas,
    caja_vencida,

    # Gastos
    CATEGORIAS_GASTO,
    registrar_gasto,
    listar_gastos,

    # Ganancias
    calcular_ganancias,

    # Reportes
    reporte_ventas_diarias,
    reporte_productos_vendidos,
    reporte_gastos_categoria,
    reporte_deudas_clientes,
    reporte_ventas_mensuales
)


# =========================
# CONFIGURACIÓN
# =========================

app = Flask(
    __name__,
    template_folder="app/templates",
    static_folder="app/static"
)

csrf = CSRFProtect(app)
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://"
)


# =========================
# CONTRASEÑA Y SESIÓN
# =========================




DEMO_PASSWORD_HASH = os.getenv("DEMO_PASSWORD_HASH", "")

app.secret_key = os.getenv("SECRET_KEY")

if not app.secret_key:
    raise RuntimeError(
        "Falta configurar SECRET_KEY en el archivo .env"
    )


# Protección de las cookies de sesión
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=(
        os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"
    )
)


MAX_INTENTOS = 5
MINUTOS_BLOQUEO = 5

intentos_fallidos = {
    "cantidad": 0,
    "hasta": 0
}


@app.before_request
def exigir_login():

    if not DEMO_PASSWORD_HASH:
        return render_template(
            "error.html",
            titulo="Falta definir la contraseña",
            mensaje="Configurá DEMO_PASSWORD_HASH en las variables de entorno."
        ), 503

    if request.endpoint in ("login", "static"):
        return None

    if not session.get("autenticado"):
        return redirect(url_for("login"))

    return None
@app.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute", methods=["POST"])
def login():

    if request.method == "POST":

        if time.time() < intentos_fallidos["hasta"]:
            flash(
                "Demasiados intentos. Esperá unos minutos.",
                "error"
            )
            return redirect(url_for("login"))

        clave = request.form.get("clave", "")
        clave_hash = DEMO_PASSWORD_HASH

        if clave_hash and check_password_hash(clave_hash, clave):
            intentos_fallidos["cantidad"] = 0

            session.clear()
            session["autenticado"] = True

            return redirect(url_for("inicio"))

        intentos_fallidos["cantidad"] += 1

        if intentos_fallidos["cantidad"] >= MAX_INTENTOS:
            intentos_fallidos["cantidad"] = 0
            intentos_fallidos["hasta"] = (
                time.time() + MINUTOS_BLOQUEO * 60
            )

        flash("Contraseña incorrecta.", "error")
        return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/salir", methods=["POST"])
def salir():
    session.clear()
    return redirect(url_for("login"))


# =========================
# REGISTRO Y MANEJO DE ERRORES
# =========================

RUTA_LOG = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "errores.log"
)

logging.basicConfig(
    filename=RUTA_LOG,
    level=logging.WARNING,
    format="%(asctime)s %(levelname)s %(message)s",
    encoding="utf-8"
)


@app.errorhandler(404)
def pagina_no_encontrada(error):
    return render_template(
        "error.html",
        titulo="Página no encontrada",
        mensaje="La dirección que abriste no existe en el sistema."
    ), 404


@app.errorhandler(Exception)
def error_inesperado(error):

    if isinstance(error, HTTPException):
        return render_template(
            "error.html",
            titulo="No se pudo completar la acción",
            mensaje="El sistema no pudo procesar la solicitud."
        ), error.code

    app.logger.exception(
        "Error inesperado en %s",
        request.path
    )

    return render_template(
        "error.html",
        titulo="Ocurrió un problema",
        mensaje="El sistema tuvo un error inesperado. "
                "No se perdió ningún dato guardado."
    ), 500


# =========================
# PANEL PRINCIPAL
# =========================

@app.route("/")
def inicio():

    return render_template(
        "index.html",
        ventas_hoy=obtener_ventas_hoy(),
        dinero_cobrado_hoy=obtener_dinero_cobrado_hoy(),
        deudas_pendientes=obtener_deudas_pendientes()
    )


# =========================
# PRODUCTOS
# =========================

@app.route("/productos", methods=["GET", "POST"])
def productos():

    if request.method == "POST":

        try:
            nombre = request.form["nombre"].strip()
            costo_kg = float(request.form["costo_kg"])
            precio_kg = float(request.form["precio_kg"])
            stock_kg = float(request.form["stock_kg"])
            stock_minimo = float(request.form["stock_minimo"])

        except (ValueError, KeyError):
            flash(
                "Los datos del producto no son válidos.",
                "error"
            )
            return redirect(url_for("productos"))

        ok = registrar_producto(
            nombre,
            costo_kg,
            precio_kg,
            stock_kg,
            stock_minimo
        )

        if ok:
            flash(
                "Producto registrado correctamente.",
                "ok"
            )
        else:
            flash(
                "No se pudo registrar. Revisá los datos o si el producto ya existe.",
                "error"
            )

        return redirect(url_for("productos"))

    return render_template(
        "productos.html",
        productos=listar_productos()
    )


@app.route("/agregar-stock", methods=["POST"])
def agregar_stock_ruta():

    try:
        producto_id = int(request.form["producto_id"])
        cantidad = float(request.form["cantidad"])

    except (ValueError, KeyError):
        flash(
            "Los datos del stock no son válidos.",
            "error"
        )
        return redirect(url_for("productos"))

    if cantidad <= 0:
        flash(
            "La cantidad debe ser mayor que cero.",
            "error"
        )
        return redirect(url_for("productos"))

    if agregar_stock(producto_id, cantidad):
        flash(
            "Stock actualizado correctamente.",
            "ok"
        )
    else:
        flash(
            "No se pudo actualizar el stock.",
            "error"
        )

    return redirect(url_for("productos"))


@app.route("/editar-producto/<int:producto_id>", methods=["POST"])
def editar_producto_ruta(producto_id):

    try:
        nombre = request.form["nombre"].strip()
        costo_kg = float(request.form["costo_kg"])
        precio_kg = float(request.form["precio_kg"])
        stock_minimo = float(request.form["stock_minimo"])

    except (ValueError, KeyError):
        flash(
            "Los datos del producto no son válidos.",
            "error"
        )
        return redirect(url_for("productos"))

    ok = editar_producto(
        producto_id,
        nombre,
        costo_kg,
        precio_kg,
        stock_minimo
    )

    if ok:
        flash(
            "Producto actualizado correctamente.",
            "ok"
        )
    else:
        flash(
            "No se pudo actualizar. Revisá los datos o si el nombre ya existe.",
            "error"
        )

    return redirect(url_for("productos"))


@app.route("/eliminar-producto/<int:producto_id>", methods=["POST"])
def eliminar_producto_ruta(producto_id):

    if eliminar_producto(producto_id):
        flash(
            "Producto eliminado correctamente.",
            "ok"
        )
    else:
        flash(
            "No se pudo eliminar el producto. Puede estar relacionado con ventas.",
            "error"
        )

    return redirect(url_for("productos"))


# =========================
# VENTAS
# =========================

@app.route("/ventas", methods=["GET", "POST"])
def ventas():

    if request.method == "POST":

        try:
            producto_id = int(request.form["producto_id"])
            cantidad = float(request.form["cantidad"])

        except (ValueError, KeyError):
            flash(
                "Datos de venta no válidos.",
                "error"
            )
            return redirect(url_for("ventas"))

        forma_pago = request.form.get("forma_pago", "")
        cliente_id = request.form.get("cliente_id")

        if cliente_id:
            try:
                cliente_id = int(cliente_id)

            except ValueError:
                flash("Cliente no válido.", "error")
                return redirect(url_for("ventas"))

        else:
            cliente_id = None

        ok, resultado = registrar_venta(
            producto_id,
            cantidad,
            forma_pago,
            cliente_id
        )

        if ok:
            total = "{:,.0f}".format(resultado).replace(",", ".")

            flash(
                f"Venta registrada correctamente. Total: Gs. {total}",
                "ok"
            )
        else:
            flash(resultado, "error")

        return redirect(url_for("ventas"))

    return render_template(
        "ventas.html",
        productos=listar_productos(),
        clientes=listar_clientes()
    )


# =========================
# HISTORIAL DE VENTAS
# =========================

@app.route("/historial")
def historial():

    return render_template(
        "historial.html",
        ventas=listar_ventas()
    )


# =========================
# CLIENTES
# =========================

@app.route("/clientes", methods=["GET", "POST"])
def clientes():

    if request.method == "POST":

        nombre = request.form.get("nombre", "").strip()
        telefono = request.form.get("telefono", "").strip()
        direccion = request.form.get("direccion", "").strip()

        if not nombre:
            flash(
                "El nombre del cliente es obligatorio.",
                "error"
            )
            return redirect(url_for("clientes"))

        registrar_cliente(
            nombre,
            telefono,
            direccion
        )

        flash(
            "Cliente registrado correctamente.",
            "ok"
        )

        return redirect(url_for("clientes"))

    return render_template(
        "clientes.html",
        clientes=listar_clientes()
    )


# =========================
# DEUDAS Y PAGOS
# =========================

@app.route("/deudas")
def deudas():

    return render_template(
        "deudas.html",
        deudas=listar_deudas()
    )


@app.route("/pagos")
def pagos():

    return render_template(
        "pagos.html",
        pagos=listar_pagos()
    )


@app.route("/registrar-pago", methods=["POST"])
def registrar_pago_ruta():

    try:
        venta_id = int(request.form["venta_id"])
        monto = float(request.form["monto"])
        forma_pago = request.form["forma_pago"]

    except (ValueError, KeyError):
        flash(
            "Datos del pago no válidos.",
            "error"
        )
        return redirect(url_for("deudas"))

    ok, resultado = registrar_pago(
        venta_id,
        monto,
        forma_pago
    )

    if ok:
        flash(
            "Pago registrado correctamente.",
            "ok"
        )
    else:
        flash(resultado, "error")

    return redirect(url_for("deudas"))


# =========================
# CONTROL DE CAJA
# =========================

@app.route("/caja")
def caja():

    caja_actual = obtener_caja_abierta()

    if caja_actual:
        saldo = calcular_saldo_caja(caja_actual[0])
        movimientos = obtener_movimientos_caja(caja_actual[0])

    else:
        saldo = 0
        movimientos = []

    return render_template(
        "caja.html",
        caja=caja_actual,
        saldo=saldo,
        movimientos=movimientos,
        historial_cajas=listar_cajas(),
        vencida=caja_vencida()
    )


@app.route("/abrir-caja", methods=["POST"])
def abrir_caja_ruta():

    try:
        monto_inicial = float(request.form["monto_inicial"])

    except (ValueError, KeyError):
        flash(
            "El monto inicial no es válido.",
            "error"
        )
        return redirect(url_for("caja"))

    ok, resultado = abrir_caja(monto_inicial)

    if ok:
        flash(
            "Caja abierta correctamente.",
            "ok"
        )
    else:
        flash(resultado, "error")

    return redirect(url_for("caja"))


@app.route("/movimiento-caja", methods=["POST"])
def movimiento_caja_ruta():

    tipo = request.form.get("tipo", "")
    concepto = request.form.get("concepto", "")

    try:
        monto = float(request.form["monto"])

    except (ValueError, KeyError):
        flash(
            "El monto ingresado no es válido.",
            "error"
        )
        return redirect(url_for("caja"))

    ok, resultado = registrar_movimiento_caja(
        tipo,
        concepto,
        monto
    )

    if ok:
        flash(
            "Movimiento registrado correctamente.",
            "ok"
        )
    else:
        flash(resultado, "error")

    return redirect(url_for("caja"))


@app.route("/cerrar-caja", methods=["POST"])
def cerrar_caja_ruta():

    try:
        monto_contado = float(request.form["monto_contado"])

    except (ValueError, KeyError):
        flash(
            "El monto contado no es válido.",
            "error"
        )
        return redirect(url_for("caja"))

    ok, resultado = cerrar_caja(monto_contado)

    if ok:
        diferencia = "{:,.0f}".format(resultado).replace(",", ".")

        flash(
            f"Caja cerrada correctamente. Diferencia: Gs. {diferencia}",
            "ok"
        )
    else:
        flash(resultado, "error")

    return redirect(url_for("caja"))


# =========================
# GASTOS
# =========================

@app.route("/gastos", methods=["GET", "POST"])
def gastos():

    if request.method == "POST":

        concepto = request.form.get("concepto", "")
        categoria = request.form.get("categoria", "")
        forma_pago = request.form.get("forma_pago", "")

        try:
            monto = float(request.form["monto"])

        except (ValueError, KeyError):
            flash(
                "El monto ingresado no es válido.",
                "error"
            )
            return redirect(url_for("gastos"))

        ok, mensaje = registrar_gasto(
            concepto,
            categoria,
            monto,
            forma_pago
        )

        flash(
            mensaje,
            "ok" if ok else "error"
        )

        return redirect(url_for("gastos"))

    return render_template(
        "gastos.html",
        categorias=CATEGORIAS_GASTO,
        gastos=listar_gastos()
    )


# =========================
# GANANCIAS Y REPORTES
# =========================

def leer_periodo(destino):
    """Lee 'desde' y 'hasta' de la dirección. Devuelve
    (desde, hasta, hoy, primer_dia_mes, redirección_o_None)."""

    hoy = datetime.now().strftime("%Y-%m-%d")
    primer_dia_mes = datetime.now().strftime("%Y-%m-01")

    desde = request.args.get("desde", primer_dia_mes)
    hasta = request.args.get("hasta", hoy)

    try:
        datetime.strptime(desde, "%Y-%m-%d")
        datetime.strptime(hasta, "%Y-%m-%d")

    except ValueError:
        flash(
            "Las fechas no son válidas.",
            "error"
        )
        return (
            desde,
            hasta,
            hoy,
            primer_dia_mes,
            redirect(url_for(destino))
        )

    if desde > hasta:
        flash(
            "La fecha «desde» no puede ser posterior a «hasta».",
            "error"
        )

        return (
            desde,
            hasta,
            hoy,
            primer_dia_mes,
            redirect(url_for(destino))
        )

    return (
        desde,
        hasta,
        hoy,
        primer_dia_mes,
        None
    )


@app.route("/ganancias")
def ganancias():

    desde, hasta, hoy, primer_dia_mes, redireccion = leer_periodo(
        "ganancias"
    )

    if redireccion:
        return redireccion

    return render_template(
        "ganancias.html",
        resultado=calcular_ganancias(desde, hasta),
        desde=desde,
        hasta=hasta,
        hoy=hoy,
        primer_dia_mes=primer_dia_mes
    )


@app.route("/reportes")
def reportes():

    desde, hasta, hoy, primer_dia_mes, redireccion = leer_periodo(
        "reportes"
    )

    if redireccion:
        return redireccion

    return render_template(
        "reportes.html",
        ventas_diarias=reporte_ventas_diarias(desde, hasta),
        ventas_mensuales=reporte_ventas_mensuales(),
        productos_vendidos=reporte_productos_vendidos(desde, hasta),
        gastos_categoria=reporte_gastos_categoria(desde, hasta),
        deudas_clientes=reporte_deudas_clientes(),
        historial_cajas=listar_cajas(),
        desde=desde,
        hasta=hasta,
        hoy=hoy,
        primer_dia_mes=primer_dia_mes
    )

# =========================
# INICIALIZACIÓN DE BASE DE DATOS
# =========================
crear_tablas()

if __name__ == "__main__":
    app.run(debug=False)
