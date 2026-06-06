"""
Dependencias de autenticación reutilizables.

`get_current_user` es la pieza central para proteger rutas: extrae el
token Bearer, lo valida, busca al usuario y lo inyecta en el endpoint.
Cualquier ruta privada solo necesita: `Depends(get_current_user)`.
"""

from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.exceptions import (
    ExpiredTokenError,
    InvalidTokenError,
    UserNotFoundError,
)
from app.core.security import ExpiredSignatureError, JWTError, verify_token
from app.db.session import get_db
from app.models.user import Usuario
from app.repositories.user_repository import UserRepository

# Esquema OAuth2: indica a Swagger dónde obtener el token (botón "Authorize")
# y de dónde leerlo (header Authorization: Bearer <token>).
# `tokenUrl` apunta al endpoint de login.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> Usuario:
    """
    Resuelve el usuario autenticado a partir del token JWT.

    Pasos:
        1. Lee el token Bearer del header Authorization (vía oauth2_scheme).
        2. Valida y decodifica el JWT.
        3. Extrae el id del usuario del claim "sub".
        4. Verifica que el usuario exista en la base de datos.

    Raises:
        ExpiredTokenError: si el token expiró.
        InvalidTokenError: si el token es inválido o malformado.
        UserNotFoundError: si el usuario del token ya no existe.

    Returns:
        La instancia del usuario autenticado.
    """
    try:
        payload = verify_token(token)
    except ExpiredSignatureError as exc:
        # El token tiene firma válida pero ya pasó su fecha de expiración.
        raise ExpiredTokenError() from exc
    except JWTError as exc:
        # Firma inválida, token malformado, algoritmo incorrecto, etc.
        raise InvalidTokenError() from exc

    sub = payload.get("sub")
    if sub is None:
        raise InvalidTokenError("El token no contiene un subject válido")

    try:
        user_id = int(sub)
    except (TypeError, ValueError) as exc:
        raise InvalidTokenError("El subject del token no es válido") from exc

    usuario = UserRepository(db).get_by_id(user_id)
    if usuario is None:
        raise UserNotFoundError()

    return usuario


# Alias tipado para usar cómodamente en las firmas de los endpoints:
#   def endpoint(usuario: CurrentUser): ...
CurrentUser = Annotated[Usuario, Depends(get_current_user)]
