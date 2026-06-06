"""
Tests de seguridad.

Verifican: validación de uploads por firma real, cabeceras de seguridad,
y que la configuración de producción rechace valores inseguros.
"""
import os


# PNG mínimo válido (1x1 pixel).
PNG_VALIDO = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
    b'\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc'
    b'\x00\x01\x00\x00\x05\x00\x01\r\n\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
)
# Archivo falso disfrazado de imagen.
HTML_FALSO = b'<html><script>alert("hack")</script></html>'
# Archivo vacío.
VACIO = b''


class TestUploadImagenes:
    """Validación de subida de imágenes."""

    def test_sube_png_real(self, client, auth, seed):
        """Un PNG real se acepta."""
        p = seed["disponible"]
        r = client.post(
            f"/productos/{p['id']}/imagen", headers=auth,
            files={"file": ("foto.png", PNG_VALIDO, "image/png")},
        )
        assert r.status_code == 200

    def test_rechaza_html_disfrazado(self, client, auth, seed):
        """Un HTML con content-type image/png se rechaza (firma inválida)."""
        p = seed["disponible"]
        r = client.post(
            f"/productos/{p['id']}/imagen", headers=auth,
            files={"file": ("malo.png", HTML_FALSO, "image/png")},
        )
        assert r.status_code == 400

    def test_rechaza_archivo_vacio(self, client, auth, seed):
        p = seed["disponible"]
        r = client.post(
            f"/productos/{p['id']}/imagen", headers=auth,
            files={"file": ("vacio.png", VACIO, "image/png")},
        )
        assert r.status_code == 400

    def test_rechaza_exe_disfrazado(self, client, auth, seed):
        """Un ejecutable con extensión .png se rechaza."""
        p = seed["disponible"]
        r = client.post(
            f"/productos/{p['id']}/imagen", headers=auth,
            files={"file": ("virus.png", b'MZ\x90\x00' + b'\x00' * 100, "image/png")},
        )
        assert r.status_code == 400


class TestCabecerasSeguridad:
    """Headers de seguridad en las respuestas."""

    def test_nosniff(self, client):
        r = client.get("/")
        assert r.headers.get("x-content-type-options") == "nosniff"

    def test_frame_deny(self, client):
        r = client.get("/")
        assert r.headers.get("x-frame-options") == "DENY"

    def test_referrer_policy(self, client):
        r = client.get("/")
        assert "referrer-policy" in {k.lower() for k in r.headers.keys()}


class TestConfigProduccion:
    """Las validaciones de configuración rechazan valores inseguros."""

    def test_rechaza_secret_key_debil(self):
        from app.core.config import Settings
        try:
            Settings(
                ENVIRONMENT="production", SECRET_KEY="corto",
                DATABASE_URL="sqlite:///x.db", CATALOG_API_KEY="a" * 40,
                ALLOWED_ORIGINS="https://a.com",
            )
            assert False, "Debió rechazar SECRET_KEY débil"
        except ValueError:
            pass  # correcto

    def test_rechaza_catalog_key_debil(self):
        from app.core.config import Settings
        try:
            Settings(
                ENVIRONMENT="production", SECRET_KEY="a" * 40,
                DATABASE_URL="sqlite:///x.db", CATALOG_API_KEY="cambiame",
                ALLOWED_ORIGINS="https://a.com",
            )
            assert False, "Debió rechazar CATALOG_API_KEY débil"
        except ValueError:
            pass

    def test_rechaza_cors_wildcard(self):
        from app.core.config import Settings
        try:
            Settings(
                ENVIRONMENT="production", SECRET_KEY="a" * 40,
                DATABASE_URL="sqlite:///x.db", CATALOG_API_KEY="b" * 40,
                ALLOWED_ORIGINS="*",
            )
            assert False, "Debió rechazar ALLOWED_ORIGINS=*"
        except ValueError:
            pass

    def test_produccion_valida_pasa(self):
        from app.core.config import Settings
        s = Settings(
            ENVIRONMENT="production", SECRET_KEY="a" * 40,
            DATABASE_URL="sqlite:///x.db", CATALOG_API_KEY="b" * 40,
            ALLOWED_ORIGINS="https://a.com",
        )
        assert s.is_production
        assert s.docs_enabled is False  # docs ocultos en prod


class TestDocsDesarrollo:
    """Documentación interactiva accesible en desarrollo."""

    def test_docs_visibles(self, client):
        assert client.get("/docs").status_code == 200

    def test_openapi_disponible(self, client):
        r = client.get("/openapi.json")
        assert r.status_code == 200
        assert "paths" in r.json()
