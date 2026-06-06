"""
Rutas del módulo de historial (Fase 11).

Endpoints (protegidos con JWT):
    GET /historial              -> listado paginado con filtros
    GET /historial/{id}         -> detalle de una venta
    GET /historial/{id}/boleta  -> reimprimir boleta (reutiliza Fase 10)

Filtros del listado: ?fecha=, ?fecha_inicio= & ?fecha_fin=, ?boleta=,
?page=, ?page_size=.

IMPORTANTE: la ruta estática no aplica aquí porque /historial/{id} y
/historial/{id}/boleta no colisionan con el listado; aun así, FastAPI evalúa
en orden y todo queda bien definido.
"""

from datetime import date
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import CurrentUser, get_current_user
from app.schemas.venta import (
    HistorialPaginado,
    HistorialResponse,
    VentaDetalleResponse,
)
from app.services.venta_service import VentaService

router = APIRouter(
    prefix="/historial",
    tags=["Historial de ventas"],
    dependencies=[Depends(get_current_user)],
)


@router.get(
    "",
    response_model=HistorialPaginado,
    status_code=status.HTTP_200_OK,
    summary="Listar el historial de ventas (paginado, con filtros)",
)
def listar_historial(
    db: Annotated[Session, Depends(get_db)],
    _: CurrentUser,
    fecha: Annotated[
        Optional[date], Query(description="Fecha exacta (YYYY-MM-DD)")
    ] = None,
    fecha_inicio: Annotated[
        Optional[date], Query(description="Inicio de rango (YYYY-MM-DD)")
    ] = None,
    fecha_fin: Annotated[
        Optional[date], Query(description="Fin de rango (YYYY-MM-DD)")
    ] = None,
    boleta: Annotated[
        Optional[str], Query(description="Búsqueda parcial por número de boleta")
    ] = None,
    page: Annotated[int, Query(ge=1, description="Número de página")] = 1,
    page_size: Annotated[
        int, Query(ge=1, le=100, description="Tamaño de página")
    ] = 20,
) -> HistorialPaginado:
    """
    Lista las ventas más recientes (orden descendente) con paginación.

    Filtros combinables:
    - `?fecha=2026-05-25` (día exacto)
    - `?fecha_inicio=2026-05-01&fecha_fin=2026-05-20` (rango)
    - `?boleta=B001` (coincidencia parcial)

    FastAPI valida automáticamente el formato de fecha (422 si es inválido).
    """
    ventas, total, page, page_size = VentaService(db).listar_historial(
        page=page,
        page_size=page_size,
        boleta=boleta,
        fecha=fecha,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
    )
    return HistorialPaginado(
        total=total,
        page=page,
        page_size=page_size,
        items=[HistorialResponse.from_venta(v) for v in ventas],
    )


@router.get(
    "/{venta_id}",
    response_model=VentaDetalleResponse,
    status_code=status.HTTP_200_OK,
    summary="Obtener el detalle de una venta del historial",
)
def detalle_historial(
    venta_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: CurrentUser,
) -> VentaDetalleResponse:
    """
    Devuelve los datos completos de una venta: cabecera, totales, descuento y
    el detalle de productos.

    Responde **404** "Venta no encontrada" si no existe.
    """
    venta = VentaService(db).obtener_detalle(venta_id)
    return VentaDetalleResponse.from_venta(venta)


@router.get(
    "/{venta_id}/boleta",
    summary="Reimprimir la boleta PDF de una venta del historial",
    responses={
        200: {"content": {"application/pdf": {}}, "description": "Boleta en PDF"},
        404: {"description": "Venta no encontrada o boleta no disponible"},
    },
)
def reimprimir_boleta(
    venta_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: CurrentUser,
) -> Response:
    """
    Reimprime la boleta de una venta. **Reutiliza** `generate_boleta()` del
    servicio (no duplica la lógica de generación de PDF).

    Errores: **404** "Venta no encontrada" o "Boleta no disponible".
    """
    pdf_bytes, filename = VentaService(db).generate_boleta(venta_id)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )
