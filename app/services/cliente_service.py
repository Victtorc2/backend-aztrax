"""
Servicio de clientes.

Lógica de negocio del módulo: control de duplicados por documento,
actualización parcial, baja lógica (no se elimina un cliente con deuda) y
adjunta la deuda total a cada cliente devuelto. No conoce FastAPI.
"""

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.exceptions import (
    ClienteAlreadyExistsError,
    ClienteHasDeudaError,
    ClienteNotFoundError,
)
from app.models.cliente import Cliente
from app.repositories.cliente_repository import ClienteRepository
from app.schemas.cliente import (
    ClienteCreate,
    ClienteInactivo,
    ClienteResponse,
    ClienteUpdate,
    CompraResumen,
    PerfilCliente,
    ProductoFavorito,
)


class ClienteService:
    """Orquesta los casos de uso del módulo de clientes."""

    def __init__(self, db: Session) -> None:
        self.repository = ClienteRepository(db)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _get_or_404(self, cliente_id: int) -> Cliente:
        cliente = self.repository.get_by_id(cliente_id)
        if cliente is None:
            raise ClienteNotFoundError()
        return cliente

    def _to_response(self, cliente: Cliente, deuda: Decimal) -> ClienteResponse:
        resp = ClienteResponse.model_validate(cliente)
        resp.deuda_total = deuda
        return resp

    # ------------------------------------------------------------------
    # Casos de uso
    # ------------------------------------------------------------------
    def create(self, data: ClienteCreate) -> ClienteResponse:
        if data.documento and self.repository.exists_by_documento(data.documento):
            raise ClienteAlreadyExistsError()
        cliente = self.repository.create_cliente(
            nombre=data.nombre,
            documento=data.documento,
            telefono=data.telefono,
            email=data.email,
            direccion=data.direccion,
            nota=data.nota,
            fecha_nacimiento=data.fecha_nacimiento,
        )
        return self._to_response(cliente, Decimal("0.00"))

    def listar(self, search: str | None = None) -> list[ClienteResponse]:
        """Lista clientes (con búsqueda opcional) y su deuda total."""
        if search and search.strip():
            clientes = self.repository.search(search)
        else:
            clientes = self.repository.get_all()

        deudas = self.repository.deudas_por_cliente()
        return [
            self._to_response(c, deudas.get(c.id, Decimal("0.00")))
            for c in clientes
        ]

    def list_deudores(self) -> list[ClienteResponse]:
        """Devuelve solo los clientes que tienen deuda pendiente (> 0)."""
        deudas = self.repository.deudas_por_cliente()
        con_deuda = {cid: d for cid, d in deudas.items() if d > 0}
        resultado: list[ClienteResponse] = []
        for cliente_id, deuda in con_deuda.items():
            cliente = self.repository.get_by_id(cliente_id)
            if cliente is not None:
                resultado.append(self._to_response(cliente, deuda))
        # Mayor deuda primero.
        resultado.sort(key=lambda c: c.deuda_total, reverse=True)
        return resultado

    def get(self, cliente_id: int) -> ClienteResponse:
        cliente = self._get_or_404(cliente_id)
        deuda = self.repository.deuda_total(cliente_id)
        return self._to_response(cliente, deuda)

    def update(self, cliente_id: int, data: ClienteUpdate) -> ClienteResponse:
        cliente = self._get_or_404(cliente_id)
        cambios = data.model_dump(exclude_unset=True)

        if cambios.get("documento"):
            if self.repository.exists_by_documento(
                cambios["documento"], exclude_id=cliente_id
            ):
                raise ClienteAlreadyExistsError()

        if cambios:
            cliente = self.repository.update(cliente, cambios)
        deuda = self.repository.deuda_total(cliente_id)
        return self._to_response(cliente, deuda)

    def delete(self, cliente_id: int) -> None:
        """
        Baja lógica de un cliente. No se permite si tiene deuda pendiente
        (para no perder de vista lo que debe).
        """
        cliente = self._get_or_404(cliente_id)
        if self.repository.deuda_total(cliente_id) > 0:
            raise ClienteHasDeudaError()
        self.repository.deactivate(cliente)

    # ------------------------------------------------------------------
    # Perfil / historial de compra
    # ------------------------------------------------------------------
    def perfil(self, cliente_id: int) -> PerfilCliente:
        """
        Construye el perfil 360° del cliente: datos, métricas de compra
        (excluyen anuladas), productos favoritos e historial reciente.
        """
        cliente = self._get_or_404(cliente_id)
        deuda = self.repository.deuda_total(cliente_id)

        total_compras, total_gastado, ultima = self.repository.metricas_compra(
            cliente_id
        )
        ticket = (
            (total_gastado / total_compras).quantize(Decimal("0.01"))
            if total_compras
            else Decimal("0.00")
        )

        favoritos = [
            ProductoFavorito(
                producto_id=pid, nombre=nombre, marca=marca, unidades=unidades
            )
            for pid, nombre, marca, unidades in self.repository.productos_favoritos(
                cliente_id
            )
        ]

        recientes = [
            CompraResumen(
                venta_id=v.id,
                numero_boleta=v.numero_boleta,
                fecha=v.fecha,
                total=v.total,
                metodo_pago=v.metodo_pago,
                tipo_pago=v.tipo_pago,
                anulada=v.anulada,
            )
            for v in self.repository.compras_recientes(cliente_id)
        ]

        return PerfilCliente(
            cliente=self._to_response(cliente, deuda),
            total_compras=total_compras,
            total_gastado=total_gastado,
            ticket_promedio=ticket,
            ultima_compra=ultima,
            productos_favoritos=favoritos,
            compras_recientes=recientes,
        )

    # ------------------------------------------------------------------
    # Clientes inactivos (no compran hace X días)
    # ------------------------------------------------------------------
    def inactivos(self, dias: int = 30) -> list[ClienteInactivo]:
        """
        Clientes activos que compraron alguna vez pero no lo hacen hace al
        menos `dias` días. Pensado para recuperarlos con una promo. Ordenados
        por mayor tiempo sin comprar primero.
        """
        dias = max(1, dias)
        ultimas = self.repository.ultima_compra_por_cliente()
        gastos = self.repository.total_gastado_por_cliente()

        resultado: list[ClienteInactivo] = []
        for cliente_id, ultima in ultimas.items():
            dias_sin = self._dias_desde(ultima)
            if dias_sin is None or dias_sin < dias:
                continue
            cliente = self.repository.get_by_id(cliente_id)
            if cliente is None or not cliente.is_active:
                continue
            resultado.append(
                ClienteInactivo(
                    id=cliente.id,
                    nombre=cliente.nombre,
                    telefono=cliente.telefono,
                    ultima_compra=ultima,
                    dias_sin_comprar=dias_sin,
                    total_gastado=gastos.get(cliente_id, Decimal("0.00")),
                )
            )

        resultado.sort(key=lambda c: c.dias_sin_comprar or 0, reverse=True)
        return resultado

    @staticmethod
    def _dias_desde(momento: datetime | None) -> int | None:
        """Días transcurridos desde `momento` hasta ahora (tz-safe)."""
        if momento is None:
            return None
        if momento.tzinfo is None:
            ahora = datetime.utcnow()
        else:
            ahora = datetime.now(timezone.utc)
        return (ahora - momento).days
