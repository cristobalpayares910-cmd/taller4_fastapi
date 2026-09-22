"""Modulo de Machine Learning: carga del modelo y clasificacion de residuos."""

from app.ml.classifier import (
    InvalidImageError,
    Prediction,
    WasteClassifier,
    get_classifier,
)

__all__ = [
    "InvalidImageError",
    "Prediction",
    "WasteClassifier",
    "get_classifier",
]
