"""
Router raíz de la API.

Agrupa todos los routers de los distintos módulos.
"""

from fastapi import APIRouter

from app.api.routes import (
    auth,
    banners,
    caja,
    catalogo,
    categorias,
    clientes,
    dashboard,
    gastos,
    proveedores,
    productos,
    por_pedir,
    rentabilidad,
    ventas,
    historial,
)

api_router = APIRouter()

# Fase 2 — Autenticación.
api_router.include_router(auth.router)
# Fase 3 — Categorías.
api_router.include_router(categorias.router)
# Fase 4 — Proveedores.
api_router.include_router(proveedores.router)
# Fase 6 — Reposición (antes que productos por el orden de rutas estáticas).
api_router.include_router(por_pedir.router)
# Fase 5 — Productos.
api_router.include_router(productos.router)
# Fases 7-10 — Ventas y boleta PDF.
api_router.include_router(ventas.router)
# Fase 11 — Historial de ventas.
api_router.include_router(historial.router)
# Dashboard — métricas e indicadores.
api_router.include_router(dashboard.router)
# Clientes y crédito (fiado).
api_router.include_router(clientes.router)
# Caja diaria (apertura, arqueo y cierre).
api_router.include_router(caja.router)
# Gastos / egresos de dinero y saldo por método de pago.
api_router.include_router(gastos.router)
# Rentabilidad (reportes de ganancia).
api_router.include_router(rentabilidad.router)
# Catálogo público (API key).
api_router.include_router(catalogo.router)
# Banners e imágenes (JWT).
api_router.include_router(banners.router)
