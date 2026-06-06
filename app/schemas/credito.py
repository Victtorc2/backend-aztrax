"""
Schemas Pydantic para crédito (fiado): abonos y estado de cuenta.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class MetodoPagoAbono(str, Enum):
    EFECTIVO = "efectivo"
    YAPE = "yape"


class AbonoCreate(BaseModel):
    """Datos para registrar un abono (pago parcial) sobre una venta a crédito."""

    monto: Decimal = Field(..., gt=0, max_digits=12, decimal_places=2, examples=[30])
    metodo_pago: MetodoPagoAbono = Field(default=MetodoPagoAbono.EFECTIVO)
    nota: Optional[str] = Field(default=None, max_length=255)


class AbonoResponse(BaseModel):
    """Un abono registrado."""

    id: int
    venta_id: int
    monto: Decimal
    metodo_pago: str
    nota: Optional[str]
    fecha: datetime

    model_config = ConfigDict(from_attributes=True)


class VentaCreditoResponse(BaseModel):
    """Resumen de una venta al crédito dentro del estado de cuenta."""

    id: int
    numero_boleta: str
    fecha: datetime
    total: Decimal
    pagado: Decimal           # total - saldo_pendiente
    saldo_pendiente: Decimal
    abonos: list[AbonoResponse]


class EstadoCuentaResponse(BaseModel):
    """Estado de cuenta de un cliente: sus ventas al crédito y el total adeudado."""

    cliente_id: int
    cliente_nombre: str
    deuda_total: Decimal
    ventas: list[VentaCreditoResponse]
