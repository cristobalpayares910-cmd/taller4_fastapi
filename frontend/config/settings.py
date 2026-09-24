"""Configuracion de Django para el cliente web de EcoScan IA.

Este frontend NO procesa el modelo: solo renderiza plantillas, captura el
stream de la camara con getUserMedia y consume la API de FastAPI.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def load_dotenv(path: Path) -> None:
    """Carga un archivo .env sin dependencias externas.

    Las variables ya presentes en el entorno tienen prioridad, de modo que en
    Railway siempre gana la configuracion del servicio (panel o railway.json).
    """
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip("'\"")
        if key and not os.getenv(key):
            os.environ[key] = value


load_dotenv(BASE_DIR / ".env")


def env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, "1" if default else "0").lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


# --- Seguridad -------------------------------------------------------------
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "django-insecure-dev-key-taller4")
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "*" if DEBUG else "localhost,127.0.0.1")

# Railway ejecuta el healthcheck del railway.json con el host
# "healthcheck.railway.app" (y desde 127.0.0.1), no con el dominio publico. Si
# Django los rechaza devuelve 400, el healthcheck no pasa nunca y el dominio
# acaba respondiendo "Application failed to respond".
for _healthcheck_host in ("healthcheck.railway.app", "127.0.0.1", "localhost"):
    if _healthcheck_host not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(_healthcheck_host)

# Dominio publico que Railway inyecta en el servicio con dominio propio: evita
# depender de que ALLOWED_HOSTS se haya escrito completo a mano.
_railway_public_domain = os.getenv("RAILWAY_PUBLIC_DOMAIN", "").strip()
if _railway_public_domain and _railway_public_domain not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(_railway_public_domain)

CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", "")

# La sesion firmada en cookie evita depender de una base de datos: el estado
# del usuario vive en FastAPI y la cookie solo guarda el JWT.
SESSION_ENGINE = "django.contrib.sessions.backends.signed_cookies"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = not DEBUG
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# --- Aplicaciones ----------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.staticfiles",
    "django.contrib.sessions",
    "django.contrib.messages",
    "web",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "web" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.messages.context_processors.messages",
                "web.context_processors.app_settings",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# Django no persiste nada propio: los usuarios viven en la base de datos de
# FastAPI y la sesion en una cookie firmada. Se mantiene SQLite solo para
# completar la configuracion. En Railway, si hay volumen montado, la base
# vive dentro de el y sobrevive a los despliegues.
#
# Railway expone la ruta del volumen en RAILWAY_VOLUME_MOUNT_PATH (no en
# RAILWAY_VOLUME, que no define, y por eso la deteccion nunca se activaba).
_volume_mount = os.getenv("RAILWAY_VOLUME_MOUNT_PATH", "").strip()
_DB_DIR = Path(_volume_mount) if _volume_mount else BASE_DIR

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": _DB_DIR / "django_local.sqlite3",
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LANGUAGE_CODE = "es"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# --- Archivos estaticos ----------------------------------------------------
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "web" / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}
WHITENOISE_USE_FINDERS = True
WHITENOISE_AUTOREFRESH = DEBUG

# --- Integracion con el backend FastAPI ------------------------------------
FASTAPI_BASE_URL = os.getenv("FASTAPI_BASE_URL", "http://127.0.0.1:8001")
FASTAPI_TIMEOUT = float(os.getenv("FASTAPI_TIMEOUT", "45"))
# 25 MiB por defecto, alineado con MAX_UPLOAD_MB del backend. Debe ir junto
# con esa variable para que el mensaje de error de la aplicacion llegue antes
# que un 413 opaco del proveedor.
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(25 * 1024 * 1024)))

# Limites de carga aceptados por Django: el archivo se reenvia tal cual a
# FastAPI, que vuelve a validar tamano y formato.
DATA_UPLOAD_MAX_MEMORY_SIZE = MAX_UPLOAD_BYTES + 512 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024
