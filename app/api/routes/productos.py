"""
Rutas del módulo de productos.

Endpoints (todos protegidos con JWT mediante `Depends(get_current_user)`):
    POST   /productos          -> registrar (código y estado automáticos)
    GET    /productos          -> listar con filtros (search, categoria, proveedor, estado)
    GET    /productos/buscar   -> búsqueda por nombre / código / marca
    GET    /productos/{id}     -> obtener por id
    PUT    /productos/{id}     -> actualizar (parcial, recalcula estado)
    DELETE /productos/{id}     -> eliminar (soft delete)

IMPORTANTE: la ruta estática `/productos/buscar` se declara ANTES que la
dinámica `/productos/{producto_id}`. FastAPI evalúa las rutas en orden, así
que de lo contrario "buscar" se interpretaría como un id y fallaría.
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import CurrentUser, get_current_user
from app.schemas.producto import (
    ProductoCreate,
    ProductoResponse,
    ProductosPaginados,
    ProductoUpdate,
)
from app.services.producto_service import ProductoService
from app.utils.productos import EstadoProducto

# La autenticación se aplica a TODO el módulo de forma centralizada.
router = APIRouter(
    prefix="/productos",
    tags=["Productos"],
    dependencies=[Depends(get_current_user)],
)


@router.post(
    "",
    response_model=ProductoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar un nuevo producto",
)
def crear_producto(
    data: ProductoCreate,
    db: Annotated[Session, Depends(get_db)],
    _: CurrentUser,
) -> ProductoResponse:
    """
    Registra un producto.

    - El **código** se genera automáticamente (P0001, P0002, ...).
    - El **estado** se calcula según el stock (agotado / bajo_stock / disponible).
    - Se valida que **categoria_id** y **proveedor_id** existan (si no, 404).
    - Precios deben ser > 0 y el stock >= 0 (si no, 422).
    """
    producto = ProductoService(db).create(data)
    return ProductoResponse.from_producto(producto)


@router.get(
    "",
    response_model=ProductosPaginados,
    status_code=status.HTTP_200_OK,
    summary="Listar productos paginados (con filtros opcionales)",
)
def listar_productos(
    db: Annotated[Session, Depends(get_db)],
    _: CurrentUser,
    search: Annotated[
        Optional[str], Query(description="Búsqueda parcial por nombre o marca")
    ] = None,
    categoria: Annotated[
        Optional[int], Query(description="Filtrar por id de categoría")
    ] = None,
    marca: Annotated[
        Optional[str], Query(description="Filtrar por marca exacta")
    ] = None,
    proveedor: Annotated[
        Optional[int], Query(description="Filtrar por id de proveedor")
    ] = None,
    estado: Annotated[
        Optional[EstadoProducto], Query(description="Filtrar por estado")
    ] = None,
    page: Annotated[int, Query(ge=1, description="Número de página (1-indexada)")] = 1,
    page_size: Annotated[
        int, Query(ge=1, le=100, description="Productos por página")
    ] = 10,
) -> ProductosPaginados:
    """
    Lista los productos activos paginados (por defecto 10 por página),
    ordenados por fecha descendente.

    Filtros combinables (pensados para el filtro encadenado del panel admin
    categoría → marca):
    - `?categoria=1`
    - `?marca=Rapala`
    - `?search=coca` (por nombre, marca o modelo)
    - `?proveedor=2`
    - `?estado=agotado`
    - `?page=2&page_size=10`

    Devuelve un objeto con `items` y los metadatos `total`, `page`,
    `page_size` y `total_pages`.
    """
    productos, total = ProductoService(db).list_paginated(
        page=page,
        page_size=page_size,
        search=search,
        categoria=categoria,
        marca=marca,
        proveedor=proveedor,
        estado=estado.value if estado else None,
    )
    return ProductosPaginados.build(list(productos), total, page, page_size)


@router.get(
    "/buscar",
    response_model=list[ProductoResponse],
    status_code=status.HTTP_200_OK,
    summary="Buscar productos por nombre, código o marca",
)
def buscar_productos(
    db: Annotated[Session, Depends(get_db)],
    _: CurrentUser,
    q: Annotated[str, Query(description="Término de búsqueda", examples=["coca", "P0001"])],
) -> list[ProductoResponse]:
    """
    Busca productos por **nombre**, **código** o **marca** (coincidencia
    parcial, sin distinguir mayúsculas/minúsculas).

    Ejemplos: `GET /productos/buscar?q=coca`, `GET /productos/buscar?q=P0001`.
    """
    productos = ProductoService(db).search(q)
    return [ProductoResponse.from_producto(p) for p in productos]


@router.get(
    "/marcas",
    response_model=list[str],
    status_code=status.HTTP_200_OK,
    summary="Listar marcas distintas (opcionalmente por categoría)",
)
def listar_marcas(
    db: Annotated[Session, Depends(get_db)],
    _: CurrentUser,
    categoria: Annotated[
        Optional[int],
        Query(description="Filtrar marcas de una categoría (filtro encadenado)"),
    ] = None,
) -> list[str]:
    """
    Devuelve las marcas distintas de los productos activos, ordenadas
    alfabéticamente.

    Para el filtro encadenado del panel admin: tras elegir una categoría se
    llama a `GET /productos/marcas?categoria=1` para poblar el selector de
    marcas con solo las marcas de esa categoría.
    """
    return list(ProductoService(db).marcas(categoria=categoria))


@router.get(
    "/reporte/pdf",
    summary="Generar un reporte PDF del inventario de productos",
    responses={
        200: {"content": {"application/pdf": {}}, "description": "Reporte en PDF"},
    },
)
def reporte_productos_pdf(
    db: Annotated[Session, Depends(get_db)],
    _: CurrentUser,
    search: Annotated[
        Optional[str], Query(description="Búsqueda parcial por nombre o marca")
    ] = None,
    categoria: Annotated[
        Optional[int], Query(description="Filtrar por id de categoría")
    ] = None,
    proveedor: Annotated[
        Optional[int], Query(description="Filtrar por id de proveedor")
    ] = None,
    estado: Annotated[
        Optional[EstadoProducto], Query(description="Filtrar por estado")
    ] = None,
) -> Response:
    """
    Genera un reporte PDF del inventario con los mismos filtros que el listado
    (`search`, `categoria`, `proveedor`, `estado`) y lo devuelve como descarga.

    El reporte incluye una tabla con código, producto, marca, categoría,
    proveedor, precios, stock y estado, además de un resumen con el total de
    productos, unidades y la valorización del inventario.
    """
    pdf_bytes, filename = ProductoService(db).generar_reporte_pdf(
        search=search,
        categoria=categoria,
        proveedor=proveedor,
        estado=estado.value if estado else None,
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.get(
    "/{producto_id}",
    response_model=ProductoResponse,
    status_code=status.HTTP_200_OK,
    summary="Obtener un producto por su id",
)
def obtener_producto(
    producto_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: CurrentUser,
) -> ProductoResponse:
    """
    Devuelve el producto indicado.

    Responde **404** "Producto no encontrado" si no existe o está inactivo.
    """
    producto = ProductoService(db).get(producto_id)
    return ProductoResponse.from_producto(producto)


@router.put(
    "/{producto_id}",
    response_model=ProductoResponse,
    status_code=status.HTTP_200_OK,
    summary="Actualizar un producto (parcial)",
)
def actualizar_producto(
    producto_id: int,
    data: ProductoUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: CurrentUser,
) -> ProductoResponse:
    """
    Actualiza un producto. Todos los campos son opcionales.

    - **404** si el producto no existe.
    - **404** si la nueva categoría o proveedor no existen.
    - Recalcula el **estado** automáticamente si cambia el stock.
    """
    producto = ProductoService(db).update(producto_id, data)
    return ProductoResponse.from_producto(producto)


@router.put(
    "/{producto_id}/destacado",
    response_model=ProductoResponse,
    summary="Marcar o desmarcar un producto como destacado",
)
def marcar_destacado(
    producto_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: CurrentUser,
    destacado: Annotated[bool, Query(description="True para destacar, False para quitar")] = True,
) -> ProductoResponse:
    """Marca (o desmarca) un producto como destacado en el catálogo."""
    producto = ProductoService(db).update(
        producto_id, ProductoUpdate(destacado=destacado)
    )
    return ProductoResponse.from_producto(producto)


@router.delete(
    "/{producto_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar un producto (soft delete)",
)
def eliminar_producto(
    producto_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: CurrentUser,
) -> None:
    """
    Elimina un producto mediante **soft delete** (marca `is_active=False`).
    El registro se conserva para no perder integridad histórica.

    Responde **404** si el producto no existe o ya está inactivo.
    """
    ProductoService(db).delete(producto_id)
    return None
