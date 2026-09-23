"""Endpoints de clasificacion de residuos e historial."""

from __future__ import annotations

import logging
from functools import lru_cache

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import get_current_user
from app.ml import InvalidImageError, get_classifier
from app.ml.labels import MATERIALS, BinColor, build_bins_guide, material_for_waste_type
from app.models import Classification, User
from app.schemas import (
    BinGuideItem,
    BinsGuideResponse,
    ClassifyResponse,
    MaterialGuideItem,
    TopPrediction,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Residuos"])

ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
    "image/heic",
    "image/heif",
    "application/octet-stream",
}


@router.post(
    "/classify-waste",
    response_model=ClassifyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Clasificar un residuo a partir de una fotografia",
    description=(
        "Recibe la imagen capturada con la camara (`multipart/form-data`, campo "
        "`file`) y devuelve la categoria, el tipo de residuo y el color del "
        "contenedor donde debe depositarse.\n\n"
        "Requiere un JWT valido en la cabecera `Authorization`."
    ),
    responses={
        400: {"description": "Archivo vacio, demasiado grande o formato invalido"},
        401: {"description": "Token ausente o expirado"},
        413: {"description": "La imagen supera el tamano maximo permitido"},
        503: {"description": "El motor de inferencia no esta disponible"},
    },
)
async def classify_waste(
    file: UploadFile = File(..., description="Fotografia del residuo"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ClassifyResponse:
    """Ejecuta la inferencia y persiste el resultado en el historial."""
    if file.content_type and file.content_type.lower() not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Formato no soportado: {file.content_type}. Usa JPEG, PNG o WEBP.",
        )

    payload = await file.read()
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo recibido esta vacio.",
        )

    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(payload) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"La imagen supera el limite de {settings.max_upload_mb} MB.",
        )

    classifier = get_classifier()
    try:
        # La inferencia es bloqueante: se ejecuta en el threadpool de FastAPI
        # para no detener el event loop mientras corre el modelo.
        prediction = await run_in_threadpool(classifier.predict, payload)
    except InvalidImageError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except Exception as exc:  # pragma: no cover - salvaguarda
        logger.exception("Error inesperado durante la clasificacion")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El clasificador no pudo procesar la imagen. Reintenta.",
        ) from exc

    record = Classification(
        user_id=current_user.id,
        waste_type=prediction.waste_type,
        category=prediction.category,
        bin_color=prediction.bin_color,
        confidence=prediction.confidence,
        engine=prediction.engine,
        note=prediction.instructions,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    return ClassifyResponse(
        id=record.id,
        category=record.category,
        type=record.waste_type,
        bin_color=record.bin_color,
        bin_name=prediction.bin_name,
        instructions=prediction.instructions,
        confidence=record.confidence,
        engine=record.engine,
        material=prediction.material,
        top_k=[TopPrediction(**item) for item in prediction.as_dict()["top_k"]],
        created_at=record.created_at,
    )


@lru_cache(maxsize=1)
def _full_guide() -> BinsGuideResponse:
    """Guia completa. Es constante, por lo que se construye una sola vez."""
    bins = build_bins_guide()
    materials = [
        MaterialGuideItem(
            material=material.key,
            type=material.waste_type,
            category=material.category.value,
            bin_color=material.bin_color.value,
            examples=list(material.examples),
            instructions=material.instructions,
        )
        for material in MATERIALS.values()
    ]
    return BinsGuideResponse(
        total_bins=len(bins),
        bins=[BinGuideItem(**item) for item in bins],
        materials=materials,
    )


@router.get(
    "/bins-guide",
    response_model=BinsGuideResponse,
    summary="Guia de reciclaje y colores de contenedor",
    description=(
        "Devuelve las instrucciones de reciclaje asociadas a cada contenedor "
        "del Punto Limpio, mas una ficha por familia de material. "
        "Endpoint publico: no requiere token."
    ),
)
def read_bins_guide(
    response: Response,
    color: BinColor | None = Query(
        default=None,
        description="Filtra la guia por color de contenedor",
    ),
) -> BinsGuideResponse:
    """Instrucciones de reciclaje, opcionalmente filtradas por color."""
    guide = _full_guide()
    if color is None:
        # El resultado es identico entre peticiones: se permite cachearlo.
        response.headers["Cache-Control"] = "public, max-age=3600"
        return guide

    return BinsGuideResponse(
        total_bins=sum(1 for item in guide.bins if item.bin_color == color.value),
        bins=[item for item in guide.bins if item.bin_color == color.value],
        materials=[item for item in guide.materials if item.bin_color == color.value],
    )


@router.get(
    "/history",
    response_model=list[ClassifyResponse],
    summary="Historial de clasificaciones del usuario",
)
def read_history(
    limit: int = Query(20, ge=1, le=100, description="Cantidad maxima de registros"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ClassifyResponse]:
    """Devuelve las ultimas clasificaciones del usuario autenticado."""
    records = db.scalars(
        select(Classification)
        .where(Classification.user_id == current_user.id)
        .order_by(Classification.created_at.desc())
        .limit(limit)
    ).all()

    results = []
    for record in records:
        material = material_for_waste_type(record.waste_type)
        results.append(
            ClassifyResponse(
                id=record.id,
                category=record.category,
                type=record.waste_type,
                bin_color=record.bin_color,
                bin_name=material.bin_name_es,
                instructions=record.note or material.instructions,
                confidence=record.confidence,
                engine=record.engine,
                material=material.key,
                created_at=record.created_at,
            )
        )
    return results
