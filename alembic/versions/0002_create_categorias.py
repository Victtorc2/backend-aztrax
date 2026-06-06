"""crear tabla categorias

Revision ID: 0002_create_categorias
Revises: 0001_create_usuarios
Create Date: 2026-05-25 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# Identificadores de la revisión.
revision: str = "0002_create_categorias"
down_revision: Union[str, None] = "0001_create_usuarios"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Crea la tabla `categorias` y sus índices."""
    op.create_table(
        "categorias",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nombre", sa.String(length=120), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_categorias_id"), "categorias", ["id"], unique=False)
    op.create_index(
        op.f("ix_categorias_nombre"), "categorias", ["nombre"], unique=True
    )


def downgrade() -> None:
    """Elimina la tabla `categorias` y sus índices."""
    op.drop_index(op.f("ix_categorias_nombre"), table_name="categorias")
    op.drop_index(op.f("ix_categorias_id"), table_name="categorias")
    op.drop_table("categorias")
