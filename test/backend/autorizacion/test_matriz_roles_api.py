import pytest

ADMIN_GET = [
    "/api/users/", "/api/users/1", "/api/users/search?q=a",
    "/api/roles/", "/api/roles/1/permissions", "/api/roles/modules",
    "/api/modulos/", "/api/modulos/permissions-list",
    "/api/bitacora/", "/api/bitacora/search?q=a",
    "/api/payments/", "/api/payments/pending",
    "/api/clients/", "/api/clients/stats",
    "/api/companies/", "/api/companies/stats",
    "/api/credit/", "/api/credit/stats",
    "/api/inventory/", "/api/inventory/low-stock", "/api/inventory/sales-orders",
    "/api/mechanics/", "/api/suppliers/",
    "/api/purchase-orders/", "/api/purchase-orders/stats",
    "/api/service-mechanics/", "/api/commissions/", "/api/qr/",
    "/api/reports/dashboard", "/api/reports/recent-orders",
    "/api/stats/revenue", "/api/stats/products",
    "/api/payment-methods/", "/api/pricing/settings",
    "/api/scanner/solicitudes-pendientes",
    "/api/vehicle-log/admin", "/api/vehicle-log/predictions",
    "/api/tickets/stats", "/api/promotions/cards",
]

ADMIN_WRITE = [
    ("POST", "/api/users/"), ("POST", "/api/roles/"),
    ("POST", "/api/products/"), ("PUT", "/api/products/update"),
    ("POST", "/api/brands/"), ("POST", "/api/categories/"),
    ("POST", "/api/sucursales/"), ("POST", "/api/suppliers/"),
    ("POST", "/api/services/"), ("POST", "/api/mechanics/"),
    ("POST", "/api/tasas/"), ("PUT", "/api/inventory/update-stock"),
    ("POST", "/api/promotions/"), ("POST", "/api/qr/"),
    ("POST", "/api/payment-methods/"), ("POST", "/api/purchase-orders/"),
    ("POST", "/api/commissions/"), ("POST", "/api/credit/"),
    ("POST", "/api/service-mechanics/"), ("PUT", "/api/pricing/settings"),
]


OPEN_GET = {
    "/api/users/", "/api/users/1", "/api/users/search?q=a",
    "/api/roles/", "/api/roles/1/permissions", "/api/roles/modules", "/api/modulos/permissions-list",
    "/api/bitacora/", "/api/bitacora/search?q=a", "/api/payments/", "/api/payments/pending",
    "/api/inventory/", "/api/inventory/low-stock", "/api/inventory/sales-orders",
    "/api/mechanics/", "/api/suppliers/", "/api/service-mechanics/", "/api/qr/",
    "/api/reports/dashboard", "/api/reports/recent-orders", "/api/stats/revenue", "/api/stats/products",
}
OPEN_WRITE = {
    ("POST", "/api/users/"), ("POST", "/api/roles/"), ("POST", "/api/products/"), ("PUT", "/api/products/update"),
    ("POST", "/api/brands/"), ("POST", "/api/categories/"), ("POST", "/api/sucursales/"), ("POST", "/api/suppliers/"),
    ("POST", "/api/services/"), ("POST", "/api/mechanics/"), ("POST", "/api/tasas/"), ("PUT", "/api/inventory/update-stock"),
    ("POST", "/api/qr/"), ("POST", "/api/service-mechanics/"),
}
BUG_AUTHZ_01 = pytest.mark.xfail(strict=True, reason="BUG-AUTHZ-01: el endpoint solo exige sesion; un cliente pasa el control de acceso")


def _params(items, open_items):
    return [pytest.param(*(i if isinstance(i, tuple) else (i,)), marks=BUG_AUTHZ_01 if i in open_items else ()) for i in items]


@pytest.mark.parametrize("path", _params(ADMIN_GET, OPEN_GET))
def test_cliente_no_puede_leer_datos_de_administracion(cliente_compartido, path):
    assert cliente_compartido.get(path).status_code == 403


@pytest.mark.parametrize("method, path", _params(ADMIN_WRITE, OPEN_WRITE))
def test_cliente_no_puede_escribir_en_administracion(cliente_compartido, method, path):
    assert cliente_compartido.request(method, path, json={}).status_code == 403


@pytest.mark.parametrize("path", ["/api/users/", "/api/roles/", "/api/bitacora/", "/api/modulos/"])
def test_admin_si_puede_leer(admin, path):
    assert admin.get(path).status_code == 200
