"""Inferencia del clasificador de residuos.

El servicio intenta, en este orden, usar el motor mas potente disponible:

1. ``trashnet``        -> modelo MobileNetV2 ya afinado con TrashNet (6 clases).
                          Se activa cuando existe el archivo indicado en
                          ``TRASHNET_MODEL_PATH``.
2. ``mobilenet-imagenet`` -> MobileNetV2 preentrenado en ImageNet + mapeo
                          semantico de las clases de ImageNet a familias de
                          residuos (ver ``labels.IMAGENET_KEYWORD_TO_MATERIAL``).
3. ``heuristic``       -> clasificador de respaldo basado en color/brillo.
                          Se usa cuando TensorFlow no esta instalado (p. ej. en
                          Vercel Serverless por el limite de tamano) o cuando el
                          modelo no pudo inicializarse.

El motor efectivamente usado se informa en el campo ``engine`` de la respuesta,
de modo que el resultado nunca se presenta como algo que no es.
"""

from __future__ import annotations

import io
import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

from app.config import settings
from app.ml.labels import (
    IMAGENET_KEYWORD_TO_MATERIAL,
    MATERIAL_BY_TRASHNET_CLASS,
    MATERIALS,
    TRASHNET_CLASSES,
    Material,
)

logger = logging.getLogger(__name__)

# Evita bombas de descompresion al abrir imagenes de usuarios.
Image.MAX_IMAGE_PIXELS = settings.max_image_pixels * settings.max_image_pixels


class InvalidImageError(ValueError):
    """La carga util recibida no es una imagen procesable."""


@dataclass
class Prediction:
    """Resultado de una inferencia."""

    category: str
    waste_type: str
    bin_color: str
    confidence: float
    engine: str
    bin_name: str
    instructions: str
    material: str
    top_k: list[tuple[str, float]] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "category": self.category,
            "type": self.waste_type,
            "bin_color": self.bin_color,
            "confidence": round(self.confidence, 4),
            "engine": self.engine,
            "material": self.material,
            "bin_name": self.bin_name,
            "instructions": self.instructions,
            "top_k": [
                {"type": label, "confidence": round(score, 4)}
                for label, score in self.top_k
            ],
        }


def load_image(payload: bytes) -> Image.Image:
    """Decodifica y normaliza la imagen recibida (RGB + orientacion EXIF)."""
    if not payload:
        raise InvalidImageError("El archivo esta vacio.")

    try:
        with Image.open(io.BytesIO(payload)) as probe:
            probe.verify()  # valida la integridad del contenedor
        image = Image.open(io.BytesIO(payload))
        image = ImageOps.exif_transpose(image)
        image = image.convert("RGB")
    except InvalidImageError:
        raise
    except Exception as exc:  # PIL lanza varios tipos segun el formato
        raise InvalidImageError("El archivo no es una imagen valida.") from exc

    if min(image.size) < 32:
        raise InvalidImageError("La imagen es demasiado pequena para clasificar.")
    return image


def _material_from_key(key: str) -> Material:
    return MATERIALS.get(key, MATERIALS["trash"])


class WasteClassifier:
    """Cargador perezoso del modelo y motor de clasificacion."""

    def __init__(
        self,
        model_path: str | Path | None = None,
        image_size: int | None = None,
    ) -> None:
        self.model_path = Path(model_path) if model_path else None
        self.image_size = image_size or settings.image_size
        self.engine = "heuristic"
        self._model = None
        self._tf = None
        self._lock = threading.Lock()
        self._loaded = False
        self.load_error: str | None = None

    # --- Carga ------------------------------------------------------------
    def _load(self) -> None:
        """Inicializa el motor de inferencia una sola vez por proceso."""
        if self._loaded:
            return
        with self._lock:
            if self._loaded:
                return
            self._loaded = True

            try:
                import tensorflow as tf  # import pesado: solo si esta disponible
            except Exception as exc:  # ImportError o fallo de librerias nativas
                self.load_error = f"TensorFlow no disponible ({type(exc).__name__})"
                logger.warning(
                    "%s: se usara el clasificador heuristico de respaldo.",
                    self.load_error,
                )
                self.engine = "heuristic"
                return

            self._tf = tf
            self._configure_quiet_logging(tf)

            if self.model_path and self.model_path.exists():
                try:
                    self._model = tf.keras.models.load_model(self.model_path)
                    self.engine = "trashnet"
                    logger.info("Modelo TrashNet cargado desde %s", self.model_path)
                    return
                except Exception as exc:
                    self.load_error = f"No se pudo cargar el modelo TrashNet: {exc}"
                    logger.error(self.load_error)

            try:
                self._model = tf.keras.applications.MobileNetV2(
                    weights="imagenet", include_top=True
                )
                self.engine = "mobilenet-imagenet"
                logger.info("MobileNetV2 (ImageNet) listo para inferencia.")
            except Exception as exc:
                self.load_error = f"No se pudo inicializar MobileNetV2: {exc}"
                logger.error(self.load_error)
                self._model = None
                self.engine = "heuristic"

    @staticmethod
    def _configure_quiet_logging(tf) -> None:
        try:
            tf.get_logger().setLevel("ERROR")
        except Exception:  # pragma: no cover - defensivo
            pass

    @property
    def is_ready(self) -> bool:
        """Indica si el modelo ya fue inicializado (no lo fuerza)."""
        return self._loaded

    def warm_up(self) -> None:
        """Fuerza la carga del modelo (usado en el arranque del servicio)."""
        self._load()

    # --- Preprocesado -----------------------------------------------------
    def _prepare(self, image: Image.Image) -> np.ndarray:
        resized = image.resize((self.image_size, self.image_size), Image.BILINEAR)
        array = np.asarray(resized, dtype=np.float32)
        assert self._tf is not None
        batch = np.expand_dims(array, axis=0)
        return self._tf.keras.applications.mobilenet_v2.preprocess_input(batch)

    # --- API publica ------------------------------------------------------
    def predict(self, payload: bytes) -> Prediction:
        """Clasifica el contenido binario de una imagen."""
        image = load_image(payload)
        self._load()

        try:
            if self.engine == "trashnet" and self._model is not None:
                return self._predict_trashnet(image)
            if self.engine == "mobilenet-imagenet" and self._model is not None:
                return self._predict_imagenet(image)
        except Exception as exc:  # nunca romper la peticion por un fallo del modelo
            logger.exception("Fallo la inferencia con el motor %s", self.engine)
            self.load_error = f"Fallo de inferencia: {exc}"
            self.engine = "heuristic"
            self._model = None

        return self._predict_heuristic(image)

    # --- Motores ----------------------------------------------------------
    def _predict_trashnet(self, image: Image.Image) -> Prediction:
        batch = self._prepare(image)
        probabilities = self._model.predict(batch, verbose=0)[0]

        ranked = sorted(
            zip(TRASHNET_CLASSES, (float(p) for p in probabilities), strict=False),
            key=lambda item: item[1],
            reverse=True,
        )
        best_class, confidence = ranked[0]
        material = MATERIAL_BY_TRASHNET_CLASS.get(best_class, MATERIALS["trash"])

        return self._build_prediction(
            material=material,
            confidence=confidence,
            top_k=[
                (MATERIAL_BY_TRASHNET_CLASS.get(name, MATERIALS["trash"]).waste_type, score)
                for name, score in ranked[:3]
            ],
        )

    def _predict_imagenet(self, image: Image.Image) -> Prediction:
        """Usa la cabeza ImageNet y traduce las clases a familias de residuos."""
        tf = self._tf
        batch = self._prepare(image)
        probabilities = self._model.predict(batch, verbose=0)[0]

        decoded = tf.keras.applications.mobilenet_v2.decode_predictions(
            np.expand_dims(probabilities, axis=0), top=10
        )[0]

        material_scores: dict[str, float] = {}
        for _index, class_name, score in decoded:
            material_key = IMAGENET_KEYWORD_TO_MATERIAL.get(class_name)
            if material_key is None:
                continue
            material_scores[material_key] = (
                material_scores.get(material_key, 0.0) + float(score)
            )

        if not material_scores:
            # ImageNet no reconocio nada recyclable: decide la heuristica y el
            # campo engine debe decirlo (no se puede presentar un resultado
            # heuristico como algo que classifico el modelo).
            prediction = self._predict_heuristic(image)
            prediction.engine = "heuristic"
            return prediction

        ranked = sorted(material_scores.items(), key=lambda item: item[1], reverse=True)
        best_key, confidence = ranked[0]
        material = _material_from_key(best_key)

        return self._build_prediction(
            material=material,
            # La probabilidad acumulada de las clases que mapean al material
            # elegido; se acota a 0.99 porque ImageNet no conoce la categoria.
            confidence=min(0.99, confidence),
            top_k=[
                (_material_from_key(key).waste_type, score)
                for key, score in ranked[:3]
            ],
        )

    def _predict_heuristic(self, image: Image.Image) -> Prediction:
        """Respaldo determinista basado en color, saturacion y brillo."""
        features = self._color_features(image)
        material_key, confidence = self._guess_material(features)
        material = _material_from_key(material_key)

        alternatives = [
            (_material_from_key(key).waste_type, round(confidence * factor, 4))
            for key, factor in self._heuristic_ranking(features, material_key)
        ]
        return self._build_prediction(
            material=material,
            confidence=confidence,
            top_k=alternatives,
        )

    def _build_prediction(
        self,
        material: Material,
        confidence: float,
        top_k: list[tuple[str, float]],
    ) -> Prediction:
        return Prediction(
            category=material.category.value,
            waste_type=material.waste_type,
            bin_color=material.bin_color.value,
            confidence=float(confidence),
            engine=self.engine,
            bin_name=material.bin_name_es,
            instructions=material.instructions,
            material=material.key,
            top_k=top_k,
        )

    # --- Analisis de color (motor heuristico) -----------------------------
    @staticmethod
    def _color_features(image: Image.Image) -> dict[str, float]:
        """Estadisticos de color baratos y suficientes para el respaldo."""
        sample = image.copy()
        sample.thumbnail((160, 160))

        hsv = np.asarray(sample.convert("HSV"), dtype=np.float32) / 255.0
        hue, saturation, value = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]

        # La hue solo es representativa en pixeles con color real.
        colorful = saturation > 0.20
        dominant_hue = (
            float(np.median(hue[colorful])) if bool(colorful.any()) else 0.0
        )

        return {
            "brightness": float(value.mean()),
            "mean_sat": float(saturation.mean()),
            "hue": dominant_hue,
            "colorful_ratio": float(colorful.mean()),
            "contrast": float(value.std()),
        }

    @staticmethod
    def _guess_material(features: dict[str, float]) -> tuple[str, float]:
        """Reglas ordenadas de mas especifica a mas generica."""
        hue = features["hue"]
        sat = features["mean_sat"]
        bright = features["brightness"]

        # Papel: luminoso y practicamente sin color (un fondo claro con
        # objetos oscuros dominantes baja el brillo medio de la escena, por
        # eso el umbral no puede ser solo 0.72).
        if bright > 0.60 and sat < 0.16:
            return "paper", 0.52
        # Carton: tono marron/naranja con luminosidad media.
        if 0.02 <= hue <= 0.14 and 0.18 <= sat <= 0.62 and 0.25 <= bright <= 0.84:
            return "cardboard", 0.50
        # Plasticos: tonos azules/cyan dominantes (botellas PET).
        if 0.45 <= hue <= 0.80 and sat > 0.20:
            return "plastic", 0.48
        # Vidrio: verdes profundos (botellas de vidrio).
        if 0.20 <= hue <= 0.45 and sat > 0.18:
            return "glass", 0.46
        # Rojos/naranjas vivos: latas pintadas o envases metalicos.
        if (hue <= 0.03 or hue >= 0.95) and sat > 0.30:
            return "metal", 0.44
        # Rango amarillo: papel/carton antes que organico cuando hay poco color.
        if 0.10 < hue < 0.20 and sat < 0.45:
            return "cardboard", 0.42
        # Colores vivos con alto contraste: restos organicos.
        if sat > 0.32 and features["colorful_ratio"] > 0.5:
            return "organic", 0.40
        # Superficies oscuras y planas: residuo de rechazo.
        if bright < 0.25:
            return "trash", 0.38
        # Grisaceo luminoso de tono medio: metales sin pintar. Un escenario
        # blanco (papel, pared) ya se resolvio arriba como paper; sin este
        # techo de brillo cualquier fondo claro caia en "Aluminum Can".
        if sat < 0.12 and features["contrast"] > 0.12 and bright <= 0.60:
            return "metal", 0.36
        return "trash", 0.32

    @staticmethod
    def _heuristic_ranking(
        features: dict[str, float], chosen: str
    ) -> list[tuple[str, float]]:
        """Alternativas plausibles para presentar un top-3 honesto."""
        fallback_order = ["trash", "metal", "paper", "plastic", "glass", "cardboard"]
        base = 0.8
        ranking: list[tuple[str, float]] = []
        for material_key in fallback_order:
            if material_key == chosen:
                continue
            ranking.append((material_key, base))
            base *= 0.55
            if len(ranking) == 2:
                break
        return ranking


_classifier: WasteClassifier | None = None
_classifier_lock = threading.Lock()


def get_classifier() -> WasteClassifier:
    """Singleton del clasificador: el modelo se carga una sola vez."""
    global _classifier
    if _classifier is None:
        with _classifier_lock:
            if _classifier is None:
                _classifier = WasteClassifier(
                    model_path=settings.trashnet_model_path or None
                )
    return _classifier
