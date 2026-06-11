"""caja diaria: tablas cajas y movimientos_caja

Revision ID: 0016_caja_diaria
Revises: 0015_fidelizacion_puntos
Create Date: 2026-06-10 22:35:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0016_caja_diaria"
down_revision: Union[str, None] = "0015_fidelizacion_puntos"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cajas",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "estado",
            sa.String(length=20),
            nullable=False,
            server_default="abierta",
        ),
        sa.Column("monto_inicial", sa.Numeric(12, 2), nullable=False),
        sa.Column("monto_declarado", sa.Numeric(12, 2), nullable=True),
        sa.Column("monto_esperado", sa.Numeric(12, 2), nullable=True),
        sa.Column("diferencia", sa.Numeric(12, 2), nullable=True),
        sa.Column("nota_apertura", sa.String(length=255), nullable=True),
        sa.Column("nota_cierre", sa.String(length=255), nullable=True),
        sa.Column(
            "abierta_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("cerrada_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(op.f("ix_cajas_estado"), "cajas", ["estado"])
    op.create_index(op.f("ix_cajas_abierta_at"), "cajas", ["abierta_at"])

    op.create_table(
        "movimientos_caja",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("caja_id", sa.Integer(), nullable=False),
        sa.Column("tipo", sa.String(length=20), nullable=False),
        sa.Column("monto", sa.Numeric(12, 2), nullable=False),
        sa.Column("motivo", sa.String(length=255), nullable=True),
        sa.Column(
            "fecha",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        op.f("ix_movimientos_caja_caja_id"), "movimientos_caja", ["caja_id"]
    )
    if op.get_bind().dialect.name != "sqlite":
        op.create_foreign_key(
            "fk_mov_caja_caja",
            "movimientos_caja",
            "cajas",
            ["caja_id"],
            ["id"],
        )


def downgrade() -> None:
    if op.get_bind().dialect.name != "sqlite":
        op.drop_constraint(
            "fk_mov_caja_caja", "movimientos_caja", type_="foreignkey"
        )
    op.drop_index(
        op.f("ix_movimientos_caja_caja_id"), table_name="movimientos_caja"
    )
    op.drop_table("movimientos_caja")
    op.drop_index(op.f("ix_cajas_abierta_at"), table_name="cajas")
    op.drop_index(op.f("ix_cajas_estado"), table_name="cajas")
    op.drop_table("cajas")
