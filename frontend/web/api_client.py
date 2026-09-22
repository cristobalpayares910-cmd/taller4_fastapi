"""Cliente HTTP del frontend Django hacia la API FastAPI.

Django actua como *backend for frontend*: guarda el JWT en la sesion firmada
y lo reenvia en la cabecera `Authorization`, de modo que el navegador nunca
manipula el token ni se ve expuesto a CORS.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)


class ApiError(Exception):
    """Error devuelto por la API FastAPI o por la red."""

    def __init__(self, message: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _extract_detail(payload: Any, fallback: str) -> str:
    """Normaliza el campo `detail` de FastAPI (string o lista de validacion)."""
    if not isinstance(payload, dict):
        return fallback
    detail = payload.get("detail")
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list):
        parts = []
        for item in detail:
            if isinstance(item, dict):
                location = ".".join(str(p) for p in item.get("loc", [])[1:])
                parts.append(f"{location}: {item.get('msg', 'dato invalido')}".strip(": "))
        if parts:
            return " | ".join(parts)
    return fallback


def _request(
    method: str,
    path: str,
    *,
    token: str | None = None,
    json_body: dict | None = None,
    form: dict | None = None,
    files: dict | None = None,
    timeout: float | None = None,
) -> Any:
    """Ejecuta una peticion contra FastAPI y normaliza los errores."""
    url = f"{settings.FASTAPI_BASE_URL.rstrip('/')}{path}"
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        response = httpx.request(
            method,
            url,
            headers=headers,
            json=json_body,
            data=form,
            files=files,
            timeout=timeout or settings.FASTAPI_TIMEOUT,
        )
    except httpx.TimeoutException as exc:
        logger.warning("Timeout llamando a %s: %s", url, exc)
        raise ApiError("El servicio de clasificacion tardo demasiado.", 504) from exc
    except httpx.HTTPError as exc:
        logger.error("Fallo de conexion con %s: %s", url, exc)
        raise ApiError(
            "No se pudo contactar el servicio de clasificacion (FastAPI).", 503
        ) from exc

    if response.status_code >= 400:
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        raise ApiError(
            _extract_detail(payload, f"Error {response.status_code} del servicio"),
            response.status_code,
        )

    if response.status_code == 204 or not response.content:
        return None
    try:
        return response.json()
    except ValueError as exc:
        raise ApiError("La respuesta del servicio no es JSON valido.", 502) from exc


# --- Autenticacion ---------------------------------------------------------
def register_user(email: str, full_name: str, password: str) -> dict:
    """Crea la cuenta en FastAPI."""
    return _request(
        "POST",
        "/api/v1/auth/register",
        json_body={"email": email, "full_name": full_name, "password": password},
    )


def login_user(email: str, password: str) -> dict:
    """Autentica al usuario y devuelve `{access_token, user, ...}`."""
    return _request(
        "POST",
        "/api/v1/auth/login/json",
        json_body={"email": email, "password": password},
    )


def fetch_profile(token: str) -> dict:
    """Obtiene el perfil asociado al token."""
    return _request("GET", "/api/v1/auth/me", token=token)


# --- Clasificacion ---------------------------------------------------------
# Margen extra sobre el timeout general: la primera inferencia carga el modelo.
INFERENCE_TIMEOUT = max(settings.FASTAPI_TIMEOUT, 60)


def classify_image(
    token: str,
    filename: str,
    content: bytes,
    content_type: str | None = None,
) -> dict:
    """Envia la imagen a FastAPI y devuelve la clasificacion."""
    files = {
        "file": (filename or "captura.jpg", content, content_type or "image/jpeg")
    }
    return _request(
        "POST",
        "/api/v1/classify-waste",
        token=token,
        files=files,
        timeout=INFERENCE_TIMEOUT,
    )


def fetch_history(token: str, limit: int = 15) -> list[dict]:
    """Historial de clasificaciones del usuario autenticado."""
    return _request("GET", f"/api/v1/history?limit={limit}", token=token)


# --- Guia de reciclaje (endpoint publico) ----------------------------------
def fetch_bins_guide() -> dict:
    """Guia de contenedores e instrucciones de reciclaje."""
    return _request("GET", "/api/v1/bins-guide")
