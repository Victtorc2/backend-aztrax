"""
Servicio de reportes de rentabilidad.

Calcula la ganancia (precio de venta − costo) a partir de las líneas de venta,
usando el costo congelado en cada línea (DetalleVenta.costo_unitario). Ofrece:

- Rentabilidad por producto (ranking por ganancia).
- Rentabilidad por periodo (día o mes).
- Resumen global del rango consultado.

Todo mediante agregaciones SQL para que rinda con volumen. El rango de fechas
es opcional; si no se indica, cubre todo el histórico.
"""

from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.producto import Producto
from app.models.venta import DetalleVenta, Venta
from app.schemas.rentabilidad import (
    RentabilidadPeriodo,
    RentabilidadProducto,
    RentabilidadResumen,
    ReporteRentabilidad,
)

_CERO = Decimal("0.00")


def _money(value) -> Decimal:
    return Decimal(value or 0).quantize(Decimal("0.01"))


def _margen(ganancia: Decimal, ingresos: Decimal) -> Decimal:
    """Margen porcentual = ganancia / ingresos * 100 (0 si no hay ingresos)."""
    if ingresos and ingresos > 0:
        return (ganancia / ingresos * Decimal("100")).quantize(Decimal("0.01"))
    return _CERO


class RentabilidadService:
    """Calcula los reportes de rentabilidad."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Helpers de rango de fechas
    # ------------------------------------------------------------------
    def _aplicar_rango(self, stmt, desde: date | None, hasta: date | None):
        """Aplica el filtro de fechas (sobre Venta.fecha) a un statement con join a Venta."""
        if desde is not None:
            stmt = stmt.where(Venta.fecha >= datetime.combine(desde, time.min))
        if hasta is not None:
            stmt = stmt.where(Venta.fecha <= datetime.combine(hasta, time.max))
        return stmt

    # ------------------------------------------------------------------
    # Por producto
    # ------------------------------------------------------------------
    def _por_producto(
        self, desde: date | None, hasta: date | None
    ) -> list[RentabilidadProducto]:
        stmt = (
            select(
                Producto.id,
                Producto.codigo,
                Producto.nombre,
                Producto.marca,
                func.sum(DetalleVenta.cantidad).label("unidades"),
                func.sum(DetalleVenta.subtotal).label("ingresos"),
                func.sum(DetalleVenta.costo_unitario * DetalleVenta.cantidad).label(
                    "costo"
                ),
            )
            .join(DetalleVenta, DetalleVenta.producto_id == Producto.id)
            .join(Venta, Venta.id == DetalleVenta.venta_id)
            .group_by(Producto.id, Producto.codigo, Producto.nombre, Producto.marca)
        )
        stmt = self._aplicar_rango(stmt, desde, hasta)

        filas = self.db.execute(stmt).all()
        resultado: list[RentabilidadProducto] = []
        for row in filas:
            ingresos = _money(row.ingresos)
            costo = _money(row.costo)
            ganancia = (ingresos - costo).quantize(Decimal("0.01"))
            resultado.append(
                RentabilidadProducto(
                    producto_id=row.id,
                    codigo=row.codigo,
                    nombre=row.nombre,
                    marca=row.marca,
                    unidades_vendidas=int(row.unidades or 0),
                    ingresos=ingresos,
                    costo=costo,
                    ganancia=ganancia,
                    margen_pct=_margen(ganancia, ingresos),
                )
            )

        # Fila agregada con las ventas libres (líneas sin producto registrado).
        # El JOIN de arriba las excluye; aquí las sumamos aparte para que su
        # ganancia real (ingreso - costo informado) entre en el reporte.
        libre = self._ventas_libres(desde, hasta)
        if libre is not None:
            resultado.append(libre)

        # Mayor ganancia primero.
        resultado.sort(key=lambda r: r.ganancia, reverse=True)
        return resultado

    def _ventas_libres(
        self, desde: date | None, hasta: date | None
    ) -> RentabilidadProducto | None:
        """
        Agrega todas las líneas libres (producto_id NULL) en una sola fila
        "Ventas libres". Devuelve None si no hubo ninguna en el rango.
        """
        stmt = (
            select(
                func.sum(DetalleVenta.cantidad).label("unidades"),
                func.sum(DetalleVenta.subtotal).label("ingresos"),
                func.sum(DetalleVenta.costo_unitario * DetalleVenta.cantidad).label(
                    "costo"
                ),
            )
            .join(Venta, Venta.id == DetalleVenta.venta_id)
            .where(DetalleVenta.producto_id.is_(None))
        )
        stmt = self._aplicar_rango(stmt, desde, hasta)
        row = self.db.execute(stmt).one()

        unidades = int(row.unidades or 0)
        if unidades == 0:
            return None

        ingresos = _money(row.ingresos)
        costo = _money(row.costo)
        ganancia = (ingresos - costo).quantize(Decimal("0.01"))
        return RentabilidadProducto(
            producto_id=None,
            codigo="—",
            nombre="Ventas libres",
            marca="",
            unidades_vendidas=unidades,
            ingresos=ingresos,
            costo=costo,
            ganancia=ganancia,
            margen_pct=_margen(ganancia, ingresos),
        )

    # ------------------------------------------------------------------
    # Por periodo (día o mes)
    # ------------------------------------------------------------------
    def _por_periodo(
        self, desde: date | None, hasta: date | None, agrupar: str
    ) -> list[RentabilidadPeriodo]:
        """
        Agrupa por día o por mes. El agrupado se hace en Python para ser
        portable entre SQLite (pruebas) y MySQL (producción), sobre las líneas
        del rango (acotado por las fechas).
        """
        stmt = (
            select(
                Venta.id,
                Venta.fecha,
                func.sum(DetalleVenta.subtotal).label("ingresos"),
                func.sum(DetalleVenta.costo_unitario * DetalleVenta.cantidad).label(
                    "costo"
                ),
            )
            .join(DetalleVenta, DetalleVenta.venta_id == Venta.id)
            .group_by(Venta.id, Venta.fecha)
        )
        stmt = self._aplicar_rango(stmt, desde, hasta)
        filas = self.db.execute(stmt).all()

        # Acumular por clave de periodo.
        acum: dict[str, dict] = {}
        for row in filas:
            fecha_dt = row.fecha
            if agrupar == "mes":
                clave = fecha_dt.strftime("%Y-%m")
            else:
                clave = fecha_dt.strftime("%Y-%m-%d")
            slot = acum.setdefault(
                clave, {"ingresos": _CERO, "costo": _CERO, "ventas": 0}
            )
            slot["ingresos"] += Decimal(row.ingresos or 0)
            slot["costo"] += Decimal(row.costo or 0)
            slot["ventas"] += 1

        periodos: list[RentabilidadPeriodo] = []
        for clave in sorted(acum.keys()):
            slot = acum[clave]
            ingresos = _money(slot["ingresos"])
            costo = _money(slot["costo"])
            ganancia = (ingresos - costo).quantize(Decimal("0.01"))
            periodos.append(
                RentabilidadPeriodo(
                    periodo=clave,
                    ingresos=ingresos,
                    costo=costo,
                    ganancia=ganancia,
                    margen_pct=_margen(ganancia, ingresos),
                    ventas=slot["ventas"],
                )
            )
        return periodos

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------
    def reporte(
        self,
        desde: date | None = None,
        hasta: date | None = None,
        agrupar: str = "dia",
    ) -> ReporteRentabilidad:
        """
        Genera el reporte completo de rentabilidad para el rango indicado.

        Args:
            desde, hasta: rango de fechas (inclusive). None = sin límite.
            agrupar: "dia" o "mes" para la serie por periodo.
        """
        por_producto = self._por_producto(desde, hasta)
        agrupar = "mes" if agrupar == "mes" else "dia"
        por_periodo = self._por_periodo(desde, hasta, agrupar)

        # Resumen global: sumamos lo de por_producto (misma base de cálculo).
        ingresos = sum((p.ingresos for p in por_producto), _CERO)
        costo = sum((p.costo for p in por_producto), _CERO)
        unidades = sum((p.unidades_vendidas for p in por_producto), 0)
        ganancia = (ingresos - costo).quantize(Decimal("0.01"))

        resumen = RentabilidadResumen(
            ingresos=_money(ingresos),
            costo=_money(costo),
            ganancia=ganancia,
            margen_pct=_margen(ganancia, ingresos),
            unidades_vendidas=unidades,
        )

        return ReporteRentabilidad(
            desde=desde,
            hasta=hasta,
            resumen=resumen,
            por_producto=por_producto,
            por_periodo=por_periodo,
        )
