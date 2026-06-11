"""
Configuración central de la aplicación.

Lee las variables de entorno desde `.env`
usando pydantic-settings.
"""

from functools import lru_cache

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# ----------------------------------------------------------------------
# Valores inseguros que NO deben usarse en producción
# ----------------------------------------------------------------------
_INSECURE_SECRETS = {
    "",
    "changeme",
    "dev-secret-key",
    "admin123",
}


class Settings(BaseSettings):
    """Configuración global del sistema."""

    # ------------------------------------------------------------------
    # ENTORNO
    # ------------------------------------------------------------------
    ENVIRONMENT: str = "development"

    # ------------------------------------------------------------------
    # BASE DE DATOS
    # ------------------------------------------------------------------
    # No se incluyen credenciales reales en el código fuente: la URL real se
    # inyecta SIEMPRE por variable de entorno (.env en local, panel del
    # proveedor en producción). El valor por defecto es solo un marcador para
    # desarrollo local y nunca debe contener una contraseña real.
    DATABASE_URL: str = "mysql://user:password@localhost:3306/sistema"

    # ------------------------------------------------------------------
    # SEGURIDAD / JWT
    # ------------------------------------------------------------------
    # Clave de desarrollo OBVIAMENTE insegura. En producción el validador de
    # más abajo obliga a definir una SECRET_KEY fuerte por variable de entorno.
    SECRET_KEY: str = "dev-only-insecure-secret-change-me"

    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # ------------------------------------------------------------------
    # RATE LIMIT LOGIN
    # ------------------------------------------------------------------
    LOGIN_MAX_ATTEMPTS: int = 5
    LOGIN_WINDOW_SECONDS: int = 300

    # ------------------------------------------------------------------
    # METADATOS APP
    # ------------------------------------------------------------------
    PROJECT_NAME: str = "Sistema de Inventario y Ventas"

    API_PREFIX: str = ""

    # ------------------------------------------------------------------
    # CORS
    # ------------------------------------------------------------------
    ALLOWED_ORIGINS: str = (
    "https://sistema-inventario-aztrax.vercel.app,"
    "https://fishingnasca.vercel.app"
)

    # ------------------------------------------------------------------
    # TRUSTED HOSTS
    # ------------------------------------------------------------------
    ALLOWED_HOSTS: str = "*"

    # ------------------------------------------------------------------
    # DOCUMENTACIÓN
    # ------------------------------------------------------------------
    DOCS_ENABLED: bool = False

    # ------------------------------------------------------------------
    # CATÁLOGO PÚBLICO
    # ------------------------------------------------------------------
    CATALOG_API_KEY: str = ""

    UPLOADS_DIR: str = "uploads"

    # Limpia espacios/saltos de línea invisibles que suelen colarse al pegar
    # la key en el panel de Railway (causa típica de 403 con la key "correcta").
    @field_validator("CATALOG_API_KEY", mode="after")
    @classmethod
    def _strip_api_key(cls, v: str) -> str:
        return v.strip()

    # ------------------------------------------------------------------
    # DATOS NEGOCIO
    # ------------------------------------------------------------------
    BUSINESS_NAME: str = "Fishing and more - Nasca"

    BUSINESS_RUC: str = "10769540089"

    BUSINESS_ADDRESS: str = "Av. Los incas 110"

    BUSINESS_CITY: str = "Perú"

    BUSINESS_PHONE: str = "991180718"

    BOLETA_SERIE: str = "B001"

    # ------------------------------------------------------------------
    # FIDELIZACIÓN (PUNTOS)
    # ------------------------------------------------------------------
    # Soles de compra necesarios para ganar 1 punto. Con el valor por defecto
    # (10), una compra de S/ 55 otorga 5 puntos. Debe ser > 0.
    PUNTOS_SOLES_POR_PUNTO: int = 10

    # ------------------------------------------------------------------
    # EDICIÓN DE VENTAS (BOLETA)
    # ------------------------------------------------------------------
    # Plazo máximo (en días) durante el cual se puede modificar una venta
    # después de registrada. Pasado ese plazo, la boleta queda en firme.
    VENTA_EDIT_DIAS: int = 3

    # ------------------------------------------------------------------
    # CONFIG PYDANTIC
    # ------------------------------------------------------------------
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ------------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------------
    @property
    def is_production(self) -> bool:
        """True si el entorno es producción."""
        return self.ENVIRONMENT.strip().lower() in {
            "production",
            "prod",
        }

    @property
    def allowed_origins_list(self) -> list[str]:
        """Convierte ALLOWED_ORIGINS en lista."""
        return [
            origin.strip()
            for origin in self.ALLOWED_ORIGINS.split(",")
            if origin.strip()
        ]

    @property
    def allowed_hosts_list(self) -> list[str]:
        """Convierte ALLOWED_HOSTS en lista."""
        hosts = [
            host.strip()
            for host in self.ALLOWED_HOSTS.split(",")
            if host.strip()
        ]

        return hosts or ["*"]

    @property
    def database_url_normalized(self) -> str:
        """
        Normaliza DATABASE_URL para SQLAlchemy.
        """

        url = self.DATABASE_URL.strip()

        if url.startswith("mysql://"):
            return (
                "mysql+pymysql://"
                + url[len("mysql://"):]
            )

        return url

    @property
    def docs_enabled(self) -> bool:
        """
        Swagger activo solo en desarrollo
        o si DOCS_ENABLED=true.
        """

        return (
            True
            if not self.is_production
            else self.DOCS_ENABLED
        )

    # ------------------------------------------------------------------
    # VALIDACIONES PRODUCCIÓN
    # ------------------------------------------------------------------
    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        """Validaciones obligatorias en producción."""

        if self.is_production:

            # SECRET_KEY
            if (
                not self.SECRET_KEY
                or self.SECRET_KEY in _INSECURE_SECRETS
                or len(self.SECRET_KEY) < 32
            ):
                raise ValueError(
                    "SECRET_KEY insegura para producción."
                )

            # DATABASE URL
            if not self.DATABASE_URL:
                raise ValueError(
                    "DATABASE_URL es obligatoria."
                )

            # API KEY
            if (
                not self.CATALOG_API_KEY
                or len(self.CATALOG_API_KEY) < 24
            ):
                raise ValueError(
                    "CATALOG_API_KEY insegura."
                )

            # CORS
            if "*" in self.allowed_origins_list:
                raise ValueError(
                    "ALLOWED_ORIGINS no puede usar '*'."
                )

        return self


# ----------------------------------------------------------------------
# SETTINGS CACHEADOS
# ----------------------------------------------------------------------
@lru_cache
def get_settings() -> Settings:
    """Devuelve instancia cacheada."""
    return Settings()


# ----------------------------------------------------------------------
# INSTANCIA GLOBAL
# ----------------------------------------------------------------------
settings: Settings = get_settings()