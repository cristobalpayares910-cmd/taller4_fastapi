"""Pruebas de integracion de la API con el cliente de FastAPI.

Estas pruebas cubren el flujo completo: registro, login, clasificacion de una
imagen real y consulta del historial. Requieren `httpx` (dependencia de
`fastapi.testclient`); si no esta instalado, se omiten.
"""

import io
import os
import sys
import tempfile
import unittest
from unittest import mock

from PIL import Image

BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_ROOT)

# Base de datos temporal y aislada para la corrida de pruebas.
_TMP_DIR = tempfile.mkdtemp(prefix="punto-limpio-tests-")
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_TMP_DIR, 'test.db')}"
os.environ["SECRET_KEY"] = "clave-solo-para-pruebas"

try:  # pragma: no cover - depende del entorno
    from fastapi.testclient import TestClient

    from app.main import app

    IMPORT_ERROR = None
except Exception as exc:  # pragma: no cover
    TestClient = None
    app = None
    IMPORT_ERROR = exc


def jpeg_bytes(color=(40, 90, 200), size=(128, 128)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, color).save(buffer, format="JPEG")
    return buffer.getvalue()


@unittest.skipIf(TestClient is None, f"requiere httpx ({IMPORT_ERROR})")
class ApiFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Se usa TestClient como gestor de contexto para que se ejecute el
        # lifespan de la app (creacion de tablas y precalentado del modelo).
        cls._client_context = TestClient(app)
        cls.client = cls._client_context.__enter__()
        cls.email = "prueba@correo.cl"
        cls.password = "Recicla2026"

    @classmethod
    def tearDownClass(cls):
        cls._client_context.__exit__(None, None, None)

    def _register_and_login(self) -> str:
        self.client.post(
            "/api/v1/auth/register",
            json={
                "email": self.email,
                "full_name": "Usuaria de Prueba",
                "password": self.password,
            },
        )
        response = self.client.post(
            "/api/v1/auth/login/json",
            json={"email": self.email, "password": self.password},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["access_token"]

    def test_health_reports_model_engine(self):
        payload = self.client.get("/health").json()
        self.assertEqual(payload["status"], "ok")
        self.assertIn(payload["model_engine"], {"trashnet", "mobilenet-imagenet", "heuristic"})

    def test_bins_guide_is_public_and_cacheable(self):
        response = self.client.get("/api/v1/bins-guide")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertGreaterEqual(body["total_bins"], 4)
        self.assertIn("public", response.headers.get("cache-control", ""))

    def test_classify_requires_authentication(self):
        response = self.client.post(
            "/api/v1/classify-waste",
            files={"file": ("foto.jpg", jpeg_bytes(), "image/jpeg")},
        )
        self.assertEqual(response.status_code, 401)

    def test_classify_returns_expected_contract(self):
        token = self._register_and_login()
        response = self.client.post(
            "/api/v1/classify-waste",
            files={"file": ("botella.jpg", jpeg_bytes(), "image/jpeg")},
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, 201, response.text)

        body = response.json()
        # El contrato se valida contra la taxonomia real: la clase exacta
        # depende del motor instalado en cada entorno (trashnet,
        # mobilenet-imagenet o heuristico), pero categoria, color y material
        # deben ser coherentes entre si.
        from app.ml.labels import MATERIALS

        waste_types = {material.waste_type for material in MATERIALS.values()}
        self.assertIn(body["type"], waste_types)
        material = next(
            item for item in MATERIALS.values() if item.waste_type == body["type"]
        )
        self.assertEqual(body["category"], material.category.value)
        self.assertEqual(body["bin_color"], material.bin_color.value)
        self.assertEqual(body["material"], material.key)
        self.assertEqual(body["bin_name"], material.bin_name_es)
        self.assertTrue(body["instructions"])
        self.assertIn(
            body["engine"], {"trashnet", "mobilenet-imagenet", "heuristic"}
        )
        self.assertGreaterEqual(body["confidence"], 0.0)
        self.assertLessEqual(body["confidence"], 1.0)
        self.assertTrue(body["top_k"])
        self.assertIsNotNone(body["id"])

    def test_classify_rejects_non_image(self):
        token = self._register_and_login()
        response = self.client.post(
            "/api/v1/classify-waste",
            files={"file": ("nota.txt", b"texto plano", "image/jpeg")},
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, 400)

    def test_classify_rejects_oversized_image(self):
        from app.config import settings as app_settings

        token = self._register_and_login()
        with mock.patch.object(app_settings, "max_upload_mb", 0):
            response = self.client.post(
                "/api/v1/classify-waste",
                files={"file": ("grande.jpg", jpeg_bytes(), "image/jpeg")},
                headers={"Authorization": f"Bearer {token}"},
            )
        self.assertEqual(response.status_code, 413)

    def test_history_returns_previous_classifications(self):
        token = self._register_and_login()
        self.client.post(
            "/api/v1/classify-waste",
            files={"file": ("botella.jpg", jpeg_bytes(), "image/jpeg")},
            headers={"Authorization": f"Bearer {token}"},
        )
        response = self.client.get(
            "/api/v1/history", headers={"Authorization": f"Bearer {token}"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(response.json()), 1)

    def test_validation_error_is_human_readable(self):
        response = self.client.post(
            "/api/v1/auth/register", json={"email": "no-es-correo"}
        )
        self.assertEqual(response.status_code, 422)
        self.assertIn("error", response.json())

    def test_login_rejects_wrong_password(self):
        self._register_and_login()
        response = self.client.post(
            "/api/v1/auth/login/json",
            json={"email": self.email, "password": "clave-incorrecta"},
        )
        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
