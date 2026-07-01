"""
Rutas del módulo de gastos / egresos de dinero (protegidas con JWT).

    POST   /gastos           -> registrar un gasto (salida de dinero)
    GET    /gastos           -> listar gastos con filtros
    GET    /gastos/saldo     -> dinero disponible por método (efectivo/yape)
    POST   /gastos/ajustes   -> agregar o modificar el saldo (con motivo)
    GET    /gastos/ajustes   -> historial de ajustes de saldo
    DELETE /gastos/{id}      -> eliminar un gasto

Las rutas estáticas (`/gastos/saldo`, `/gastos/ajustes`) se declaran ANTES que
la dinámica `/gastos/{id}` para que no las capture la ruta con parámetro.

Los endpoints son delgados: la lógica vive en GastoService.
"""

from datetime import date
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import CurrentUser, get_current_user
from app.schemas.gasto import (
    AjusteSaldoCreate,
    AjusteSaldoResponse,
    CategoriaGasto,
    GastoCreate,
    GastoResponse,
    MetodoPagoGasto,
    SaldoResponse,
)
from app.services.gasto_service import GastoService

router = APIRouter(
    prefix="/gastos",
    tags=["Gastos y saldo"],
    dependencies=[Depends(get_current_user)],
)


@router.post(
    "",
    response_model=GastoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar un gasto (salida de dinero)",
)
def registrar_gasto(
    data: GastoCreate,
    db: Annotated[Session, Depends(get_db)],
    _: CurrentUser,
) -> GastoResponse:
    """
    Registra una salida de dinero (un pedido/compra, un servicio, un sueldo,
    etc.) con su método de pago. El saldo del método usado baja al instante.

    Si el gasto es en efectivo y hay una caja abierta, se vincula a esa sesión
    para que el arqueo lo descuente. **404** si el proveedor indicado no existe.
    """
    return GastoService(db).registrar(data)


@router.get(
    "/saldo",
    response_model=SaldoResponse,
    summary="Dinero disponible por método de pago",
)
def obtener_saldo(
    db: Annotated[Session, Depends(get_db)],
    _: CurrentUser,
) -> SaldoResponse:
    """
    Devuelve el dinero disponible por método (efectivo y yape) y el total.

    Saldo de cada método = ventas al contado + abonos con ese método − gastos
    con ese método (todo sobre ventas no anuladas).
    """
    return GastoService(db).saldo()


@router.post(
    "/ajustes",
    response_model=SaldoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Agregar o modificar el saldo de un método (con motivo)",
)
def ajustar_saldo(
    data: AjusteSaldoCreate,
    db: Annotated[Session, Depends(get_db)],
    _: CurrentUser,
) -> SaldoResponse:
    """
    Ajusta manualmente el saldo de un método de pago, guardando una
    especificación (motivo):

    - `modo="agregar"`: suma el monto al saldo actual.
    - `modo="establecer"`: fija el saldo a ese monto (registra la diferencia).

    Devuelve el saldo actualizado. **400** si el ajuste no cambia el saldo.
    """
    return GastoService(db).registrar_ajuste(data)


@router.get(
    "/ajustes",
    response_model=list[AjusteSaldoResponse],
    summary="Historial de ajustes de saldo",
)
def listar_ajustes(
    db: Annotated[Session, Depends(get_db)],
    _: CurrentUser,
    metodo_pago: Annotated[
        Optional[MetodoPagoGasto], Query(description="Filtrar por método de pago")
    ] = None,
) -> list[AjusteSaldoResponse]:
    """Lista los ajustes de saldo, más recientes primero."""
    return GastoService(db).listar_ajustes(
        metodo_pago=metodo_pago.value if metodo_pago else None,
    )


@router.get(
    "",
    response_model=list[GastoResponse],
    summary="Listar gastos con filtros",
)
def listar_gastos(
    db: Annotated[Session, Depends(get_db)],
    _: CurrentUser,
    categoria: Annotated[
        Optional[CategoriaGasto], Query(description="Filtrar por categoría")
    ] = None,
    metodo_pago: Annotated[
        Optional[MetodoPagoGasto], Query(description="Filtrar por método de pago")
    ] = None,
    proveedor: Annotated[
        Optional[int], Query(description="Filtrar por id de proveedor")
    ] = None,
    fecha_inicio: Annotated[
        Optional[date], Query(description="Desde esta fecha (inclusive)")
    ] = None,
    fecha_fin: Annotated[
        Optional[date], Query(description="Hasta esta fecha (inclusive)")
    ] = None,
) -> list[GastoResponse]:
    """Lista los gastos que cumplen los filtros, más recientes primero."""
    return GastoService(db).listar(
        categoria=categoria.value if categoria else None,
        metodo_pago=metodo_pago.value if metodo_pago else None,
        proveedor_id=proveedor,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
    )


@router.delete(
    "/{gasto_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar un gasto",
)
def eliminar_gasto(
    gasto_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: CurrentUser,
) -> None:
    """Elimina un gasto. **404** si no existe."""
    GastoService(db).eliminar(gasto_id)
