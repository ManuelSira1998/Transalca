import pytest
from unittest.mock import patch
from model.payment_model import PaymentModel
from config.validation import ValidationError


@pytest.fixture
def model():
    return PaymentModel()


class TestPaymentModelValidation:

    @pytest.mark.parametrize("observaciones, is_valid", [
        ("Número de referencia no coincide con el estado de cuenta", True),
        ("Monto transferido no cubre el total de la orden", True),
        ("", False),
        ("   ", False),
        (None, False),
    ])
    @patch.object(PaymentModel, "update")
    @patch.object(PaymentModel, "fetch_one")
    def test_reject_observaciones_data_provider(
        self, mock_fetch_one, mock_update, model, observaciones, is_valid
    ):
        mock_fetch_one.return_value = {"id": 1, "orden_venta_id": 10, "estado": "pendiente"}
        mock_update.return_value = 1

        if is_valid:
            result = model._reject(1, "V-10000000", observaciones)
            assert result is True
        else:
            with pytest.raises(ValidationError) as exc_info:
                model._reject(1, "V-10000000", observaciones)
            assert "observaciones" in exc_info.value.errors


class TestPaymentModelDatabaseOperations:

    @patch.object(PaymentModel, "_attach_client")
    @patch.object(PaymentModel, "fetch_all")
    def test_get_pending(self, mock_fetch_all, mock_attach_client, model):
        mock_fetch_all.return_value = [
            {"id": 1, "orden_venta_id": 10, "estado": "pendiente", "total": 150.00}
        ]
        mock_attach_client.side_effect = lambda x: x
        result = model.ejecutar("get_pending")

        assert len(result) == 1
        assert result[0]["estado"] == "pendiente"
        mock_fetch_all.assert_called_once()

    @patch.object(PaymentModel, "_attach_client")
    @patch.object(PaymentModel, "fetch_all")
    def test_get_all_with_and_without_status(self, mock_fetch_all, mock_attach_client, model):
        mock_fetch_all.return_value = [{"id": 1, "orden_venta_id": 10, "estado": "verificado"}]
        mock_attach_client.side_effect = lambda x: x

        result1 = model.ejecutar("get_all", "verificado")
        assert len(result1) == 1

        result2 = model.ejecutar("get_all")
        assert len(result2) == 1

    @patch.object(PaymentModel, "fetch_one")
    def test_get_by_id_found(self, mock_fetch_one, model):
        mock_fetch_one.side_effect = [
            {"id": 1, "orden_venta_id": 10, "cliente_cedula": "V-12345678"},
            {"nombre": "Ana", "apellido": "López", "email": "ana@ejemplo.com"}
        ]
        with patch.object(PaymentModel, "fetch_all", return_value=[]):
            result = model.ejecutar("get_by_id", 1)

        assert result["id"] == 1
        assert result["nombre"] == "Ana"

    @patch.object(PaymentModel, "fetch_one")
    def test_get_by_id_not_found_returns_none(self, mock_fetch_one, model):
        mock_fetch_one.return_value = None
        result = model.ejecutar("get_by_id", 999)
        assert result is None

    @patch("model.order_model.OrderModel.ejecutar")
    @patch.object(PaymentModel, "update")
    @patch.object(PaymentModel, "fetch_one")
    def test_approve_payment_success(self, mock_fetch_one, mock_update, mock_order_ejecutar, model):
        mock_fetch_one.return_value = {"id": 1, "orden_venta_id": 10, "estado": "pendiente"}
        mock_update.return_value = 1

        result = model.ejecutar("approve", 1, "V-10000000")
        assert result is True
        mock_update.assert_called_once()

    @patch.object(PaymentModel, "fetch_one")
    def test_approve_payment_not_found_returns_false(self, mock_fetch_one, model):
        mock_fetch_one.return_value = None
        result = model.ejecutar("approve", 999)
        assert result is False

    @patch.object(PaymentModel, "fetch_one")
    def test_reject_payment_not_found_returns_false(self, mock_fetch_one, model):
        mock_fetch_one.return_value = None
        result = model.ejecutar("reject", 999, "V-10000000", "Motivo cualquiera")
        assert result is False

    @patch.object(PaymentModel, "fetch_all")
    @patch.object(PaymentModel, "fetch_one")
    def test_get_order_info_for_email_found(self, mock_fetch_one, mock_fetch_all, model):
        mock_fetch_one.side_effect = [
            {"id": 10, "cliente_cedula": "V-12345678", "total": 120.0},
            {"nombre": "Carlos", "email": "carlos@ejemplo.com"}
        ]
        mock_fetch_all.return_value = [{"item_nombre": "Filtro", "subtotal": 120.0}]

        info = model.ejecutar("get_order_info_for_email", 10)
        assert info is not None
        assert info["order"]["id"] == 10
        assert info["client"]["nombre"] == "Carlos"
        assert len(info["details"]) == 1

    @patch.object(PaymentModel, "fetch_one")
    def test_get_order_info_for_email_not_found(self, mock_fetch_one, model):
        mock_fetch_one.return_value = None
        info = model.ejecutar("get_order_info_for_email", 999)
        assert info is None

    def test_ejecutar_invalid_action(self, model):
        with pytest.raises(ValueError) as exc_info:
            model.ejecutar("accion_inexistente")

        assert "Accion no permitida" in str(exc_info.value)
