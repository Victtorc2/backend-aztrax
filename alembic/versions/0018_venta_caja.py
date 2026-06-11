"""venta: vincular a la sesion de caja (caja_id)

Agrega `ventas.caja_id` (FK opcional a cajas) para que el arqueo de caja sume
exactamente las ventas registradas durante la sesión, sin depender de rangos
de tiempo.

Revision ID: 0018_venta_caja
Revises: 0017_venta_anulada
Create Date: 2026-06-10 22:50:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0018_venta_caja"
down_revision: Union[str, None] = "0017_venta_anulada"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("ventas", sa.Column("caja_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_ventas_caja_id"), "ventas", ["caja_id"])
    if op.get_bind().dialect.name != "sqlite":
        op.create_foreign_key(
            "fk_ventas_caja", "ventas", "cajas", ["caja_id"], ["id"]
        )


def downgrade() -> None:
    if op.get_bind().dialect.name != "sqlite":
        op.drop_constraint("fk_ventas_caja", "ventas", type_="foreignkey")
    op.drop_index(op.f("ix_ventas_caja_id"), table_name="ventas")
    op.drop_column("ventas", "caja_id")
