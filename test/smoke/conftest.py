import pytest

from helpers.http_client import ApiClient


@pytest.fixture
def anon(live_server):
    with ApiClient(live_server) as client:
        yield client


@pytest.fixture(scope="session")
def browser():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        pytest.skip("playwright no esta instalado")
    with sync_playwright() as playwright:
        try:
            navegador = playwright.chromium.launch(headless=True)
        except Exception as exc:
            pytest.skip(f"Chromium de Playwright no disponible (python -m playwright install chromium): {exc}")
        yield navegador
        navegador.close()


@pytest.fixture
def page(browser, live_server):
    context = browser.new_context(base_url=live_server)
    yield _vigilar(context.new_page(), live_server)
    context.close()


def _contexto_con_sesion(browser, live_server, email, password):
    context = browser.new_context(base_url=live_server)
    response = context.request.post("/auth/do_login", data={"email": email, "password": password})
    assert response.status == 200, response.text()
    return context


@pytest.fixture(scope="session")
def contexto_admin(browser, live_server):
    from helpers.test_data import TEST_PASSWORD, TEST_USERS
    context = _contexto_con_sesion(browser, live_server, TEST_USERS["admin"]["email"], TEST_PASSWORD)
    yield context
    context.close()


@pytest.fixture(scope="session")
def contexto_cliente(browser, live_server):
    from helpers.api_client import unique_cedula, unique_suffix
    from helpers.test_data import TEST_PASSWORD
    context = browser.new_context(base_url=live_server)
    email = f"smoke.{unique_suffix()}@transalca.test"
    registro = context.request.post("/auth/do_register", data={
        "nombre": "Cliente", "apellido": "Smoke", "cedula": unique_cedula(), "telefono": "04141234567",
        "email": email, "direccion": "Barquisimeto", "password": TEST_PASSWORD, "confirm_password": TEST_PASSWORD,
    })
    assert registro.status == 200, registro.text()
    assert context.request.post("/auth/do_login", data={"email": email, "password": TEST_PASSWORD}).status == 200
    yield context
    context.close()


def _vigilar(pestana, live_server):
    pestana.js_errors = []
    pestana.server_errors = []
    pestana.on("pageerror", lambda error: pestana.js_errors.append(str(error)))
    pestana.on("response", lambda r: pestana.server_errors.append(f"{r.status} {r.url}")
               if r.url.startswith(live_server) and r.status >= 500 else None)
    return pestana


@pytest.fixture
def pagina_admin(contexto_admin, live_server):
    pestana = _vigilar(contexto_admin.new_page(), live_server)
    yield pestana
    pestana.close()


@pytest.fixture
def pagina_cliente(contexto_cliente, live_server):
    pestana = _vigilar(contexto_cliente.new_page(), live_server)
    yield pestana
    pestana.close()
