"""agregar columna modelo a productos

Revision ID: 0006_producto_modelo
Revises: 0005_create_ventas
Create Date: 2026-06-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0006_producto_modelo"
down_revision: Union[str, None] = "0005_create_ventas"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Añade la columna opcional `modelo` y su índice."""
    op.add_column(
        "productos",
        sa.Column("modelo", sa.String(length=100), nullable=True),
    )
    op.create_index(op.f("ix_productos_modelo"), "productos", ["modelo"], unique=False)


def downgrade() -> None:
    """Revierte la columna `modelo`."""
    op.drop_index(op.f("ix_productos_modelo"), table_name="productos")
    op.drop_column("productos", "modelo")
