import pytest
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock
from model.credit_model import CreditModel
from config.validation import ValidationError


@pytest.fixture
def model():
    """Instancia del modelo de crédito para pruebas."""
    return CreditModel()


class TestCreditModelHelpers:

    @pytest.mark.parametrize("input_val, expected_decimal", [
        (100, Decimal("100.00")),
        ("50.5", Decimal("50.50")),
        ("1200.758", Decimal("1200.76")),
        (None, Decimal("0.00")),
        ("invalido", Decimal("0.00")),
    ])
    def test_as_money(self, model, input_val, expected_decimal):
        assert model._as_money(input_val) == expected_decimal

    @pytest.mark.parametrize("saldo, days_offset, expected_estado", [
        (0.00, 10, "pagado"),
        (-5.00, -10, "pagado"),
        (150.00, -1, "vencido"),
        (150.00, 10, "activo"),
    ])
    def test_estado_por_saldo(self, model, saldo, days_offset, expected_estado):
        fecha_fin = date.today() + timedelta(days=days_offset)
        assert model._estado_por_saldo(saldo, fecha_fin) == expected_estado


class TestCreditModelValidation:

    @pytest.mark.parametrize("amount, is_valid", [
        (100, True),
        ("250.75", True),
        (0, False),
        (-50, False),
        ("abc", False),
        ("", False),
    ])
    def test_validate_amount(self, model, amount, is_valid):
        errors = {}
        result = model._validate_amount(amount, "total", errors, "El monto")

        if is_valid:
            assert result > 0
            assert "total" not in errors
        else:
            assert result is None
            assert "total" in errors

    def test_validate_credit_dates_end_before_start_fails(self, model):
        errors = {}
        start = model._validate_date("2026-08-20", "fecha_inicio", errors)
        end = model._validate_date("2026-08-10", "fecha_fin", errors)

        if start and end and end < start:
            errors['fecha_fin'] = "La fecha fin no puede ser menor a la fecha inicio."

        assert "fecha_fin" in errors

    def test_create_credit_validation_errors(self, model):
        data = {
            "cliente_cedula": "",
            "total": -10,
            "fecha_inicio": "2026-08-20",
            "fecha_fin": "2026-08-10"
        }
        with pytest.raises(ValidationError) as exc:
            model.ejecutar("create_credit", data)
        assert "cliente_cedula" in exc.value.errors
        assert "total" in exc.value.errors
        assert "fecha_fin" in exc.value.errors


class TestCreditModelDatabaseOperations:

    @patch.object(CreditModel, "fetch_all")
    @patch.object(CreditModel, "_safe_sync_credit_statuses")
    def test_get_all(self, mock_sync, mock_fetch_all, model):
        mock_fetch_all.return_value = [
            {"id": 1, "cliente_cedula": "J-12345678-9", "credito_estado": "activo", "monto_deuda": 500.00}
        ]
        result = model.ejecutar("get_all")

        assert len(result) == 1
        assert result[0]["credito_estado"] == "activo"
        mock_fetch_all.assert_called_once()

    @patch.object(CreditModel, "fetch_one")
    @patch.object(CreditModel, "_safe_sync_credit_statuses")
    def test_get_stats(self, mock_sync, mock_fetch_one, model):
        mock_fetch_one.return_value = {
            "total": 10,
            "pendientes": 5,
            "pagados": 3,
            "vencidos": 2,
            "saldo": 2500.00
        }
        stats = model.ejecutar("get_stats")

        assert stats["total"] == 10
        assert stats["pendientes"] == 5
        assert stats["pagados"] == 3

    def test_update_status(self, model):
        with patch.object(CreditModel, "update", return_value=1) as mock_update:
            result = model.ejecutar("update_status", 1, "activo")
            assert result == 1
            mock_update.assert_called_once()

    def test_update_status_invalid_value_raises_error(self, model):
        with pytest.raises(ValidationError) as exc_info:
            model.ejecutar("update_status", 1, "estado_invalido")
        assert "estado" in exc_info.value.errors

    def test_get_by_order(self, model):
        with patch.object(CreditModel, "fetch_one", return_value={"id": 1, "credito_estado": "activo"}):
            res = model.ejecutar("get_by_order", 100)
            assert res["id"] == 1

    def test_get_payments(self, model):
        with patch.object(CreditModel, "fetch_all", return_value=[{"id": 1, "monto_pago": 50.0}]):
            payments = model.ejecutar("get_payments", 1)
            assert len(payments) == 1

    def test_create_credit_for_order(self, model):
        with patch.object(CreditModel, "insert", return_value=1):
            res = model.ejecutar("create_credit_for_order", 100, dias_credito=30)
            assert res == 1

    @pytest.mark.parametrize("credit_data, expected_ok, expected_msg", [
        (None, False, "Crédito no encontrado"),
        ({"credito_estado": "anulado"}, False, "ya está anulado"),
        ({"credito_estado": "pagado"}, False, "No se puede anular un crédito pagado"),
    ])
    def test_anular_credit_validation(self, model, credit_data, expected_ok, expected_msg):
        with patch.object(CreditModel, "_get_by_order", return_value=credit_data):
            res = model.ejecutar("anular_credit", 100)
            assert res["ok"] is expected_ok
            assert expected_msg in res["message"]

    def test_anular_credit_success(self, model):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.object(CreditModel, "_get_by_order", return_value={"credito_estado": "activo"}), \
             patch.object(CreditModel, "con_transalca", return_value=mock_conn), \
             patch.object(CreditModel, "_log_credito"):
            res = model.ejecutar("anular_credit", 100)
            assert res["ok"] is True
            mock_conn.commit.assert_called_once()

    def test_revert_last_payment_no_payments(self, model):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None  # no hay abonos
        mock_conn.cursor.return_value = mock_cursor

        with patch.object(CreditModel, "_get_by_order", return_value={"id": 1, "credito_estado": "activo"}), \
             patch.object(CreditModel, "con_transalca", return_value=mock_conn):
            res = model.ejecutar("revert_last_payment", 100)
            assert res["ok"] is False
            assert "No hay abonos" in res["message"]
            mock_conn.rollback.assert_called_once()

    def test_ejecutar_invalid_action(self, model):
        with pytest.raises(ValueError) as exc_info:
            model.ejecutar("accion_inexistente")
        assert "Accion no permitida" in str(exc_info.value)


class TestCreditNotifications:

    @patch("model.mail_service.MailService.send_credit_reminder_7d")
    @patch.object(CreditModel, "update")
    @patch.object(CreditModel, "fetch_one", return_value={"monto": 45.00})
    @patch.object(CreditModel, "fetch_all")
    def test_sync_credit_7d_notification(self, mock_fetch_all, mock_fetch_one, mock_update, mock_mail, model):
        mock_fetch_all.return_value = [{
            "id_credito": 1,
            "id": 101,
            "estado_credito": "activo",
            "fecha_vencimiento_credito": date.today() + timedelta(days=6),
            "monto_deuda": Decimal("500.00"),
            "notificacion_7d": 0,
            "notificacion_2d": 0,
            "notificacion_vencido": 0,
            "email": "empresa@correo.com",
            "razon_social": "Corporacion ABC",
            "rif": "J-12345678-0",
            "tipo_cliente": "juridica"
        }]

        model.ejecutar("sync_credit_statuses")

        mock_mail.assert_called_once()
        mock_update.assert_called_with(
            "transalca",
            "UPDATE creditos_orden_venta SET notificacion_7d = 1 WHERE id_credito = %s",
            (1,)
        )

    @patch("model.mail_service.MailService.send_credit_alert_2d")
    @patch.object(CreditModel, "update")
    @patch.object(CreditModel, "fetch_one", return_value={"monto": 45.00})
    @patch.object(CreditModel, "fetch_all")
    def test_sync_credit_2d_notification(self, mock_fetch_all, mock_fetch_one, mock_update, mock_mail, model):
        mock_fetch_all.return_value = [{
            "id_credito": 2,
            "id": 102,
            "estado_credito": "activo",
            "fecha_vencimiento_credito": date.today() + timedelta(days=1),
            "monto_deuda": Decimal("850.00"),
            "notificacion_7d": 1,
            "notificacion_2d": 0,
            "notificacion_vencido": 0,
            "email": "empresa2@correo.com",
            "razon_social": "Distribuidora XYZ",
            "rif": "J-87654321-0",
            "tipo_cliente": "juridica"
        }]

        model.ejecutar("sync_credit_statuses")

        mock_mail.assert_called_once()
        mock_update.assert_called_with(
            "transalca",
            "UPDATE creditos_orden_venta SET notificacion_2d = 1, notificacion_7d = 1 WHERE id_credito = %s",
            (2,)
        )

    @patch("model.mail_service.MailService.send_credit_expired")
    @patch.object(CreditModel, "update")
    @patch.object(CreditModel, "fetch_one", return_value={"monto": 45.00})
    @patch.object(CreditModel, "fetch_all")
    def test_sync_credit_expired_notification(self, mock_fetch_all, mock_fetch_one, mock_update, mock_mail, model):
        mock_fetch_all.return_value = [{
            "id_credito": 3,
            "id": 103,
            "estado_credito": "activo",
            "fecha_vencimiento_credito": date.today() - timedelta(days=2),
            "monto_deuda": Decimal("300.00"),
            "notificacion_7d": 1,
            "notificacion_2d": 1,
            "notificacion_vencido": 0,
            "email": "empresa3@correo.com",
            "razon_social": "Inversiones Norte",
            "rif": "J-11223344-5",
            "tipo_cliente": "juridica"
        }]

        model.ejecutar("sync_credit_statuses")

        mock_mail.assert_called_once()
        update_calls = [c[0][1] for c in mock_update.call_args_list]
        assert any("estado_credito = 'vencido'" in sql for sql in update_calls)
        assert any("notificacion_vencido = 1" in sql for sql in update_calls)

    @patch("model.mail_service.MailService.send_credit_reminder_7d")
    @patch.object(CreditModel, "update")
    @patch.object(CreditModel, "fetch_one", return_value=None)
    @patch.object(CreditModel, "fetch_all")
    def test_sync_credit_ignores_non_juridica(self, mock_fetch_all, mock_fetch_one, mock_update, mock_mail, model):
        mock_fetch_all.return_value = [{
            "id_credito": 4,
            "id": 104,
            "estado_credito": "activo",
            "fecha_vencimiento_credito": date.today() + timedelta(days=5),
            "monto_deuda": Decimal("150.00"),
            "notificacion_7d": 0,
            "notificacion_2d": 0,
            "notificacion_vencido": 0,
            "email": "persona@correo.com",
            "razon_social": "Pedro Perez",
            "rif": "V-12345678",
            "tipo_cliente": "natural"
        }]

        model.ejecutar("sync_credit_statuses")

        mock_mail.assert_not_called()
