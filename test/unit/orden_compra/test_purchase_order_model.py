import pytest
from decimal import Decimal
from datetime import datetime, date
from unittest.mock import patch, MagicMock
from model.purchase_order_model import PurchaseOrderModel
from config.validation import ValidationError


@pytest.fixture
def model():
    return PurchaseOrderModel()


class TestPurchaseOrderModelHelpersAndValidation:

    @pytest.mark.parametrize("input_val, expected_date", [
        (datetime(2026, 8, 20, 14, 30), date(2026, 8, 20)),
        (date(2026, 8, 20), date(2026, 8, 20)),
        ("2026-08-20T10:00:00", date(2026, 8, 20)),
        ("2026-08-20", date(2026, 8, 20)),
        (None, None),
    ])
    def test_as_date_data_provider(self, input_val, expected_date):
        model = PurchaseOrderModel()
        assert model._as_date(input_val) == expected_date

    @pytest.mark.parametrize("input_val, expected_decimal", [
        (100, Decimal("100.00")),
        ("45.50", Decimal("45.50")),
        ("120.758", Decimal("120.76")),
        (None, Decimal("0.00")),
        ("invalido", Decimal("0.00")),
    ])
    def test_as_money_data_provider(self, input_val, expected_decimal):
        model = PurchaseOrderModel()
        assert model._as_money(input_val) == expected_decimal

    @pytest.mark.parametrize("data, is_valid, expected_error_key", [
        ({
            "proveedor_rif": "J-12345678-0",
            "sucursal_id": 1,
            "items": [{"producto_codigo": "PROD001", "cantidad": 5, "precio_unitario": "10.00"}]
        }, True, None),
        ({
            "proveedor_rif": "",
            "sucursal_id": 1,
            "items": [{"producto_codigo": "PROD001", "cantidad": 5, "precio_unitario": "10.00"}]
        }, False, "proveedor_rif"),
        ({
            "proveedor_rif": "J-12345678-0",
            "sucursal_id": None,
            "items": [{"producto_codigo": "PROD001", "cantidad": 5, "precio_unitario": "10.00"}]
        }, False, "sucursal_id"),
        ({
            "proveedor_rif": "J-12345678-0",
            "sucursal_id": 1,
            "items": []
        }, False, "items"),
        ({
            "proveedor_rif": "J-12345678-0",
            "sucursal_id": 1,
            "items": [{"producto_codigo": "", "cantidad": 5, "precio_unitario": "10.00"}]
        }, False, "items_0_code"),
        ({
            "proveedor_rif": "J-12345678-0",
            "sucursal_id": 1,
            "items": [{"producto_codigo": "PROD001", "cantidad": 0, "precio_unitario": "10.00"}]
        }, False, "items_0_qty"),
        ({
            "proveedor_rif": "J-12345678-0",
            "sucursal_id": 1,
            "items": [{"producto_codigo": "PROD001", "cantidad": 5, "precio_unitario": "-5.00"}]
        }, False, "items_0_price"),
    ])
    def test_validate_data_provider(self, data, is_valid, expected_error_key):
        model = PurchaseOrderModel()
        if is_valid:
            model._validate(data)
        else:
            with pytest.raises(ValidationError) as exc_info:
                model._validate(data)
            assert expected_error_key in exc_info.value.errors


class TestPurchaseOrderModelTransactionsAndDatabase:

    @patch.object(PurchaseOrderModel, "fetch_all")
    def test_get_all_with_filters(self, mock_fetch_all):
        mock_fetch_all.return_value = [
            {"id": 1, "proveedor_nombre": "Distribuidora A", "total": 1500.0}
        ]
        model = PurchaseOrderModel()
        orders = model.ejecutar("get_all", "Distribuidora", "pendiente")

        assert len(orders) == 1
        assert orders[0]["id"] == 1
        mock_fetch_all.assert_called_once()

    @patch.object(PurchaseOrderModel, "fetch_one")
    def test_get_stats(self, mock_fetch_one):
        mock_fetch_one.return_value = {
            "total": 10, "pendientes": 3, "comprados": 7, "total_invertido": 12500.00
        }
        model = PurchaseOrderModel()
        stats = model.ejecutar("get_stats")

        assert stats["total"] == 10
        assert stats["pendientes"] == 3
        assert stats["total_invertido"] == 12500.00

    @patch.object(PurchaseOrderModel, "fetch_all")
    @patch.object(PurchaseOrderModel, "fetch_one")
    def test_get_by_id(self, mock_fetch_one, mock_fetch_all):
        mock_fetch_one.return_value = {
            "id": 1, "proveedor_nombre": "Proveedor X", "total": 300.0
        }
        mock_fetch_all.return_value = [
            {"id": 10, "producto_codigo": "PROD001", "cantidad": 3, "precio_unitario": 100.0}
        ]
        model = PurchaseOrderModel()
        order = model.ejecutar("get_by_id", 1)

        assert order["id"] == 1
        assert len(order["detalles"]) == 1

    @patch.object(PurchaseOrderModel, "_validate")
    def test_create_transaction_success(self, mock_validate):
        model = PurchaseOrderModel()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.lastrowid = 100

        mock_cursor.fetchone.side_effect = [
            {"id_sucursal": 1},
            {"rif_proveedor": "J-12345678-0"},
            {"codigo": "PROD001"}
        ]

        with patch.object(PurchaseOrderModel, "con_transalca", return_value=mock_conn):
            data = {
                "proveedor_rif": "J-12345678-0",
                "sucursal_id": 1,
                "observaciones": "Compra mensual",
                "items": [{"producto_codigo": "PROD001", "cantidad": 10, "precio_unitario": 25.0}]
            }
            res = model.ejecutar("create", data)

            assert res["ok"] is True
            assert res["id"] == 100
            mock_conn.begin.assert_called_once()
            mock_conn.commit.assert_called_once()
            mock_conn.rollback.assert_not_called()

    @patch.object(PurchaseOrderModel, "_validate")
    def test_create_transaction_inactive_sucursal_rollback(self, mock_validate):
        model = PurchaseOrderModel()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None

        with patch.object(PurchaseOrderModel, "con_transalca", return_value=mock_conn):
            data = {"proveedor_rif": "J-12345678-0", "sucursal_id": 999, "items": [{"producto_codigo": "P1", "cantidad": 1, "precio_unitario": 10}]}
            res = model.ejecutar("create", data)

            assert res["ok"] is False
            assert "sucursal destino no existe" in res["message"]
            mock_conn.rollback.assert_called_once()
            mock_conn.commit.assert_not_called()

    @patch.object(PurchaseOrderModel, "_validate")
    def test_create_transaction_inactive_product_rollback(self, mock_validate):
        model = PurchaseOrderModel()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.lastrowid = 100
        mock_cursor.fetchone.side_effect = [
            {"id_sucursal": 1},
            {"rif_proveedor": "J-12345678-0"},
            None
        ]

        with patch.object(PurchaseOrderModel, "con_transalca", return_value=mock_conn):
            data = {"proveedor_rif": "J-12345678-0", "sucursal_id": 1, "items": [{"producto_codigo": "NOEXISTE", "cantidad": 1, "precio_unitario": 10}]}
            res = model.ejecutar("create", data)

            assert res["ok"] is False
            assert "no existe o esta inactivo" in res["message"]
            mock_conn.rollback.assert_called_once()
            mock_conn.commit.assert_not_called()

    def test_mark_as_bought_transaction_success(self):
        model = PurchaseOrderModel()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchone.side_effect = [
            {"id": 1, "sucursal_id": 1, "estado": "pendiente"},
            {"stock": 10}
        ]
        mock_cursor.fetchall.return_value = [
            {"producto_codigo": "PROD001", "cantidad": 5}
        ]

        with patch.object(PurchaseOrderModel, "con_transalca", return_value=mock_conn):
            res = model.ejecutar("mark_as_bought", 1)

            assert res["ok"] is True
            assert "Stock actualizado" in res["message"]
            mock_conn.begin.assert_called_once()
            mock_conn.commit.assert_called_once()
            mock_conn.rollback.assert_not_called()

    def test_mark_as_bought_already_processed_rollback(self):
        model = PurchaseOrderModel()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchone.return_value = {"id": 1, "sucursal_id": 1, "estado": "comprado"}

        with patch.object(PurchaseOrderModel, "con_transalca", return_value=mock_conn):
            res = model.ejecutar("mark_as_bought", 1)

            assert res["ok"] is False
            assert "ya ha sido procesada" in res["message"]
            mock_conn.rollback.assert_called_once()
            mock_conn.commit.assert_not_called()

    def test_mark_as_bought_insert_new_stock_when_not_exists(self):
        model = PurchaseOrderModel()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchone.side_effect = [
            {"id": 2, "sucursal_id": 1, "estado": "pendiente"},
            None
        ]
        mock_cursor.fetchall.return_value = [
            {"producto_codigo": "PROD002", "cantidad": 10}
        ]

        with patch.object(PurchaseOrderModel, "con_transalca", return_value=mock_conn):
            res = model.ejecutar("mark_as_bought", 2)

            assert res["ok"] is True
            mock_conn.commit.assert_called_once()
            executed_sql = [call[0][0] for call in mock_cursor.execute.call_args_list]
            assert any("INSERT INTO stock" in sql for sql in executed_sql)

    def test_ejecutar_invalid_action(self):
        model = PurchaseOrderModel()
        with pytest.raises(ValueError) as exc_info:
            model.ejecutar("accion_inexistente")

        assert "Accion no permitida" in str(exc_info.value)
