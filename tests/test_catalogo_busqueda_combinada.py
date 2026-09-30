import pytest


@pytest.fixture(scope="module")
def producto_busqueda(client, auth, seed):
    response = client.post("/productos", headers=auth, json={
        "nombre": "Señuelo de prueba", "marca": "MarcaUnica",
        "modelo": "XR-25", "color": "Verde",
        "categoria_id": seed["categoria"]["id"],
        "proveedor_id": seed["proveedor"]["id"],
        "precio_compra": 10, "precio_venta": 20,
        "stock": 10, "stock_minimo": 1,
    })
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.parametrize("search", [
    "señuelo MarcaUnica XR-25", "XR-25 verde marcaunica",
    "  MarcaUnica   prueba  XR-25  ", "marcaunica", "Señuelos MarcaUnica",
])
def test_combina_campos(client, catalog_headers, producto_busqueda, search):
    response = client.get("/catalogo/productos", headers=catalog_headers,
                          params={"search": search, "page_size": 1})
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == producto_busqueda["id"]


@pytest.mark.parametrize("search", ["MarcaUnica inexistente", "MarcaUnica %", "MarcaUnica _"])
def test_exige_todas_las_palabras(client, catalog_headers, producto_busqueda, search):
    data = client.get("/catalogo/productos", headers=catalog_headers,
                      params={"search": search}).json()
    assert data["total"] == 0


def test_respeta_destacados(client, catalog_headers, producto_busqueda):
    data = client.get("/catalogo/productos", headers=catalog_headers,
                      params={"search": "MarcaUnica XR-25", "solo_destacados": True}).json()
    assert data["total"] == 0
