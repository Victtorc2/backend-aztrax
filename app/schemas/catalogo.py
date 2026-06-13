"""
Schemas Pydantic para el catálogo público.

Versiones simplificadas de producto y categoría, solo con la info que el
visitante necesita ver (sin precios de compra, IDs internos innecesarios, etc.).
"""

from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict


class CatalogoProducto(BaseModel):
    """Producto visible en el catálogo público."""

    id: int
    codigo: str
    nombre: str
    marca: str
    modelo: Optional[str]
    color: Optional[str]
    categoria: str
    precio_venta: Decimal
    stock: int
    estado: str  # "disponible", "bajo_stock", "agotado"
    representacion: str  # "unidad", "sobre", "caja", ...
    imagen_url: Optional[str]
    destacado: bool
    descripcion: Optional[str]
    ficha_tecnica: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class CatalogoProductosPaginados(BaseModel):
    """Página de productos del catálogo con metadatos de paginación."""

    items: list[CatalogoProducto]
    total: int           # total de productos que cumplen los filtros (sin paginar)
    page: int            # página actual (1-indexada)
    page_size: int       # tamaño de página
    total_pages: int     # número total de páginas


class CatalogoCategoriaResponse(BaseModel):
    """Categoría para el filtro del catálogo."""

    id: int
    nombre: str
    cantidad_productos: int


class CatalogoMarcaResponse(BaseModel):
    """Marca para el filtro del catálogo."""

    nombre: str
    cantidad_productos: int


class CatalogoModeloResponse(BaseModel):
    """
    Modelo (agrupación) para la navegación del catálogo.

    En el flujo Categoría → Marca → Modelo → colores, al elegir una marca se
    listan sus modelos. Cada modelo agrupa varias variantes de color.
    """

    modelo: str
    cantidad_productos: int          # número de variantes (colores) del modelo
    imagen_url: Optional[str]        # imagen representativa de una variante
    precio_desde: Decimal            # precio de venta más bajo entre las variantes


class CatalogoBannerResponse(BaseModel):
    """Banner promocional activo."""

    id: int
    titulo: str
    descripcion: Optional[str]
    imagen_url: str
    orden: int

    model_config = ConfigDict(from_attributes=True)
