"""
Schemas Pydantic del módulo de gastos / egresos y del saldo de dinero.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class MetodoPagoGasto(str, Enum):
    """Método de pago con el que salió el dinero del gasto."""

    EFECTIVO = "efectivo"
    YAPE = "yape"


class CategoriaGasto(str, Enum):
    """Categoría del gasto."""

    PEDIDO = "pedido"        # compra / reposición a proveedor
    SERVICIO = "servicio"    # luz, agua, internet, etc.
    SUELDO = "sueldo"
    ALQUILER = "alquiler"
    OTRO = "otro"


class GastoCreate(BaseModel):
    """Datos para registrar un gasto (salida de dinero)."""

    categoria: CategoriaGasto = Field(default=CategoriaGasto.OTRO)
    monto: Decimal = Field(
        ..., gt=0, max_digits=12, decimal_places=2, examples=[120.50]
    )
    metodo_pago: MetodoPagoGasto = Field(default=MetodoPagoGasto.EFECTIVO)
    proveedor_id: Optional[int] = Field(
        default=None, description="Proveedor asociado (opcional, típico en un pedido)"
    )
    descripcion: Optional[str] = Field(default=None, max_length=255)


class GastoResponse(BaseModel):
    """Un gasto registrado."""

    id: int
    categoria: str
    monto: Decimal
    metodo_pago: str
    proveedor_id: Optional[int]
    proveedor_nombre: Optional[str] = None
    descripcion: Optional[str]
    caja_id: Optional[int]
    fecha: datetime

    model_config = ConfigDict(from_attributes=True)


class SaldoMetodo(BaseModel):
    """Desglose del saldo disponible de un método de pago."""

    ingresos: Decimal   # ventas al contado + abonos con este método
    egresos: Decimal    # gastos con este método
    saldo: Decimal      # ingresos − egresos


class SaldoResponse(BaseModel):
    """
    Dinero disponible por método de pago.

    Saldo de cada método = (ventas al contado no anuladas + abonos de ventas no
    anuladas con ese método) − (gastos con ese método) + (ajustes manuales). El
    fondo de cambio de la caja (monto inicial) NO se incluye: esto refleja el
    dinero neto generado y gastado por el negocio.
    """

    efectivo: SaldoMetodo
    yape: SaldoMetodo
    total: Decimal      # efectivo.saldo + yape.saldo


# ---------------------------------------------------------------------------
# Ajustes manuales del saldo
# ---------------------------------------------------------------------------
class ModoAjusteSaldo(str, Enum):
    """Cómo aplicar el ajuste al saldo del método."""

    AGREGAR = "agregar"        # suma `monto` al saldo actual
    ESTABLECER = "establecer"  # fija el saldo a `monto` (calcula la diferencia)


class AjusteSaldoCreate(BaseModel):
    """Datos para agregar o modificar el saldo de un método (con motivo)."""

    metodo_pago: MetodoPagoGasto
    modo: ModoAjusteSaldo = Field(default=ModoAjusteSaldo.AGREGAR)
    # En modo "agregar": monto a sumar (> 0). En modo "establecer": el nuevo
    # saldo deseado (>= 0).
    monto: Decimal = Field(
        ..., ge=0, max_digits=12, decimal_places=2, examples=[50.00]
    )
    # Especificación obligatoria del ajuste.
    motivo: str = Field(..., min_length=1, max_length=255, examples=["Aporte de capital"])


class AjusteSaldoResponse(BaseModel):
    """Un ajuste manual de saldo registrado."""

    id: int
    metodo_pago: str
    monto: Decimal      # con signo (positivo sube el saldo, negativo lo baja)
    motivo: str
    fecha: datetime

    model_config = ConfigDict(from_attributes=True)
