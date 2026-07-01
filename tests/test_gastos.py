"""
Tests del módulo de gastos / egresos y del saldo de dinero por método.

La BD de test es compartida por toda la sesión y acumula ventas de otras
pruebas, así que aquí se comprueban DELTAS (saldo antes vs. después de una
acción) en lugar de totales absolutos, para que sean robustos.
"""

import uuid


def _crear_producto(client, auth, precio=50, stock=50):
    suf = uuid.uuid4().hex[:8]
    cat = client.post("/categorias", json={"nombre": f"Cat-{suf}"}, headers=auth).json()
    prov = client.post("/proveedores", json={"nombre": f"Prov-{suf}"}, headers=auth).json()
    r = client.post("/productos", json={
        "nombre": f"Prod-{suf}", "marca": "TestMarca",
        "categoria_id": cat["id"], "proveedor_id": prov["id"],
        "precio_compra": round(precio * 0.6, 2), "precio_venta": precio,
        "stock": stock, "stock_minimo": 3,
    }, headers=auth)
    assert r.status_code == 201, r.text
    return r.json()


def _crear_proveedor(client, auth):
    suf = uuid.uuid4().hex[:8]
    r = client.post("/proveedores", json={"nombre": f"Prov-{suf}"}, headers=auth)
    assert r.status_code == 201, r.text
    return r.json()


def _saldo(client, auth):
    r = client.get("/gastos/saldo", headers=auth)
    assert r.status_code == 200, r.text
    return r.json()


class TestRegistrarGasto:
    def test_gasto_baja_saldo_del_metodo(self, client, auth):
        antes = _saldo(client, auth)
        prov = _crear_proveedor(client, auth)

        r = client.post("/gastos", json={
            "categoria": "pedido",
            "monto": 120.50,
            "metodo_pago": "yape",
            "proveedor_id": prov["id"],
            "descripcion": "Pedido de reposición",
        }, headers=auth)
        assert r.status_code == 201, r.text
        g = r.json()
        assert g["categoria"] == "pedido"
        assert g["proveedor_nombre"] == prov["nombre"]

        despues = _saldo(client, auth)
        # El egreso de yape sube 120.50 y el saldo de yape baja 120.50.
        assert (
            float(despues["yape"]["egresos"]) - float(antes["yape"]["egresos"])
            == 120.50
        )
        assert (
            float(antes["yape"]["saldo"]) - float(despues["yape"]["saldo"])
            == 120.50
        )
        # El total baja en la misma cantidad.
        assert round(float(antes["total"]) - float(despues["total"]), 2) == 120.50

    def test_venta_contado_sube_ingresos(self, client, auth):
        antes = _saldo(client, auth)
        p = _crear_producto(client, auth, precio=50)
        venta = client.post("/ventas", json={
            "items": [{"producto_id": p["id"], "cantidad": 2}],  # total 100
            "metodo_pago": "efectivo",
        }, headers=auth).json()
        despues = _saldo(client, auth)
        assert round(
            float(despues["efectivo"]["ingresos"])
            - float(antes["efectivo"]["ingresos"]), 2
        ) == 100.0

        # Anular deja el saldo (y el agregado global de rentabilidad) como antes:
        # una venta anulada no cuenta como ingreso.
        client.post(f"/ventas/{venta['id']}/anular", json={}, headers=auth)
        final = _saldo(client, auth)
        assert float(final["efectivo"]["ingresos"]) == float(antes["efectivo"]["ingresos"])

    def test_proveedor_inexistente_404(self, client, auth):
        r = client.post("/gastos", json={
            "monto": 10, "metodo_pago": "efectivo", "proveedor_id": 999999,
        }, headers=auth)
        assert r.status_code == 404

    def test_monto_no_positivo_422(self, client, auth):
        r = client.post("/gastos", json={"monto": 0, "metodo_pago": "efectivo"},
                        headers=auth)
        assert r.status_code == 422


class TestEliminarGasto:
    def test_eliminar_restaura_saldo(self, client, auth):
        antes = _saldo(client, auth)
        g = client.post("/gastos", json={
            "monto": 30, "metodo_pago": "yape",
        }, headers=auth).json()
        assert client.delete(f"/gastos/{g['id']}", headers=auth).status_code == 204
        despues = _saldo(client, auth)
        assert float(antes["yape"]["saldo"]) == float(despues["yape"]["saldo"])

    def test_eliminar_inexistente_404(self, client, auth):
        assert client.delete("/gastos/999999", headers=auth).status_code == 404


class TestListarGastos:
    def test_filtra_por_metodo(self, client, auth):
        client.post("/gastos", json={"monto": 15, "metodo_pago": "efectivo",
                    "categoria": "servicio"}, headers=auth)
        r = client.get("/gastos?metodo_pago=efectivo", headers=auth)
        assert r.status_code == 200
        assert all(g["metodo_pago"] == "efectivo" for g in r.json())


class TestGastoAfectaCaja:
    def test_gasto_efectivo_baja_esperado_de_caja(self, client, auth):
        # Cerrar cualquier caja abierta de otra prueba.
        if client.get("/caja/actual", headers=auth).status_code == 200:
            client.post("/caja/cerrar", json={"monto_declarado": 0}, headers=auth)

        client.post("/caja/abrir", json={"monto_inicial": 100}, headers=auth)
        esperado_antes = float(
            client.get("/caja/actual", headers=auth).json()["monto_esperado"]
        )

        # Gasto en efectivo de 40 con la caja abierta.
        client.post("/gastos", json={"monto": 40, "metodo_pago": "efectivo",
                    "categoria": "pedido"}, headers=auth)

        caja = client.get("/caja/actual", headers=auth).json()
        assert float(caja["gastos_efectivo"]) == 40.0
        assert round(esperado_antes - float(caja["monto_esperado"]), 2) == 40.0

        client.post("/caja/cerrar", json={"monto_declarado": 0}, headers=auth)

    def test_gasto_yape_no_afecta_caja(self, client, auth):
        if client.get("/caja/actual", headers=auth).status_code == 200:
            client.post("/caja/cerrar", json={"monto_declarado": 0}, headers=auth)
        client.post("/caja/abrir", json={"monto_inicial": 100}, headers=auth)
        esperado_antes = float(
            client.get("/caja/actual", headers=auth).json()["monto_esperado"]
        )
        client.post("/gastos", json={"monto": 40, "metodo_pago": "yape"}, headers=auth)
        caja = client.get("/caja/actual", headers=auth).json()
        assert float(caja["monto_esperado"]) == esperado_antes
        assert float(caja["gastos_efectivo"]) == 0.0
        client.post("/caja/cerrar", json={"monto_declarado": 0}, headers=auth)
