import pytest


class TestBitacora:

    def test_login_queda_registrado_en_la_bitacora(self, admin, db):
        with db["mantenimiento"].cursor() as cursor:
            cursor.execute(
                "SELECT b.accion FROM bitacora b JOIN usuarios u ON u.id = b.usuario_id "
                "WHERE u.email = 'admin.test@transalca.test' ORDER BY b.id DESC LIMIT 1"
            )
            assert cursor.fetchone()["accion"] == "LOGIN"

    def test_admin_lista_con_paginacion(self, admin):
        response = admin.get("/api/bitacora/", query_string={"page": 1, "limit": 5})
        assert response.status_code == 200
        body = response.get_json()
        assert len(body["data"]) <= 5
        assert body["total"] >= len(body["data"])
        assert all("password_hash" not in fila for fila in body["data"])

    @pytest.mark.parametrize("q", ["' OR 1=1 --", "%", "LOGIN' UNION SELECT 1,2 --"])
    def test_busqueda_con_caracteres_especiales_no_falla(self, admin, q):
        response = admin.get("/api/bitacora/search", query_string={"q": q})
        assert response.status_code == 200

    def test_sin_sesion_devuelve_401(self, anon):
        assert anon.get("/api/bitacora/").status_code == 401

    @pytest.mark.xfail(strict=True, reason="BUG-BIT-01: /api/bitacora/ no valida page; page=0 genera OFFSET negativo y responde 500")
    def test_pagina_cero_devuelve_400(self, admin):
        assert admin.get("/api/bitacora/", query_string={"page": 0}).status_code == 400

    @pytest.mark.xfail(strict=True, reason="BUG-BIT-01: /api/bitacora/ no valida page/limit; un valor no numerico responde 500")
    def test_page_no_numerico_devuelve_400(self, admin):
        assert admin.get("/api/bitacora/", query_string={"page": "abc"}).status_code == 400

    @pytest.mark.xfail(strict=True, reason="BUG-BIT-02: /api/bitacora/ no limita 'limit' y devuelve toda la tabla")
    def test_limit_excesivo_se_acota(self, admin):
        body = admin.get("/api/bitacora/", query_string={"page": 1, "limit": 1000000}).get_json()
        assert body["total"] > 100
        assert len(body["data"]) <= 100

    @pytest.mark.xfail(strict=True, reason="BUG-AUTHZ-01: /api/bitacora solo exige sesion; un cliente puede leer la bitacora")
    def test_cliente_no_puede_leer_la_bitacora(self, cliente_a):
        assert cliente_a.get("/api/bitacora/").status_code == 403
