"""
Servicio de proveedores.

Contiene la LÓGICA DE NEGOCIO y todas las validaciones del módulo:
control de duplicados por nombre (sin distinguir mayúsculas/minúsculas) y por
RUC, verificación de existencia, actualización parcial y la regla que impide
eliminar proveedores con productos asociados. No conoce FastAPI: lanza
excepciones de dominio que la capa de API traduce a respuestas HTTP.
"""

from typing import Sequence

from sqlalchemy.orm import Session

from app.core.exceptions import (
    ProveedorAlreadyExistsError,
    ProveedorHasProductsError,
    ProveedorNotFoundError,
    ProveedorRucAlreadyExistsError,
)
from app.models.proveedor import Proveedor
from app.repositories.proveedor_repository import ProveedorRepository
from app.schemas.proveedor import ProveedorCreate, ProveedorUpdate


class ProveedorService:
    """Orquesta los casos de uso del módulo de proveedores."""

    def __init__(self, db: Session) -> None:
        self.repository = ProveedorRepository(db)

    # ------------------------------------------------------------------
    # Helpers internos
    # ------------------------------------------------------------------
    def _get_or_404(self, proveedor_id: int) -> Proveedor:
        """Devuelve el proveedor o lanza ProveedorNotFoundError (404)."""
        proveedor = self.repository.get_by_id(proveedor_id)
        if proveedor is None:
            raise ProveedorNotFoundError()
        return proveedor

    def _validar_nombre_unico(
        self, nombre: str, exclude_id: int | None = None
    ) -> None:
        """Lanza ProveedorAlreadyExistsError si el nombre ya está en uso."""
        if self.repository.exists_by_name(nombre, exclude_id=exclude_id):
            raise ProveedorAlreadyExistsError()

    def _validar_ruc_unico(
        self, ruc: str, exclude_id: int | None = None
    ) -> None:
        """Lanza ProveedorRucAlreadyExistsError si el RUC ya está en uso."""
        if self.repository.exists_by_ruc(ruc, exclude_id=exclude_id):
            raise ProveedorRucAlreadyExistsError()

    # ------------------------------------------------------------------
    # Casos de uso
    # ------------------------------------------------------------------
    def create(self, data: ProveedorCreate) -> Proveedor:
        """
        Registra un nuevo proveedor.

        Valida que el nombre no esté duplicado (ignorando mayúsculas/minúsculas)
        y, si se proporcionó RUC, que tampoco esté duplicado.

        Raises:
            ProveedorAlreadyExistsError: nombre duplicado.
            ProveedorRucAlreadyExistsError: RUC duplicado.
        """
        self._validar_nombre_unico(data.nombre)
        if data.ruc is not None:
            self._validar_ruc_unico(data.ruc)

        return self.repository.create_proveedor(
            nombre=data.nombre,
            telefono=data.telefono,
            direccion=data.direccion,
            ruc=data.ruc,
            observaciones=data.observaciones,
        )

    def list(self, search: str | None = None) -> Sequence[Proveedor]:
        """
        Lista los proveedores ordenados por fecha descendente. Si se envía
        `search`, devuelve coincidencias parciales por nombre o RUC.
        """
        if search and search.strip():
            return self.repository.search(search)
        return self.repository.get_all()

    def get(self, proveedor_id: int) -> Proveedor:
        """Devuelve un proveedor por id o lanza 404 si no existe."""
        return self._get_or_404(proveedor_id)

    def update(self, proveedor_id: int, data: ProveedorUpdate) -> Proveedor:
        """
        Actualiza parcialmente un proveedor.

        Solo se aplican los campos realmente enviados por el cliente
        (`exclude_unset=True`). Si entre ellos viene el nombre o el RUC, se
        valida que no choquen con OTRO proveedor distinto.

        Raises:
            ProveedorNotFoundError: si el proveedor no existe.
            ProveedorAlreadyExistsError: si el nuevo nombre ya lo usa otro.
            ProveedorRucAlreadyExistsError: si el nuevo RUC ya lo usa otro.
        """
        proveedor = self._get_or_404(proveedor_id)

        # Solo los campos que el cliente incluyó en la petición.
        cambios = data.model_dump(exclude_unset=True)

        # Validar duplicados únicamente si esos campos van a cambiar.
        if "nombre" in cambios and cambios["nombre"] is not None:
            self._validar_nombre_unico(cambios["nombre"], exclude_id=proveedor_id)

        if "ruc" in cambios and cambios["ruc"] is not None:
            self._validar_ruc_unico(cambios["ruc"], exclude_id=proveedor_id)

        # Si no hay nada que cambiar, devolvemos el proveedor tal cual.
        if not cambios:
            return proveedor

        return self.repository.update(proveedor, cambios)

    def delete(self, proveedor_id: int) -> None:
        """
        Elimina un proveedor.

        Reglas:
            - Debe existir (si no, 404).
            - No debe tener productos asociados (preparado para fases futuras);
              si los tiene, se impide la eliminación.

        Raises:
            ProveedorNotFoundError: si el proveedor no existe.
            ProveedorHasProductsError: si tiene productos asociados.
        """
        proveedor = self._get_or_404(proveedor_id)

        if self.repository.has_associated_products(proveedor_id):
            raise ProveedorHasProductsError()

        self.repository.delete(proveedor)
