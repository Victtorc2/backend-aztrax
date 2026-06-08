"""
Servicio de productos.

Centraliza la LÓGICA DE NEGOCIO del módulo:
- Validar que la categoría y el proveedor referenciados existan.
- Generar el código automático.
- Calcular el estado a partir del stock (creación y actualización).
- Actualización parcial.
- Soft delete.

No conoce FastAPI: lanza excepciones de dominio que la API traduce a HTTP.
Las validaciones de "precios positivos" y "stock no negativo" ya las garantiza
el schema (Pydantic), por lo que aquí no se repiten.
"""

from typing import Optional, Sequence

from sqlalchemy.orm import Session

from app.core.exceptions import (
    CategoriaNotFoundError,
    ProductoNotFoundError,
    ProveedorNotFoundError,
)
from app.models.producto import Producto
from app.pdf.reporte_productos import (
    generate_reporte_productos_pdf,
    reporte_filename,
)
from app.repositories.categoria_repository import CategoriaRepository
from app.repositories.producto_repository import ProductoRepository
from app.repositories.proveedor_repository import ProveedorRepository
from app.schemas.producto import ProductoCreate, ProductoUpdate
from app.utils.productos import calculate_stock_status


class ProductoService:
    """Orquesta los casos de uso del módulo de productos."""

    def __init__(self, db: Session) -> None:
        self.repository = ProductoRepository(db)
        # Repos auxiliares para validar las relaciones (categoría/proveedor).
        self.categoria_repository = CategoriaRepository(db)
        self.proveedor_repository = ProveedorRepository(db)

    # ------------------------------------------------------------------
    # Helpers internos
    # ------------------------------------------------------------------
    def _get_or_404(self, producto_id: int) -> Producto:
        """Devuelve el producto activo o lanza ProductoNotFoundError (404)."""
        producto = self.repository.get_by_id(producto_id)
        if producto is None:
            raise ProductoNotFoundError()
        return producto

    def _validar_categoria(self, categoria_id: int) -> None:
        """Lanza CategoriaNotFoundError si la categoría no existe."""
        if self.categoria_repository.get_by_id(categoria_id) is None:
            raise CategoriaNotFoundError()

    def _validar_proveedor(self, proveedor_id: int) -> None:
        """Lanza ProveedorNotFoundError si el proveedor no existe."""
        if self.proveedor_repository.get_by_id(proveedor_id) is None:
            raise ProveedorNotFoundError()

    # ------------------------------------------------------------------
    # Casos de uso
    # ------------------------------------------------------------------
    def create(self, data: ProductoCreate) -> Producto:
        """
        Registra un producto.

        Pasos:
            1. Validar que la categoría y el proveedor existan.
            2. Generar el código automático (P0001, P0002, ...).
            3. Calcular el estado según el stock.
            4. Persistir.

        Raises:
            CategoriaNotFoundError / ProveedorNotFoundError si las relaciones
            no existen.
        """
        self._validar_categoria(data.categoria_id)
        self._validar_proveedor(data.proveedor_id)

        codigo = self.repository.generate_code()
        estado = calculate_stock_status(data.stock, data.stock_minimo)

        return self.repository.create_producto(
            codigo=codigo,
            nombre=data.nombre,
            marca=data.marca,
            modelo=data.modelo,
            categoria_id=data.categoria_id,
            proveedor_id=data.proveedor_id,
            precio_compra=data.precio_compra,
            precio_venta=data.precio_venta,
            stock=data.stock,
            stock_minimo=data.stock_minimo,
            estado=estado,
            representacion=data.representacion.value,
            descripcion=data.descripcion,
            ficha_tecnica=data.ficha_tecnica,
        )

    def list(
        self,
        search: Optional[str] = None,
        categoria: Optional[int] = None,
        marca: Optional[str] = None,
        proveedor: Optional[int] = None,
        estado: Optional[str] = None,
        destacado: Optional[bool] = None,
        activo: Optional[bool] = True,
        orden: Optional[str] = None,
    ) -> Sequence[Producto]:
        """Lista TODOS los productos con filtros opcionales combinables."""
        return self.repository.get_all(
            search=search,
            categoria_id=categoria,
            marca=marca,
            proveedor_id=proveedor,
            estado=estado,
            destacado=destacado,
            activo=activo,
            orden=orden,
        )

    def list_paginated(
        self,
        page: int,
        page_size: int,
        search: Optional[str] = None,
        categoria: Optional[int] = None,
        marca: Optional[str] = None,
        proveedor: Optional[int] = None,
        estado: Optional[str] = None,
        destacado: Optional[bool] = None,
        activo: Optional[bool] = True,
        orden: Optional[str] = None,
    ) -> tuple[Sequence[Producto], int]:
        """
        Devuelve una página de productos (filtros combinables) y el total de
        coincidencias. Pensado para el panel admin: filtra por categoría y
        marca y pagina de a `page_size` (por defecto 10).
        """
        return self.repository.get_paginated(
            page=page,
            page_size=page_size,
            search=search,
            categoria_id=categoria,
            marca=marca,
            proveedor_id=proveedor,
            estado=estado,
            destacado=destacado,
            activo=activo,
            orden=orden,
        )

    def marcas(self, categoria: Optional[int] = None) -> Sequence[str]:
        """Marcas distintas (opcionalmente de una categoría) para el filtro."""
        return self.repository.marcas(categoria_id=categoria)

    def search(self, termino: str) -> Sequence[Producto]:
        """Búsqueda por nombre, código o marca (coincidencia parcial)."""
        return self.repository.search(termino)

    def generar_reporte_pdf(
        self,
        search: Optional[str] = None,
        categoria: Optional[int] = None,
        proveedor: Optional[int] = None,
        estado: Optional[str] = None,
    ) -> tuple[bytes, str]:
        """
        Genera un reporte PDF del inventario aplicando los mismos filtros que
        el listado.

        Returns:
            (pdf_bytes, filename) listos para devolver como descarga.
        """
        productos = self.repository.get_all(
            search=search,
            categoria_id=categoria,
            proveedor_id=proveedor,
            estado=estado,
        )

        # Nombres legibles de los filtros (categoría/proveedor) para el encabezado.
        categoria_nombre = None
        if categoria is not None:
            cat = self.categoria_repository.get_by_id(categoria)
            categoria_nombre = cat.nombre if cat else f"ID {categoria}"
        proveedor_nombre = None
        if proveedor is not None:
            prov = self.proveedor_repository.get_by_id(proveedor)
            proveedor_nombre = prov.nombre if prov else f"ID {proveedor}"

        pdf_bytes = generate_reporte_productos_pdf(
            productos,
            search=search,
            categoria=categoria_nombre,
            proveedor=proveedor_nombre,
            estado=estado,
        )
        return pdf_bytes, reporte_filename()

    def get(self, producto_id: int) -> Producto:
        """Devuelve un producto por id o lanza 404 si no existe/está inactivo."""
        return self._get_or_404(producto_id)

    def update(self, producto_id: int, data: ProductoUpdate) -> Producto:
        """
        Actualiza parcialmente un producto y RECALCULA el estado si cambió el
        stock o el stock mínimo.

        Solo se aplican los campos enviados. Si se cambian las relaciones,
        se valida que existan.

        Raises:
            ProductoNotFoundError: si el producto no existe.
            CategoriaNotFoundError / ProveedorNotFoundError: si las nuevas
            relaciones no existen.
        """
        producto = self._get_or_404(producto_id)
        cambios = data.model_dump(exclude_unset=True)

        # Validar relaciones solo si se están modificando.
        if "categoria_id" in cambios and cambios["categoria_id"] is not None:
            self._validar_categoria(cambios["categoria_id"])
        if "proveedor_id" in cambios and cambios["proveedor_id"] is not None:
            self._validar_proveedor(cambios["proveedor_id"])

        # Recalcular el estado si cambia el stock o el stock mínimo.
        if "stock" in cambios or "stock_minimo" in cambios:
            nuevo_stock = cambios.get("stock", producto.stock)
            nuevo_minimo = cambios.get("stock_minimo", producto.stock_minimo)
            cambios["estado"] = calculate_stock_status(nuevo_stock, nuevo_minimo)

        # Normalizar el enum de representación a su valor de texto para la BD.
        if cambios.get("representacion") is not None:
            cambios["representacion"] = cambios["representacion"].value

        if not cambios:
            return producto

        return self.repository.update(producto, cambios)

    def toggle_activo(self, producto_id: int, activo: bool) -> Producto:
        """
        Activa o desactiva un producto (soft delete reversible).

        A diferencia de `delete`/`update`, busca el producto SIN filtrar por
        estado, para poder reactivar uno que estaba desactivado.

        Raises:
            ProductoNotFoundError: si el producto no existe (ni activo ni inactivo).
        """
        producto = self.repository.get_by_id_any(producto_id)
        if producto is None:
            raise ProductoNotFoundError()
        return self.repository.set_active(producto, activo)

    def delete(self, producto_id: int) -> None:
        """
        Elimina un producto mediante SOFT DELETE (is_active = False).

        Raises:
            ProductoNotFoundError: si el producto no existe o ya está inactivo.
        """
        producto = self._get_or_404(producto_id)
        self.repository.delete(producto)
