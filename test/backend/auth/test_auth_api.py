import pytest

from helpers.http_client import ApiClient, http_register
from helpers.test_data import TEST_PASSWORD, TEST_USERS


def _set_cookie(response):
    return response.headers.get("Set-Cookie", "")


class TestLoginHttp:

    def test_login_correcto_emite_cookie_segura_y_respuesta_minima(self, anon):
        response = anon.post("/auth/do_login", json={"email": TEST_USERS["admin"]["email"], "password": TEST_PASSWORD})

        assert response.status_code == 200
        assert response.headers["Content-Type"].startswith("application/json")
        cookie = _set_cookie(response)
        assert cookie.startswith("session=")
        assert "HttpOnly" in cookie
        assert "SameSite=Lax" in cookie
        assert "Path=/" in cookie
        body = response.json()
        assert body == {"status": "success", "redirect": "/admin/dashboard", "user": {"nombre": "Prueba", "tipo": "admin"}}

    def test_login_fallido_no_emite_cookie_de_sesion(self, anon):
        response = anon.post("/auth/do_login", json={"email": TEST_USERS["admin"]["email"], "password": "Incorrecta1!"})
        assert response.status_code == 401
        assert "session=" not in _set_cookie(response)
        assert response.json() == {"status": "error", "message": "Credenciales incorrectas."}

    def test_cliente_es_redirigido_al_portal(self, live_server):
        with ApiClient(live_server) as client:
            http_register(client)
            response = client.post("/auth/do_login", json={"email": client.info["email"], "password": TEST_PASSWORD})
        assert response.json()["redirect"] == "/client/home"

    def test_session_devuelve_perfil_sin_secretos(self, admin):
        user = admin.get("/auth/session").json()["user"]
        assert set(user) == {"id", "cedula", "nombre", "apellido", "email", "tipo", "foto", "permisos", "roles"}
        assert user["roles"] == ["Administrador"]

    def test_logout_invalida_la_sesion_en_el_servidor_y_el_cliente(self, admin):
        response = admin.post("/auth/logout")
        assert response.status_code == 200
        assert response.json() == {"status": "success", "redirect": "/auth/login"}
        assert admin.get("/auth/session").status_code == 401
        assert admin.get("/api/users/").status_code == 401

    def test_cookie_manipulada_no_autentica(self, live_server, admin):
        cookie = admin.cookies.get("session")
        with ApiClient(live_server) as intruso:
            intruso.cookies.set("session", cookie[:-3] + ("aaa" if not cookie.endswith("aaa") else "bbb"))
            assert intruso.get("/auth/session").status_code == 401

    def test_cookie_firmada_con_otra_clave_no_autentica(self, live_server):
        from flask import Flask
        from flask.sessions import SecureCookieSessionInterface

        falsa = Flask("falsa")
        falsa.secret_key = "otra-clave"
        serializer = SecureCookieSessionInterface().get_signing_serializer(falsa)
        token = serializer.dumps({"user_id": 1, "user_tipo": "admin", "roles": ["Administrador"]})
        with ApiClient(live_server) as intruso:
            intruso.cookies.set("session", token)
            assert intruso.get("/api/users/").status_code == 401


class TestRedireccionNext:

    @pytest.mark.parametrize("next_url, esperado", [
        ("/client/catalog", "/client/catalog"),
        ("https://sitio-externo.example/robo", "/admin/dashboard"),
        ("//sitio-externo.example", "/admin/dashboard"),
        ("javascript:alert(1)", "/admin/dashboard"),
        pytest.param("/\\sitio-externo.example", "/admin/dashboard", marks=pytest.mark.xfail(
            strict=True,
            reason="BUG-AUTH-02: el parametro next acepta '/\\\\dominio', que los navegadores tratan como '//dominio' (redireccion abierta)",
        )),
    ])
    def test_next_solo_admite_rutas_internas(self, anon, next_url, esperado):
        response = anon.post("/auth/do_login", json={
            "email": TEST_USERS["admin"]["email"], "password": TEST_PASSWORD, "next": next_url,
        })
        assert response.status_code == 200
        assert response.json()["redirect"] == esperado


class TestPaginasProtegidas:

    @pytest.mark.parametrize("path", ["/admin/dashboard", "/client/profile", "/scanner"])
    def test_paginas_privadas_redirigen_al_login(self, anon, path):
        response = anon.get(path)
        assert response.status_code == 302
        assert "/auth/login" in response.headers["Location"]

    @pytest.mark.parametrize("path", ["/client/home", "/client/catalog", "/auth/login", "/auth/register"])
    def test_paginas_publicas_cargan(self, anon, path):
        response = anon.get(path)
        assert response.status_code == 200
        assert response.headers["Content-Type"].startswith("text/html")

    def test_reset_sin_token_redirige_al_login(self, anon):
        response = anon.get("/auth/reset")
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/auth/login")
