"""Rutas raiz del frontend Django."""

from django.urls import include, path

urlpatterns = [
    path("", include("web.urls")),
]
