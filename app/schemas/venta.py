"""
Schemas Pydantic del módulo de ventas e historial.

Incluye:
- Entrada para registrar una venta (VentaCreate / VentaItemCreate).
- Salida del historial (HistorialResponse) y del detalle
  (DetalleHistorialResponse) requeridos por la Fase 11.
- BoletaResponse: metadatos de la boleta generada.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, Optional

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from app.models.venta import DetalleVenta, Venta


class DescuentoTipo(str, Enum):
    """Tipo de descuento aplicable a una venta."""

    MONTO = "monto"            # descuento fijo en soles
    PORCENTAJE = "porcentaje"  # descuento como % del subtotal


class MetodoPago(str, Enum):
    """Forma de pago de la venta."""

    EFECTIVO = "efectivo"
    YAPE = "yape"


class TipoPago(str, Enum):
    """Tipo de pago: al contado o al crédito (fiado)."""

    CONTADO = "contado"
    CREDITO = "credito"


# ---------------------------------------------------------------------------
# Entrada: registrar venta
# ---------------------------------------------------------------------------
class VentaItemCreate(BaseModel):
    """Una línea solicitada en la venta."""

    producto_id: int = Field(..., gt=0)
    cantidad: int = Field(..., gt=0, examples=[2])


class VentaCreate(BaseModel):
    """
    Datos para registrar una venta.

    El precio de cada producto NO se recibe del cliente: se toma del producto
    (precio_venta) en el servidor para evitar manipulación.

    Para una venta al crédito (fiado): `tipo_pago="credito"` y `cliente_id`
    con el cliente que queda debiendo. El saldo inicial será el total.
    """

    items: list[VentaItemCreate] = Field(..., min_length=1)
    descuento: Decimal = Field(default=Decimal("0"), ge=0, max_digits=12, decimal_places=2)
    descuento_tipo: Optional[DescuentoTipo] = Field(default=None)
    # Forma de pago: efectivo (por defecto) o yape.
    metodo_pago: MetodoPago = Field(default=MetodoPago.EFECTIVO, examples=["efectivo"])
    # Tipo de pago: contado (por defecto) o crédito.
    tipo_pago: TipoPago = Field(default=TipoPago.CONTADO, examples=["contado"])
    # Cliente: obligatorio si tipo_pago == credito.
    cliente_id: Optional[int] = Field(default=None, gt=0)
    # Datos rápidos del cliente para ventas al contado (opcional). Si se envían
    # y no hay cliente_id, el sistema busca por documento o crea el cliente.
    cliente_nombre: Optional[str] = Field(default=None, max_length=150)
    cliente_documento: Optional[str] = Field(default=None, max_length=20)


# ---------------------------------------------------------------------------
# Salida: detalle de líneas
# ---------------------------------------------------------------------------
class DetalleHistorialResponse(BaseModel):
    """Una línea de detalle dentro del historial / detalle de venta."""

    id: int
    producto_id: int
    producto: str          # nombre del producto
    marca: str
    codigo: str
    cantidad: int
    precio: Decimal        # precio unitario
    subtotal: Decimal

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_detalle(cls, d: "DetalleVenta") -> "DetalleHistorialResponse":
        """Construye la línea a partir del ORM (usa el producto ya cargado)."""
        return cls(
            id=d.id,
            producto_id=d.producto_id,
            producto=d.producto.nombre,
            marca=d.producto.marca,
            codigo=d.producto.codigo,
            cantidad=d.cantidad,
            precio=d.precio,
            subtotal=d.subtotal,
        )


# ---------------------------------------------------------------------------
# Salida: listado de historial
# ---------------------------------------------------------------------------
class HistorialResponse(BaseModel):
    """Resumen de una venta para el listado del historial."""

    id: int
    numero_boleta: str
    fecha: datetime
    subtotal: Decimal
    descuento: Decimal
    total: Decimal
    metodo_pago: str
    tipo_pago: str
    saldo_pendiente: Decimal
    cliente_id: Optional[int]
    cliente_nombre: Optional[str]
    cantidad_productos: int  # nº de líneas distintas en la venta

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_venta(cls, v: "Venta") -> "HistorialResponse":
        return cls(
            id=v.id,
            numero_boleta=v.numero_boleta,
            fecha=v.fecha,
            subtotal=v.subtotal,
            descuento=v.descuento,
            total=v.total,
            metodo_pago=v.metodo_pago,
            tipo_pago=v.tipo_pago,
            saldo_pendiente=v.saldo_pendiente,
            cliente_id=v.cliente_id,
            cliente_nombre=v.cliente.nombre if v.cliente else None,
            cantidad_productos=len(v.detalles),
        )


# ---------------------------------------------------------------------------
# Salida: detalle completo de una venta
# ---------------------------------------------------------------------------
class VentaDetalleResponse(BaseModel):
    """Detalle completo de una venta (cabecera + líneas)."""

    id: int
    numero_boleta: str
    fecha: datetime
    subtotal: Decimal
    descuento: Decimal
    descuento_tipo: Optional[str]
    metodo_pago: str
    tipo_pago: str
    saldo_pendiente: Decimal
    cliente_id: Optional[int]
    cliente_nombre: Optional[str]
    total: Decimal
    detalles: list[DetalleHistorialResponse]

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_venta(cls, v: "Venta") -> "VentaDetalleResponse":
        return cls(
            id=v.id,
            numero_boleta=v.numero_boleta,
            fecha=v.fecha,
            subtotal=v.subtotal,
            descuento=v.descuento,
            descuento_tipo=v.descuento_tipo,
            metodo_pago=v.metodo_pago,
            tipo_pago=v.tipo_pago,
            saldo_pendiente=v.saldo_pendiente,
            cliente_id=v.cliente_id,
            cliente_nombre=v.cliente.nombre if v.cliente else None,
            total=v.total,
            detalles=[DetalleHistorialResponse.from_detalle(d) for d in v.detalles],
        )


# Paginación del historial.
class HistorialPaginado(BaseModel):
    """Respuesta paginada del listado de historial."""

    total: int               # total de ventas que cumplen el filtro
    page: int
    page_size: int
    items: list[HistorialResponse]


# ---------------------------------------------------------------------------
# Salida: metadatos de boleta (cuando se quiere info JSON en vez del PDF)
# ---------------------------------------------------------------------------
class BoletaResponse(BaseModel):
    """Metadatos de la boleta generada para una venta."""

    venta_id: int
    numero_boleta: str
    filename: str
    content_type: str = "application/pdf"
