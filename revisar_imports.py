import ast
import os
from importlib import metadata

IGNORAR = {".git", "node_modules", "venv", "__pycache__", ".venv"}


def obtener_imports_proyecto(directorio):
    encontrados = set()
    for root, dirs, files in os.walk(directorio):
        dirs[:] = [d for d in dirs if d not in IGNORAR]
        for file in files:
            if not file.endswith(".py"):
                continue
            ruta = os.path.join(root, file)
            try:
                with open(ruta, "r", encoding="utf-8") as f:
                    arbol = ast.parse(f.read(), filename=ruta)
            except (OSError, SyntaxError, UnicodeDecodeError):
                continue
            for nodo in ast.walk(arbol):
                if isinstance(nodo, ast.Import):
                    encontrados.update(n.name.split(".")[0] for n in nodo.names)
                elif isinstance(nodo, ast.ImportFrom) and nodo.module and nodo.level == 0:
                    encontrados.add(nodo.module.split(".")[0])
    return encontrados


usados = obtener_imports_proyecto(".")
# Relaciona cada paquete instalado con los módulos que realmente aporta (ej. pillow -> PIL)
modulos_por_paquete = {}
for modulo, paquetes in metadata.packages_distributions().items():
    for paquete in paquetes:
        modulos_por_paquete.setdefault(paquete.lower(), set()).add(modulo)

no_usados = []
for dist in metadata.distributions():
    nombre = dist.metadata["Name"]
    if not nombre:
        continue
    modulos = modulos_por_paquete.get(nombre.lower(), {nombre.lower().replace("-", "_")})
    if not (modulos & usados):
        no_usados.append(nombre)

print("Paquetes instalados que posiblemente NO se importan en el código")
print("(pueden ser dependencias de otros paquetes: no los borres sin revisar):")
for p in sorted(set(no_usados), key=str.lower):
    print(f"- {p}")
