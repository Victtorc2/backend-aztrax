"""
Repositorio de clientes.

Encapsula el acceso a datos de la tabla `clientes`, incluyendo el cálculo de
la deuda total de cada cliente (suma de saldos pendientes de sus ventas al
crédito) mediante una agregación SQL, sin cargar las ventas en memoria.
"""

from decimal import Decimal
from typing import Any, Optional, Sequence

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.cliente import Cliente
from app.models.venta import Venta

_CERO = Decimal("0.00")


class ClienteRepository:
    """Acceso a datos para la entidad Cliente."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Lectura
    # ------------------------------------------------------------------
    def get_all(self, solo_activos: bool = True) -> Sequence[Cliente]:
        stmt = select(Cliente)
        if solo_activos:
            stmt = stmt.where(Cliente.is_active.is_(True))
        stmt = stmt.order_by(Cliente.nombre.asc(), Cliente.id.desc())
        return self.db.scalars(stmt).all()

    def get_by_id(self, cliente_id: int) -> Optional[Cliente]:
        return self.db.get(Cliente, cliente_id)

    def search(self, termino: str, solo_activos: bool = True) -> Sequence[Cliente]:
        """Busca por nombre, documento o teléfono (coincidencia parcial)."""
        patron = f"%{termino.strip().lower()}%"
        stmt = select(Cliente).where(
            or_(
                func.lower(Cliente.nombre).like(patron),
                func.lower(Cliente.documento).like(patron),
                func.lower(Cliente.telefono).like(patron),
            )
        )
        if solo_activos:
            stmt = stmt.where(Cliente.is_active.is_(True))
        stmt = stmt.order_by(Cliente.nombre.asc(), Cliente.id.desc())
        return self.db.scalars(stmt).all()

    def exists_by_documento(
        self, documento: str, exclude_id: Optional[int] = None
    ) -> bool:
        stmt = select(Cliente.id).where(Cliente.documento == documento.strip())
        if exclude_id is not None:
            stmt = stmt.where(Cliente.id != exclude_id)
        return self.db.scalar(stmt) is not None

    def get_by_documento(self, documento: str) -> Optional[Cliente]:
        """Devuelve el cliente con ese documento, o None."""
        stmt = select(Cliente).where(Cliente.documento == documento.strip())
        return self.db.scalars(stmt).first()

    def deuda_total(self, cliente_id: int) -> Decimal:
        """Suma de saldos pendientes de las ventas al crédito del cliente."""
        total = self.db.scalar(
            select(func.coalesce(func.sum(Venta.saldo_pendiente), 0)).where(
                Venta.cliente_id == cliente_id
            )
        )
        return Decimal(total or 0).quantize(Decimal("0.01"))

    def deudas_por_cliente(self) -> dict[int, Decimal]:
        """
        Devuelve {cliente_id: deuda_total} para todos los clientes con saldo,
        en una sola consulta agregada (evita N+1 al listar).
        """
        filas = self.db.execute(
            select(
                Venta.cliente_id,
                func.coalesce(func.sum(Venta.saldo_pendiente), 0),
            )
            .where(Venta.cliente_id.is_not(None))
            .group_by(Venta.cliente_id)
        ).all()
        return {
            cid: Decimal(total or 0).quantize(Decimal("0.01"))
            for cid, total in filas
        }

    # ------------------------------------------------------------------
    # Escritura
    # ------------------------------------------------------------------
    def create_cliente(self, **campos: Any) -> Cliente:
        cliente = Cliente(**campos)
        self.db.add(cliente)
        self.db.commit()
        self.db.refresh(cliente)
        return cliente

    def update(self, cliente: Cliente, cambios: dict[str, Any]) -> Cliente:
        for campo, valor in cambios.items():
            setattr(cliente, campo, valor)
        self.db.commit()
        self.db.refresh(cliente)
        return cliente

    def deactivate(self, cliente: Cliente) -> None:
        """Baja lógica: nunca borramos un cliente con historial."""
        cliente.is_active = False
        self.db.commit()
