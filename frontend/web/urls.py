"""Rutas de la aplicacion web."""

from django.urls import path

from web import views

app_name = "web"

urlpatterns = [
    # --- Paginas ----------------------------------------------------------
    path("", views.home_view, name="home"),
    path("ingresar/", views.login_view, name="login"),
    path("registro/", views.register_view, name="register"),
    path("salir/", views.logout_view, name="logout"),
    path("clasificar/", views.classify_view, name="classify"),
    path("historial/", views.history_view, name="history"),
    # --- Proxy JSON hacia FastAPI ----------------------------------------
    path("api/clasificar/", views.classify_api_view, name="classify_api"),
    path("api/guia/", views.bins_guide_api_view, name="bins_guide_api"),
    # --- Operaciones -------------------------------------------------------
    path("healthz", views.healthz_view, name="healthz"),
]
