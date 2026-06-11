"""
Schemas Pydantic para la entidad Cliente.

Mismo enfoque que Proveedor: el nombre se normaliza (recorte y colapso de
espacios), los opcionales vacíos se vuelven None, y Update tiene todos los
campos opcionales para actualizaciones parciales.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _limpiar_nombre(valor: str) -> str:
    limpio = " ".join(valor.split())
    if not limpio:
        raise ValueError("El nombre no puede estar vacío")
    return limpio


def _limpiar_opcional(valor: Optional[str]) -> Optional[str]:
    if valor is None:
        return None
    limpio = " ".join(valor.split())
    return limpio or None


class ClienteCreate(BaseModel):
    """Datos para registrar un cliente. Solo `nombre` es obligatorio."""

    nombre: str = Field(..., min_length=1, max_length=150, examples=["Juan Pérez"])
    documento: Optional[str] = Field(default=None, max_length=20, examples=["12345678"])
    telefono: Optional[str] = Field(default=None, max_length=20, examples=["999888777"])
    email: Optional[str] = Field(default=None, max_length=120)
    direccion: Optional[str] = Field(default=None, max_length=200)
    nota: Optional[str] = Field(default=None, max_length=255)
    fecha_nacimiento: Optional[date] = Field(default=None, examples=["1990-05-20"])

    @field_validator("nombre")
    @classmethod
    def _v_nombre(cls, v: str) -> str:
        return _limpiar_nombre(v)

    @field_validator("documento", "telefono", "email", "direccion", "nota")
    @classmethod
    def _v_opcionales(cls, v: Optional[str]) -> Optional[str]:
        return _limpiar_opcional(v)


class ClienteUpdate(BaseModel):
    """Datos para actualizar un cliente (todos los campos opcionales)."""

    nombre: Optional[str] = Field(default=None, min_length=1, max_length=150)
    documento: Optional[str] = Field(default=None, max_length=20)
    telefono: Optional[str] = Field(default=None, max_length=20)
    email: Optional[str] = Field(default=None, max_length=120)
    direccion: Optional[str] = Field(default=None, max_length=200)
    nota: Optional[str] = Field(default=None, max_length=255)
    fecha_nacimiento: Optional[date] = Field(default=None)

    @field_validator("nombre")
    @classmethod
    def _v_nombre(cls, v: Optional[str]) -> Optional[str]:
        return _limpiar_nombre(v) if v is not None else None

    @field_validator("documento", "telefono", "email", "direccion", "nota")
    @classmethod
    def _v_opcionales(cls, v: Optional[str]) -> Optional[str]:
        return _limpiar_opcional(v)


class ClienteResponse(BaseModel):
    """Representación pública de un cliente, con su deuda total pendiente."""

    id: int
    nombre: str
    documento: Optional[str]
    telefono: Optional[str]
    email: Optional[str]
    direccion: Optional[str]
    nota: Optional[str]
    fecha_nacimiento: Optional[date]
    puntos: int = 0
    is_active: bool
    created_at: datetime
    # Suma de saldos pendientes de todas sus ventas al crédito.
    deuda_total: Decimal = Decimal("0.00")

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Perfil / historial de compra del cliente
# ---------------------------------------------------------------------------
class ProductoFavorito(BaseModel):
    """Un producto dentro del top de los más comprados por el cliente."""

    producto_id: int
    nombre: str
    marca: str
    unidades: int


class CompraResumen(BaseModel):
    """Resumen de una venta para el historial reciente del cliente."""

    venta_id: int
    numero_boleta: str
    fecha: datetime
    total: Decimal
    metodo_pago: str
    tipo_pago: str
    anulada: bool


class PerfilCliente(BaseModel):
    """
    Perfil 360° del cliente: sus datos, métricas de compra y favoritos.

    Las métricas excluyen ventas anuladas. Sirve para conocer al cliente y
    fidelizarlo (cuánto ha gastado, qué prefiere, cuándo fue su última visita).
    """

    cliente: ClienteResponse
    total_compras: int
    total_gastado: Decimal
    ticket_promedio: Decimal
    ultima_compra: Optional[datetime]
    productos_favoritos: list[ProductoFavorito]
    compras_recientes: list[CompraResumen]


class ClienteInactivo(BaseModel):
    """Cliente que no compra hace cierto tiempo (candidato a recuperar)."""

    id: int
    nombre: str
    telefono: Optional[str]
    ultima_compra: Optional[datetime]
    dias_sin_comprar: Optional[int]
    total_gastado: Decimal
