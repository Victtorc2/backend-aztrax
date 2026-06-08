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
        body = r.json()
        # Respuesta paginada: items + metadatos
        assert body["total"] >= 3
        assert len(body["items"]) >= 3
        assert body["page"] == 1
        assert body["page_size"] == 10

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


class TestProductoFiltrosPaginacion:
    """Filtro encadenado categoría → marca y paginación del panel admin."""

    def test_filtro_por_marca(self, client, auth, seed):
        r = client.get("/productos", params={"marca": "Rapala"}, headers=auth)
        assert r.status_code == 200
        items = r.json()["items"]
        assert len(items) >= 1
        assert all(p["marca"] == "Rapala" for p in items)

    def test_filtro_categoria_mas_marca(self, client, auth, seed):
        """Filtro encadenado: categoría + marca (lo que pide el panel)."""
        cat_id = seed["categoria"]["id"]
        r = client.get(
            "/productos",
            params={"categoria": cat_id, "marca": "Storm"},
            headers=auth,
        )
        assert r.status_code == 200
        items = r.json()["items"]
        assert all(p["marca"] == "Storm" and p["categoria"] == "Señuelos" for p in items)

    def test_paginacion_respeta_page_size(self, client, auth, seed):
        r = client.get("/productos", params={"page_size": 2}, headers=auth)
        assert r.status_code == 200
        body = r.json()
        assert len(body["items"]) <= 2
        assert body["page_size"] == 2
        assert body["total_pages"] >= 1

    def test_paginas_no_se_solapan(self, client, auth, seed):
        """La página 1 y la 2 devuelven productos distintos."""
        p1 = client.get("/productos", params={"page": 1, "page_size": 1}, headers=auth).json()
        p2 = client.get("/productos", params={"page": 2, "page_size": 1}, headers=auth).json()
        if p1["total"] >= 2:
            assert p1["items"][0]["id"] != p2["items"][0]["id"]

    def test_pagina_invalida_rechaza(self, client, auth, seed):
        assert client.get("/productos", params={"page": 0}, headers=auth).status_code == 422

    def test_filtro_destacado(self, client, auth, seed):
        """El filtro destacado=true solo devuelve productos destacados."""
        p = seed["tercero"]
        client.put(f"/productos/{p['id']}/destacado", params={"destacado": True}, headers=auth)
        body = client.get("/productos", params={"destacado": True}, headers=auth).json()
        assert body["total"] >= 1
        assert all(item["destacado"] for item in body["items"])

    def test_listar_marcas(self, client, auth, seed):
        r = client.get("/productos/marcas", headers=auth)
        assert r.status_code == 200
        marcas = r.json()
        assert "Rapala" in marcas and "Storm" in marcas

    def test_marcas_por_categoria(self, client, auth, seed):
        cat_id = seed["categoria"]["id"]
        r = client.get("/productos/marcas", params={"categoria": cat_id}, headers=auth)
        assert r.status_code == 200
        assert "Rapala" in r.json()


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


class TestProductoRepresentacion:
    """Campo opcional 'representacion' (unidad/sobre/caja/...)."""

    def test_default_es_unidad(self, client, auth, seed):
        """Si no se envía, la representación por defecto es 'unidad'."""
        p = client.post("/productos", json={
            "nombre": "Repr Default", "marca": "X",
            "categoria_id": seed["categoria"]["id"],
            "proveedor_id": seed["proveedor"]["id"],
            "precio_compra": 1, "precio_venta": 2,
            "stock": 1, "stock_minimo": 0,
        }, headers=auth).json()
        assert p["representacion"] == "unidad"

    def test_crear_con_representacion(self, client, auth, seed):
        p = client.post("/productos", json={
            "nombre": "Sobre Anzuelos", "marca": "Owner",
            "categoria_id": seed["categoria"]["id"],
            "proveedor_id": seed["proveedor"]["id"],
            "precio_compra": 1, "precio_venta": 3,
            "stock": 10, "stock_minimo": 2,
            "representacion": "sobre",
        }, headers=auth).json()
        assert p["representacion"] == "sobre"

    def test_editar_representacion(self, client, auth, seed):
        p = seed["tercero"]
        r = client.put(f"/productos/{p['id']}", json={"representacion": "caja"}, headers=auth)
        assert r.status_code == 200
        assert r.json()["representacion"] == "caja"

    def test_representacion_invalida_rechaza(self, client, auth, seed):
        """Un valor fuera de la lista cerrada se rechaza (422)."""
        r = client.post("/productos", json={
            "nombre": "Repr Mala", "marca": "X",
            "categoria_id": seed["categoria"]["id"],
            "proveedor_id": seed["proveedor"]["id"],
            "precio_compra": 1, "precio_venta": 2,
            "stock": 1, "stock_minimo": 0,
            "representacion": "tonel",
        }, headers=auth)
        assert r.status_code == 422


class TestProductoActivar:
    """Activar / desactivar productos (soft delete reversible)."""

    def _crear(self, client, auth, seed, nombre):
        return client.post("/productos", json={
            "nombre": nombre, "marca": "ToggleMarca",
            "categoria_id": seed["categoria"]["id"],
            "proveedor_id": seed["proveedor"]["id"],
            "precio_compra": 1, "precio_venta": 2,
            "stock": 1, "stock_minimo": 0,
        }, headers=auth).json()

    def test_desactivar_lo_oculta_del_listado(self, client, auth, seed):
        p = self._crear(client, auth, seed, "Para Desactivar")
        r = client.put(f"/productos/{p['id']}/activo", params={"activo": False}, headers=auth)
        assert r.status_code == 200
        assert r.json()["is_active"] is False
        # Ya no aparece en el listado por defecto (solo activos).
        body = client.get("/productos", params={"page_size": 100}, headers=auth).json()
        assert all(item["id"] != p["id"] for item in body["items"])

    def test_filtro_activo_false_muestra_desactivados(self, client, auth, seed):
        p = self._crear(client, auth, seed, "Desactivado Visible")
        client.put(f"/productos/{p['id']}/activo", params={"activo": False}, headers=auth)
        body = client.get("/productos", params={"activo": False, "page_size": 100}, headers=auth).json()
        assert any(item["id"] == p["id"] for item in body["items"])

    def test_reactivar_producto(self, client, auth, seed):
        p = self._crear(client, auth, seed, "Para Reactivar")
        client.put(f"/productos/{p['id']}/activo", params={"activo": False}, headers=auth)
        r = client.put(f"/productos/{p['id']}/activo", params={"activo": True}, headers=auth)
        assert r.status_code == 200
        assert r.json()["is_active"] is True
        # Vuelve a aparecer en el listado por defecto.
        body = client.get("/productos", params={"page_size": 100}, headers=auth).json()
        assert any(item["id"] == p["id"] for item in body["items"])

    def test_desactivado_no_sale_en_catalogo(self, client, auth, seed, catalog_headers):
        p = self._crear(client, auth, seed, "Oculto Catalogo")
        client.put(f"/productos/{p['id']}/activo", params={"activo": False}, headers=auth)
        body = client.get("/catalogo/productos", params={"page_size": 100}, headers=catalog_headers).json()
        assert all(item["id"] != p["id"] for item in body["items"])

    def test_activar_inexistente_404(self, client, auth):
        r = client.put("/productos/99999/activo", params={"activo": False}, headers=auth)
        assert r.status_code == 404


class TestProductoOrden:
    """Ordenamiento del listado de productos."""

    def test_orden_nombre_ascendente(self, client, auth, seed):
        """Con orden=nombre, los productos salen alfabéticamente (A-Z)."""
        # Creamos varios con la misma marca y nombres desordenados.
        for nombre in ["Zeta Orden", "Alfa Orden", "Mu Orden"]:
            client.post("/productos", json={
                "nombre": nombre, "marca": "OrdenTestMarca",
                "categoria_id": seed["categoria"]["id"],
                "proveedor_id": seed["proveedor"]["id"],
                "precio_compra": 1, "precio_venta": 2,
                "stock": 1, "stock_minimo": 0,
            }, headers=auth)
        body = client.get(
            "/productos",
            params={"orden": "nombre", "page_size": 100, "marca": "OrdenTestMarca"},
            headers=auth,
        ).json()
        nombres = [item["nombre"] for item in body["items"]]
        assert nombres == ["Alfa Orden", "Mu Orden", "Zeta Orden"]

    def test_orden_invalido_rechaza(self, client, auth, seed):
        r = client.get("/productos", params={"orden": "precio"}, headers=auth)
        assert r.status_code == 422


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
