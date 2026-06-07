"""
Rutas públicas del catálogo.

Autenticadas con API key (header X-API-Key), sin JWT. Devuelven la info que
el visitante necesita ver en el catálogo: productos con imagen y precio,
categorías y marcas para filtrar, y banners de promociones.
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.api_key import require_api_key
from app.models.producto import Producto
from app.models.categoria import Categoria
from app.models.banner import Banner
from app.schemas.catalogo import (
    CatalogoBannerResponse,
    CatalogoCategoriaResponse,
    CatalogoMarcaResponse,
    CatalogoProducto,
    CatalogoProductosPaginados,
)

router = APIRouter(
    prefix="/catalogo",
    tags=["Catálogo público"],
    dependencies=[Depends(require_api_key)],
)


@router.get(
    "/productos",
    response_model=CatalogoProductosPaginados,
    summary="Lista paginada de productos para el catálogo público",
)
def listar_productos_catalogo(
    db: Annotated[Session, Depends(get_db)],
    categoria_id: Annotated[Optional[int], Query(description="Filtrar por categoría")] = None,
    marca: Annotated[Optional[str], Query(description="Filtrar por marca exacta")] = None,
    search: Annotated[Optional[str], Query(description="Buscar por nombre, marca o modelo")] = None,
    solo_destacados: Annotated[bool, Query(description="Solo productos destacados")] = False,
    page: Annotated[int, Query(ge=1, description="Número de página (1-indexada)")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Productos por página")] = 10,
) -> CatalogoProductosPaginados:
    """
    Devuelve los productos activos (incluidos los agotados) paginados, por
    defecto 10 por página. Filtros opcionales: categoría, marca, búsqueda y
    destacados. Los destacados se ordenan primero.

    Devuelve un objeto con `items` y los metadatos `total`, `page`,
    `page_size` y `total_pages`.
    """
    # Filtros comunes, aplicados tanto al conteo como a la página de datos.
    def aplicar_filtros(stmt):
        if categoria_id is not None:
            stmt = stmt.where(Producto.categoria_id == categoria_id)
        if marca and marca.strip():
            stmt = stmt.where(Producto.marca == marca.strip())
        if solo_destacados:
            stmt = stmt.where(Producto.destacado.is_(True))
        if search and search.strip():
            pattern = f"%{search.strip().lower()}%"
            stmt = stmt.where(
                func.lower(Producto.nombre).like(pattern)
                | func.lower(Producto.marca).like(pattern)
                | func.lower(Producto.modelo).like(pattern)
            )
        return stmt

    # Total de coincidencias (sin paginar) para calcular el número de páginas.
    total = db.scalar(
        aplicar_filtros(
            select(func.count(Producto.id)).where(Producto.is_active.is_(True))
        )
    ) or 0

    stmt = aplicar_filtros(
        select(Producto)
        .where(Producto.is_active.is_(True))
        .order_by(Producto.destacado.desc(), Producto.nombre.asc())
    ).offset((page - 1) * page_size).limit(page_size)

    productos = db.scalars(stmt).all()
    items = [
        CatalogoProducto(
            id=p.id, codigo=p.codigo, nombre=p.nombre, marca=p.marca,
            modelo=p.modelo, categoria=p.categoria.nombre, precio_venta=p.precio_venta,
            stock=p.stock, estado=p.estado, imagen_url=p.imagen_url, destacado=p.destacado,
            descripcion=p.descripcion, ficha_tecnica=p.ficha_tecnica,
        )
        for p in productos
    ]
    total_pages = (total + page_size - 1) // page_size if page_size else 0
    return CatalogoProductosPaginados(
        items=items, total=total, page=page, page_size=page_size, total_pages=total_pages,
    )


@router.get(
    "/categorias",
    response_model=list[CatalogoCategoriaResponse],
    summary="Categorías con cantidad de productos activos",
)
def listar_categorias_catalogo(
    db: Annotated[Session, Depends(get_db)],
) -> list[CatalogoCategoriaResponse]:
    """Devuelve las categorías que tienen al menos un producto activo."""
    stmt = (
        select(Categoria.id, Categoria.nombre, func.count(Producto.id).label("cantidad"))
        .join(Producto, Producto.categoria_id == Categoria.id)
        .where(Producto.is_active.is_(True))
        .group_by(Categoria.id, Categoria.nombre)
        .having(func.count(Producto.id) > 0)
        .order_by(Categoria.nombre.asc())
    )
    rows = db.execute(stmt).all()
    return [CatalogoCategoriaResponse(id=r.id, nombre=r.nombre, cantidad_productos=r.cantidad) for r in rows]


@router.get(
    "/marcas",
    response_model=list[CatalogoMarcaResponse],
    summary="Marcas con cantidad de productos (opcionalmente por categoría)",
)
def listar_marcas_catalogo(
    db: Annotated[Session, Depends(get_db)],
    categoria_id: Annotated[Optional[int], Query(description="Filtrar marcas de una categoría")] = None,
) -> list[CatalogoMarcaResponse]:
    """
    Devuelve las marcas con al menos un producto activo. Si se pasa
    `categoria_id`, devuelve solo las marcas de esa categoría (para el filtro
    encadenado categoría → marca).
    """
    stmt = (
        select(Producto.marca, func.count(Producto.id).label("cantidad"))
        .where(Producto.is_active.is_(True))
        .group_by(Producto.marca)
        .order_by(Producto.marca.asc())
    )
    if categoria_id is not None:
        stmt = stmt.where(Producto.categoria_id == categoria_id)
    rows = db.execute(stmt).all()
    return [CatalogoMarcaResponse(nombre=r.marca, cantidad_productos=r.cantidad) for r in rows]


@router.get(
    "/banners",
    response_model=list[CatalogoBannerResponse],
    summary="Banners promocionales activos",
)
def listar_banners_catalogo(
    db: Annotated[Session, Depends(get_db)],
) -> list[CatalogoBannerResponse]:
    """Devuelve los banners activos, ordenados por el campo `orden`."""
    stmt = select(Banner).where(Banner.is_active.is_(True)).order_by(Banner.orden.asc(), Banner.id.desc())
    return [CatalogoBannerResponse.model_validate(b) for b in db.scalars(stmt).all()]
