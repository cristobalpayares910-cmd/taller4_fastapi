"""Esquemas Pydantic: contrato de entrada/salida de la API."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field

# Alias documentados: se reutilizan en todos los esquemas para que Swagger
# muestre ejemplos reales en lugar de valores genericos.
ExampleColor = Annotated[str, Field(examples=["Blue"])]

# ---------------------------------------------------------------------------
# Autenticacion
# ---------------------------------------------------------------------------


class UserRegister(BaseModel):
    """Datos necesarios para registrar un usuario nuevo."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "vecina@correo.cl",
                "full_name": "Ana Soto",
                "password": "Recicla2026",
            }
        }
    )

    email: EmailStr = Field(..., examples=["vecina@correo.cl"])
    full_name: str = Field(..., min_length=3, max_length=120, examples=["Ana Soto"])
    password: str = Field(
        ...,
        min_length=8,
        max_length=72,
        examples=["Recicla2026"],
        description="Minimo 8 caracteres. Se persiste unicamente como hash bcrypt.",
    )


class UserLogin(BaseModel):
    """Credenciales para el endpoint JSON de login."""

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=72)


class UserOut(BaseModel):
    """Usuario expuesto por la API (nunca incluye la contrasena)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str
    is_active: bool
    is_admin: bool
    created_at: datetime


class Token(BaseModel):
    """Respuesta estandar del endpoint de login."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Segundos de vigencia del token")
    user: UserOut


# ---------------------------------------------------------------------------
# Clasificacion de residuos
# ---------------------------------------------------------------------------


class TopPrediction(BaseModel):
    """Alternativa secundaria devuelta junto al resultado principal."""

    type: str = Field(..., examples=["Glass Bottle"])
    confidence: float = Field(..., ge=0, le=1, examples=[0.14])


class ClassifyResponse(BaseModel):
    """Resultado de clasificar una fotografia de residuo."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": 12,
                "category": "Recyclable",
                "type": "Plastic Bottle",
                "bin_color": "Blue",
                "bin_name": "Contenedor azul (plasticos y latas)",
                "instructions": "Enjuaga el envase, quita la tapa y aplicalo.",
                "confidence": 0.93,
                "engine": "trashnet",
                "material": "plastic",
                "top_k": [{"type": "Aluminum Can", "confidence": 0.05}],
                "created_at": "2026-09-22T17:47:29Z",
            }
        }
    )

    id: int | None = Field(
        default=None, description="Identificador del registro en el historial"
    )
    category: str = Field(..., examples=["Recyclable"])
    type: str = Field(
        ...,
        examples=["Plastic Bottle"],
        description="Tipo de residuo detectado",
    )
    bin_color: ExampleColor = Field(
        ..., description="Color del contenedor de destino"
    )
    bin_name: str = Field(..., examples=["Contenedor azul (plasticos y latas)"])
    instructions: str = Field(..., description="Como preparar el residuo")
    confidence: float = Field(..., ge=0, le=1, examples=[0.93])
    engine: str = Field(
        ...,
        description=(
            "Motor de inferencia utilizado: `trashnet`, `mobilenet-imagenet` "
            "o `heuristic` (respaldo por color)."
        ),
        examples=["mobilenet-imagenet"],
    )
    material: str = Field(..., examples=["plastic"])
    top_k: list[TopPrediction] = Field(
        default_factory=list,
        description="Alternativas secundarias ordenadas por probabilidad",
    )
    created_at: datetime | None = Field(
        default=None, description="Fecha de la clasificacion (UTC)"
    )


# ---------------------------------------------------------------------------
# Guia de contenedores (/bins-guide)
# ---------------------------------------------------------------------------


class BinGuideItem(BaseModel):
    """Instrucciones asociadas a un color de contenedor."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "bin_color": "Blue",
                "bin_name": "Contenedor azul (plasticos y latas)",
                "category": "Recyclable",
                "accepted": ["Plastic Bottle", "Aluminum Can"],
                "instructions": "Enjuaga el envase y aplicalo para reducir volumen.",
            }
        }
    )

    bin_color: ExampleColor
    bin_name: str = Field(..., description="Nombre del contenedor en espanol")
    category: str = Field(..., description="Categoria general que recibe")
    accepted: list[str] = Field(
        ..., description="Tipos de residuo aceptados en este contenedor"
    )
    instructions: str = Field(..., description="Como preparar el residuo")


class MaterialGuideItem(BaseModel):
    """Ficha de reciclaje por familia de residuo."""

    material: str = Field(..., examples=["plastic"])
    type: str = Field(..., examples=["Plastic Bottle"])
    category: str = Field(..., examples=["Recyclable"])
    bin_color: ExampleColor
    examples: list[str] = Field(..., description="Ejemplos cotidianos del material")
    instructions: str


class BinsGuideResponse(BaseModel):
    """Respuesta completa de la guia de reciclaje."""

    total_bins: int = Field(..., examples=[6])
    bins: list[BinGuideItem]
    materials: list[MaterialGuideItem]
