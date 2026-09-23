"""Pruebas de las vistas de Django (paginas y proxy hacia FastAPI).

Se sustituye `web.api_client` por dobles para no depender de un FastAPI en
ejecucion. Requieren el stack completo del frontend (`django`, `httpx`,
`whitenoise`); si falta alguna dependencia las pruebas se omiten.
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


HAS_STACK = _available("django", "httpx", "whitenoise")

LOGIN_PAYLOAD = {
    "access_token": "jwt-de-prueba",
    "token_type": "bearer",
    "expires_in": 3600,
    "user": {"id": 1, "email": "ana@correo.cl", "full_name": "Ana Soto"},
}

CLASSIFY_PAYLOAD = {
    "id": 5,
    "category": "Recyclable",
    "type": "Plastic Bottle",
    "bin_color": "Blue",
    "bin_name": "Contenedor azul (plasticos y latas)",
    "instructions": "Enjuaga el envase.",
    "confidence": 0.93,
    "engine": "heuristic",
    "material": "plastic",
    "top_k": [],
    "created_at": None,
}


@unittest.skipUnless(HAS_STACK, "requiere django, httpx y whitenoise instalados")
class ViewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import django

        django.setup()
        from django.test import Client, override_settings

        from django.conf import settings

        cls.Client = Client
        cls.settings = settings
        cls.api = importlib.import_module("web.api_client")
        # El .env documentado en el README restringe ALLOWED_HOSTS a
        # localhost/127.0.0.1, pero el cliente de pruebas viaja con el host
        # "testserver"; sin esto todas las vistas devuelven 400 (DisallowedHost).
        cls._hosts_override = override_settings(
            ALLOWED_HOSTS=[*settings.ALLOWED_HOSTS, "testserver"]
        )
        cls._hosts_override.enable()

    @classmethod
    def tearDownClass(cls):
        cls._hosts_override.disable()

    def setUp(self):
        self.client = self.Client()

    def _session_client(self, **session_data):
        """Cliente con sesion iniciada.

        El proyecto usa sesiones en cookie firmada, donde el valor de la cookie
        se genera al llamar a `save()`; por eso hay que reescribir la cookie en
        el jar del cliente despues de guardar los datos.
        """
        client = self.Client()
        session = client.session
        session.update(session_data)
        session.save()
        client.cookies[self.settings.SESSION_COOKIE_NAME] = session.session_key
        return client

    @staticmethod
    def _upload(name="captura.jpg", size=1024):
        """Simula un UploadedFile de Django."""
        upload = mock.MagicMock(size=size)
        upload.name = name
        upload.content_type = "image/jpeg"
        upload.read.return_value = b"contenido-de-imagen"
        return upload

    # --- Acceso ----------------------------------------------------------
    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get("/clasificar/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/ingresar/", response["Location"])

    def test_home_is_public(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)

    def test_login_creates_session(self):
        with mock.patch.object(self.api, "login_user", return_value=LOGIN_PAYLOAD):
            response = self.client.post(
                "/ingresar/", {"email": "ana@correo.cl", "password": "Recicla2026"}
            )

        self.assertEqual(response.status_code, 302)
        self.assertIn("/clasificar/", response["Location"])
        self.assertEqual(self.client.session["access_token"], "jwt-de-prueba")

    def test_login_surfaces_api_error(self):
        error = self.api.ApiError("Correo o contrasena incorrectos", 401)
        with mock.patch.object(self.api, "login_user", side_effect=error):
            response = self.client.post(
                "/ingresar/", {"email": "ana@correo.cl", "password": "mala-clave"}
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn(
            "Correo o contrasena incorrectos", response.content.decode("utf-8")
        )

    def test_logout_clears_session(self):
        self.client = self._authenticated_client()

        response = self.client.get("/salir/")
        self.assertEqual(response.status_code, 302)
        self.assertNotIn("access_token", self.client.session)

    # --- Proxy hacia FastAPI ---------------------------------------------
    def _authenticated_client(self):
        return self._session_client(
            access_token="jwt-de-prueba", user=LOGIN_PAYLOAD["user"]
        )

    def test_classify_proxy_returns_classification(self):
        client = self._authenticated_client()
        with mock.patch.object(
            self.api, "classify_image", return_value=CLASSIFY_PAYLOAD
        ) as classify:
            response = client.post("/api/clasificar/", {"image": self._upload()})

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["bin_color"], "Blue")
        self.assertEqual(classify.call_args.args[0], "jwt-de-prueba")

    def test_classify_proxy_requires_image(self):
        response = self._authenticated_client().post("/api/clasificar/", {})
        self.assertEqual(response.status_code, 400)
        self.assertIn("imagen", response.json()["error"].lower())

    def test_classify_proxy_maps_api_errors(self):
        client = self._authenticated_client()
        error = self.api.ApiError("El archivo no es una imagen valida.", 400)
        with mock.patch.object(self.api, "classify_image", side_effect=error):
            response = client.post("/api/clasificar/", {"image": self._upload("x.jpg", 10)})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "El archivo no es una imagen valida.")

    def test_classify_proxy_rejects_oversized_upload(self):
        """El limite se evalua en Django: la imagen no llega a FastAPI."""
        from django.test import override_settings

        client = self._authenticated_client()
        with override_settings(MAX_UPLOAD_BYTES=16):
            with mock.patch.object(self.api, "classify_image") as classify:
                response = client.post(
                    "/api/clasificar/", {"image": self._upload("grande.jpg", 4096)}
                )

        self.assertEqual(response.status_code, 413)
        self.assertIn("limite", response.json()["error"])
        classify.assert_not_called()

    def test_classify_proxy_rejects_get(self):
        response = self._authenticated_client().get("/api/clasificar/")
        self.assertEqual(response.status_code, 405)

    def test_history_page_renders_records(self):
        client = self._authenticated_client()
        with mock.patch.object(
            self.api, "fetch_history", return_value=[CLASSIFY_PAYLOAD]
        ):
            response = client.get("/historial/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Plastic Bottle", response.content.decode("utf-8"))

    def test_guide_is_exposed_through_proxy(self):
        client = self._authenticated_client()
        guide = {"total_bins": 1, "bins": [], "materials": []}
        with mock.patch.object(self.api, "fetch_bins_guide", return_value=guide):
            response = client.get("/api/guia/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total_bins"], 1)

    def test_classify_markup_keeps_camera_and_preview_exclusive(self):
        """La plantilla no debe dejar video y vista previa visibles a la vez.

        Regresion: `.camera-stage img/video { display: block }` vencia al
        atributo `hidden` (regla de autor > regla UA) y ambos elementos se
        repartian el flex: la foto capturada salia a medio encuadrar.
        """
        css = (
            FRONTEND_ROOT / "web" / "static" / "css" / "styles.css"
        ).read_text(encoding="utf-8")
        self.assertRegex(css, r"\[hidden\]\s*\{\s*display:\s*none\s*!important")

        html = (
            FRONTEND_ROOT / "web" / "templates" / "web" / "classify.html"
        ).read_text(encoding="utf-8")
        self.assertIn('<video id="camera"', html)
        self.assertIn('<img id="preview"', html)
        self.assertRegex(html, r'<img id="preview"[^>]*\bhidden\b')


if __name__ == "__main__":
    unittest.main()
