"""
Entorno de migraciones de Alembic.

Se integra con la aplicación:
- Toma la URL de la base de datos desde `app.core.config.settings`.
- Usa `Base.metadata` (con todos los modelos importados) como target,
  lo que habilita el autogenerado de migraciones (`alembic revision --autogenerate`).
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Importamos la configuración y la metadata de la app.
from app.core.config import settings
from app.db.base import Base

# Importar el paquete de modelos registra todas las tablas en Base.metadata.
import app.models  # noqa: F401

# Objeto de configuración de Alembic (lee alembic.ini).
config = context.config

# Inyectamos la URL de la base de datos desde el .env de la app.
config.set_main_option("sqlalchemy.url", settings.database_url_normalized)

# Configuración de logging desde el .ini.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata objetivo para el autogenerado.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Ejecuta migraciones en modo 'offline' (genera SQL sin conectar)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Ejecuta migraciones en modo 'online' (conectado a la base de datos)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
