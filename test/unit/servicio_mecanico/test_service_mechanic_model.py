import pytest
from unittest.mock import patch, MagicMock
from model.service_mechanic_model import ServiceMechanicModel
from config.validation import ValidationError, SELECT_TAMPER_MESSAGE


@pytest.fixture
def model():
    return ServiceMechanicModel()


class TestServiceMechanicModelValidation:

    @pytest.mark.parametrize("estado_valido", [
        "sin_asignar",
        "asignado",
        "en_proceso",
        "completado",
        "cancelado",
    ])
    @patch.object(ServiceMechanicModel, "_vehiculo_exists", return_value=True)
    @patch.object(ServiceMechanicModel, "_cliente_exists", return_value=True)
    @patch.object(ServiceMechanicModel, "_mechanic_exists", return_value=True)
    @patch.object(ServiceMechanicModel, "_service_exists", return_value=True)
    def test_validate_valid_estados_data_provider(
        self, mock_serv, mock_mech, mock_cli, mock_veh, model, estado_valido
    ):
        data = {
            "servicio_id": 1,
            "mecanico_cedula": "V-12345678",
            "cliente_cedula": "V-87654321",
            "vehiculo_placa": "ABC123",
            "estado": estado_valido
        }
        clean = model._validate(data)
        assert clean["estado"] == estado_valido
        assert clean["servicio_id"] == 1

    @pytest.mark.parametrize("invalid_estado", [
        "estado_fantasma",
        "finalizado_exitosamente",
    ])
    @patch.object(ServiceMechanicModel, "_vehiculo_exists", return_value=True)
    @patch.object(ServiceMechanicModel, "_cliente_exists", return_value=True)
    @patch.object(ServiceMechanicModel, "_service_exists", return_value=True)
    def test_validate_invalid_estados_data_provider(
        self, mock_serv, mock_cli, mock_veh, model, invalid_estado
    ):
        data = {
            "servicio_id": 1,
            "cliente_cedula": "V-87654321",
            "vehiculo_placa": "ABC123",
            "estado": invalid_estado
        }
        with pytest.raises(ValidationError) as exc_info:
            model._validate(data)
        assert "estado" in exc_info.value.errors

    @pytest.mark.parametrize("porcentaje, is_valid", [
        (10, True),
        (50.5, True),
        (100, True),
        (0, False),
        (-15, False),
        (105, False),
        ("invalido", False)
    ])
    @patch.object(ServiceMechanicModel, "_mechanic_exists", return_value=True)
    def test_validate_mechanic_update_commission_data_provider(
        self, mock_mech_exists, model, porcentaje, is_valid
    ):
        data = {
            "mecanico_cedula": "V-12345678",
            "porcentaje_comision": porcentaje
        }
        if is_valid:
            cedula, pct = model._validate_mechanic_update(data)
            assert cedula == "V-12345678"
            assert pct == float(porcentaje)
        else:
            with pytest.raises(ValidationError) as exc_info:
                model._validate_mechanic_update(data)
            assert "porcentaje_comision" in exc_info.value.errors

    @patch.object(ServiceMechanicModel, "_vehiculo_exists", return_value=True)
    @patch.object(ServiceMechanicModel, "_cliente_exists", return_value=True)
    @patch.object(ServiceMechanicModel, "_service_exists", return_value=True)
    def test_validate_en_proceso_without_mechanic_fails(
        self, mock_serv, mock_cli, mock_veh, model
    ):
        data = {
            "servicio_id": 1,
            "cliente_cedula": "V-87654321",
            "vehiculo_placa": "ABC123",
            "estado": "en_proceso"
        }
        with pytest.raises(ValidationError) as exc_info:
            model._validate(data)
        assert "mecanico_cedula" in exc_info.value.errors

    @patch.object(ServiceMechanicModel, "_vehiculo_exists", return_value=True)
    @patch.object(ServiceMechanicModel, "_cliente_exists", return_value=True)
    @patch.object(ServiceMechanicModel, "_service_exists", return_value=True)
    def test_validate_observaciones_only_spaces_fails(
        self, mock_serv, mock_cli, mock_veh, model
    ):
        data = {
            "servicio_id": 1,
            "cliente_cedula": "V-87654321",
            "vehiculo_placa": "ABC123",
            "observaciones": "     "
        }
        with pytest.raises(ValidationError) as exc_info:
            model._validate(data)
        assert "observaciones" in exc_info.value.errors
        assert "solo espacios en blanco" in exc_info.value.errors["observaciones"]

    @patch.object(ServiceMechanicModel, "_vehiculo_exists", return_value=True)
    @patch.object(ServiceMechanicModel, "_cliente_exists", return_value=True)
    @patch.object(ServiceMechanicModel, "_service_exists", return_value=True)
    def test_validate_observaciones_invalid_characters_fails(
        self, mock_serv, mock_cli, mock_veh, model
    ):
        data = {
            "servicio_id": 1,
            "cliente_cedula": "V-87654321",
            "vehiculo_placa": "ABC123",
            "observaciones": "<script>alert('xss')</script>"
        }
        with pytest.raises(ValidationError) as exc_info:
            model._validate(data)
        assert "observaciones" in exc_info.value.errors

    @patch.object(ServiceMechanicModel, "_service_exists", return_value=True)
    def test_validate_missing_cliente_and_vehiculo_fails(
        self, mock_serv, model
    ):
        data = {
            "servicio_id": 1,
            "cliente_cedula": "",
            "vehiculo_placa": ""
        }
        with pytest.raises(ValidationError) as exc_info:
            model._validate(data)
        assert "cliente_cedula" in exc_info.value.errors
        assert "vehiculo_placa" in exc_info.value.errors

    @patch.object(ServiceMechanicModel, "_vehiculo_exists", return_value=False)
    @patch.object(ServiceMechanicModel, "_cliente_exists", return_value=False)
    @patch.object(ServiceMechanicModel, "_service_exists", return_value=False)
    def test_validate_nonexistent_foreign_keys_tamper_fails(
        self, mock_serv, mock_cli, mock_veh, model
    ):
        data = {
            "servicio_id": 999,
            "cliente_cedula": "V-99999999",
            "vehiculo_placa": "INVENTADA",
        }
        with pytest.raises(ValidationError) as exc_info:
            model._validate(data)
        assert exc_info.value.errors.get("servicio_id") == SELECT_TAMPER_MESSAGE
        assert exc_info.value.errors.get("cliente_cedula") == SELECT_TAMPER_MESSAGE
        assert exc_info.value.errors.get("vehiculo_placa") == SELECT_TAMPER_MESSAGE

    @patch.object(ServiceMechanicModel, "_order_exists", return_value=False)
    @patch.object(ServiceMechanicModel, "_vehiculo_exists", return_value=True)
    @patch.object(ServiceMechanicModel, "_cliente_exists", return_value=True)
    @patch.object(ServiceMechanicModel, "_service_exists", return_value=True)
    def test_validate_nonexistent_order_fails(
        self, mock_serv, mock_cli, mock_veh, mock_order, model
    ):
        data = {
            "servicio_id": 1,
            "cliente_cedula": "V-87654321",
            "vehiculo_placa": "ABC123",
            "orden_venta_id": 888
        }
        with pytest.raises(ValidationError) as exc_info:
            model._validate(data)
        assert "orden_venta_id" in exc_info.value.errors
        assert "La orden seleccionada no existe" in exc_info.value.errors["orden_venta_id"]

    def test_validate_mechanic_update_empty_cedula_fails(self, model):
        data = {
            "mecanico_cedula": "   ",
            "porcentaje_comision": 20
        }
        with pytest.raises(ValidationError) as exc_info:
            model._validate_mechanic_update(data)
        assert "mecanico_cedula" in exc_info.value.errors

    @patch.object(ServiceMechanicModel, "_mechanic_exists", return_value=False)
    def test_validate_mechanic_update_nonexistent_mechanic_fails(
        self, mock_mech_exists, model
    ):
        data = {
            "mecanico_cedula": "V-99999999",
            "porcentaje_comision": 25
        }
        with pytest.raises(ValidationError) as exc_info:
            model._validate_mechanic_update(data)
        assert exc_info.value.errors.get("mecanico_cedula") == SELECT_TAMPER_MESSAGE

    @patch.object(ServiceMechanicModel, "_mechanic_exists", return_value=True)
    def test_validate_mechanic_update_empty_commission_fails(
        self, mock_mech_exists, model
    ):
        data = {
            "mecanico_cedula": "V-12345678",
            "porcentaje_comision": ""
        }
        with pytest.raises(ValidationError) as exc_info:
            model._validate_mechanic_update(data)
        assert "porcentaje_comision" in exc_info.value.errors


class TestServiceMechanicModelDatabaseOperations:

    @patch.object(ServiceMechanicModel, "fetch_all")
    def test_get_all(self, mock_fetch_all, model):
        mock_fetch_all.return_value = [
            {
                "id": 1,
                "servicio_id": 1,
                "servicio_nombre": "Alineación",
                "mecanico_nombre_base": "Carlos",
                "mecanico_apellido_base": "Gómez",
                "estado": "asignado"
            }
        ]
        result = model.ejecutar("get_all")

        assert len(result) == 1
        assert result[0]["mecanico_nombre"] == "Carlos Gómez"
        assert "mecanico_nombre_base" not in result[0]
        mock_fetch_all.assert_called_once()

    @patch.object(ServiceMechanicModel, "fetch_all")
    def test_get_all_mechanic_unassigned_fallback(self, mock_fetch_all, model):
        mock_fetch_all.return_value = [
            {
                "id": 2,
                "servicio_id": 1,
                "mecanico_nombre_base": None,
                "mecanico_apellido_base": "",
                "estado": "sin_asignar"
            }
        ]
        result = model.ejecutar("get_all")
        assert result[0]["mecanico_nombre"] == "Sin asignar"

    @patch.object(ServiceMechanicModel, "fetch_all")
    def test_get_all_from_view(self, mock_fetch_all, model):
        mock_fetch_all.return_value = [{"id_servicio_mecanico": 10, "estado_servicio": "completado"}]
        result = model.ejecutar("get_all_from_view")
        assert result == [{"id_servicio_mecanico": 10, "estado_servicio": "completado"}]
        mock_fetch_all.assert_called_once_with(
            "transalca", "SELECT * FROM vw_servicios_mecanicos_detalle ORDER BY fecha_ts DESC"
        )

    @patch.object(ServiceMechanicModel, "fetch_one")
    def test_get_by_id(self, mock_fetch_one, model):
        mock_fetch_one.return_value = {
            "id": 1,
            "servicio_id": 1,
            "mecanico_nombre_base": "Carlos",
            "mecanico_apellido_base": "Gómez"
        }
        result = model.ejecutar("get_by_id", 1)

        assert result["id"] == 1
        assert result["mecanico_nombre"] == "Carlos Gómez"

    @patch.object(ServiceMechanicModel, "fetch_one")
    def test_get_by_id_returns_none_when_not_found(self, mock_fetch_one, model):
        mock_fetch_one.return_value = None
        result = model.ejecutar("get_by_id", 999)
        assert result is None

    @patch.object(ServiceMechanicModel, "insert")
    @patch.object(ServiceMechanicModel, "_validate")
    def test_assign(self, mock_validate, mock_insert, model):
        mock_validate.return_value = {
            "servicio_id": 1,
            "mecanico_cedula": "V-12345678",
            "orden_venta_id": None,
            "observaciones": "Revisión rápida",
            "cliente_cedula": "V-87654321",
            "vehiculo_placa": "ABC123",
            "estado": "asignado"
        }
        mock_insert.return_value = 10

        data = {
            "servicio_id": 1,
            "mecanico_cedula": "V-12345678",
            "cliente_cedula": "V-87654321",
            "vehiculo_placa": "ABC123"
        }
        aid = model.ejecutar("assign", data)

        assert aid == 10
        mock_insert.assert_called_once()

    @patch.object(ServiceMechanicModel, "insert")
    @patch.object(ServiceMechanicModel, "_validate")
    def test_assign_without_mechanic_defaults_to_sin_asignar(
        self, mock_validate, mock_insert, model
    ):
        mock_validate.return_value = {
            "servicio_id": 1,
            "mecanico_cedula": None,
            "orden_venta_id": None,
            "observaciones": "",
            "cliente_cedula": "V-87654321",
            "vehiculo_placa": "ABC123",
            "estado": "asignado"
        }
        mock_insert.return_value = 15

        data = {"servicio_id": 1, "cliente_cedula": "V-87654321", "vehiculo_placa": "ABC123"}
        aid = model.ejecutar("assign", data)
        assert aid == 15
        
        args = mock_insert.call_args[0]
        params = args[2]
        assert params[6] == "sin_asignar"

    @patch.object(ServiceMechanicModel, "update")
    def test_update_mechanic_with_cedula(self, mock_update, model):
        mock_update.return_value = 1
        result = model.ejecutar("update_mechanic", 5, "V-12345678")
        assert result == 1
        mock_update.assert_called_once()
        query = mock_update.call_args[0][1]
        assert "SET mecanico_cedula = %s" in query

    @patch.object(ServiceMechanicModel, "update")
    def test_update_mechanic_without_cedula_unassigns(self, mock_update, model):
        mock_update.return_value = 1
        result = model.ejecutar("update_mechanic", 5, "")
        assert result == 1
        mock_update.assert_called_once()
        query = mock_update.call_args[0][1]
        assert "SET mecanico_cedula = NULL" in query

    @patch.object(ServiceMechanicModel, "update")
    @patch.object(ServiceMechanicModel, "_get_by_id")
    def test_update_status_success(self, mock_get_by_id, mock_update, model):
        mock_get_by_id.return_value = {
            "id": 1,
            "mecanico_cedula": "V-12345678",
            "cliente_cedula": "V-87654321",
            "vehiculo_placa": "ABC123"
        }
        mock_update.return_value = 1
        result = model.ejecutar("update_status", 1, "en_proceso")
        assert result == 1
        mock_update.assert_called_once()

    def test_update_status_invalid_choice_fails(self, model):
        with pytest.raises(ValidationError) as exc_info:
            model.ejecutar("update_status", 1, "estado_inexistente")
        assert "estado" in exc_info.value.errors

    @patch.object(ServiceMechanicModel, "_get_by_id")
    def test_update_status_missing_required_data_fails(self, mock_get_by_id, model):
        mock_get_by_id.return_value = {
            "id": 1,
            "mecanico_cedula": None,
            "cliente_cedula": "V-87654321",
            "vehiculo_placa": "ABC123"
        }
        with pytest.raises(ValidationError) as exc_info:
            model.ejecutar("update_status", 1, "en_proceso")
        assert "mecanico_cedula" in exc_info.value.errors

    @patch.object(ServiceMechanicModel, "update")
    @patch.object(ServiceMechanicModel, "_validate")
    def test_update_assignment_success(self, mock_validate, mock_update, model):
        mock_validate.return_value = {
            "servicio_id": 2,
            "mecanico_cedula": "V-12345678",
            "orden_venta_id": None,
            "observaciones": "Actualizado",
            "cliente_cedula": "V-87654321",
            "vehiculo_placa": "ABC123",
            "estado": "en_proceso"
        }
        mock_update.return_value = 1
        payload = {"servicio_id": 2, "mecanico_cedula": "V-12345678"}
        result = model.ejecutar("update_assignment", 5, payload)
        assert result == 1
        mock_update.assert_called_once()

    @patch.object(ServiceMechanicModel, "delete")
    def test_delete_assignment(self, mock_delete, model):
        mock_delete.return_value = 1
        result = model.ejecutar("delete_assignment", 1)

        assert result == 1
        mock_delete.assert_called_once()

    @patch.object(ServiceMechanicModel, "execute_query")
    def test_complete_service_sp(self, mock_execute, model):
        mock_execute.return_value = True
        result = model.ejecutar("complete_service_sp", 10, 15.5, "Servicio finalizado ok")
        assert result is True
        mock_execute.assert_called_once_with(
            "transalca", "CALL sp_completar_servicio_mecanico(%s, %s, %s)",
            (10, 15.5, "Servicio finalizado ok")
        )

    def test_ejecutar_invalid_action(self, model):
        with pytest.raises(ValueError) as exc_info:
            model.ejecutar("accion_inexistente")

        assert "Accion no permitida" in str(exc_info.value)


class TestServiceMechanicModelHelperChecks:

    @patch.object(ServiceMechanicModel, "fetch_one")
    def test_service_exists(self, mock_fetch_one, model):
        mock_fetch_one.return_value = {"id_servicio": 1}
        assert model.ejecutar("service_exists", 1) is True

        mock_fetch_one.return_value = None
        assert model.ejecutar("service_exists", 999) is False

    @patch.object(ServiceMechanicModel, "fetch_one")
    def test_mechanic_exists(self, mock_fetch_one, model):
        assert model.ejecutar("mechanic_exists", None) is True

        mock_fetch_one.return_value = {"cedula_mecanico": "V-12345678"}
        assert model.ejecutar("mechanic_exists", "V-12345678") is True

        mock_fetch_one.return_value = None
        assert model.ejecutar("mechanic_exists", "V-99999999") is False

    @patch.object(ServiceMechanicModel, "fetch_one")
    def test_order_exists(self, mock_fetch_one, model):
        assert model.ejecutar("order_exists", None) is True

        mock_fetch_one.return_value = {"id_orden_venta": 5}
        assert model.ejecutar("order_exists", 5) is True

    @patch.object(ServiceMechanicModel, "fetch_one")
    def test_cliente_exists_transalca_and_mantenimiento_fallback(self, mock_fetch_one, model):
        assert model._cliente_exists("") is False

        mock_fetch_one.return_value = {"id_cliente": 1}
        assert model._cliente_exists("V-12345678") is True

        mock_fetch_one.side_effect = [None, {"id": 1}]
        assert model._cliente_exists("V-87654321") is True

        mock_fetch_one.side_effect = [None, None]
        assert model._cliente_exists("V-00000000") is False

    @patch.object(ServiceMechanicModel, "fetch_one")
    def test_mechanic_busy_elsewhere(self, mock_fetch_one, model):
        assert model.ejecutar("mechanic_busy_elsewhere", "") is False

        mock_fetch_one.return_value = {"1": 1}
        assert model.ejecutar("mechanic_busy_elsewhere", "V-12345678", exclude_id=10) is True
        query = mock_fetch_one.call_args[0][1]
        assert "AND id_servicio_mecanico != %s" in query

        mock_fetch_one.return_value = None
        assert model.ejecutar("mechanic_busy_elsewhere", "V-12345678") is False
