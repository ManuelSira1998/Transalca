import pytest
from unittest.mock import patch, MagicMock
from model.ticket_model import TicketModel


@pytest.fixture
def model():
    return TicketModel()


class TestTicketModelProperties:

    def test_property_setters_strip_whitespace(self, model):
        model.cliente_cedula = "  V-12345678  "
        model.asunto = "  Problema con factura  "
        model.descripcion = "  No aparece reflejado el pago  "
        model.prioridad = "  alta  "

        assert model.cliente_cedula == "V-12345678"
        assert model.asunto == "Problema con factura"
        assert model.descripcion == "No aparece reflejado el pago"
        assert model.prioridad == "alta"

    def test_property_setters_none(self, model):
        model.cliente_cedula = None
        model.asunto = None
        model.descripcion = None
        model.prioridad = None

        assert model.cliente_cedula is None
        assert model.asunto is None
        assert model.descripcion is None
        assert model.prioridad is None


class TestTicketModelValidationAndCreation:

    @pytest.mark.parametrize("prioridad_valida", [
        "baja",
        "media",
        "alta",
        "urgente",
    ])
    def test_create_with_valid_priorities(self, model, prioridad_valida):
        data = {
            "cliente_cedula": "V-12345678",
            "asunto": "Consulta de servicio",
            "descripcion": "Detalles adicionales",
            "prioridad": prioridad_valida
        }
        with patch.object(TicketModel, "insert", return_value=1) as mock_insert:
            tid = model.ejecutar("create", data)
            assert tid == 1
            assert model.prioridad == prioridad_valida
            mock_insert.assert_called_once()

    @pytest.mark.parametrize("ref_tipo, ref_field, ref_val, mock_ret", [
        ("general", "ref_none", None, None),
        ("vehiculo", "vehiculo_placa", "ABC123", {"placa_vehiculo": "ABC123"}),
        ("producto", "referencia_id", "PROD-001", {"codigo": "PROD-001"}),
        ("servicio", "referencia_id", "5", {"id": 5}),
    ])
    def test_create_with_reference_types(self, model, ref_tipo, ref_field, ref_val, mock_ret):
        data = {
            "cliente_cedula": "V-12345678",
            "asunto": "Soporte técnico",
            "referencia_tipo": ref_tipo,
            ref_field: ref_val
        }
        with patch.object(TicketModel, "fetch_one", return_value=mock_ret), \
             patch.object(TicketModel, "insert", return_value=10) as mock_insert:
            tid = model.ejecutar("create", data)
            assert tid == 10
            mock_insert.assert_called_once()


class TestTicketModelDatabaseOperations:

    @pytest.mark.parametrize("estado, prioridad", [
        (None, None),
        ("abierto", None),
        (None, "alta"),
        ("resuelto", "urgente"),
    ])
    def test_get_all(self, model, estado, prioridad):
        with patch.object(TicketModel, "fetch_all", return_value=[
            {"id": 1, "asunto": "Falla en vehículo", "estado": "abierto", "prioridad": "alta"}
        ]) as mock_fetch:
            result = model.ejecutar("get_all", estado, prioridad)
            assert len(result) == 1
            assert result[0]["asunto"] == "Falla en vehículo"
            mock_fetch.assert_called_once()

    def test_get_by_id_found(self, model):
        with patch.object(TicketModel, "fetch_one", return_value={"id": 1, "asunto": "Falla en vehículo"}), \
             patch.object(TicketModel, "_get_responses", return_value=[{"id": 10, "mensaje": "En revisión"}]):
            result = model.ejecutar("get_by_id", 1)
            assert result["id"] == 1
            assert len(result["respuestas"]) == 1

    def test_get_by_id_not_found(self, model):
        with patch.object(TicketModel, "fetch_one", return_value=None):
            assert model.ejecutar("get_by_id", 999) is None

    def test_get_by_cliente(self, model):
        with patch.object(TicketModel, "fetch_all", return_value=[{"id": 1, "asunto": "Ticket cliente"}]):
            res = model.ejecutar("get_by_cliente", "V-12345678")
            assert len(res) == 1

    def test_update_status(self, model):
        with patch.object(TicketModel, "update", return_value=1) as mock_update:
            result = model.ejecutar("update_status", 1, "resuelto")
            assert result == 1
            mock_update.assert_called_once()

    def test_add_response(self, model):
        data = {
            "ticket_id": 1,
            "autor_id": 2,
            "autor_tipo": "admin",
            "mensaje": "Su requerimiento fue procesado.",
            "adjunto_url": None
        }
        with patch.object(TicketModel, "insert", return_value=5) as mock_insert:
            rid = model.ejecutar("add_response", data)
            assert rid == 5
            mock_insert.assert_called_once()

    @pytest.mark.parametrize("user_found, expected_autor", [
        ({"nombre": "Carlos", "apellido": "Perez"}, "Carlos Perez"),
        (None, "Sistema"),
    ])
    def test_get_responses(self, model, user_found, expected_autor):
        with patch.object(TicketModel, "fetch_all", return_value=[{"id": 1, "autor_id": 2, "mensaje": "Hola"}]), \
             patch.object(TicketModel, "fetch_one", return_value=user_found):
            resp = model.ejecutar("get_responses", 1)
            assert len(resp) == 1
            assert resp[0]["autor_nombre"] == expected_autor

    def test_count_by_estado(self, model):
        with patch.object(TicketModel, "fetch_all", return_value=[
            {"estado": "abierto", "total": 4},
            {"estado": "resuelto", "total": 10}
        ]):
            stats = model.ejecutar("count_by_estado")
            assert len(stats) == 2
            assert stats[0]["estado"] == "abierto"

    @pytest.mark.parametrize("db_result, expected_count", [
        ({"total": 3}, 3),
        (None, 0),
    ])
    def test_count_open_by_cliente(self, model, db_result, expected_count):
        with patch.object(TicketModel, "fetch_one", return_value=db_result):
            assert model.ejecutar("count_open_by_cliente", "V-12345678") == expected_count

    def test_user_id_by_cedula(self, model):
        with patch.object(TicketModel, "fetch_one", return_value={"id": 7}):
            assert model.ejecutar("user_id_by_cedula", "V-12345678") == {"id": 7}

    def test_ejecutar_invalid_action(self, model):
        with pytest.raises(ValueError) as exc_info:
            model.ejecutar("accion_inexistente")
        assert "Accion no permitida" in str(exc_info.value)
