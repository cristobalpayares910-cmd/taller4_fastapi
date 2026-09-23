"""WSGI entrypoint (usado por gunicorn en Railway y por runserver en local)."""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_wsgi_application()
