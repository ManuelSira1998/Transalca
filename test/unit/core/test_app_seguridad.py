import pytest

from app import app as flask_app


@pytest.fixture
def client():
    previous = flask_app.config.get("TESTING")
    flask_app.config["TESTING"] = False
    with flask_app.test_client() as c:
        yield c
    flask_app.config["TESTING"] = previous


class TestCabeceras:

    def test_cabeceras_de_seguridad_en_respuestas_api(self, client):
        response = client.get("/api/users/")
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
        assert response.headers["Server"] == "Transalca"
        assert "no-store" in response.headers["Cache-Control"]
        csp = response.headers["Content-Security-Policy"]
        assert "default-src 'self'" in csp and "frame-ancestors 'none'" in csp and "object-src 'none'" in csp

    def test_html_recibe_nonce_en_scripts(self, client):
        response = client.get("/auth/login")
        assert response.status_code == 200
        body = response.get_data(as_text=True)
        csp = response.headers["Content-Security-Policy"]
        nonce = csp.split("'nonce-")[1].split("'")[0]
        if "<script" in body:
            assert f'nonce="{nonce}"' in body

    def test_nonce_cambia_en_cada_respuesta(self, client):
        a = client.get("/auth/login").headers["Content-Security-Policy"]
        b = client.get("/auth/login").headers["Content-Security-Policy"]
        assert a != b


class TestCors:

    def test_origen_no_autorizado_devuelve_403(self, client):
        response = client.get("/api/products/active", headers={"Origin": "https://sitio-malicioso.example"})
        assert response.status_code == 403
        assert "Access-Control-Allow-Origin" not in response.headers

    def test_preflight_del_mismo_origen_devuelve_204(self, client):
        response = client.options("/api/users/", headers={"Origin": "http://localhost"})
        assert response.status_code == 204
        assert response.headers["Access-Control-Allow-Origin"] == "http://localhost"
        assert response.headers["Access-Control-Allow-Credentials"] == "true"


class TestAutenticacionGlobal:

    @pytest.mark.parametrize("ruta", [
        "/api/users/", "/api/roles/", "/api/bitacora/", "/api/payments/", "/api/backup/",
        "/api/clients/", "/api/vehicles/", "/api/reports/dashboard", "/api/stats/revenue", "/api/inventory/",
    ])
    def test_api_privada_sin_sesion_devuelve_401(self, client, ruta):
        response = client.get(ruta)
        assert response.status_code == 401
        assert response.get_json() == {"status": "error", "message": "Debe iniciar sesion."}

    def test_ruta_api_inexistente_devuelve_404_json(self, client):
        with client.session_transaction() as s:
            s["user_id"] = 1
        response = client.get("/api/no-existe")
        assert response.status_code == 404
        assert response.get_json()["message"] == "Ruta no encontrada."

    def test_metodo_no_permitido_devuelve_405_json(self, client):
        response = client.delete("/auth/session")
        assert response.status_code == 405
        assert response.get_json()["status"] == "error"

    def test_pagina_desconocida_redirige_al_inicio(self, client):
        response = client.get("/pagina-que-no-existe")
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/client/home")

    def test_admin_sin_sesion_redirige_al_login(self, client):
        response = client.get("/admin/dashboard")
        assert response.status_code == 302
        assert "/auth/login" in response.headers["Location"]

    def test_cliente_no_entra_al_panel_admin(self, client):
        with client.session_transaction() as s:
            s.update(user_id=9, user_tipo="cliente")
        response = client.get("/admin/dashboard")
        assert response.status_code == 302
        assert "/auth/login" in response.headers["Location"]

    def test_error_no_controlado_devuelve_500_sin_traza(self, client, mocker):
        mocker.patch("model.modulo_model.ModuloModel.ejecutar", side_effect=RuntimeError("detalle interno secreto"))
        with client.session_transaction() as s:
            s.update(user_id=1, roles=["Administrador"])
        response = client.get("/api/modulos/")
        assert response.status_code == 500
        body = response.get_data(as_text=True)
        assert "detalle interno secreto" not in body
        assert "Traceback" not in body


class TestArchivosPublicos:

    def test_widget_del_asistente_es_publico(self, client):
        assert client.get("/componente_ia/chat_widget.js").status_code == 200

    def test_no_permite_salir_del_directorio(self, client):
        assert client.get("/componente_ia/../config/config.py").status_code == 404

    @pytest.mark.parametrize("ruta", [
        "/componente_ia/ai_mode.py",
        "/componente_ia/api_asistente.py",
        "/componente_ia/.env.example",
        "/componente_ia/data/business_knowledge.json",
    ])
    @pytest.mark.xfail(strict=True, reason="BUG-EXP-01: /componente_ia/<path> sirve sin sesion codigo fuente y datos internos, no solo el widget")
    def test_no_expone_codigo_ni_datos_internos(self, client, ruta):
        assert client.get(ruta).status_code == 404


class TestMetricasAsistente:

    @pytest.mark.xfail(strict=True, reason="BUG-IA-01: _metrics_allowed lee claves de sesion ('rol', 'role'...) que el login nunca crea; un administrador real recibe 403")
    def test_administrador_logueado_puede_ver_metricas(self, client):
        with client.session_transaction() as s:
            s.update(user_id=1, user_tipo="admin", roles=["Administrador"])
        assert client.get("/api/asistente/metrics").status_code == 200

    def test_anonimo_no_ve_metricas(self, client):
        assert client.get("/api/asistente/metrics").status_code == 403

    @pytest.mark.xfail(strict=True, reason="BUG-IA-02: _metrics_allowed concede acceso a cualquiera cuando app.config['TESTING'] es True")
    def test_modo_testing_no_abre_las_metricas(self, client):
        flask_app.config["TESTING"] = True
        assert client.get("/api/asistente/metrics").status_code == 403
