"""
Modelo ORM de la tabla `productos`.

Cada producto pertenece a una categoría y a un proveedor (claves foráneas).
Incluye:
- `estado`: calculado automáticamente a partir del stock (en la capa de servicio).
- `is_active`: bandera para SOFT DELETE (no se borran filas físicamente),
  pensado para conservar la integridad cuando existan ventas en fases futuras.
"""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

# Solo para anotaciones de tipo (evita imports circulares en tiempo de ejecución).
if TYPE_CHECKING:
    from app.models.categoria import Categoria
    from app.models.proveedor import Proveedor


class Producto(Base):
    """Representa un producto del inventario."""

    __tablename__ = "productos"

    # Identificador único autoincremental.
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Código único autogenerado (P0001, P0002, ...). Indexado para búsquedas.
    codigo: Mapped[str] = mapped_column(
        String(20), unique=True, index=True, nullable=False
    )

    # Nombre del producto: obligatorio e indexado.
    nombre: Mapped[str] = mapped_column(String(150), index=True, nullable=False)

    # Marca del producto: obligatoria e indexada para búsquedas/filtros.
    marca: Mapped[str] = mapped_column(String(100), index=True, nullable=False)

    # Modelo del producto: opcional (no todos los productos tienen modelo).
    # Indexado porque también se usa en búsquedas.
    modelo: Mapped[Optional[str]] = mapped_column(
        String(100), index=True, nullable=True
    )

    # Color del producto: opcional. En el dominio de señuelos, un mismo modelo
    # viene en varios colores; cada color es un producto distinto. Indexado
    # porque también se usa en búsquedas y en la navegación del catálogo.
    color: Mapped[Optional[str]] = mapped_column(
        String(100), index=True, nullable=True
    )

    # URL/ruta de la imagen del producto (relativa a /uploads/productos/).
    imagen_url: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )

    # Producto destacado: aparece resaltado en el catálogo público.
    destacado: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )

    # Representación / presentación de venta (unidad, sobre, caja, ...).
    # Lista cerrada validada en el schema. Por defecto "unidad".
    representacion: Mapped[str] = mapped_column(
        String(20), nullable=False, default="unidad", server_default="unidad"
    )

    # Descripción larga del producto (texto libre para el catálogo).
    descripcion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Ficha técnica: especificaciones, una por línea "Etiqueta: valor".
    ficha_tecnica: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # --- Claves foráneas -------------------------------------------------
    # ondelete no se define como CASCADE a propósito: la eliminación de una
    # categoría/proveedor con productos se bloquea en su propio servicio.
    categoria_id: Mapped[int] = mapped_column(
        ForeignKey("categorias.id"), index=True, nullable=False
    )
    proveedor_id: Mapped[int] = mapped_column(
        ForeignKey("proveedores.id"), index=True, nullable=False
    )

    # --- Precios y stock -------------------------------------------------
    # Numeric(12, 2): hasta 10 dígitos enteros y 2 decimales. Se usa Decimal
    # (no float) para evitar errores de redondeo en valores monetarios.
    precio_compra: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    precio_venta: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    stock: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stock_minimo: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Estado calculado: "agotado" | "bajo_stock" | "disponible".
    estado: Mapped[str] = mapped_column(String(20), nullable=False)

    # Soft delete: los productos no se eliminan físicamente.
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, index=True
    )

    # Fecha de creación en UTC, gestionada automáticamente por la BD.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # --- Relaciones ------------------------------------------------------
    # `producto.categoria` y `producto.proveedor` permiten navegar al objeto
    # relacionado. back_populates mantiene la relación inversa sincronizada.
    categoria: Mapped["Categoria"] = relationship(back_populates="productos")
    proveedor: Mapped["Proveedor"] = relationship(back_populates="productos")

    def __repr__(self) -> str:  # pragma: no cover - solo depuración
        return f"<Producto id={self.id} codigo={self.codigo!r} nombre={self.nombre!r}>"
