"""detalle_venta linea libre (producto opcional + descripcion libre)

Permite registrar en una venta una línea "libre": un producto NO registrado en
el inventario, escrito a mano (descripcion_libre) con su precio. Para eso,
`producto_id` pasa a ser opcional y se agrega `descripcion_libre`.

Revision ID: 0013_detalle_venta_linea_libre
Revises: 0012_producto_descripcion
Create Date: 2026-06-08 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0013_detalle_venta_linea_libre"
down_revision: Union[str, None] = "0012_producto_descripcion"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # batch_alter_table: en MySQL emite ALTER directo; en SQLite (que no soporta
    # ALTER COLUMN) recrea la tabla. Así la migración es portable.
    with op.batch_alter_table("detalle_venta") as batch:
        # producto_id pasa a NULL para permitir líneas libres (sin producto).
        batch.alter_column(
            "producto_id",
            existing_type=sa.Integer(),
            nullable=True,
        )
        # Descripción escrita a mano para las líneas libres.
        batch.add_column(
            sa.Column("descripcion_libre", sa.String(length=150), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("detalle_venta") as batch:
        batch.drop_column("descripcion_libre")
        batch.alter_column(
            "producto_id",
            existing_type=sa.Integer(),
            nullable=False,
        )
