import pytest


class TestPagos:

    def test_sin_sesion_devuelve_401(self, anon):
        assert anon.get("/api/payments/").status_code == 401
        assert anon.post("/api/payments/1/approve").status_code == 401

    def test_admin_lista_pagos(self, admin):
        response = admin.get("/api/payments/")
        assert response.status_code == 200
        assert isinstance(response.get_json()["data"], list)

    def test_aprobar_comprobante_inexistente_devuelve_404(self, admin):
        assert admin.post("/api/payments/99999999/approve").status_code == 404

    def test_rechazo_de_comprobante_inexistente_devuelve_404(self, admin):
        assert admin.post("/api/payments/99999999/reject", json={"observaciones": "x"}).status_code == 404

    @pytest.mark.xfail(strict=True, reason="BUG-AUTHZ-02: GET /api/payments/ no comprueba rol; un cliente ve los comprobantes de todos")
    def test_cliente_no_puede_listar_todos_los_pagos(self, cliente_a):
        assert cliente_a.get("/api/payments/").status_code == 403

    @pytest.mark.xfail(strict=True, reason="BUG-AUTHZ-02: POST /api/payments/<id>/approve no comprueba rol; un cliente puede aprobar pagos")
    def test_cliente_no_puede_aprobar_pagos(self, cliente_a):
        assert cliente_a.post("/api/payments/99999999/approve").status_code == 403
