"""gastos: tabla de egresos de dinero con metodo de pago

Crea la tabla `gastos` para registrar salidas de dinero (pedidos/compras,
servicios, sueldos, etc.) con su método de pago, de modo que el saldo por
método (efectivo/yape) se pueda calcular y mantener actualizado.

Revision ID: 0020_gastos
Revises: 0019_producto_color
Create Date: 2026-07-01 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0020_gastos"
down_revision: Union[str, None] = "0019_producto_color"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "gastos",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "categoria",
            sa.String(length=30),
            nullable=False,
            server_default="otro",
        ),
        sa.Column("monto", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "metodo_pago",
            sa.String(length=20),
            nullable=False,
            server_default="efectivo",
        ),
        sa.Column("proveedor_id", sa.Integer(), nullable=True),
        sa.Column("descripcion", sa.String(length=255), nullable=True),
        sa.Column("caja_id", sa.Integer(), nullable=True),
        sa.Column(
            "fecha",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(op.f("ix_gastos_categoria"), "gastos", ["categoria"])
    op.create_index(op.f("ix_gastos_metodo_pago"), "gastos", ["metodo_pago"])
    op.create_index(op.f("ix_gastos_proveedor_id"), "gastos", ["proveedor_id"])
    op.create_index(op.f("ix_gastos_caja_id"), "gastos", ["caja_id"])
    op.create_index(op.f("ix_gastos_fecha"), "gastos", ["fecha"])

    if op.get_bind().dialect.name != "sqlite":
        op.create_foreign_key(
            "fk_gastos_proveedor",
            "gastos",
            "proveedores",
            ["proveedor_id"],
            ["id"],
        )
        op.create_foreign_key(
            "fk_gastos_caja",
            "gastos",
            "cajas",
            ["caja_id"],
            ["id"],
        )


def downgrade() -> None:
    if op.get_bind().dialect.name != "sqlite":
        op.drop_constraint("fk_gastos_caja", "gastos", type_="foreignkey")
        op.drop_constraint("fk_gastos_proveedor", "gastos", type_="foreignkey")
    op.drop_index(op.f("ix_gastos_fecha"), table_name="gastos")
    op.drop_index(op.f("ix_gastos_caja_id"), table_name="gastos")
    op.drop_index(op.f("ix_gastos_proveedor_id"), table_name="gastos")
    op.drop_index(op.f("ix_gastos_metodo_pago"), table_name="gastos")
    op.drop_index(op.f("ix_gastos_categoria"), table_name="gastos")
    op.drop_table("gastos")
