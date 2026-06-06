"""
Rutas del módulo de dashboard (métricas e indicadores).

Endpoints (protegidos con JWT):
    GET /dashboard           -> resumen + series + top + métodos de pago
    GET /dashboard/resumen   -> solo las tarjetas KPI (respuesta ligera)

Pensados para alimentar el panel de inicio del frontend.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import CurrentUser, get_current_user
from app.schemas.dashboard import DashboardCompleto, ResumenDashboard
from app.services.dashboard_service import DashboardService

router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"],
    dependencies=[Depends(get_current_user)],
)


@router.get(
    "",
    response_model=DashboardCompleto,
    summary="Métricas completas del dashboard",
)
def obtener_dashboard(
    db: Annotated[Session, Depends(get_db)],
    _: CurrentUser,
    dias: int = Query(
        default=14, ge=1, le=365, description="Días de la serie de ventas"
    ),
    top: int = Query(
        default=5, ge=1, le=50, description="Nº de productos en el ranking"
    ),
) -> DashboardCompleto:
    """
    Devuelve todo lo necesario para pintar el dashboard:

    - **resumen**: KPIs de ventas, inventario y catálogo.
    - **ventas_por_dia**: serie temporal continua (para gráficos).
    - **top_productos**: ranking por unidades vendidas.
    - **metodos_pago**: desglose efectivo / yape.
    """
    return DashboardService(db).completo(dias=dias, top=top)


@router.get(
    "/resumen",
    response_model=ResumenDashboard,
    summary="Solo las tarjetas KPI (respuesta ligera)",
)
def obtener_resumen(
    db: Annotated[Session, Depends(get_db)],
    _: CurrentUser,
) -> ResumenDashboard:
    """Versión ligera: solo los indicadores rápidos (sin series ni rankings)."""
    return DashboardService(db).resumen()
