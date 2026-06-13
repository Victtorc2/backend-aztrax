"""agregar columna color a productos

Añade `productos.color` (opcional, indexado). En el dominio de señuelos un
mismo modelo viene en varios colores; cada color es un producto distinto. El
campo `modelo` pasa a usarse para el modelo en sí y `color` para el color.

Revision ID: 0019_producto_color
Revises: 0018_venta_caja
Create Date: 2026-06-12 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0019_producto_color"
down_revision: Union[str, None] = "0018_venta_caja"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Añade la columna opcional `color` y su índice, y hace un backfill único:
    copia el valor de `modelo` a `color` en los productos existentes.

    Motivo: hasta ahora `modelo` guardaba el COLOR del señuelo. Al separar los
    conceptos, se preservan esos colores en la nueva columna `color`. NO se
    vacía `modelo` (se rellenará manualmente con el modelo real de cada
    producto). La condición `color IS NULL` mantiene la operación idempotente.
    """
    op.add_column(
        "productos",
        sa.Column("color", sa.String(length=100), nullable=True),
    )
    op.create_index(op.f("ix_productos_color"), "productos", ["color"], unique=False)
    op.execute(
        sa.text(
            "UPDATE productos SET color = modelo "
            "WHERE color IS NULL AND modelo IS NOT NULL"
        )
    )


def downgrade() -> None:
    """Revierte la columna `color`."""
    op.drop_index(op.f("ix_productos_color"), table_name="productos")
    op.drop_column("productos", "color")
