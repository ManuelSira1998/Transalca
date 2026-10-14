import pytest
from unittest.mock import patch, MagicMock
from model.inventory_model import InventoryModel
from config.validation import ValidationError


@pytest.fixture
def model():
    """Instancia del modelo de inventario para pruebas."""
    return InventoryModel()


class TestInventoryModelHelpers:
    """Pruebas unitarias para metodos auxiliares del modelo de inventario/stock."""

    @pytest.mark.parametrize("config_val, expected", [
        ({"valor": "8"}, 8),
        ({"valor": "12"}, 12),
        ({"valor": "0"}, 0),
        ({"valor": "no_num"}, 5),
        (None, 5),
    ])
    def test_get_low_stock_threshold(self, model, config_val, expected):
        with patch.object(InventoryModel, "fetch_one", return_value=config_val):
            assert model.ejecutar("get_low_stock_threshold") == expected

    @pytest.mark.parametrize("usuarios_row, cliente_row, expected_name", [
        ({"nombre": "Ana", "apellido": "Gomez"}, None, "Ana Gomez"),
        (None, {"nombre_cliente": "Empresa ABC"}, "Empresa ABC"),
        (None, None, "N/A"),
    ])
    def test_client_name_resolution(self, model, usuarios_row, cliente_row, expected_name):
        with patch.object(InventoryModel, "fetch_one") as mock_fetch:
            if usuarios_row:
                mock_fetch.return_value = usuarios_row
            else:
                mock_fetch.side_effect = [None, cliente_row]
            name = model._client_name("V-12345678")
            assert name == expected_name


class TestInventoryModelValidationAndStockUpdates:
    """Pruebas unitarias con Data Provider (@pytest.mark.parametrize) para validaciones y operaciones de stock."""

    @pytest.mark.parametrize("data, is_valid, expected_error_key", [
        ({"producto_codigo": "PROD001", "stock": 10, "sucursal_id": 1}, True, None),
        ({"producto_codigo": "PROD001", "stock": "0", "sucursal_id": 1}, True, None),
        ({"producto_codigo": "PROD001", "stock": 50}, True, None),  # Sin sucursal
        ({"producto_codigo": "", "stock": 10}, False, "producto_codigo"),
        ({"producto_codigo": None, "stock": 10}, False, "producto_codigo"),
        ({"producto_codigo": "PROD001", "stock": -5}, False, "stock"),
        ({"producto_codigo": "PROD001", "stock": "invalido"}, False, "stock"),
        ({"producto_codigo": "PROD001"}, False, "stock"),
    ])
    def test_update_stock_validation(self, model, data, is_valid, expected_error_key):
        if is_valid:
            with patch.object(InventoryModel, "fetch_one", return_value={"producto_codigo": "PROD001"}), \
                 patch.object(InventoryModel, "update", return_value=1), \
                 patch.object(InventoryModel, "_check_low_stock_and_notify", return_value=0):
                res = model.ejecutar("update_stock", data)
                assert res == 1
        else:
            with pytest.raises(ValidationError) as exc_info:
                model.ejecutar("update_stock", data)
            assert expected_error_key in exc_info.value.errors

    def test_update_stock_inserts_new_branch_record(self, model):
        with patch.object(InventoryModel, "fetch_one", return_value=None), \
             patch.object(InventoryModel, "insert", return_value=1) as mock_insert, \
             patch.object(InventoryModel, "_check_low_stock_and_notify"):
            data = {"producto_codigo": "PROD001", "sucursal_id": 2, "stock": 15}
            res = model.ejecutar("update_stock", data)
            assert res == 1
            mock_insert.assert_called_once()

    def test_update_stock_without_sucursal(self, model):
        with patch.object(InventoryModel, "update", return_value=1) as mock_update, \
             patch.object(InventoryModel, "_check_low_stock_and_notify"):
            data = {"producto_codigo": "PROD001", "stock": 25}
            res = model.ejecutar("update_stock", data)
            assert res == 1
            mock_update.assert_called_once()

    def test_update_stock_handles_notification_exception(self, model):
        with patch.object(InventoryModel, "fetch_one", return_value={"producto_codigo": "PROD001"}), \
             patch.object(InventoryModel, "update", return_value=1), \
             patch.object(InventoryModel, "_check_low_stock_and_notify", side_effect=Exception("Notification error")):
            data = {"producto_codigo": "PROD001", "sucursal_id": 1, "stock": 2}
            res = model.ejecutar("update_stock", data)
            assert res == 1  # No se propaga la excepcion, solo loggea

    @pytest.mark.parametrize("sucursal_id", [1, None])
    def test_update_min_stock(self, model, sucursal_id):
        with patch.object(InventoryModel, "update", return_value=1) as mock_update:
            res = model.ejecutar("update_min_stock", "PROD001", 10, sucursal_id=sucursal_id)
            assert res == 1
            mock_update.assert_called_once()

    def test_check_low_stock_and_notify_success(self, model):
        low_items = [
            {"codigo": "PROD001", "producto_nombre": "Filtro", "stock": 2, "stock_minimo": 5, "sucursal_nombre": "Central"},
            {"codigo": "PROD002", "producto_nombre": None, "stock": 0, "stock_minimo": None, "sucursal_nombre": None}
        ]
        with patch.object(InventoryModel, "_get_low_stock_threshold", return_value=5), \
             patch.object(InventoryModel, "_get_low_stock", return_value=low_items), \
             patch("model.inventory_model.NotificationModel.ejecutar", return_value=1) as mock_notify:
            notified = model.ejecutar("check_low_stock_and_notify", "PROD001")
            assert notified == 2
            assert mock_notify.call_count == 2

    def test_check_low_stock_and_notify_empty(self, model):
        with patch.object(InventoryModel, "_get_low_stock_threshold", return_value=5), \
             patch.object(InventoryModel, "_get_low_stock", return_value=[]):
            notified = model.ejecutar("check_low_stock_and_notify")
            assert notified == 0


class TestInventoryModelQueries:
    """Pruebas unitarias para consultas y paginacion de inventario y detalle de ordenes de venta."""

    def test_get_all(self, model):
        with patch.object(InventoryModel, "fetch_all", return_value=[{"codigo": "PROD001", "stock": 15}]):
            res = model.ejecutar("get_all")
            assert len(res) == 1
            assert res[0]["codigo"] == "PROD001"

    def test_get_by_sucursal(self, model):
        with patch.object(InventoryModel, "fetch_all", return_value=[{"codigo": "PROD001", "sucursal_id": 1, "stock": 10}]):
            res = model.ejecutar("get_by_sucursal", 1)
            assert len(res) == 1
            assert res[0]["sucursal_id"] == 1

    @pytest.mark.parametrize("sucursal_id, q, total, expected_pages, input_page, expected_page", [
        (1, "Filtro", 20, 2, 1, 1),
        (None, None, 50, 5, 2, 2),
        (None, None, 10, 1, 99, 1),  # page > pages ajusta page a pages
        (None, None, 0, 0, 1, 1),    # total 0
    ])
    def test_get_paginated(self, model, sucursal_id, q, total, expected_pages, input_page, expected_page):
        with patch.object(InventoryModel, "fetch_one", return_value={"total": total} if total else None), \
             patch.object(InventoryModel, "fetch_all", return_value=[{"codigo": "PROD001"}] if total else []):
            pag = model.ejecutar("get_paginated", input_page, 10, sucursal_id=sucursal_id, q=q)
            assert pag["total"] == total
            assert pag["pages"] == expected_pages
            assert pag["page"] == expected_page

    @pytest.mark.parametrize("producto_codigo", ["PROD001", None])
    def test_get_low_stock(self, model, producto_codigo):
        with patch.object(InventoryModel, "_get_low_stock_threshold", return_value=5), \
             patch.object(InventoryModel, "fetch_all", return_value=[{"codigo": "PROD001", "stock": 1}]):
            low = model.ejecutar("get_low_stock", producto_codigo)
            assert len(low) == 1

    def test_get_sales_orders(self, model):
        with patch.object(InventoryModel, "fetch_all", return_value=[
            {"id": 1, "cliente_cedula": "V-12345678", "total": 200.0}
        ]), patch.object(InventoryModel, "_client_name", return_value="Carlos Mendoza"):
            orders = model.ejecutar("get_sales_orders")
            assert len(orders) == 1
            assert orders[0]["cliente_nombre"] == "Carlos Mendoza"

    def test_get_sales_order_detail_found(self, model):
        with patch.object(InventoryModel, "fetch_one") as mock_fetch_one, \
             patch.object(InventoryModel, "fetch_all") as mock_fetch_all:
            mock_fetch_one.side_effect = [
                {"id": 1, "cliente_cedula": "V-12345678", "total": 100.0},
                {"nombre": "Carlos", "apellido": "Mendoza", "email": "c@mail.com", "telefono": "123"}
            ]
            mock_fetch_all.return_value = [
                {"id": 1, "item_nombre": "Filtro", "cantidad": 2, "precio_unitario": 50.0}
            ]
            detail = model.ejecutar("get_sales_order_detail", 1)
            assert detail["id"] == 1
            assert detail["cliente_nombre"] == "Carlos Mendoza"
            assert detail["cliente_email"] == "c@mail.com"
            assert len(detail["detalles"]) == 1

    def test_get_sales_order_detail_not_found(self, model):
        with patch.object(InventoryModel, "fetch_one", return_value=None):
            detail = model.ejecutar("get_sales_order_detail", 999)
            assert detail is None

    def test_ejecutar_invalid_action(self, model):
        with pytest.raises(ValueError) as exc_info:
            model.ejecutar("accion_inexistente")
        assert "Accion no permitida" in str(exc_info.value)
