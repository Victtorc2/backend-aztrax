"""
Dependencia de autenticación por API key para endpoints del catálogo público.

El catálogo envía la API key en el header `X-API-Key`. Si no coincide con
CATALOG_API_KEY del settings, responde 403.
"""

import secrets

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.core.config import settings

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(
    api_key: str | None = Security(_api_key_header),
) -> str:
    """Valida que el header X-API-Key coincida con el configurado.

    Compara ignorando espacios/saltos de línea sobrantes (un `\\n` invisible
    pegado en el panel de Railway es la causa típica de un 403 con la key
    aparentemente correcta) y en tiempo constante para evitar timing attacks.
    """
    expected = (settings.CATALOG_API_KEY or "").strip()
    provided = (api_key or "").strip()
    if not provided or not expected or not secrets.compare_digest(provided, expected):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API key inválida o ausente",
        )
    return api_key
