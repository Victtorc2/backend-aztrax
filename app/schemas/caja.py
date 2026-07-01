"""
Schemas Pydantic del módulo de caja diaria (apertura, cierre, arqueo).
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class TipoMovimientoCaja(str, Enum):
    """Tipo de movimiento manual de efectivo en la caja."""

    INGRESO = "ingreso"
    EGRESO = "egreso"


class CajaAbrir(BaseModel):
    """Datos para abrir una caja (fondo de cambio inicial)."""

    monto_inicial: Decimal = Field(
        ..., ge=0, max_digits=12, decimal_places=2, examples=[100.00]
    )
    nota: Optional[str] = Field(default=None, max_length=255)


class CajaCerrar(BaseModel):
    """Datos para cerrar la caja (efectivo contado al hacer el arqueo)."""

    monto_declarado: Decimal = Field(
        ..., ge=0, max_digits=12, decimal_places=2, examples=[450.00]
    )
    nota: Optional[str] = Field(default=None, max_length=255)


class MovimientoCajaCreate(BaseModel):
    """Registrar un ingreso o egreso manual de efectivo en la caja abierta."""

    tipo: TipoMovimientoCaja
    monto: Decimal = Field(..., gt=0, max_digits=12, decimal_places=2, examples=[50.00])
    motivo: Optional[str] = Field(default=None, max_length=255)


class MovimientoCajaResponse(BaseModel):
    """Un movimiento manual de efectivo dentro de la caja."""

    id: int
    tipo: str
    monto: Decimal
    motivo: Optional[str]
    fecha: datetime

    model_config = ConfigDict(from_attributes=True)


class CajaResponse(BaseModel):
    """
    Estado de una sesión de caja con su arqueo en vivo.

    Mientras la caja está abierta, `monto_esperado` se calcula al vuelo
    (inicial + ventas en efectivo + ingresos − egresos) y `diferencia` es None
    hasta el cierre. Al cerrar, los tres importes quedan congelados.
    """

    id: int
    estado: str
    monto_inicial: Decimal
    ventas_efectivo: Decimal      # efectivo de ventas (no anuladas) en la sesión
    total_ingresos: Decimal       # ingresos manuales
    total_egresos: Decimal        # egresos manuales
    gastos_efectivo: Decimal = Decimal("0.00")  # gastos en efectivo de la sesión
    monto_esperado: Decimal       # lo que debería haber en caja
    monto_declarado: Optional[Decimal]
    diferencia: Optional[Decimal]
    nota_apertura: Optional[str]
    nota_cierre: Optional[str]
    abierta_at: datetime
    cerrada_at: Optional[datetime]
    movimientos: list[MovimientoCajaResponse]


class CajaHistorialItem(BaseModel):
    """Resumen de una sesión de caja para el listado histórico."""

    id: int
    estado: str
    monto_inicial: Decimal
    monto_esperado: Optional[Decimal]
    monto_declarado: Optional[Decimal]
    diferencia: Optional[Decimal]
    abierta_at: datetime
    cerrada_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)
