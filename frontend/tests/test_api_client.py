"""Pruebas del cliente HTTP que consume la API de FastAPI.

Se simula `httpx.request` para verificar la normalizacion de errores, la
propagacion del token y el contrato de las funciones publicas.
"""

import importlib
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

FRONTEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(FRONTEND_ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")


def _available(*modules: str) -> bool:
    for name in modules:
        try:
            importlib.import_module(name)
        except ImportError:
            return False
    return True


HAS_HTTP_CLIENT = _available("httpx", "django")


@unittest.skipUnless(
    HAS_HTTP_CLIENT, "requiere httpx y django instalados en el entorno"
)
class ApiClientTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import django

        django.setup()
        cls.api = importlib.import_module("web.api_client")

    def _fake_response(self, status_code=200, payload=None):
        response = mock.Mock()
        response.status_code = status_code
        response.content = b"{}" if payload is not None else b""
        response.json.return_value = payload if payload is not None else {}
        return response

    def test_login_posts_json_with_credentials(self):
        with mock.patch.object(
            self.api.httpx, "request", return_value=self._fake_response(200, {"access_token": "t"})
        ) as request:
            result = self.api.login_user("a@b.cl", "secreta123")

        self.assertEqual(result["access_token"], "t")
        method, url = request.call_args.args[:2]
        self.assertEqual(method, "POST")
        self.assertTrue(url.endswith("/api/v1/auth/login/json"))
        self.assertEqual(
            request.call_args.kwargs["json"],
            {"email": "a@b.cl", "password": "secreta123"},
        )

    def test_token_is_forwarded_in_authorization_header(self):
        with mock.patch.object(
            self.api.httpx, "request", return_value=self._fake_response(200, {"id": 1})
        ) as request:
            self.api.fetch_profile("jwt-123")

        self.assertEqual(
            request.call_args.kwargs["headers"]["Authorization"], "Bearer jwt-123"
        )

    def test_detail_string_becomes_api_error(self):
        with mock.patch.object(
            self.api.httpx,
            "request",
            return_value=self._fake_response(401, {"detail": "Credenciales invalidas"}),
        ):
            with self.assertRaises(self.api.ApiError) as ctx:
                self.api.login_user("a@b.cl", "mala1234")

        self.assertEqual(ctx.exception.status_code, 401)
        self.assertEqual(ctx.exception.message, "Credenciales invalidas")

    def test_detail_list_is_flattened(self):
        payload = {
            "detail": [
                {"loc": ["body", "email"], "msg": "value is not a valid email"},
                {"loc": ["body", "password"], "msg": "too short"},
            ]
        }
        with mock.patch.object(
            self.api.httpx, "request", return_value=self._fake_response(422, payload)
        ):
            with self.assertRaises(self.api.ApiError) as ctx:
                self.api.register_user("x", "y", "z")

        self.assertIn("email", ctx.exception.message)
        self.assertIn("password", ctx.exception.message)

    def test_timeout_becomes_504(self):
        with mock.patch.object(
            self.api.httpx, "request", side_effect=self.api.httpx.TimeoutException("boom")
        ):
            with self.assertRaises(self.api.ApiError) as ctx:
                self.api.fetch_bins_guide()

        self.assertEqual(ctx.exception.status_code, 504)

    def test_connection_error_becomes_503(self):
        with mock.patch.object(
            self.api.httpx, "request", side_effect=self.api.httpx.ConnectError("down")
        ):
            with self.assertRaises(self.api.ApiError) as ctx:
                self.api.fetch_bins_guide()

        self.assertEqual(ctx.exception.status_code, 503)

    def test_classify_sends_multipart_field_named_file(self):
        with mock.patch.object(
            self.api.httpx, "request", return_value=self._fake_response(201, {"type": "Paper"})
        ) as request:
            self.api.classify_image("jwt", "captura.jpg", b"bytes", "image/jpeg")

        files = request.call_args.kwargs["files"]
        self.assertIn("file", files)
        self.assertEqual(files["file"][0], "captura.jpg")


if __name__ == "__main__":
    unittest.main()
