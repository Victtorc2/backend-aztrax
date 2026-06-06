"""producto descripcion y ficha tecnica

Revision ID: 0012_producto_descripcion
Revises: 0011_producto_destacado
Create Date: 2026-06-03 16:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0012_producto_descripcion"
down_revision: Union[str, None] = "0011_producto_destacado"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("productos", sa.Column("descripcion", sa.Text(), nullable=True))
    op.add_column("productos", sa.Column("ficha_tecnica", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("productos", "ficha_tecnica")
    op.drop_column("productos", "descripcion")
