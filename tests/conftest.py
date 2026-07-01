"""
Fixtures compartidos para toda la suite de tests.

Usa una base SQLite en memoria (rápida, aislada, se destruye al terminar).
Cada test que use `client` tiene un estado limpio con el admin ya creado.
"""

import os
import tempfile

# Variables de entorno ANTES de importar la app (la config se lee al importar).
os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.gettempdir()}/test_suite.db"
os.environ["SECRET_KEY"] = "test-secret-key-0123456789abcdef0123456789abcdef"
os.environ["CATALOG_API_KEY"] = "test-catalog-key-segura-1234"
os.environ["UPLOADS_DIR"] = f"{tempfile.gettempdir()}/test_uploads"
os.environ["ENVIRONMENT"] = "development"

import pytest
from fastapi.testclient import TestClient

from app.main import app


def _reset_db_con_admin() -> None:
    """
    Deja la BD de test en un estado limpio y reproducible:
    recrea TODO el esquema y siembra el usuario admin que usan los fixtures.

    Necesario porque la BD de test es un archivo SQLite que persiste entre
    corridas; sin esto, datos de una sesión anterior (p. ej. la categoría
    "Señuelos") harían fallar el seed con errores de duplicado.
    """
    # Importar todos los modelos para que se registren en Base.metadata.
    from app.models import (  # noqa: F401
        banner, caja, categoria, cliente, gasto, producto, proveedor, puntos,
        user, venta,
    )
    from app.core.security import hash_password
    from app.db.base import Base
    from app.db.session import SessionLocal, engine
    from app.repositories.user_repository import UserRepository

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        repo = UserRepository(db)
        if not repo.exists_by_email("admin@sistema.com"):
            repo.create("Admin", "admin@sistema.com", hash_password("admin123"))
    finally:
        db.close()


@pytest.fixture(scope="session")
def client():
    """TestClient que vive toda la sesión de tests (con BD limpia y admin)."""
    _reset_db_con_admin()
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def admin_token(client: TestClient) -> str:
    """Token JWT del administrador (login una vez, reusar)."""
    r = client.post("/auth/login", json={
        "correo": "admin@sistema.com",
        "password": "admin123",
    })
    assert r.status_code == 200, f"Login falló: {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="session")
def auth(admin_token: str) -> dict:
    """Headers de autorización listos para usar."""
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="session")
def catalog_headers() -> dict:
    """Headers para los endpoints del catálogo público."""
    return {"X-API-Key": "test-catalog-key-segura-1234"}


@pytest.fixture(scope="session")
def seed(client: TestClient, auth: dict) -> dict:
    """
    Datos semilla: una categoría, un proveedor y 3 productos.
    Se crean una vez y se reutilizan en toda la sesión.
    """
    cat = client.post("/categorias", json={"nombre": "Señuelos"}, headers=auth).json()
    prov = client.post("/proveedores", json={"nombre": "Mayorista Pesca"}, headers=auth).json()

    productos = []
    for nombre, marca, precio, stock in [
        ("Rapala X-Rap 12cm", "Rapala", 52, 20),
        ("Señuelo Storm 15g", "Storm", 35, 10),
        ("Jig Mustad 30g", "Mustad", 18, 5),
    ]:
        r = client.post("/productos", json={
            "nombre": nombre, "marca": marca,
            "categoria_id": cat["id"], "proveedor_id": prov["id"],
            "precio_compra": round(precio * 0.6, 2),
            "precio_venta": precio,
            "stock": stock, "stock_minimo": 3,
        }, headers=auth)
        assert r.status_code == 201, f"Fallo al crear '{nombre}': {r.text}"
        productos.append(r.json())

    return {
        "categoria": cat,
        "proveedor": prov,
        "productos": productos,
        "disponible": productos[0],   # stock=20
        "bajo_stock": productos[1],   # stock=10
        "tercero": productos[2],      # stock=5
    }
