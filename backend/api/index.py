"""Entrypoint Serverless de Vercel para la API FastAPI.

Vercel ejecuta el modulo como funcion ASGI. El runtime de Python busca una
variable llamada ``app`` (ASGI) o ``handler`` (WSGI); se expone unicamente
``app`` para que el servicio se trate como ASGI.

En el despliegue, el modulo se ejecuta desde ``backend/api/``, por lo que se
agrega la raiz del backend al ``sys.path`` antes de importar la aplicacion.
"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.main import app  # noqa: E402  (import despues de ajustar sys.path)

__all__ = ["app"]
