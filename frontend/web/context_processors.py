"""Context processor con ajustes expuestos a las plantillas."""

from django.conf import settings


def app_settings(request) -> dict:
    """Expone datos de la app y de la sesion a todas las plantillas."""
    return {
        "APP_NAME": "Punto Limpio",
        "API_BASE_URL": settings.FASTAPI_BASE_URL,
        "current_user": request.session.get("user"),
        "is_authenticated": bool(request.session.get("access_token")),
    }
