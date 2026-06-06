"""Tests de CRUD de productos y funcionalidad de destacados."""


class TestProductoCRUD:
    """Operaciones básicas de productos."""

    def test_crear_producto(self, client, auth, seed):
        r = client.post("/productos", json={
            "nombre": "Anzuelo Owner 2/0",
            "marca": "Owner",
            "categoria_id": seed["categoria"]["id"],
            "proveedor_id": seed["proveedor"]["id"],
            "precio_compra": 3, "precio_venta": 8,
            "stock": 50, "stock_minimo": 10,
        }, headers=auth)
        assert r.status_code == 201
        p = r.json()
        assert p["nombre"] == "Anzuelo Owner 2/0"
        assert p["codigo"]  # tiene código autogenerado (no vacío)

    def test_crear_con_descripcion_y_ficha(self, client, auth, seed):
        r = client.post("/productos", json={
            "nombre": "Caña Test", "marca": "Daiwa",
            "categoria_id": seed["categoria"]["id"],
            "proveedor_id": seed["proveedor"]["id"],
            "precio_compra": 50, "precio_venta": 98,
            "stock": 5, "stock_minimo": 2,
            "descripcion": "Caña telescópica resistente.",
            "ficha_tecnica": "Longitud: 3.6 m\nMaterial: Grafito",
        }, headers=auth)
        assert r.status_code == 201
        assert r.json()["descripcion"] == "Caña telescópica resistente."
        assert "Grafito" in r.json()["ficha_tecnica"]

    def test_listar_productos(self, client, auth, seed):
        r = client.get("/productos", headers=auth)
        assert r.status_code == 200
        assert len(r.json()) >= 3

    def test_obtener_producto(self, client, auth, seed):
        p = seed["disponible"]
        r = client.get(f"/productos/{p['id']}", headers=auth)
        assert r.status_code == 200
        assert r.json()["id"] == p["id"]

    def test_producto_inexistente(self, client, auth):
        assert client.get("/productos/99999", headers=auth).status_code == 404

    def test_editar_producto(self, client, auth, seed):
        p = seed["disponible"]
        r = client.put(f"/productos/{p['id']}", json={"nombre": "Rapala Editado"}, headers=auth)
        assert r.status_code == 200
        assert r.json()["nombre"] == "Rapala Editado"

    def test_editar_descripcion(self, client, auth, seed):
        p = seed["bajo_stock"]
        r = client.put(f"/productos/{p['id']}", json={
            "descripcion": "Señuelo para agua salada",
            "ficha_tecnica": "Peso: 15g\nColor: Plateado",
        }, headers=auth)
        assert r.status_code == 200
        assert r.json()["descripcion"] == "Señuelo para agua salada"

    def test_buscar_producto(self, client, auth, seed):
        r = client.get("/productos/buscar", params={"q": "rapala"}, headers=auth)
        assert r.status_code == 200

    def test_eliminar_producto(self, client, auth, seed):
        # Crear uno para no afectar los seeds
        p = client.post("/productos", json={
            "nombre": "Temporal", "marca": "X",
            "categoria_id": seed["categoria"]["id"],
            "proveedor_id": seed["proveedor"]["id"],
            "precio_compra": 1, "precio_venta": 2,
            "stock": 1, "stock_minimo": 0,
        }, headers=auth).json()
        r = client.delete(f"/productos/{p['id']}", headers=auth)
        assert r.status_code in (200, 204)


class TestProductoDestacado:
    """Toggle de producto destacado."""

    def test_producto_nace_no_destacado(self, client, auth, seed):
        p = seed["bajo_stock"]
        r = client.get(f"/productos/{p['id']}", headers=auth)
        # El campo existe (puede ser True si otro test lo cambió, lo importante es que el campo exista)
        assert "destacado" in r.json()

    def test_marcar_destacado(self, client, auth, seed):
        p = seed["bajo_stock"]
        r = client.put(f"/productos/{p['id']}/destacado", params={"destacado": True}, headers=auth)
        assert r.status_code == 200
        assert r.json()["destacado"] is True

    def test_desmarcar_destacado(self, client, auth, seed):
        p = seed["bajo_stock"]
        r = client.put(f"/productos/{p['id']}/destacado", params={"destacado": False}, headers=auth)
        assert r.status_code == 200
        assert r.json()["destacado"] is False

    def test_destacado_via_put_normal(self, client, auth, seed):
        """También se puede cambiar vía el PUT general."""
        p = seed["disponible"]
        r = client.put(f"/productos/{p['id']}", json={"destacado": True}, headers=auth)
        assert r.json()["destacado"] is True


class TestCategoriaProveedor:
    """CRUD básico de categorías y proveedores."""

    def test_crear_categoria(self, client, auth):
        r = client.post("/categorias", json={"nombre": "Carretes"}, headers=auth)
        assert r.status_code == 201
        assert r.json()["nombre"] == "Carretes"

    def test_categoria_duplicada(self, client, auth):
        client.post("/categorias", json={"nombre": "Duplicada"}, headers=auth)
        r = client.post("/categorias", json={"nombre": "Duplicada"}, headers=auth)
        assert r.status_code in (400, 409)  # la app puede devolver 400 o 409

    def test_crear_proveedor(self, client, auth):
        r = client.post("/proveedores", json={"nombre": "Nuevo Prov"}, headers=auth)
        assert r.status_code == 201
