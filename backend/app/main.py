"""Punto de entrada del backend FastAPI (Clasificador de Residuos).

Arquitectura del proyecto:
    Django  -> interfaz web, captura de camara y consumo de la API.
    FastAPI -> inferencia del modelo, validacion Pydantic y Swagger (/docs).
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db


def create_app() -> FastAPI:
    """Construye y configura la instancia de FastAPI."""
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "API de clasificacion de residuos para Puntos Limpios. "
            "Clasifica una fotografia y devuelve la categoria, el tipo de "
            "residuo y el color de contenedor donde debe depositarse."
        ),
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    def _on_startup() -> None:
        init_db()

    @app.get("/", tags=["Salud"], summary="Raiz del servicio")
    def root() -> dict:
        return {
            "service": settings.app_name,
            "version": settings.app_version,
            "docs": "/docs",
        }

    @app.get("/health", tags=["Salud"], summary="Healthcheck")
    def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
