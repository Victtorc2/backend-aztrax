"""
Modelo ORM de la tabla `proveedores`.

Los proveedores serán referenciados por el módulo de productos en una fase
posterior (para saber quién suministra cada producto y gestionar la
reposición). El diseño deja preparada esa relación.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.producto import Producto


class Proveedor(Base):
    """Representa a un proveedor que suministra productos al inventario."""

    __tablename__ = "proveedores"

    # Identificador único autoincremental.
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Nombre del proveedor: obligatorio e indexado para búsquedas.
    nombre: Mapped[str] = mapped_column(String(150), index=True, nullable=False)

    # Teléfono de contacto (opcional).
    telefono: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)

    # Dirección (opcional).
    direccion: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # RUC (opcional). Indexado y único: si se proporciona, no puede repetirse.
    # `unique=True` permite múltiples NULL en PostgreSQL (varios proveedores
    # sin RUC), pero impide RUC duplicados a nivel de base de datos.
    ruc: Mapped[Optional[str]] = mapped_column(
        String(20), index=True, unique=True, nullable=True
    )

    # Observaciones libres (opcional). `Text` admite contenido largo.
    observaciones: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Fecha de creación en UTC, gestionada automáticamente por la BD.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # --- Relación con productos (Fase 5) ----------------------------------
    # Relación inversa: un proveedor suministra muchos productos. La
    # eliminación se bloquea si existen productos asociados
    # (ver ProveedorService.delete / has_associated_products).
    productos: Mapped[list["Producto"]] = relationship(
        back_populates="proveedor"
    )

    def __repr__(self) -> str:  # pragma: no cover - solo depuración
        return f"<Proveedor id={self.id} nombre={self.nombre!r}>"
