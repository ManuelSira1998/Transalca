import re

import pytest

PANTALLAS_ADMIN = [
    "dashboard", "products", "inventory", "orders_sales", "payments", "clients", "companies", "users", "roles",
    "services", "service_mechanics", "mechanics", "credit", "reports", "report_stats", "promotions",
    "vehicle_log", "tickets", "sucursales", "suppliers", "purchase_orders", "categories", "brands",
    "payment_methods", "tasas", "qr", "bitacora", "modulos", "profile",
]

PANTALLAS_CLIENTE = ["home", "catalog", "cart", "my_orders", "profile", "my_loyalty", "vehicle_log", "help"]


@pytest.mark.parametrize("pantalla", PANTALLAS_ADMIN)
def test_pantallas_del_panel_administrativo(pagina_admin, pantalla):
    response = pagina_admin.goto(f"/admin/{pantalla}")
    assert response.status == 200
    pagina_admin.wait_for_load_state("networkidle")
    assert re.search(rf"/admin/{pantalla}$", pagina_admin.url), pagina_admin.url
    assert pagina_admin.js_errors == []
    assert pagina_admin.server_errors == []


@pytest.mark.parametrize("pantalla", PANTALLAS_CLIENTE)
def test_pantallas_del_portal_del_cliente(pagina_cliente, pantalla):
    response = pagina_cliente.goto(f"/client/{pantalla}")
    assert response.status == 200
    pagina_cliente.wait_for_load_state("networkidle")
    assert re.search(rf"/client/{pantalla}$", pagina_cliente.url), pagina_cliente.url
    assert pagina_cliente.js_errors == []
    assert pagina_cliente.server_errors == []
