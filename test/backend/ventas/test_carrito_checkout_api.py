import pytest


@pytest.fixture
def producto(db):
    with db["transalca"].cursor() as cursor:
        cursor.execute(
            "SELECT p.codigo, s.sucursal_id FROM productos p JOIN stock s ON s.producto_codigo = p.codigo "
            "WHERE p.estado = 1 AND s.stock > 50 ORDER BY s.stock DESC LIMIT 1"
        )
        fila = cursor.fetchone()
    if not fila:
        pytest.skip("La base de prueba no tiene productos con stock suficiente")
    return fila


def _item_del_carrito(cliente, codigo):
    items = cliente.get("/api/orders/cart").json()["data"]
    return next(i for i in items if codigo in (i.get("producto_codigo"), i.get("codigo"), i.get("item_id")))


class TestCarrito:

    def test_agregar_consultar_y_actualizar_el_carrito(self, cliente_a, producto):
        assert cliente_a.post("/api/orders/cart/add", json={"item_id": producto["codigo"], "cantidad": 2}).status_code == 200
        item = _item_del_carrito(cliente_a, producto["codigo"])
        assert int(item.get("cantidad") or item.get("cantidad_carrito")) == 2
        assert int(cliente_a.get("/api/orders/cart/count").json()["count"]) == 2

        item_id = item.get("id") or item.get("id_carrito_compra")
        assert cliente_a.put(f"/api/orders/cart/{item_id}/update", json={"cantidad": 5}).status_code == 200
        item = _item_del_carrito(cliente_a, producto["codigo"])
        assert int(item.get("cantidad") or item.get("cantidad_carrito")) == 5

    def test_agregar_el_mismo_producto_suma_cantidades(self, cliente_a, producto):
        cliente_a.post("/api/orders/cart/add", json={"item_id": producto["codigo"], "cantidad": 1})
        cliente_a.post("/api/orders/cart/add", json={"item_id": producto["codigo"], "cantidad": 3})
        item = _item_del_carrito(cliente_a, producto["codigo"])
        assert int(item.get("cantidad") or item.get("cantidad_carrito")) == 4

    @pytest.mark.parametrize("payload, campo", [
        ({"cantidad": 1}, "item_id"),
        pytest.param({"item_id": "X", "cantidad": 0}, "cantidad", marks=pytest.mark.xfail(
            strict=True, reason="BUG-CART-01: cantidad 0 se convierte en 1 sin error (data.get('cantidad') or 1)")),
        ({"item_id": "X", "cantidad": -2}, "cantidad"),
        ({"item_id": "X", "cantidad": 1000}, "cantidad"),
        ({"item_id": "X", "cantidad": "muchos"}, "cantidad"),
        ({"item_id": "X", "tipo": "vehiculo"}, "tipo"),
    ])
    def test_datos_invalidos_devuelven_400(self, cliente_a, payload, campo):
        response = cliente_a.post("/api/orders/cart/add", json=payload)
        assert response.status_code == 400
        assert campo in response.json()["errors"]

    @pytest.mark.parametrize("codigo", ["NO-EXISTE-123", "' OR '1'='1"])
    def test_producto_inexistente_devuelve_400(self, cliente_a, codigo):
        response = cliente_a.post("/api/orders/cart/add", json={"item_id": codigo})
        assert response.status_code == 400
        assert response.json()["message"] == "Producto no disponible"

    def test_otro_cliente_no_puede_tocar_mi_carrito(self, cliente_a, cliente_b, producto):
        cliente_a.post("/api/orders/cart/add", json={"item_id": producto["codigo"], "cantidad": 1})
        item = _item_del_carrito(cliente_a, producto["codigo"])
        item_id = item.get("id") or item.get("id_carrito_compra")
        assert cliente_b.put(f"/api/orders/cart/{item_id}/update", json={"cantidad": 99}).status_code == 403
        assert cliente_b.delete(f"/api/orders/cart/{item_id}/remove").status_code == 403
        item = _item_del_carrito(cliente_a, producto["codigo"])
        assert int(item.get("cantidad") or item.get("cantidad_carrito")) == 1

    @pytest.mark.xfail(strict=True, reason="BUG-API-03: /api/orders/cart/count devuelve el conteo como texto (Decimal de SUM) en vez de numero")
    def test_contador_del_carrito_es_numerico(self, cliente_a, producto):
        cliente_a.post("/api/orders/cart/add", json={"item_id": producto["codigo"], "cantidad": 3})
        assert cliente_a.get("/api/orders/cart/count").json()["count"] == 3

    def test_sin_sesion(self, anon):
        assert anon.post("/api/orders/cart/add", json={"item_id": "X"}).status_code == 401
        assert anon.get("/api/orders/cart/count").status_code == 401


class TestCheckout:

    def test_checkout_crea_la_orden_y_vacia_el_carrito(self, cliente_a, cliente_b, admin, producto, db):
        cliente_a.post("/api/orders/cart/add", json={"item_id": producto["codigo"], "cantidad": 1})
        response = cliente_a.post("/api/orders/checkout", data={"metodo_pago": "efectivo", "sucursal_id": producto["sucursal_id"]})

        assert response.status_code == 200, response.text
        order_id = response.json()["id"]
        assert cliente_a.get("/api/orders/cart").json()["data"] == []
        assert order_id in [o.get("id") or o.get("id_orden_venta") for o in cliente_a.get("/api/orders/my-orders").json()["data"]]
        with db["transalca"].cursor() as cursor:
            cursor.execute("SELECT cliente_cedula FROM ordenes_venta WHERE id_orden_venta = %s", (order_id,))
            assert cursor.fetchone()["cliente_cedula"] == cliente_a.info["cedula"]

        assert cliente_a.get(f"/api/orders/{order_id}").status_code == 200
        assert cliente_b.get(f"/api/orders/{order_id}").status_code == 403
        assert admin.get(f"/api/orders/{order_id}").status_code == 200

    def test_checkout_con_carrito_vacio_devuelve_400(self, cliente_a):
        response = cliente_a.post("/api/orders/checkout", data={"metodo_pago": "efectivo"})
        assert response.status_code == 400

    @pytest.mark.parametrize("metodo", ["", "bitcoin", "' OR 1=1 --", "999999"])
    def test_metodo_de_pago_invalido_devuelve_400(self, cliente_a, metodo):
        assert cliente_a.post("/api/orders/checkout", data={"metodo_pago": metodo}).status_code == 400

    def test_comprobante_con_extension_no_permitida_devuelve_400(self, cliente_a, producto):
        cliente_a.post("/api/orders/cart/add", json={"item_id": producto["codigo"], "cantidad": 1})
        response = cliente_a.post(
            "/api/orders/checkout",
            data={"metodo_pago": "pago_movil"},
            files={"comprobante": ("malicioso.exe", b"MZ\x90\x00", "application/octet-stream")},
        )
        assert response.status_code == 400
