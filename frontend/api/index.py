"""Entrypoint Serverless de Vercel para el frontend Django (WSGI).

El runtime de Python busca ``app`` (ASGI) o ``handler`` (WSGI). Django se
despliega como aplicacion WSGI, por lo que se expone la variable ``app``
apuntando a la aplicacion WSGI de Django.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

FRONTEND_ROOT = Path(__file__).resolve().parent.parent
if str(FRONTEND_ROOT) not in sys.path:
    sys.path.insert(0, str(FRONTEND_ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from config.wsgi import application  # noqa: E402  (requiere las rutas ajustadas)

app = application

__all__ = ["app"]
