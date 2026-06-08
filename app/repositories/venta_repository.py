"""
Repositorio de ventas.

Encapsula el acceso a datos de `ventas` y `detalle_venta`. Incluye:
- Generación del correlativo de boleta (SERIE-000001).
- Consultas del historial con filtros y paginación.
- Carga optimizada de relaciones (selectinload de detalles, joined del
  producto) para evitar N+1 al construir boletas e historial.
"""

from datetime import date, datetime, time
from decimal import Decimal
from typing import Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.models.producto import Producto
from app.models.venta import DetalleVenta, Venta


class VentaRepository:
    """Acceso a datos para ventas e historial."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Numeración de boleta
    # ------------------------------------------------------------------
    def next_numero_boleta(self) -> str:
        """
        Genera el siguiente número de boleta con formato SERIE-000001.

        Toma el correlativo más alto existente para la serie configurada y le
        suma 1. La restricción UNIQUE sobre `numero_boleta` es la red final.
        """
        serie = settings.BOLETA_SERIE
        ultimo = self.db.scalar(
            select(Venta.numero_boleta)
            .where(Venta.numero_boleta.like(f"{serie}-%"))
            .order_by(Venta.id.desc())
            .limit(1)
        )
        if ultimo is None:
            correlativo = 1
        else:
            # "B001-000007" -> 7 -> 8
            correlativo = int(ultimo.split("-")[1]) + 1
        return f"{serie}-{correlativo:06d}"

    # ------------------------------------------------------------------
    # Escritura
    # ------------------------------------------------------------------
    def create_venta(
        self,
        numero_boleta: str,
        subtotal: Decimal,
        descuento: Decimal,
        descuento_tipo: Optional[str],
        total: Decimal,
        detalles: list[dict],
        metodo_pago: str = "efectivo",
        tipo_pago: str = "contado",
        cliente_id: Optional[int] = None,
        saldo_pendiente: Decimal = Decimal("0.00"),
    ) -> Venta:
        """
        Crea una venta junto con sus líneas de detalle.

        `detalles` es una lista de dicts con: producto_id, cantidad, precio,
        costo_unitario, subtotal. La venta y sus detalles se persisten en una
        sola transacción.

        Para ventas al crédito: `tipo_pago="credito"`, `cliente_id` con el
        cliente y `saldo_pendiente` igual al total (la deuda inicial).
        """
        venta = Venta(
            numero_boleta=numero_boleta,
            subtotal=subtotal,
            descuento=descuento,
            descuento_tipo=descuento_tipo,
            metodo_pago=metodo_pago,
            tipo_pago=tipo_pago,
            cliente_id=cliente_id,
            saldo_pendiente=saldo_pendiente,
            total=total,
            detalles=[
                DetalleVenta(
                    producto_id=d.get("producto_id"),
                    descripcion_libre=d.get("descripcion_libre"),
                    cantidad=d["cantidad"],
                    precio=d["precio"],
                    costo_unitario=d.get("costo_unitario", Decimal("0.00")),
                    subtotal=d["subtotal"],
                )
                for d in detalles
            ],
        )
        self.db.add(venta)
        self.db.commit()
        return self.get_by_id(venta.id)  # type: ignore[return-value]

    def get_creditos_by_cliente(self, cliente_id: int) -> Sequence[Venta]:
        """
        Devuelve las ventas al crédito de un cliente (con sus abonos),
        ordenadas por fecha. Incluye saldadas y pendientes para el estado
        de cuenta completo.
        """
        stmt = (
            select(Venta)
            .where(Venta.cliente_id == cliente_id, Venta.tipo_pago == "credito")
            .order_by(Venta.fecha.desc(), Venta.id.desc())
        )
        return self.db.scalars(stmt).unique().all()

    # ------------------------------------------------------------------
    # Lectura
    # ------------------------------------------------------------------
    def _base_select(self):
        """
        SELECT base de ventas con carga optimizada:
        - selectinload de detalles (una consulta extra, no N).
        - joined del producto dentro de cada detalle (definido en el modelo).
        """
        return select(Venta).options(
            selectinload(Venta.detalles).joinedload(DetalleVenta.producto)
        )

    def get_by_id(self, venta_id: int) -> Optional[Venta]:
        """Devuelve una venta por id con detalles y productos cargados."""
        stmt = self._base_select().where(Venta.id == venta_id)
        return self.db.scalar(stmt)

    def get_historial(
        self,
        page: int,
        page_size: int,
        boleta: Optional[str] = None,
        fecha: Optional[date] = None,
        fecha_inicio: Optional[date] = None,
        fecha_fin: Optional[date] = None,
    ) -> tuple[Sequence[Venta], int]:
        """
        Lista paginada del historial con filtros combinables.

        Filtros:
            boleta: coincidencia parcial por número de boleta.
            fecha: fecha exacta (día completo).
            fecha_inicio / fecha_fin: rango de fechas inclusivo.

        Returns:
            (lista_de_ventas_de_la_pagina, total_de_ventas_que_cumplen_filtro)
        """
        stmt = self._base_select()
        count_stmt = select(func.count()).select_from(Venta)

        # Construimos las condiciones una vez y las aplicamos a ambos selects.
        condiciones = []
        if boleta and boleta.strip():
            condiciones.append(Venta.numero_boleta.ilike(f"%{boleta.strip()}%"))
        if fecha is not None:
            # Día completo [00:00:00, 23:59:59.999999].
            inicio = datetime.combine(fecha, time.min)
            fin = datetime.combine(fecha, time.max)
            condiciones.append(Venta.fecha.between(inicio, fin))
        if fecha_inicio is not None:
            condiciones.append(Venta.fecha >= datetime.combine(fecha_inicio, time.min))
        if fecha_fin is not None:
            condiciones.append(Venta.fecha <= datetime.combine(fecha_fin, time.max))

        for c in condiciones:
            stmt = stmt.where(c)
            count_stmt = count_stmt.where(c)

        total = self.db.scalar(count_stmt) or 0

        # Orden descendente (más recientes primero) + paginación.
        stmt = (
            stmt.order_by(Venta.fecha.desc(), Venta.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        ventas = self.db.scalars(stmt).unique().all()
        return ventas, total

    def get_by_boleta(self, boleta: str) -> Sequence[Venta]:
        """Búsqueda por número de boleta (coincidencia parcial)."""
        stmt = (
            self._base_select()
            .where(Venta.numero_boleta.ilike(f"%{boleta.strip()}%"))
            .order_by(Venta.fecha.desc(), Venta.id.desc())
        )
        return self.db.scalars(stmt).unique().all()

    def get_by_fecha(self, fecha: date) -> Sequence[Venta]:
        """Búsqueda por fecha exacta (día completo)."""
        inicio = datetime.combine(fecha, time.min)
        fin = datetime.combine(fecha, time.max)
        stmt = (
            self._base_select()
            .where(Venta.fecha.between(inicio, fin))
            .order_by(Venta.fecha.desc(), Venta.id.desc())
        )
        return self.db.scalars(stmt).unique().all()
