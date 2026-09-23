# --- Frontend Django · imagen de produccion (Railway) ----------------------
# Railway inyecta la variable PORT; gunicorn escucha en 0.0.0.0:$PORT.

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# WhiteNoise sirve los estaticos desde STATICFILES_DIRS
# (WHITENOISE_USE_FINDERS=True), asi que no se necesita collectstatic.

EXPOSE 8000

# railway.json no define startCommand a proposito: se usa este CMD.
CMD ["sh", "-c", "gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 2 --threads 4 --timeout 120 --access-logfile -"]
