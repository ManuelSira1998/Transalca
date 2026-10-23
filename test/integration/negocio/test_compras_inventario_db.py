import uuid

import pytest

from helpers.api_client import unique_letters


@pytest.fixture
def proveedor(admin):
    rif = "J-" + str(uuid.uuid4().int % 90000000 + 10000000) + "-" + str(uuid.uuid4().int % 10)
    response = admin.post("/api/suppliers/", json={"rif": rif, "nombre": "Proveedor " + unique_letters()})
    assert response.status_code == 200, response.get_json()
    return rif


@pytest.fixture
def productos(db):
    with db["transalca"].cursor() as cursor:
        cursor.execute("SELECT codigo FROM productos WHERE estado = 1 ORDER BY codigo LIMIT 2 OFFSET 5")
        codigos = [fila["codigo"] for fila in cursor.fetchall()]
        for codigo in codigos:
            cursor.execute(
                "INSERT INTO stock (producto_codigo, sucursal_id, stock) VALUES (%s, 1, 20) ON DUPLICATE KEY UPDATE stock = 20",
                (codigo,),
            )
    return codigos


def _stock(db, codigo, sucursal=1):
    with db["transalca"].cursor() as cursor:
        cursor.execute("SELECT stock FROM stock WHERE producto_codigo = %s AND sucursal_id = %s", (codigo, sucursal))
        fila = cursor.fetchone()
        return fila["stock"] if fila else None


def _orden(proveedor, productos, **overrides):
    data = {
        "proveedor_rif": proveedor,
        "sucursal_id": 1,
        "observaciones": "Reposicion",
        "items": [
            {"producto_codigo": productos[0], "cantidad": 10, "precio_unitario": "12.50"},
            {"producto_codigo": productos[1], "cantidad": 4, "precio_unitario": "3"},
        ],
    }
    data.update(overrides)
    return data


class TestOrdenesDeCompra:

    def test_crear_orden_calcula_el_total_y_queda_pendiente(self, admin, db, proveedor, productos):
        response = admin.post("/api/purchase-orders/", json=_orden(proveedor, productos))
        assert response.status_code == 200, response.get_json()
        orden = response.get_json()["data"]["id"]
        with db["transalca"].cursor() as cursor:
            cursor.execute("SELECT estado, total_orden_compra FROM ordenes_compra WHERE id_orden_compra = %s", (orden,))
            fila = cursor.fetchone()
        assert fila["estado"] == "pendiente"
        assert float(fila["total_orden_compra"]) == 137.0
        assert _stock(db, productos[0]) == 20

    def test_marcar_como_comprada_suma_el_stock(self, admin, db, proveedor, productos):
        orden = admin.post("/api/purchase-orders/", json=_orden(proveedor, productos)).get_json()["data"]["id"]
        assert admin.post(f"/api/purchase-orders/{orden}/buy").status_code == 200
        assert _stock(db, productos[0]) == 30
        assert _stock(db, productos[1]) == 24

    def test_no_se_puede_comprar_dos_veces(self, admin, db, proveedor, productos):
        orden = admin.post("/api/purchase-orders/", json=_orden(proveedor, productos)).get_json()["data"]["id"]
        admin.post(f"/api/purchase-orders/{orden}/buy")
        assert admin.post(f"/api/purchase-orders/{orden}/buy").status_code == 400
        assert _stock(db, productos[0]) == 30

    def test_compra_en_sucursal_sin_stock_previo_crea_el_registro(self, admin, db, proveedor, productos):
        with db["transalca"].cursor() as cursor:
            cursor.execute("DELETE FROM stock WHERE producto_codigo = %s AND sucursal_id = 2", (productos[0],))
        data = _orden(proveedor, productos, sucursal_id=2, items=[{"producto_codigo": productos[0], "cantidad": 7, "precio_unitario": "1"}])
        orden = admin.post("/api/purchase-orders/", json=data).get_json()["data"]["id"]
        admin.post(f"/api/purchase-orders/{orden}/buy")
        assert _stock(db, productos[0], 2) == 7

    def test_orden_inexistente(self, admin):
        assert admin.post("/api/purchase-orders/99999999/buy").status_code == 400
        assert admin.get("/api/purchase-orders/99999999").status_code == 404

    @pytest.mark.parametrize("item, clave", [
        ({"producto_codigo": "", "cantidad": 1, "precio_unitario": "1"}, "items_0_code"),
        ({"producto_codigo": "X", "cantidad": 0, "precio_unitario": "1"}, "items_0_qty"),
        ({"producto_codigo": "X", "cantidad": -3, "precio_unitario": "1"}, "items_0_qty"),
        ({"producto_codigo": "X", "cantidad": "diez", "precio_unitario": "1"}, "items_0_qty"),
        ({"producto_codigo": "X", "cantidad": 1, "precio_unitario": "-5"}, "items_0_price"),
        ({"producto_codigo": "X", "cantidad": 1, "precio_unitario": "gratis"}, "items_0_price"),
    ])
    def test_items_invalidos_devuelven_400(self, admin, proveedor, productos, item, clave):
        response = admin.post("/api/purchase-orders/", json=_orden(proveedor, productos, items=[item]))
        assert response.status_code == 400
        assert clave in response.get_json()["errors"]

    @pytest.mark.parametrize("campo, valor, clave", [
        ("items", [], "items"), ("proveedor_rif", "", "proveedor_rif"), ("sucursal_id", None, "sucursal_id"),
    ])
    def test_campos_obligatorios(self, admin, proveedor, productos, campo, valor, clave):
        response = admin.post("/api/purchase-orders/", json=_orden(proveedor, productos, **{campo: valor}))
        assert response.status_code == 400
        assert clave in response.get_json()["errors"]

    def test_proveedor_o_sucursal_inexistentes(self, admin, proveedor, productos):
        assert admin.post("/api/purchase-orders/", json=_orden("J-00000000-0", productos)).status_code == 400
        assert admin.post("/api/purchase-orders/", json=_orden(proveedor, productos, sucursal_id=999999)).status_code == 400

    def test_producto_inexistente_devuelve_400(self, admin, proveedor, productos):
        item = {"producto_codigo": "NO-EXISTE-" + unique_letters(), "cantidad": 1, "precio_unitario": "1"}
        assert admin.post("/api/purchase-orders/", json=_orden(proveedor, productos, items=[item])).status_code == 400

    def test_cliente_no_puede_crear_ordenes_de_compra(self, cliente_a, proveedor, productos):
        assert cliente_a.post("/api/purchase-orders/", json=_orden(proveedor, productos)).status_code == 403


class TestAjusteDeInventario:

    def test_ajustar_stock_de_una_sucursal(self, admin, db, productos):
        response = admin.put("/api/inventory/update-stock", json={"producto_codigo": productos[0], "sucursal_id": 1, "stock": 55})
        assert response.status_code == 200, response.get_json()
        assert _stock(db, productos[0]) == 55

    @pytest.mark.parametrize("stock", [-1, "muchos", None])
    def test_stock_invalido_devuelve_400(self, admin, db, productos, stock):
        response = admin.put("/api/inventory/update-stock", json={"producto_codigo": productos[0], "sucursal_id": 1, "stock": stock})
        assert response.status_code == 400
        assert "stock" in response.get_json()["errors"]
        assert _stock(db, productos[0]) == 20

    def test_sin_producto_devuelve_400(self, admin):
        response = admin.put("/api/inventory/update-stock", json={"sucursal_id": 1, "stock": 5})
        assert response.status_code == 400
        assert "producto_codigo" in response.get_json()["errors"]

    @pytest.mark.xfail(strict=True, reason="BUG-INV-01: update-stock no verifica que el producto exista; la FK falla al insertar y responde 500")
    def test_producto_inexistente_devuelve_400(self, admin):
        response = admin.put("/api/inventory/update-stock", json={"producto_codigo": "NO-EXISTE", "sucursal_id": 1, "stock": 5})
        assert response.status_code in (400, 404)

    def test_stock_bajo_el_minimo_genera_notificacion(self, admin, db, productos):
        with db["transalca"].cursor() as cursor:
            cursor.execute("SELECT COUNT(*) AS n FROM notificaciones")
            antes = cursor.fetchone()["n"]
        admin.put("/api/inventory/update-stock", json={"producto_codigo": productos[1], "sucursal_id": 1, "stock": 1})
        with db["transalca"].cursor() as cursor:
            cursor.execute("SELECT COUNT(*) AS n FROM notificaciones")
            assert cursor.fetchone()["n"] > antes

    def test_productos_con_stock_bajo_aparecen_en_el_reporte(self, admin, productos):
        admin.put("/api/inventory/update-stock", json={"producto_codigo": productos[1], "sucursal_id": 1, "stock": 1})
        bajos = admin.get("/api/inventory/low-stock").get_json()["data"]
        assert productos[1] in [p.get("producto_codigo") or p.get("codigo") for p in bajos]
