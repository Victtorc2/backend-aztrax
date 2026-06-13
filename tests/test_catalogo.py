"""
Tests del catálogo público.

Verifican que los endpoints abiertos (con API key) devuelvan los datos
correctos y que los filtros (categoría, marca, destacados) funcionen.
"""

import pytest


@pytest.fixture(scope="module")
def variantes_daiwa(client, auth, seed):
    """
    Crea, una sola vez, dos modelos de la marca 'Daiwa': 'Tournament' con dos
    colores y 'Steez' con uno. La BD se comparte en la sesión, por lo que se
    crean en un fixture de módulo para no duplicar entre tests.
    """
    cat_id = seed["categoria"]["id"]
    prov_id = seed["proveedor"]["id"]
    variantes = [
        ("Daiwa", "Tournament", "Verde fluor", 40),
        ("Daiwa", "Tournament", "Azul metálico", 42),
        ("Daiwa", "Steez", "Rojo", 60),
    ]
    for marca, modelo, color, precio in variantes:
        r = client.post("/productos", json={
            "nombre": f"{marca} {modelo} {color}", "marca": marca,
            "modelo": modelo, "color": color,
            "categoria_id": cat_id, "proveedor_id": prov_id,
            "precio_compra": round(precio * 0.6, 2), "precio_venta": precio,
            "stock": 5, "stock_minimo": 1,
        }, headers=auth)
        assert r.status_code == 201, r.text


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
        body = r.json()
        assert isinstance(body["items"], list)


class TestCatalogoProductos:
    """Listado y filtrado de productos."""

    def test_devuelve_productos(self, client, catalog_headers, seed):
        body = client.get("/catalogo/productos", headers=catalog_headers).json()
        assert body["total"] >= 3  # los 3 del seed
        assert len(body["items"]) >= 3
        # Cada producto tiene los campos del catálogo
        p = body["items"][0]
        for campo in ("id", "nombre", "marca", "categoria", "precio_venta", "estado", "destacado"):
            assert campo in p, f"Falta el campo '{campo}'"

    def test_paginacion(self, client, catalog_headers, seed):
        """Respeta page_size y expone los metadatos de paginación."""
        body = client.get("/catalogo/productos", params={"page_size": 2}, headers=catalog_headers).json()
        assert len(body["items"]) <= 2
        assert body["page"] == 1
        assert body["page_size"] == 2
        assert body["total_pages"] >= 1

    def test_incluye_descripcion_y_ficha(self, client, catalog_headers, seed):
        """El catálogo expone descripción y ficha técnica."""
        body = client.get("/catalogo/productos", headers=catalog_headers).json()
        assert "descripcion" in body["items"][0]
        assert "ficha_tecnica" in body["items"][0]

    def test_filtro_por_categoria(self, client, catalog_headers, seed):
        cat_id = seed["categoria"]["id"]
        prods = client.get("/catalogo/productos", params={"categoria_id": cat_id}, headers=catalog_headers).json()["items"]
        assert all(p["categoria"] == "Señuelos" for p in prods)

    def test_filtro_por_marca(self, client, catalog_headers, seed):
        prods = client.get("/catalogo/productos", params={"marca": "Rapala"}, headers=catalog_headers).json()["items"]
        assert all(p["marca"] == "Rapala" for p in prods)

    def test_filtro_categoria_mas_marca(self, client, catalog_headers, seed):
        """Filtro encadenado: categoría + marca."""
        cat_id = seed["categoria"]["id"]
        prods = client.get("/catalogo/productos", params={
            "categoria_id": cat_id, "marca": "Rapala"
        }, headers=catalog_headers).json()["items"]
        assert all(p["marca"] == "Rapala" and p["categoria"] == "Señuelos" for p in prods)

    def test_busqueda_por_texto(self, client, catalog_headers, seed):
        prods = client.get("/catalogo/productos", params={"search": "rapala"}, headers=catalog_headers).json()["items"]
        assert any("Rapala" in p["nombre"] or p["marca"] == "Rapala" for p in prods)

    def test_busqueda_sin_resultados(self, client, catalog_headers, seed):
        body = client.get("/catalogo/productos", params={"search": "xyznoexiste"}, headers=catalog_headers).json()
        assert body["items"] == []
        assert body["total"] == 0


class TestCatalogoDestacados:
    """Productos destacados en el catálogo."""

    def test_solo_destacados(self, client, auth, catalog_headers, seed):
        # Marcar uno como destacado
        p = seed["disponible"]
        client.put(f"/productos/{p['id']}/destacado", params={"destacado": True}, headers=auth)
        prods = client.get("/catalogo/productos", params={"solo_destacados": True}, headers=catalog_headers).json()["items"]
        assert len(prods) >= 1
        assert all(p["destacado"] for p in prods)

    def test_destacados_primero_en_orden(self, client, catalog_headers, seed):
        """Los destacados aparecen antes que los no destacados."""
        prods = client.get("/catalogo/productos", headers=catalog_headers).json()["items"]
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


class TestCatalogoModelos:
    """Navegación Categoría → Marca → Modelo → colores."""

    def test_producto_expone_color(self, client, catalog_headers, variantes_daiwa):
        """El catálogo devuelve el nuevo campo `color`."""
        prods = client.get("/catalogo/productos", params={"marca": "Daiwa"}, headers=catalog_headers).json()["items"]
        assert prods, "No se encontraron productos de la marca"
        assert all("color" in p for p in prods)
        assert any(p["color"] == "Verde fluor" for p in prods)

    def test_modelos_de_una_marca(self, client, catalog_headers, variantes_daiwa):
        """`/catalogo/modelos?marca=` agrupa por modelo con cantidad de colores."""
        modelos = client.get("/catalogo/modelos", params={"marca": "Daiwa"}, headers=catalog_headers).json()
        por_modelo = {m["modelo"]: m for m in modelos}
        assert "Tournament" in por_modelo and "Steez" in por_modelo
        # Tournament tiene 2 colores; Steez, 1.
        assert por_modelo["Tournament"]["cantidad_productos"] == 2
        assert por_modelo["Steez"]["cantidad_productos"] == 1
        # precio_desde = el más bajo de las variantes del modelo.
        assert float(por_modelo["Tournament"]["precio_desde"]) == 40

    def test_colores_de_un_modelo(self, client, catalog_headers, variantes_daiwa):
        """Tras elegir un modelo, sus colores se piden filtrando productos."""
        prods = client.get("/catalogo/productos", params={
            "marca": "Daiwa", "modelo": "Tournament",
        }, headers=catalog_headers).json()["items"]
        assert len(prods) == 2
        colores = {p["color"] for p in prods}
        assert colores == {"Verde fluor", "Azul metálico"}
        assert all(p["modelo"] == "Tournament" for p in prods)
