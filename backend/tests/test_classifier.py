"""Pruebas del clasificador de residuos y de la taxonomia de materiales.

Ejecutar con:
    cd backend && python -m unittest discover -s tests -v
"""

import io
import os
import sys
import unittest

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.ml.classifier import InvalidImageError, WasteClassifier, load_image
from app.ml.labels import (
    MATERIAL_BY_TRASHNET_CLASS,
    TRASHNET_CLASSES,
    build_bins_guide,
    material_for_waste_type,
)


def make_image(color=(255, 255, 255), size=(96, 96), image_format="JPEG") -> bytes:
    """Genera una imagen solida en memoria para las pruebas."""
    buffer = io.BytesIO()
    Image.new("RGB", size, color).save(buffer, format=image_format)
    return buffer.getvalue()


class LoadImageTests(unittest.TestCase):
    def test_rejects_empty_payload(self):
        with self.assertRaises(InvalidImageError):
            load_image(b"")

    def test_rejects_non_image_payload(self):
        with self.assertRaises(InvalidImageError):
            load_image(b"esto no es una imagen")

    def test_rejects_tiny_image(self):
        with self.assertRaises(InvalidImageError):
            load_image(make_image(size=(16, 16)))

    def test_accepts_valid_image(self):
        image = load_image(make_image())
        self.assertEqual(image.mode, "RGB")


class HeuristicEngineTests(unittest.TestCase):
    """El entorno de pruebas no siempre tiene TensorFlow: se fuerza el respaldo."""

    def setUp(self):
        self.classifier = WasteClassifier()
        # Fuerza el motor heuristico sin depender de TensorFlow instalado.
        self.classifier._loaded = True
        self.classifier.engine = "heuristic"
        self.classifier._model = None

    def test_blue_bottle_maps_to_plastic_blue(self):
        prediction = self.classifier.predict(make_image((40, 90, 200)))
        self.assertEqual(prediction.waste_type, "Plastic Bottle")
        self.assertEqual(prediction.category, "Recyclable")
        self.assertEqual(prediction.bin_color, "Blue")
        self.assertEqual(prediction.engine, "heuristic")

    def test_white_sheet_maps_to_paper(self):
        prediction = self.classifier.predict(make_image((246, 246, 243)))
        self.assertEqual(prediction.waste_type, "Paper")

    def test_brown_box_maps_to_cardboard(self):
        prediction = self.classifier.predict(make_image((150, 105, 60)))
        self.assertEqual(prediction.waste_type, "Cardboard")

    def test_green_shade_maps_to_glass(self):
        prediction = self.classifier.predict(make_image((30, 120, 60)))
        self.assertEqual(prediction.bin_color, "Green")

    def test_dark_surface_maps_to_general_waste(self):
        prediction = self.classifier.predict(make_image((18, 18, 18)))
        self.assertEqual(prediction.category, "Non-Recyclable")
        self.assertEqual(prediction.bin_color, "Black")

    def test_response_contract_fields(self):
        """El contrato exigido: category, type y bin_color en el nivel raiz."""
        payload = self.classifier.predict(make_image((40, 90, 200))).as_dict()
        self.assertIn("category", payload)
        self.assertIn("type", payload)
        self.assertIn("bin_color", payload)
        self.assertIsInstance(payload["confidence"], float)
        self.assertLessEqual(len(payload["top_k"]), 3)

    def test_bright_neutral_scene_is_paper_not_metal(self):
        """Un escenario claro y sin color (papel, pared) no es aluminio.

        Regresion: el techo de brillo de la regla gris metálica no existía y
        cualquier fondo luminoso con contraste caía en "Aluminum Can".
        """
        features = {
            "brightness": 0.65,
            "mean_sat": 0.05,
            "hue": 0.0,
            "colorful_ratio": 0.0,
            "contrast": 0.30,
        }
        material_key, _confidence = self.classifier._guess_material(features)
        self.assertEqual(material_key, "paper")

    def test_midtone_gray_is_still_metal(self):
        """El techo de brillo no debe matar el caso metal de verdad."""
        features = {
            "brightness": 0.45,
            "mean_sat": 0.06,
            "hue": 0.0,
            "colorful_ratio": 0.0,
            "contrast": 0.25,
        }
        material_key, _confidence = self.classifier._guess_material(features)
        self.assertEqual(material_key, "metal")


class EngineFallbackTests(unittest.TestCase):
    """El campo `engine` debe decir quien decidio realmente el resultado."""

    def test_unmapped_imagenet_result_reports_heuristic_engine(self):
        from unittest import mock

        import numpy as np

        classifier = WasteClassifier()
        classifier._loaded = True
        classifier.engine = "mobilenet-imagenet"

        fake_tf = mock.MagicMock()
        fake_tf.keras.applications.mobilenet_v2.preprocess_input = lambda batch: batch
        # ImageNet solo devuelve clases sin mapeo a residuos.
        fake_tf.keras.applications.mobilenet_v2.decode_predictions = (
            lambda probabilities, top: [[(0, "sunglasses", 0.9)]]
        )
        fake_model = mock.MagicMock()
        fake_model.predict.return_value = np.zeros((1, 1000), dtype=np.float32)

        classifier._tf = fake_tf
        classifier._model = fake_model

        prediction = classifier.predict(make_image((180, 175, 170)))

        # Decide la heuristica, asi que el motor declarado debe ser esa.
        self.assertEqual(prediction.engine, "heuristic")
        # El clasificador sigue teniendo cargado el modelo de ImageNet.
        self.assertEqual(classifier.engine, "mobilenet-imagenet")


class TaxonomyTests(unittest.TestCase):
    def test_trashnet_classes_are_covered(self):
        for class_name in TRASHNET_CLASSES:
            self.assertIn(class_name, MATERIAL_BY_TRASHNET_CLASS)
        self.assertEqual(MATERIAL_BY_TRASHNET_CLASS["trash"].key, "trash")

    def test_bins_guide_groups_by_color(self):
        guide = build_bins_guide()
        colors = {entry["bin_color"] for entry in guide}
        self.assertIn("Blue", colors)
        self.assertIn("Green", colors)
        for entry in guide:
            self.assertTrue(entry["accepted"])
            self.assertTrue(entry["instructions"])

    def test_unknown_waste_type_falls_back_to_trash(self):
        self.assertEqual(material_for_waste_type("Nave espacial").key, "trash")


if __name__ == "__main__":
    unittest.main()
