import pytest


class TestSupplierPurchaseOrderIntegration:

    def test_unauthenticated_access_restrictions(self, client):
        resp_prov_post = client.post("/api/suppliers/", json={
            "rif": "J-99999999-0",
            "nombre": "Proveedor No Autorizado",
            "email": "noauth@test.com"
        })
        assert resp_prov_post.status_code == 401

        resp_oc_get = client.get("/api/purchase-orders/")
        assert resp_oc_get.status_code == 401

        resp_oc_post = client.post("/api/purchase-orders/", json={
            "proveedor_rif": "J-12345678-0",
            "sucursal_id": 1,
            "items": [{"producto_codigo": "CAU-001", "cantidad": 1, "precio_unitario": 50.0}]
        })
        assert resp_oc_post.status_code == 401
        assert resp_prov_post.get_json() == {"status": "error", "message": "Debe iniciar sesion."}

    def test_operator_permission_boundary(self, operator_client):
        resp_get = operator_client.get("/api/purchase-orders/")
        assert resp_get.status_code == 200
        data = resp_get.get_json()
        assert data["status"] == "success"
        assert isinstance(data["data"], list)

        resp_stats = operator_client.get("/api/purchase-orders/stats")
        assert resp_stats.status_code == 200
        stats = resp_stats.get_json()["data"]
        assert "total" in stats
        assert "pendientes" in stats

    @pytest.mark.xfail(strict=True, reason="BUG-AUTHZ-04: los permisos por modulo no se aplican; un operador de solo lectura crea ordenes de compra")
    def test_operator_cannot_create_purchase_orders(self, operator_client):
        response = operator_client.post("/api/purchase-orders/", json={
            "proveedor_rif": "J-12345678-0",
            "sucursal_id": 1,
            "items": [{"producto_codigo": "CAU-001", "cantidad": 1, "precio_unitario": 50.0}]
        })
        assert response.status_code == 403

    def test_supplier_unique_rif_and_email_check(self, auth_client):
        resp_rif_exist = auth_client.post("/api/suppliers/check-unique", json={
            "field": "rif",
            "value": "J-12345678-0"
        })
        assert resp_rif_exist.status_code == 200
        assert resp_rif_exist.get_json()["exists"] is True

        resp_rif_new = auth_client.post("/api/suppliers/check-unique", json={
            "field": "rif",
            "value": "J-88888888-8"
        })
        assert resp_rif_new.status_code == 200
        assert resp_rif_new.get_json()["exists"] is False

        resp_email_exist = auth_client.post("/api/suppliers/check-unique", json={
            "field": "email",
            "value": "ventas@losandes.com"
        })
        assert resp_email_exist.status_code == 200
        assert resp_email_exist.get_json()["exists"] is True

        resp_email_new = auth_client.post("/api/suppliers/check-unique", json={
            "field": "email",
            "value": "suministros_nuevos@proveedor.com"
        })
        assert resp_email_new.status_code == 200
        assert resp_email_new.get_json()["exists"] is False

    def test_create_and_fetch_new_supplier(self, auth_client):
        new_supplier = {
            "rif": "J-50123456-7",
            "rif_prefijo": "J",
            "nombre": "Distribuidora Repuestos Express C.A.",
            "telefono": "04141112233",
            "email": "express@repuestos.com",
            "direccion": "Av. Las Industrias Galpón 4"
        }
        res_create = auth_client.post("/api/suppliers/", json=new_supplier)
        assert res_create.status_code == 200
        assert res_create.get_json()["status"] == "success"

        res_get = auth_client.get("/api/suppliers/J-50123456-7")
        assert res_get.status_code == 200
        prov = res_get.get_json()["data"]
        assert prov["rif"] == "J-50123456-7"
        assert prov["nombre"] == "Distribuidora Repuestos Express C.A."
        assert prov["email"] == "express@repuestos.com"

        res_active = auth_client.get("/api/suppliers/active")
        assert res_active.status_code == 200
        active_list = res_active.get_json()["data"]
        assert any(p["rif"] == "J-50123456-7" for p in active_list)

    def test_duplicate_supplier_rejection(self, auth_client):
        duplicate_data = {
            "rif": "J-12345678-0",
            "nombre": "Distribuidora Clon",
            "telefono": "04120000000",
            "email": "clon@test.com"
        }
        res = auth_client.post("/api/suppliers/", json=duplicate_data)
        assert res.status_code == 400
        error_json = res.get_json()
        assert "ya esta registrado" in str(error_json.get("errors", {}).get("rif", "")) or "ya esta registrado" in error_json.get("message", "")

    def test_supplier_update_and_soft_delete(self, auth_client):
        update_data = {
            "old_rif": "J-12345678-0",
            "rif": "J-12345678-0",
            "rif_prefijo": "J",
            "nombre": "Distribuidora Repuestos Los Andes Renovada C.A.",
            "telefono": "04129998877",
            "email": "ventas_nuevas@losandes.com",
            "direccion": "Zona Industrial Castillito Torre B"
        }
        res_up = auth_client.put("/api/suppliers/update", json=update_data)
        assert res_up.status_code == 200

        res_check = auth_client.get("/api/suppliers/J-12345678-0")
        assert res_check.status_code == 200
        assert res_check.get_json()["data"]["nombre"] == "Distribuidora Repuestos Los Andes Renovada C.A."
        assert res_check.get_json()["data"]["telefono"] == "04129998877"

        res_toggle = auth_client.put("/api/suppliers/toggle", json={"rif": "J-12345678-0"})
        assert res_toggle.status_code == 200

        res_active = auth_client.get("/api/suppliers/active")
        active_rifs = [p["rif"] for p in res_active.get_json()["data"]]
        assert "J-12345678-0" not in active_rifs

    def test_purchase_order_validation_errors(self, auth_client):
        res_no_prov = auth_client.post("/api/purchase-orders/", json={
            "sucursal_id": 1,
            "items": [{"producto_codigo": "CAU-001", "cantidad": 5, "precio_unitario": 50.0}]
        })
        assert res_no_prov.status_code == 400

        res_no_suc = auth_client.post("/api/purchase-orders/", json={
            "proveedor_rif": "J-98765432-1",
            "items": [{"producto_codigo": "CAU-001", "cantidad": 5, "precio_unitario": 50.0}]
        })
        assert res_no_suc.status_code == 400

        res_invalid_qty = auth_client.post("/api/purchase-orders/", json={
            "proveedor_rif": "J-98765432-1",
            "sucursal_id": 1,
            "items": [{"producto_codigo": "CAU-001", "cantidad": 0, "precio_unitario": 50.0}]
        })
        assert res_invalid_qty.status_code == 400

        res_invalid_price = auth_client.post("/api/purchase-orders/", json={
            "proveedor_rif": "J-98765432-1",
            "sucursal_id": 1,
            "items": [{"producto_codigo": "CAU-001", "cantidad": 5, "precio_unitario": -10.0}]
        })
        assert res_invalid_price.status_code == 400

    def test_create_purchase_order_with_multiple_items_and_totals(self, auth_client):
        order_payload = {
            "proveedor_rif": "J-98765432-1",
            "sucursal_id": 1,
            "observaciones": "Reposición de stock para sucursal principal",
            "items": [
                {
                    "producto_codigo": "CAU-001",
                    "cantidad": 5,
                    "precio_unitario": 40.00
                },
                {
                    "producto_codigo": "BAT-001",
                    "cantidad": 2,
                    "precio_unitario": 75.00
                }
            ]
        }
        res_create = auth_client.post("/api/purchase-orders/", json=order_payload)
        assert res_create.status_code == 200
        order_id = res_create.get_json()["data"]["id"]
        assert order_id is not None

        res_get = auth_client.get(f"/api/purchase-orders/{order_id}")
        assert res_get.status_code == 200
        order = res_get.get_json()["data"]

        assert order["id"] == order_id
        assert order["estado"] == "pendiente"
        assert float(order["total"]) == 350.00
        assert order["proveedor_nombre"] == "Importadora Global Auto C.A."
        assert order["sucursal_nombre"] == "Sede Central"

        detalles = order.get("detalles", [])
        assert len(detalles) == 2
        items_map = {d["producto_codigo"]: d for d in detalles}
        assert "CAU-001" in items_map
        assert items_map["CAU-001"]["cantidad"] == 5
        assert float(items_map["CAU-001"]["precio_unitario"]) == 40.00
        assert "BAT-001" in items_map
        assert items_map["BAT-001"]["cantidad"] == 2
        assert float(items_map["BAT-001"]["precio_unitario"]) == 75.00

    def test_purchase_order_stats_and_list_filtering(self, auth_client):
        auth_client.post("/api/purchase-orders/", json={
            "proveedor_rif": "J-98765432-1",
            "sucursal_id": 1,
            "items": [{"producto_codigo": "CAU-001", "cantidad": 1, "precio_unitario": 45.00}]
        })

        res_stats = auth_client.get("/api/purchase-orders/stats")
        assert res_stats.status_code == 200
        stats = res_stats.get_json()["data"]
        assert stats["total"] >= 1
        assert stats["pendientes"] >= 1

        res_list = auth_client.get("/api/purchase-orders/?estado=pendiente")
        assert res_list.status_code == 200
        orders = res_list.get_json()["data"]
        assert all(o["estado"] == "pendiente" for o in orders)

    def test_mark_as_bought_flow_updates_inventory_stock(self, auth_client, mock_db):
        initial_stock_cau = next(
            (st["stock"] for st in mock_db.stock if st["producto_codigo"] == "CAU-001" and st["sucursal_id"] == 1),
            0
        )
        assert initial_stock_cau == 10

        res_order = auth_client.post("/api/purchase-orders/", json={
            "proveedor_rif": "J-98765432-1",
            "sucursal_id": 1,
            "items": [
                {"producto_codigo": "CAU-001", "cantidad": 6, "precio_unitario": 50.00}
            ]
        })
        assert res_order.status_code == 200
        order_id = res_order.get_json()["data"]["id"]

        res_buy = auth_client.post(f"/api/purchase-orders/{order_id}/buy")
        assert res_buy.status_code == 200
        assert res_buy.get_json()["status"] == "success"

        res_check = auth_client.get(f"/api/purchase-orders/{order_id}")
        assert res_check.status_code == 200
        assert res_check.get_json()["data"]["estado"] == "comprado"

        final_stock_cau = next(
            (st["stock"] for st in mock_db.stock if st["producto_codigo"] == "CAU-001" and st["sucursal_id"] == 1),
            0
        )
        assert final_stock_cau == 16

        res_re_buy = auth_client.post(f"/api/purchase-orders/{order_id}/buy")
        assert res_re_buy.status_code == 400
        assert "ya ha sido procesada" in res_re_buy.get_json()["message"]
