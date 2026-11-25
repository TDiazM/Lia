# Lia

Lia es el ecosistema de atención y cotizaciones de Pits Detailing: un asistente que busca productos en un catálogo local (SQLite),
arma un carrito y genera una cotización en PDF. Incluye una página de demostración (`index.html`).

## Rutas del proyecto (un solo servidor)

Al arrancar el servidor (`uvicorn app:app --port 8000`) todo se abre desde `http://localhost:8000/`.

| Ruta | Qué abre |
|---|---|
| `/` | Página principal (centro de navegación de las 3 soluciones) |
| `/whatsapp` | Opción 1 · WhatsApp: página "Próximamente" (aún no implementada) |
| `/chatbot` | Opción 2 · Demo del chatbot web incrustable (antes `/demo`, que ahora redirige aquí) |
| `/totem` | Opción 3 · Tótem de autoatención |
| `/bodega` | Panel de bodega del tótem (se comunica con `/totem` en tiempo real) |
| `/login` | Inicio de sesión (te lleva a tu panel según tu rol). `/plataforma` redirige aquí |
| `/admin` | Panel del **administrador** (quien ofrece el servicio): solicitudes de contacto por interés, canales y configuración |
| `/cliente` | Panel del **cliente** (el negocio que contrata): pedidos, cotizaciones, conversaciones y catálogo |
| `/widget.js` | Script incrustable del chatbot |
| `/nav.js` | Barra de navegación compartida de las demos (Volver al inicio + menú) |
| `/api/chat`, `/api/pdf/{archivo}`, `/api/ticket`, `/api/health` | Backend (sin cambios; `/api/chat` ahora también registra la conversación) |
| `POST /api/contacto` | Formulario de contacto de la página principal (guarda la solicitud y avisa por correo si está configurado) |
| `/api/pedidos` (GET/POST), `/api/pedidos/{n}/estado`, `/api/pedidos/reiniciar` | Pedidos del tótem guardados en el servidor |
| `/api/cliente/*`, `/api/admin/*`, `/api/auth/*` | Datos de cada panel (con sesión y rol) e inicio/cierre de sesión |

`/totem/totem.html` y `/totem/bodega.html` siguen funcionando como antes.

## Puesta en marcha

```bash
pip install -r requirements.txt
python ingest.py                  # data/Pitsdata.xlsx -> data/pits.db (ejecutar al cambiar el Excel)
uvicorn app:app --port 8000       # abre http://localhost:8000
```

## Cómo se usa el chat

| Escribes            | Resultado                                   |
|---------------------|---------------------------------------------|
| `shampoo`, `cera`   | Lista hasta 5 opciones numeradas            |
| `1`, `1 y 3`, `1,2` | Agrega esas opciones al carrito             |
| `carrito` / `vaciar`| Ver o limpiar el carrito                    |
| `cotizar`           | Genera el PDF y entrega el enlace de descarga |

## Archivos

- `app.py`: API FastAPI (`POST /api/chat`, `GET /api/pdf/{archivo}`, `GET /api/health`, `GET /` sirve la demo).
- `ingest.py`: convierte el Excel en `data/pits.db` (limpia HTML y caracteres que el PDF no soporta).
- `config.json`: nombre de la empresa, moneda y orígenes CORS permitidos (en producción reemplaza `"*"` por tu dominio).
- `keywords.json`: sinónimos de búsqueda (ej. shampoo = shampu, champú).
- `api_logger.py`: bitácora técnica en `logs/bitacora_apis.log`.
- `revisar_imports.py`: lista paquetes instalados que el código no importa.

Los PDF se guardan en `cotizaciones/` y se eliminan automáticamente después de 24 horas.

## Incrustar el chatbot en una tienda (ej. Shopify)

1. Publica la API en un servidor con HTTPS (el sitio de la tienda no puede cargar scripts `http://`).
2. En `config.json`, reemplaza `"origenes_permitidos": ["*"]` por el dominio de la tienda, por ejemplo `["https://mitienda.cl"]`.
3. En Shopify: *Tienda en línea > Temas > Editar código > `theme.liquid`* y pega antes de `</body>`:

```html
<script src="https://TU-SERVIDOR/widget.js" defer></script>
```

Atributos opcionales: `data-titulo="Asistente Pits"`, `data-color="#283627"`, `data-api="https://TU-SERVIDOR"`.
Para ver cómo queda, abre `http://localhost:8000/demo` (maqueta con marca neutra, no es un sitio real).
El catálogo del asistente es una copia del Excel: al cambiar productos o precios, actualiza `data/Pitsdata.xlsx` y ejecuta `python ingest.py`.

## Demo del Tótem de Autoatención (opción 3 de `index.html`)

Simulación interactiva e independiente del chatbot (carpeta `totem/`, HTML/CSS/JS sin dependencias).

| Ruta | Qué es |
|---|---|
| `/totem/totem.html` | Pantalla del cliente (formato vertical 9:16): bienvenida → catálogo → carrito → resumen → envío a bodega → seguimiento → ticket |
| `/totem/bodega.html` | Panel del trabajador: cambia el estado (1 Recibido, 2 En preparación, 3 Listo, 4 Entregado) |
| `POST /api/ticket` | Genera el ticket en PDF (ReportLab, 80 mm). Si el servidor no responde, el tótem imprime con `window.print()` |

- En `index.html` → opción 3 → **Ver demo del tótem / Ver panel de bodega / Ver ambas pantallas** (ventana "Modo demostración" con las dos pantallas lado a lado).
- Sincronización tótem ↔ bodega: `localStorage` + `BroadcastChannel` (mismo navegador y origen; sin backend ni base de datos). Los pedidos parten en #104. "Reiniciar demo" limpia todo.
- Productos y marca ("Lumina") son datos de ejemplo en `totem/catalogo.js`. No hay pagos reales.
- La lógica del tótem no comparte código con `/api/chat` ni con `widget.js`.

## Plataforma y base de datos

- Los datos nuevos (conversaciones del chatbot web, cotizaciones y pedidos del tótem) se guardan en `data/plataforma.db` (SQLite, se crea sola). El catálogo `pits.db` sigue siendo de solo lectura. **`data/plataforma.db` está en `.gitignore`: contiene datos reales, no la subas a GitHub.** El catálogo `data/pits.db` sí forma parte del proyecto.
- Los pedidos del tótem parten en el N° 104 y siguen aumentando. "Reiniciar demo" limpia el tablero pero **archiva** los pedidos (siguen visibles en el panel del cliente).
- Si el servidor no responde, el tótem sigue funcionando en modo local (localStorage), como antes; esos pedidos no quedan registrados en la plataforma.
- **Acceso a los paneles**: con usuario y contraseña, con dos roles: `admin` (panel `/admin`; también puede abrir `/cliente` para dar soporte) y `cliente` (solo `/cliente`). Ver la sección siguiente.
- Limitaciones: WhatsApp no está implementado; el tótem usa un catálogo de ejemplo (no `pits.db`); `/api/chat` y `/api/pedidos` siguen abiertos con CORS `*`; las conversaciones se guardan sin política de retención; Clientes, Reportes avanzados y Usuarios y permisos no están desarrollados.

## Formulario de contacto y aviso por correo

Las solicitudes del formulario de la página principal se guardan en `data/plataforma.db` y las ve el administrador en `/admin` → pestaña **Solicitudes** (filtradas por interés: ecosistema completo, WhatsApp, chatbot web o tótem). Si además configuras un correo, te llega un email por cada solicitud (con *Responder a* = correo del cliente). Si el correo falla o no está configurado, la solicitud igual queda guardada.

Variables de entorno (nunca se escriben en el código ni se suben a GitHub):

| Variable | Qué es |
|---|---|
| `PITS_SMTP_USER` | Tu correo Gmail que envía el aviso |
| `PITS_SMTP_PASS` | **Contraseña de aplicación** de Google (no tu clave normal; requiere verificación en 2 pasos) |
| `PITS_SMTP_TO` | (opcional) Dónde recibir los avisos; por defecto el mismo `PITS_SMTP_USER` |
| `PITS_SMTP_HOST` / `PITS_SMTP_PORT` | (opcional) Por defecto `smtp.gmail.com` / `587` |

PowerShell, antes de arrancar el servidor (valen solo para esa ventana):

```
$env:PITS_SMTP_USER = "tucorreo@gmail.com"
$env:PITS_SMTP_PASS = "xxxx xxxx xxxx xxxx"
python -m uvicorn app:app --port 8001
```

Protecciones: límite de 5 envíos cada 10 minutos por IP, campo trampa anti-robots y validación del correo. Los avisos no se pueden ver desde el exterior: la lista de solicitudes solo está en el panel.

## Usuarios y roles

No hay usuarios ni contraseñas por defecto: se crean desde la terminal, en la carpeta del proyecto. La contraseña se pide por teclado (mínimo 10 caracteres) y se guarda cifrada (scrypt + sal); nunca queda escrita en un archivo.

```
python crear_usuario.py tomas admin       # administrador: panel /admin
python crear_usuario.py minegocio cliente # cliente: panel /cliente
python crear_usuario.py tomas --cambiar   # cambia la contraseña de un usuario existente
```

Luego entra a `/login`. Cada usuario también puede cambiar su contraseña desde su panel. Detalles de seguridad: sesión por cookie `HttpOnly` + `SameSite=Strict` (12 horas), bloqueo temporal tras 5 intentos fallidos por usuario (30 por IP), y rechazo de peticiones de sesión que vengan de otros sitios. En internet usa siempre HTTPS (la cookie se marca `Secure` cuando detecta HTTPS).

Qué **no** está protegido todavía: el panel de bodega (`/bodega`) y `/api/pedidos` siguen abiertos, como en la demo original, para que el tótem y la bodega funcionen sin iniciar sesión; `/api/pdf/{archivo}` y `/api/chat` también siguen abiertos. Un modelo de varios clientes en una sola plataforma (cada uno con sus datos aislados) no está desarrollado: hoy cada negocio usa su propia instalación.

