import pytest

from helpers.http_client import ApiClient, http_login, http_register
from helpers.test_data import TEST_USERS

BLUEPRINTS_CRITICOS = {
    "auth", "users", "roles", "products", "categories", "orders", "payments",
    "vehicle_bp", "ticket_bp", "client_admin", "asistente_ia",
}


def test_la_app_registra_todas_sus_rutas(flask_app):
    endpoints = {rule.endpoint.split(".")[0] for rule in flask_app.url_map.iter_rules()}
    assert BLUEPRINTS_CRITICOS <= endpoints
    assert len(list(flask_app.url_map.iter_rules())) >= 280


@pytest.mark.parametrize("base", ["transalca", "mantenimiento"])
def test_la_conexion_a_cada_base_de_datos_esta_activa(test_databases, base):
    from model.connection import Connection
    fila = Connection().fetch_one(base, "SELECT DATABASE() AS nombre, 1 AS ok")
    assert fila == {"nombre": test_databases[base], "ok": 1}


def test_el_servidor_http_responde(anon):
    response = anon.get("/auth/login")
    assert response.status_code == 200
    assert response.headers["Content-Type"].startswith("text/html")


def test_la_raiz_redirige_al_portal(anon):
    response = anon.get("/")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/client/home")


@pytest.mark.parametrize("path", [
    "/api/products/active",
    "/api/categories/active",
    "/api/sucursales/active",
    "/api/services/active",
])
def test_servicios_publicos_responden(anon, path):
    response = anon.get(path)
    assert response.status_code == 200
    assert response.json()["status"] == "success"


def test_el_asistente_esta_operativo(anon):
    salud = anon.get("/api/asistente/health").json()
    assert salud["status"] in ("ok", "degraded")
    componentes = salud.get("components", {})
    if componentes:
        assert componentes["orchestrator"]["status"] == "ok"
        assert componentes["intent_model"]["status"] == "active"


@pytest.mark.parametrize("path", ["/public/js/auth.js", "/public/js/client_common.js", "/componente_ia/chat_widget.js"])
def test_recursos_estaticos_se_sirven(anon, path):
    response = anon.get(path)
    assert response.status_code == 200
    assert len(response.content) > 0


def test_flujo_vital_administrador(anon):
    http_login(anon, TEST_USERS["admin"]["email"])
    assert anon.get("/auth/session").json()["user"]["tipo"] == "admin"
    assert anon.get("/api/users/").status_code == 200
    assert anon.get("/api/products/").status_code == 200
    assert anon.get("/admin/dashboard").status_code == 200
    assert anon.post("/auth/logout").status_code == 200
    assert anon.get("/auth/session").status_code == 401


def test_flujo_vital_cliente(live_server):
    with ApiClient(live_server) as cliente:
        http_register(cliente)
        http_login(cliente, cliente.info["email"])
        assert cliente.get("/auth/session").json()["user"]["tipo"] == "cliente"
        assert cliente.get("/api/products/active").status_code == 200
        assert cliente.get("/api/orders/cart").json()["data"] == []
        assert cliente.get("/client/catalog").status_code == 200
        assert cliente.post("/auth/logout").status_code == 200
