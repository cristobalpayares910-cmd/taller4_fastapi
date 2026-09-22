"""Vistas del cliente web del Punto Limpio."""

from django.shortcuts import render


def home_view(request):
    """Landing del proyecto."""
    return render(request, "web/home.html")
