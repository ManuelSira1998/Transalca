import pytest

from helpers.archivos import png

BUG_QR_01 = pytest.mark.xfail(strict=True, reason="BUG-QR-01: /api/qr/<id> (leer, modificar, borrar e imagen) no comprueba el dueno del QR")


@pytest.fixture
def qr_de_a(cliente_a, db, tmp_path, monkeypatch):
    monkeypatch.setattr("controller.order_controller.UPLOAD_FOLDER", str(tmp_path))
    with db["transalca"].cursor() as cursor:
        cursor.execute("SELECT codigo FROM productos WHERE estado = 1 ORDER BY codigo LIMIT 1")
        codigo = cursor.fetchone()["codigo"]
    cliente_a.post("/api/orders/cart/add", json={"item_id": codigo, "cantidad": 1})
    orden = cliente_a.post("/api/orders/checkout", data={"metodo_pago": "efectivo", "comprobante": png()},
                           content_type="multipart/form-data").get_json()["id"]
    with db["transalca"].cursor() as cursor:
        cursor.execute("SELECT id_qr_code AS id FROM qr_codes WHERE referencia_qr_code = %s ORDER BY id_qr_code DESC LIMIT 1", (orden,))
        return cursor.fetchone()["id"]


def _estado(db, qr_id):
    with db["transalca"].cursor() as cursor:
        cursor.execute("SELECT estado FROM qr_codes WHERE id_qr_code = %s", (qr_id,))
        return cursor.fetchone()["estado"]


class TestQrPropios:

    def test_el_cliente_ve_su_qr(self, cliente_a, qr_de_a):
        assert qr_de_a in [q.get("id") or q.get("id_qr_code") for q in cliente_a.get("/api/qr/my").get_json()["data"]]
        assert cliente_a.get(f"/api/qr/{qr_de_a}").status_code == 200
        imagen = cliente_a.get(f"/api/qr/{qr_de_a}/image")
        assert imagen.status_code == 200 and imagen.data.startswith(b"\x89PNG")

    def test_otro_cliente_no_lo_lista(self, cliente_b, qr_de_a):
        assert qr_de_a not in [q.get("id") or q.get("id_qr_code") for q in cliente_b.get("/api/qr/my").get_json()["data"]]

    def test_solo_clientes_tienen_mis_qr(self, admin):
        assert admin.get("/api/qr/my").status_code == 403

    def test_qr_inexistente(self, cliente_a):
        assert cliente_a.get("/api/qr/99999999").status_code == 404
        assert cliente_a.get("/api/qr/99999999/image").status_code == 404


class TestQrAjenos:

    @BUG_QR_01
    def test_otro_cliente_no_puede_leerlo(self, cliente_b, qr_de_a):
        assert cliente_b.get(f"/api/qr/{qr_de_a}").status_code == 403

    @BUG_QR_01
    def test_otro_cliente_no_puede_generar_su_imagen(self, cliente_b, qr_de_a):
        assert cliente_b.get(f"/api/qr/{qr_de_a}/image").status_code == 403

    @BUG_QR_01
    def test_otro_cliente_no_puede_borrarlo(self, cliente_b, db, qr_de_a):
        response = cliente_b.delete(f"/api/qr/{qr_de_a}")
        assert response.status_code == 403
        assert _estado(db, qr_de_a) == 1
