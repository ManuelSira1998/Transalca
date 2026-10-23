import pytest

from helpers.archivos import png


@pytest.fixture
def uploads(tmp_path, monkeypatch):
    monkeypatch.setattr("controller.order_controller.UPLOAD_FOLDER", str(tmp_path))
    return tmp_path


@pytest.fixture
def producto(db):
    with db["transalca"].cursor() as cursor:
        cursor.execute("SELECT codigo, precio_producto FROM productos WHERE estado = 1 ORDER BY codigo LIMIT 1")
        fila = cursor.fetchone()
        for sucursal in (1, 2):
            cursor.execute(
                "INSERT INTO stock (producto_codigo, sucursal_id, stock) VALUES (%s, %s, 100) "
                "ON DUPLICATE KEY UPDATE stock = 100",
                (fila["codigo"], sucursal),
            )
    return fila["codigo"]


def _stock(db, codigo, sucursal):
    with db["transalca"].cursor() as cursor:
        cursor.execute("SELECT stock FROM stock WHERE producto_codigo = %s AND sucursal_id = %s", (codigo, sucursal))
        return cursor.fetchone()["stock"]


def _fila(db, sql, params):
    with db["transalca"].cursor() as cursor:
        cursor.execute(sql, params)
        return cursor.fetchone()


def _comprar(cliente, codigo, cantidad, sucursal=1, metodo="efectivo", con_comprobante=True):
    assert cliente.post("/api/orders/cart/add", json={"item_id": codigo, "cantidad": cantidad}).status_code == 200
    data = {"metodo_pago": metodo}
    if sucursal is not None:
        data["sucursal_id"] = str(sucursal)
    if con_comprobante:
        data["comprobante"] = png("pago.png")
    return cliente.post("/api/orders/checkout", data=data, content_type="multipart/form-data")


def _orden_y_comprobante(db, response):
    assert response.status_code == 200, response.get_json()
    orden = response.get_json()["id"]
    comprobante = _fila(db, "SELECT id_comprobante_pago AS id FROM comprobantes_pago WHERE orden_venta_id = %s", (orden,))
    return orden, comprobante["id"]


class TestCompraYAprobacion:

    def test_la_compra_queda_pendiente_y_no_descuenta_stock(self, cliente_a, db, producto, uploads):
        orden, comprobante = _orden_y_comprobante(db, _comprar(cliente_a, producto, 3))
        assert _fila(db, "SELECT estado FROM ordenes_venta WHERE id_orden_venta = %s", (orden,))["estado"] == "pendiente"
        assert _fila(db, "SELECT estado FROM comprobantes_pago WHERE id_comprobante_pago = %s", (comprobante,))["estado"] == "pendiente"
        assert _stock(db, producto, 1) == 100
        assert len(list(uploads.iterdir())) == 1

    def test_el_total_de_la_orden_es_precio_por_cantidad(self, cliente_a, db, producto, uploads):
        precio = _fila(db, "SELECT precio_producto FROM productos WHERE codigo = %s", (producto,))["precio_producto"]
        orden, _ = _orden_y_comprobante(db, _comprar(cliente_a, producto, 4))
        total = _fila(db, "SELECT total_orden_venta FROM ordenes_venta WHERE id_orden_venta = %s", (orden,))["total_orden_venta"]
        assert float(total) == pytest.approx(float(precio) * 4)

    def test_aprobar_el_pago_aprueba_la_orden_y_descuenta_stock(self, cliente_a, admin, db, producto, uploads):
        orden, comprobante = _orden_y_comprobante(db, _comprar(cliente_a, producto, 3))
        assert admin.post(f"/api/payments/{comprobante}/approve").status_code == 200

        assert _fila(db, "SELECT estado FROM ordenes_venta WHERE id_orden_venta = %s", (orden,))["estado"] == "aprobada"
        assert _fila(db, "SELECT estado FROM comprobantes_pago WHERE id_comprobante_pago = %s", (comprobante,))["estado"] == "verificado"
        assert _stock(db, producto, 1) == 97
        assert _stock(db, producto, 2) == 100

    def test_aprobar_dos_veces_no_descuenta_dos_veces(self, cliente_a, admin, db, producto, uploads):
        _, comprobante = _orden_y_comprobante(db, _comprar(cliente_a, producto, 2))
        admin.post(f"/api/payments/{comprobante}/approve")
        admin.post(f"/api/payments/{comprobante}/approve")
        assert _stock(db, producto, 1) == 98

    def test_el_cliente_recibe_una_notificacion_al_aprobarse(self, cliente_a, admin, db, producto, uploads):
        orden, comprobante = _orden_y_comprobante(db, _comprar(cliente_a, producto, 1))
        admin.post(f"/api/payments/{comprobante}/approve")
        notificaciones = cliente_a.get("/api/notifications/").get_json()["data"]
        assert any(f"#{orden}" in (n.get("titulo") or "") for n in notificaciones)

    def test_rechazar_exige_motivo(self, cliente_a, admin, db, producto, uploads):
        _, comprobante = _orden_y_comprobante(db, _comprar(cliente_a, producto, 1))
        response = admin.post(f"/api/payments/{comprobante}/reject", json={"observaciones": "   "})
        assert response.status_code == 400
        assert "observaciones" in response.get_json()["errors"]

    def test_rechazar_el_pago_rechaza_la_orden_sin_tocar_stock(self, cliente_a, admin, db, producto, uploads):
        orden, comprobante = _orden_y_comprobante(db, _comprar(cliente_a, producto, 5))
        assert admin.post(f"/api/payments/{comprobante}/reject", json={"observaciones": "Monto incompleto"}).status_code == 200
        assert _fila(db, "SELECT estado FROM ordenes_venta WHERE id_orden_venta = %s", (orden,))["estado"] == "rechazada"
        comprobante_db = _fila(db, "SELECT estado, observaciones FROM comprobantes_pago WHERE id_comprobante_pago = %s", (comprobante,))
        assert comprobante_db == {"estado": "rechazado", "observaciones": "Monto incompleto"}
        assert _stock(db, producto, 1) == 100

    def test_rechazar_un_pago_ya_aprobado_devuelve_el_stock(self, cliente_a, admin, db, producto, uploads):
        _, comprobante = _orden_y_comprobante(db, _comprar(cliente_a, producto, 4))
        admin.post(f"/api/payments/{comprobante}/approve")
        assert _stock(db, producto, 1) == 96
        admin.post(f"/api/payments/{comprobante}/reject", json={"observaciones": "Pago revertido por el banco"})
        assert _stock(db, producto, 1) == 100

    @pytest.mark.xfail(strict=True, reason="BUG-STK-02: aprobar un pago ya rechazado deja la orden 'aprobada' sin descontar stock (el trigger solo descuenta desde pendiente/procesando)")
    def test_aprobar_un_pago_rechazado_no_deja_la_orden_aprobada_sin_descontar(self, cliente_a, admin, db, producto, uploads):
        orden, comprobante = _orden_y_comprobante(db, _comprar(cliente_a, producto, 3))
        admin.post(f"/api/payments/{comprobante}/reject", json={"observaciones": "Comprobante ilegible"})
        respuesta = admin.post(f"/api/payments/{comprobante}/approve")
        estado = _fila(db, "SELECT estado FROM ordenes_venta WHERE id_orden_venta = %s", (orden,))["estado"]
        assert respuesta.status_code == 400 or (estado == "aprobada" and _stock(db, producto, 1) == 97)


class TestReglasDeStock:

    @pytest.mark.xfail(strict=True, reason="BUG-STK-01: el carrito y el checkout no comprueban el stock disponible; se puede comprar mas de lo que existe")
    def test_no_se_puede_comprar_mas_de_lo_disponible(self, cliente_a, db, producto, uploads):
        cliente_a.post("/api/orders/cart/add", json={"item_id": producto, "cantidad": 150})
        response = cliente_a.post("/api/orders/checkout", data={"metodo_pago": "efectivo", "sucursal_id": "1"})
        assert response.status_code == 400

    @pytest.mark.xfail(strict=True, reason="BUG-STK-03: si la orden no tiene sucursal, al aprobarla el trigger descuenta el producto en todas las sucursales")
    def test_orden_sin_sucursal_descuenta_una_sola_vez(self, cliente_a, admin, db, producto, uploads):
        _, comprobante = _orden_y_comprobante(db, _comprar(cliente_a, producto, 10, sucursal=None))
        admin.post(f"/api/payments/{comprobante}/approve")
        assert _stock(db, producto, 1) + _stock(db, producto, 2) == 190

    def test_metodo_a_credito_solo_para_empresas(self, cliente_a, db, producto, uploads):
        response = _comprar(cliente_a, producto, 1, metodo="8", con_comprobante=False)
        assert response.status_code == 400
        assert "empresas" in response.get_json()["message"]
        assert _stock(db, producto, 1) == 100


class TestAccesoALosPagos:

    def test_el_cliente_ve_su_orden_con_detalle(self, cliente_a, db, producto, uploads):
        orden, _ = _orden_y_comprobante(db, _comprar(cliente_a, producto, 2))
        response = cliente_a.get(f"/api/orders/{orden}")
        assert response.status_code == 200

    def test_otro_cliente_no_ve_la_orden(self, cliente_a, cliente_b, db, producto, uploads):
        orden, _ = _orden_y_comprobante(db, _comprar(cliente_a, producto, 2))
        assert cliente_b.get(f"/api/orders/{orden}").status_code == 403
