"""producto destacado

Revision ID: 0011_producto_destacado
Revises: 0010_imagenes_banners
Create Date: 2026-06-03 14:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0011_producto_destacado"
down_revision: Union[str, None] = "0010_imagenes_banners"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "productos",
        sa.Column("destacado", sa.Boolean(), nullable=False, server_default=sa.text("0")),
    )


def downgrade() -> None:
    op.drop_column("productos", "destacado")
