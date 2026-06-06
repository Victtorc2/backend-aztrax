"""imagen_url en productos y tabla banners

Revision ID: 0010_imagenes_banners
Revises: 0009_abonos
Create Date: 2026-06-03 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0010_imagenes_banners"
down_revision: Union[str, None] = "0009_abonos"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Imagen de producto.
    op.add_column(
        "productos",
        sa.Column("imagen_url", sa.String(length=255), nullable=True),
    )

    # Tabla de banners promocionales.
    op.create_table(
        "banners",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("titulo", sa.String(length=150), nullable=False),
        sa.Column("descripcion", sa.String(length=255), nullable=True),
        sa.Column("imagen_url", sa.String(length=255), nullable=False),
        sa.Column("orden", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("banners")
    op.drop_column("productos", "imagen_url")
