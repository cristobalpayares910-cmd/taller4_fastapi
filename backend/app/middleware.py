"""Middleware transversal: tiempo de proceso y cache de endpoints estaticos."""

from __future__ import annotations

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class ProcessTimeMiddleware(BaseHTTPMiddleware):
    """Agrega `X-Process-Time-Ms` para medir la latencia del servicio."""

    async def dispatch(self, request: Request, call_next):
        started = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - started) * 1000
        response.headers["X-Process-Time-Ms"] = f"{elapsed_ms:.1f}"
        return response


# Rutas cuyo contenido no cambia entre peticiones: se pueden cachear.
CACHEABLE_PREFIXES = ("/api/v1/bins-guide",)


class StaticCacheMiddleware(BaseHTTPMiddleware):
    """Marca como cacheables las respuestas de datos de referencia."""

    def __init__(self, app, max_age: int = 3600) -> None:
        super().__init__(app)
        self.max_age = max_age

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if (
            request.method == "GET"
            and response.status_code == 200
            and request.url.path.startswith(CACHEABLE_PREFIXES)
        ):
            response.headers.setdefault(
                "Cache-Control", f"public, max-age={self.max_age}"
            )
        return response
