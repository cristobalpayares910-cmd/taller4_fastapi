"""Pruebas de resiliencia de la configuracion SQLite.

Cubren el caso de produccion que crasheaba el arranque: ``DATABASE_URL``
apuntando a una carpeta inexistente o de solo lectura, lo que producía
``sqlite3.OperationalError: unable to open database file`` en el lifespan.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from sqlalchemy import text

BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_ROOT)

from app import database  # noqa: E402
from app.config import Settings, _default_database_url, sqlite_file_path  # noqa: E402


class SqliteFilePathTests(unittest.TestCase):
    """Extraccion de la ruta de archivo desde URLs de SQLAlchemy."""

    def test_url_relativa(self):
        self.assertEqual(sqlite_file_path("sqlite:///./ecoscan.db"), Path("./ecoscan.db"))

    def test_url_absoluta(self):
        self.assertEqual(sqlite_file_path("sqlite:////app/data/ecoscan.db"), Path("/app/data/ecoscan.db"))

    def test_url_windows(self):
        self.assertEqual(sqlite_file_path("sqlite:///C:/data/ecoscan.db"), Path("C:/data/ecoscan.db"))

    def test_memoria_y_otros_motores(self):
        self.assertIsNone(sqlite_file_path("sqlite://"))
        self.assertIsNone(sqlite_file_path("sqlite:///:memory:"))
        self.assertIsNone(sqlite_file_path("postgresql://u:p@host/db"))


class DefaultDatabaseUrlTests(unittest.TestCase):
    """Deteccion del volumen de Railway."""

    def test_con_volumen_montado(self):
        with mock.patch.dict(os.environ, {"RAILWAY_VOLUME_MOUNT_PATH": "/app/data"}):
            self.assertEqual(_default_database_url(), "sqlite:////app/data/ecoscan.db")

    def test_sin_volumen(self):
        env = {k: v for k, v in os.environ.items() if k != "RAILWAY_VOLUME_MOUNT_PATH"}
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(_default_database_url(), "sqlite:///./ecoscan.db")


class SettingsValidatorTests(unittest.TestCase):
    """El validador de Settings crea el directorio padre de la base."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="ecoscan-cfg-")
        self.addCleanup(self._tmp.cleanup)

    def test_crea_directorio_padre(self):
        target = Path(self._tmp.name) / "anidado" / "profundo" / "test.db"
        Settings(database_url=f"sqlite:///{target.as_posix()}")
        self.assertTrue(target.parent.is_dir())

    def test_no_toca_urls_de_otros_motores(self):
        # No debe lanzar ni crear directorios raros para Postgres.
        Settings(database_url="postgresql://u:p@localhost:5432/ecoscan")


class PrepareDatabaseTests(unittest.TestCase):
    """Fallback a una ruta escribible cuando la configurada no lo es."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="ecoscan-db-")
        self.addCleanup(self._tmp.cleanup)
        # Estado global que prepare_database puede mutar.
        self._original = (
            database.settings.database_url,
            database.engine,
            database.SessionLocal,
        )
        self.addCleanup(self._restore)

    def _restore(self):
        (url, engine, sessionlocal) = self._original
        database.settings.database_url = url
        database.engine = engine
        database.SessionLocal = sessionlocal

    def test_url_valida_no_se_reemplaza(self):
        ok_url = f"sqlite:///{Path(self._tmp.name) / 'ok.db'}"
        database.settings.database_url = ok_url
        database.prepare_database()
        self.assertEqual(database.settings.database_url, ok_url)

    def test_fallback_cuando_el_directorio_no_es_criable(self):
        # Un archivo donde deberia ir la carpeta de la base hace fallar mkdir
        # en cualquier sistema operativo.
        blocker = Path(self._tmp.name) / "blocked"
        blocker.write_text("", encoding="utf-8")
        bad_url = f"sqlite:///{(blocker / 'nested' / 'ecoscan.db').as_posix()}"

        old_cwd = os.getcwd()
        os.chdir(self._tmp.name)  # el fallback ./data cae en el temp
        try:
            database.settings.database_url = bad_url
            database.prepare_database()

            self.assertNotEqual(database.settings.database_url, bad_url)
            self.assertTrue(database.settings.database_url.startswith("sqlite:///"))
            # El engine reasignado debe funcionar de verdad.
            with database.SessionLocal() as session:
                self.assertEqual(session.execute(text("SELECT 1")).scalar(), 1)
        finally:
            # Libera el archivo SQLite (en Windows bloquea el cleanup del temp).
            database.engine.dispose()
            os.chdir(old_cwd)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
