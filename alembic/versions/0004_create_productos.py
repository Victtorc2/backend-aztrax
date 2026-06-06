"""crear tabla productos

Revision ID: 0004_create_productos
Revises: 0003_create_proveedores
Create Date: 2026-05-25 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# Identificadores de la revisión.
revision: str = "0004_create_productos"
down_revision: Union[str, None] = "0003_create_proveedores"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Crea la tabla `productos`, sus claves foráneas e índices."""
    op.create_table(
        "productos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("codigo", sa.String(length=20), nullable=False),
        sa.Column("nombre", sa.String(length=150), nullable=False),
        sa.Column("marca", sa.String(length=100), nullable=False),
        sa.Column("categoria_id", sa.Integer(), nullable=False),
        sa.Column("proveedor_id", sa.Integer(), nullable=False),
        sa.Column("precio_compra", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("precio_venta", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("stock", sa.Integer(), nullable=False),
        sa.Column("stock_minimo", sa.Integer(), nullable=False),
        sa.Column("estado", sa.String(length=20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["categoria_id"], ["categorias.id"]),
        sa.ForeignKeyConstraint(["proveedor_id"], ["proveedores.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_productos_id"), "productos", ["id"], unique=False)
    op.create_index(op.f("ix_productos_codigo"), "productos", ["codigo"], unique=True)
    op.create_index(op.f("ix_productos_nombre"), "productos", ["nombre"], unique=False)
    op.create_index(op.f("ix_productos_marca"), "productos", ["marca"], unique=False)
    op.create_index(
        op.f("ix_productos_categoria_id"), "productos", ["categoria_id"], unique=False
    )
    op.create_index(
        op.f("ix_productos_proveedor_id"), "productos", ["proveedor_id"], unique=False
    )
    op.create_index(
        op.f("ix_productos_is_active"), "productos", ["is_active"], unique=False
    )


def downgrade() -> None:
    """Elimina la tabla `productos` y sus índices."""
    op.drop_index(op.f("ix_productos_is_active"), table_name="productos")
    op.drop_index(op.f("ix_productos_proveedor_id"), table_name="productos")
    op.drop_index(op.f("ix_productos_categoria_id"), table_name="productos")
    op.drop_index(op.f("ix_productos_marca"), table_name="productos")
    op.drop_index(op.f("ix_productos_nombre"), table_name="productos")
    op.drop_index(op.f("ix_productos_codigo"), table_name="productos")
    op.drop_index(op.f("ix_productos_id"), table_name="productos")
    op.drop_table("productos")
