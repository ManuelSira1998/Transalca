import pytest
import json
from unittest.mock import patch
from model.qr_model import QRModel, qr_tipo_to_int
from config.validation import ValidationError


@pytest.fixture
def model():
    return QRModel()


class TestQRModelHelpers:

    @pytest.mark.parametrize("tipo_str, expected_int", [
        ("info", 0),
        ("pago", 1),
        ("promocion", 2),
        ("servicio", 3),
        ("INFO", 0),
        ("PAGO", 1),
        (2, 2),
        ("desconocido", 0),
    ])
    def test_qr_tipo_to_int(self, tipo_str, expected_int):
        assert qr_tipo_to_int(tipo_str) == expected_int

    @pytest.mark.parametrize("content, expected_type", [
        ('{"clave": "valor"}', dict),
        ({"clave": "valor"}, dict),
        ("", dict),
        ("texto_plano_invalido", dict),
        (None, dict),
    ])
    def test_parse_content(self, model, content, expected_type):
        res = model._parse_content(content)
        assert isinstance(res, expected_type)


class TestQRModelValidation:

    @pytest.mark.parametrize("tipo_valido, utilidad_valida", [
        ("info", "catalogo"),
        ("pago", "validar_pago"),
        ("promocion", "canje_puntos"),
        ("servicio", "reserva_mecanico"),
    ])
    def test_validate_valid_qr(self, model, tipo_valido, utilidad_valida):
        data = {
            "tipo": tipo_valido,
            "utilidad_tipo": utilidad_valida,
            "referencia_id": 10 if tipo_valido == "promocion" else None
        }
        model.ejecutar("validate", data)

    @pytest.mark.parametrize("invalid_data, expected_field", [
        ({"tipo": "", "utilidad_tipo": "info"}, "tipo"),
        ({"tipo": "tipo_inexistente", "utilidad_tipo": "info"}, "tipo"),
        ({"tipo": "info", "utilidad_tipo": ""}, "utilidad_tipo"),
        ({"tipo": "promocion", "utilidad_tipo": "promocion", "referencia_id": ""}, "referencia_id"),
    ])
    def test_validate_invalid_qr(self, model, invalid_data, expected_field):
        with pytest.raises(ValidationError) as exc_info:
            model.ejecutar("validate", invalid_data)
        assert expected_field in exc_info.value.errors


class TestQRModelDatabaseOperations:

    def test_get_user_qrs(self, model):
        with patch.object(QRModel, "fetch_all", return_value=[
            {"id": 1, "tipo": "pago", "referencia_id": 10, "estado": 1}
        ]) as mock_fetch:
            result = model.ejecutar("get_user_qrs", "V-12345678")
            assert len(result) == 1
            assert result[0]["tipo"] == "pago"
            mock_fetch.assert_called_once()

    def test_get_by_id_found(self, model):
        with patch.object(QRModel, "fetch_one", return_value={
            "id": 1,
            "usuario_cedula": "V-12345678",
            "tipo": "promocion",
            "utilidad": "promocion",
            "contenido": '{"kind": "promocion", "estado": "activa", "nota": "Promo 5to cambio"}'
        }):
            result = model.ejecutar("get_by_id", 1)
            assert result["id"] == 1
            assert result["utilidad_estado"] == "activa"
            assert result["contenido_resumen"] == "Promo 5to cambio"

    def test_get_by_id_not_found(self, model):
        with patch.object(QRModel, "fetch_one", return_value=None):
            assert model.ejecutar("get_by_id", 999) is None

    def test_create_qr(self, model):
        data = {
            "usuario_cedula": "V-12345678",
            "tipo": "pago",
            "utilidad_tipo": "factura",
            "referencia_id": 105,
            "contenido": "Pago de orden"
        }
        with patch.object(QRModel, "_columns", return_value={"usuario_cedula", "tipo_qr_code", "contenido", "utilidad", "orden_venta_id"}), \
             patch.object(QRModel, "insert", return_value=12) as mock_insert:
            res = model.ejecutar("create_qr", data)
            assert res == 12
            mock_insert.assert_called_once()

    def test_update_qr(self, model):
        data = {
            "tipo": "info",
            "utilidad_tipo": "catalogo",
            "contenido": "Actualizado"
        }
        with patch.object(QRModel, "_get_by_id", return_value={"contenido": "{}"}), \
             patch.object(QRModel, "_columns", return_value={"id_qr_code", "tipo_qr_code", "contenido", "utilidad"}), \
             patch.object(QRModel, "update", return_value=1) as mock_update:
            res = model.ejecutar("update_qr", 1, data)
            assert res == 1
            mock_update.assert_called_once()

    def test_delete_and_soft_delete(self, model):
        with patch.object(QRModel, "update", return_value=1) as mock_update:
            assert model.ejecutar("delete_qr", 1) == 1
            assert model.ejecutar("soft_delete", 1) == 1
            assert mock_update.call_count == 2

    def test_get_qr_data_promocion(self, model):
        with patch.object(QRModel, "_get_by_id", return_value={
            "id": 1, "usuario_cedula": "V-12345678", "tipo": "promocion",
            "contenido": '{"tarjeta_id": 5}'
        }), patch.object(QRModel, "fetch_one") as mock_fetch:
            mock_fetch.side_effect = [
                {"nombre": "Juan", "apellido": "Perez"},
                {"id": 5, "promo_nombre": "Lavado Gratis"}
            ]
            data = model.ejecutar("get_qr_data", 1)
            assert data["usuario"]["nombre"] == "Juan"
            assert data["tarjeta"]["promo_nombre"] == "Lavado Gratis"

    def test_get_qr_data_servicio(self, model):
        with patch.object(QRModel, "_get_by_id", return_value={
            "id": 2, "usuario_cedula": "V-12345678", "tipo": "servicio",
            "contenido": '{"orden_id": 100}'
        }), patch.object(QRModel, "fetch_one") as mock_fetch_one, \
             patch.object(QRModel, "fetch_all", return_value=[{"item_nombre": "Cambio Aceite"}]):
            mock_fetch_one.side_effect = [
                {"nombre": "Maria", "apellido": "Lopez"},
                {"id": 100, "total": 80.0}
            ]
            data = model.ejecutar("get_qr_data", 2)
            assert data["usuario"]["nombre"] == "Maria"
            assert data["orden"]["id"] == 100
            assert len(data["orden"]["detalles"]) == 1

    def test_get_qr_data_not_found(self, model):
        with patch.object(QRModel, "_get_by_id", return_value=None):
            assert model.ejecutar("get_qr_data", 999) is None

    def test_get_all_qrs(self, model):
        with patch.object(QRModel, "fetch_all", return_value=[
            {"id": 1, "usuario_cedula": "V-12345678", "contenido": '{"nota": "Resumen"}', "utilidad": "pago"}
        ]), patch.object(QRModel, "fetch_one", return_value={"nombre": "Pedro", "apellido": "Gomez"}):
            qrs = model.ejecutar("get_all_qrs")
            assert len(qrs) == 1
            assert qrs[0]["usuario_nombre"] == "Pedro Gomez"
            assert qrs[0]["contenido_resumen"] == "Resumen"

    def test_ejecutar_invalid_action(self, model):
        with pytest.raises(ValueError) as exc_info:
            model.ejecutar("accion_inexistente")
        assert "Accion no permitida" in str(exc_info.value)
