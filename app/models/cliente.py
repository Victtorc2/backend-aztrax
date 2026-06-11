"""
Modelo ORM de clientes.

Lista de clientes del negocio. Un cliente puede tener ventas al crédito
asociadas (fiado); la relación se define desde el lado de Venta.
"""

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Cliente(Base):
    """Cliente del negocio (para ventas al crédito / fiado y registro)."""

    __tablename__ = "clientes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Nombre completo o razón social. Obligatorio e indexado para búsquedas.
    nombre: Mapped[str] = mapped_column(String(150), index=True, nullable=False)

    # Documento de identidad (DNI/RUC). Opcional pero único si se informa.
    documento: Mapped[Optional[str]] = mapped_column(
        String(20), unique=True, index=True, nullable=True
    )

    # Datos de contacto, todos opcionales.
    telefono: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    direccion: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    nota: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Fecha de nacimiento (opcional). Permite saludar y dar promos de cumpleaños.
    fecha_nacimiento: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Saldo de puntos de fidelización. Se acumula con cada compra y se reduce al
    # canjearlos. El historial de movimientos vive en `movimientos_puntos`.
    puntos: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )

    # Baja lógica: nunca se borra un cliente con historial; se desactiva.
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Cliente id={self.id} nombre={self.nombre!r}>"
