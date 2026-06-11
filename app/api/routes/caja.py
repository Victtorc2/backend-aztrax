"""
Rutas del módulo de caja diaria (protegidas con JWT).

    POST /caja/abrir        -> abrir caja con un fondo inicial
    GET  /caja/actual       -> estado y arqueo en vivo de la caja abierta
    POST /caja/movimientos  -> registrar ingreso/egreso manual de efectivo
    POST /caja/cerrar       -> cerrar caja (arqueo: esperado vs declarado)
    GET  /caja              -> historial de sesiones de caja

Los endpoints son delgados: la lógica vive en CajaService.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import CurrentUser, get_current_user
from app.schemas.caja import (
    CajaAbrir,
    CajaCerrar,
    CajaHistorialItem,
    CajaResponse,
    MovimientoCajaCreate,
)
from app.services.caja_service import CajaService

router = APIRouter(
    prefix="/caja",
    tags=["Caja diaria"],
    dependencies=[Depends(get_current_user)],
)


@router.post(
    "/abrir",
    response_model=CajaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Abrir la caja con un fondo inicial",
)
def abrir_caja(
    data: CajaAbrir,
    db: Annotated[Session, Depends(get_db)],
    _: CurrentUser,
) -> CajaResponse:
    """
    Abre una sesión de caja con el efectivo inicial (fondo de cambio).

    **409** si ya hay una caja abierta (debe cerrarse antes de abrir otra).
    """
    return CajaService(db).abrir(data)


@router.get(
    "/actual",
    response_model=CajaResponse,
    summary="Estado y arqueo en vivo de la caja abierta",
)
def caja_actual(
    db: Annotated[Session, Depends(get_db)],
    _: CurrentUser,
) -> CajaResponse:
    """
    Devuelve la caja abierta con su arqueo calculado en vivo (efectivo inicial,
    ventas en efectivo, ingresos/egresos y monto esperado).

    **409** si no hay ninguna caja abierta.
    """
    return CajaService(db).actual()


@router.post(
    "/movimientos",
    response_model=CajaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar un ingreso/egreso manual de efectivo",
)
def registrar_movimiento(
    data: MovimientoCajaCreate,
    db: Annotated[Session, Depends(get_db)],
    _: CurrentUser,
) -> CajaResponse:
    """
    Registra un ingreso (entra efectivo) o egreso (sale efectivo, p. ej. un
    retiro para comprar) en la caja abierta. **409** si no hay caja abierta.
    """
    return CajaService(db).registrar_movimiento(data)


@router.post(
    "/cerrar",
    response_model=CajaResponse,
    summary="Cerrar la caja (arqueo)",
)
def cerrar_caja(
    data: CajaCerrar,
    db: Annotated[Session, Depends(get_db)],
    _: CurrentUser,
) -> CajaResponse:
    """
    Cierra la caja abierta. Calcula el monto esperado (inicial + ventas en
    efectivo + ingresos − egresos) y la diferencia con el efectivo declarado.

    **409** si no hay ninguna caja abierta.
    """
    return CajaService(db).cerrar(data)


@router.get(
    "",
    response_model=list[CajaHistorialItem],
    summary="Historial de sesiones de caja",
)
def historial_cajas(
    db: Annotated[Session, Depends(get_db)],
    _: CurrentUser,
) -> list[CajaHistorialItem]:
    """Lista las sesiones de caja, más recientes primero."""
    return CajaService(db).historial()
