"""producto representacion (unidad/sobre/caja/...)

Agrega el campo opcional `representacion` al producto, para indicar cómo se
vende (unidad, sobre, caja, paquete, blister, docena, par, kit). Es una lista
cerrada validada en la capa de schema; en la BD se guarda como texto corto.

Revision ID: 0014_producto_representacion
Revises: 0013_detalle_venta_linea_libre
Create Date: 2026-06-08 10:05:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0014_producto_representacion"
down_revision: Union[str, None] = "0013_detalle_venta_linea_libre"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "productos",
        sa.Column(
            "representacion",
            sa.String(length=20),
            nullable=False,
            server_default="unidad",
        ),
    )


def downgrade() -> None:
    op.drop_column("productos", "representacion")
