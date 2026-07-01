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

from app.core.exceptions import (
    AjusteSaldoInvalidoError,
    GastoNotFoundError,
    ProveedorNotFoundError,
)
from app.models.ajuste_saldo import AjusteSaldo
from app.models.gasto import Gasto
from app.repositories.caja_repository import CajaRepository
from app.repositories.gasto_repository import GastoRepository
from app.repositories.proveedor_repository import ProveedorRepository
from app.schemas.gasto import (
    AjusteSaldoCreate,
    AjusteSaldoResponse,
    GastoCreate,
    GastoResponse,
    ModoAjusteSaldo,
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
        ajustes = self.repo.ajustes_por_metodo()

        def _metodo(nombre: str) -> SaldoMetodo:
            ingresos = (
                ventas.get(nombre, _CERO) + abonos.get(nombre, _CERO)
            )
            egresos = gastos.get(nombre, _CERO)
            # Los ajustes con signo se reparten en ingresos/egresos para que
            # el saldo siga cumpliendo saldo = ingresos − egresos.
            ajuste = ajustes.get(nombre, _CERO)
            if ajuste >= _CERO:
                ingresos += ajuste
            else:
                egresos += -ajuste
            ingresos = ingresos.quantize(Decimal("0.01"))
            egresos = egresos.quantize(Decimal("0.01"))
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
    # Ajustes manuales de saldo
    # ------------------------------------------------------------------
    def registrar_ajuste(self, data: AjusteSaldoCreate) -> SaldoResponse:
        """
        Agrega o modifica el saldo de un método guardando un ajuste con signo.

        - "agregar": suma `monto` (> 0) al saldo.
        - "establecer": fija el saldo del método a `monto`; se registra la
          diferencia contra el saldo actual.
        """
        metodo = data.metodo_pago.value
        monto = Decimal(data.monto).quantize(Decimal("0.01"))

        if data.modo is ModoAjusteSaldo.ESTABLECER:
            actual = self._saldo_metodo(metodo)
            delta = (monto - actual).quantize(Decimal("0.01"))
        else:  # AGREGAR
            if monto <= _CERO:
                raise AjusteSaldoInvalidoError(
                    "El monto a agregar debe ser mayor que 0"
                )
            delta = monto

        if delta == _CERO:
            raise AjusteSaldoInvalidoError("El ajuste no cambia el saldo actual")

        self.repo.add_ajuste(
            AjusteSaldo(
                metodo_pago=metodo,
                monto=delta,
                motivo=data.motivo.strip(),
            )
        )
        self.repo.commit()
        return self.saldo()

    def listar_ajustes(
        self, metodo_pago: Optional[str] = None
    ) -> list[AjusteSaldoResponse]:
        return [
            AjusteSaldoResponse.model_validate(a)
            for a in self.repo.listar_ajustes(metodo_pago=metodo_pago)
        ]

    def _saldo_metodo(self, metodo: str) -> Decimal:
        """Saldo actual de un método concreto (reusa el cálculo global)."""
        saldo = self.saldo()
        if metodo == "efectivo":
            return Decimal(saldo.efectivo.saldo).quantize(Decimal("0.01"))
        return Decimal(saldo.yape.saldo).quantize(Decimal("0.01"))

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
