"""ajustes de saldo: tabla ajustes_saldo

Crea la tabla `ajustes_saldo` para agregar o modificar manualmente el saldo de
un método de pago (efectivo/yape), guardando un monto con signo y un motivo
obligatorio (la especificación del ajuste).

Revision ID: 0021_ajustes_saldo
Revises: 0020_gastos
Create Date: 2026-07-01 00:10:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0021_ajustes_saldo"
down_revision: Union[str, None] = "0020_gastos"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ajustes_saldo",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("metodo_pago", sa.String(length=20), nullable=False),
        sa.Column("monto", sa.Numeric(12, 2), nullable=False),
        sa.Column("motivo", sa.String(length=255), nullable=False),
        sa.Column(
            "fecha",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        op.f("ix_ajustes_saldo_metodo_pago"), "ajustes_saldo", ["metodo_pago"]
    )
    op.create_index(op.f("ix_ajustes_saldo_fecha"), "ajustes_saldo", ["fecha"])


def downgrade() -> None:
    op.drop_index(op.f("ix_ajustes_saldo_fecha"), table_name="ajustes_saldo")
    op.drop_index(
        op.f("ix_ajustes_saldo_metodo_pago"), table_name="ajustes_saldo"
    )
    op.drop_table("ajustes_saldo")
