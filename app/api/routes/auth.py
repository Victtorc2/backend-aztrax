"""
Rutas de autenticación: /auth/login y /auth/me.

Los endpoints son DELGADOS: solo orquestan. La lógica vive en el servicio
(`AuthService`) y la autorización en la dependencia (`get_current_user`).
Esto cumple la regla de "no poner lógica directamente en los endpoints".
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.core.exceptions import InvalidCredentialsError, TooManyRequestsError
from app.core.rate_limit import login_rate_limiter
from app.db.session import get_db
from app.dependencies.auth import CurrentUser
from app.schemas.token import Token
from app.schemas.user import UserLogin, UserResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Autenticación"])


def _client_ip(request: Request) -> str:
    """
    Obtiene la IP del cliente.

    Detrás de un proxy/balanceador se respeta el primer valor de
    X-Forwarded-For si está presente; si no, se usa la IP directa.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post(
    "/login",
    response_model=Token,
    status_code=status.HTTP_200_OK,
    summary="Iniciar sesión y obtener un token JWT",
)
def login(
    credentials: UserLogin,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> Token:
    """
    Autentica a un usuario con su correo y contraseña.

    - **correo**: correo del usuario (ej. admin@sistema.com)
    - **password**: contraseña en texto plano (ej. admin123)

    Devuelve un `access_token` JWT que se debe enviar en las rutas
    protegidas como cabecera `Authorization: Bearer <token>`.

    Protección anti fuerza bruta: tras varios intentos fallidos desde la
    misma IP/correo se responde **429** durante unos minutos.
    """
    # Clave de rate limit: IP + correo (en minúsculas) para no penalizar a
    # toda una IP por culpa de un solo correo equivocado.
    rl_key = f"{_client_ip(request)}:{credentials.correo.strip().lower()}"

    permitido, retry_after = login_rate_limiter.check(rl_key)
    if not permitido:
        raise TooManyRequestsError(
            f"Demasiados intentos fallidos. Inténtalo en {retry_after} segundos.",
            headers={"Retry-After": str(retry_after)},
        )

    service = AuthService(db)
    try:
        token = service.login(credentials.correo, credentials.password)
    except InvalidCredentialsError:
        # Registramos el fallo para el rate limiter y propagamos el 401.
        login_rate_limiter.register_failure(rl_key)
        raise

    # Login correcto: limpiamos el contador de esa clave.
    login_rate_limiter.reset(rl_key)
    return token


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Obtener los datos del usuario autenticado",
)
def read_current_user(current_user: CurrentUser) -> UserResponse:
    """
    Devuelve la información del usuario asociado al token JWT.

    Requiere un token válido. `CurrentUser` ejecuta `get_current_user`,
    que valida el token y carga el usuario; si algo falla, responde 401.
    """
    # `from_attributes=True` permite serializar el modelo ORM directamente.
    return UserResponse.model_validate(current_user)
