"""crear tablas ventas y detalle_venta

Revision ID: 0005_create_ventas
Revises: 0004_create_productos
Create Date: 2026-05-25 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005_create_ventas"
down_revision: Union[str, None] = "0004_create_productos"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Crea las tablas `ventas` y `detalle_venta` con sus índices y FKs."""
    op.create_table(
        "ventas",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("numero_boleta", sa.String(length=20), nullable=False),
        sa.Column("subtotal", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("descuento", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("descuento_tipo", sa.String(length=20), nullable=True),
        sa.Column("total", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column(
            "fecha",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ventas_id"), "ventas", ["id"], unique=False)
    op.create_index(
        op.f("ix_ventas_numero_boleta"), "ventas", ["numero_boleta"], unique=True
    )
    op.create_index(op.f("ix_ventas_fecha"), "ventas", ["fecha"], unique=False)

    op.create_table(
        "detalle_venta",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("venta_id", sa.Integer(), nullable=False),
        sa.Column("producto_id", sa.Integer(), nullable=False),
        sa.Column("cantidad", sa.Integer(), nullable=False),
        sa.Column("precio", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("subtotal", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.ForeignKeyConstraint(["venta_id"], ["ventas.id"]),
        sa.ForeignKeyConstraint(["producto_id"], ["productos.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_detalle_venta_id"), "detalle_venta", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_detalle_venta_venta_id"), "detalle_venta", ["venta_id"], unique=False
    )
    op.create_index(
        op.f("ix_detalle_venta_producto_id"),
        "detalle_venta",
        ["producto_id"],
        unique=False,
    )


def downgrade() -> None:
    """Elimina las tablas de ventas."""
    op.drop_index(op.f("ix_detalle_venta_producto_id"), table_name="detalle_venta")
    op.drop_index(op.f("ix_detalle_venta_venta_id"), table_name="detalle_venta")
    op.drop_index(op.f("ix_detalle_venta_id"), table_name="detalle_venta")
    op.drop_table("detalle_venta")
    op.drop_index(op.f("ix_ventas_fecha"), table_name="ventas")
    op.drop_index(op.f("ix_ventas_numero_boleta"), table_name="ventas")
    op.drop_index(op.f("ix_ventas_id"), table_name="ventas")
    op.drop_table("ventas")
