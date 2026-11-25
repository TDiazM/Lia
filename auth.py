"""
Inicio de sesión y roles de la plataforma.

Dos roles:
  admin    -> quien ofrece el servicio: ve /admin (solicitudes de contacto, canales, configuración).
              También puede abrir /cliente para dar soporte.
  cliente  -> el negocio que contrató la plataforma: ve /cliente (pedidos, cotizaciones, conversaciones, catálogo).

Seguridad:
  - Las contraseñas se guardan con scrypt + sal aleatoria (nunca en texto plano).
  - No existen usuarios ni contraseñas por defecto: se crean con `python crear_usuario.py`.
  - La sesión es una cookie HttpOnly + SameSite=Strict con un identificador aleatorio; en la base solo se guarda su hash.
  - Límite de intentos fallidos: 5 cada 10 minutos por usuario y 30 por IP.
  - Las peticiones POST de sesión rechazan orígenes de otros sitios.

Los usuarios y sesiones viven en data/plataforma.db (la misma base de la plataforma).
"""
import hashlib
import hmac
import os
import secrets
import sqlite3
import threading
import time
from contextlib import closing
from datetime import datetime
from urllib.parse import urlparse

from fastapi import HTTPException, Request
from pydantic import BaseModel, Field
from starlette.responses import JSONResponse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "plataforma.db")

ROLES = ("admin", "cliente")
COOKIE = "lia_sesion"
DURACION_SESION = 12 * 3600       # segundos
CLAVE_MIN = 10
MAX_FALLOS = 5                    # por usuario
MAX_FALLOS_IP = 30                # por IP (más alto: detrás de un proxy muchos usuarios comparten IP)
VENTANA_FALLOS = 600              # segundos
_SCRYPT = dict(n=2 ** 14, r=8, p=1, dklen=32)

_fallos = {}                      # clave de límite -> instantes de intentos fallidos
_fallos_lock = threading.Lock()


# ---------------------------------------------------------------- base de datos
def _con():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    return con


def iniciar():
    with closing(_con()) as con, con:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario TEXT NOT NULL UNIQUE COLLATE NOCASE,
                rol TEXT NOT NULL CHECK (rol IN ('admin','cliente')),
                sal BLOB NOT NULL,
                clave_hash BLOB NOT NULL,
                activo INTEGER NOT NULL DEFAULT 1,
                creado TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sesiones (
                id_hash TEXT PRIMARY KEY,
                usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
                expira REAL NOT NULL
            );
            """
        )


# ---------------------------------------------------------------- contraseñas
def _hash(clave: str, sal: bytes) -> bytes:
    return hashlib.scrypt(clave.encode("utf-8"), salt=sal, **_SCRYPT)


def _validar_nombre(usuario: str) -> str:
    u = (usuario or "").strip()
    if not (3 <= len(u) <= 40) or not all(c.isalnum() or c in "._-@" for c in u):
        raise ValueError("El usuario debe tener 3 a 40 caracteres: letras, números, punto, guion o @.")
    return u


def _validar_clave(clave: str):
    if len(clave or "") < CLAVE_MIN:
        raise ValueError("La contraseña debe tener al menos %d caracteres." % CLAVE_MIN)
    if len(clave) > 200:
        raise ValueError("La contraseña es demasiado larga.")


def crear_usuario(usuario: str, clave: str, rol: str):
    """Crea un usuario. Lanza ValueError si los datos no sirven o el usuario ya existe."""
    if rol not in ROLES:
        raise ValueError("El rol debe ser 'admin' o 'cliente'.")
    usuario = _validar_nombre(usuario)
    _validar_clave(clave)
    sal = secrets.token_bytes(16)
    try:
        with closing(_con()) as con, con:
            con.execute(
                "INSERT INTO usuarios(usuario, rol, sal, clave_hash, creado) VALUES (?,?,?,?,?)",
                (usuario, rol, sal, _hash(clave, sal), datetime.now().isoformat(timespec="seconds")),
            )
    except sqlite3.IntegrityError:
        raise ValueError("Ese usuario ya existe.")


def cambiar_clave_usuario(usuario: str, clave_nueva: str) -> bool:
    _validar_clave(clave_nueva)
    sal = secrets.token_bytes(16)
    with closing(_con()) as con, con:
        cur = con.execute("UPDATE usuarios SET sal=?, clave_hash=? WHERE usuario=?", (sal, _hash(clave_nueva, sal), usuario))
        if cur.rowcount:
            con.execute("DELETE FROM sesiones WHERE usuario_id=(SELECT id FROM usuarios WHERE usuario=?)", (usuario,))
        return bool(cur.rowcount)


def _verificar(usuario: str, clave: str):
    """Devuelve la fila del usuario si usuario y clave son correctos; si no, None. Tarda parecido en ambos casos."""
    with closing(_con()) as con:
        fila = con.execute("SELECT * FROM usuarios WHERE usuario=? AND activo=1", (usuario,)).fetchone()
    if fila is None:
        _hash(clave, b"\x00" * 16)          # trabajo equivalente: no revela si el usuario existe
        return None
    return fila if hmac.compare_digest(_hash(clave, fila["sal"]), fila["clave_hash"]) else None


# ---------------------------------------------------------------- límite de intentos
def _claves_limite(ip: str, usuario: str):
    return ("ip:" + ip, "u:" + (usuario or "").lower()[:60])


def _bloqueado(ip: str, usuario: str) -> bool:
    ahora = time.time()
    with _fallos_lock:
        for k in _claves_limite(ip, usuario):
            recientes = [t for t in _fallos.get(k, []) if ahora - t < VENTANA_FALLOS]
            _fallos[k] = recientes
            if len(recientes) >= (MAX_FALLOS_IP if k.startswith("ip:") else MAX_FALLOS):
                return True
    return False


def _registrar_fallo(ip: str, usuario: str):
    with _fallos_lock:
        for k in _claves_limite(ip, usuario):
            _fallos.setdefault(k, []).append(time.time())
        if len(_fallos) > 5000:
            _fallos.clear()


def _limpiar_fallos(ip: str, usuario: str):
    with _fallos_lock:
        for k in _claves_limite(ip, usuario):
            _fallos.pop(k, None)


# ---------------------------------------------------------------- sesiones
def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _abrir_sesion(usuario_id: int) -> str:
    token = secrets.token_urlsafe(32)
    with closing(_con()) as con, con:
        con.execute("DELETE FROM sesiones WHERE expira < ?", (time.time(),))
        con.execute("INSERT INTO sesiones(id_hash, usuario_id, expira) VALUES (?,?,?)",
                    (_hash_token(token), usuario_id, time.time() + DURACION_SESION))
    return token


def _cerrar_sesion(token: str):
    with closing(_con()) as con, con:
        con.execute("DELETE FROM sesiones WHERE id_hash=?", (_hash_token(token),))


def usuario_actual(request: Request):
    """Devuelve {'id','usuario','rol'} de la sesión de la petición, o None."""
    token = request.cookies.get(COOKIE, "")
    if not token or len(token) > 200:
        return None
    with closing(_con()) as con:
        fila = con.execute(
            "SELECT u.id, u.usuario, u.rol FROM sesiones s JOIN usuarios u ON u.id=s.usuario_id "
            "WHERE s.id_hash=? AND s.expira>? AND u.activo=1",
            (_hash_token(token), time.time()),
        ).fetchone()
    return {"id": fila["id"], "usuario": fila["usuario"], "rol": fila["rol"]} if fila else None


def exigir_rol(request: Request, *roles):
    """Para las rutas protegidas: 401 si no hay sesión, 403 si el rol no corresponde."""
    u = usuario_actual(request)
    if u is None:
        raise HTTPException(status_code=401, detail="Inicia sesión para continuar")
    if u["rol"] not in roles:
        raise HTTPException(status_code=403, detail="Tu usuario no tiene permiso para ver esto")
    return u


def _mismo_origen(request: Request):
    origen = request.headers.get("origin")
    if origen and urlparse(origen).netloc != request.headers.get("host", ""):
        raise HTTPException(status_code=403, detail="Origen no permitido")


def _es_https(request: Request) -> bool:
    return request.url.scheme == "https" or request.headers.get("x-forwarded-proto", "").lower() == "https"


# ---------------------------------------------------------------- rutas
class LoginEntrada(BaseModel):
    usuario: str = Field(..., min_length=1, max_length=60)
    clave: str = Field(..., min_length=1, max_length=200)


class CambioClaveEntrada(BaseModel):
    clave_actual: str = Field(..., min_length=1, max_length=200)
    clave_nueva: str = Field(..., min_length=1, max_length=200)


def registrar_rutas(app):
    @app.post("/api/auth/login")
    def api_login(data: LoginEntrada, request: Request):
        _mismo_origen(request)
        ip = request.client.host if request.client else "?"
        usuario = data.usuario.strip()
        if _bloqueado(ip, usuario):
            raise HTTPException(status_code=429, detail="Demasiados intentos. Espera unos minutos e inténtalo de nuevo.")
        fila = _verificar(usuario, data.clave)
        if fila is None:
            _registrar_fallo(ip, usuario)
            raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")
        _limpiar_fallos(ip, usuario)
        token = _abrir_sesion(fila["id"])
        resp = JSONResponse({"usuario": fila["usuario"], "rol": fila["rol"]})
        resp.set_cookie(COOKIE, token, max_age=DURACION_SESION, httponly=True, samesite="strict",
                        secure=_es_https(request), path="/")
        return resp

    @app.post("/api/auth/logout")
    def api_logout(request: Request):
        _mismo_origen(request)
        token = request.cookies.get(COOKIE, "")
        if token:
            _cerrar_sesion(token)
        resp = JSONResponse({"ok": True})
        resp.delete_cookie(COOKIE, path="/")
        return resp

    @app.get("/api/auth/yo")
    def api_yo(request: Request):
        u = usuario_actual(request)
        if u is None:
            raise HTTPException(status_code=401, detail="Sin sesión")
        return {"usuario": u["usuario"], "rol": u["rol"]}

    @app.post("/api/auth/cambiar-clave")
    def api_cambiar_clave(data: CambioClaveEntrada, request: Request):
        _mismo_origen(request)
        u = usuario_actual(request)
        if u is None:
            raise HTTPException(status_code=401, detail="Inicia sesión para continuar")
        ip = request.client.host if request.client else "?"
        if _bloqueado(ip, u["usuario"]):
            raise HTTPException(status_code=429, detail="Demasiados intentos. Espera unos minutos.")
        if _verificar(u["usuario"], data.clave_actual) is None:
            _registrar_fallo(ip, u["usuario"])
            raise HTTPException(status_code=403, detail="La contraseña actual no es correcta")
        try:
            cambiar_clave_usuario(u["usuario"], data.clave_nueva)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        # el cambio cierra todas las sesiones: se abre una nueva para quien lo hizo
        with closing(_con()) as con:
            fila = con.execute("SELECT id FROM usuarios WHERE usuario=?", (u["usuario"],)).fetchone()
        token = _abrir_sesion(fila["id"])
        resp = JSONResponse({"ok": True})
        resp.set_cookie(COOKIE, token, max_age=DURACION_SESION, httponly=True, samesite="strict",
                        secure=_es_https(request), path="/")
        return resp
