"""
Repositorio de usuarios.

El repositorio es la ÚNICA capa que conoce SQLAlchemy. Encapsula todas las
consultas a la tabla `usuarios`, de modo que los servicios trabajen con
métodos de alto nivel (`get_by_email`, `create`, ...) sin escribir SQL.
Esto facilita testear los servicios (se puede mockear el repositorio) y
cambiar la implementación de persistencia en el futuro.
"""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import Usuario


class UserRepository:
    """Acceso a datos para la entidad Usuario."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, user_id: int) -> Optional[Usuario]:
        """Devuelve un usuario por su id, o None si no existe."""
        return self.db.get(Usuario, user_id)

    def get_by_email(self, correo: str) -> Optional[Usuario]:
        """Devuelve un usuario por su correo, o None si no existe."""
        stmt = select(Usuario).where(Usuario.correo == correo)
        return self.db.scalar(stmt)

    def create(self, nombre: str, correo: str, password_hash: str) -> Usuario:
        """
        Crea y persiste un nuevo usuario.

        Recibe el hash ya calculado: el repositorio NO conoce la lógica
        de seguridad, solo persiste lo que se le entrega.
        """
        usuario = Usuario(
            nombre=nombre,
            correo=correo,
            password_hash=password_hash,
        )
        self.db.add(usuario)
        self.db.commit()
        self.db.refresh(usuario)  # recarga id y created_at generados por la BD
        return usuario

    def exists_by_email(self, correo: str) -> bool:
        """Indica si ya existe un usuario con ese correo."""
        stmt = select(Usuario.id).where(Usuario.correo == correo)
        return self.db.scalar(stmt) is not None
