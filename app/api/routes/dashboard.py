"""
Rutas del módulo de dashboard (métricas e indicadores).

Endpoints (protegidos con JWT):
    GET /dashboard           -> resumen + series + top + métodos de pago
    GET /dashboard/resumen   -> solo las tarjetas KPI (respuesta ligera)

Pensados para alimentar el panel de inicio del frontend.
"""

from datetime import date, timedelta
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import CurrentUser, get_current_user
from app.schemas.dashboard import DashboardCompleto, ResumenDashboard, VentaPorDia, VentasProductoPaginado
from app.services.dashboard_service import DashboardService

router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/ventas-por-producto", response_model=VentasProductoPaginado)
def buscar_ventas_producto(
    db: Annotated[Session, Depends(get_db)],
    _: CurrentUser,
    q: str = Query(default="", max_length=150),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> VentasProductoPaginado:
    """Busca productos y cuenta boletas distintas y unidades; excluye anuladas."""
    return DashboardService(db).buscar_ventas_producto(q, page, page_size)


@router.get(
    "",
    response_model=DashboardCompleto,
    summary="Métricas completas del dashboard",
)
def obtener_dashboard(
    db: Annotated[Session, Depends(get_db)],
    _: CurrentUser,
    mes: str | None = Query(
        default=None, pattern=r"^(?:[1-8][0-9]{3}|9[0-9]{2}[0-8])-(0[1-9]|1[0-2])$",
        description="Mes YYYY-MM (hora de Perú); filtra totales, gráfico y ranking",
    ),
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
    return DashboardService(db).completo(dias=dias, top=top, mes=mes)


@router.get(
    "/ventas-por-dia",
    response_model=list[VentaPorDia],
    summary="Serie de ventas por día en un rango de fechas",
)
def obtener_ventas_por_dia(
    db: Annotated[Session, Depends(get_db)],
    _: CurrentUser,
    desde: Annotated[
        Optional[date], Query(description="Fecha inicial (YYYY-MM-DD)")
    ] = None,
    hasta: Annotated[
        Optional[date], Query(description="Fecha final (YYYY-MM-DD)")
    ] = None,
    dias: int = Query(
        default=30,
        ge=1,
        le=365,
        description="Tamaño de la ventana si no se indica 'desde'",
    ),
) -> list[VentaPorDia]:
    """
    Serie continua de ventas por día para graficar, con navegación temporal.

    Si se indican `desde`/`hasta` se usa ese rango; si faltan, se asume una
    ventana de `dias` que termina en `hasta` (o en hoy). Los días sin ventas
    se rellenan con cero para mantener la serie continua.
    """
    hasta_real = hasta or date.today()
    desde_real = desde or (hasta_real - timedelta(days=dias - 1))
    return DashboardService(db).ventas_por_dia(desde_real, hasta_real)


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
