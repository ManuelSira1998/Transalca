import re

import pytest

from app import PUBLIC_API_PREFIXES, app as flask_app

BUG_API_02 = pytest.mark.xfail(strict=True, reason="BUG-API-02: los controladores asumen que el JSON es un objeto; un JSON escalar (texto, numero, booleano) provoca 500")

SECURITY_HEADERS = {
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
}


def _is_public(path):
    return any(path == p or path.startswith(p + "/") for p in PUBLIC_API_PREFIXES)


def _concrete(rule):
    path = re.sub(r"<int:[^>]+>", "1", rule)
    return re.sub(r"<(?:path:|string:)?[^>]+>", "x", path)


def _private_api_endpoints():
    endpoints = []
    for rule in flask_app.url_map.iter_rules():
        path = _concrete(rule.rule)
        if not path.startswith("/api/") or _is_public(path):
            continue
        for method in sorted(rule.methods - {"HEAD", "OPTIONS"}):
            endpoints.append(pytest.param(method, path, id=f"{method} {rule.rule}"))
    return endpoints


PRIVATE_ENDPOINTS = _private_api_endpoints()


def test_la_matriz_cubre_toda_la_api_privada():
    assert len(PRIVATE_ENDPOINTS) >= 220


@pytest.mark.parametrize("method, path", PRIVATE_ENDPOINTS)
def test_endpoint_privado_sin_sesion_devuelve_401_json(anon, method, path):
    response = anon.request(method, path, json={})
    assert response.status_code == 401
    assert response.headers["Content-Type"].startswith("application/json")
    assert response.json() == {"status": "error", "message": "Debe iniciar sesion."}


@pytest.mark.parametrize("path", [
    "/api/products/active",
    "/api/categories/active",
    "/api/sucursales/active",
    "/api/services/active",
    "/api/rates/",
    "/api/asistente/health",
])
def test_endpoints_publicos_responden_sin_sesion(anon, path):
    response = anon.get(path)
    assert response.status_code == 200
    assert response.headers["Content-Type"].startswith("application/json")


class TestCabeceras:

    @pytest.mark.parametrize("path", ["/api/products/active", "/api/users/", "/auth/login", "/api/no-existe"])
    def test_cabeceras_de_seguridad_en_toda_respuesta(self, anon, path):
        response = anon.get(path)
        for header, value in SECURITY_HEADERS.items():
            assert response.headers[header] == value
        assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
        assert "Werkzeug" not in response.headers.get("Server", "")
        assert "Python" not in response.headers.get("Server", "")
        assert "no-store" in response.headers["Cache-Control"]

    @pytest.mark.xfail(strict=True, reason="BUG-HTTP-01: con el servidor de app.py la respuesta lleva dos cabeceras Server (werkzeug + after_request)")
    def test_una_sola_cabecera_server(self, anon):
        assert anon.get("/auth/login").headers["Server"] == "Transalca"

    def test_no_se_anuncia_hsts_sobre_http(self, anon):
        assert "Strict-Transport-Security" not in anon.get("/auth/login").headers


class TestCors:

    def test_origen_externo_es_rechazado(self, anon):
        response = anon.get("/api/products/active", headers={"Origin": "https://otro-sitio.example"})
        assert response.status_code == 403
        assert "Access-Control-Allow-Origin" not in response.headers

    def test_preflight_del_mismo_origen(self, anon):
        origin = anon.base_url
        response = anon.options("/api/users/", headers={"Origin": origin, "Access-Control-Request-Method": "POST"})
        assert response.status_code == 204
        assert response.headers["Access-Control-Allow-Origin"] == origin
        assert response.headers["Access-Control-Allow-Credentials"] == "true"


class TestErrores:

    def test_ruta_api_inexistente_devuelve_404_json(self, admin):
        response = admin.get("/api/esta-ruta-no-existe")
        assert response.status_code == 404
        assert response.json() == {"status": "error", "message": "Ruta no encontrada."}

    def test_metodo_no_permitido_devuelve_405_json(self, admin):
        response = admin.patch("/api/users/")
        assert response.status_code == 405
        assert response.json()["status"] == "error"

    @pytest.mark.xfail(strict=True, reason="BUG-API-01: el 413 de Werkzeug por cuerpo mayor a 16 MB se captura con except Exception y responde 500")
    def test_cuerpo_mayor_a_16mb_es_rechazado(self, admin):
        response = admin.post("/api/brands/", data=b"x" * (16 * 1024 * 1024 + 1), headers={"Content-Type": "application/json"})
        assert response.status_code == 413

    @pytest.mark.xfail(strict=True, reason="BUG-API-01: un JSON malformado hace fallar request.get_json() y el controlador responde 500 en vez de 400")
    def test_json_malformado_devuelve_400(self, admin):
        response = admin.post("/api/brands/", data='{"nombre": ', headers={"Content-Type": "application/json"})
        assert response.status_code == 400

    @pytest.mark.xfail(strict=True, reason="BUG-API-01: un Content-Type distinto de JSON hace responder 500 al login en vez de 400/415")
    def test_login_con_content_type_incorrecto_devuelve_4xx(self, anon):
        response = anon.post("/auth/do_login", data="email=a@b.com", headers={"Content-Type": "application/x-www-form-urlencoded"})
        assert response.status_code in (400, 415)

    @pytest.mark.parametrize("cuerpo", [
        "[]",
        "null",
        "{}",
        pytest.param('"texto"', marks=BUG_API_02),
        pytest.param("123", marks=BUG_API_02),
        pytest.param("true", marks=BUG_API_02),
    ])
    def test_cuerpo_json_que_no_es_objeto_no_rompe_el_login(self, anon, cuerpo):
        response = anon.post("/auth/do_login", data=cuerpo, headers={"Content-Type": "application/json"})
        assert response.status_code == 400
        assert "Traceback" not in response.text
