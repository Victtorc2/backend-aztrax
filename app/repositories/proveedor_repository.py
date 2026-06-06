"""
Repositorio de proveedores.

Encapsula TODO el acceso a datos de la tabla `proveedores`. Los servicios
trabajan con estos métodos de alto nivel sin escribir SQL ni conocer detalles
de SQLAlchemy, lo que mantiene la lógica de negocio limpia y testeable.
"""

from typing import Any, Optional, Sequence

from sqlalchemy import func, inspect, or_, select, text
from sqlalchemy.orm import Session

from app.models.proveedor import Proveedor


class ProveedorRepository:
    """Acceso a datos para la entidad Proveedor."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Lectura
    # ------------------------------------------------------------------
    def get_all(self) -> Sequence[Proveedor]:
        """
        Devuelve todos los proveedores ordenados por fecha descendente.

        Se añade `id` descendente como desempate para un orden estable y
        determinista cuando varios comparten el mismo `created_at`.
        """
        stmt = select(Proveedor).order_by(
            Proveedor.created_at.desc(), Proveedor.id.desc()
        )
        return self.db.scalars(stmt).all()

    def get_by_id(self, proveedor_id: int) -> Optional[Proveedor]:
        """Devuelve un proveedor por su id, o None si no existe."""
        return self.db.get(Proveedor, proveedor_id)

    def search(self, termino: str) -> Sequence[Proveedor]:
        """
        Busca proveedores por NOMBRE o RUC (coincidencia parcial), sin
        distinguir mayúsculas/minúsculas. Ordena por fecha descendente.

        Ejemplo: search("norte") -> ["Distribuidora Norte", ...]
        """
        patron = f"%{termino.strip().lower()}%"
        stmt = (
            select(Proveedor)
            .where(
                or_(
                    func.lower(Proveedor.nombre).like(patron),
                    func.lower(Proveedor.ruc).like(patron),
                )
            )
            .order_by(Proveedor.created_at.desc(), Proveedor.id.desc())
        )
        return self.db.scalars(stmt).all()

    def exists_by_name(
        self, nombre: str, exclude_id: Optional[int] = None
    ) -> bool:
        """
        Indica si ya existe un proveedor con ese nombre, ignorando
        mayúsculas/minúsculas y espacios sobrantes.

        Args:
            nombre: Nombre a comprobar.
            exclude_id: Id a excluir (útil al actualizar, para no considerar
                        al propio proveedor como duplicado).
        """
        nombre_normalizado = " ".join(nombre.split()).lower()
        stmt = select(Proveedor.id).where(
            func.lower(Proveedor.nombre) == nombre_normalizado
        )
        if exclude_id is not None:
            stmt = stmt.where(Proveedor.id != exclude_id)
        return self.db.scalar(stmt) is not None

    def exists_by_ruc(
        self, ruc: str, exclude_id: Optional[int] = None
    ) -> bool:
        """
        Indica si ya existe un proveedor con ese RUC.

        Args:
            ruc: RUC a comprobar (ya normalizado por el schema).
            exclude_id: Id a excluir (útil al actualizar).
        """
        stmt = select(Proveedor.id).where(Proveedor.ruc == ruc.strip())
        if exclude_id is not None:
            stmt = stmt.where(Proveedor.id != exclude_id)
        return self.db.scalar(stmt) is not None

    # ------------------------------------------------------------------
    # Escritura
    # ------------------------------------------------------------------
    def create_proveedor(
        self,
        nombre: str,
        telefono: Optional[str] = None,
        direccion: Optional[str] = None,
        ruc: Optional[str] = None,
        observaciones: Optional[str] = None,
    ) -> Proveedor:
        """Crea y persiste un nuevo proveedor (datos ya normalizados)."""
        proveedor = Proveedor(
            nombre=nombre,
            telefono=telefono,
            direccion=direccion,
            ruc=ruc,
            observaciones=observaciones,
        )
        self.db.add(proveedor)
        self.db.commit()
        self.db.refresh(proveedor)  # recarga id y created_at generados por la BD
        return proveedor

    def update(self, proveedor: Proveedor, cambios: dict[str, Any]) -> Proveedor:
        """
        Aplica una actualización PARCIAL a un proveedor.

        Args:
            proveedor: Instancia existente a modificar.
            cambios: Diccionario {campo: valor} con SOLO los campos que el
                     cliente envió (ya validados/normalizados por el schema).

        Returns:
            El proveedor actualizado y persistido.
        """
        for campo, valor in cambios.items():
            setattr(proveedor, campo, valor)
        self.db.commit()
        self.db.refresh(proveedor)
        return proveedor

    def delete(self, proveedor: Proveedor) -> None:
        """Elimina el proveedor de la base de datos."""
        self.db.delete(proveedor)
        self.db.commit()

    # ------------------------------------------------------------------
    # Integración futura con productos
    # ------------------------------------------------------------------
    def has_associated_products(self, proveedor_id: int) -> bool:
        """
        Indica si el proveedor tiene productos asociados.

        Lógica preparada para fases futuras: el módulo de productos creará una
        tabla `productos` con una columna `proveedor_id`. Mientras esa tabla no
        exista, este método devuelve False de forma segura. En cuanto exista,
        la comprobación pasa a contar los productos que referencian a este
        proveedor SIN necesidad de tocar este código.
        """
        inspector = inspect(self.db.get_bind())
        if "productos" not in inspector.get_table_names():
            return False

        total = self.db.execute(
            text("SELECT COUNT(*) FROM productos WHERE proveedor_id = :pid"),
            {"pid": proveedor_id},
        ).scalar()
        return bool(total)
