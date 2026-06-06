"""
Middleware de cabeceras de seguridad.

Añade encabezados HTTP recomendados a todas las respuestas para mitigar
ataques comunes (clickjacking, MIME sniffing, fuga de referrer, etc.).
Son cabeceras estándar y de bajo riesgo; HSTS solo se envía en producción
(en desarrollo se sirve por HTTP y forzar HTTPS estorbaría).
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Inyecta cabeceras de seguridad en cada respuesta."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # Evita que el navegador "adivine" el tipo de contenido.
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        # Evita que la app se cargue dentro de un iframe (anti-clickjacking).
        response.headers.setdefault("X-Frame-Options", "DENY")
        # Limita la información del referrer enviada a otros orígenes.
        response.headers.setdefault(
            "Referrer-Policy", "strict-origin-when-cross-origin"
        )
        # Desactiva APIs sensibles del navegador que la API no necesita.
        response.headers.setdefault(
            "Permissions-Policy", "geolocation=(), microphone=(), camera=()"
        )

        # HSTS: fuerza HTTPS durante un año. Solo en producción.
        if settings.is_production:
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )

        return response
