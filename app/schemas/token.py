"""
Schemas Pydantic relacionados con la autenticación JWT.
"""

from typing import Optional

from pydantic import BaseModel, Field


class Token(BaseModel):
    """Respuesta del endpoint de login: el token y su tipo."""

    access_token: str = Field(..., description="JWT firmado")
    token_type: str = Field(default="bearer", description="Tipo de token")


class TokenData(BaseModel):
    """
    Datos extraídos del payload de un token validado.

    `sub` (subject) contiene el identificador del usuario. Mantenerlo en
    un schema facilita escalar el token con más claims en el futuro
    (por ejemplo, roles o permisos).
    """

    sub: Optional[str] = None
