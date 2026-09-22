"""Rutas de la aplicacion web."""

from django.urls import path

from web import views

app_name = "web"

urlpatterns = [
    path("", views.home_view, name="home"),
]
