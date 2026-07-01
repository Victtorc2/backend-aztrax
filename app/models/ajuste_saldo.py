"""
Modelo ORM de ajustes manuales del saldo: tabla `ajustes_saldo`.

El saldo por método se deriva de ventas + abonos − gastos. Un `AjusteSaldo`
permite corregir ese saldo manualmente: inyectar dinero (aporte de capital,
vuelto inicial, etc.) o fijar el saldo a un valor exacto tras un conteo real.

Cada ajuste guarda un `monto` CON SIGNO (positivo = sube el saldo, negativo =
lo baja) y un `motivo` obligatorio (la especificación de por qué se ajustó).
El saldo del método suma todos sus ajustes.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AjusteSaldo(Base):
    """Ajuste manual del saldo de un método de pago (con motivo)."""

    __tablename__ = "ajustes_saldo"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Método de pago cuyo saldo se ajusta: "efectivo" o "yape".
    metodo_pago: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True
    )

    # Monto con signo: positivo aumenta el saldo, negativo lo disminuye.
    monto: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    # Motivo / especificación del ajuste. Obligatorio.
    motivo: Mapped[str] = mapped_column(String(255), nullable=False)

    # Fecha y hora del ajuste (UTC), gestionada por la BD.
    fecha: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True,
        nullable=False,
    )

    def __repr__(self) -> str:  # pragma: no cover - solo depuración
        return (
            f"<AjusteSaldo id={self.id} metodo={self.metodo_pago!r} "
            f"monto={self.monto}>"
        )
