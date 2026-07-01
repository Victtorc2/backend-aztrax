"""
Servicio de gastos / egresos y del saldo de dinero.

Registra salidas de dinero (pedidos, servicios, sueldos, etc.) con su método
de pago y calcula el dinero disponible por método:

    saldo[metodo] = ventas_al_contado[metodo] + abonos[metodo] − gastos[metodo]

Un gasto en efectivo hecho con la caja abierta se vincula a esa sesión
(`caja_id`) para que el arqueo de caja lo descuente automáticamente.
"""

from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.core.exceptions import GastoNotFoundError, ProveedorNotFoundError
from app.models.gasto import Gasto
from app.repositories.caja_repository import CajaRepository
from app.repositories.gasto_repository import GastoRepository
from app.repositories.proveedor_repository import ProveedorRepository
from app.schemas.gasto import (
    GastoCreate,
    GastoResponse,
    SaldoMetodo,
    SaldoResponse,
)

_CERO = Decimal("0.00")


class GastoService:
    """Orquesta el registro de gastos y el cálculo del saldo."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = GastoRepository(db)
        self.caja_repo = CajaRepository(db)
        self.proveedor_repo = ProveedorRepository(db)

    # ------------------------------------------------------------------
    # Registrar un gasto
    # ------------------------------------------------------------------
    def registrar(self, data: GastoCreate) -> GastoResponse:
        # Validar el proveedor si se indicó uno.
        if data.proveedor_id is not None:
            if self.proveedor_repo.get_by_id(data.proveedor_id) is None:
                raise ProveedorNotFoundError()

        # Si el gasto es en efectivo y hay una caja abierta, lo vinculamos a esa
        # sesión para que el arqueo lo descuente del efectivo esperado.
        caja_id: Optional[int] = None
        if data.metodo_pago.value == "efectivo":
            caja = self.caja_repo.get_abierta()
            if caja is not None:
                caja_id = caja.id

        gasto = Gasto(
            categoria=data.categoria.value,
            monto=Decimal(data.monto).quantize(Decimal("0.01")),
            metodo_pago=data.metodo_pago.value,
            proveedor_id=data.proveedor_id,
            descripcion=data.descripcion,
            caja_id=caja_id,
        )
        self.repo.add(gasto)
        self.repo.commit()
        self.repo.refresh(gasto)
        return self._to_response(gasto)

    # ------------------------------------------------------------------
    # Listado
    # ------------------------------------------------------------------
    def listar(
        self,
        categoria: Optional[str] = None,
        metodo_pago: Optional[str] = None,
        proveedor_id: Optional[int] = None,
        fecha_inicio=None,
        fecha_fin=None,
    ) -> list[GastoResponse]:
        gastos = self.repo.listar(
            categoria=categoria,
            metodo_pago=metodo_pago,
            proveedor_id=proveedor_id,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
        )
        return [self._to_response(g) for g in gastos]

    # ------------------------------------------------------------------
    # Eliminar
    # ------------------------------------------------------------------
    def eliminar(self, gasto_id: int) -> None:
        gasto = self.repo.get_by_id(gasto_id)
        if gasto is None:
            raise GastoNotFoundError()
        self.repo.delete(gasto)

    # ------------------------------------------------------------------
    # Saldo de dinero disponible por método
    # ------------------------------------------------------------------
    def saldo(self) -> SaldoResponse:
        ventas = self.repo.ventas_contado_por_metodo()
        abonos = self.repo.abonos_por_metodo()
        gastos = self.repo.gastos_por_metodo()

        def _metodo(nombre: str) -> SaldoMetodo:
            ingresos = (
                ventas.get(nombre, _CERO) + abonos.get(nombre, _CERO)
            ).quantize(Decimal("0.01"))
            egresos = gastos.get(nombre, _CERO).quantize(Decimal("0.01"))
            return SaldoMetodo(
                ingresos=ingresos,
                egresos=egresos,
                saldo=(ingresos - egresos).quantize(Decimal("0.01")),
            )

        efectivo = _metodo("efectivo")
        yape = _metodo("yape")
        return SaldoResponse(
            efectivo=efectivo,
            yape=yape,
            total=(efectivo.saldo + yape.saldo).quantize(Decimal("0.01")),
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _to_response(self, gasto: Gasto) -> GastoResponse:
        return GastoResponse(
            id=gasto.id,
            categoria=gasto.categoria,
            monto=Decimal(gasto.monto).quantize(Decimal("0.01")),
            metodo_pago=gasto.metodo_pago,
            proveedor_id=gasto.proveedor_id,
            proveedor_nombre=gasto.proveedor.nombre if gasto.proveedor else None,
            descripcion=gasto.descripcion,
            caja_id=gasto.caja_id,
            fecha=gasto.fecha,
        )
