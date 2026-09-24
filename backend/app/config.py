"""Configuracion central del backend, leida desde variables de entorno."""

import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def sqlite_file_path(database_url: str) -> Path | None:
    """Extrae la ruta del archivo de una URL sqlite, o None si no aplica.

    Cubre las variantes de SQLAlchemy: ``sqlite:///ruta/relativa``,
    ``sqlite:///C:\ruta`` (Windows), ``sqlite:////ruta/absoluta`` y
    ``sqlite://`` (base en memoria).
    """
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        return None
    path = database_url[len(prefix) :]
    if not path or path == ":memory:":
        return None
    return Path(path)


def _ensure_sqlite_parent_dir(database_url: str) -> None:
    """Crea el directorio padre del archivo SQLite si falta.

    SQLAlchemy/SQLite no crean directorios: si ``DATABASE_URL`` apunta a una
    carpeta inexistente (p. ej. un volumen no montado todavia), la conexion
    falla con "unable to open database file" y el servicio entra en crash-loop.
    Si el directorio no se puede crear (sistema de archivos de solo lectura),
    se deja que SQLite reporte el error original.
    """
    db_file = sqlite_file_path(database_url)
    if db_file is None:
        return
    try:
        db_file.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass


def _default_database_url() -> str:
    """SQLite escribible.

    En Railway, si el servicio tiene un volumen montado, la base de datos vive
    dentro del volumen y sobrevive a los despliegues. Railway inyecta la ruta
    del volumen en ``RAILWAY_VOLUME_MOUNT_PATH``; antes se leia
    ``RAILWAY_VOLUME``, variable que Railway no define, de modo que la
    deteccion nunca se activaba y la base quedaba en una ruta efimera.

    En local se usa un archivo junto al backend.
    """
    mount_path = os.getenv("RAILWAY_VOLUME_MOUNT_PATH", "").strip()
    if mount_path:
        # as_posix() mantiene las barras normales tambien en Windows.
        # 4 barras: sqlite:// + ruta absoluta (/app/data/ecoscan.db).
        return f"sqlite:///{(Path(mount_path) / 'ecoscan.db').as_posix()}"
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

    @field_validator("database_url")
    @classmethod
    def _prepare_sqlite_location(cls, value: str) -> str:
        """Garantiza que la ruta SQLite sea abrible antes de conectar."""
        value = os.path.expanduser(value)
        _ensure_sqlite_parent_dir(value)
        return value

    # --- CORS -------------------------------------------------------------
    cors_origins: str = "http://127.0.0.1:8000,http://localhost:8000"

    # --- Modelo de ML -----------------------------------------------------
    # Ruta opcional a un modelo TrashNet ya entrenado (*.h5 / *.keras).
    # Si no existe, se usa MobileNetV2 preentrenado en ImageNet + mapeo
    # semantico de clases. Si TensorFlow no esta instalado, se degrada a
    # un clasificador heuristico.
    trashnet_model_path: str = ""
    image_size: int = 224
    # 25 MiB, alineado con MAX_UPLOAD_BYTES del frontend. En Railway no hay
    # limite de proxy tan bajo como en Vercel (4.5 MB), asi que se puede
    # aceptar un margen mayor.
    max_upload_mb: int = 25
    max_image_pixels: int = 4000  # redimensionado defensivo antes de inferir

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Devuelve una unica instancia cacheada de la configuracion."""
    return Settings()


settings = get_settings()
