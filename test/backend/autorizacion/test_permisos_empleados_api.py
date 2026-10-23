import pytest

DENEGADO = "denegado"
PERMITIDO = "permitido"

CASOS = [
    ("empleado_sin_rol", "GET", "/api/users/", DENEGADO),
    ("empleado_sin_rol", "POST", "/api/users/", DENEGADO),
    ("empleado_sin_rol", "POST", "/api/roles/", DENEGADO),
    ("empleado_sin_rol", "GET", "/api/bitacora/", DENEGADO),
    ("empleado_sin_rol", "GET", "/api/modulos/", DENEGADO),
    ("empleado_sin_rol", "POST", "/api/modulos/", DENEGADO),
    ("empleado_sin_rol", "GET", "/api/payments/", DENEGADO),
    ("empleado_sin_rol", "POST", "/api/payments/99999999/approve", DENEGADO),
    ("empleado_sin_rol", "GET", "/api/credit/", DENEGADO),
    ("empleado_sin_rol", "GET", "/api/suppliers/", DENEGADO),
    ("empleado_sin_rol", "GET", "/api/purchase-orders/", DENEGADO),
    ("empleado_sin_rol", "POST", "/api/products/", DENEGADO),
    ("empleado_sin_rol", "PUT", "/api/inventory/update-stock", DENEGADO),
    ("empleado_sin_rol", "POST", "/api/backup/restore", DENEGADO),
    ("empleado_sin_rol", "GET", "/api/reports/dashboard", DENEGADO),
    ("vendedor", "GET", "/api/users/", DENEGADO),
    ("vendedor", "POST", "/api/users/", DENEGADO),
    ("vendedor", "POST", "/api/roles/", DENEGADO),
    ("vendedor", "GET", "/api/bitacora/", DENEGADO),
    ("vendedor", "POST", "/api/modulos/", DENEGADO),
    ("vendedor", "POST", "/api/brands/", DENEGADO),
    ("vendedor", "POST", "/api/categories/", DENEGADO),
    ("vendedor", "POST", "/api/products/", DENEGADO),
    ("vendedor", "GET", "/api/suppliers/", DENEGADO),
    ("vendedor", "GET", "/api/purchase-orders/", DENEGADO),
    ("vendedor", "POST", "/api/backup/restore", DENEGADO),
    ("vendedor", "GET", "/api/payments/", PERMITIDO),
    ("vendedor", "POST", "/api/payments/99999999/approve", PERMITIDO),
    ("vendedor", "GET", "/api/credit/", PERMITIDO),
    ("vendedor", "GET", "/api/reports/dashboard", PERMITIDO),
    ("vendedor", "GET", "/api/inventory/", PERMITIDO),
    ("vendedor", "GET", "/api/products/", PERMITIDO),
    ("mecanico", "GET", "/api/users/", DENEGADO),
    ("mecanico", "GET", "/api/payments/", DENEGADO),
    ("mecanico", "POST", "/api/payments/99999999/approve", DENEGADO),
    ("mecanico", "GET", "/api/credit/", DENEGADO),
    ("mecanico", "POST", "/api/products/", DENEGADO),
    ("mecanico", "GET", "/api/reports/dashboard", DENEGADO),
    ("mecanico", "GET", "/api/commissions/", PERMITIDO),
    ("mecanico", "GET", "/api/vehicles/", PERMITIDO),
    ("mecanico", "GET", "/api/tickets/", PERMITIDO),
]


CON_CONTROL_DE_PERMISOS = {"/api/modulos/", "/api/backup/restore"}
BUG_AUTHZ_04 = pytest.mark.xfail(strict=True, reason="BUG-AUTHZ-04: los permisos por modulo no se aplican; cualquier empleado pasa el control de acceso aunque su rol no tenga el permiso")


def _marcas(caso):
    rol, method, path, esperado = caso
    if esperado == DENEGADO and path not in CON_CONTROL_DE_PERMISOS:
        return BUG_AUTHZ_04
    return ()


def _id(caso):
    rol, method, path, esperado = caso
    return f"{rol}-{method}-{path.strip('/').replace('/', '_')}-{esperado}"


@pytest.mark.parametrize("rol, method, path, esperado", [pytest.param(*c, id=_id(c), marks=_marcas(c)) for c in CASOS])
def test_permisos_por_rol(request, rol, method, path, esperado):
    cliente = request.getfixturevalue(rol)
    status = cliente.request(method, path, json={}).status_code
    if esperado == DENEGADO:
        assert status == 403
    else:
        assert status not in (401, 403)


def test_el_administrador_tiene_acceso_total(admin):
    for path in ("/api/users/", "/api/roles/", "/api/bitacora/", "/api/modulos/", "/api/payments/", "/api/credit/"):
        assert admin.get(path).status_code == 200, path
