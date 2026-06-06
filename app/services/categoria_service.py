"""
Servicio de categorías.

Contiene la LÓGICA DE NEGOCIO y todas las validaciones del módulo:
control de duplicados (sin distinguir mayúsculas/minúsculas), verificación
de existencia y la regla que impide eliminar categorías con productos
asociados. No conoce FastAPI: lanza excepciones de dominio que la capa de
API traduce a respuestas HTTP.
"""

from typing import Sequence

from sqlalchemy.orm import Session

from app.core.exceptions import (
    CategoriaAlreadyExistsError,
    CategoriaHasProductsError,
    CategoriaNotFoundError,
)
from app.models.categoria import Categoria
from app.repositories.categoria_repository import CategoriaRepository
from app.schemas.categoria import CategoriaCreate, CategoriaUpdate


class CategoriaService:
    """Orquesta los casos de uso del módulo de categorías."""

    def __init__(self, db: Session) -> None:
        self.repository = CategoriaRepository(db)

    # ------------------------------------------------------------------
    # Helpers internos
    # ------------------------------------------------------------------
    def _get_or_404(self, categoria_id: int) -> Categoria:
        """
        Devuelve la categoría o lanza CategoriaNotFoundError (404).

        Centralizar esta comprobación evita repetir el mismo bloque en
        get_by_id, update y delete.
        """
        categoria = self.repository.get_by_id(categoria_id)
        if categoria is None:
            raise CategoriaNotFoundError()
        return categoria

    # ------------------------------------------------------------------
    # Casos de uso
    # ------------------------------------------------------------------
    def create(self, data: CategoriaCreate) -> Categoria:
        """
        Crea una nueva categoría.

        El nombre ya llega normalizado (recortado) por el schema. Aquí solo
        validamos que no exista otra categoría con el mismo nombre, ignorando
        mayúsculas/minúsculas.

        Raises:
            CategoriaAlreadyExistsError: si el nombre ya está registrado.
        """
        if self.repository.exists_by_name(data.nombre):
            raise CategoriaAlreadyExistsError()
        return self.repository.create_categoria(data.nombre)

    def list(self, search: str | None = None) -> Sequence[Categoria]:
        """
        Lista las categorías.

        Si se proporciona `search`, devuelve solo las coincidencias parciales
        (sin distinguir mayúsculas/minúsculas). En ambos casos el orden es por
        fecha de creación descendente.
        """
        if search and search.strip():
            return self.repository.search(search)
        return self.repository.get_all()

    def get(self, categoria_id: int) -> Categoria:
        """Devuelve una categoría por id o lanza 404 si no existe."""
        return self._get_or_404(categoria_id)

    def update(self, categoria_id: int, data: CategoriaUpdate) -> Categoria:
        """
        Actualiza el nombre de una categoría.

        Valida que la categoría exista y que el nuevo nombre no choque con
        otra categoría distinta (se excluye la propia de la comprobación).

        Raises:
            CategoriaNotFoundError: si la categoría no existe.
            CategoriaAlreadyExistsError: si el nombre ya lo usa otra categoría.
        """
        categoria = self._get_or_404(categoria_id)

        # Excluimos la categoría actual para permitir "guardar sin cambios"
        # o cambios de casing sobre su propio nombre.
        if self.repository.exists_by_name(data.nombre, exclude_id=categoria_id):
            raise CategoriaAlreadyExistsError()

        return self.repository.update(categoria, data.nombre)

    def delete(self, categoria_id: int) -> None:
        """
        Elimina una categoría.

        Reglas:
            - Debe existir (si no, 404).
            - No debe tener productos asociados (preparado para fases futuras);
              si los tiene, se impide la eliminación.

        Raises:
            CategoriaNotFoundError: si la categoría no existe.
            CategoriaHasProductsError: si tiene productos asociados.
        """
        categoria = self._get_or_404(categoria_id)

        if self.repository.has_associated_products(categoria_id):
            raise CategoriaHasProductsError()

        self.repository.delete(categoria)
