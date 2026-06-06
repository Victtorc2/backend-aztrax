"""
Rutas del módulo de categorías.

Endpoints (todos protegidos con JWT mediante `Depends(get_current_user)`):
    POST   /categorias        -> crear
    GET    /categorias        -> listar / buscar
    GET    /categorias/{id}   -> obtener por id
    PUT    /categorias/{id}   -> actualizar
    DELETE /categorias/{id}   -> eliminar

Los endpoints son delgados: solo manejan la capa HTTP (entrada/salida y
códigos de estado). Toda la lógica vive en CategoriaService.
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import CurrentUser
from app.schemas.categoria import (
    CategoriaCreate,
    CategoriaResponse,
    CategoriaUpdate,
)
from app.services.categoria_service import CategoriaService

# `dependencies=[Depends(...)]` a nivel de router aplica la autenticación a
# TODAS las rutas del módulo, de forma centralizada y a prueba de olvidos.
# Importamos get_current_user para usarlo aquí.
from app.dependencies.auth import get_current_user

router = APIRouter(
    prefix="/categorias",
    tags=["Categorías"],
    dependencies=[Depends(get_current_user)],  # protege TODO el módulo
)


@router.post(
    "",
    response_model=CategoriaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar una nueva categoría",
)
def crear_categoria(
    data: CategoriaCreate,
    db: Annotated[Session, Depends(get_db)],
    _: CurrentUser,  # exige token válido (el usuario en sí no se usa aquí)
) -> CategoriaResponse:
    """
    Crea una categoría.

    - **nombre**: obligatorio. Se recortan los espacios sobrantes.
    - No se permiten nombres duplicados (ignorando mayúsculas/minúsculas).
      Si el nombre ya existe, responde **400** con
      "Ya existe una categoría con ese nombre".
    """
    categoria = CategoriaService(db).create(data)
    return CategoriaResponse.model_validate(categoria)


@router.get(
    "",
    response_model=list[CategoriaResponse],
    status_code=status.HTTP_200_OK,
    summary="Listar categorías (con búsqueda opcional)",
)
def listar_categorias(
    db: Annotated[Session, Depends(get_db)],
    _: CurrentUser,
    search: Annotated[
        Optional[str],
        Query(description="Filtro de búsqueda parcial por nombre", examples=["beb"]),
    ] = None,
) -> list[CategoriaResponse]:
    """
    Lista todas las categorías ordenadas por fecha de creación descendente.

    Si se envía el parámetro **search**, devuelve solo las coincidencias
    parciales por nombre (sin distinguir mayúsculas/minúsculas).
    Ejemplo: `GET /categorias?search=beb`.
    """
    categorias = CategoriaService(db).list(search=search)
    return [CategoriaResponse.model_validate(c) for c in categorias]


@router.get(
    "/{categoria_id}",
    response_model=CategoriaResponse,
    status_code=status.HTTP_200_OK,
    summary="Obtener una categoría por su id",
)
def obtener_categoria(
    categoria_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: CurrentUser,
) -> CategoriaResponse:
    """
    Devuelve la categoría indicada.

    Responde **404** "Categoría no encontrada" si el id no existe.
    """
    categoria = CategoriaService(db).get(categoria_id)
    return CategoriaResponse.model_validate(categoria)


@router.put(
    "/{categoria_id}",
    response_model=CategoriaResponse,
    status_code=status.HTTP_200_OK,
    summary="Actualizar una categoría",
)
def actualizar_categoria(
    categoria_id: int,
    data: CategoriaUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: CurrentUser,
) -> CategoriaResponse:
    """
    Actualiza el nombre de una categoría.

    - Responde **404** si la categoría no existe.
    - Responde **400** si el nuevo nombre ya lo usa otra categoría.
    """
    categoria = CategoriaService(db).update(categoria_id, data)
    return CategoriaResponse.model_validate(categoria)


@router.delete(
    "/{categoria_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar una categoría",
)
def eliminar_categoria(
    categoria_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: CurrentUser,
) -> None:
    """
    Elimina una categoría.

    - Responde **404** si la categoría no existe.
    - Responde **409** "No se puede eliminar una categoría asociada a
      productos" si tiene productos asociados (preparado para fases futuras).

    Un 204 no devuelve cuerpo de respuesta.
    """
    CategoriaService(db).delete(categoria_id)
    return None
