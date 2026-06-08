"""
Tests de ventas — la lógica de negocio más crítica.

Cubren: cálculo de totales, descuentos, descuento de stock, ventas al
contado con cliente rápido (nombre+DNI), crédito, y casos de error.
"""


class TestVentaContado:
    """Ventas al contado (el flujo más común)."""

    def test_venta_basica(self, client, auth, seed):
        """Venta simple: 2 unidades de un producto disponible."""
        p = seed["disponible"]
        r = client.post("/ventas", json={
            "items": [{"producto_id": p["id"], "cantidad": 2}],
        }, headers=auth)
        assert r.status_code == 201
        venta = r.json()
        assert venta["tipo_pago"] == "contado"
        assert float(venta["total"]) == float(p["precio_venta"]) * 2

    def test_venta_descuenta_stock(self, client, auth, seed):
        """Después de vender, el stock del producto baja."""
        p = seed["disponible"]
        stock_antes = client.get(f"/productos/{p['id']}", headers=auth).json()["stock"]
        client.post("/ventas", json={
            "items": [{"producto_id": p["id"], "cantidad": 1}],
        }, headers=auth)
        stock_despues = client.get(f"/productos/{p['id']}", headers=auth).json()["stock"]
        assert stock_despues == stock_antes - 1

    def test_venta_multiples_productos(self, client, auth, seed):
        """Venta con 2 productos distintos."""
        p1, p2 = seed["disponible"], seed["bajo_stock"]
        r = client.post("/ventas", json={
            "items": [
                {"producto_id": p1["id"], "cantidad": 1},
                {"producto_id": p2["id"], "cantidad": 2},
            ],
        }, headers=auth)
        assert r.status_code == 201
        total_esperado = float(p1["precio_venta"]) + float(p2["precio_venta"]) * 2
        assert float(r.json()["total"]) == total_esperado


class TestVentaConCliente:
    """Ventas al contado con nombre y DNI del cliente."""

    def test_crea_cliente_nuevo(self, client, auth, seed):
        """Si el DNI no existe, crea el cliente y lo enlaza a la venta."""
        p = seed["disponible"]
        r = client.post("/ventas", json={
            "items": [{"producto_id": p["id"], "cantidad": 1}],
            "cliente_nombre": "Carlos Pescador",
            "cliente_documento": "77665544",
        }, headers=auth)
        assert r.status_code == 201
        assert r.json()["cliente_nombre"] == "Carlos Pescador"
        assert r.json()["cliente_id"] is not None

    def test_reusa_cliente_existente(self, client, auth, seed):
        """Si el DNI ya existe, reusa el cliente (no duplica)."""
        p = seed["disponible"]
        # Primera venta crea el cliente
        v1 = client.post("/ventas", json={
            "items": [{"producto_id": p["id"], "cantidad": 1}],
            "cliente_nombre": "María",
            "cliente_documento": "11223344",
        }, headers=auth).json()
        # Segunda venta con mismo DNI
        v2 = client.post("/ventas", json={
            "items": [{"producto_id": p["id"], "cantidad": 1}],
            "cliente_documento": "11223344",
        }, headers=auth).json()
        assert v1["cliente_id"] == v2["cliente_id"]

    def test_venta_anonima(self, client, auth, seed):
        """Sin datos de cliente, la venta queda anónima."""
        p = seed["disponible"]
        r = client.post("/ventas", json={
            "items": [{"producto_id": p["id"], "cantidad": 1}],
        }, headers=auth)
        assert r.json()["cliente_id"] is None


class TestVentaCredito:
    """Ventas al crédito (fiado)."""

    def test_credito_con_cliente(self, client, auth, seed):
        """Crédito válido: necesita un cliente registrado."""
        p = seed["disponible"]
        cli = client.post("/clientes", json={"nombre": "Pedro"}, headers=auth).json()
        r = client.post("/ventas", json={
            "items": [{"producto_id": p["id"], "cantidad": 1}],
            "tipo_pago": "credito",
            "cliente_id": cli["id"],
        }, headers=auth)
        assert r.status_code == 201
        assert r.json()["tipo_pago"] == "credito"
        assert float(r.json()["saldo_pendiente"]) > 0

    def test_credito_sin_cliente_falla(self, client, auth, seed):
        """Crédito sin cliente → error (no se puede fiar sin saber a quién)."""
        p = seed["disponible"]
        r = client.post("/ventas", json={
            "items": [{"producto_id": p["id"], "cantidad": 1}],
            "tipo_pago": "credito",
        }, headers=auth)
        assert r.status_code == 400


class TestVentaDescuento:
    """Descuentos en ventas."""

    def test_descuento_monto(self, client, auth, seed):
        """Descuento fijo en soles."""
        p = seed["disponible"]
        r = client.post("/ventas", json={
            "items": [{"producto_id": p["id"], "cantidad": 1}],
            "descuento": 10,
            "descuento_tipo": "monto",
        }, headers=auth)
        assert r.status_code == 201
        assert float(r.json()["total"]) == float(p["precio_venta"]) - 10

    def test_descuento_porcentaje(self, client, auth, seed):
        """Descuento en porcentaje."""
        p = seed["disponible"]
        r = client.post("/ventas", json={
            "items": [{"producto_id": p["id"], "cantidad": 1}],
            "descuento": 50,  # 50%
            "descuento_tipo": "porcentaje",
        }, headers=auth)
        assert r.status_code == 201
        assert float(r.json()["total"]) == float(p["precio_venta"]) * 0.5


class TestVentaErrores:
    """Casos de error en ventas."""

    def test_producto_agotado(self, client, auth, seed):
        """No se puede vender un producto sin stock."""
        # Crear un producto con stock 0 específicamente para este test.
        p = client.post("/productos", json={
            "nombre": "Agotado Test", "marca": "X",
            "categoria_id": seed["categoria"]["id"],
            "proveedor_id": seed["proveedor"]["id"],
            "precio_compra": 5, "precio_venta": 10,
            "stock": 0, "stock_minimo": 1,
        }, headers=auth).json()
        r = client.post("/ventas", json={
            "items": [{"producto_id": p["id"], "cantidad": 1}],
        }, headers=auth)
        assert r.status_code == 400

    def test_cantidad_mayor_al_stock(self, client, auth, seed):
        """No se puede vender más de lo que hay en stock."""
        p = seed["tercero"]  # stock=5
        r = client.post("/ventas", json={
            "items": [{"producto_id": p["id"], "cantidad": 9999}],
        }, headers=auth)
        assert r.status_code == 400

    def test_producto_inexistente(self, client, auth):
        """Producto que no existe → error."""
        r = client.post("/ventas", json={
            "items": [{"producto_id": 99999, "cantidad": 1}],
        }, headers=auth)
        assert r.status_code in (400, 404)

    def test_venta_sin_items(self, client, auth):
        """Venta vacía → error."""
        r = client.post("/ventas", json={"items": []}, headers=auth)
        assert r.status_code in (400, 422)


class TestVentaLineaLibre:
    """Líneas libres: vender algo NO registrado, escrito a mano con su precio."""

    def test_venta_solo_linea_libre(self, client, auth):
        """Venta de un ítem libre: usa el precio que se manda, sin tocar stock."""
        r = client.post("/ventas", json={
            "items": [{"descripcion": "Anzuelos sueltos", "precio": 5, "cantidad": 3}],
        }, headers=auth)
        assert r.status_code == 201
        venta = r.json()
        assert float(venta["total"]) == 15.0
        linea = venta["detalles"][0]
        assert linea["es_libre"] is True
        assert linea["producto_id"] is None
        assert linea["producto"] == "Anzuelos sueltos"

    def test_linea_libre_no_toca_stock(self, client, auth, seed):
        """Una línea libre no descuenta stock de ningún producto."""
        p = seed["disponible"]
        stock_antes = client.get(f"/productos/{p['id']}", headers=auth).json()["stock"]
        client.post("/ventas", json={
            "items": [{"descripcion": "Servicio de armado", "precio": 10, "cantidad": 1}],
        }, headers=auth)
        stock_despues = client.get(f"/productos/{p['id']}", headers=auth).json()["stock"]
        assert stock_despues == stock_antes

    def test_venta_mixta_producto_y_libre(self, client, auth, seed):
        """Una venta puede combinar un producto registrado y una línea libre."""
        p = seed["disponible"]
        r = client.post("/ventas", json={
            "items": [
                {"producto_id": p["id"], "cantidad": 1},
                {"descripcion": "Plomada artesanal", "precio": 4, "cantidad": 2},
            ],
        }, headers=auth)
        assert r.status_code == 201
        venta = r.json()
        total_esperado = float(p["precio_venta"]) + 4 * 2
        assert float(venta["total"]) == total_esperado
        assert any(d["es_libre"] for d in venta["detalles"])
        assert any(not d["es_libre"] for d in venta["detalles"])

    def test_linea_libre_sin_precio_falla(self, client, auth):
        """Una línea libre sin precio es inválida (422)."""
        r = client.post("/ventas", json={
            "items": [{"descripcion": "Algo", "cantidad": 1}],
        }, headers=auth)
        assert r.status_code == 422

    def test_linea_libre_sin_descripcion_falla(self, client, auth):
        """Una línea sin producto_id y sin descripción es inválida (422)."""
        r = client.post("/ventas", json={
            "items": [{"precio": 5, "cantidad": 1}],
        }, headers=auth)
        assert r.status_code == 422

    def test_boleta_con_linea_libre(self, client, auth):
        """La boleta PDF se genera bien aunque tenga líneas libres."""
        v = client.post("/ventas", json={
            "items": [{"descripcion": "Carnada viva", "precio": 8, "cantidad": 1}],
        }, headers=auth).json()
        r = client.get(f"/ventas/{v['id']}/boleta", headers=auth)
        assert r.status_code == 200
        assert r.content[:4] == b"%PDF"


class TestBoleta:
    """Generación de boleta PDF."""

    def test_boleta_pdf(self, client, auth, seed):
        """La boleta se genera como PDF válido."""
        p = seed["disponible"]
        v = client.post("/ventas", json={
            "items": [{"producto_id": p["id"], "cantidad": 1}],
        }, headers=auth).json()
        r = client.get(f"/ventas/{v['id']}/boleta", headers=auth)
        assert r.status_code == 200
        assert r.content[:4] == b"%PDF"  # firma de un PDF real
