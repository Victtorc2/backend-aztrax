"""
Servicio de crédito (fiado).

Gestiona los abonos (pagos parciales) sobre ventas al crédito y construye el
estado de cuenta de un cliente. La creación de ventas al crédito vive en
VentaService (al registrar la venta); aquí se gestionan los pagos posteriores.

Regla central del abono:
    saldo_pendiente_nuevo = saldo_pendiente_actual - monto_abonado
El abono no puede superar el saldo. Cuando el saldo llega a 0, la deuda de esa
venta queda saldada.
"""

from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.exceptions import (
    AbonoInvalidoError,
    ClienteNotFoundError,
    VentaNoEsCreditoError,
    VentaNotFoundError,
)
from app.models.venta import Abono, Venta
from app.repositories.cliente_repository import ClienteRepository
from app.repositories.venta_repository import VentaRepository
from app.schemas.credito import (
    AbonoCreate,
    AbonoResponse,
    EstadoCuentaResponse,
    VentaCreditoResponse,
)

_CERO = Decimal("0.00")


class CreditoService:
    """Orquesta abonos y estado de cuenta del crédito."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.ventas = VentaRepository(db)
        self.clientes = ClienteRepository(db)

    # ------------------------------------------------------------------
    # Abonos
    # ------------------------------------------------------------------
    def registrar_abono(self, venta_id: int, data: AbonoCreate) -> AbonoResponse:
        """
        Registra un abono sobre una venta al crédito y reduce su saldo.

        Raises:
            VentaNotFoundError: la venta no existe.
            VentaNoEsCreditoError: la venta es al contado.
            AbonoInvalidoError: el monto supera el saldo pendiente.
        """
        venta = self.ventas.get_by_id(venta_id)
        if venta is None:
            raise VentaNotFoundError()
        if venta.tipo_pago != "credito":
            raise VentaNoEsCreditoError()

        monto = Decimal(data.monto).quantize(Decimal("0.01"))
        if monto <= 0:
            raise AbonoInvalidoError("El monto debe ser mayor que cero")
        if monto > venta.saldo_pendiente:
            raise AbonoInvalidoError(
                f"El abono ({monto}) supera el saldo pendiente "
                f"({venta.saldo_pendiente})"
            )

        abono = Abono(
            venta_id=venta.id,
            monto=monto,
            metodo_pago=data.metodo_pago.value,
            nota=data.nota,
        )
        self.db.add(abono)

        # Reducir el saldo de la venta.
        venta.saldo_pendiente = (venta.saldo_pendiente - monto).quantize(
            Decimal("0.01")
        )
        self.db.commit()
        self.db.refresh(abono)
        return AbonoResponse.model_validate(abono)

    # ------------------------------------------------------------------
    # Estado de cuenta
    # ------------------------------------------------------------------
    def estado_cuenta(self, cliente_id: int) -> EstadoCuentaResponse:
        """
        Construye el estado de cuenta del cliente: todas sus ventas al crédito,
        con abonos y saldos, y el total adeudado.

        Raises:
            ClienteNotFoundError: si el cliente no existe.
        """
        cliente = self.clientes.get_by_id(cliente_id)
        if cliente is None:
            raise ClienteNotFoundError()

        ventas = self.ventas.get_creditos_by_cliente(cliente_id)

        ventas_resp: list[VentaCreditoResponse] = []
        deuda_total = _CERO
        for v in ventas:
            pagado = (Decimal(v.total) - Decimal(v.saldo_pendiente)).quantize(
                Decimal("0.01")
            )
            deuda_total += Decimal(v.saldo_pendiente)
            ventas_resp.append(
                VentaCreditoResponse(
                    id=v.id,
                    numero_boleta=v.numero_boleta,
                    fecha=v.fecha,
                    total=v.total,
                    pagado=pagado,
                    saldo_pendiente=v.saldo_pendiente,
                    abonos=[AbonoResponse.model_validate(a) for a in v.abonos],
                )
            )

        return EstadoCuentaResponse(
            cliente_id=cliente.id,
            cliente_nombre=cliente.nombre,
            deuda_total=deuda_total.quantize(Decimal("0.01")),
            ventas=ventas_resp,
        )
