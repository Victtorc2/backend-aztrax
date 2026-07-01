"""
Paquete de modelos ORM.

Importar aquí todos los modelos garantiza que queden registrados en
`Base.metadata` y en el registry de SQLAlchemy. Esto es necesario para
`create_all()`, para que Alembic detecte las tablas y para que las
relaciones por nombre (back_populates) se resuelvan correctamente.
"""

from app.models.categoria import Categoria
from app.models.proveedor import Proveedor
from app.models.producto import Producto
from app.models.venta import Venta, DetalleVenta, Abono
from app.models.cliente import Cliente
from app.models.puntos import MovimientoPuntos
from app.models.caja import Caja, MovimientoCaja
from app.models.gasto import Gasto
from app.models.ajuste_saldo import AjusteSaldo
from app.models.banner import Banner
from app.models.user import Usuario

__all__ = [
    "Usuario",
    "Categoria",
    "Proveedor",
    "Producto",
    "Venta",
    "DetalleVenta",
    "Abono",
    "Cliente",
    "MovimientoPuntos",
    "Caja",
    "MovimientoCaja",
    "Gasto",
    "AjusteSaldo",
    "Banner",
]
