"""
Servicio de clientes.

Lógica de negocio del módulo: control de duplicados por documento,
actualización parcial, baja lógica (no se elimina un cliente con deuda) y
adjunta la deuda total a cada cliente devuelto. No conoce FastAPI.
"""

from decimal import Decimal
from typing import Sequence

from sqlalchemy.orm import Session

from app.core.exceptions import (
    ClienteAlreadyExistsError,
    ClienteHasDeudaError,
    ClienteNotFoundError,
)
from app.models.cliente import Cliente
from app.repositories.cliente_repository import ClienteRepository
from app.schemas.cliente import ClienteCreate, ClienteResponse, ClienteUpdate


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
