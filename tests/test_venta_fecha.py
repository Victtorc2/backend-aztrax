"""Límites de emisión retroactiva; nunca usa la base de producción."""

from datetime import datetime, timezone

import pytest

from app.services import venta_service


@pytest.fixture
def fecha_fija(monkeypatch):
    class Reloj(datetime):
        @classmethod
        def now(cls, tz=None):
            # En UTC ya es octubre; en Perú todavía es 30 de septiembre.
            return datetime(2026, 10, 1, 2, 30, tzinfo=timezone.utc).astimezone(tz)

    monkeypatch.setattr(venta_service, "datetime", Reloj)


@pytest.mark.parametrize("fecha", ["2026-09-26", "2026-09-27", "2026-09-28", "2026-09-29", "2026-09-30"])
def test_fecha_permitida_persiste_en_historial_y_boleta(client, auth, fecha_fija, fecha):
    response = client.post("/ventas", headers=auth, json={
        "fecha": fecha,
        "items": [{"descripcion": "Venta anterior", "precio": 8, "cantidad": 2}],
    })
    assert response.status_code == 201, response.text
    venta = response.json()
    assert venta["fecha"].startswith(fecha)
    assert float(venta["total"]) == 16
    historial = client.get("/historial", headers=auth, params={"fecha": fecha})
    assert historial.status_code == 200
    assert any(v["id"] == venta["id"] for v in historial.json()["items"])
    pdf = client.get(f"/ventas/{venta['id']}/boleta", headers=auth)
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF")


@pytest.mark.parametrize("fecha", ["2026-09-25", "2026-10-01", "2026-10-02"])
def test_fecha_fuera_de_plazo_no_registra_ni_descuenta_stock(client, auth, seed, fecha_fija, fecha):
    producto_id = seed["disponible"]["id"]
    antes = client.get(f"/productos/{producto_id}", headers=auth).json()["stock"]
    total = client.get("/historial", headers=auth).json()["total"]
    response = client.post("/ventas", headers=auth, json={
        "fecha": fecha,
        "items": [{"producto_id": producto_id, "cantidad": 1}],
    })
    assert response.status_code == 400
    assert "4 días" in response.text
    assert client.get(f"/productos/{producto_id}", headers=auth).json()["stock"] == antes
    assert client.get("/historial", headers=auth).json()["total"] == total


def test_fecha_malformada(client, auth):
    response = client.post("/ventas", headers=auth, json={
        "fecha": "2026-02-30",
        "items": [{"descripcion": "Venta", "precio": 8, "cantidad": 1}],
    })
    assert response.status_code == 422
