import functools
import os
from datetime import datetime

LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")


def registrar_api(nombre_api):
    """Decorador que deja en una bitácora técnica cada uso de una API o librería."""
    def decorador(func):
        @functools.wraps(func)
        def envoltorio(*args, **kwargs):
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            try:
                os.makedirs(LOG_DIR, exist_ok=True)
                with open(os.path.join(LOG_DIR, "bitacora_apis.log"), "a", encoding="utf-8") as f:
                    f.write(f"{timestamp} | API_ACTIVA: {nombre_api} | Funcion: {func.__name__}\n")
            except OSError:
                pass  # la bitácora nunca debe tumbar la aplicación
            return func(*args, **kwargs)
        return envoltorio
    return decorador
