"""Rutas de la aplicacion web."""

from django.urls import path

from web import views

app_name = "web"

urlpatterns = [
    path("", views.home_view, name="home"),
    path("ingresar/", views.login_view, name="login"),
    path("registro/", views.register_view, name="register"),
    path("salir/", views.logout_view, name="logout"),
    path("clasificar/", views.classify_view, name="classify"),
]
