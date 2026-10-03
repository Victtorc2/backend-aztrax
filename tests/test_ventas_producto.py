"""Buscador histórico: boletas distintas, cantidades y exclusión de anuladas."""

from decimal import Decimal

from app.db.session import SessionLocal
from app.models.producto import Producto
from app.models.venta import DetalleVenta


def test_conteos_busqueda_y_anulacion(client, auth, seed):
    producto = client.post("/productos", headers=auth, json={
        "nombre": "Buscador prueba", "marca": "Aztrax", "modelo": "Tuna",
        "color": "Azul", "categoria_id": seed["categoria"]["id"],
        "proveedor_id": seed["proveedor"]["id"], "precio_compra": 5,
        "precio_venta": 10, "stock": 50, "stock_minimo": 1,
    }).json()
    pid = producto["id"]
    def buscar(q):
        r = client.get("/dashboard/ventas-por-producto", headers=auth, params={"q": q})
        assert r.status_code == 200, r.text
        return r.json()

    assert buscar(producto["codigo"])["items"][0]["veces_vendido"] == 0
    ventas = []
    for cantidad in (3, 2, 7):
        r = client.post("/ventas", headers=auth, json={"items": [{"producto_id": pid, "cantidad": cantidad}]})
        assert r.status_code == 201
        ventas.append(r.json()["id"])
    assert client.post(f"/ventas/{ventas[2]}/anular", headers=auth, json={}).status_code == 200
    # Dos líneas del mismo producto en una boleta cuentan una sola venta.
    with SessionLocal() as db:
        db.add(DetalleVenta(venta_id=ventas[0], producto_id=pid, cantidad=1,
                            precio=Decimal("10"), subtotal=Decimal("10"), costo_unitario=Decimal("5")))
        db.get(Producto, pid).is_active = False
        db.commit()
    for q in (producto["codigo"], "buscador AZTRAX azul", "Tuna"):
        item = next(p for p in buscar(q)["items"] if p["producto_id"] == pid)
        assert item["veces_vendido"] == 2
        assert item["unidades_vendidas"] == 6
        assert item["activo"] is False
    assert buscar("no-existe-este-producto")["items"] == []
    assert buscar("%")["items"] == []


def test_paginacion_y_autenticacion(client, auth, seed):
    url = "/dashboard/ventas-por-producto"
    assert client.get(url).status_code == 401
    first = client.get(url, headers=auth, params={"page_size": 1}).json()
    second = client.get(url, headers=auth, params={"page_size": 1, "page": 2}).json()
    assert first["total"] >= 3
    assert first["total"] == second["total"]
    assert len(first["items"]) == len(second["items"]) == 1
    assert first["items"][0]["producto_id"] != second["items"][0]["producto_id"]
    assert client.get(url, headers=auth, params={"page_size": 101}).status_code == 422
    assert client.get(url, headers=auth, params={"page": 0}).status_code == 422
