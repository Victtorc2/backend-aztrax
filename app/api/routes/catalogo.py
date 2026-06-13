"""
Rutas públicas del catálogo.

Autenticadas con API key (header X-API-Key), sin JWT. Devuelven la info que
el visitante necesita ver en el catálogo: productos con imagen y precio,
categorías y marcas para filtrar, y banners de promociones.
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, select
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
    CatalogoModeloResponse,
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
    modelo: Annotated[Optional[str], Query(description="Filtrar por modelo exacto (para ver sus colores)")] = None,
    search: Annotated[Optional[str], Query(description="Buscar por nombre, marca, modelo o color")] = None,
    solo_destacados: Annotated[bool, Query(description="Solo productos destacados")] = False,
    orden: Annotated[
        str,
        Query(description="Orden: destacados | precio_asc | precio_desc | nombre | reciente"),
    ] = "destacados",
    page: Annotated[int, Query(ge=1, description="Número de página (1-indexada)")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Productos por página")] = 10,
) -> CatalogoProductosPaginados:
    """
    Devuelve los productos activos (incluidos los agotados) paginados, por
    defecto 10 por página. Filtros opcionales: categoría, marca, búsqueda y
    destacados.

    Los productos agotados siempre se muestran al final. Dentro de los
    disponibles, `orden` controla el criterio: `destacados` (por defecto:
    destacados primero, luego A-Z), `precio_asc`, `precio_desc`, `nombre` o
    `reciente`.

    Devuelve un objeto con `items` y los metadatos `total`, `page`,
    `page_size` y `total_pages`.
    """
    # Los agotados van siempre al final (0 = disponible/bajo stock, 1 = agotado).
    agotado_last = case((Producto.estado == "agotado", 1), else_=0).asc()
    criterios = {
        "precio_asc": (Producto.precio_venta.asc(), Producto.nombre.asc()),
        "precio_desc": (Producto.precio_venta.desc(), Producto.nombre.asc()),
        "nombre": (Producto.nombre.asc(),),
        "reciente": (Producto.created_at.desc(), Producto.id.desc()),
    }
    orden_cols = criterios.get(orden, (Producto.destacado.desc(), Producto.nombre.asc()))
    # Filtros comunes, aplicados tanto al conteo como a la página de datos.
    def aplicar_filtros(stmt):
        if categoria_id is not None:
            stmt = stmt.where(Producto.categoria_id == categoria_id)
        if marca and marca.strip():
            stmt = stmt.where(Producto.marca == marca.strip())
        if modelo and modelo.strip():
            stmt = stmt.where(func.lower(Producto.modelo) == modelo.strip().lower())
        if solo_destacados:
            stmt = stmt.where(Producto.destacado.is_(True))
        if search and search.strip():
            pattern = f"%{search.strip().lower()}%"
            stmt = stmt.where(
                func.lower(Producto.nombre).like(pattern)
                | func.lower(Producto.marca).like(pattern)
                | func.lower(Producto.modelo).like(pattern)
                | func.lower(Producto.color).like(pattern)
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
        .order_by(agotado_last, *orden_cols)
    ).offset((page - 1) * page_size).limit(page_size)

    productos = db.scalars(stmt).all()
    items = [
        CatalogoProducto(
            id=p.id, codigo=p.codigo, nombre=p.nombre, marca=p.marca,
            modelo=p.modelo, color=p.color, categoria=p.categoria.nombre,
            precio_venta=p.precio_venta,
            stock=p.stock, estado=p.estado, representacion=p.representacion,
            imagen_url=p.imagen_url, destacado=p.destacado,
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
    "/modelos",
    response_model=list[CatalogoModeloResponse],
    summary="Modelos de una marca (con cantidad de colores e imagen)",
)
def listar_modelos_catalogo(
    db: Annotated[Session, Depends(get_db)],
    marca: Annotated[str, Query(description="Marca de la que se listan los modelos")],
    categoria_id: Annotated[Optional[int], Query(description="Acotar a una categoría")] = None,
) -> list[CatalogoModeloResponse]:
    """
    Devuelve los modelos de una marca para la navegación encadenada del
    catálogo: Categoría → Marca → **Modelo** → colores.

    Por cada modelo incluye la cantidad de variantes (colores), una imagen
    representativa y el precio más bajo. Los productos sin modelo se omiten.
    Tras elegir un modelo, se piden sus colores con
    `GET /catalogo/productos?marca=...&modelo=...`.
    """
    stmt = (
        select(
            Producto.modelo.label("modelo"),
            func.count(Producto.id).label("cantidad"),
            # MAX ignora NULL: devuelve una imagen no nula si alguna existe.
            func.max(Producto.imagen_url).label("imagen_url"),
            func.min(Producto.precio_venta).label("precio_desde"),
        )
        .where(
            Producto.is_active.is_(True),
            Producto.modelo.is_not(None),
            func.lower(Producto.marca) == marca.strip().lower(),
        )
        .group_by(Producto.modelo)
        .order_by(Producto.modelo.asc())
    )
    if categoria_id is not None:
        stmt = stmt.where(Producto.categoria_id == categoria_id)
    rows = db.execute(stmt).all()
    return [
        CatalogoModeloResponse(
            modelo=r.modelo,
            cantidad_productos=r.cantidad,
            imagen_url=r.imagen_url,
            precio_desde=r.precio_desde,
        )
        for r in rows
    ]


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
