"""agregar metodo_pago a ventas

Revision ID: 0007_venta_metodo_pago
Revises: 0006_producto_modelo
Create Date: 2026-06-02 00:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0007_venta_metodo_pago"
down_revision: Union[str, None] = "0006_producto_modelo"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Añade la columna `metodo_pago` con default "efectivo".

    El server_default garantiza que las ventas históricas (creadas antes de
    esta columna) queden con un método válido en lugar de NULL.
    """
    op.add_column(
        "ventas",
        sa.Column(
            "metodo_pago",
            sa.String(length=20),
            nullable=False,
            server_default="efectivo",
        ),
    )


def downgrade() -> None:
    """Revierte la columna `metodo_pago`."""
    op.drop_column("ventas", "metodo_pago")
