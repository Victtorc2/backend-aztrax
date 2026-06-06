"""crear tabla proveedores

Revision ID: 0003_create_proveedores
Revises: 0002_create_categorias
Create Date: 2026-05-25 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# Identificadores de la revisión.
revision: str = "0003_create_proveedores"
down_revision: Union[str, None] = "0002_create_categorias"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Crea la tabla `proveedores` y sus índices."""
    op.create_table(
        "proveedores",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nombre", sa.String(length=150), nullable=False),
        sa.Column("telefono", sa.String(length=30), nullable=True),
        sa.Column("direccion", sa.String(length=255), nullable=True),
        sa.Column("ruc", sa.String(length=20), nullable=True),
        sa.Column("observaciones", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_proveedores_id"), "proveedores", ["id"], unique=False)
    op.create_index(
        op.f("ix_proveedores_nombre"), "proveedores", ["nombre"], unique=False
    )
    # RUC indexado y único (permite múltiples NULL en PostgreSQL).
    op.create_index(
        op.f("ix_proveedores_ruc"), "proveedores", ["ruc"], unique=True
    )


def downgrade() -> None:
    """Elimina la tabla `proveedores` y sus índices."""
    op.drop_index(op.f("ix_proveedores_ruc"), table_name="proveedores")
    op.drop_index(op.f("ix_proveedores_nombre"), table_name="proveedores")
    op.drop_index(op.f("ix_proveedores_id"), table_name="proveedores")
    op.drop_table("proveedores")
