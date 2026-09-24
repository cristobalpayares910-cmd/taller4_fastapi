"""Configuracion de SQLAlchemy 2.x (engine, sesion y Base declarativa)."""

import logging
import tempfile
from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings, sqlite_file_path

logger = logging.getLogger(__name__)


def _make_engine(url: str):
    """Crea un engine para la URL dada con los kwargs correctos."""
    kwargs = {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {"pool_pre_ping": True}
    return create_engine(url, **kwargs)


engine = _make_engine(settings.database_url)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    """Base declarativa de todos los modelos ORM."""


def get_db() -> Generator[Session, None, None]:
    """Dependencia FastAPI: entrega una sesion y la cierra al terminar."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _can_write_sqlite_file(url: str) -> bool:
    """Indica si SQLite puede crear/abrir el archivo en la ruta indicada."""
    db_file = sqlite_file_path(url)
    if db_file is None:
        return True  # memoria u otro motor: no hay archivo que validar
    try:
        db_file.parent.mkdir(parents=True, exist_ok=True)
        probe = db_file.with_name(f"{db_file.name}.write-test")
        probe.write_bytes(b"")
        probe.unlink()
        return True
    except OSError:
        return False


def prepare_database() -> None:
    """Garantiza un destino de base de datos escribible antes de abrir conexiones.

    Orden de intentos:
    1. La URL configurada tal cual (volumen de Railway, ruta local, etc.).
    2. ``./data/`` junto al backend (mountpoint esperado en Railway).
    3. ``/tmp/ecoscan/ecoscan.db`` (siempre escribible; base efimera).

    Sin este paso, un volumen ausente o de solo lectura deja a SQLite con
    "unable to open database file" en el arranque y el contenedor entra en
    crash-loop. Si se elige un destino de emergencia, se registra en los logs.
    """
    global engine, SessionLocal

    url = settings.database_url
    if not _can_write_sqlite_file(url):
        for fallback in (
            Path("data") / "ecoscan.db",
            Path(tempfile.gettempdir()) / "ecoscan" / "ecoscan.db",
        ):
            fallback_url = f"sqlite:///{fallback.as_posix()}"
            if _can_write_sqlite_file(fallback_url):
                logger.warning(
                    "La base de datos %r no es escribible; usando el destino "
                    "de emergencia %r (los datos no persisten entre despliegues).",
                    url,
                    fallback_url,
                )
                settings.database_url = fallback_url
                engine = _make_engine(fallback_url)
                SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
                break
        else:
            logger.error(
                "Ninguna ruta escribible para SQLite; se conserva %r y la "
                "conexion fallara con el error original.",
                url,
            )


def init_db() -> None:
    """Crea las tablas pendientes. Importa los modelos para registrarlos."""
    from app import models  # noqa: F401  (registra las tablas en Base.metadata)

    Base.metadata.create_all(bind=engine)
