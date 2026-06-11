"""
Servicio de caja diaria (apertura, movimientos, cierre y arqueo).

Solo puede haber una caja abierta a la vez. El arqueo al cerrar compara el
efectivo declarado (contado a mano) contra el esperado por el sistema:

    esperado = monto_inicial
             + ventas_en_efectivo (no anuladas, durante la sesión)
             + ingresos_manuales
             − egresos_manuales

    diferencia = declarado − esperado   (negativo = falta; positivo = sobra)

Las fechas se manejan en UTC naive para ser coherentes con el resto del
sistema (columnas pobladas por func.now()).
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.exceptions import (
    CajaNoAbiertaError,
    CajaYaAbiertaError,
)
from app.models.caja import Caja, MovimientoCaja
from app.repositories.caja_repository import CajaRepository
from app.schemas.caja import (
    CajaAbrir,
    CajaCerrar,
    CajaHistorialItem,
    CajaResponse,
    MovimientoCajaCreate,
    MovimientoCajaResponse,
)

_CERO = Decimal("0.00")


class CajaService:
    """Orquesta los casos de uso de la caja diaria."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = CajaRepository(db)

    # ------------------------------------------------------------------
    # Apertura
    # ------------------------------------------------------------------
    def abrir(self, data: CajaAbrir) -> CajaResponse:
        if self.repo.get_abierta() is not None:
            raise CajaYaAbiertaError()
        caja = Caja(
            estado="abierta",
            monto_inicial=Decimal(data.monto_inicial).quantize(Decimal("0.01")),
            nota_apertura=data.nota,
        )
        self.repo.add(caja)
        self.repo.commit()
        self.repo.refresh(caja)
        return self._resumen(caja)

    # ------------------------------------------------------------------
    # Estado actual
    # ------------------------------------------------------------------
    def actual(self) -> CajaResponse:
        caja = self.repo.get_abierta()
        if caja is None:
            raise CajaNoAbiertaError()
        return self._resumen(caja)

    # ------------------------------------------------------------------
    # Movimiento manual (ingreso / egreso de efectivo)
    # ------------------------------------------------------------------
    def registrar_movimiento(self, data: MovimientoCajaCreate) -> CajaResponse:
        caja = self.repo.get_abierta()
        if caja is None:
            raise CajaNoAbiertaError()
        self.repo.add(
            MovimientoCaja(
                caja_id=caja.id,
                tipo=data.tipo.value,
                monto=Decimal(data.monto).quantize(Decimal("0.01")),
                motivo=data.motivo,
            )
        )
        self.repo.commit()
        self.repo.refresh(caja)
        return self._resumen(caja)

    # ------------------------------------------------------------------
    # Cierre (arqueo)
    # ------------------------------------------------------------------
    def cerrar(self, data: CajaCerrar) -> CajaResponse:
        caja = self.repo.get_abierta()
        if caja is None:
            raise CajaNoAbiertaError()

        ahora = datetime.utcnow()
        ventas_ef = self.repo.ventas_efectivo(caja.id)
        ingresos, egresos = self._totales_movimientos(caja)
        esperado = (
            Decimal(caja.monto_inicial) + ventas_ef + ingresos - egresos
        ).quantize(Decimal("0.01"))
        declarado = Decimal(data.monto_declarado).quantize(Decimal("0.01"))

        caja.estado = "cerrada"
        caja.cerrada_at = ahora
        caja.monto_esperado = esperado
        caja.monto_declarado = declarado
        caja.diferencia = (declarado - esperado).quantize(Decimal("0.01"))
        caja.nota_cierre = data.nota
        self.repo.commit()
        self.repo.refresh(caja)
        return self._resumen(caja)

    # ------------------------------------------------------------------
    # Historial
    # ------------------------------------------------------------------
    def historial(self) -> list[CajaHistorialItem]:
        return [
            CajaHistorialItem.model_validate(c) for c in self.repo.listar()
        ]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _totales_movimientos(self, caja: Caja) -> tuple[Decimal, Decimal]:
        ingresos = _CERO
        egresos = _CERO
        for m in caja.movimientos:
            if m.tipo == "ingreso":
                ingresos += Decimal(m.monto)
            else:
                egresos += Decimal(m.monto)
        return ingresos.quantize(Decimal("0.01")), egresos.quantize(Decimal("0.01"))

    def _resumen(self, caja: Caja) -> CajaResponse:
        """Construye la respuesta con el arqueo (en vivo si está abierta)."""
        ingresos, egresos = self._totales_movimientos(caja)

        ventas_ef = self.repo.ventas_efectivo(caja.id)
        if caja.estado == "abierta":
            esperado = (
                Decimal(caja.monto_inicial) + ventas_ef + ingresos - egresos
            ).quantize(Decimal("0.01"))
            declarado = None
            diferencia = None
        else:
            esperado = Decimal(caja.monto_esperado or 0).quantize(Decimal("0.01"))
            declarado = caja.monto_declarado
            diferencia = caja.diferencia

        return CajaResponse(
            id=caja.id,
            estado=caja.estado,
            monto_inicial=Decimal(caja.monto_inicial).quantize(Decimal("0.01")),
            ventas_efectivo=ventas_ef,
            total_ingresos=ingresos,
            total_egresos=egresos,
            monto_esperado=esperado,
            monto_declarado=declarado,
            diferencia=diferencia,
            nota_apertura=caja.nota_apertura,
            nota_cierre=caja.nota_cierre,
            abierta_at=caja.abierta_at,
            cerrada_at=caja.cerrada_at,
            movimientos=[
                MovimientoCajaResponse.model_validate(m) for m in caja.movimientos
            ],
        )
