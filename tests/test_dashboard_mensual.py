from datetime import datetime
from decimal import Decimal

import pytest

from app.db.session import SessionLocal
from app.models.venta import DetalleVenta, Venta
from app.services.dashboard_service import DashboardService


def test_mes_limites_peru_ranking_y_anulaciones(seed):
    with SessionLocal() as db:
        productos = seed["productos"]
        # UTC: febrero en Perú comienza a las 05:00 y termina el 1/3 a las 05:00.
        casos = [
            ("2024-02-01T04:59:59", 90, 0, False),
            ("2024-02-01T05:00:00", 2, 0, False),
            ("2024-03-01T04:59:59", 3, 1, False),
            ("2024-03-01T05:00:00", 80, 0, False),
            ("2024-02-15T12:00:00", 70, 0, True),
        ]
        for i, (fecha, cantidad, producto, anulada) in enumerate(casos):
            db.add(Venta(
                numero_boleta=f"TEST-MES-{i}", fecha=datetime.fromisoformat(fecha),
                subtotal=cantidad * 10, total=cantidad * 10 - 1,
                descuento=1, anulada=anulada, metodo_pago="efectivo",
                detalles=[DetalleVenta(producto_id=productos[producto]["id"],
                    cantidad=cantidad, precio=10, subtotal=cantidad * 10)],
            ))
        db.flush()
        resultado = DashboardService(db).completo(mes="2024-02")
        assert resultado.resumen.ventas_total == 2
        assert resultado.resumen.monto_total == Decimal("48.00")
        assert resultado.resumen.ticket_promedio == Decimal("24.00")
        assert len(resultado.ventas_por_dia) == 29
        assert resultado.ventas_por_dia[0].monto == 19
        assert resultado.ventas_por_dia[-1].monto == 29
        assert sum(d.monto for d in resultado.ventas_por_dia) == 48
        assert [p.unidades_vendidas for p in resultado.top_productos] == [3, 2]
        assert resultado.top_productos[0].producto_id == productos[1]["id"]
        assert resultado.metodos_pago[0].monto == 48
        vacio = DashboardService(db).completo(mes="2023-12")
        assert len(vacio.ventas_por_dia) == 31
        assert vacio.resumen.monto_total == 0
        assert vacio.top_productos == []
        assert vacio.metodos_pago == []
        db.rollback()


@pytest.mark.parametrize("mes", ["2024-00", "2024-13", "2024-2", "0000-01", "9999-12", "texto"])
def test_mes_invalido(client, auth, mes):
    assert client.get("/dashboard", params={"mes": mes}, headers=auth).status_code == 422


def test_dashboard_con_y_sin_mes(client, auth):
    for params, dias in [({"mes": "2024-02"}, 29), ({"dias": 7}, 7)]:
        response = client.get("/dashboard", params=params, headers=auth)
        assert response.status_code == 200
        assert len(response.json()["ventas_por_dia"]) == dias


def test_navegacion_por_rango_conservada(client, auth):
    response = client.get("/dashboard/ventas-por-dia", params={
        "desde": "2024-02-01", "hasta": "2024-02-29",
    }, headers=auth)
    assert response.status_code == 200
    assert len(response.json()) == 29
