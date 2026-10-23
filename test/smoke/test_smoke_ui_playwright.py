import re

import pytest

from helpers.test_data import TEST_PASSWORD, TEST_USERS


def test_la_pagina_de_login_carga_su_formulario(page):
    page.goto("/auth/login")
    assert page.locator("#loginForm").is_visible()
    assert page.locator("#loginEmail").is_visible()
    assert page.locator("#loginPassword").get_attribute("type") == "password"
    assert page.js_errors == []
    assert page.server_errors == []


def test_login_de_administrador_desde_la_interfaz(page):
    page.goto("/auth/login")
    page.fill("#loginEmail", TEST_USERS["admin"]["email"])
    page.fill("#loginPassword", TEST_PASSWORD)
    page.click("#loginForm button[type=submit]")
    page.wait_for_url(re.compile(r".*/admin/dashboard"), timeout=15000)
    page.wait_for_load_state("networkidle")
    assert "Dashboard" in page.title()
    assert page.server_errors == []


def test_login_incorrecto_no_sale_de_la_pagina(page):
    page.goto("/auth/login")
    page.fill("#loginEmail", TEST_USERS["admin"]["email"])
    page.fill("#loginPassword", "Incorrecta123!")
    with page.expect_response(lambda r: r.url.endswith("/auth/do_login")) as respuesta:
        page.click("#loginForm button[type=submit]")
    assert respuesta.value.status == 401
    page.wait_for_timeout(800)
    assert page.url.endswith("/auth/login")


@pytest.mark.parametrize("path", ["/client/home", "/client/catalog"])
def test_paginas_publicas_del_portal_cargan_sin_errores(page, path):
    response = page.goto(path)
    assert response.status == 200
    page.wait_for_load_state("networkidle")
    assert page.title().startswith("Transalca")
    assert page.js_errors == []
    assert page.server_errors == []


def test_pagina_privada_redirige_al_login(page):
    page.goto("/admin/dashboard")
    page.wait_for_url(re.compile(r".*/auth/login.*"), timeout=10000)
    assert page.locator("#loginForm").is_visible()
