"""
Plataforma PITS: registro persistente (SQLite) y API del panel de administración.

Guarda lo que antes se perdía: conversaciones y cotizaciones del chatbot web y los pedidos del tótem.
Usa su propia base, data/plataforma.db (se crea sola), separada del catálogo data/pits.db.

Este módulo NO cambia el comportamiento del chatbot ni del tótem: si algo falla al registrar,
el chat y los pedidos siguen funcionando (los registros se hacen con "intentar y seguir").

Rutas que registra (ver registrar_rutas):
  Públicas, para el tótem y la bodega:   POST /api/pedidos · GET /api/pedidos
                                          POST /api/pedidos/{numero}/estado · POST /api/pedidos/reiniciar
  Públicas, formulario de la página:      POST /api/contacto
  Panel CLIENTE (rol cliente o admin):    /api/cliente/resumen | cotizaciones | pedidos | conversaciones
                                          | conversaciones/{id} | catalogo
  Panel ADMIN (solo rol admin):           /api/admin/resumen | solicitudes | canales
  Sesión (auth.py):                       /api/auth/login | logout | yo | cambiar-clave

Los paneles exigen iniciar sesión (usuario y contraseña, ver auth.py y crear_usuario.py).
"""
import json
import os
import re
import smtplib
import sqlite3
import threading
import time
from email.message import EmailMessage
from contextlib import closing
from datetime import datetime, timedelta
from typing import List

import auth
from fastapi import HTTPException, Request
from pydantic import BaseModel, Field

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "plataforma.db")

NUMERO_PEDIDO_INICIAL = 104   # el primer pedido del tótem es el #104 (igual que en la demo)
MAX_ITEMS_PEDIDO = 50
ESTADOS_PEDIDO = ["Pedido recibido", "En preparación", "Listo para retirar", "Entregado"]


# ---------------------------------------------------------------- base de datos
def _ahora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _con():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    return con


def iniciar():
    """Crea las tablas si no existen (incluidas las de usuarios). Es seguro llamarla en cada arranque."""
    auth.iniciar()
    with closing(_con()) as con, con:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS conversaciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                canal TEXT NOT NULL,
                sesion TEXT NOT NULL,
                creada TEXT NOT NULL,
                actualizada TEXT NOT NULL,
                UNIQUE (canal, sesion)
            );
            CREATE TABLE IF NOT EXISTS mensajes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversacion_id INTEGER NOT NULL REFERENCES conversaciones(id),
                rol TEXT NOT NULL,
                texto TEXT NOT NULL,
                creado TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_mensajes_conv ON mensajes(conversacion_id);
            CREATE TABLE IF NOT EXISTS cotizaciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                canal TEXT NOT NULL,
                sesion TEXT NOT NULL,
                archivo TEXT,
                n_items INTEGER NOT NULL,
                total INTEGER NOT NULL,
                items_json TEXT NOT NULL,
                creada TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS pedidos (
                numero INTEGER PRIMARY KEY AUTOINCREMENT,
                canal TEXT NOT NULL DEFAULT 'totem',
                items_json TEXT NOT NULL,
                total INTEGER NOT NULL,
                estado INTEGER NOT NULL DEFAULT 0,
                hist_json TEXT NOT NULL,
                creado TEXT NOT NULL,
                actualizado TEXT NOT NULL,
                archivado INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS solicitudes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                empresa TEXT NOT NULL,
                correo TEXT NOT NULL,
                solucion TEXT NOT NULL,
                detalle TEXT NOT NULL,
                creada TEXT NOT NULL,
                correo_estado TEXT NOT NULL DEFAULT 'pendiente'
            );
            """
        )
        # El primer pedido será el #104: se fija el contador solo si aún no existe
        con.execute(
            "INSERT INTO sqlite_sequence(name, seq) "
            "SELECT 'pedidos', ? WHERE NOT EXISTS (SELECT 1 FROM sqlite_sequence WHERE name = 'pedidos')",
            (NUMERO_PEDIDO_INICIAL - 1,),
        )


# ---------------------------------------------------------------- registro desde los canales
def registrar_intercambio(canal: str, sesion: str, texto_cliente: str, texto_bot: str):
    """Guarda un mensaje del cliente y la respuesta del bot en su conversación."""
    ahora = _ahora()
    with closing(_con()) as con, con:
        fila = con.execute("SELECT id FROM conversaciones WHERE canal = ? AND sesion = ?", (canal, sesion)).fetchone()
        if fila:
            conv_id = fila["id"]
            con.execute("UPDATE conversaciones SET actualizada = ? WHERE id = ?", (ahora, conv_id))
        else:
            conv_id = con.execute(
                "INSERT INTO conversaciones (canal, sesion, creada, actualizada) VALUES (?, ?, ?, ?)",
                (canal, sesion, ahora, ahora),
            ).lastrowid
        con.executemany(
            "INSERT INTO mensajes (conversacion_id, rol, texto, creado) VALUES (?, ?, ?, ?)",
            [(conv_id, "cliente", texto_cliente, ahora), (conv_id, "bot", texto_bot, ahora)],
        )


def registrar_cotizacion(canal: str, sesion: str, archivo: str, carrito: list):
    """Guarda una cotización generada (productos y total) para poder verla después."""
    items = [{"id": p.get("id"), "nombre": p.get("nombre"), "precio": int(p.get("precio", 0))} for p in carrito]
    total = sum(i["precio"] for i in items)
    with closing(_con()) as con, con:
        con.execute(
            "INSERT INTO cotizaciones (canal, sesion, archivo, n_items, total, items_json, creada) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (canal, sesion, archivo, len(items), total, json.dumps(items, ensure_ascii=False), _ahora()),
        )


# ---------------------------------------------------------------- pedidos del tótem
class ItemPedido(BaseModel):
    id: str = Field(..., max_length=40)
    nombre: str = Field(..., max_length=120)
    precio: int = Field(..., ge=0, le=10_000_000)
    cant: int = Field(..., ge=1, le=99)


class PedidoEntrada(BaseModel):
    items: List[ItemPedido] = Field(..., min_length=1, max_length=MAX_ITEMS_PEDIDO)


# ---------------------------------------------------------------- formulario de contacto
SOLUCIONES = {"todas": "Las 3 soluciones (ecosistema completo)", "api": "Opción 1: API Webhook WhatsApp",
              "app": "Opción 2: Chatbot web incrustable", "totem": "Opción 3: Tótem de autoatención"}
_RE_CORREO = re.compile(r"^[^@\s<>\"',;]+@[^@\s<>\"',;]+\.[^@\s<>\"',;]{2,}$")
_ENVIOS = {}            # ip -> instantes de los últimos envíos (límite simple contra abuso)
_ENVIOS_LOCK = threading.Lock()
MAX_ENVIOS = 5
VENTANA_SEG = 600


class ContactoEntrada(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=100)
    empresa: str = Field(..., min_length=1, max_length=100)
    correo: str = Field(..., min_length=5, max_length=150)
    solucion: str = Field("todas", max_length=20)
    detalle: str = Field("", max_length=2000)
    sitio_web: str = Field("", max_length=200)   # campo trampa para robots: las personas lo dejan vacío


def _una_linea(txt: str, maximo: int) -> str:
    return re.sub(r"[\r\n\t\x00-\x1f]+", " ", str(txt)).strip()[:maximo]


def correo_configurado() -> bool:
    return bool(os.environ.get("PITS_SMTP_USER", "").strip() and os.environ.get("PITS_SMTP_PASS", "").strip())


def _enviar_correo(sol_id: int, d: dict):
    """Envía el aviso por SMTP y anota el resultado. Nunca lanza errores ni escribe la contraseña en ningún lado."""
    estado = "no_configurado"
    if correo_configurado():
        try:
            usuario = os.environ["PITS_SMTP_USER"].strip()
            clave = os.environ["PITS_SMTP_PASS"].replace(" ", "").strip()
            destino = os.environ.get("PITS_SMTP_TO", "").strip() or usuario
            host = os.environ.get("PITS_SMTP_HOST", "").strip() or "smtp.gmail.com"
            puerto = int(os.environ.get("PITS_SMTP_PORT", "").strip() or 587)
            msg = EmailMessage()
            msg["Subject"] = "Nueva solicitud de contacto - " + _una_linea(d["empresa"], 60)
            msg["From"] = usuario
            msg["To"] = destino
            msg["Reply-To"] = d["correo"]
            msg.set_content(
                "Nueva solicitud recibida desde la página (N° %d)\n\nNombre: %s\nEmpresa: %s\nCorreo: %s\nSolución de interés: %s\n\nDetalles:\n%s\n"
                % (sol_id, d["nombre"], d["empresa"], d["correo"], SOLUCIONES.get(d["solucion"], d["solucion"]), d["detalle"] or "(sin detalles)")
            )
            with smtplib.SMTP(host, puerto, timeout=20) as smtp:
                smtp.starttls()
                smtp.login(usuario, clave)
                smtp.send_message(msg)
            estado = "enviado"
        except Exception as e:          # no se guarda el texto del error completo: podría incluir datos sensibles
            estado = "error: " + type(e).__name__
    try:
        with closing(_con()) as con, con:
            con.execute("UPDATE solicitudes SET correo_estado=? WHERE id=?", (estado, sol_id))
    except Exception as e:
        print("[plataforma] no se pudo anotar el estado del correo:", type(e).__name__)


def _permitir_envio(ip: str) -> bool:
    ahora = time.time()
    with _ENVIOS_LOCK:
        recientes = [t for t in _ENVIOS.get(ip, []) if ahora - t < VENTANA_SEG]
        if len(recientes) >= MAX_ENVIOS:
            _ENVIOS[ip] = recientes
            return False
        recientes.append(ahora)
        _ENVIOS[ip] = recientes
        if len(_ENVIOS) > 5000:
            _ENVIOS.clear()
        return True


def guardar_solicitud(data: ContactoEntrada) -> int:
    correo = _una_linea(data.correo, 150)
    if not _RE_CORREO.match(correo):
        raise HTTPException(status_code=422, detail="El correo no es válido")
    d = {"nombre": _una_linea(data.nombre, 100), "empresa": _una_linea(data.empresa, 100), "correo": correo,
         "solucion": data.solucion if data.solucion in SOLUCIONES else "todas", "detalle": data.detalle.replace("\x00", "").strip()}
    if not d["nombre"] or not d["empresa"]:
        raise HTTPException(status_code=422, detail="Faltan datos")
    with closing(_con()) as con, con:
        cur = con.execute(
            "INSERT INTO solicitudes(nombre,empresa,correo,solucion,detalle,creada,correo_estado) VALUES (?,?,?,?,?,?,?)",
            (d["nombre"], d["empresa"], d["correo"], d["solucion"], d["detalle"], _ahora(),
             "pendiente" if correo_configurado() else "no_configurado"),
        )
        sol_id = cur.lastrowid
    if correo_configurado():
        threading.Thread(target=_enviar_correo, args=(sol_id, d), daemon=True).start()
    return sol_id


def listar_solicitudes(limite: int, interes: str = "") -> list:
    with closing(_con()) as con:
        if interes in SOLUCIONES:
            filas = con.execute("SELECT * FROM solicitudes WHERE solucion=? ORDER BY id DESC LIMIT ?", (interes, _limite(limite))).fetchall()
        else:
            filas = con.execute("SELECT * FROM solicitudes ORDER BY id DESC LIMIT ?", (_limite(limite),)).fetchall()
    return [{k: f[k] for k in f.keys()} for f in filas]


class EstadoEntrada(BaseModel):
    estado: int = Field(..., ge=0, le=3)


def _pedido_dict(fila) -> dict:
    """Mismo formato que usa el navegador (totem/store.js): id = número de pedido."""
    return {
        "id": fila["numero"],
        "numero": fila["numero"],
        "canal": fila["canal"],
        "items": json.loads(fila["items_json"]),
        "total": fila["total"],
        "estado": fila["estado"],
        "hist": json.loads(fila["hist_json"]),
        "creado": fila["creado"],
        "actualizado": fila["actualizado"],
        "archivado": bool(fila["archivado"]),
    }


def crear_pedido(data: PedidoEntrada) -> dict:
    ahora = _ahora()
    items = [it.model_dump() for it in data.items]
    total = sum(i["precio"] * i["cant"] for i in items)   # el total siempre se recalcula en el servidor
    hist = [{"estado": 0, "ts": ahora}]
    with closing(_con()) as con, con:
        numero = con.execute(
            "INSERT INTO pedidos (canal, items_json, total, estado, hist_json, creado, actualizado) VALUES ('totem', ?, ?, 0, ?, ?, ?)",
            (json.dumps(items, ensure_ascii=False), total, json.dumps(hist), ahora, ahora),
        ).lastrowid
        return _pedido_dict(con.execute("SELECT * FROM pedidos WHERE numero = ?", (numero,)).fetchone())


def listar_pedidos_activos(limite: int = 50) -> list:
    with closing(_con()) as con:
        filas = con.execute(
            "SELECT * FROM (SELECT * FROM pedidos WHERE archivado = 0 ORDER BY numero DESC LIMIT ?) ORDER BY numero",
            (limite,),
        ).fetchall()
    return [_pedido_dict(f) for f in filas]


def cambiar_estado_pedido(numero: int, estado: int) -> dict:
    ahora = _ahora()
    with closing(_con()) as con, con:
        fila = con.execute("SELECT * FROM pedidos WHERE numero = ?", (numero,)).fetchone()
        if not fila:
            raise HTTPException(status_code=404, detail="Pedido no encontrado")
        if fila["estado"] != estado:
            hist = json.loads(fila["hist_json"]) + [{"estado": estado, "ts": ahora}]
            con.execute(
                "UPDATE pedidos SET estado = ?, hist_json = ?, actualizado = ? WHERE numero = ?",
                (estado, json.dumps(hist), ahora, numero),
            )
        return _pedido_dict(con.execute("SELECT * FROM pedidos WHERE numero = ?", (numero,)).fetchone())


def archivar_pedidos() -> int:
    """'Reiniciar demo': limpia el tablero de bodega SIN borrar los pedidos (siguen en la plataforma)."""
    with closing(_con()) as con, con:
        return con.execute("UPDATE pedidos SET archivado = 1 WHERE archivado = 0").rowcount


# ---------------------------------------------------------------- control de acceso del panel
# ---------------------------------------------------------------- consultas del panel
def _limite(valor: int, maximo: int = 500) -> int:
    return max(1, min(int(valor), maximo))


def resumen(total_productos: int) -> dict:
    hoy = datetime.now().strftime("%Y-%m-%d")
    dias = [(datetime.now() - timedelta(days=n)).strftime("%Y-%m-%d") for n in range(6, -1, -1)]
    with closing(_con()) as con:
        def uno(sql, *args):
            return con.execute(sql, args).fetchone()[0]

        por_dia = {}
        for clave, sql in (
            ("conversaciones", "SELECT substr(creada,1,10) d, COUNT(*) c FROM conversaciones GROUP BY d"),
            ("cotizaciones", "SELECT substr(creada,1,10) d, COUNT(*) c FROM cotizaciones GROUP BY d"),
            ("pedidos", "SELECT substr(creado,1,10) d, COUNT(*) c FROM pedidos GROUP BY d"),
        ):
            m = {f["d"]: f["c"] for f in con.execute(sql).fetchall()}
            por_dia[clave] = [m.get(d, 0) for d in dias]
        estados = {f["estado"]: f["c"] for f in con.execute("SELECT estado, COUNT(*) c FROM pedidos WHERE archivado=0 GROUP BY estado").fetchall()}
        return {
            "productos_catalogo": total_productos,
            "conversaciones": {"total": uno("SELECT COUNT(*) FROM conversaciones"), "hoy": uno("SELECT COUNT(*) FROM conversaciones WHERE substr(creada,1,10)=?", hoy)},
            "mensajes_cliente": uno("SELECT COUNT(*) FROM mensajes WHERE rol='cliente'"),
            "cotizaciones": {
                "total": uno("SELECT COUNT(*) FROM cotizaciones"),
                "hoy": uno("SELECT COUNT(*) FROM cotizaciones WHERE substr(creada,1,10)=?", hoy),
                "monto_total": uno("SELECT COALESCE(SUM(total),0) FROM cotizaciones"),
            },
            "pedidos": {
                "total": uno("SELECT COUNT(*) FROM pedidos"),
                "hoy": uno("SELECT COUNT(*) FROM pedidos WHERE substr(creado,1,10)=?", hoy),
                "por_estado": [{"estado": ESTADOS_PEDIDO[i], "cantidad": estados.get(i, 0)} for i in range(4)],
            },
            "dias": dias,
            "por_dia": por_dia,
        }


def resumen_admin() -> dict:
    """Cifras para el panel del administrador: solicitudes del formulario de contacto."""
    hoy = datetime.now().strftime("%Y-%m-%d")
    dias = [(datetime.now() - timedelta(days=n)).strftime("%Y-%m-%d") for n in range(6, -1, -1)]
    with closing(_con()) as con:
        por_interes = {f["solucion"]: f["c"] for f in con.execute("SELECT solucion, COUNT(*) c FROM solicitudes GROUP BY solucion").fetchall()}
        por_dia = {f["d"]: f["c"] for f in con.execute("SELECT substr(creada,1,10) d, COUNT(*) c FROM solicitudes GROUP BY d").fetchall()}
        total = con.execute("SELECT COUNT(*) FROM solicitudes").fetchone()[0]
        hoy_n = con.execute("SELECT COUNT(*) FROM solicitudes WHERE substr(creada,1,10)=?", (hoy,)).fetchone()[0]
        sin_correo = con.execute("SELECT COUNT(*) FROM solicitudes WHERE correo_estado NOT IN ('enviado')").fetchone()[0]
    return {
        "solicitudes": {"total": total, "hoy": hoy_n, "sin_aviso_por_correo": sin_correo},
        "por_interes": [{"id": k, "nombre": SOLUCIONES[k], "cantidad": por_interes.get(k, 0)} for k in SOLUCIONES],
        "dias": dias,
        "por_dia": [por_dia.get(d, 0) for d in dias],
    }


def listar_cotizaciones(limite: int) -> list:
    with closing(_con()) as con:
        filas = con.execute("SELECT * FROM cotizaciones ORDER BY id DESC LIMIT ?", (_limite(limite),)).fetchall()
    return [
        {"id": f["id"], "canal": f["canal"], "archivo": f["archivo"], "n_items": f["n_items"], "total": f["total"],
         "items": json.loads(f["items_json"]), "creada": f["creada"]}
        for f in filas
    ]


def listar_pedidos_todos(limite: int) -> list:
    with closing(_con()) as con:
        filas = con.execute("SELECT * FROM pedidos ORDER BY numero DESC LIMIT ?", (_limite(limite),)).fetchall()
    return [_pedido_dict(f) for f in filas]


def listar_conversaciones(limite: int) -> list:
    with closing(_con()) as con:
        filas = con.execute(
            "SELECT c.*, (SELECT COUNT(*) FROM mensajes m WHERE m.conversacion_id = c.id) n_mensajes, "
            "(SELECT texto FROM mensajes m WHERE m.conversacion_id = c.id AND m.rol='cliente' ORDER BY m.id DESC LIMIT 1) ultimo "
            "FROM conversaciones c ORDER BY c.actualizada DESC, c.id DESC LIMIT ?",
            (_limite(limite),),
        ).fetchall()
    return [
        {"id": f["id"], "canal": f["canal"], "sesion": f["sesion"], "creada": f["creada"], "actualizada": f["actualizada"],
         "n_mensajes": f["n_mensajes"], "ultimo_mensaje": f["ultimo"]}
        for f in filas
    ]


def detalle_conversacion(conv_id: int) -> dict:
    with closing(_con()) as con:
        c = con.execute("SELECT * FROM conversaciones WHERE id = ?", (conv_id,)).fetchone()
        if not c:
            raise HTTPException(status_code=404, detail="Conversación no encontrada")
        ms = con.execute("SELECT rol, texto, creado FROM mensajes WHERE conversacion_id = ? ORDER BY id", (conv_id,)).fetchall()
    return {"id": c["id"], "canal": c["canal"], "sesion": c["sesion"], "creada": c["creada"], "actualizada": c["actualizada"],
            "mensajes": [{"rol": m["rol"], "texto": m["texto"], "creado": m["creado"]} for m in ms]}


def info_canales(config: dict, n_sinonimos: int) -> dict:
    with closing(_con()) as con:
        def fila(sql, *a):
            return con.execute(sql, a).fetchone()
        web = fila("SELECT COUNT(*) c, MAX(actualizada) u FROM conversaciones WHERE canal='web'")
        web_cot = fila("SELECT COUNT(*) c FROM cotizaciones WHERE canal='web'")["c"]
        totem = fila("SELECT COUNT(*) c, MAX(actualizado) u FROM pedidos")
    return {
        "canales": [
            {"id": "whatsapp", "nombre": "WhatsApp (API Webhook)", "estado": "en_desarrollo", "ruta": "/whatsapp",
             "detalle": "Aún no está implementado: la ruta /whatsapp solo muestra una página \"Próximamente\".",
             "metricas": []},
            {"id": "web", "nombre": "Chatbot web incrustable", "estado": "operativo", "ruta": "/chatbot",
             "detalle": "Responde en /api/chat y se incrusta con widget.js.",
             "metricas": [{"nombre": "Conversaciones", "valor": web["c"]}, {"nombre": "Cotizaciones", "valor": web_cot}],
             "ultima_actividad": web["u"]},
            {"id": "totem", "nombre": "Tótem de autoatención", "estado": "demo", "ruta": "/totem", "ruta_extra": "/bodega",
             "detalle": "Los pedidos se guardan en el servidor. Usa un catálogo de ejemplo (16 productos ficticios), no el catálogo real.",
             "metricas": [{"nombre": "Pedidos", "valor": totem["c"]}],
             "ultima_actividad": totem["u"]},
        ],
        "configuracion": {
            "nombre_empresa": config.get("nombre_empresa"),
            "moneda": config.get("moneda"),
            "origenes_permitidos": config.get("origenes_permitidos"),
            "grupos_de_sinonimos": n_sinonimos,
            "correo_de_avisos": "configurado" if correo_configurado() else "no configurado (las solicitudes solo se guardan)",
            "acceso_panel": "usuario y contraseña (roles: admin y cliente)",
        },
    }


# ---------------------------------------------------------------- registro de rutas en la app
def registrar_rutas(app, catalogo_fn, config: dict, n_sinonimos_fn):
    """Agrega las rutas de pedidos (tótem) y del panel. catalogo_fn() devuelve la lista del catálogo real."""

    # --- públicas: las usan el tótem y el panel de bodega
    @app.post("/api/contacto")
    def api_contacto(data: ContactoEntrada, request: Request):
        if data.sitio_web.strip():            # un robot rellenó el campo trampa: se responde "ok" sin guardar
            return {"ok": True}
        ip = request.client.host if request.client else "?"
        if not _permitir_envio(ip):
            raise HTTPException(status_code=429, detail="Demasiadas solicitudes. Inténtalo más tarde.")
        guardar_solicitud(data)
        return {"ok": True}

    @app.post("/api/pedidos")
    def api_crear_pedido(data: PedidoEntrada):
        return crear_pedido(data)

    @app.get("/api/pedidos")
    def api_listar_pedidos():
        return {"pedidos": listar_pedidos_activos()}

    @app.post("/api/pedidos/reiniciar")
    def api_reiniciar_pedidos():
        return {"archivados": archivar_pedidos()}

    @app.post("/api/pedidos/{numero}/estado")
    def api_estado_pedido(numero: int, data: EstadoEntrada):
        return cambiar_estado_pedido(numero, data.estado)

    # --- sesión (inicio de sesión, cierre, quién soy, cambio de contraseña)
    auth.registrar_rutas(app)

    # --- panel del CLIENTE: el negocio que contrató la plataforma (también lo puede abrir el administrador)
    CLIENTE = ("cliente", "admin")

    @app.get("/api/cliente/resumen")
    def api_cliente_resumen(request: Request):
        auth.exigir_rol(request, *CLIENTE)
        return resumen(len(catalogo_fn()))

    @app.get("/api/cliente/cotizaciones")
    def api_cliente_cotizaciones(request: Request, limite: int = 100):
        auth.exigir_rol(request, *CLIENTE)
        return {"cotizaciones": listar_cotizaciones(limite)}

    @app.get("/api/cliente/pedidos")
    def api_cliente_pedidos(request: Request, limite: int = 100):
        auth.exigir_rol(request, *CLIENTE)
        return {"pedidos": listar_pedidos_todos(limite)}

    @app.get("/api/cliente/conversaciones")
    def api_cliente_conversaciones(request: Request, limite: int = 100):
        auth.exigir_rol(request, *CLIENTE)
        return {"conversaciones": listar_conversaciones(limite)}

    @app.get("/api/cliente/conversaciones/{conv_id}")
    def api_cliente_conversacion(conv_id: int, request: Request):
        auth.exigir_rol(request, *CLIENTE)
        return detalle_conversacion(conv_id)

    @app.get("/api/cliente/catalogo")
    def api_cliente_catalogo(request: Request, q: str = "", limite: int = 50):
        auth.exigir_rol(request, *CLIENTE)
        q = q.strip().lower()[:80]
        items = catalogo_fn()
        if q:
            items = [p for p in items if q in p["nombre"].lower()]
        return {"total": len(items),
                "productos": [{"id": p["id"], "nombre": p["nombre"], "precio": p["precio"]} for p in items[:_limite(limite)]]}

    # --- panel del ADMINISTRADOR: quien ofrece el servicio
    @app.get("/api/admin/resumen")
    def api_admin_resumen(request: Request):
        auth.exigir_rol(request, "admin")
        return resumen_admin()

    @app.get("/api/admin/solicitudes")
    def api_admin_solicitudes(request: Request, interes: str = "", limite: int = 200):
        auth.exigir_rol(request, "admin")
        return {"solicitudes": listar_solicitudes(limite, interes)}

    @app.get("/api/admin/canales")
    def api_admin_canales(request: Request):
        auth.exigir_rol(request, "admin")
        return info_canales(config, n_sinonimos_fn())
