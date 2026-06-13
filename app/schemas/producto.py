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

from app.utils.productos import EstadoProducto, Representacion

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
    color: Optional[str] = Field(
        default=None, max_length=100, examples=["Verde fluor"]
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
    # Representación de venta (opcional): unidad por defecto.
    representacion: Representacion = Field(
        default=Representacion.UNIDAD, examples=["unidad"]
    )
    descripcion: Optional[str] = Field(default=None, max_length=5000)
    ficha_tecnica: Optional[str] = Field(default=None, max_length=5000)

    @field_validator("nombre", "marca")
    @classmethod
    def _v_texto(cls, v: str) -> str:
        return _limpiar_obligatorio(v)

    @field_validator("modelo", "color")
    @classmethod
    def _v_opcional(cls, v: Optional[str]) -> Optional[str]:
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
    color: Optional[str] = Field(default=None, max_length=100)
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
    representacion: Optional[Representacion] = Field(default=None)
    descripcion: Optional[str] = Field(default=None, max_length=5000)
    ficha_tecnica: Optional[str] = Field(default=None, max_length=5000)

    @field_validator("nombre", "marca")
    @classmethod
    def _v_texto(cls, v: Optional[str]) -> Optional[str]:
        return _limpiar_obligatorio(v) if v is not None else None

    @field_validator("modelo", "color")
    @classmethod
    def _v_opcional(cls, v: Optional[str]) -> Optional[str]:
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
    color: Optional[str]
    categoria: str
    proveedor: str
    precio_compra: Decimal
    precio_venta: Decimal
    stock: int
    stock_minimo: int
    estado: EstadoProducto
    representacion: Representacion
    is_active: bool
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
            color=producto.color,
            categoria=producto.categoria.nombre,
            proveedor=producto.proveedor.nombre,
            precio_compra=producto.precio_compra,
            precio_venta=producto.precio_venta,
            stock=producto.stock,
            stock_minimo=producto.stock_minimo,
            estado=EstadoProducto(producto.estado),
            representacion=Representacion(producto.representacion),
            is_active=producto.is_active,
            imagen_url=producto.imagen_url,
            destacado=producto.destacado,
            descripcion=producto.descripcion,
            ficha_tecnica=producto.ficha_tecnica,
            created_at=producto.created_at,
        )


class ProductosPaginados(BaseModel):
    """
    Página de productos con metadatos de paginación.

    El panel de administración usa `total` y `total_pages` para dibujar los
    controles de paginación (10 productos por página por defecto).
    """

    items: list[ProductoResponse]
    total: int           # total de productos que cumplen los filtros (sin paginar)
    page: int            # página actual (1-indexada)
    page_size: int       # tamaño de página
    total_pages: int     # número total de páginas

    @classmethod
    def build(
        cls,
        productos: "list[Producto]",
        total: int,
        page: int,
        page_size: int,
    ) -> "ProductosPaginados":
        """Construye la respuesta paginada calculando el número de páginas."""
        total_pages = (total + page_size - 1) // page_size if page_size else 0
        return cls(
            items=[ProductoResponse.from_producto(p) for p in productos],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
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
    modelo: Optional[str] = None
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
            modelo=producto.modelo,
            stock=producto.stock,
            stock_minimo=producto.stock_minimo,
            estado=EstadoProducto(producto.estado),
            categoria=producto.categoria.nombre,
            proveedor=producto.proveedor.nombre,
        )
