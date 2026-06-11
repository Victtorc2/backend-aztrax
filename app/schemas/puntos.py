"""
Schemas Pydantic del módulo de fidelización (puntos).
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class CanjeCreate(BaseModel):
    """Datos para canjear puntos de un cliente."""

    puntos: int = Field(..., gt=0, examples=[50])
    descripcion: Optional[str] = Field(
        default=None, max_length=255, examples=["Descuento en señuelos"]
    )


class MovimientoPuntosResponse(BaseModel):
    """Un movimiento del historial de puntos."""

    id: int
    tipo: str            # "ganado" | "canjeado"
    puntos: int          # con signo: + ganado, - canjeado
    venta_id: Optional[int]
    descripcion: Optional[str]
    fecha: datetime

    model_config = ConfigDict(from_attributes=True)


class PuntosResponse(BaseModel):
    """Saldo de puntos del cliente y su historial de movimientos."""

    cliente_id: int
    cliente_nombre: str
    puntos: int
    movimientos: list[MovimientoPuntosResponse]
