"""Punto de entrada del backend FastAPI (Clasificador de Residuos).

Arquitectura del proyecto:
    Django  -> interfaz web, captura de camara y consumo de la API.
    FastAPI -> inferencia del modelo, validacion Pydantic y Swagger (/docs).
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.ml import get_classifier
from app.routers import auth, waste

logger = logging.getLogger(__name__)

DESCRIPTION = """
API del **Clasificador de Residuos** para Puntos Limpios.

Resuelve la mala separacion de basura en la fuente: el usuario fotografia un
objeto y el servicio responde la categoria, el tipo de residuo y el color del
contenedor donde debe depositarse.

### Flujo de uso
1. `POST /api/v1/auth/register` para crear la cuenta.
2. `POST /api/v1/auth/login` para obtener el **JWT** (usa el boton *Authorize*).
3. `POST /api/v1/classify-waste` enviando la foto de la camara.
4. `GET /api/v1/bins-guide` para las instrucciones de reciclaje.

### Motor de inferencia
El resultado incluye el campo `engine`, que indica con que modelo se clasifico:
`trashnet` (MobileNetV2 afinado con TrashNet), `mobilenet-imagenet`
(MobileNetV2 preentrenado + mapeo semantico de clases) o `heuristic`
(respaldo por color cuando TensorFlow no esta disponible).
"""

TAGS_METADATA = [
    {
        "name": "Salud",
        "description": "Verificacion de disponibilidad del servicio.",
    },
    {
        "name": "Autenticacion",
        "description": (
            "Registro, login y perfil. Las contrasenas se almacenan con hash "
            "bcrypt y la sesion se resuelve con JWT firmados."
        ),
    },
    {
        "name": "Residuos",
        "description": (
            "Clasificacion de imagenes, historial del usuario y guia de "
            "contenedores del Punto Limpio."
        ),
    },
]


def create_app() -> FastAPI:
    """Construye y configura la instancia de FastAPI."""
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=DESCRIPTION,
        summary="Clasificacion de residuos con MobileNetV2",
        contact={
            "name": "Equipo Taller 4",
            "url": "https://github.com/",
        },
        license_info={"name": "MIT"},
        openapi_tags=TAGS_METADATA,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
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
        """Prepara base de datos y modelo antes de atender trafico."""
        init_db()
        try:
            get_classifier().warm_up()
        except Exception:  # la API debe arrancar aunque el modelo falle
            logger.exception("No se pudo precalentar el clasificador")

    # --- Routers de la API v1 --------------------------------------------
    app.include_router(auth.router, prefix=settings.api_prefix)
    app.include_router(waste.router, prefix=settings.api_prefix)

    @app.get("/", tags=["Salud"], summary="Raiz del servicio")
    def root() -> dict:
        return {
            "service": settings.app_name,
            "version": settings.app_version,
            "docs": "/docs",
            "engine": get_classifier().engine,
        }

    @app.get("/health", tags=["Salud"], summary="Healthcheck")
    def health() -> dict:
        classifier = get_classifier()
        return {
            "status": "ok",
            "model_engine": classifier.engine,
            "model_loaded": classifier.is_ready,
        }

    return app


app = create_app()
