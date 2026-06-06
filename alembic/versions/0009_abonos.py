"""tabla abonos (pagos de credito)

Revision ID: 0009_abonos
Revises: 0008_clientes_credito
Create Date: 2026-06-02 12:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0009_abonos"
down_revision: Union[str, None] = "0008_clientes_credito"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "abonos",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("venta_id", sa.Integer(), nullable=False),
        sa.Column("monto", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "metodo_pago",
            sa.String(length=20),
            nullable=False,
            server_default="efectivo",
        ),
        sa.Column("nota", sa.String(length=255), nullable=True),
        sa.Column(
            "fecha",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(op.f("ix_abonos_venta_id"), "abonos", ["venta_id"])
    if op.get_bind().dialect.name != "sqlite":
        op.create_foreign_key(
            "fk_abonos_venta", "abonos", "ventas", ["venta_id"], ["id"]
        )


def downgrade() -> None:
    if op.get_bind().dialect.name != "sqlite":
        op.drop_constraint("fk_abonos_venta", "abonos", type_="foreignkey")
    op.drop_index(op.f("ix_abonos_venta_id"), table_name="abonos")
    op.drop_table("abonos")
