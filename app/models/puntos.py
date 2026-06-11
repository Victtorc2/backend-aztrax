"""
Modelo ORM del historial de puntos de fidelización: `movimientos_puntos`.

Cada fila registra una variación del saldo de puntos de un cliente: puntos
ganados por una compra ("ganado") o canjeados ("canjeado"). El saldo vigente
se guarda desnormalizado en `clientes.puntos`; esta tabla es la trazabilidad.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MovimientoPuntos(Base):
    """Un movimiento (ganado/canjeado) en el saldo de puntos de un cliente."""

    __tablename__ = "movimientos_puntos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    cliente_id: Mapped[int] = mapped_column(
        ForeignKey("clientes.id"), index=True, nullable=False
    )

    # Tipo de movimiento: "ganado" (suma) o "canjeado" (resta).
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)

    # Puntos del movimiento. Se guarda con signo según el tipo: positivo cuando
    # se ganan, negativo cuando se canjean (facilita sumar el historial).
    puntos: Mapped[int] = mapped_column(Integer, nullable=False)

    # Venta que originó el movimiento (cuando aplica: puntos ganados/revertidos).
    venta_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("ventas.id"), index=True, nullable=True
    )

    descripcion: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    fecha: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True,
        nullable=False,
    )

    def __repr__(self) -> str:  # pragma: no cover - solo depuración
        return (
            f"<MovimientoPuntos id={self.id} cliente_id={self.cliente_id} "
            f"tipo={self.tipo!r} puntos={self.puntos}>"
        )
