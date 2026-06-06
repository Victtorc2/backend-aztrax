"""
Repositorio de categorías.

Encapsula TODO el acceso a datos de la tabla `categorias`. Los servicios
trabajan con estos métodos de alto nivel sin escribir SQL ni conocer detalles
de SQLAlchemy, lo que mantiene la lógica de negocio limpia y testeable.
"""

from typing import Optional, Sequence

from sqlalchemy import func, inspect, select, text
from sqlalchemy.orm import Session

from app.models.categoria import Categoria


class CategoriaRepository:
    """Acceso a datos para la entidad Categoría."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Lectura
    # ------------------------------------------------------------------
    def get_all(self) -> Sequence[Categoria]:
        """
        Devuelve todas las categorías ordenadas por fecha descendente.

        Se añade `id` descendente como criterio de desempate para garantizar
        un orden estable y determinista cuando varias categorías comparten el
        mismo `created_at` (algo posible bajo inserciones muy seguidas).
        """
        stmt = select(Categoria).order_by(
            Categoria.created_at.desc(), Categoria.id.desc()
        )
        return self.db.scalars(stmt).all()

    def get_by_id(self, categoria_id: int) -> Optional[Categoria]:
        """Devuelve una categoría por su id, o None si no existe."""
        return self.db.get(Categoria, categoria_id)

    def search(self, termino: str) -> Sequence[Categoria]:
        """
        Busca categorías cuyo nombre contenga `termino` (coincidencia parcial),
        sin distinguir mayúsculas/minúsculas. Ordena por fecha descendente.

        Ejemplo: search("beb") -> ["Bebidas frías", "Bebidas", ...]
        """
        patron = f"%{termino.strip().lower()}%"
        stmt = (
            select(Categoria)
            .where(func.lower(Categoria.nombre).like(patron))
            .order_by(Categoria.created_at.desc(), Categoria.id.desc())
        )
        return self.db.scalars(stmt).all()

    def exists_by_name(
        self, nombre: str, exclude_id: Optional[int] = None
    ) -> bool:
        """
        Indica si ya existe una categoría con ese nombre, ignorando
        mayúsculas/minúsculas y espacios sobrantes.

        Args:
            nombre: Nombre a comprobar (se normaliza internamente).
            exclude_id: Id a excluir de la comprobación. Útil al actualizar,
                        para no considerar la propia categoría como duplicada.
        """
        nombre_normalizado = " ".join(nombre.split()).lower()
        stmt = select(Categoria.id).where(
            func.lower(Categoria.nombre) == nombre_normalizado
        )
        if exclude_id is not None:
            stmt = stmt.where(Categoria.id != exclude_id)
        return self.db.scalar(stmt) is not None

    # ------------------------------------------------------------------
    # Escritura
    # ------------------------------------------------------------------
    def create_categoria(self, nombre: str) -> Categoria:
        """Crea y persiste una nueva categoría con el nombre dado (ya normalizado)."""
        categoria = Categoria(nombre=nombre)
        self.db.add(categoria)
        self.db.commit()
        self.db.refresh(categoria)  # recarga id y created_at generados por la BD
        return categoria

    def update(self, categoria: Categoria, nombre: str) -> Categoria:
        """Actualiza el nombre de una categoría existente y persiste el cambio."""
        categoria.nombre = nombre
        self.db.commit()
        self.db.refresh(categoria)
        return categoria

    def delete(self, categoria: Categoria) -> None:
        """Elimina la categoría de la base de datos."""
        self.db.delete(categoria)
        self.db.commit()

    # ------------------------------------------------------------------
    # Integración futura con productos
    # ------------------------------------------------------------------
    def has_associated_products(self, categoria_id: int) -> bool:
        """
        Indica si la categoría tiene productos asociados.

        Lógica preparada para fases futuras: el módulo de productos creará
        una tabla `productos` con una columna `categoria_id`. Mientras esa
        tabla no exista, este método devuelve False de forma segura.

        En cuanto exista la tabla, la comprobación pasa a contar los productos
        que referencian a esta categoría, SIN necesidad de tocar este código.

        Returns:
            True si existe al menos un producto asociado; False en caso contrario.
        """
        inspector = inspect(self.db.get_bind())
        if "productos" not in inspector.get_table_names():
            # El módulo de productos aún no existe: no hay nada asociado.
            return False

        # La tabla ya existe: contamos productos con esta categoría.
        total = self.db.execute(
            text("SELECT COUNT(*) FROM productos WHERE categoria_id = :cid"),
            {"cid": categoria_id},
        ).scalar()
        return bool(total)
