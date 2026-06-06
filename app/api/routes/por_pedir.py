"""
Rutas del módulo de reposición ("productos por pedir").

Endpoints (todos protegidos con JWT mediante `Depends(get_current_user)`):
    GET /productos/agotados     -> productos agotados
    GET /productos/bajo-stock   -> productos en bajo stock (no agotados)
    GET /productos/por-pedir    -> lista combinada con filtros y búsqueda

IMPORTANTE: estas rutas comparten el prefijo `/productos` con el módulo de
productos. Como son ESTÁTICAS, deben evaluarse antes que la ruta dinámica
`/productos/{producto_id}`. Esto se garantiza incluyendo este router ANTES
que el de productos en `app/api/router.py`.
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import CurrentUser, get_current_user
from app.schemas.producto import ProductoPorPedirResponse
from app.services.restock_service import RestockService
from app.utils.productos import EstadoPorPedir

# Autenticación aplicada a todo el módulo de forma centralizada.
router = APIRouter(
    prefix="/productos",
    tags=["Productos por Pedir"],
    dependencies=[Depends(get_current_user)],
)


@router.get(
    "/agotados",
    response_model=list[ProductoPorPedirResponse],
    status_code=status.HTTP_200_OK,
    summary="Listar productos agotados",
)
def listar_agotados(
    db: Annotated[Session, Depends(get_db)],
    _: CurrentUser,
) -> list[ProductoPorPedirResponse]:
    """
    Devuelve los productos **agotados** (stock 0 o estado "agotado"),
    excluyendo los inactivos.

    Orden: primero los más recientes, luego por menor stock.
    """
    productos = RestockService(db).agotados()
    return [ProductoPorPedirResponse.from_producto(p) for p in productos]


@router.get(
    "/bajo-stock",
    response_model=list[ProductoPorPedirResponse],
    status_code=status.HTTP_200_OK,
    summary="Listar productos con bajo stock",
)
def listar_bajo_stock(
    db: Annotated[Session, Depends(get_db)],
    _: CurrentUser,
) -> list[ProductoPorPedirResponse]:
    """
    Devuelve los productos con **bajo stock** (stock > 0 y stock <= mínimo, o
    estado "bajo_stock"), excluyendo los agotados y los inactivos.

    Orden: menor stock primero.
    """
    productos = RestockService(db).bajo_stock()
    return [ProductoPorPedirResponse.from_producto(p) for p in productos]


@router.get(
    "/por-pedir",
    response_model=list[ProductoPorPedirResponse],
    status_code=status.HTTP_200_OK,
    summary="Listar productos por pedir (agotados + bajo stock)",
)
def listar_por_pedir(
    db: Annotated[Session, Depends(get_db)],
    _: CurrentUser,
    search: Annotated[
        Optional[str], Query(description="Búsqueda parcial por nombre o código")
    ] = None,
    estado: Annotated[
        Optional[EstadoPorPedir],
        Query(description="Filtrar por estado: agotado o bajo_stock"),
    ] = None,
    categoria: Annotated[
        Optional[int], Query(description="Filtrar por id de categoría")
    ] = None,
    proveedor: Annotated[
        Optional[int], Query(description="Filtrar por id de proveedor")
    ] = None,
) -> list[ProductoPorPedirResponse]:
    """
    Devuelve la lista combinada de productos por pedir (agotados + bajo stock).

    Orden de prioridad: 1) agotados, 2) bajo stock.

    Filtros combinables:
    - `?estado=agotado` o `?estado=bajo_stock`
    - `?categoria=1`  (404 si la categoría no existe)
    - `?proveedor=2`  (404 si el proveedor no existe)
    - `?search=arroz` (por nombre o código)
    """
    productos = RestockService(db).por_pedir(
        search=search,
        estado=estado.value if estado else None,
        categoria=categoria,
        proveedor=proveedor,
    )
    return [ProductoPorPedirResponse.from_producto(p) for p in productos]
