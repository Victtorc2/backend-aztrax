"""
Rutas del módulo de rentabilidad (reportes de ganancia).

Endpoint (protegido con JWT):
    GET /rentabilidad -> reporte por producto + por periodo + resumen

Parámetros opcionales: rango de fechas (desde/hasta) y agrupación (dia/mes).
"""

from datetime import date
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import CurrentUser, get_current_user
from app.schemas.rentabilidad import ReporteRentabilidad
from app.services.rentabilidad_service import RentabilidadService

router = APIRouter(
    prefix="/rentabilidad",
    tags=["Rentabilidad"],
    dependencies=[Depends(get_current_user)],
)


@router.get(
    "",
    response_model=ReporteRentabilidad,
    summary="Reporte de rentabilidad (por producto y por periodo)",
)
def obtener_rentabilidad(
    db: Annotated[Session, Depends(get_db)],
    _: CurrentUser,
    desde: Annotated[
        Optional[date], Query(description="Fecha inicial (YYYY-MM-DD)")
    ] = None,
    hasta: Annotated[
        Optional[date], Query(description="Fecha final (YYYY-MM-DD)")
    ] = None,
    agrupar: Annotated[
        str, Query(description="Agrupación de la serie: 'dia' o 'mes'")
    ] = "dia",
) -> ReporteRentabilidad:
    """
    Devuelve el reporte de rentabilidad:

    - **resumen**: ingresos, costo, ganancia y margen % globales.
    - **por_producto**: cuánto se ganó en cada artículo (ordenado por ganancia).
    - **por_periodo**: ganancia agrupada por día o por mes.

    La ganancia se calcula con el costo congelado en cada venta, por lo que es
    fiel aunque el precio de compra del producto cambie luego.
    """
    return RentabilidadService(db).reporte(desde=desde, hasta=hasta, agrupar=agrupar)
