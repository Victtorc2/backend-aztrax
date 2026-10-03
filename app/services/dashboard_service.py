"""
Servicio del dashboard.

Calcula las métricas del panel mediante agregaciones SQL (SUM, COUNT, GROUP BY)
en lugar de cargar filas en memoria, para que rinda bien aunque crezca el
volumen de ventas. No conoce FastAPI: solo recibe una Session y devuelve
objetos de esquema.

Las fechas se manejan con límites de día completo para evitar problemas de
zona horaria al comparar columnas DateTime.
"""

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, or_, select
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
    VentasProducto,
    VentasProductoPaginado,
)
from app.utils.productos import EstadoProducto

_LIMA = timezone(timedelta(hours=-5))

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
    def _resumen(self, periodo=None) -> ResumenDashboard:
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
            select(func.count()).select_from(Venta).where(Venta.anulada.is_(False), *self._filtro(periodo))
        ) or 0
        monto_total = db.scalar(
            select(func.coalesce(func.sum(Venta.total), 0)).where(
                Venta.anulada.is_(False), *self._filtro(periodo)
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
    def _ventas_por_dia(self, dias: int, periodo=None) -> list[VentaPorDia]:
        """
        Ventas agrupadas por día en los últimos `dias` días (incluido hoy).

        Atajo sobre `_ventas_por_dia_rango` para la ventana que termina hoy.
        """
        if periodo:
            desde = periodo[0].astimezone(_LIMA).date()
            hasta = periodo[1].astimezone(_LIMA).date() - timedelta(days=1)
            return self._ventas_por_dia_rango(desde, hasta, periodo)
        dias = max(1, min(dias, self.MAX_DIAS))
        hoy = date.today()
        return self._ventas_por_dia_rango(hoy - timedelta(days=dias - 1), hoy)

    def _ventas_por_dia_rango(self, desde: date, hasta: date, periodo=None) -> list[VentaPorDia]:
        """
        Ventas agrupadas por día en el rango [desde, hasta] (ambos inclusive).

        Se rellenan con cero los días sin ventas para que la serie sea continua
        (mejor para graficar). El agrupado por fecha se hace en Python sobre las
        filas del rango, que está acotado por MAX_DIAS. Permite navegar hacia
        meses anteriores desplazando la ventana con flechas en el frontend.
        """
        # Normalizar orden y acotar la amplitud a MAX_DIAS.
        if hasta < desde:
            desde, hasta = hasta, desde
        span = (hasta - desde).days + 1
        if span > self.MAX_DIAS:
            desde = hasta - timedelta(days=self.MAX_DIAS - 1)
            span = self.MAX_DIAS

        inicio = datetime.combine(desde, time.min)
        fin = datetime.combine(hasta, time.max)

        if periodo:
            desde = periodo[0].astimezone(_LIMA).date()
            inicio = periodo[0]

        filas = self.db.execute(
            select(Venta.fecha, Venta.total).where(
                Venta.fecha >= inicio,
                Venta.fecha < periodo[1] if periodo else Venta.fecha <= fin,
                Venta.anulada.is_(False),
            )
        ).all()

        # Acumular por día.
        acum: dict[date, dict] = {}
        for fecha_dt, total in filas:
            if periodo:
                fecha_dt = fecha_dt.replace(tzinfo=timezone.utc) if fecha_dt.tzinfo is None else fecha_dt
                fecha_dt = fecha_dt.astimezone(_LIMA)
            d = fecha_dt.date()
            slot = acum.setdefault(d, {"cantidad": 0, "monto": _CERO})
            slot["cantidad"] += 1
            slot["monto"] += Decimal(total)

        # Construir la serie continua día a día.
        serie: list[VentaPorDia] = []
        for i in range(span):
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
    def _top_productos(self, limite: int, periodo=None) -> list[TopProducto]:
        """Ranking de productos por unidades vendidas (todas las ventas)."""
        limite = max(1, min(limite, 50))
        stmt = (
            select(
                Producto.id,
                Producto.codigo,
                Producto.nombre,
                Producto.marca,
                Producto.modelo,
                Producto.color,
                func.sum(DetalleVenta.cantidad).label("unidades"),
                func.sum(DetalleVenta.subtotal).label("monto"),
            )
            .join(DetalleVenta, DetalleVenta.producto_id == Producto.id)
            .join(Venta, Venta.id == DetalleVenta.venta_id)
            .where(Venta.anulada.is_(False), *self._filtro(periodo))
            .group_by(
                Producto.id, Producto.codigo, Producto.nombre, Producto.marca,
                Producto.modelo, Producto.color,
            )
            .order_by(func.sum(DetalleVenta.cantidad).desc(), Producto.id)
            .limit(limite)
        )
        filas = self.db.execute(stmt).all()
        return [
            TopProducto(
                producto_id=row.id,
                codigo=row.codigo,
                nombre=row.nombre,
                marca=row.marca,
                modelo=row.modelo,
                color=row.color,
                unidades_vendidas=int(row.unidades or 0),
                monto_vendido=_money(row.monto),
            )
            for row in filas
        ]

    # ------------------------------------------------------------------
    # Desglose por método de pago
    # ------------------------------------------------------------------
    def _metodos_pago(self, periodo=None) -> list[MetodoPagoResumen]:
        """Cantidad de ventas y monto por método de pago."""
        stmt = (
            select(
                Venta.metodo_pago,
                func.count().label("cantidad"),
                func.coalesce(func.sum(Venta.total), 0).label("monto"),
            )
            .where(Venta.anulada.is_(False), *self._filtro(periodo))
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

    def buscar_ventas_producto(self, q: str, page: int, page_size: int) -> VentasProductoPaginado:
        """Conteo histórico por producto, incluyendo inactivos y productos sin ventas."""
        filtros = []
        for palabra in q.split():
            literal = palabra.replace("/", "//").replace("%", "/%").replace("_", "/_")
            filtros.append(or_(*(
                campo.ilike(f"%{literal}%", escape="/")
                for campo in (Producto.nombre, Producto.codigo, Producto.marca, Producto.modelo, Producto.color)
            )))
        total = self.db.scalar(select(func.count(Producto.id)).where(*filtros)) or 0
        productos = self.db.scalars(
            select(Producto).where(*filtros).order_by(Producto.nombre, Producto.id)
            .offset((page - 1) * page_size).limit(page_size)
        ).all()
        conteos = {}
        if productos:
            filas = self.db.execute(
                select(
                    DetalleVenta.producto_id,
                    func.count(func.distinct(DetalleVenta.venta_id)),
                    func.sum(DetalleVenta.cantidad),
                )
                .join(Venta, Venta.id == DetalleVenta.venta_id)
                .where(Venta.anulada.is_(False), DetalleVenta.producto_id.in_([p.id for p in productos]))
                .group_by(DetalleVenta.producto_id)
            ).all()
            conteos = {pid: (int(veces), int(unidades)) for pid, veces, unidades in filas}
        return VentasProductoPaginado(
            total=total, page=page, page_size=page_size,
            items=[VentasProducto(
                producto_id=p.id, codigo=p.codigo, nombre=p.nombre, marca=p.marca,
                modelo=p.modelo, color=p.color, activo=p.is_active,
                veces_vendido=conteos.get(p.id, (0, 0))[0],
                unidades_vendidas=conteos.get(p.id, (0, 0))[1],
            ) for p in productos],
        )

    def ventas_por_dia(self, desde: date, hasta: date) -> list[VentaPorDia]:
        """Serie de ventas por día en un rango arbitrario (para el gráfico)."""
        return self._ventas_por_dia_rango(desde, hasta)

    @staticmethod
    def _filtro(periodo):
        return (Venta.fecha >= periodo[0], Venta.fecha < periodo[1]) if periodo else ()

    def completo(self, dias: int = 14, top: int = 5, mes: str | None = None) -> DashboardCompleto:
        """Agrega todas las secciones del dashboard en una sola respuesta."""
        periodo = None
        if mes:
            anio, numero = map(int, mes.split("-"))
            inicio = datetime(anio, numero, 1, tzinfo=_LIMA)
            fin = datetime(anio + (numero == 12), numero % 12 + 1, 1, tzinfo=_LIMA)
            periodo = (inicio.astimezone(timezone.utc), fin.astimezone(timezone.utc))
        return DashboardCompleto(
            resumen=self._resumen(periodo),
            ventas_por_dia=self._ventas_por_dia(dias, periodo),
            top_productos=self._top_productos(top, periodo),
            metodos_pago=self._metodos_pago(periodo),
        )
