"""Control de acceso del frontend basado en la sesion de Django."""

from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect

SESSION_TOKEN_KEY = "access_token"
SESSION_USER_KEY = "user"


def login_required(view):
    """Redirige al login si la sesion no contiene un JWT."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.session.get(SESSION_TOKEN_KEY):
            messages.warning(request, "Inicia sesion para continuar.")
            return redirect("web:login")
        return view(request, *args, **kwargs)

    return wrapper


def start_session(request, token_payload: dict) -> None:
    """Persiste el token y los datos del usuario en la sesion de Django."""
    request.session[SESSION_TOKEN_KEY] = token_payload["access_token"]
    request.session[SESSION_USER_KEY] = token_payload.get("user", {})
    request.session.set_expiry(token_payload.get("expires_in", 28800))


def clear_session(request) -> None:
    """Cierra la sesion del frontend."""
    request.session.flush()
