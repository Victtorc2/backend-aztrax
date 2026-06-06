"""
Configuración de la conexión a la base de datos.

Expone:
- `engine`: el motor de conexión a PostgreSQL.
- `SessionLocal`: la fábrica de sesiones.
- `get_db()`: dependencia de FastAPI que provee una sesión por request
  y garantiza que se cierre al terminar.
"""

from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

# Motor de conexión. `pool_pre_ping` evita usar conexiones muertas del pool.
# Usamos la URL normalizada (convierte mysql:// -> mysql+pymysql:// si el
# proveedor la entrega sin el driver explícito, como hace Railway).
engine = create_engine(
    settings.database_url_normalized,
    pool_pre_ping=True,
    future=True,
)

# Fábrica de sesiones. autoflush=False nos da control explícito sobre cuándo
# se sincroniza con la BD; las sesiones se confirman manualmente con commit().
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    future=True,
)


def get_db() -> Generator[Session, None, None]:
    """
    Dependencia de FastAPI que entrega una sesión de base de datos.

    Uso:
        def endpoint(db: Session = Depends(get_db)):
            ...

    El patrón try/finally asegura que la sesión SIEMPRE se cierre,
    incluso si el endpoint lanza una excepción.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
