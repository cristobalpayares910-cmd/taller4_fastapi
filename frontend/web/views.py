"""Vistas del cliente web de EcoScan IA."""

import logging

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import RequestDataTooBig
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import ensure_csrf_cookie

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


# ---------------------------------------------------------------------------
# Pantallas autenticadas
# ---------------------------------------------------------------------------


@ensure_csrf_cookie
@login_required
def classify_view(request):
    """Pantalla de captura; incluye la guia de reciclaje traida de FastAPI."""
    guide = None
    try:
        guide = api_client.fetch_bins_guide()
    except api_client.ApiError as exc:
        # La guia es informativa: si falla, la pantalla sigue siendo utilizable.
        logger.warning("No se pudo obtener la guia de reciclaje: %s", exc.message)
    return render(request, "web/classify.html", {"guide": guide})


@login_required
def history_view(request):
    """Historial de clasificaciones renderizado en el servidor."""
    if request.GET.get("format") == "json":
        try:
            records = api_client.fetch_history(request.session[SESSION_TOKEN_KEY])
        except api_client.ApiError as exc:
            return JsonResponse({"error": exc.message}, status=exc.status_code)
        return JsonResponse({"results": records})

    records, error = [], None
    try:
        records = api_client.fetch_history(request.session[SESSION_TOKEN_KEY])
    except api_client.ApiError as exc:
        error = exc.message
        if exc.status_code == 401:
            clear_session(request)
            return redirect("web:login")
    return render(request, "web/history.html", {"records": records, "error": error})


# ---------------------------------------------------------------------------
# Proxy hacia FastAPI (el navegador solo habla con Django)
# ---------------------------------------------------------------------------


def _proxy_error(exc: api_client.ApiError):
    """Traduce un error de FastAPI a una respuesta JSON para el navegador."""
    return JsonResponse({"error": exc.message}, status=exc.status_code)


@login_required
def classify_api_view(request):
    """Recibe la imagen del navegador y la reenvia a FastAPI."""
    if request.method != "POST":
        return JsonResponse({"error": "Metodo no permitido."}, status=405)

    try:
        upload = request.FILES.get("image")
    except RequestDataTooBig:
        limit_mb = settings.MAX_UPLOAD_BYTES // (1024 * 1024)
        return JsonResponse(
            {"error": f"La imagen supera el limite de {limit_mb} MB."}, status=413
        )

    if upload is None:
        return JsonResponse({"error": "No se recibio ninguna imagen."}, status=400)

    if upload.size == 0:
        return JsonResponse({"error": "El archivo esta vacio."}, status=400)

    if upload.size > settings.MAX_UPLOAD_BYTES:
        limit_mb = settings.MAX_UPLOAD_BYTES // (1024 * 1024)
        return JsonResponse(
            {"error": f"La imagen supera el limite de {limit_mb} MB."}, status=413
        )

    try:
        payload = api_client.classify_image(
            request.session[SESSION_TOKEN_KEY],
            upload.name,
            upload.read(),
            upload.content_type,
        )
    except api_client.ApiError as exc:
        if exc.status_code == 401:
            clear_session(request)
        return _proxy_error(exc)

    return JsonResponse(payload, status=201)


@login_required
def bins_guide_api_view(request):
    """Expone la guia de reciclaje al navegador."""
    try:
        return JsonResponse(api_client.fetch_bins_guide())
    except api_client.ApiError as exc:
        return _proxy_error(exc)


# ---------------------------------------------------------------------------
# Operaciones
# ---------------------------------------------------------------------------


def healthz_view(request):
    """Healthcheck para el orquestador (Railway) y monitorizacion externa.

    Solo comprueba que Django responda; NO contacta a FastAPI para que el
    healthcheck no falle por una caida de un servicio ajeno.
    """
    return JsonResponse({"status": "ok"})
