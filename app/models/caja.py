"""
Modelos ORM de la caja diaria: `cajas` y `movimientos_caja`.

- Caja: una sesión de caja (apertura → cierre) con su arqueo. Solo puede haber
  una abierta a la vez. Al cerrar se calcula el monto esperado (inicial +
  ventas en efectivo + ingresos − egresos) y la diferencia con lo declarado.
- MovimientoCaja: ingresos/egresos manuales de efectivo durante la sesión
  (p. ej. retiro para compras, ingreso de vuelto), para que el arqueo cuadre.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Caja(Base):
    """Sesión de caja (apertura y cierre) con su arqueo."""

    __tablename__ = "cajas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Estado: "abierta" mientras opera; "cerrada" tras el arqueo.
    estado: Mapped[str] = mapped_column(
        String(20), nullable=False, default="abierta", server_default="abierta",
        index=True,
    )

    # Efectivo con el que se abre la caja (fondo de cambio).
    monto_inicial: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    # Cierre: efectivo declarado al contar la caja, lo esperado por el sistema y
    # la diferencia (declarado − esperado). Nulos mientras la caja está abierta.
    monto_declarado: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    monto_esperado: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    diferencia: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2), nullable=True
    )

    nota_apertura: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    nota_cierre: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    abierta_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True,
        nullable=False,
    )
    cerrada_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    movimientos: Mapped[list["MovimientoCaja"]] = relationship(
        back_populates="caja",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="MovimientoCaja.fecha",
    )

    def __repr__(self) -> str:  # pragma: no cover - solo depuración
        return f"<Caja id={self.id} estado={self.estado!r}>"


class MovimientoCaja(Base):
    """Ingreso o egreso manual de efectivo dentro de una sesión de caja."""

    __tablename__ = "movimientos_caja"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    caja_id: Mapped[int] = mapped_column(
        ForeignKey("cajas.id"), index=True, nullable=False
    )

    # Tipo: "ingreso" (entra efectivo) o "egreso" (sale efectivo).
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)

    monto: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    motivo: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    fecha: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True,
        nullable=False,
    )

    caja: Mapped["Caja"] = relationship(back_populates="movimientos")

    def __repr__(self) -> str:  # pragma: no cover - solo depuración
        return (
            f"<MovimientoCaja id={self.id} caja_id={self.caja_id} "
            f"tipo={self.tipo!r} monto={self.monto}>"
        )
