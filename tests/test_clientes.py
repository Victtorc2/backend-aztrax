"""Tests del módulo de clientes."""


class TestClienteCRUD:
    """Operaciones básicas de clientes."""

    def test_crear_cliente(self, client, auth):
        r = client.post("/clientes", json={
            "nombre": "Ana López",
            "documento": "99887766",
            "telefono": "999111222",
        }, headers=auth)
        assert r.status_code == 201
        c = r.json()
        assert c["nombre"] == "Ana López"
        assert c["documento"] == "99887766"

    def test_crear_cliente_solo_nombre(self, client, auth):
        """Un cliente puede tener solo nombre (DNI opcional)."""
        r = client.post("/clientes", json={"nombre": "Solo Nombre"}, headers=auth)
        assert r.status_code == 201

    def test_listar_clientes(self, client, auth):
        r = client.get("/clientes", headers=auth)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_editar_cliente(self, client, auth):
        c = client.post("/clientes", json={"nombre": "Editable"}, headers=auth).json()
        r = client.put(f"/clientes/{c['id']}", json={
            "telefono": "987654321",
            "email": "editable@correo.com",
        }, headers=auth)
        assert r.status_code == 200
        assert r.json()["telefono"] == "987654321"
        assert r.json()["email"] == "editable@correo.com"

    def test_cliente_creado_por_venta_se_puede_completar(self, client, auth, seed):
        """
        Un cliente creado automáticamente desde una venta (solo nombre+DNI)
        puede completar sus datos después desde el módulo de clientes.
        """
        # Crear cliente vía venta
        p = seed["disponible"]
        v = client.post("/ventas", json={
            "items": [{"producto_id": p["id"], "cantidad": 1}],
            "cliente_nombre": "Venta Rápida",
            "cliente_documento": "55443322",
        }, headers=auth).json()
        cli_id = v["cliente_id"]
        assert cli_id is not None

        # Completar datos
        r = client.put(f"/clientes/{cli_id}", json={
            "telefono": "911222333",
            "email": "ventarapida@correo.com",
        }, headers=auth)
        assert r.status_code == 200
        assert r.json()["nombre"] == "Venta Rápida"
        assert r.json()["telefono"] == "911222333"


class TestDashboardYRentabilidad:
    """Endpoints de reportes."""

    def test_dashboard(self, client, auth, seed):
        r = client.get("/dashboard", headers=auth)
        assert r.status_code == 200
        assert "resumen" in r.json()

    def test_rentabilidad(self, client, auth, seed):
        r = client.get("/rentabilidad", headers=auth)
        assert r.status_code == 200
        assert "resumen" in r.json()
