# --- Backend FastAPI · imagen de produccion (Railway) ----------------------
# Railway inyecta la variable PORT; uvicorn escucha en 0.0.0.0:$PORT.

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Requisitos primero para aprovechar la cache de capas de Docker.
# TensorFlow queda fuera a proposito (ver requirements-ml.txt): sin el, el
# clasificador degrada al motor heuristico y la imagen se mantiene ligera.
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# railway.json no define startCommand a proposito: se usa este CMD.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
