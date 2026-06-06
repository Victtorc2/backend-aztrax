"""
Modelo ORM de la tabla `categorias`.

Las categorías serán referenciadas por el módulo de productos en una fase
posterior. El diseño deja preparada esa relación (ver comentario al final).
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.producto import Producto


class Categoria(Base):
    """Representa una categoría de productos del inventario."""

    __tablename__ = "categorias"

    # Identificador único autoincremental.
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Nombre de la categoría: obligatorio, único e indexado para búsquedas.
    # La unicidad a nivel de BD es un seguro adicional frente a la validación
    # del servicio (que además ignora mayúsculas/minúsculas y espacios).
    nombre: Mapped[str] = mapped_column(
        String(120), unique=True, index=True, nullable=False
    )

    # Fecha de creación en UTC, gestionada automáticamente por la BD.
    # `func.now()` con timezone=True almacena el instante con zona horaria.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # --- Relación con productos (Fase 5) ----------------------------------
    # Relación inversa: una categoría tiene muchos productos. No se usa
    # cascade de borrado: la eliminación se bloquea si existen productos
    # (ver CategoriaService.delete / has_associated_products).
    productos: Mapped[list["Producto"]] = relationship(
        back_populates="categoria"
    )

    def __repr__(self) -> str:  # pragma: no cover - solo depuración
        return f"<Categoria id={self.id} nombre={self.nombre!r}>"
