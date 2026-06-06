"""
Modelo ORM de la tabla `usuarios`.
"""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Usuario(Base):
    """
    Representa a un usuario del sistema.

    En esta fase solo existirá el administrador, pero la tabla está
    diseñada para soportar múltiples usuarios (y, más adelante, roles).
    """

    __tablename__ = "usuarios"

    # Identificador único autoincremental.
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Nombre visible del usuario.
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)

    # Correo electrónico: único e indexado para búsquedas rápidas en login.
    correo: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )

    # Hash bcrypt de la contraseña. NUNCA se guarda la contraseña en texto plano.
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    # Fecha de creación gestionada por el servidor de base de datos.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:  # pragma: no cover - solo para depuración
        return f"<Usuario id={self.id} correo={self.correo!r}>"
