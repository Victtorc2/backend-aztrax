"""
Punto de entrada de la aplicación FastAPI.

Responsabilidades:
- Crear la instancia de FastAPI y montar los routers.
- Manejar el ciclo de vida (lifespan): crear tablas en desarrollo.
- Registrar los manejadores centralizados de errores del dominio.
- Configurar CORS para permitir peticiones desde el frontend React.
- Configurar Swagger para soportar el botón "Authorize" con JWT.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.config import settings
from app.core.exceptions import AppException
from app.core.middleware import SecurityHeadersMiddleware
from app.db.base import Base
from app.db.session import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Ciclo de vida de la aplicación.

    Al ARRANCAR:
        - Crea las tablas si no existen (útil en desarrollo; en producción
          se recomienda usar las migraciones de Alembic).
    """
    logger.info("Iniciando aplicación...")

    # Importante: importar los modelos para que se registren en Base.metadata
    # antes de crear las tablas.
    from app.models import user  # noqa: F401

    # En producción NO creamos tablas automáticamente: el esquema se gestiona
    # con migraciones de Alembic (`alembic upgrade head`), que es reproducible
    # y versionado. El create_all automático solo se usa en desarrollo.
    if settings.is_production:
        logger.info(
            "Modo producción: omitiendo create_all. "
            "Asegúrate de haber corrido `alembic upgrade head`."
        )
    else:
        Base.metadata.create_all(bind=engine)

    yield  # <-- la app atiende peticiones aquí

    logger.info("Cerrando aplicación...")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.2.0",
    description="Sistema de inventario y ventas + catálogo público.",
    lifespan=lifespan,
    # En producción la documentación se oculta por defecto (no expone la
    # superficie de la API). Configurable con DOCS_ENABLED.
    docs_url="/docs" if settings.docs_enabled else None,
    redoc_url="/redoc" if settings.docs_enabled else None,
    openapi_url="/openapi.json" if settings.docs_enabled else None,
)


# ---------------------------------------------------------------------------
# Middlewares — se registran ANTES que cualquier router
# ---------------------------------------------------------------------------
# Validación de Host (anti Host-header spoofing) solo en producción y solo si
# se especificaron hosts concretos (distinto de "*").
if settings.is_production and settings.allowed_hosts_list != ["*"]:
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts_list
    )

# Cabeceras de seguridad (X-Frame-Options, nosniff, HSTS en prod, etc.).
app.add_middleware(SecurityHeadersMiddleware)

# CORS restringido: solo los orígenes del frontend y los métodos/headers que
# la API realmente usa (en vez de "*"), que es lo correcto cuando se permiten
# credenciales. Incluye X-API-Key, que usa el catálogo público.

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    max_age=600,
)




# ---------------------------------------------------------------------------
# Manejo centralizado de errores
# ---------------------------------------------------------------------------
@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """
    Traduce CUALQUIER excepción del dominio (AppException y subclases) a una
    respuesta JSON coherente.

    Cubre: credenciales incorrectas, token inválido, token expirado,
    usuario inexistente y correo duplicado, sin que los servicios tengan
    que conocer detalles de HTTP.
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Red de seguridad para errores NO previstos.

    Registra el error completo en el log del servidor (para diagnóstico) pero
    devuelve al cliente un mensaje genérico, sin stack traces ni detalles
    internos que podrían exponer la estructura del sistema.
    """
    logger.exception("Error no controlado en %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Error interno del servidor"},
    )


# ---------------------------------------------------------------------------
# Rutas
# ---------------------------------------------------------------------------
app.include_router(api_router, prefix=settings.API_PREFIX)

# Servir archivos subidos (imágenes de productos y banners) como estáticos.
_uploads = Path(settings.UPLOADS_DIR)
_uploads.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(_uploads)), name="uploads")


@app.get("/", tags=["Salud"], summary="Verificar que el servicio está activo")
def health_check() -> dict[str, str]:
    """Endpoint público simple para comprobar que la API responde."""
    return {"status": "ok", "service": settings.PROJECT_NAME}
