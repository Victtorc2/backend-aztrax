"""
Repositorio de productos.

Encapsula TODO el acceso a datos de la tabla `productos`. Aplica:
- Carga anticipada (joinedload) de categoría y proveedor para evitar el
  problema N+1 al construir las respuestas.
- Filtro por `is_active = True` en las consultas de lectura, de modo que los
  productos con soft delete no aparecen en listados ni búsquedas.
"""

from decimal import Decimal
from typing import Any, Optional, Sequence

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.sql import Select

from app.models.producto import Producto
from app.utils.productos import OrdenProducto, generate_product_code


class ProductoRepository:
    """Acceso a datos para la entidad Producto."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # Opciones de carga anticipada reutilizadas en las consultas de lectura.
    def _eager(self):
        return (
            joinedload(Producto.categoria),
            joinedload(Producto.proveedor),
        )

    # ------------------------------------------------------------------
    # Generación de código
    # ------------------------------------------------------------------
    def generate_code(self) -> str:
        """
        Genera el siguiente código secuencial (P0001, P0002, ...).

        Toma el código del producto con mayor id (incluyendo los desactivados
        por soft delete, que siguen ocupando su número) y le suma 1. La
        restricción UNIQUE sobre `codigo` actúa como red de seguridad final.
        """
        ultimo_codigo = self.db.scalar(
            select(Producto.codigo).order_by(Producto.id.desc()).limit(1)
        )
        if ultimo_codigo is None:
            siguiente = 1
        else:
            # "P0007" -> 7 -> 8
            siguiente = int(ultimo_codigo[1:]) + 1
        return generate_product_code(siguiente)

    # ------------------------------------------------------------------
    # Lectura
    # ------------------------------------------------------------------
    def get_by_id(self, producto_id: int) -> Optional[Producto]:
        """Devuelve un producto ACTIVO por su id (con relaciones cargadas)."""
        stmt = (
            select(Producto)
            .where(Producto.id == producto_id, Producto.is_active.is_(True))
            .options(*self._eager())
        )
        return self.db.scalar(stmt)

    def get_by_id_any(self, producto_id: int) -> Optional[Producto]:
        """
        Devuelve un producto por id SIN filtrar por estado (activo o inactivo).

        Necesario para REACTIVAR un producto desactivado: `get_by_id` solo trae
        activos, por lo que no sirve para encontrar uno desactivado.
        """
        stmt = (
            select(Producto)
            .where(Producto.id == producto_id)
            .options(*self._eager())
        )
        return self.db.scalar(stmt)

    def _aplicar_filtros(
        self,
        stmt: Select,
        search: Optional[str] = None,
        categoria_id: Optional[int] = None,
        marca: Optional[str] = None,
        proveedor_id: Optional[int] = None,
        estado: Optional[str] = None,
        destacado: Optional[bool] = None,
    ) -> Select:
        """
        Aplica los filtros comunes (compartidos por el listado, el paginado y
        el conteo) sobre una consulta que ya restringe a productos activos.

        Filtros:
            search: coincidencia parcial por nombre, marca o modelo.
            categoria_id: filtra por categoría.
            marca: filtra por marca EXACTA (case-insensitive).
            proveedor_id: filtra por proveedor.
            estado: filtra por estado exacto.
            destacado: filtra por productos destacados (True) o no (False).
        """
        if search and search.strip():
            patron = f"%{search.strip().lower()}%"
            stmt = stmt.where(
                or_(
                    Producto.nombre.ilike(patron),
                    Producto.marca.ilike(patron),
                    Producto.modelo.ilike(patron),
                )
            )
        if categoria_id is not None:
            stmt = stmt.where(Producto.categoria_id == categoria_id)
        if marca and marca.strip():
            stmt = stmt.where(func.lower(Producto.marca) == marca.strip().lower())
        if proveedor_id is not None:
            stmt = stmt.where(Producto.proveedor_id == proveedor_id)
        if estado is not None:
            stmt = stmt.where(Producto.estado == estado)
        if destacado is not None:
            stmt = stmt.where(Producto.destacado.is_(destacado))
        return stmt

    def _aplicar_estado_activo(self, stmt: Select, activo: Optional[bool]) -> Select:
        """
        Filtra por estado de activación:
            True  -> solo activos (por defecto).
            False -> solo desactivados (para revisarlos/reactivarlos).
            None  -> todos (activos e inactivos).
        """
        if activo is True:
            return stmt.where(Producto.is_active.is_(True))
        if activo is False:
            return stmt.where(Producto.is_active.is_(False))
        return stmt

    def _aplicar_orden(self, stmt: Select, orden: Optional[str]) -> Select:
        """
        Aplica el criterio de ordenamiento.

        - "nombre": alfabético ascendente (A-Z).
        - cualquier otro / None: más recientes primero (fecha desc).
        """
        if orden == OrdenProducto.NOMBRE.value:
            return stmt.order_by(Producto.nombre.asc(), Producto.id.asc())
        return stmt.order_by(Producto.created_at.desc(), Producto.id.desc())

    def get_all(
        self,
        search: Optional[str] = None,
        categoria_id: Optional[int] = None,
        marca: Optional[str] = None,
        proveedor_id: Optional[int] = None,
        estado: Optional[str] = None,
        destacado: Optional[bool] = None,
        activo: Optional[bool] = True,
        orden: Optional[str] = None,
    ) -> Sequence[Producto]:
        """
        Lista TODOS los productos que cumplen los filtros (sin paginar).

        Se usa, por ejemplo, para el reporte PDF, que necesita el inventario
        completo. Por defecto solo activos; `orden` permite alfabético (A-Z).
        """
        stmt = self._aplicar_estado_activo(
            select(Producto).options(*self._eager()), activo
        )
        stmt = self._aplicar_filtros(
            stmt, search, categoria_id, marca, proveedor_id, estado, destacado
        )
        stmt = self._aplicar_orden(stmt, orden)
        return self.db.scalars(stmt).all()

    def get_paginated(
        self,
        page: int,
        page_size: int,
        search: Optional[str] = None,
        categoria_id: Optional[int] = None,
        marca: Optional[str] = None,
        proveedor_id: Optional[int] = None,
        estado: Optional[str] = None,
        destacado: Optional[bool] = None,
        activo: Optional[bool] = True,
        orden: Optional[str] = None,
    ) -> tuple[Sequence[Producto], int]:
        """
        Devuelve una PÁGINA de productos junto con el total de coincidencias
        (para que el cliente calcule el número de páginas).

        Por defecto solo activos (`activo=True`); con `activo=False` trae solo
        los desactivados y con `activo=None` trae todos. `orden` permite
        alfabético ascendente (A-Z) además del orden por defecto (recientes).

        Returns:
            (items, total): la lista de la página y el total sin paginar.
        """
        # Total de coincidencias: se cuenta sobre los mismos filtros, sin
        # ordenar ni cargar relaciones (más barato).
        count_stmt = self._aplicar_estado_activo(
            select(func.count(Producto.id)), activo
        )
        count_stmt = self._aplicar_filtros(
            count_stmt, search, categoria_id, marca, proveedor_id, estado, destacado,
        )
        total = self.db.scalar(count_stmt) or 0

        stmt = self._aplicar_estado_activo(
            select(Producto).options(*self._eager()), activo
        )
        stmt = self._aplicar_filtros(
            stmt, search, categoria_id, marca, proveedor_id, estado, destacado
        )
        stmt = self._aplicar_orden(stmt, orden)
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        items = self.db.scalars(stmt).all()
        return items, total

    def marcas(self, categoria_id: Optional[int] = None) -> Sequence[str]:
        """
        Devuelve las marcas distintas de los productos activos, ordenadas
        alfabéticamente. Si se pasa `categoria_id`, solo las de esa categoría
        (para el filtro encadenado categoría → marca del panel admin).
        """
        stmt = (
            select(Producto.marca)
            .where(Producto.is_active.is_(True))
            .group_by(Producto.marca)
            .order_by(Producto.marca.asc())
        )
        if categoria_id is not None:
            stmt = stmt.where(Producto.categoria_id == categoria_id)
        return self.db.scalars(stmt).all()

    def search(self, termino: str) -> Sequence[Producto]:
        """
        Búsqueda para el endpoint /productos/buscar: por NOMBRE, CÓDIGO o MARCA
        (coincidencia parcial, sin distinguir mayúsculas/minúsculas).
        """
        patron = f"%{termino.strip().lower()}%"
        stmt = (
            select(Producto)
            .where(
                Producto.is_active.is_(True),
                or_(
                    Producto.nombre.ilike(patron),
                    Producto.codigo.ilike(patron),
                    Producto.marca.ilike(patron),
                    Producto.modelo.ilike(patron),
                ),
            )
            .options(*self._eager())
            .order_by(Producto.created_at.desc(), Producto.id.desc())
        )
        return self.db.scalars(stmt).all()

    # ------------------------------------------------------------------
    # Escritura
    # ------------------------------------------------------------------
    def create_producto(
        self,
        codigo: str,
        nombre: str,
        marca: str,
        categoria_id: int,
        proveedor_id: int,
        precio_compra: Decimal,
        precio_venta: Decimal,
        stock: int,
        stock_minimo: int,
        estado: str,
        modelo: Optional[str] = None,
        representacion: str = "unidad",
        descripcion: Optional[str] = None,
        ficha_tecnica: Optional[str] = None,
    ) -> Producto:
        """Crea y persiste un nuevo producto (datos ya validados/calculados)."""
        producto = Producto(
            codigo=codigo,
            nombre=nombre,
            marca=marca,
            modelo=modelo,
            categoria_id=categoria_id,
            proveedor_id=proveedor_id,
            precio_compra=precio_compra,
            precio_venta=precio_venta,
            stock=stock,
            stock_minimo=stock_minimo,
            estado=estado,
            representacion=representacion,
            descripcion=descripcion,
            ficha_tecnica=ficha_tecnica,
        )
        self.db.add(producto)
        self.db.commit()
        # Re-consultamos con las relaciones cargadas para construir la respuesta.
        return self.get_by_id(producto.id)  # type: ignore[return-value]

    def update(self, producto: Producto, cambios: dict[str, Any]) -> Producto:
        """
        Aplica una actualización parcial. `cambios` contiene solo los campos
        a modificar (incluido `estado`, ya recalculado por el servicio).
        """
        for campo, valor in cambios.items():
            setattr(producto, campo, valor)
        self.db.commit()
        return self.get_by_id(producto.id)  # type: ignore[return-value]

    def set_active(self, producto: Producto, activo: bool) -> Producto:
        """
        Activa o desactiva un producto y devuelve el objeto recargado.

        A diferencia de `update`, recarga con `get_by_id_any` para que también
        funcione al DESACTIVAR (un producto inactivo no lo trae `get_by_id`).
        """
        producto.is_active = activo
        self.db.commit()
        return self.get_by_id_any(producto.id)  # type: ignore[return-value]

    def delete(self, producto: Producto) -> None:
        """
        SOFT DELETE: marca el producto como inactivo en lugar de borrarlo.

        Así se preserva la integridad histórica cuando existan ventas que
        referencien al producto (fases futuras). Los productos inactivos no
        aparecen en listados ni búsquedas.
        """
        producto.is_active = False
        self.db.commit()
