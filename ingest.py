import html
import os
import re
import sqlite3
import unicodedata

import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
excel_path = os.path.join(BASE_DIR, "data", "Pitsdata.xlsx")
db_path = os.path.join(BASE_DIR, "data", "pits.db")

# Caracteres que Helvetica (PDF) no puede dibujar y salen como cuadros negros
REEMPLAZOS = {
    "‑": "-",   # guion no separable
    "‐": "-",
    "‒": "-",
    " ": " ",   # espacio fino no separable
    " ": " ",   # espacio no separable
    " ": " ",
    "​": "",    # espacio de ancho cero
    "“": '"', "”": '"',
    "‘": "'", "’": "'",
}


def limpiar(texto):
    """Quita HTML, normaliza Unicode y colapsa espacios."""
    texto = html.unescape(str(texto))
    texto = re.sub(r"<[^>]+>", " ", texto)
    for origen, destino in REEMPLAZOS.items():
        texto = texto.replace(origen, destino)
    texto = unicodedata.normalize("NFC", texto)
    return re.sub(r"\s+", " ", texto).strip()


if not os.path.exists(excel_path):
    print(f"❌ No se encontró {excel_path}")
    raise SystemExit(1)

xls = pd.ExcelFile(excel_path, engine="openpyxl")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("DROP TABLE IF EXISTS productos")
cursor.execute("""
    CREATE TABLE productos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        categoria TEXT,
        nombre TEXT,
        precio INTEGER,
        detalle TEXT
    )
""")

total = 0
sin_precio = 0
for hoja in xls.sheet_names:
    df = pd.read_excel(xls, sheet_name=hoja).fillna("")
    for _, fila in df.iterrows():
        nombre = ""
        precio = 0
        partes_detalle = []

        for col, val in fila.items():
            col_str = str(col).strip()
            val_str = limpiar(val)
            if not val_str or "Unnamed" in col_str:
                continue

            col_lower = col_str.lower()
            if not nombre and any(k in col_lower for k in ["title", "nombre", "producto", "descripcion", "ítem", "item"]):
                nombre = val_str
            elif precio == 0 and any(k in col_lower for k in ["precio", "price", "valor", "monto"]):
                # Acepta 15990, 15990.0, "$15.990"
                if isinstance(val, (int, float)):
                    precio = int(round(float(val)))
                else:
                    digitos = "".join(c for c in val_str if c.isdigit())
                    precio = int(digitos) if digitos else 0
            partes_detalle.append(f"{col_str}: {val_str}")

        if not nombre and partes_detalle:
            nombre = partes_detalle[0].split(":", 1)[-1].strip()

        if nombre:
            if precio == 0:
                sin_precio += 1
            cursor.execute(
                "INSERT INTO productos (categoria, nombre, precio, detalle) VALUES (?, ?, ?, ?)",
                (hoja, nombre, precio, " | ".join(partes_detalle)),
            )
            total += 1

conn.commit()
conn.close()
print(f"✅ Base de datos SQLite creada en {db_path} con {total} productos.")
if sin_precio:
    print(f"⚠️ {sin_precio} productos quedaron con precio 0: revisa el Excel.")
