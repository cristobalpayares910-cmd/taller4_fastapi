"""Manejadores de errores globales con respuestas JSON homogeneas."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)

# Traduccion de los codigos de error de Pydantic a mensajes para el cliente.
VALIDATION_MESSAGES: dict[str, str] = {
    "missing": "Campo obligatorio",
    "string_too_short": "El texto es demasiado corto",
    "string_too_long": "El texto es demasiado largo",
    "value_error": "Valor invalido",
    "int_parsing": "Se esperaba un numero entero",
    "float_parsing": "Se esperaba un numero",
    "bool_parsing": "Se esperaba un booleano",
    "json_invalid": "El cuerpo de la peticion no es JSON valido",
    "too_short": "Se recibieron menos elementos de los requeridos",
    "too_long": "Se recibieron mas elementos de los permitidos",
}


def _humanize(error: dict) -> dict:
    """Convierte un error de validacion en un item legible."""
    location = [str(part) for part in error.get("loc", []) if part not in ("body", "query", "path")]
    field = ".".join(location) or "cuerpo"
    message = VALIDATION_MESSAGES.get(error.get("type", ""), error.get("msg") or "Dato invalido")
    return {"field": field, "message": message, "type": error.get("type", "invalid")}


def register_exception_handlers(app: FastAPI) -> None:
    """Registra los manejadores en la aplicacion."""

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """422 con un detalle legible en lugar del volcado crudo de Pydantic."""
        errors = [_humanize(error) for error in exc.errors()]
        summary = "; ".join(f"{item['field']}: {item['message']}" for item in errors)
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"error": summary or "Datos invalidos", "errors": errors},
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        """Mantiene `detail` y agrega `error` para clientes simples."""
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.detail, "detail": exc.detail},
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """Evita filtrar trazas internas al cliente."""
        logger.exception("Error no controlado en %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "Error interno del servidor.",
                "detail": "Ocurrio un fallo inesperado. Reintenta en unos segundos.",
            },
        )
