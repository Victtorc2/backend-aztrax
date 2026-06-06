"""
Rutas del módulo de ventas (Fase 10 + registro de venta).

Endpoints (protegidos con JWT):
    POST /ventas             -> registrar una venta (descuenta stock)
    GET  /ventas/{id}/boleta -> generar/descargar la boleta en PDF

La respuesta de la boleta es un application/pdf descargable.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import CurrentUser, get_current_user
from app.schemas.credito import AbonoCreate, AbonoResponse
from app.schemas.venta import VentaCreate, VentaDetalleResponse
from app.services.credito_service import CreditoService
from app.services.venta_service import VentaService

router = APIRouter(
    prefix="/ventas",
    tags=["Ventas"],
    dependencies=[Depends(get_current_user)],
)


@router.post(
    "",
    response_model=VentaDetalleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar una venta",
)
def registrar_venta(
    data: VentaCreate,
    db: Annotated[Session, Depends(get_db)],
    _: CurrentUser,
) -> VentaDetalleResponse:
    """
    Registra una venta.

    - Toma el precio de venta vigente de cada producto (no se confía en el cliente).
    - Aplica descuento (monto o porcentaje) y calcula el total.
    - Genera el número de boleta (B001-000001, ...).
    - Descuenta el stock y recalcula el estado de cada producto.

    Errores: **400** stock insuficiente o venta inválida, **404** producto
    inexistente.
    """
    venta = VentaService(db).registrar_venta(data)
    return VentaDetalleResponse.from_venta(venta)


@router.post(
    "/{venta_id}/abonos",
    response_model=AbonoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar un abono (pago parcial) sobre una venta al crédito",
)
def registrar_abono(
    venta_id: int,
    data: AbonoCreate,
    db: Annotated[Session, Depends(get_db)],
    _: CurrentUser,
) -> AbonoResponse:
    """
    Registra un abono sobre una venta al crédito y reduce su saldo pendiente.

    - **400** si la venta es al contado o el monto supera el saldo.
    - **404** si la venta no existe.
    """
    return CreditoService(db).registrar_abono(venta_id, data)


@router.get(
    "/{venta_id}/boleta",
    summary="Generar y descargar la boleta PDF de una venta",
    responses={
        200: {"content": {"application/pdf": {}}, "description": "Boleta en PDF"},
        404: {"description": "Venta no encontrada o boleta no disponible"},
    },
)
def descargar_boleta(
    venta_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: CurrentUser,
) -> Response:
    """
    Genera la boleta de la venta y la devuelve como PDF descargable.

    El header `Content-Disposition` incluye el nombre del archivo
    (p. ej. `boleta_B001-000001.pdf`).

    Errores: **404** "Venta no encontrada" o "Boleta no disponible".
    """
    pdf_bytes, filename = VentaService(db).generate_boleta(venta_id)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )
