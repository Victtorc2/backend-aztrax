"""
Repositorio del módulo de reposición ("productos por pedir").

Opera sobre el modelo Producto existente (no crea tablas nuevas). Centraliza
las condiciones SQL de "agotado" y "bajo stock" en métodos privados para no
duplicar la lógica entre las distintas consultas, y usa `joinedload` para
traer categoría y proveedor en una sola consulta (evita el problema N+1).
"""

from typing import Optional, Sequence

from sqlalchemy import and_, case, or_, select
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.sql.elements import ColumnElement

from app.models.producto import Producto
from app.utils.productos import EstadoProducto


class RestockRepository:
    """Acceso a datos para la reposición de productos."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Carga anticipada de relaciones (evita N+1)
    # ------------------------------------------------------------------
    def _eager(self):
        return (
            joinedload(Producto.categoria),
            joinedload(Producto.proveedor),
        )

    # ------------------------------------------------------------------
    # Condiciones SQL reutilizables (única fuente de verdad por módulo)
    # ------------------------------------------------------------------
    def _expr_agotado(self) -> ColumnElement[bool]:
        """
        Producto agotado: stock 0 O estado 'agotado'.

        Se combinan ambos para ser robustos incluso si el estado quedara
        desincronizado respecto del stock.
        """
        return or_(
            Producto.stock == 0,
            Producto.estado == EstadoProducto.AGOTADO.value,
        )

    def _expr_bajo_stock(self) -> ColumnElement[bool]:
        """
        Producto en bajo stock: (stock > 0 y stock <= stock_minimo) O estado
        'bajo_stock', EXCLUYENDO los agotados.
        """
        return and_(
            ~self._expr_agotado(),
            or_(
                and_(Producto.stock > 0, Producto.stock <= Producto.stock_minimo),
                Producto.estado == EstadoProducto.BAJO_STOCK.value,
            ),
        )

    def _expr_por_pedir(self) -> ColumnElement[bool]:
        """Producto por pedir: agotado O bajo stock."""
        return or_(self._expr_agotado(), self._expr_bajo_stock())

    # ------------------------------------------------------------------
    # Consultas
    # ------------------------------------------------------------------
    def get_agotados(self) -> Sequence[Producto]:
        """
        Productos agotados y activos.

        Orden: primero los más recientes, luego por menor stock.
        """

        stmt = (
            select(Producto)
            .where(Producto.is_active.is_(True), self._expr_agotado())
            .options(*self._eager())
            .order_by(
                Producto.created_at.desc(), Producto.stock.asc(), Producto.id.desc()
            )
        )
        return self.db.scalars(stmt).all()

    def get_bajo_stock(self) -> Sequence[Producto]:
        """
        Productos en bajo stock (no agotados) y activos.

        Orden: menor stock primero (con fecha descendente como desempate).
        """

        stmt = (
            select(Producto)
            .where(Producto.is_active.is_(True), self._expr_bajo_stock())
            .options(*self._eager())
            .order_by(
                Producto.stock.asc(), Producto.created_at.desc(), Producto.id.desc()
            )
        )
        return self.db.scalars(stmt).all()

    def get_por_pedir(
        self,
        search: Optional[str] = None,
        estado: Optional[str] = None,
        categoria_id: Optional[int] = None,
        proveedor_id: Optional[int] = None,
    ) -> Sequence[Producto]:
        """
        Lista combinada de productos por pedir (agotados + bajo stock), con
        filtros opcionales combinables.

        Orden de prioridad:
            1. agotados (stock 0)
            2. bajo stock
        Dentro de cada grupo: menor stock primero, luego fecha descendente.

        Args:
            search: coincidencia parcial por nombre o código.
            estado: 'agotado' | 'bajo_stock' para restringir a un solo grupo.
            categoria_id / proveedor_id: filtros por relación.
        """

        stmt = (
            select(Producto)
            .where(Producto.is_active.is_(True))
            .options(*self._eager())
        )

        # Restricción por estado (o ambos grupos si no se especifica).
        if estado == EstadoProducto.AGOTADO.value:
            stmt = stmt.where(self._expr_agotado())
        elif estado == EstadoProducto.BAJO_STOCK.value:
            stmt = stmt.where(self._expr_bajo_stock())
        else:
            stmt = stmt.where(self._expr_por_pedir())

        # Filtros adicionales.
        if categoria_id is not None:
            stmt = stmt.where(Producto.categoria_id == categoria_id)
        if proveedor_id is not None:
            stmt = stmt.where(Producto.proveedor_id == proveedor_id)
        if search and search.strip():
            patron = f"%{search.strip().lower()}%"
            stmt = stmt.where(
                or_(
                    Producto.nombre.ilike(patron),
                    Producto.codigo.ilike(patron),
                )
            )

        # Prioridad: agotados (0) antes que bajo stock (1).
        prioridad = case((self._expr_agotado(), 0), else_=1)
        stmt = stmt.order_by(
            prioridad.asc(),
            Producto.stock.asc(),
            Producto.created_at.desc(),
            Producto.id.desc(),
        )
        return self.db.scalars(stmt).all()

    def search_por_pedir(
        self,
        termino: str,
        estado: Optional[str] = None,
        categoria_id: Optional[int] = None,
        proveedor_id: Optional[int] = None,
    ) -> Sequence[Producto]:
        """
        Búsqueda por nombre o código dentro de la lista por pedir.

        Delega en `get_por_pedir` para no duplicar la lógica de filtrado
        ni el ordenamiento.
        """
        return self.get_por_pedir(
            search=termino,
            estado=estado,
            categoria_id=categoria_id,
            proveedor_id=proveedor_id,
        )
