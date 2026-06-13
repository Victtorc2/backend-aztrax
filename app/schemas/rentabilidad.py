"""
Schemas Pydantic para los reportes de rentabilidad.

Dos vistas:
- Por producto: cuánto se ganó en cada artículo (ingresos, costo, ganancia,
  margen %).
- Por periodo: ganancia total agrupada por día o por mes.

La ganancia usa el costo CONGELADO en cada venta (DetalleVenta.costo_unitario),
de modo que el reporte es histórico-fiel aunque el costo del producto cambie.
"""

from datetime import date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class RentabilidadProducto(BaseModel):
    """Rentabilidad acumulada de un producto en el periodo consultado."""

    # None en la fila agregada de "Ventas libres" (líneas sin producto registrado).
    producto_id: Optional[int]
    codigo: str
    nombre: str
    marca: str
    modelo: Optional[str] = None
    color: Optional[str] = None
    unidades_vendidas: int
    ingresos: Decimal          # suma de subtotales vendidos
    costo: Decimal             # suma de (costo_unitario * cantidad)
    ganancia: Decimal          # ingresos - costo
    margen_pct: Decimal        # ganancia / ingresos * 100


class RentabilidadPeriodo(BaseModel):
    """Ganancia agregada de un periodo (un día o un mes)."""

    periodo: str               # "2026-05-28" (día) o "2026-05" (mes)
    ingresos: Decimal
    costo: Decimal
    ganancia: Decimal
    margen_pct: Decimal
    ventas: int                # nº de ventas en el periodo


class RentabilidadResumen(BaseModel):
    """Totales globales del periodo consultado."""

    ingresos: Decimal
    costo: Decimal
    ganancia: Decimal
    margen_pct: Decimal
    unidades_vendidas: int


class ReporteRentabilidad(BaseModel):
    """Respuesta completa del reporte de rentabilidad."""

    desde: date | None
    hasta: date | None
    resumen: RentabilidadResumen
    por_producto: list[RentabilidadProducto]
    por_periodo: list[RentabilidadPeriodo]
