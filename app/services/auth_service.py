"""
Servicio de autenticación.

Contiene la LÓGICA DE NEGOCIO de la autenticación: autenticar credenciales,
emitir tokens y registrar usuarios. No sabe nada de FastAPI (no usa Request,
Depends ni HTTPException); lanza excepciones de dominio que la capa de API
traduce a respuestas HTTP. Así la lógica es reutilizable y testeable.
"""

from sqlalchemy.orm import Session

from app.core.exceptions import EmailAlreadyExistsError, InvalidCredentialsError
from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.models.user import Usuario
from app.repositories.user_repository import UserRepository
from app.schemas.token import Token
from app.schemas.user import UserCreate


class AuthService:
    """Orquesta los casos de uso relacionados con autenticación."""

    def __init__(self, db: Session) -> None:
        # El servicio depende del repositorio, no de la sesión directamente.
        self.repository = UserRepository(db)

    def authenticate(self, correo: str, password: str) -> Usuario:
        """
        Verifica credenciales y devuelve el usuario autenticado.

        Args:
            correo: Correo enviado por el cliente.
            password: Contraseña en texto plano.

        Returns:
            El usuario si las credenciales son válidas.

        Raises:
            InvalidCredentialsError: si el usuario no existe o la
                contraseña es incorrecta. Usamos el MISMO error en ambos
                casos para no revelar si un correo está registrado o no
                (buena práctica de seguridad).
        """
        usuario = self.repository.get_by_email(correo)
        if usuario is None:
            raise InvalidCredentialsError()

        if not verify_password(password, usuario.password_hash):
            raise InvalidCredentialsError()

        return usuario

    def login(self, correo: str, password: str) -> Token:
        """
        Caso de uso de login: autentica y emite un access token.

        Returns:
            Un schema Token con el JWT y el tipo "bearer".
        """
        usuario = self.authenticate(correo, password)

        # Guardamos el id del usuario como subject del token.
        access_token = create_access_token(subject=usuario.id)
        return Token(access_token=access_token, token_type="bearer")

    def register(self, data: UserCreate) -> Usuario:
        """
        Caso de uso de registro de usuario.

        Aunque en esta fase solo exista el administrador, el método queda
        listo para fases futuras (gestión de usuarios).

        Raises:
            EmailAlreadyExistsError: si el correo ya está registrado.
        """
        if self.repository.exists_by_email(data.correo):
            raise EmailAlreadyExistsError()

        return self.repository.create(
            nombre=data.nombre,
            correo=data.correo,
            password_hash=hash_password(data.password),
        )
