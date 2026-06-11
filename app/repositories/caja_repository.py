"""
Repositorio de caja diaria.

Acceso a datos de `cajas` y `movimientos_caja`, más el cálculo del efectivo de
ventas dentro de una sesión (ventas en efectivo, no anuladas, en el rango de la
sesión) mediante agregación SQL.
"""

from decimal import Decimal
from typing import Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.caja import Caja
from app.models.venta import Venta

_CERO = Decimal("0.00")


class CajaRepository:
    """Acceso a datos para la caja diaria."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_abierta(self) -> Optional[Caja]:
        """Devuelve la caja abierta actual, o None si no hay ninguna."""
        return self.db.scalars(
            select(Caja).where(Caja.estado == "abierta").order_by(Caja.id.desc())
        ).first()

    def get_by_id(self, caja_id: int) -> Optional[Caja]:
        return self.db.get(Caja, caja_id)

    def add(self, obj) -> None:
        self.db.add(obj)

    def commit(self) -> None:
        self.db.commit()

    def refresh(self, obj) -> None:
        self.db.refresh(obj)

    def ventas_efectivo(self, caja_id: int) -> Decimal:
        """
        Suma el total de las ventas en efectivo (no anuladas) registradas
        durante una sesión de caja.
        """
        total = self.db.scalar(
            select(func.coalesce(func.sum(Venta.total), 0)).where(
                Venta.caja_id == caja_id,
                Venta.metodo_pago == "efectivo",
                Venta.anulada.is_(False),
            )
        )
        return Decimal(total or 0).quantize(Decimal("0.01"))

    def listar(self, limite: int = 50) -> Sequence[Caja]:
        """Sesiones de caja, más recientes primero."""
        return self.db.scalars(
            select(Caja).order_by(Caja.abierta_at.desc(), Caja.id.desc()).limit(limite)
        ).all()
