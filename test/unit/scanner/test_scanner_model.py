import pytest
from unittest.mock import patch
from model.scanner_model import ScannerModel


@pytest.fixture
def model():
    return ScannerModel()


class TestScannerModelResolvers:

    @pytest.mark.parametrize("raw_input, expected_id, is_valid", [
        ("15", 15, True),
        ("http://localhost/scanner?qr=15", 15, True),
        ("http://transalca.com/client/qr_scan?id=20", 20, True),
        ("/scanner?qr=99", 99, True),
        ("", None, False),
        ("codigo_qr_no_sistema", None, False),
    ])
    def test_resolve_qr_from_raw(self, model, raw_input, expected_id, is_valid):
        with patch.object(ScannerModel, "_get_active_qr_by_id", return_value={"id": expected_id, "tipo": "pago"} if expected_id else None):
            qr, error = model.ejecutar("resolve_qr_from_raw", raw_input)
            if is_valid:
                assert qr is not None
                assert qr["id"] == expected_id
                assert error is None
            else:
                assert qr is None
                assert error is not None


class TestScannerModelUtilityState:

    @pytest.mark.parametrize("contenido, expected_active, expected_msg_part", [
        ('{"utilidad": "info"}', False, "no tiene nada todavia"),
        ('{"utilidad": "pago", "estado": "cumplida"}', False, "ya fue utilizado"),
        ('{"utilidad": "pago", "estado": "usado"}', False, "ya fue utilizado"),
        ('{"utilidad": "promocion", "estado": "activa", "referencia_id": 5}', True, "activa"),
    ])
    def test_get_utility_state(self, model, contenido, expected_active, expected_msg_part):
        qr = {"id": 1, "tipo": "promocion", "contenido": contenido}
        state = model._get_utility_state(qr)
        assert state["active"] == expected_active
        assert expected_msg_part in state["message"].lower()


class TestScannerModelDatabaseOperations:

    def test_process_scan_for_employee_factura_valid(self, model):
        with patch.object(ScannerModel, "_get_utility_state", return_value={
            "active": True,
            "utility": "factura",
            "reference_id": 10,
            "content": {"kind": "factura", "orden_id": 10}
        }), patch.object(ScannerModel, "_mark_completed"), \
             patch.object(ScannerModel, "_get_order_full", return_value={"id": 10, "total": 250.00, "cliente_cedula": "V-12345678"}):
            qr = {"id": 1, "tipo": "pago", "referencia_id": 10, "contenido": "{}"}
            result = model.ejecutar("process_scan_for_employee", qr)

            assert result["mode"] == "factura_validada"
            assert result["order"]["id"] == 10

    def test_process_scan_for_employee_inactive_qr(self, model):
        with patch.object(ScannerModel, "_get_utility_state", return_value={
            "active": False,
            "message": "QR no disponible"
        }):
            qr = {"id": 1, "tipo": "pago", "contenido": "{}"}
            result = model.ejecutar("process_scan_for_employee", qr)
            assert result["mode"] == "qr_sin_utilidad"
            assert result["message"] == "QR no disponible"

    @pytest.mark.parametrize("order_client, expected_mode", [
        ("V-12345678", "factura_cliente"),
        ("V-87654321", "factura_restringida"),
        (None, "factura_invalida"),
    ])
    def test_process_scan_for_client_factura(self, model, order_client, expected_mode):
        with patch.object(ScannerModel, "_get_utility_state", return_value={
            "active": True,
            "utility": "factura",
            "reference_id": 10,
            "content": {"kind": "factura", "orden_id": 10}
        }), patch.object(ScannerModel, "_get_order_full", return_value={"id": 10, "cliente_cedula": order_client} if order_client else None):
            qr = {"id": 1, "tipo": "pago", "referencia_id": 10, "contenido": "{}"}
            result = model.ejecutar("process_scan_for_client", qr, "V-12345678")
            assert result["mode"] == expected_mode

    def test_get_active_promotions(self, model):
        with patch.object(ScannerModel, "fetch_all", return_value=[
            {"id": 1, "nombre": "Promo 5to Cambio", "puntos_requeridos": 5}
        ]):
            promos = model.ejecutar("get_active_promotions")
            assert len(promos) == 1
            assert promos[0]["nombre"] == "Promo 5to Cambio"

    def test_set_order_and_comprobante_status(self, model):
        with patch.object(ScannerModel, "update", return_value=1) as mock_update:
            assert model.ejecutar("set_order_status", 10, "pagado") == 1
            assert model.ejecutar("set_comprobante_status", 5, "aprobado") == 1
            assert mock_update.call_count == 2

    def test_validation_request_lifecycle(self, model):
        with patch.object(ScannerModel, "insert", return_value=1), \
             patch.object(ScannerModel, "fetch_all", return_value=[{"id": 1, "estado": "pendiente"}]), \
             patch.object(ScannerModel, "update", return_value=1):
            assert model.ejecutar("create_validation_request", "pago", 10) == 1
            validations = model.ejecutar("get_pending_validations")
            assert len(validations) == 1
            assert model.ejecutar("mark_alert_seen", 1) == 1
            assert model.ejecutar("set_validation_status", 1, "aprobada") == 1

    def test_ejecutar_invalid_action(self, model):
        with pytest.raises(ValueError) as exc_info:
            model.ejecutar("accion_inexistente")
        assert "Accion no permitida" in str(exc_info.value)
