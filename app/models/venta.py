"""
Modelos ORM de ventas: `ventas` y `detalle_venta`.

Estructura según el esquema acordado:
- venta: cabecera con numeración de boleta, totales y descuento.
- detalle_venta: líneas de la venta (un registro por producto vendido).

Se definen las relaciones para poder cargar todo con joinedload/selectinload
y evitar el problema N+1 al generar la boleta o el historial.
"""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.producto import Producto
    from app.models.cliente import Cliente


class Venta(Base):
    """Cabecera de una venta / comprobante (boleta)."""

    __tablename__ = "ventas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Número de boleta con formato SERIE-correlativo (ej. B001-000001).
    # Único e indexado para búsquedas y reimpresión.
    numero_boleta: Mapped[str] = mapped_column(
        String(20), unique=True, index=True, nullable=False
    )

    # Importes monetarios con Decimal (evita errores de redondeo).
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    descuento: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    # Tipo de descuento: "monto" (S/ fijo) o "porcentaje" (%). Opcional.
    descuento_tipo: Mapped[str | None] = mapped_column(String(20), nullable=True)
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    # Método de pago: "efectivo" o "yape". Obligatorio (con default "efectivo"
    # para no romper ventas históricas creadas antes de esta columna).
    metodo_pago: Mapped[str] = mapped_column(
        String(20), nullable=False, default="efectivo", server_default="efectivo"
    )

    # --- Crédito / fiado --------------------------------------------------
    # Tipo de pago: "contado" (pagada al instante) o "credito" (fiado).
    tipo_pago: Mapped[str] = mapped_column(
        String(20), nullable=False, default="contado", server_default="contado"
    )
    # Cliente asociado. Obligatorio en ventas al crédito; opcional al contado.
    cliente_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("clientes.id"), index=True, nullable=True
    )
    # Saldo pendiente de pago. En ventas al contado es 0; en crédito arranca
    # igual al total y baja con cada abono hasta llegar a 0 (deuda saldada).
    saldo_pendiente: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00"), server_default="0.00"
    )

    # Fecha y hora de la venta (UTC), gestionada por la BD.
    fecha: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True,
        nullable=False,
    )

    # Relación con las líneas de detalle. `cascade` propaga el alta/baja del
    # detalle junto con la venta; selectin evita N+1 al cargar varias ventas.
    detalles: Mapped[list["DetalleVenta"]] = relationship(
        back_populates="venta",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # Cliente (cargado en la misma consulta cuando exista).
    cliente: Mapped[Optional["Cliente"]] = relationship(lazy="joined")

    # Abonos (pagos parciales) de una venta al crédito.
    abonos: Mapped[list["Abono"]] = relationship(
        back_populates="venta",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="Abono.fecha",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Venta id={self.id} boleta={self.numero_boleta!r} total={self.total}>"


class DetalleVenta(Base):
    """Línea de detalle de una venta (un producto vendido)."""

    __tablename__ = "detalle_venta"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    venta_id: Mapped[int] = mapped_column(
        ForeignKey("ventas.id"), index=True, nullable=False
    )
    # producto_id es OPCIONAL: en una "línea libre" (producto no registrado en
    # el inventario, escrito a mano) queda en None y se usa descripcion_libre.
    producto_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("productos.id"), index=True, nullable=True
    )
    # Texto escrito a mano cuando la línea es libre (sin producto registrado).
    descripcion_libre: Mapped[Optional[str]] = mapped_column(
        String(150), nullable=True
    )

    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    # Precio unitario al momento de la venta (se "congela" aquí para que el
    # historial sea fiel aunque el precio del producto cambie luego).
    precio: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    # Costo unitario al momento de la venta (precio_compra congelado). Permite
    # calcular la ganancia real aunque el costo del producto cambie después.
    costo_unitario: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00"), server_default="0.00"
    )
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    # Relaciones.
    venta: Mapped["Venta"] = relationship(back_populates="detalles")
    # joined: al cargar un detalle casi siempre queremos el producto (nombre,
    # marca, código) para la boleta; se trae en la misma consulta.
    producto: Mapped["Producto"] = relationship(lazy="joined")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<DetalleVenta id={self.id} venta_id={self.venta_id} prod={self.producto_id}>"


class Abono(Base):
    """Pago parcial (abono) sobre una venta al crédito."""

    __tablename__ = "abonos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    venta_id: Mapped[int] = mapped_column(
        ForeignKey("ventas.id"), index=True, nullable=False
    )

    # Monto abonado en este pago.
    monto: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    # Forma del abono (efectivo/yape), por si se quiere rastrear.
    metodo_pago: Mapped[str] = mapped_column(
        String(20), nullable=False, default="efectivo", server_default="efectivo"
    )
    nota: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    fecha: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True,
        nullable=False,
    )

    venta: Mapped["Venta"] = relationship(back_populates="abonos")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Abono id={self.id} venta_id={self.venta_id} monto={self.monto}>"
