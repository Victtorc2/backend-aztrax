"""
Tests del reporte de rentabilidad, con foco en las ventas libres.

Las líneas libres (productos no registrados) no tienen producto, así que se
agregan en una fila "Ventas libres". Si se informa el costo de la línea, la
ganancia que reporta es la real (ingreso - costo).
"""


class TestRentabilidadVentasLibres:
    """La fila agregada de ventas libres y su ganancia real."""

    def test_linea_libre_con_costo_da_ganancia_real(self, client, auth):
        """Venta libre con costo: la ganancia es ingreso - costo."""
        # precio 20, costo 8, cantidad 1 -> ingreso 20, costo 8, ganancia 12.
        r = client.post("/ventas", json={
            "items": [{
                "descripcion": "Reparación de carrete",
                "precio": 20, "costo": 8, "cantidad": 1,
            }],
        }, headers=auth)
        assert r.status_code == 201

        reporte = client.get("/rentabilidad", headers=auth).json()

        # Debe existir la fila agregada de ventas libres, sin producto_id.
        fila = next(
            (p for p in reporte["por_producto"] if p["nombre"] == "Ventas libres"),
            None,
        )
        assert fila is not None
        assert fila["producto_id"] is None
        # Internamente consistente y con costo real (> 0 gracias al costo informado).
        assert float(fila["ganancia"]) == float(fila["ingresos"]) - float(fila["costo"])
        assert float(fila["costo"]) >= 8

    def test_resumen_es_consistente(self, client, auth):
        """El resumen global cuadra: ganancia == ingresos - costo."""
        reporte = client.get("/rentabilidad", headers=auth).json()
        resumen = reporte["resumen"]
        assert float(resumen["ganancia"]) == float(resumen["ingresos"]) - float(resumen["costo"])

    def test_linea_libre_sin_costo_es_ganancia_total(self, client, auth):
        """Sin costo informado, la venta libre cuenta como ganancia 100%."""
        # Esta venta aporta ingreso con costo 0; la fila agregada sigue cuadrando.
        r = client.post("/ventas", json={
            "items": [{"descripcion": "Propina/servicio", "precio": 15, "cantidad": 1}],
        }, headers=auth)
        assert r.status_code == 201
        reporte = client.get("/rentabilidad", headers=auth).json()
        fila = next(
            (p for p in reporte["por_producto"] if p["nombre"] == "Ventas libres"),
            None,
        )
        assert fila is not None
        assert float(fila["ganancia"]) == float(fila["ingresos"]) - float(fila["costo"])
