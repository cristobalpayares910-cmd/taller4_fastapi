"""Vistas del cliente web del Punto Limpio."""

import logging

from django.contrib import messages
from django.shortcuts import redirect, render

from web import api_client
from web.decorators import (
    SESSION_TOKEN_KEY,
    clear_session,
    login_required,
    start_session,
)

logger = logging.getLogger(__name__)


def home_view(request):
    """Landing publica; redirige al area privada si ya hay sesion activa."""
    if request.session.get(SESSION_TOKEN_KEY):
        return redirect("web:classify")
    return render(request, "web/home.html")


def login_view(request):
    """Formulario y procesamiento del inicio de sesion."""
    if request.session.get(SESSION_TOKEN_KEY):
        return redirect("web:classify")

    if request.method == "POST":
        email = (request.POST.get("email") or "").strip()
        password = request.POST.get("password") or ""

        if not email or not password:
            messages.error(request, "Debes completar correo y contrasena.")
            return render(request, "web/login.html", {"email": email}, status=400)

        try:
            payload = api_client.login_user(email, password)
        except api_client.ApiError as exc:
            messages.error(request, exc.message)
            return render(request, "web/login.html", {"email": email}, status=400)

        start_session(request, payload)
        messages.success(request, f"Bienvenido/a, {payload['user']['full_name']}.")
        return redirect("web:classify")

    return render(request, "web/login.html")


def register_view(request):
    """Formulario y procesamiento del registro de usuario."""
    if request.session.get(SESSION_TOKEN_KEY):
        return redirect("web:classify")

    if request.method == "POST":
        email = (request.POST.get("email") or "").strip()
        full_name = (request.POST.get("full_name") or "").strip()
        password = request.POST.get("password") or ""
        password2 = request.POST.get("password2") or ""
        form_data = {"email": email, "full_name": full_name}

        if password != password2:
            messages.error(request, "Las contrasenas no coinciden.")
            return render(request, "web/register.html", form_data, status=400)

        try:
            api_client.register_user(email, full_name, password)
            payload = api_client.login_user(email, password)
        except api_client.ApiError as exc:
            messages.error(request, exc.message)
            return render(request, "web/register.html", form_data, status=400)

        start_session(request, payload)
        messages.success(request, "Cuenta creada. Ya puedes clasificar residuos.")
        return redirect("web:classify")

    return render(request, "web/register.html")


@login_required
def logout_view(request):
    """Cierra la sesion del frontend (el JWT queda descartado)."""
    clear_session(request)
    messages.info(request, "Sesion cerrada correctamente.")
    return redirect("web:home")


@login_required
def classify_view(request):
    """Pantalla principal de captura y clasificacion."""
    return render(request, "web/classify.html")
