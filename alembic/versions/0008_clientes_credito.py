"""clientes + campos de credito en ventas + costo en detalle

Revision ID: 0008_clientes_credito
Revises: 0007_venta_metodo_pago
Create Date: 2026-06-02 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0008_clientes_credito"
down_revision: Union[str, None] = "0007_venta_metodo_pago"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Tabla clientes ---
    op.create_table(
        "clientes",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("nombre", sa.String(length=150), nullable=False, index=True),
        sa.Column("documento", sa.String(length=20), nullable=True),
        sa.Column("telefono", sa.String(length=20), nullable=True),
        sa.Column("email", sa.String(length=120), nullable=True),
        sa.Column("direccion", sa.String(length=200), nullable=True),
        sa.Column("nota", sa.String(length=255), nullable=True),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(op.f("ix_clientes_documento"), "clientes", ["documento"], unique=True)

    # --- Campos de crédito en ventas ---
    op.add_column(
        "ventas",
        sa.Column(
            "tipo_pago",
            sa.String(length=20),
            nullable=False,
            server_default="contado",
        ),
    )
    op.add_column("ventas", sa.Column("cliente_id", sa.Integer(), nullable=True))
    op.add_column(
        "ventas",
        sa.Column(
            "saldo_pendiente",
            sa.Numeric(12, 2),
            nullable=False,
            server_default="0.00",
        ),
    )
    op.create_index(op.f("ix_ventas_cliente_id"), "ventas", ["cliente_id"])
    # La FK se añade vía ALTER, que SQLite no soporta. En MySQL/PostgreSQL sí.
    # En SQLite (entorno de pruebas) la omitimos: la integridad la garantiza
    # la capa de aplicación.
    if op.get_bind().dialect.name != "sqlite":
        op.create_foreign_key(
            "fk_ventas_cliente", "ventas", "clientes", ["cliente_id"], ["id"]
        )

    # --- Costo congelado en cada línea (para rentabilidad) ---
    op.add_column(
        "detalle_venta",
        sa.Column(
            "costo_unitario",
            sa.Numeric(12, 2),
            nullable=False,
            server_default="0.00",
        ),
    )


def downgrade() -> None:
    op.drop_column("detalle_venta", "costo_unitario")
    if op.get_bind().dialect.name != "sqlite":
        op.drop_constraint("fk_ventas_cliente", "ventas", type_="foreignkey")
    op.drop_index(op.f("ix_ventas_cliente_id"), table_name="ventas")
    op.drop_column("ventas", "saldo_pendiente")
    op.drop_column("ventas", "cliente_id")
    op.drop_column("ventas", "tipo_pago")
    op.drop_index(op.f("ix_clientes_documento"), table_name="clientes")
    op.drop_table("clientes")
