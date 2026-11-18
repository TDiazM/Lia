# mvp-pits-detailing

Asistente de cotizaciones para Pits Detailing: busca productos en un catálogo local (SQLite),
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
| `/widget.js` | Script incrustable del chatbot |
| `/nav.js` | Barra de navegación compartida de las demos (Volver al inicio + menú) |
| `/api/chat`, `/api/pdf/{archivo}`, `/api/ticket`, `/api/health` | Backend (sin cambios) |

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
