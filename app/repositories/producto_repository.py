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

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from app.models.producto import Producto
from app.utils.productos import generate_product_code


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

    def get_all(
        self,
        search: Optional[str] = None,
        categoria_id: Optional[int] = None,
        proveedor_id: Optional[int] = None,
        estado: Optional[str] = None,
    ) -> Sequence[Producto]:
        """
        Lista productos activos aplicando filtros opcionales combinables.

        Filtros:
            search: coincidencia parcial por nombre o marca (case-insensitive).
            categoria_id: filtra por categoría.
            proveedor_id: filtra por proveedor.
            estado: filtra por estado exacto.

        Orden: fecha de creación descendente (con id como desempate estable).
        """
        stmt = (
            select(Producto)
            .where(Producto.is_active.is_(True))
            .options(*self._eager())
        )

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
        if proveedor_id is not None:
            stmt = stmt.where(Producto.proveedor_id == proveedor_id)
        if estado is not None:
            stmt = stmt.where(Producto.estado == estado)

        stmt = stmt.order_by(Producto.created_at.desc(), Producto.id.desc())
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

    def delete(self, producto: Producto) -> None:
        """
        SOFT DELETE: marca el producto como inactivo en lugar de borrarlo.

        Así se preserva la integridad histórica cuando existan ventas que
        referencien al producto (fases futuras). Los productos inactivos no
        aparecen en listados ni búsquedas.
        """
        producto.is_active = False
        self.db.commit()
