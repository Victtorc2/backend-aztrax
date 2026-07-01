"""
Modelo ORM de gastos / egresos de dinero: tabla `gastos`.

Un gasto registra una SALIDA de dinero del negocio: un pedido/compra a un
proveedor, el pago de un servicio, un sueldo, etc. Cada gasto lleva su método
de pago (efectivo o yape) para poder actualizar el saldo disponible por método.

A diferencia de `movimientos_caja` (que solo rastrea efectivo y solo dentro de
una sesión de caja), los gastos forman parte del "libro" global de dinero del
negocio y se restan del saldo por método sin depender de la caja del día. Aun
así, un gasto en efectivo hecho con la caja abierta se vincula a esa sesión
(`caja_id`) para que el arqueo siga cuadrando.
"""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.proveedor import Proveedor


class Gasto(Base):
    """Salida de dinero (egreso) con su método de pago."""

    __tablename__ = "gastos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Categoría del gasto: "pedido" (compra a proveedor), "servicio", "sueldo",
    # "alquiler" u "otro". Guardado como texto; se valida con un Enum en el
    # schema de entrada.
    categoria: Mapped[str] = mapped_column(
        String(30), nullable=False, default="otro", server_default="otro", index=True
    )

    # Monto del gasto (positivo).
    monto: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    # Método de pago con el que salió el dinero: "efectivo" o "yape".
    metodo_pago: Mapped[str] = mapped_column(
        String(20), nullable=False, default="efectivo", server_default="efectivo",
        index=True,
    )

    # Proveedor asociado (opcional; típico en un "pedido"/compra).
    proveedor_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("proveedores.id"), index=True, nullable=True
    )

    # Descripción libre (a qué correspondió el gasto).
    descripcion: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Sesión de caja a la que pertenece el gasto (solo cuando es en efectivo y
    # había una caja abierta al registrarlo). Permite descontarlo del arqueo.
    caja_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("cajas.id"), index=True, nullable=True
    )

    # Fecha y hora del gasto (UTC), gestionada por la BD.
    fecha: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True,
        nullable=False,
    )

    # Proveedor (cargado en la misma consulta cuando exista).
    proveedor: Mapped[Optional["Proveedor"]] = relationship(lazy="joined")

    def __repr__(self) -> str:  # pragma: no cover - solo depuración
        return (
            f"<Gasto id={self.id} categoria={self.categoria!r} "
            f"monto={self.monto} metodo={self.metodo_pago!r}>"
        )
