"""
Base declarativa de SQLAlchemy.

Todos los modelos ORM heredan de `Base`. Mantenerla en su propio módulo
evita importaciones circulares entre los modelos y la sesión.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Clase base para todos los modelos ORM del sistema."""

    pass
