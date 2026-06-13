"""
Schemas Pydantic del módulo de dashboard (métricas e indicadores).

Todos los importes monetarios usan Decimal para mantener la precisión que
arrastra el resto del sistema. Las respuestas están pensadas para alimentar
tarjetas de KPIs y gráficos en el frontend.
"""

from datetime import date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class ResumenDashboard(BaseModel):
    """Indicadores rápidos (tarjetas KPI)."""

    # Ventas
    ventas_hoy: int
    monto_hoy: Decimal
    ventas_total: int
    monto_total: Decimal
    ticket_promedio: Decimal  # monto_total / ventas_total

    # Inventario
    productos_activos: int
    productos_agotados: int
    productos_bajo_stock: int
    valor_inventario: Decimal  # suma de precio_venta * stock (productos activos)

    # Catálogo
    total_categorias: int
    total_proveedores: int


class VentaPorDia(BaseModel):
    """Punto de la serie temporal de ventas (para gráfico de líneas/barras)."""

    fecha: date
    cantidad: int      # nº de ventas ese día
    monto: Decimal     # total vendido ese día


class TopProducto(BaseModel):
    """Producto más vendido (ranking por unidades)."""

    producto_id: int
    codigo: str
    nombre: str
    marca: str
    modelo: Optional[str] = None
    color: Optional[str] = None
    unidades_vendidas: int
    monto_vendido: Decimal


class MetodoPagoResumen(BaseModel):
    """Desglose de ventas por método de pago."""

    metodo_pago: str   # "efectivo" | "yape"
    cantidad: int
    monto: Decimal


class DashboardCompleto(BaseModel):
    """Respuesta agregada con todo lo necesario para pintar el dashboard."""

    resumen: ResumenDashboard
    ventas_por_dia: list[VentaPorDia]
    top_productos: list[TopProducto]
    metodos_pago: list[MetodoPagoResumen]
