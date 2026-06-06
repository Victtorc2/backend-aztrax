"""
Rutas del módulo de proveedores.

Endpoints (todos protegidos con JWT mediante `Depends(get_current_user)`):
    POST   /proveedores        -> registrar
    GET    /proveedores        -> listar / buscar (por nombre o RUC)
    GET    /proveedores/{id}   -> obtener por id
    PUT    /proveedores/{id}   -> actualizar (parcial)
    DELETE /proveedores/{id}   -> eliminar

Los endpoints son delgados: solo manejan la capa HTTP. Toda la lógica vive
en ProveedorService.
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import CurrentUser, get_current_user
from app.schemas.proveedor import (
    ProveedorCreate,
    ProveedorResponse,
    ProveedorUpdate,
)
from app.services.proveedor_service import ProveedorService

# La autenticación se aplica a TODO el módulo de forma centralizada.
router = APIRouter(
    prefix="/proveedores",
    tags=["Proveedores"],
    dependencies=[Depends(get_current_user)],
)


@router.post(
    "",
    response_model=ProveedorResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar un nuevo proveedor",
)
def crear_proveedor(
    data: ProveedorCreate,
    db: Annotated[Session, Depends(get_db)],
    _: CurrentUser,
) -> ProveedorResponse:
    """
    Registra un proveedor.

    - **nombre**: obligatorio (se recortan los espacios sobrantes).
    - **telefono, direccion, ruc, observaciones**: opcionales.
    - No se permiten nombres duplicados (ignorando mayúsculas/minúsculas) →
      **400** "Ya existe un proveedor con ese nombre".
    - Si se envía un **ruc** ya registrado → **400** "Ya existe un proveedor
      con ese RUC".
    """
    proveedor = ProveedorService(db).create(data)
    return ProveedorResponse.model_validate(proveedor)


@router.get(
    "",
    response_model=list[ProveedorResponse],
    status_code=status.HTTP_200_OK,
    summary="Listar proveedores (con búsqueda opcional)",
)
def listar_proveedores(
    db: Annotated[Session, Depends(get_db)],
    _: CurrentUser,
    search: Annotated[
        Optional[str],
        Query(description="Búsqueda parcial por nombre o RUC", examples=["norte"]),
    ] = None,
) -> list[ProveedorResponse]:
    """
    Lista todos los proveedores ordenados por fecha de creación descendente.

    Con el parámetro **search**, devuelve coincidencias parciales por
    **nombre o RUC** (sin distinguir mayúsculas/minúsculas).
    Ejemplo: `GET /proveedores?search=norte`.
    """
    proveedores = ProveedorService(db).list(search=search)
    return [ProveedorResponse.model_validate(p) for p in proveedores]


@router.get(
    "/{proveedor_id}",
    response_model=ProveedorResponse,
    status_code=status.HTTP_200_OK,
    summary="Obtener un proveedor por su id",
)
def obtener_proveedor(
    proveedor_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: CurrentUser,
) -> ProveedorResponse:
    """
    Devuelve el proveedor indicado.

    Responde **404** "Proveedor no encontrado" si el id no existe.
    """
    proveedor = ProveedorService(db).get(proveedor_id)
    return ProveedorResponse.model_validate(proveedor)


@router.put(
    "/{proveedor_id}",
    response_model=ProveedorResponse,
    status_code=status.HTTP_200_OK,
    summary="Actualizar un proveedor (parcial)",
)
def actualizar_proveedor(
    proveedor_id: int,
    data: ProveedorUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: CurrentUser,
) -> ProveedorResponse:
    """
    Actualiza un proveedor. Todos los campos son opcionales: se modifican
    únicamente los enviados.

    - **404** si el proveedor no existe.
    - **400** si el nuevo nombre o RUC ya lo usa otro proveedor.
    """
    proveedor = ProveedorService(db).update(proveedor_id, data)
    return ProveedorResponse.model_validate(proveedor)


@router.delete(
    "/{proveedor_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar un proveedor",
)
def eliminar_proveedor(
    proveedor_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: CurrentUser,
) -> None:
    """
    Elimina un proveedor.

    - **404** si el proveedor no existe.
    - **409** "No se puede eliminar un proveedor asociado a productos" si
      tiene productos asociados (preparado para fases futuras).
    """
    ProveedorService(db).delete(proveedor_id)
    return None
