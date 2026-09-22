"""Taxonomia de residuos, colores de contenedor y guia de reciclaje.

Esquema de colores usado (convencion de Puntos Limpios):

    Azul    -> plasticos y latas
    Amarillo-> papel y carton
    Verde   -> vidrio
    Marron  -> residuos organicos
    Negro   -> no reciclable (rechazo)
    Rojo    -> residuos peligrosos / especiales
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class WasteCategory(str, Enum):
    """Categoria general del residuo."""

    RECYCLABLE = "Recyclable"
    ORGANIC = "Organic"
    NON_RECYCLABLE = "Non-Recyclable"
    HAZARDOUS = "Hazardous"


class BinColor(str, Enum):
    """Color del contenedor de destino."""

    BLUE = "Blue"
    YELLOW = "Yellow"
    GREEN = "Green"
    BROWN = "Brown"
    BLACK = "Black"
    RED = "Red"


@dataclass(frozen=True)
class Material:
    """Metadato completo de una familia de residuos."""

    key: str
    trashnet_class: str
    waste_type: str
    category: WasteCategory
    bin_color: BinColor
    bin_name_es: str
    instructions: str
    examples: tuple[str, ...]
    imagenet_keywords: tuple[str, ...]


MATERIALS: dict[str, Material] = {
    "plastic": Material(
        key="plastic",
        trashnet_class="plastic",
        waste_type="Plastic Bottle",
        category=WasteCategory.RECYCLABLE,
        bin_color=BinColor.BLUE,
        bin_name_es="Contenedor azul (plasticos y latas)",
        instructions=(
            "Enjuaga el envase, quita la tapa y aplicalo para reducir volumen."
        ),
        examples=("Botella PET", "Envase de yogur", "Bolsa de plastico limpia"),
        imagenet_keywords=(
            "water_bottle",
            "pop_bottle",
            "pill_bottle",
            "plastic_bag",
            "water_jug",
            "beaker",
            "nipple",
            "lotion",
            "soap_dispenser",
            "bucket",
            "washbasin",
            "tub",
            "toothbrush",
            "syringe",
            "cd_player",
            "remote_control",
            "cellular_telephone",
            "keyboard",
            "mouse",
            "tape_player",
            "radio",
            "monitor",
            "laptop",
            "modem",
            "printer",
        ),
    ),
    "glass": Material(
        key="glass",
        trashnet_class="glass",
        waste_type="Glass Bottle",
        category=WasteCategory.RECYCLABLE,
        bin_color=BinColor.GREEN,
        bin_name_es="Contenedor verde (vidrio)",
        instructions=(
            "Retira tapas y corchos. No rompas el vidrio: puede cortar al "
            "personal de recoleccion."
        ),
        examples=("Botella de vidrio", "Frasco de mermelada", "Tarro de conserva"),
        imagenet_keywords=(
            "wine_bottle",
            "beer_bottle",
            "goblet",
            "vase",
            "pitcher",
            "water_glass",
            "measuring_cup",
            "cocktail_shaker",
            "whiskey_jug",
            "jar",
            "perfume",
            "lens_cap",
        ),
    ),
    "metal": Material(
        key="metal",
        trashnet_class="metal",
        waste_type="Aluminum Can",
        category=WasteCategory.RECYCLABLE,
        bin_color=BinColor.BLUE,
        bin_name_es="Contenedor azul (plasticos y latas)",
        instructions=(
            "Aplasta la lata y enjuagala. El aluminio es 100% reciclable."
        ),
        examples=("Lata de bebida", "Lata de conserva", "Papel de aluminio limpio"),
        imagenet_keywords=(
            "beer_can",
            "can_opener",
            "soda_can",
            "tin_can",
            "aluminum",
            "frying_pan",
            "kettle",
            "corkscrew",
            "pot",
            "dutch_oven",
            "wok",
            "spatula",
            "ladle",
            "strainer",
            "cleaver",
            "letter_opener",
            "screwdriver",
            "hammer",
            "wrench",
            "can",
        ),
    ),
    "paper": Material(
        key="paper",
        trashnet_class="paper",
        waste_type="Paper",
        category=WasteCategory.RECYCLABLE,
        bin_color=BinColor.YELLOW,
        bin_name_es="Contenedor amarillo (papel y carton)",
        instructions="Manten el papel seco y sin grasa; no lo arrugues en exceso.",
        examples=("Periodico", "Revista", "Hoja de cuaderno"),
        imagenet_keywords=(
            "newspaper",
            "book_jacket",
            "envelope",
            "menu",
            "comic_book",
            "notebook",
            "binder",
            "paper_towel",
            "toilet_tissue",
            "crossword_puzzle",
            "packet",
            "bannister",
            "carton",
            "paper",
        ),
    ),
    "cardboard": Material(
        key="cardboard",
        trashnet_class="cardboard",
        waste_type="Cardboard",
        category=WasteCategory.RECYCLABLE,
        bin_color=BinColor.YELLOW,
        bin_name_es="Contenedor amarillo (papel y carton)",
        instructions="Desarma la caja y retira cintas o etiquetas plasticas.",
        examples=("Caja de carton corrugado", "Caja de cereales", "Tubo de papel"),
        imagenet_keywords=(
            "carton",
            "packet",
            "crate",
            "shopping_basket",
            "wooden_spoon",
            "matchstick",
            "pencil_box",
            "cork",
            "barrel",
        ),
    ),
    "organic": Material(
        key="organic",
        trashnet_class="trash",
        waste_type="Organic Waste",
        category=WasteCategory.ORGANIC,
        bin_color=BinColor.BROWN,
        bin_name_es="Contenedor marron (organicos)",
        instructions=(
            "Separa restos de comida y poda. Idealmente usa bolsas compostables."
        ),
        examples=("Cascara de fruta", "Restos de verdura", "Cafe molido usado"),
        imagenet_keywords=(
            "banana",
            "apple",
            "orange",
            "lemon",
            "strawberry",
            "pineapple",
            "fig",
            "pomegranate",
            "broccoli",
            "cucumber",
            "mushroom",
            "corn",
            "cabbage",
            "cauliflower",
            "artichoke",
            "pizza",
            "bread",
            "bagel",
            "pretzel",
            "eggnog",
            "meat_loaf",
            "carbonara",
            "guacamole",
            "consomme",
            "trifle",
            "ice_cream",
            "chocolate_sauce",
            "dough",
            "head_cabbage",
            "acorn_squash",
            "spaghetti_squash",
            "butternut_squash",
            "zucchini",
            "bell_pepper",
            "hay",
            "ear",
            "rapeseed",
            "daisy",
            "pot",
            "coffee_mug",
            "teapot",
            "espresso",
            "cup",
        ),
    ),
    "trash": Material(
        key="trash",
        trashnet_class="trash",
        waste_type="General Waste",
        category=WasteCategory.NON_RECYCLABLE,
        bin_color=BinColor.BLACK,
        bin_name_es="Contenedor negro (no reciclable)",
        instructions=(
            "Residuo de rechazo: va al contenedor negro. Si esta contaminado "
            "con quimicos, derivar a punto de residuos peligrosos."
        ),
        examples=("Papel higienico usado", "Mascarilla", "Envase sucio no lavable"),
        imagenet_keywords=(),
    ),
}

# Orden canonico de las clases TrashNet -> material
TRASHNET_CLASSES: tuple[str, ...] = (
    "cardboard",
    "glass",
    "metal",
    "paper",
    "plastic",
    "trash",
)

MATERIAL_BY_TRASHNET_CLASS: dict[str, Material] = {}
for _trashnet_key, _material in MATERIALS.items():
    MATERIAL_BY_TRASHNET_CLASS.setdefault(_material.trashnet_class, _material)
# "trash" de TrashNet se resuelve a residuo no reciclable, no a organico.
MATERIAL_BY_TRASHNET_CLASS["trash"] = MATERIALS["trash"]

# Nombre de clase ImageNet (snake_case) -> material
IMAGENET_KEYWORD_TO_MATERIAL: dict[str, str] = {
    keyword: material.key
    for material in MATERIALS.values()
    for keyword in material.imagenet_keywords
}


def material_for_waste_type(waste_type: str) -> Material:
    """Busca un material por el nombre visible de `waste_type`."""
    for material in MATERIALS.values():
        if material.waste_type.lower() == waste_type.strip().lower():
            return material
    return MATERIALS["trash"]


def build_bins_guide() -> list[dict]:
    """Construye la guia de reciclaje consumida por `/api/v1/bins-guide`."""
    guide: dict[str, dict] = {}
    for material in MATERIALS.values():
        color = material.bin_color.value
        entry = guide.setdefault(
            color,
            {
                "bin_color": color,
                "bin_name": material.bin_name_es,
                "category": material.category.value,
                "accepted": [],
                "instructions": material.instructions,
            },
        )
        entry["accepted"].append(material.waste_type)
    return list(guide.values())
