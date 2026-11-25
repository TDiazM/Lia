import json
import os
import re
import sqlite3
import threading
import time
import unicodedata
from datetime import datetime
from typing import List
from xml.sax.saxutils import escape as xml_escape

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from api_logger import registrar_api
import plataforma

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "pits.db")
PDF_DIR = os.path.join(BASE_DIR, "cotizaciones")
INDEX_PATH = os.path.join(BASE_DIR, "index.html")
WIDGET_PATH = os.path.join(BASE_DIR, "widget.js")
DEMO_PATH = os.path.join(BASE_DIR, "demo-tienda.html")
WHATSAPP_PATH = os.path.join(BASE_DIR, "whatsapp.html")
NAV_PATH = os.path.join(BASE_DIR, "nav.js")
LOGIN_PATH = os.path.join(BASE_DIR, "login.html")
ADMIN_PATH = os.path.join(BASE_DIR, "admin.html")
CLIENTE_PATH = os.path.join(BASE_DIR, "cliente.html")
TOTEM_DIR = os.path.join(BASE_DIR, "totem")

PDF_NOMBRE_RE = re.compile(r"(?:Cotizacion|Ticket)_\w{1,20}_\d{8}_\d{6}\.pdf")
PDF_MAX_EDAD_SEG = 24 * 3600
SESION_MAX_EDAD_SEG = 2 * 3600
SESIONES_MAX = 1000
LIMITE_RESULTADOS = 5

# ---------------------------------------------------------------- configuración
with open(os.path.join(BASE_DIR, "config.json"), "r", encoding="utf-8") as f:
    config = json.load(f)

SIMBOLO = config.get("moneda", "$")
EMPRESA = config.get("nombre_empresa", "PITS DETAILING")


def plegar(texto: str) -> str:
    """Minúsculas y sin tildes, para comparar 'Neumáticos' con 'neumaticos'."""
    texto = unicodedata.normalize("NFKD", str(texto).lower())
    return "".join(c for c in texto if not unicodedata.combining(c))


# Grupos de sinónimos: cada grupo es [clave] + sus sinónimos, ya plegados
grupos_sinonimos = []
kw_path = os.path.join(BASE_DIR, "keywords.json")
if os.path.exists(kw_path):
    with open(kw_path, "r", encoding="utf-8") as f:
        for clave, sinonimos in json.load(f).get("sinonimos", {}).items():
            grupos_sinonimos.append([plegar(clave)] + [plegar(s) for s in sinonimos])

PALABRAS_VACIAS = {
    "para", "los", "las", "con", "del", "una", "uno", "unos", "unas", "por", "que",
    "quiero", "busco", "necesito", "hola", "favor", "algo", "mi", "mis", "tu", "sus",
}

# ---------------------------------------------------------------- aplicación
app = FastAPI(title="Asistente Pits Detailing")

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.get("origenes_permitidos", ["*"]),
    allow_credentials=False,  # "*" con credenciales no es válido ni seguro
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

sesiones = {}
lock = threading.Lock()


def _registrar(funcion, *args):
    """Guarda datos en la plataforma (data/plataforma.db). Si falla, el chat sigue funcionando igual."""
    try:
        funcion(*args)
    except Exception as e:  # noqa: BLE001 - el registro nunca debe afectar al cliente
        print(f"[plataforma] no se pudo registrar: {e}")


_registrar(plataforma.iniciar)


def obtener_sesion(session_id: str):
    ahora = time.time()
    # Limpieza de sesiones viejas para que la memoria no crezca sin límite
    for sid in [s for s, d in sesiones.items() if ahora - d["visto"] > SESION_MAX_EDAD_SEG]:
        del sesiones[sid]
    while len(sesiones) >= SESIONES_MAX and session_id not in sesiones:
        del sesiones[min(sesiones, key=lambda s: sesiones[s]["visto"])]
    sesion = sesiones.setdefault(session_id, {"carrito": [], "ultimas_opciones": {}, "visto": ahora})
    sesion["visto"] = ahora
    return sesion


def fmt_precio(valor: int) -> str:
    return f"{SIMBOLO}{valor:,}".replace(",", ".")


# ---------------------------------------------------------------- catálogo y búsqueda
_catalogo = {"mtime": None, "items": []}


def cargar_catalogo():
    """Carga el catálogo en memoria y lo recarga solo si cambió pits.db."""
    if not os.path.exists(DB_PATH):
        return []
    mtime = os.path.getmtime(DB_PATH)
    if _catalogo["mtime"] != mtime:
        conn = sqlite3.connect(DB_PATH)
        try:
            filas = conn.execute("SELECT id, nombre, precio, detalle FROM productos").fetchall()
        finally:
            conn.close()
        _catalogo["items"] = [
            {
                "id": prod_id,
                "nombre": nombre,
                "precio": precio,
                "nombre_n": plegar(nombre),
                "detalle_n": plegar(detalle or ""),
            }
            for prod_id, nombre, precio, detalle in filas
        ]
        _catalogo["mtime"] = mtime
    return _catalogo["items"]


def _equivalentes(a: str, b: str) -> bool:
    if a == b:
        return True
    return min(len(a), len(b)) >= 4 and (a.startswith(b) or b.startswith(a))


def expandir_terminos(consulta: str):
    """Devuelve (términos originales, sinónimos). Los originales pesan más al ordenar."""
    tokens = re.findall(r"\w+", plegar(consulta))
    originales = [t for t in tokens if len(t) >= 2 and t not in PALABRAS_VACIAS]
    if not originales:
        originales = [t for t in tokens if t]
    originales = list(dict.fromkeys(originales))

    sinonimos = []
    for grupo in grupos_sinonimos:
        if any(_equivalentes(t, g) for t in originales for g in grupo):
            sinonimos.extend(g for g in grupo if g not in originales and g not in sinonimos)
    return originales, sinonimos


def _puntaje_termino(termino: str, texto: str, peso_nombre: float, peso_detalle: float) -> float:
    """Puntaje de un término contra un texto; coincide al inicio de palabra, no a mitad."""
    if not re.search(r"(?<!\w)" + re.escape(termino), texto):
        return 0.0
    exacta = re.search(r"(?<!\w)" + re.escape(termino) + r"(?!\w)", texto) is not None
    return peso_nombre * (2.0 if exacta else 1.0) if peso_nombre else peso_detalle


@registrar_api("SQLite (Catálogo Pits)")
def buscar_productos_sqlite(consulta: str, limite: int = LIMITE_RESULTADOS):
    catalogo = cargar_catalogo()
    originales, sinonimos = expandir_terminos(consulta)
    if not originales:
        return []

    puntuados = []
    for prod in catalogo:
        score = 0.0
        for t in originales:
            score += _puntaje_termino(t, prod["nombre_n"], 3.0, 0)
            score += _puntaje_termino(t, prod["detalle_n"], 0, 1.0)
        for t in sinonimos:
            score += _puntaje_termino(t, prod["nombre_n"], 1.0, 0)
            score += _puntaje_termino(t, prod["detalle_n"], 0, 0.3)
        if score > 0:
            puntuados.append((score, prod))

    puntuados.sort(key=lambda x: (-x[0], x[1]["id"]))
    return [
        {"id": p["id"], "nombre": p["nombre"], "precio": p["precio"]}
        for _, p in puntuados[:limite]
    ]


# ---------------------------------------------------------------- PDF
REEMPLAZOS_PDF = {
    "‑": "-", "‐": "-", "‒": "-",
    " ": " ", " ": " ", " ": " ", "​": "",
    "“": '"', "”": '"', "‘": "'", "’": "'",
}


def texto_pdf(texto: str) -> str:
    """Deja el texto seguro para Helvetica y para el mini-XML de Paragraph."""
    for origen, destino in REEMPLAZOS_PDF.items():
        texto = texto.replace(origen, destino)
    return xml_escape(texto)


def limpiar_pdfs_viejos():
    ahora = time.time()
    for archivo in os.listdir(PDF_DIR):
        ruta = os.path.join(PDF_DIR, archivo)
        if PDF_NOMBRE_RE.fullmatch(archivo) and ahora - os.path.getmtime(ruta) > PDF_MAX_EDAD_SEG:
            try:
                os.remove(ruta)
            except OSError:
                pass


@registrar_api("ReportLab (Generación de PDF)")
def generar_pdf_cotizacion(items_carrito, identificador):
    os.makedirs(PDF_DIR, exist_ok=True)
    limpiar_pdfs_viejos()

    seguro = re.sub(r"\W", "", str(identificador))[:20] or "cliente"
    nombre_archivo = f"Cotizacion_{seguro}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    ruta_pdf = os.path.join(PDF_DIR, nombre_archivo)

    doc = SimpleDocTemplate(
        ruta_pdf, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40
    )
    styles = getSampleStyleSheet()
    titulo_style = ParagraphStyle(
        "Titulo", parent=styles["Heading1"], fontSize=20,
        textColor=colors.HexColor("#283627"), spaceAfter=4,
    )
    subtitulo_style = ParagraphStyle(
        "Sub", parent=styles["Normal"], fontSize=10,
        textColor=colors.HexColor("#6FA074"), spaceAfter=20,
    )
    celda_style = ParagraphStyle("Celda", parent=styles["Normal"], fontSize=9, leading=11)
    total_style = ParagraphStyle(
        "Total", parent=celda_style, fontName="Helvetica-Bold", textColor=colors.white
    )

    elements = [
        Paragraph(f"<b>{texto_pdf(EMPRESA)}</b>", titulo_style),
        Paragraph(
            f"COMPROBANTE DE COTIZACIÓN &bull; {datetime.now().strftime('%d/%m/%Y %H:%M')}",
            subtitulo_style,
        ),
        Spacer(1, 10),
    ]

    data = [["N°", "Producto / Descripción", "Precio Unitario"]]
    total = 0
    for idx, item in enumerate(items_carrito, 1):
        data.append([
            str(idx),
            Paragraph(texto_pdf(item["nombre"]), celda_style),  # se ajusta al ancho de la celda
            fmt_precio(item["precio"]),
        ])
        total += item["precio"]
    data.append(["", Paragraph("TOTAL COTIZADO", total_style), fmt_precio(total)])

    tabla = Table(data, colWidths=[35, 375, 120], repeatRows=1)
    tabla.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#283627")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#FAF7EE")),
        ("ALIGN", (2, 0), (2, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("BACKGROUND", (0, 1), (-1, -2), colors.HexColor("#FAF7EE")),
        ("GRID", (0, 0), (-1, -2), 0.5, colors.HexColor("#EBDCB4")),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#C9796A")),
        ("TEXTCOLOR", (0, -1), (-1, -1), colors.white),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
    ]))
    elements.append(tabla)
    doc.build(elements)
    return nombre_archivo


# ---------------------------------------------------------------- lógica del chat
# Solo números y conectores: "1", "1,2", "1 y 3", "el 2", "agrega 1 2". No "aro 14", "3m", "v80".
SELECCION_RE = re.compile(
    r"(?:(?:el|la|los|las|numero|n|opcion|opciones|agrega|agregar|anade|anadir|quiero|item|y)\s*)*"
    r"\d+(?:\s*(?:,|;|y|\s)\s*\d+)*"
)
SALUDOS = {"hola", "ayuda", "help", "menu", "buenas", "buenos dias", "buenas tardes"}
VER_CARRITO = {"carrito", "ver carrito", "mi carrito"}
VACIAR_CARRITO = {"vaciar", "vaciar carrito", "limpiar carrito", "borrar carrito"}

AYUDA = (
    "👋 ¡Hola! Escribe el producto que buscas (ej: shampoo, cera, microfibra).\n"
    "Luego escribe el número de la opción para agregarla al carrito.\n"
    "Comandos: 'carrito' para verlo, 'vaciar' para limpiarlo y 'cotizar' para generar tu PDF."
)


def _lineas_carrito(carrito):
    lineas = [f"{i}. {p['nombre']} - {fmt_precio(p['precio'])}" for i, p in enumerate(carrito, 1)]
    lineas.append(f"TOTAL: {fmt_precio(sum(p['precio'] for p in carrito))}")
    return lineas


def procesar_mensaje(session_id: str, texto: str):
    """Devuelve (respuesta, nombre_pdf_o_None)."""
    sesion = obtener_sesion(session_id)
    carrito = sesion["carrito"]
    opciones = sesion["ultimas_opciones"]
    texto_n = plegar(texto).strip()
    palabras = re.findall(r"\w+", texto_n)

    if texto_n in SALUDOS:
        return AYUDA, None

    if texto_n in VER_CARRITO:
        if not carrito:
            return "🛒 Tu carrito está vacío.", None
        return "🛒 Tu carrito:\n" + "\n".join(_lineas_carrito(carrito)), None

    if texto_n in VACIAR_CARRITO:
        carrito.clear()
        return "🗑️ Carrito vaciado.", None

    if any(p.startswith("cotiz") or p == "pdf" for p in palabras):
        if not carrito:
            return "⚠️ Tu carrito está vacío. Busca un producto y escribe su número para agregarlo.", None
        archivo = generar_pdf_cotizacion(carrito, session_id)
        cantidad = len(carrito)
        total = sum(p["precio"] for p in carrito)
        _registrar(plataforma.registrar_cotizacion, "web", session_id, archivo, list(carrito))
        carrito.clear()
        return (
            f"✅ ¡Cotización generada! {cantidad} producto(s), total {fmt_precio(total)}.\n"
            f"Archivo: {archivo}",
            archivo,
        )

    if SELECCION_RE.fullmatch(texto_n):
        if not opciones:
            return "Primero busca un producto (ej: shampoo) y luego escribe el número de la opción.", None
        agregados, invalidos = [], []
        for n in dict.fromkeys(int(x) for x in re.findall(r"\d+", texto_n)):
            if n in opciones:
                carrito.append(opciones[n])
                agregados.append(f"🛒 Agregado: {opciones[n]['nombre']} ({fmt_precio(opciones[n]['precio'])})")
            else:
                invalidos.append(str(n))
        partes = list(agregados)
        if invalidos:
            partes.append(f"❌ No existe la opción {', '.join(invalidos)} en la lista actual.")
        if agregados:
            partes.append(f"📦 Total en carrito: {len(carrito)}. Escribe 'cotizar' para generar tu PDF.")
        return "\n".join(partes), None

    resultados = buscar_productos_sqlite(texto)
    if not resultados:
        return "No encontré productos en el catálogo de Pits que coincidan con tu búsqueda.", None

    opciones.clear()
    lineas = ["Encontré estas opciones en Pits:"]
    for idx, prod in enumerate(resultados, 1):
        opciones[idx] = {"id": prod["id"], "nombre": prod["nombre"], "precio": prod["precio"]}
        lineas.append(f"[{idx}] {prod['nombre']} - {fmt_precio(prod['precio'])}")
    lineas.append("👉 Escribe el número para agregar al carrito.")
    return "\n".join(lineas), None


# ---------------------------------------------------------------- endpoints
class ChatEntrada(BaseModel):
    mensaje: str = Field("", max_length=500)
    session_id: str = Field("web_demo", pattern=r"^[\w-]{1,64}$")


@app.post("/api/chat")
def chat_web(data: ChatEntrada):
    mensaje = data.mensaje.strip()
    if not mensaje:
        return {"respuesta": "Escribe el producto que buscas.", "pdf": None}
    with lock:
        respuesta, archivo = procesar_mensaje(data.session_id, mensaje)
    _registrar(plataforma.registrar_intercambio, "web", data.session_id, mensaje, respuesta)
    return {"respuesta": respuesta, "pdf": f"/api/pdf/{archivo}" if archivo else None}


@app.get("/api/pdf/{nombre}")
def descargar_pdf(nombre: str):
    if not PDF_NOMBRE_RE.fullmatch(nombre):
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    ruta = os.path.join(PDF_DIR, nombre)
    if not os.path.isfile(ruta):
        raise HTTPException(status_code=404, detail="Archivo no encontrado o expirado")
    return FileResponse(ruta, media_type="application/pdf", filename=nombre)


@app.get("/api/health")
def health():
    return {"ok": True, "productos": len(cargar_catalogo())}


@app.get("/")
def inicio():
    if os.path.isfile(INDEX_PATH):
        return FileResponse(INDEX_PATH, media_type="text/html")
    return {"ok": True, "mensaje": "API activa. Coloca index.html junto a app.py para ver la demo."}


@app.get("/widget.js")
def widget_js():
    """Script incrustable: <script src="https://TU-SERVIDOR/widget.js" defer></script>"""
    if not os.path.isfile(WIDGET_PATH):
        raise HTTPException(status_code=404, detail="widget.js no encontrado")
    return FileResponse(WIDGET_PATH, media_type="application/javascript")


# ---------------------------------------------------------------- navegación entre módulos
# Rutas limpias de cada demostración:
#   /            página principal          /whatsapp  Próximamente (opción 1)
#   /chatbot     demo del chatbot web      /totem     tótem de autoatención (opción 3)
#   /bodega      panel de bodega del tótem /nav.js    barra de navegación compartida
def _archivo_html(ruta: str, nombre: str):
    if not os.path.isfile(ruta):
        raise HTTPException(status_code=404, detail=f"{nombre} no encontrado")
    return FileResponse(ruta, media_type="text/html")


@app.get("/chatbot")
def chatbot_demo():
    return _archivo_html(DEMO_PATH, "demo-tienda.html")


@app.get("/demo", include_in_schema=False)
def demo_tienda():
    """Ruta anterior de la demo del chatbot: se mantiene para no romper enlaces."""
    return RedirectResponse(url="/chatbot")


@app.get("/whatsapp")
def whatsapp_proximamente():
    return _archivo_html(WHATSAPP_PATH, "whatsapp.html")


@app.get("/plataforma")
def plataforma_panel():
    # Enlace de siempre: lleva al inicio de sesión, que redirige según el rol (admin o cliente)
    return RedirectResponse("/login", status_code=302)


@app.get("/login")
def login_pagina():
    return _archivo_html(LOGIN_PATH, "login.html")


@app.get("/admin")
def admin_panel():
    return _archivo_html(ADMIN_PATH, "admin.html")


@app.get("/cliente")
def cliente_panel():
    return _archivo_html(CLIENTE_PATH, "cliente.html")


# Pedidos del tótem (/api/pedidos) y API del panel (/api/plataforma/*): ver plataforma.py
plataforma.registrar_rutas(app, cargar_catalogo, config, lambda: len(grupos_sinonimos))


@app.get("/nav.js")
def nav_js():
    if not os.path.isfile(NAV_PATH):
        raise HTTPException(status_code=404, detail="nav.js no encontrado")
    return FileResponse(NAV_PATH, media_type="application/javascript")


def _pagina_totem(nombre: str):
    """Sirve una página de totem/ en una ruta sin carpeta (/totem, /bodega).
    Se inserta <base href="/totem/"> para que sus rutas relativas (catalogo.js, ../api/ticket…) sigan funcionando."""
    ruta = os.path.join(TOTEM_DIR, nombre)
    if not os.path.isfile(ruta):
        raise HTTPException(status_code=404, detail=f"totem/{nombre} no encontrado")
    with open(ruta, encoding="utf-8") as f:
        html = f.read()
    html = html.replace("<head>", '<head>\n<base href="/totem/">', 1)
    return HTMLResponse(html)


@app.get("/totem")
def totem_demo():
    return _pagina_totem("totem.html")


@app.get("/bodega")
def bodega_demo():
    return _pagina_totem("bodega.html")


# ---------------------------------------------------------------- tótem: ticket en PDF
# (la simulación de pedidos del tótem vive en el navegador; aquí solo se genera el PDF del ticket)
class ItemTicket(BaseModel):
    nombre: str = Field(..., max_length=120)
    cantidad: int = Field(..., ge=1, le=99)
    precio: int = Field(..., ge=0, le=10_000_000)


class TicketEntrada(BaseModel):
    numero: int = Field(..., ge=1, le=999999)
    fecha: str = Field("", max_length=40)
    estado: str = Field("", max_length=40)
    items: List[ItemTicket] = Field(..., min_length=1, max_length=50)


@registrar_api("ReportLab (Ticket de pedido)")
def generar_pdf_ticket(data: TicketEntrada):
    """Ticket tipo comprobante de 80 mm; el total se calcula aquí, no se confía en el del cliente."""
    os.makedirs(PDF_DIR, exist_ok=True)
    limpiar_pdfs_viejos()
    nombre_archivo = f"Ticket_{data.numero}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    ruta_pdf = os.path.join(PDF_DIR, nombre_archivo)

    ancho, margen = 80 * mm, 8
    disponible = ancho - 2 * margen - 12  # 12 = relleno interno del marco de ReportLab
    base = getSampleStyleSheet()["Normal"]
    normal = ParagraphStyle("TkN", parent=base, fontSize=8, leading=10)
    centro = ParagraphStyle("TkC", parent=normal, alignment=1)
    titulo = ParagraphStyle("TkT", parent=centro, fontName="Helvetica-Bold", fontSize=13, leading=16)
    numero = ParagraphStyle("TkNum", parent=centro, fontName="Helvetica-Bold", fontSize=24, leading=28)
    negrita = ParagraphStyle("TkB", parent=normal, fontName="Helvetica-Bold")
    derecha = ParagraphStyle("TkR", parent=normal, alignment=2)
    derecha_b = ParagraphStyle("TkRB", parent=derecha, fontName="Helvetica-Bold")

    def linea():
        return HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#5e7a5d"), dash=(2, 2), spaceBefore=5, spaceAfter=5)

    filas = [[Paragraph("Producto", negrita), Paragraph("Cant.", derecha_b), Paragraph("Subtotal", derecha_b)]]
    total = 0
    for it in data.items:
        sub = it.cantidad * it.precio
        total += sub
        filas.append([Paragraph(texto_pdf(it.nombre), normal), Paragraph(f"{it.cantidad} x", derecha), Paragraph(fmt_precio(sub), derecha)])
    tabla = Table(filas, colWidths=[disponible * 0.56, disponible * 0.16, disponible * 0.28])
    tabla.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.black),
        ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    total_t = Table(
        [[Paragraph("TOTAL", ParagraphStyle("TkTot", parent=negrita, fontSize=11, leading=13)),
          Paragraph(fmt_precio(total), ParagraphStyle("TkTotR", parent=derecha_b, fontSize=11, leading=13))]],
        colWidths=[disponible * 0.5, disponible * 0.5],
    )
    total_t.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))

    historia = [
        Paragraph(f"<b>{texto_pdf(EMPRESA)}</b>", titulo),
        Paragraph("Ticket de pedido", centro), linea(),
        Paragraph(f"#{data.numero}", numero),
        Paragraph(texto_pdf(data.fecha), centro), linea(),
        tabla, linea(), total_t, Spacer(1, 6),
    ]
    if data.estado:
        historia.append(Paragraph(f"<b>ESTADO: {texto_pdf(data.estado.upper())}</b>", centro))
    historia += [Spacer(1, 6), Paragraph("Presenta este número en el mesón.<br/>Demostración: sin valor comercial.", centro)]

    alto = 2 * margen + 12 + 10
    for f in historia:
        _, h = f.wrap(disponible, 100000)
        alto += h + f.getSpaceBefore() + f.getSpaceAfter()

    doc = SimpleDocTemplate(ruta_pdf, pagesize=(ancho, alto), leftMargin=margen, rightMargin=margen, topMargin=margen, bottomMargin=margen)
    doc.build(historia)
    return nombre_archivo


@app.post("/api/ticket")
def crear_ticket(data: TicketEntrada):
    return {"pdf": f"/api/pdf/{generar_pdf_ticket(data)}"}


# Archivos del tótem y del panel de bodega (HTML/CSS/JS estáticos): /totem/totem.html y /totem/bodega.html
if os.path.isdir(TOTEM_DIR):
    app.mount("/totem", StaticFiles(directory=TOTEM_DIR), name="totem")
