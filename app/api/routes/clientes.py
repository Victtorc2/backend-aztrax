"""
Rutas del módulo de clientes.

Endpoints (protegidos con JWT):
    POST   /clientes            -> registrar
    GET    /clientes            -> listar / buscar
    GET    /clientes/deudores   -> solo clientes con deuda pendiente
    GET    /clientes/{id}       -> obtener (con deuda total)
    GET    /clientes/{id}/estado-cuenta -> ventas a crédito + abonos
    PUT    /clientes/{id}       -> actualizar (parcial)
    DELETE /clientes/{id}       -> baja lógica

Los endpoints son delgados: la lógica vive en ClienteService.
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import CurrentUser, get_current_user
from app.schemas.cliente import ClienteCreate, ClienteResponse, ClienteUpdate
from app.schemas.credito import EstadoCuentaResponse
from app.services.cliente_service import ClienteService
from app.services.credito_service import CreditoService

router = APIRouter(
    prefix="/clientes",
    tags=["Clientes"],
    dependencies=[Depends(get_current_user)],
)


@router.post(
    "",
    response_model=ClienteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar un nuevo cliente",
)
def crear_cliente(
    data: ClienteCreate,
    db: Annotated[Session, Depends(get_db)],
    _: CurrentUser,
) -> ClienteResponse:
    """
    Registra un cliente.

    - **nombre**: obligatorio.
    - **documento, telefono, email, direccion, nota**: opcionales.
    - Si se envía un **documento** ya registrado → **400**.
    """
    return ClienteService(db).create(data)


@router.get(
    "",
    response_model=list[ClienteResponse],
    summary="Listar clientes (con búsqueda opcional)",
)
def listar_clientes(
    db: Annotated[Session, Depends(get_db)],
    _: CurrentUser,
    search: Annotated[
        Optional[str],
        Query(description="Búsqueda por nombre, documento o teléfono"),
    ] = None,
) -> list[ClienteResponse]:
    """Lista clientes con su deuda total. Con `search`, filtra por coincidencia."""
    return ClienteService(db).listar(search=search)


@router.get(
    "/deudores",
    response_model=list[ClienteResponse],
    summary="Clientes con deuda pendiente",
)
def listar_deudores(
    db: Annotated[Session, Depends(get_db)],
    _: CurrentUser,
) -> list[ClienteResponse]:
    """Devuelve solo los clientes con saldo pendiente, mayor deuda primero."""
    return ClienteService(db).list_deudores()


@router.get(
    "/{cliente_id}",
    response_model=ClienteResponse,
    summary="Obtener un cliente por su id",
)
def obtener_cliente(
    cliente_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: CurrentUser,
) -> ClienteResponse:
    """Devuelve el cliente y su deuda total. **404** si no existe."""
    return ClienteService(db).get(cliente_id)


@router.get(
    "/{cliente_id}/estado-cuenta",
    response_model=EstadoCuentaResponse,
    summary="Estado de cuenta: ventas al crédito y abonos del cliente",
)
def estado_cuenta(
    cliente_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: CurrentUser,
) -> EstadoCuentaResponse:
    """
    Devuelve el detalle de las ventas al crédito del cliente, con sus abonos
    y saldos, más el total adeudado. **404** si el cliente no existe.
    """
    return CreditoService(db).estado_cuenta(cliente_id)


@router.put(
    "/{cliente_id}",
    response_model=ClienteResponse,
    summary="Actualizar un cliente (parcial)",
)
def actualizar_cliente(
    cliente_id: int,
    data: ClienteUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: CurrentUser,
) -> ClienteResponse:
    """Actualiza solo los campos enviados. **404** si no existe; **400** si el documento choca."""
    return ClienteService(db).update(cliente_id, data)


@router.delete(
    "/{cliente_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Dar de baja un cliente",
)
def eliminar_cliente(
    cliente_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: CurrentUser,
) -> None:
    """
    Baja lógica del cliente.

    - **404** si no existe.
    - **409** si tiene deuda pendiente (no se puede dar de baja).
    """
    ClienteService(db).delete(cliente_id)
    return None
