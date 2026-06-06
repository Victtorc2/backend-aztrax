"""
Schemas Pydantic para la entidad Producto.

Notas de diseño:
- El `codigo` NO se recibe del cliente: lo genera el sistema. Por eso no
  aparece en `ProductoCreate` ni en `ProductoUpdate`.
- El `estado` tampoco se recibe: se calcula a partir del stock.
- Las validaciones de precios positivos (gt=0) y stock no negativo (ge=0) se
  declaran con restricciones de Pydantic, que devuelven 422 con detalle del
  campo si no se cumplen.
- `ProductoResponse` expone la categoría y el proveedor como NOMBRES (str),
  no como ids ni objetos, tal como pide el contrato del endpoint.
"""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.utils.productos import EstadoProducto

if TYPE_CHECKING:
    from app.models.producto import Producto


def _limpiar_obligatorio(valor: str) -> str:
    """Recorta/colapsa espacios; el campo no puede quedar vacío."""
    limpio = " ".join(valor.split())
    if not limpio:
        raise ValueError("El valor no puede estar vacío")
    return limpio


class ProductoCreate(BaseModel):
    """Datos para registrar un producto (sin código: se autogenera)."""

    nombre: str = Field(..., min_length=1, max_length=150, examples=["Coca Cola 3L"])
    marca: str = Field(..., min_length=1, max_length=100, examples=["Coca Cola"])
    modelo: Optional[str] = Field(
        default=None, max_length=100, examples=["Botella 3L retornable"]
    )
    categoria_id: int = Field(..., gt=0, examples=[1])
    proveedor_id: int = Field(..., gt=0, examples=[2])
    # Precios monetarios: deben ser positivos (> 0).
    precio_compra: Decimal = Field(
        ..., gt=0, max_digits=12, decimal_places=2, examples=[7.50]
    )
    precio_venta: Decimal = Field(
        ..., gt=0, max_digits=12, decimal_places=2, examples=[10.00]
    )
    # Stock: no puede ser negativo (>= 0).
    stock: int = Field(..., ge=0, examples=[15])
    stock_minimo: int = Field(..., ge=0, examples=[5])
    descripcion: Optional[str] = Field(default=None, max_length=5000)
    ficha_tecnica: Optional[str] = Field(default=None, max_length=5000)

    @field_validator("nombre", "marca")
    @classmethod
    def _v_texto(cls, v: str) -> str:
        return _limpiar_obligatorio(v)

    @field_validator("modelo")
    @classmethod
    def _v_modelo(cls, v: Optional[str]) -> Optional[str]:
        # Campo opcional: si llega vacío o solo espacios, se guarda como None.
        if v is None:
            return None
        limpio = " ".join(v.split())
        return limpio or None


class ProductoUpdate(BaseModel):
    """
    Datos para actualizar un producto. TODOS los campos son opcionales:
    se modifican únicamente los enviados (actualización parcial).
    """

    nombre: Optional[str] = Field(default=None, min_length=1, max_length=150)
    marca: Optional[str] = Field(default=None, min_length=1, max_length=100)
    modelo: Optional[str] = Field(default=None, max_length=100)
    categoria_id: Optional[int] = Field(default=None, gt=0)
    proveedor_id: Optional[int] = Field(default=None, gt=0)
    precio_compra: Optional[Decimal] = Field(
        default=None, gt=0, max_digits=12, decimal_places=2
    )
    precio_venta: Optional[Decimal] = Field(
        default=None, gt=0, max_digits=12, decimal_places=2
    )
    stock: Optional[int] = Field(default=None, ge=0)
    stock_minimo: Optional[int] = Field(default=None, ge=0)
    destacado: Optional[bool] = Field(default=None)
    descripcion: Optional[str] = Field(default=None, max_length=5000)
    ficha_tecnica: Optional[str] = Field(default=None, max_length=5000)

    @field_validator("nombre", "marca")
    @classmethod
    def _v_texto(cls, v: Optional[str]) -> Optional[str]:
        return _limpiar_obligatorio(v) if v is not None else None

    @field_validator("modelo")
    @classmethod
    def _v_modelo(cls, v: Optional[str]) -> Optional[str]:
        # Opcional: cadena vacía o espacios -> None (permite "limpiar" el campo).
        if v is None:
            return None
        limpio = " ".join(v.split())
        return limpio or None


class ProductoResponse(BaseModel):
    """
    Representación pública de un producto.

    La categoría y el proveedor se exponen como sus nombres.
    """

    id: int
    codigo: str
    nombre: str
    marca: str
    modelo: Optional[str]
    categoria: str
    proveedor: str
    precio_compra: Decimal
    precio_venta: Decimal
    stock: int
    stock_minimo: int
    estado: EstadoProducto
    imagen_url: Optional[str]
    destacado: bool
    descripcion: Optional[str]
    ficha_tecnica: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_producto(cls, producto: "Producto") -> "ProductoResponse":
        """
        Construye la respuesta a partir de un objeto ORM Producto.

        Extrae los nombres de las relaciones (categoría y proveedor). Hacerlo
        explícitamente mantiene el contrato claro y evita lazy-loads sorpresa.
        """
        return cls(
            id=producto.id,
            codigo=producto.codigo,
            nombre=producto.nombre,
            marca=producto.marca,
            modelo=producto.modelo,
            categoria=producto.categoria.nombre,
            proveedor=producto.proveedor.nombre,
            precio_compra=producto.precio_compra,
            precio_venta=producto.precio_venta,
            stock=producto.stock,
            stock_minimo=producto.stock_minimo,
            estado=EstadoProducto(producto.estado),
            imagen_url=producto.imagen_url,
            destacado=producto.destacado,
            descripcion=producto.descripcion,
            ficha_tecnica=producto.ficha_tecnica,
            created_at=producto.created_at,
        )


class ProductoPorPedirResponse(BaseModel):
    """
    Proyección de un producto para el módulo de reposición ("por pedir").

    Contiene solo los campos relevantes para decidir una reposición; la
    categoría y el proveedor se exponen como nombres.
    """

    id: int
    codigo: str
    nombre: str
    stock: int
    stock_minimo: int
    estado: EstadoProducto
    categoria: str
    proveedor: str

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_producto(cls, producto: "Producto") -> "ProductoPorPedirResponse":
        """Construye la respuesta a partir de un objeto ORM Producto."""
        return cls(
            id=producto.id,
            codigo=producto.codigo,
            nombre=producto.nombre,
            stock=producto.stock,
            stock_minimo=producto.stock_minimo,
            estado=EstadoProducto(producto.estado),
            categoria=producto.categoria.nombre,
            proveedor=producto.proveedor.nombre,
        )
