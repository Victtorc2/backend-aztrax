"""
Tests de las funcionalidades de fidelización y operación:

- Perfil e historial de compra del cliente.
- Puntos de fidelización (ganar, canjear, revertir al anular).
- Clientes inactivos (no compran hace tiempo).
- Caja diaria (apertura, movimientos, cierre y arqueo).
- Anulación de ventas (devolución total: repone stock y revierte puntos).

Se crean recursos propios (categoría/proveedor/productos) para no depender del
stock de `seed`, que otras pruebas van consumiendo durante la sesión.
"""

import uuid


def _crear_producto(client, auth, precio=50, stock=50):
    """Crea una categoría, proveedor y un producto con stock amplio."""
    suf = uuid.uuid4().hex[:8]
    cat = client.post(
        "/categorias", json={"nombre": f"Cat-{suf}"}, headers=auth
    ).json()
    prov = client.post(
        "/proveedores", json={"nombre": f"Prov-{suf}"}, headers=auth
    ).json()
    r = client.post("/productos", json={
        "nombre": f"Prod-{suf}", "marca": "TestMarca",
        "categoria_id": cat["id"], "proveedor_id": prov["id"],
        "precio_compra": round(precio * 0.6, 2), "precio_venta": precio,
        "stock": stock, "stock_minimo": 3,
    }, headers=auth)
    assert r.status_code == 201, r.text
    return r.json()


def _crear_cliente(client, auth, **extra):
    suf = uuid.uuid4().hex[:8]
    data = {"nombre": f"Cliente {suf}", "documento": suf}
    data.update(extra)
    r = client.post("/clientes", json=data, headers=auth)
    assert r.status_code == 201, r.text
    return r.json()


class TestPerfilCliente:
    def test_perfil_acumula_metricas(self, client, auth):
        p = _crear_producto(client, auth, precio=40)
        cli = _crear_cliente(client, auth)

        # Dos compras del mismo cliente.
        client.post("/ventas", json={
            "items": [{"producto_id": p["id"], "cantidad": 2}],
            "cliente_id": cli["id"],
        }, headers=auth)
        client.post("/ventas", json={
            "items": [{"producto_id": p["id"], "cantidad": 1}],
            "cliente_id": cli["id"],
        }, headers=auth)

        r = client.get(f"/clientes/{cli['id']}/perfil", headers=auth)
        assert r.status_code == 200
        perfil = r.json()
        assert perfil["total_compras"] == 2
        assert float(perfil["total_gastado"]) == 120.0  # 80 + 40
        assert float(perfil["ticket_promedio"]) == 60.0
        assert perfil["ultima_compra"] is not None
        assert perfil["productos_favoritos"][0]["producto_id"] == p["id"]
        assert perfil["productos_favoritos"][0]["unidades"] == 3
        assert len(perfil["compras_recientes"]) == 2

    def test_perfil_cliente_inexistente_404(self, client, auth):
        assert client.get("/clientes/999999/perfil", headers=auth).status_code == 404


class TestPuntos:
    def test_gana_puntos_en_compra(self, client, auth):
        # Tasa por defecto: 10 soles = 1 punto.
        p = _crear_producto(client, auth, precio=50)
        cli = _crear_cliente(client, auth)
        client.post("/ventas", json={
            "items": [{"producto_id": p["id"], "cantidad": 2}],  # total 100
            "cliente_id": cli["id"],
        }, headers=auth)

        r = client.get(f"/clientes/{cli['id']}/puntos", headers=auth)
        assert r.status_code == 200
        assert r.json()["puntos"] == 10
        assert r.json()["movimientos"][0]["tipo"] == "ganado"

    def test_canjear_puntos(self, client, auth):
        p = _crear_producto(client, auth, precio=50)
        cli = _crear_cliente(client, auth)
        client.post("/ventas", json={
            "items": [{"producto_id": p["id"], "cantidad": 2}],
            "cliente_id": cli["id"],
        }, headers=auth)

        r = client.post(
            f"/clientes/{cli['id']}/puntos/canjear",
            json={"puntos": 6, "descripcion": "Descuento"},
            headers=auth,
        )
        assert r.status_code == 200
        assert r.json()["puntos"] == 4

    def test_canjear_sin_saldo_400(self, client, auth):
        cli = _crear_cliente(client, auth)
        r = client.post(
            f"/clientes/{cli['id']}/puntos/canjear",
            json={"puntos": 100}, headers=auth,
        )
        assert r.status_code == 400


class TestClientesInactivos:
    def test_recien_comprado_no_aparece(self, client, auth):
        p = _crear_producto(client, auth)
        cli = _crear_cliente(client, auth)
        client.post("/ventas", json={
            "items": [{"producto_id": p["id"], "cantidad": 1}],
            "cliente_id": cli["id"],
        }, headers=auth)

        r = client.get("/clientes/inactivos?dias=30", headers=auth)
        assert r.status_code == 200
        ids = [c["id"] for c in r.json()]
        assert cli["id"] not in ids  # acaba de comprar


class TestCaja:
    def test_arqueo_completo(self, client, auth):
        # Asegurar que no haya una caja abierta de otra prueba.
        actual = client.get("/caja/actual", headers=auth)
        if actual.status_code == 200:
            client.post("/caja/cerrar", json={"monto_declarado": 0}, headers=auth)

        abrir = client.post("/caja/abrir", json={"monto_inicial": 100}, headers=auth)
        assert abrir.status_code == 201
        assert abrir.json()["estado"] == "abierta"

        # Venta en efectivo de 50.
        p = _crear_producto(client, auth, precio=50)
        client.post("/ventas", json={
            "items": [{"producto_id": p["id"], "cantidad": 1}],
            "metodo_pago": "efectivo",
        }, headers=auth)

        # Movimientos manuales: +20 ingreso, -5 egreso.
        client.post("/caja/movimientos", json={"tipo": "ingreso", "monto": 20}, headers=auth)
        client.post("/caja/movimientos", json={"tipo": "egreso", "monto": 5}, headers=auth)

        actual = client.get("/caja/actual", headers=auth).json()
        # 100 + 50 (efectivo) + 20 - 5 = 165
        assert float(actual["monto_esperado"]) == 165.0
        assert float(actual["ventas_efectivo"]) == 50.0

        cierre = client.post(
            "/caja/cerrar", json={"monto_declarado": 165}, headers=auth
        ).json()
        assert cierre["estado"] == "cerrada"
        assert float(cierre["diferencia"]) == 0.0

    def test_no_dos_cajas_abiertas(self, client, auth):
        actual = client.get("/caja/actual", headers=auth)
        if actual.status_code == 200:
            client.post("/caja/cerrar", json={"monto_declarado": 0}, headers=auth)
        client.post("/caja/abrir", json={"monto_inicial": 0}, headers=auth)
        r = client.post("/caja/abrir", json={"monto_inicial": 0}, headers=auth)
        assert r.status_code == 409
        client.post("/caja/cerrar", json={"monto_declarado": 0}, headers=auth)


class TestAnularVenta:
    def test_anular_repone_stock_y_revierte_puntos(self, client, auth):
        p = _crear_producto(client, auth, precio=50, stock=30)
        cli = _crear_cliente(client, auth)
        venta = client.post("/ventas", json={
            "items": [{"producto_id": p["id"], "cantidad": 4}],  # total 200 -> 20 pts
            "cliente_id": cli["id"],
        }, headers=auth).json()

        stock_tras_venta = client.get(f"/productos/{p['id']}", headers=auth).json()["stock"]
        assert stock_tras_venta == 26
        assert client.get(f"/clientes/{cli['id']}/puntos", headers=auth).json()["puntos"] == 20

        r = client.post(
            f"/ventas/{venta['id']}/anular",
            json={"motivo": "Cliente devolvió todo"}, headers=auth,
        )
        assert r.status_code == 200
        assert r.json()["anulada"] is True

        # Stock repuesto y puntos revertidos a 0.
        assert client.get(f"/productos/{p['id']}", headers=auth).json()["stock"] == 30
        assert client.get(f"/clientes/{cli['id']}/puntos", headers=auth).json()["puntos"] == 0

    def test_anular_dos_veces_409(self, client, auth):
        p = _crear_producto(client, auth)
        venta = client.post("/ventas", json={
            "items": [{"producto_id": p["id"], "cantidad": 1}],
        }, headers=auth).json()
        assert client.post(f"/ventas/{venta['id']}/anular", json={}, headers=auth).status_code == 200
        assert client.post(f"/ventas/{venta['id']}/anular", json={}, headers=auth).status_code == 409
