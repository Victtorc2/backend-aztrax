"""
Servicio del módulo de reposición ("productos por pedir").

Centraliza la lógica de negocio: validación de los filtros (categoría y
proveedor deben existir) y delegación de las consultas al repositorio, que
es quien aplica las reglas SQL de agotado/bajo stock y el ordenamiento.

No conoce FastAPI: lanza excepciones de dominio que la API traduce a HTTP.
"""

from typing import Optional, Sequence

from sqlalchemy.orm import Session

from app.core.exceptions import (
    CategoriaNotFoundError,
    ProveedorNotFoundError,
)
from app.models.producto import Producto
from app.repositories.categoria_repository import CategoriaRepository
from app.repositories.proveedor_repository import ProveedorRepository
from app.repositories.restock_repository import RestockRepository


class RestockService:
    """Orquesta los casos de uso de la reposición de productos."""

    def __init__(self, db: Session) -> None:
        self.repository = RestockRepository(db)
        self.categoria_repository = CategoriaRepository(db)
        self.proveedor_repository = ProveedorRepository(db)

    # ------------------------------------------------------------------
    # Validación de filtros
    # ------------------------------------------------------------------
    def _validar_filtros(
        self, categoria_id: Optional[int], proveedor_id: Optional[int]
    ) -> None:
        """
        Valida que la categoría y el proveedor de los filtros existan.

        Raises:
            CategoriaNotFoundError / ProveedorNotFoundError si no existen.
        """
        if categoria_id is not None:
            if self.categoria_repository.get_by_id(categoria_id) is None:
                raise CategoriaNotFoundError()
        if proveedor_id is not None:
            if self.proveedor_repository.get_by_id(proveedor_id) is None:
                raise ProveedorNotFoundError()

    # ------------------------------------------------------------------
    # Casos de uso
    # ------------------------------------------------------------------
    def agotados(self) -> Sequence[Producto]:
        """Productos agotados (más recientes primero, luego menor stock)."""
        return self.repository.get_agotados()

    def bajo_stock(self) -> Sequence[Producto]:
        """Productos en bajo stock, no agotados (menor stock primero)."""
        return self.repository.get_bajo_stock()

    def por_pedir(
        self,
        search: Optional[str] = None,
        estado: Optional[str] = None,
        categoria: Optional[int] = None,
        proveedor: Optional[int] = None,
    ) -> Sequence[Producto]:
        """
        Lista combinada por pedir (agotados + bajo stock) con filtros.

        Valida primero que los filtros de categoría/proveedor existan; de lo
        contrario devuelve un 404 claro en lugar de una lista vacía silenciosa.
        """
        self._validar_filtros(categoria, proveedor)
        return self.repository.get_por_pedir(
            search=search,
            estado=estado,
            categoria_id=categoria,
            proveedor_id=proveedor,
        )
