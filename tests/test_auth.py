"""Tests de autenticación y autorización."""


class TestLogin:
    """Login y manejo de credenciales."""

    def test_login_exitoso(self, client, admin_token):
        """El admin puede loguearse y recibe un JWT."""
        assert admin_token  # ya se obtuvo en el fixture
        assert len(admin_token.split(".")) == 3  # formato JWT: header.payload.signature

    def test_login_password_incorrecto(self, client):
        r = client.post("/auth/login", json={
            "correo": "admin@sistema.com", "password": "incorrecta"
        })
        assert r.status_code == 401

    def test_login_usuario_inexistente(self, client):
        r = client.post("/auth/login", json={
            "correo": "nadie@inexistente.com", "password": "algo"
        })
        assert r.status_code == 401

    def test_login_campos_vacios(self, client):
        r = client.post("/auth/login", json={"correo": "", "password": ""})
        assert r.status_code == 422  # validación pydantic

    def test_perfil_autenticado(self, client, auth):
        """GET /auth/me devuelve los datos del usuario logueado."""
        r = client.get("/auth/me", headers=auth)
        assert r.status_code == 200
        assert r.json()["correo"] == "admin@sistema.com"


class TestProteccion:
    """Endpoints protegidos rechazan peticiones sin token."""

    def test_productos_sin_token(self, client):
        assert client.get("/productos").status_code == 401

    def test_ventas_sin_token(self, client):
        assert client.post("/ventas", json={}).status_code == 401

    def test_categorias_sin_token(self, client):
        assert client.get("/categorias").status_code == 401

    def test_dashboard_sin_token(self, client):
        assert client.get("/dashboard").status_code == 401

    def test_token_invalido(self, client):
        r = client.get("/productos", headers={"Authorization": "Bearer token.falso.inventado"})
        assert r.status_code == 401
