"""
Servicio del dashboard.

Calcula las métricas del panel mediante agregaciones SQL (SUM, COUNT, GROUP BY)
en lugar de cargar filas en memoria, para que rinda bien aunque crezca el
volumen de ventas. No conoce FastAPI: solo recibe una Session y devuelve
objetos de esquema.

Las fechas se manejan con límites de día completo para evitar problemas de
zona horaria al comparar columnas DateTime.
"""

from datetime import date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.categoria import Categoria
from app.models.producto import Producto
from app.models.proveedor import Proveedor
from app.models.venta import DetalleVenta, Venta
from app.schemas.dashboard import (
    DashboardCompleto,
    MetodoPagoResumen,
    ResumenDashboard,
    TopProducto,
    VentaPorDia,
)
from app.utils.productos import EstadoProducto

_CERO = Decimal("0.00")


def _money(value) -> Decimal:
    """Normaliza un valor (posible None) a Decimal con 2 decimales."""
    if value is None:
        return _CERO
    return Decimal(value).quantize(Decimal("0.01"))


class DashboardService:
    """Calcula los indicadores y series del dashboard."""

    # Tope defensivo para la serie temporal (evita rangos absurdos).
    MAX_DIAS = 365

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Resumen (tarjetas KPI)
    # ------------------------------------------------------------------
    def _resumen(self) -> ResumenDashboard:
        db = self.db
        hoy = date.today()
        inicio = datetime.combine(hoy, time.min)
        fin = datetime.combine(hoy, time.max)

        # Ventas de hoy (excluye anuladas).
        ventas_hoy = db.scalar(
            select(func.count())
            .select_from(Venta)
            .where(Venta.fecha.between(inicio, fin), Venta.anulada.is_(False))
        ) or 0
        monto_hoy = db.scalar(
            select(func.coalesce(func.sum(Venta.total), 0)).where(
                Venta.fecha.between(inicio, fin), Venta.anulada.is_(False)
            )
        )

        # Totales históricos (excluyen anuladas).
        ventas_total = db.scalar(
            select(func.count()).select_from(Venta).where(Venta.anulada.is_(False))
        ) or 0
        monto_total = db.scalar(
            select(func.coalesce(func.sum(Venta.total), 0)).where(
                Venta.anulada.is_(False)
            )
        )

        monto_total_dec = _money(monto_total)
        ticket_promedio = (
            (monto_total_dec / ventas_total).quantize(Decimal("0.01"))
            if ventas_total
            else _CERO
        )

        # Inventario (solo productos activos).
        activos_base = select(func.count()).select_from(Producto).where(
            Producto.is_active.is_(True)
        )
        productos_activos = db.scalar(activos_base) or 0
        productos_agotados = db.scalar(
            activos_base.where(Producto.estado == EstadoProducto.AGOTADO.value)
        ) or 0
        productos_bajo_stock = db.scalar(
            activos_base.where(Producto.estado == EstadoProducto.BAJO_STOCK.value)
        ) or 0

        # Valor del inventario: SUM(precio_venta * stock) de productos activos.
        valor_inventario = db.scalar(
            select(
                func.coalesce(func.sum(Producto.precio_venta * Producto.stock), 0)
            ).where(Producto.is_active.is_(True))
        )

        total_categorias = db.scalar(select(func.count()).select_from(Categoria)) or 0
        total_proveedores = db.scalar(select(func.count()).select_from(Proveedor)) or 0

        return ResumenDashboard(
            ventas_hoy=ventas_hoy,
            monto_hoy=_money(monto_hoy),
            ventas_total=ventas_total,
            monto_total=monto_total_dec,
            ticket_promedio=ticket_promedio,
            productos_activos=productos_activos,
            productos_agotados=productos_agotados,
            productos_bajo_stock=productos_bajo_stock,
            valor_inventario=_money(valor_inventario),
            total_categorias=total_categorias,
            total_proveedores=total_proveedores,
        )

    # ------------------------------------------------------------------
    # Serie temporal: ventas por día
    # ------------------------------------------------------------------
    def _ventas_por_dia(self, dias: int) -> list[VentaPorDia]:
        """
        Ventas agrupadas por día en los últimos `dias` días (incluido hoy).

        Se rellenan con cero los días sin ventas para que la serie sea continua
        (mejor para graficar). El agrupado por fecha se hace en Python sobre las
        filas del rango, que está acotado por MAX_DIAS.
        """
        dias = max(1, min(dias, self.MAX_DIAS))
        hoy = date.today()
        desde = hoy - timedelta(days=dias - 1)
        inicio = datetime.combine(desde, time.min)

        filas = self.db.execute(
            select(Venta.fecha, Venta.total).where(
                Venta.fecha >= inicio, Venta.anulada.is_(False)
            )
        ).all()

        # Acumular por día.
        acum: dict[date, dict] = {}
        for fecha_dt, total in filas:
            d = fecha_dt.date()
            slot = acum.setdefault(d, {"cantidad": 0, "monto": _CERO})
            slot["cantidad"] += 1
            slot["monto"] += Decimal(total)

        # Construir la serie continua día a día.
        serie: list[VentaPorDia] = []
        for i in range(dias):
            d = desde + timedelta(days=i)
            slot = acum.get(d, {"cantidad": 0, "monto": _CERO})
            serie.append(
                VentaPorDia(
                    fecha=d,
                    cantidad=slot["cantidad"],
                    monto=_money(slot["monto"]),
                )
            )
        return serie

    # ------------------------------------------------------------------
    # Top productos más vendidos
    # ------------------------------------------------------------------
    def _top_productos(self, limite: int) -> list[TopProducto]:
        """Ranking de productos por unidades vendidas (todas las ventas)."""
        limite = max(1, min(limite, 50))
        stmt = (
            select(
                Producto.id,
                Producto.codigo,
                Producto.nombre,
                Producto.marca,
                func.sum(DetalleVenta.cantidad).label("unidades"),
                func.sum(DetalleVenta.subtotal).label("monto"),
            )
            .join(DetalleVenta, DetalleVenta.producto_id == Producto.id)
            .join(Venta, Venta.id == DetalleVenta.venta_id)
            .where(Venta.anulada.is_(False))
            .group_by(Producto.id, Producto.codigo, Producto.nombre, Producto.marca)
            .order_by(func.sum(DetalleVenta.cantidad).desc())
            .limit(limite)
        )
        filas = self.db.execute(stmt).all()
        return [
            TopProducto(
                producto_id=row.id,
                codigo=row.codigo,
                nombre=row.nombre,
                marca=row.marca,
                unidades_vendidas=int(row.unidades or 0),
                monto_vendido=_money(row.monto),
            )
            for row in filas
        ]

    # ------------------------------------------------------------------
    # Desglose por método de pago
    # ------------------------------------------------------------------
    def _metodos_pago(self) -> list[MetodoPagoResumen]:
        """Cantidad de ventas y monto por método de pago."""
        stmt = (
            select(
                Venta.metodo_pago,
                func.count().label("cantidad"),
                func.coalesce(func.sum(Venta.total), 0).label("monto"),
            )
            .where(Venta.anulada.is_(False))
            .group_by(Venta.metodo_pago)
            .order_by(func.sum(Venta.total).desc())
        )
        filas = self.db.execute(stmt).all()
        return [
            MetodoPagoResumen(
                metodo_pago=row.metodo_pago or "efectivo",
                cantidad=int(row.cantidad or 0),
                monto=_money(row.monto),
            )
            for row in filas
        ]

    # ------------------------------------------------------------------
    # API pública del servicio
    # ------------------------------------------------------------------
    def resumen(self) -> ResumenDashboard:
        return self._resumen()

    def completo(self, dias: int = 14, top: int = 5) -> DashboardCompleto:
        """Agrega todas las secciones del dashboard en una sola respuesta."""
        return DashboardCompleto(
            resumen=self._resumen(),
            ventas_por_dia=self._ventas_por_dia(dias),
            top_productos=self._top_productos(top),
            metodos_pago=self._metodos_pago(),
        )
