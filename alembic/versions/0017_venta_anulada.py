"""venta: anulacion (devolucion total)

Agrega a `ventas` las columnas de anulación: `anulada` (bandera), `anulada_at`
y `motivo_anulacion`. Una venta anulada se conserva pero deja de contar en los
reportes; al anular se repone el stock y se revierten los puntos.

Revision ID: 0017_venta_anulada
Revises: 0016_caja_diaria
Create Date: 2026-06-10 22:40:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0017_venta_anulada"
down_revision: Union[str, None] = "0016_caja_diaria"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ventas",
        sa.Column(
            "anulada",
            sa.Boolean(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "ventas",
        sa.Column("anulada_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "ventas",
        sa.Column("motivo_anulacion", sa.String(length=255), nullable=True),
    )
    op.create_index(op.f("ix_ventas_anulada"), "ventas", ["anulada"])


def downgrade() -> None:
    op.drop_index(op.f("ix_ventas_anulada"), table_name="ventas")
    op.drop_column("ventas", "motivo_anulacion")
    op.drop_column("ventas", "anulada_at")
    op.drop_column("ventas", "anulada")
