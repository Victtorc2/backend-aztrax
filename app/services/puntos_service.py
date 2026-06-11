"""
Servicio de fidelización (puntos).

Reglas:
- Al registrar una venta asociada a un cliente se otorgan puntos:
      puntos = total_de_la_venta // PUNTOS_SOLES_POR_PUNTO
  (parte entera; una compra de S/ 55 con tasa 10 da 5 puntos).
- Al anular una venta se revierten los puntos que otorgó.
- El cliente puede canjear puntos (se descuentan de su saldo).

El saldo vigente se guarda en `clientes.puntos` y cada cambio queda registrado
en `movimientos_puntos` para trazabilidad. Los métodos que participan en una
venta NO hacen commit (lo hace el VentaService al cerrar la transacción); el
canje, que es una operación propia, sí confirma.
"""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import (
    CanjeInvalidoError,
    ClienteNotFoundError,
    PuntosInsuficientesError,
)
from app.models.puntos import MovimientoPuntos
from app.repositories.cliente_repository import ClienteRepository
from app.schemas.puntos import (
    CanjeCreate,
    MovimientoPuntosResponse,
    PuntosResponse,
)


class PuntosService:
    """Orquesta los casos de uso de puntos de fidelización."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.clientes = ClienteRepository(db)

    # ------------------------------------------------------------------
    # Otorgar / revertir dentro de una venta (sin commit)
    # ------------------------------------------------------------------
    def calcular_puntos(self, total: Decimal) -> int:
        """Puntos que otorga una compra de importe `total`."""
        tasa = settings.PUNTOS_SOLES_POR_PUNTO
        if tasa <= 0:
            return 0
        return int(Decimal(total) // Decimal(tasa))

    def otorgar_por_venta(self, cliente_id: int, total: Decimal, venta_id: int) -> int:
        """
        Suma al cliente los puntos de una venta y registra el movimiento.
        No hace commit (lo hace el llamador). Devuelve los puntos otorgados.
        """
        puntos = self.calcular_puntos(total)
        if puntos <= 0:
            return 0
        cliente = self.clientes.get_by_id(cliente_id)
        if cliente is None:
            return 0
        cliente.puntos = (cliente.puntos or 0) + puntos
        self.db.add(
            MovimientoPuntos(
                cliente_id=cliente_id,
                tipo="ganado",
                puntos=puntos,
                venta_id=venta_id,
                descripcion=f"Compra {venta_id}",
            )
        )
        return puntos

    def revertir_por_venta(self, cliente_id: int, venta_id: int) -> int:
        """
        Revierte los puntos otorgados por una venta (al anularla). Registra un
        movimiento negativo y no deja el saldo por debajo de cero. Sin commit.
        Devuelve los puntos revertidos (positivo).
        """
        otorgados = self.db.scalar(
            select(MovimientoPuntos.puntos).where(
                MovimientoPuntos.venta_id == venta_id,
                MovimientoPuntos.tipo == "ganado",
            )
        )
        if not otorgados:
            return 0
        cliente = self.clientes.get_by_id(cliente_id)
        if cliente is None:
            return 0
        revertir = min(int(otorgados), cliente.puntos or 0)
        if revertir <= 0:
            return 0
        cliente.puntos = (cliente.puntos or 0) - revertir
        self.db.add(
            MovimientoPuntos(
                cliente_id=cliente_id,
                tipo="revertido",
                puntos=-revertir,
                venta_id=venta_id,
                descripcion=f"Anulación venta {venta_id}",
            )
        )
        return revertir

    # ------------------------------------------------------------------
    # Canje (operación propia: confirma)
    # ------------------------------------------------------------------
    def canjear(self, cliente_id: int, data: CanjeCreate) -> PuntosResponse:
        """
        Canjea puntos del cliente (los descuenta de su saldo).

        Raises:
            ClienteNotFoundError: si el cliente no existe.
            CanjeInvalidoError: si la cantidad es <= 0.
            PuntosInsuficientesError: si no tiene suficientes puntos.
        """
        cliente = self.clientes.get_by_id(cliente_id)
        if cliente is None:
            raise ClienteNotFoundError()
        if data.puntos <= 0:
            raise CanjeInvalidoError()
        if (cliente.puntos or 0) < data.puntos:
            raise PuntosInsuficientesError(
                f"Saldo {cliente.puntos or 0}, se intentó canjear {data.puntos}"
            )

        cliente.puntos = (cliente.puntos or 0) - data.puntos
        self.db.add(
            MovimientoPuntos(
                cliente_id=cliente_id,
                tipo="canjeado",
                puntos=-data.puntos,
                venta_id=None,
                descripcion=data.descripcion or "Canje de puntos",
            )
        )
        self.db.commit()
        return self.estado(cliente_id)

    # ------------------------------------------------------------------
    # Consulta
    # ------------------------------------------------------------------
    def estado(self, cliente_id: int) -> PuntosResponse:
        """Saldo de puntos del cliente y su historial de movimientos."""
        cliente = self.clientes.get_by_id(cliente_id)
        if cliente is None:
            raise ClienteNotFoundError()

        movimientos = self.db.scalars(
            select(MovimientoPuntos)
            .where(MovimientoPuntos.cliente_id == cliente_id)
            .order_by(MovimientoPuntos.fecha.desc(), MovimientoPuntos.id.desc())
        ).all()

        return PuntosResponse(
            cliente_id=cliente.id,
            cliente_nombre=cliente.nombre,
            puntos=cliente.puntos or 0,
            movimientos=[
                MovimientoPuntosResponse.model_validate(m) for m in movimientos
            ],
        )
