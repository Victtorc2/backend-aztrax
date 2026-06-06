"""
Utilidades de seguridad: hashing de contraseñas y manejo de JWT.

Este módulo NO conoce nada de FastAPI ni de la base de datos: solo
expone funciones puras y reutilizables. Eso lo hace fácil de testear
y de reutilizar en futuras fases del sistema.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from jose import ExpiredSignatureError, JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

# Contexto de Passlib configurado con bcrypt como algoritmo de hash.
# `deprecated="auto"` permite migrar a algoritmos más nuevos en el futuro
# sin romper los hashes ya almacenados.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ---------------------------------------------------------------------------
# Hashing de contraseñas
# ---------------------------------------------------------------------------
def hash_password(password: str) -> str:
    """
    Genera un hash seguro (bcrypt) a partir de una contraseña en texto plano.

    Args:
        password: Contraseña en texto plano.

    Returns:
        El hash resultante, listo para almacenar en la base de datos.
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifica que una contraseña en texto plano coincida con su hash.

    Args:
        plain_password: Contraseña que envía el usuario al hacer login.
        hashed_password: Hash almacenado en la base de datos.

    Returns:
        True si coinciden, False en caso contrario.
    """
    return pwd_context.verify(plain_password, hashed_password)


# ---------------------------------------------------------------------------
# JSON Web Tokens (JWT)
# ---------------------------------------------------------------------------
def create_access_token(
    subject: str | int,
    expires_delta: Optional[timedelta] = None,
    extra_claims: Optional[dict[str, Any]] = None,
) -> str:
    """
    Crea un access token JWT firmado.

    Args:
        subject: Identificador único del usuario (lo guardamos en el claim "sub").
                 Normalmente el id o el correo del usuario.
        expires_delta: Tiempo de expiración personalizado. Si no se indica,
                       se usa ACCESS_TOKEN_EXPIRE_MINUTES del .env.
        extra_claims: Claims adicionales opcionales (rol, permisos, etc.),
                      útil para escalar el sistema en fases posteriores.

    Returns:
        El token JWT codificado como string.
    """
    expire = datetime.now(timezone.utc) + (
        expires_delta
        or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    # Claims estándar del token.
    to_encode: dict[str, Any] = {
        "sub": str(subject),   # subject: a quién pertenece el token
        "exp": expire,         # expiration: cuándo deja de ser válido
        "iat": datetime.now(timezone.utc),  # issued at: cuándo se emitió
    }

    if extra_claims:
        to_encode.update(extra_claims)

    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def verify_token(token: str) -> dict[str, Any]:
    """
    Decodifica y valida un token JWT.

    Lanza JWTError si el token es inválido o ha expirado; esa excepción se
    traduce a un 401 en la capa de dependencias (`get_current_user`).

    Args:
        token: El JWT recibido en el header Authorization.

    Returns:
        El payload (diccionario de claims) ya decodificado.

    Raises:
        JWTError: si la firma es inválida, está malformado o expiró.
    """
    payload: dict[str, Any] = jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.ALGORITHM],
    )
    return payload


# Re-exportamos JWTError para que otros módulos no tengan que importar
# directamente de `jose`, manteniendo el desacoplamiento.
__all__ = [
    "hash_password",
    "verify_password",
    "create_access_token",
    "verify_token",
    "JWTError",
    "ExpiredSignatureError",
]
