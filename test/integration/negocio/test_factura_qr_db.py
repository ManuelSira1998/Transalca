import pytest

from helpers.archivos import png


@pytest.fixture
def orden(cliente_a, db, tmp_path, monkeypatch):
    monkeypatch.setattr("controller.order_controller.UPLOAD_FOLDER", str(tmp_path))
    with db["transalca"].cursor() as cursor:
        cursor.execute("SELECT codigo FROM productos WHERE estado = 1 ORDER BY codigo LIMIT 1")
        codigo = cursor.fetchone()["codigo"]
    cliente_a.post("/api/orders/cart/add", json={"item_id": codigo, "cantidad": 1})
    response = cliente_a.post("/api/orders/checkout", data={"metodo_pago": "efectivo", "comprobante": png("pago.png")},
                              content_type="multipart/form-data")
    orden_id = response.get_json()["id"]
    with db["transalca"].cursor() as cursor:
        cursor.execute("SELECT id_comprobante_pago AS id FROM comprobantes_pago WHERE orden_venta_id = %s", (orden_id,))
        comprobante = cursor.fetchone()["id"]
        cursor.execute("SELECT id_qr_code AS id FROM qr_codes WHERE referencia_qr_code = %s AND utilidad = 'factura' ORDER BY id_qr_code DESC LIMIT 1",
                       (str(orden_id),))
        qr = cursor.fetchone()["id"]
    return {"id": orden_id, "comprobante": comprobante, "qr": qr}


def _escanear(cliente, qr_id):
    return cliente.post("/api/scanner/scan", json={"raw": f"http://localhost/scanner?qr={qr_id}"})


class TestImagenDeFactura:

    def test_no_disponible_mientras_el_pago_esta_pendiente(self, cliente_a, orden):
        response = cliente_a.get(f"/api/scanner/invoice/{orden['id']}/image")
        assert response.status_code == 403

    def test_disponible_al_aprobar_el_pago(self, cliente_a, admin, orden):
        admin.post(f"/api/payments/{orden['comprobante']}/approve")
        response = cliente_a.get(f"/api/scanner/invoice/{orden['id']}/image")
        assert response.status_code == 200
        assert response.mimetype == "image/png"
        assert response.data.startswith(b"\x89PNG")

    def test_otro_cliente_no_obtiene_la_factura(self, cliente_b, admin, orden):
        admin.post(f"/api/payments/{orden['comprobante']}/approve")
        assert cliente_b.get(f"/api/scanner/invoice/{orden['id']}/image").status_code == 403

    def test_orden_inexistente(self, admin):
        assert admin.get("/api/scanner/invoice/99999999/image").status_code == 404


class TestEscaner:

    def test_el_dueno_ve_su_factura(self, cliente_a, orden):
        datos = _escanear(cliente_a, orden["qr"]).get_json()["data"]
        assert datos["mode"] == "factura_cliente"
        assert datos["order"]["cliente_cedula"] == cliente_a.info["cedula"]

    def test_otro_cliente_recibe_factura_restringida(self, cliente_b, orden):
        datos = _escanear(cliente_b, orden["qr"]).get_json()["data"]
        assert datos["mode"] == "factura_restringida"
        assert "order" not in datos

    def test_el_empleado_valida_la_factura(self, admin, orden):
        datos = _escanear(admin, orden["qr"]).get_json()["data"]
        assert datos["mode"] == "factura_validada"

    @pytest.mark.parametrize("raw, mensaje", [
        ("", "Debe indicar"),
        ("https://otro-sitio.example/pagina", "no pertenece"),
        ("99999999", "no encontrado"),
    ])
    def test_codigos_invalidos(self, cliente_a, raw, mensaje):
        response = cliente_a.post("/api/scanner/scan", json={"raw": raw})
        assert response.status_code == 400
        assert mensaje in response.get_json()["message"]

    def test_sin_sesion(self, anon):
        assert anon.post("/api/scanner/scan", json={"raw": "1"}).status_code == 401

    def test_promociones_del_escaner_solo_para_empleados(self, cliente_a, admin):
        assert cliente_a.get("/api/scanner/promotions").status_code == 403
        assert admin.get("/api/scanner/promotions").status_code == 200
