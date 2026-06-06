"""
Tests del catálogo público.

Verifican que los endpoints abiertos (con API key) devuelvan los datos
correctos y que los filtros (categoría, marca, destacados) funcionen.
"""


class TestCatalogoAcceso:
    """Acceso y autenticación del catálogo."""

    def test_sin_api_key_rechaza(self, client):
        assert client.get("/catalogo/productos").status_code == 403

    def test_api_key_incorrecta_rechaza(self, client):
        r = client.get("/catalogo/productos", headers={"X-API-Key": "clave-falsa"})
        assert r.status_code == 403

    def test_con_api_key_funciona(self, client, catalog_headers, seed):
        r = client.get("/catalogo/productos", headers=catalog_headers)
        assert r.status_code == 200
        assert isinstance(r.json(), list)


class TestCatalogoProductos:
    """Listado y filtrado de productos."""

    def test_devuelve_productos(self, client, catalog_headers, seed):
        prods = client.get("/catalogo/productos", headers=catalog_headers).json()
        assert len(prods) >= 3  # los 3 del seed
        # Cada producto tiene los campos del catálogo
        p = prods[0]
        for campo in ("id", "nombre", "marca", "categoria", "precio_venta", "estado", "destacado"):
            assert campo in p, f"Falta el campo '{campo}'"

    def test_incluye_descripcion_y_ficha(self, client, catalog_headers, seed):
        """El catálogo expone descripción y ficha técnica."""
        prods = client.get("/catalogo/productos", headers=catalog_headers).json()
        assert "descripcion" in prods[0]
        assert "ficha_tecnica" in prods[0]

    def test_filtro_por_categoria(self, client, catalog_headers, seed):
        cat_id = seed["categoria"]["id"]
        prods = client.get("/catalogo/productos", params={"categoria_id": cat_id}, headers=catalog_headers).json()
        assert all(p["categoria"] == "Señuelos" for p in prods)

    def test_filtro_por_marca(self, client, catalog_headers, seed):
        prods = client.get("/catalogo/productos", params={"marca": "Rapala"}, headers=catalog_headers).json()
        assert all(p["marca"] == "Rapala" for p in prods)

    def test_filtro_categoria_mas_marca(self, client, catalog_headers, seed):
        """Filtro encadenado: categoría + marca."""
        cat_id = seed["categoria"]["id"]
        prods = client.get("/catalogo/productos", params={
            "categoria_id": cat_id, "marca": "Rapala"
        }, headers=catalog_headers).json()
        assert all(p["marca"] == "Rapala" and p["categoria"] == "Señuelos" for p in prods)

    def test_busqueda_por_texto(self, client, catalog_headers, seed):
        prods = client.get("/catalogo/productos", params={"search": "rapala"}, headers=catalog_headers).json()
        assert any("Rapala" in p["nombre"] or p["marca"] == "Rapala" for p in prods)

    def test_busqueda_sin_resultados(self, client, catalog_headers, seed):
        prods = client.get("/catalogo/productos", params={"search": "xyznoexiste"}, headers=catalog_headers).json()
        assert prods == []


class TestCatalogoDestacados:
    """Productos destacados en el catálogo."""

    def test_solo_destacados(self, client, auth, catalog_headers, seed):
        # Marcar uno como destacado
        p = seed["disponible"]
        client.put(f"/productos/{p['id']}/destacado", params={"destacado": True}, headers=auth)
        prods = client.get("/catalogo/productos", params={"solo_destacados": True}, headers=catalog_headers).json()
        assert len(prods) >= 1
        assert all(p["destacado"] for p in prods)

    def test_destacados_primero_en_orden(self, client, catalog_headers, seed):
        """Los destacados aparecen antes que los no destacados."""
        prods = client.get("/catalogo/productos", headers=catalog_headers).json()
        if len(prods) >= 2:
            # Buscar el primer no-destacado
            primer_no_dest = next((i for i, p in enumerate(prods) if not p["destacado"]), len(prods))
            # Todos los destacados deben estar antes
            for i, p in enumerate(prods):
                if p["destacado"]:
                    assert i < primer_no_dest, "Un destacado apareció después de un no-destacado"


class TestCatalogoCategorias:
    """Categorías del catálogo."""

    def test_lista_categorias(self, client, catalog_headers, seed):
        cats = client.get("/catalogo/categorias", headers=catalog_headers).json()
        assert len(cats) >= 1
        assert "nombre" in cats[0]
        assert "cantidad_productos" in cats[0]


class TestCatalogoMarcas:
    """Marcas del catálogo (filtro encadenado)."""

    def test_lista_marcas(self, client, catalog_headers, seed):
        marcas = client.get("/catalogo/marcas", headers=catalog_headers).json()
        assert len(marcas) >= 1
        assert "nombre" in marcas[0]
        assert "cantidad_productos" in marcas[0]

    def test_marcas_por_categoria(self, client, catalog_headers, seed):
        cat_id = seed["categoria"]["id"]
        marcas = client.get("/catalogo/marcas", params={"categoria_id": cat_id}, headers=catalog_headers).json()
        nombres = [m["nombre"] for m in marcas]
        assert "Rapala" in nombres
