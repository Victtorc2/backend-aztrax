"""fidelizacion: puntos del cliente, cumpleanos y movimientos_puntos

Agrega:
- `clientes.fecha_nacimiento` (opcional) para saludos/promos de cumpleaños.
- `clientes.puntos` (saldo de puntos de fidelización, default 0).
- tabla `movimientos_puntos` con el historial de puntos ganados/canjeados.

Revision ID: 0015_fidelizacion_puntos
Revises: 0014_producto_representacion
Create Date: 2026-06-10 22:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0015_fidelizacion_puntos"
down_revision: Union[str, None] = "0014_producto_representacion"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "clientes",
        sa.Column("fecha_nacimiento", sa.Date(), nullable=True),
    )
    op.add_column(
        "clientes",
        sa.Column(
            "puntos", sa.Integer(), nullable=False, server_default="0"
        ),
    )

    op.create_table(
        "movimientos_puntos",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("cliente_id", sa.Integer(), nullable=False),
        sa.Column("tipo", sa.String(length=20), nullable=False),
        sa.Column("puntos", sa.Integer(), nullable=False),
        sa.Column("venta_id", sa.Integer(), nullable=True),
        sa.Column("descripcion", sa.String(length=255), nullable=True),
        sa.Column(
            "fecha",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        op.f("ix_movimientos_puntos_cliente_id"),
        "movimientos_puntos",
        ["cliente_id"],
    )
    op.create_index(
        op.f("ix_movimientos_puntos_venta_id"),
        "movimientos_puntos",
        ["venta_id"],
    )
    if op.get_bind().dialect.name != "sqlite":
        op.create_foreign_key(
            "fk_mov_puntos_cliente",
            "movimientos_puntos",
            "clientes",
            ["cliente_id"],
            ["id"],
        )
        op.create_foreign_key(
            "fk_mov_puntos_venta",
            "movimientos_puntos",
            "ventas",
            ["venta_id"],
            ["id"],
        )


def downgrade() -> None:
    if op.get_bind().dialect.name != "sqlite":
        op.drop_constraint(
            "fk_mov_puntos_venta", "movimientos_puntos", type_="foreignkey"
        )
        op.drop_constraint(
            "fk_mov_puntos_cliente", "movimientos_puntos", type_="foreignkey"
        )
    op.drop_index(
        op.f("ix_movimientos_puntos_venta_id"), table_name="movimientos_puntos"
    )
    op.drop_index(
        op.f("ix_movimientos_puntos_cliente_id"),
        table_name="movimientos_puntos",
    )
    op.drop_table("movimientos_puntos")
    op.drop_column("clientes", "puntos")
    op.drop_column("clientes", "fecha_nacimiento")
