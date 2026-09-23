"""Configuracion central del backend, leida desde variables de entorno."""

import os
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_database_url() -> str:
    """SQLite escribible.

    En Vercel el paquete desplegado es de solo lectura: el unico directorio
    escribible es ``/tmp``. En local se usa un archivo junto al backend.
    """
    if os.getenv("VERCEL"):
        return "sqlite:////tmp/ecoscan.db"
    return "sqlite:///./ecoscan.db"


class Settings(BaseSettings):
    """Variables de entorno del servicio FastAPI."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        # Evita el warning de pydantic v2 por campos que empiezan con "model_"
        protected_namespaces=("settings_",),
    )

    # --- Aplicacion -------------------------------------------------------
    app_name: str = "EcoScan IA API"
    app_version: str = "1.0.0"
    api_prefix: str = "/api/v1"
    debug: bool = True

    # --- Seguridad / JWT --------------------------------------------------
    secret_key: str = "dev-secret-cambiar-en-produccion"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 480  # 8 h (una jornada de taller)

    # --- Base de datos ----------------------------------------------------
    database_url: str = Field(default_factory=_default_database_url)

    # --- CORS -------------------------------------------------------------
    cors_origins: str = "http://127.0.0.1:8000,http://localhost:8000"

    # --- Modelo de ML -----------------------------------------------------
    # Ruta opcional a un modelo TrashNet ya entrenado (*.h5 / *.keras).
    # Si no existe, se usa MobileNetV2 preentrenado en ImageNet + mapeo
    # semantico de clases. Si TensorFlow no esta instalado, se degrada a
    # un clasificador heuristico.
    trashnet_model_path: str = ""
    image_size: int = 224
    # 4 MiB, alineado con MAX_UPLOAD_BYTES del frontend y con el limite de
    # 4.5 MB del cuerpo de las funciones de Vercel.
    max_upload_mb: int = 4
    max_image_pixels: int = 4000  # redimensionado defensivo antes de inferir

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Devuelve una unica instancia cacheada de la configuracion."""
    return Settings()


settings = get_settings()
