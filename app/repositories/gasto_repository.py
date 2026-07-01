"""
Repositorio de gastos y del cálculo del saldo de dinero por método de pago.

Además del CRUD de `gastos`, agrega:
- Los ingresos por método (ventas al contado no anuladas + abonos de ventas no
  anuladas) mediante agregación SQL.
- Los egresos (gastos) por método.
- Los gastos en efectivo de una sesión de caja (para el arqueo).
"""

from datetime import date, datetime, time
from decimal import Decimal
from typing import Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.gasto import Gasto
from app.models.venta import Abono, Venta

_CERO = Decimal("0.00")


class GastoRepository:
    """Acceso a datos para gastos y saldo de dinero."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Escritura
    # ------------------------------------------------------------------
    def add(self, obj: Gasto) -> None:
        self.db.add(obj)

    def commit(self) -> None:
        self.db.commit()

    def refresh(self, obj: Gasto) -> None:
        self.db.refresh(obj)

    def get_by_id(self, gasto_id: int) -> Optional[Gasto]:
        return self.db.get(Gasto, gasto_id)

    def delete(self, gasto: Gasto) -> None:
        self.db.delete(gasto)
        self.db.commit()

    # ------------------------------------------------------------------
    # Lectura / listado
    # ------------------------------------------------------------------
    def listar(
        self,
        categoria: Optional[str] = None,
        metodo_pago: Optional[str] = None,
        proveedor_id: Optional[int] = None,
        fecha_inicio: Optional[date] = None,
        fecha_fin: Optional[date] = None,
        limite: int = 100,
    ) -> Sequence[Gasto]:
        """Gastos que cumplen los filtros, más recientes primero."""
        stmt = select(Gasto)
        if categoria:
            stmt = stmt.where(Gasto.categoria == categoria)
        if metodo_pago:
            stmt = stmt.where(Gasto.metodo_pago == metodo_pago)
        if proveedor_id is not None:
            stmt = stmt.where(Gasto.proveedor_id == proveedor_id)
        if fecha_inicio is not None:
            stmt = stmt.where(Gasto.fecha >= datetime.combine(fecha_inicio, time.min))
        if fecha_fin is not None:
            stmt = stmt.where(Gasto.fecha <= datetime.combine(fecha_fin, time.max))
        stmt = stmt.order_by(Gasto.fecha.desc(), Gasto.id.desc()).limit(limite)
        return self.db.scalars(stmt).unique().all()

    # ------------------------------------------------------------------
    # Agregados para el saldo
    # ------------------------------------------------------------------
    def gastos_por_metodo(self) -> dict[str, Decimal]:
        """Total de gastos agrupado por método de pago."""
        filas = self.db.execute(
            select(Gasto.metodo_pago, func.coalesce(func.sum(Gasto.monto), 0))
            .group_by(Gasto.metodo_pago)
        ).all()
        return {
            metodo: Decimal(total or 0).quantize(Decimal("0.01"))
            for metodo, total in filas
        }

    def ventas_contado_por_metodo(self) -> dict[str, Decimal]:
        """
        Total de ventas al contado NO anuladas, agrupado por método de pago.

        (Las ventas al crédito no ingresan dinero al venderse; su cobro se
        registra vía abonos.)
        """
        filas = self.db.execute(
            select(Venta.metodo_pago, func.coalesce(func.sum(Venta.total), 0))
            .where(Venta.tipo_pago == "contado", Venta.anulada.is_(False))
            .group_by(Venta.metodo_pago)
        ).all()
        return {
            metodo: Decimal(total or 0).quantize(Decimal("0.01"))
            for metodo, total in filas
        }

    def abonos_por_metodo(self) -> dict[str, Decimal]:
        """
        Total de abonos (cobros de ventas al crédito) sobre ventas NO anuladas,
        agrupado por método de pago.
        """
        filas = self.db.execute(
            select(Abono.metodo_pago, func.coalesce(func.sum(Abono.monto), 0))
            .join(Venta, Abono.venta_id == Venta.id)
            .where(Venta.anulada.is_(False))
            .group_by(Abono.metodo_pago)
        ).all()
        return {
            metodo: Decimal(total or 0).quantize(Decimal("0.01"))
            for metodo, total in filas
        }

    def gastos_efectivo(self, caja_id: int) -> Decimal:
        """Suma de los gastos en efectivo vinculados a una sesión de caja."""
        total = self.db.scalar(
            select(func.coalesce(func.sum(Gasto.monto), 0)).where(
                Gasto.caja_id == caja_id,
                Gasto.metodo_pago == "efectivo",
            )
        )
        return Decimal(total or 0).quantize(Decimal("0.01"))
