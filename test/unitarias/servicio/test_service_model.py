import pytest
from unittest.mock import patch, MagicMock
from model.service_model import ServiceModel
from config.validation import ValidationError, SELECT_TAMPER_MESSAGE


@pytest.fixture
def model():
    """Fixture para obtener una instancia limpia de ServiceModel."""
    return ServiceModel()


class TestServiceModelProperties:
    """Pruebas unitarias para getters y setters del modelo de servicio."""

    def test_property_setters_strip_whitespace(self, model):
        model.nombre = "  Alineación y Balanceo  "
        model.descripcion = "  Servicio completo de suspensión  "
        model.tipo = "  alineacion  "
        model.precio = 25.50

        assert model.nombre == "Alineación y Balanceo"
        assert model.descripcion == "Servicio completo de suspensión"
        assert model.tipo == "alineacion"
        assert model.precio == 25.50

    def test_property_setters_none(self, model):
        model.nombre = None
        model.descripcion = None
        model.tipo = None

        assert model.nombre is None
        assert model.descripcion is None
        assert model.tipo is None


class TestServiceModelValidation:
    """Pruebas unitarias con Data Provider (@pytest.mark.parametrize) para validaciones de servicio."""

    # DATA PROVIDER: Pruebas con tipos de servicio válidos
    @pytest.mark.parametrize("tipo_valido", [
        "alineacion",
        "rotacion",
        "balanceo",
        "cambio_aceite",
        "general",
    ])
    @patch.object(ServiceModel, "_sucursal_exists", return_value=True)
    def test_validate_valid_tipos_data_provider(self, mock_suc_exists, model, tipo_valido):
        data = {
            "nombre": "Alineación Computarizada",
            "descripcion": "Alineación de tren delantero",
            "precio": 30.00,
            "tipo": tipo_valido,
            "sucursal_ids": [1]
        }
        clean = model._validate(data)
        assert clean["tipo"] == tipo_valido
        assert clean["precio"] == 30.00
        assert clean["duracion_estimada"] == 60  # Default value

    # DATA PROVIDER: Pruebas con tipos de servicio inválidos
    @pytest.mark.parametrize("invalid_tipo", [
        "inventado",
        "mantenimiento_super_express",
        "",
    ])
    @patch.object(ServiceModel, "_sucursal_exists", return_value=True)
    def test_validate_invalid_tipos_data_provider(self, mock_suc_exists, model, invalid_tipo):
        data = {
            "nombre": "Servicio Test",
            "precio": 30.00,
            "tipo": invalid_tipo,
            "sucursal_ids": [1]
        }
        with pytest.raises(ValidationError) as exc_info:
            model._validate(data)
        assert "tipo" in exc_info.value.errors

    # DATA PROVIDER: Validaciones de precios inválidos
    @pytest.mark.parametrize("invalid_precio", [
        -10.00,        # Precio negativo
        "abc",         # No numérico
        None,          # Precio ausente
    ])
    @patch.object(ServiceModel, "_sucursal_exists", return_value=True)
    def test_validate_invalid_precios_data_provider(self, mock_suc_exists, model, invalid_precio):
        data = {
            "nombre": "Servicio Test",
            "precio": invalid_precio,
            "tipo": "general",
            "sucursal_ids": [1]
        }
        with pytest.raises(ValidationError) as exc_info:
            model._validate(data)
        assert "precio" in exc_info.value.errors

    # DATA PROVIDER: Nombres inválidos (longitud o vacíos)
    @pytest.mark.parametrize("invalid_nombre", [
        "",
        "   ",
        "AB",          # Menor a 3 caracteres
        "X" * 201,     # Mayor a 200 caracteres
    ])
    @patch.object(ServiceModel, "_sucursal_exists", return_value=True)
    def test_validate_invalid_nombre_data_provider(self, mock_suc_exists, model, invalid_nombre):
        data = {
            "nombre": invalid_nombre,
            "precio": 25.00,
            "tipo": "general",
            "sucursal_ids": [1]
        }
        with pytest.raises(ValidationError) as exc_info:
            model._validate(data)
        assert "nombre" in exc_info.value.errors

    # DATA PROVIDER: Validaciones de sucursal vacía o no seleccionada
    @pytest.mark.parametrize("empty_sucursal_ids", [
        [],
        None,
        "",
    ])
    def test_validate_missing_sucursal_data_provider(self, model, empty_sucursal_ids):
        data = {
            "nombre": "Servicio Test",
            "precio": 30.00,
            "tipo": "general",
            "sucursal_ids": empty_sucursal_ids
        }
        with pytest.raises(ValidationError) as exc_info:
            model._validate(data)
        assert "sucursal_id" in exc_info.value.errors

    # DATA PROVIDER: Duraciones estimadas válidas e inválidas
    @pytest.mark.parametrize("duracion, is_valid", [
        (1, True),
        (60, True),
        (1440, True),
        (-5, False),        # Menor a 1
        (1441, False),      # Mayor a 1440
        ("invalido", False) # No numérico
    ])
    @patch.object(ServiceModel, "_sucursal_exists", return_value=True)
    def test_validate_duracion_estimada_data_provider(self, mock_suc_exists, model, duracion, is_valid):
        data = {
            "nombre": "Servicio Duracion",
            "precio": 20.00,
            "tipo": "general",
            "duracion_estimada": duracion,
            "sucursal_ids": [1]
        }
        if is_valid:
            clean = model._validate(data)
            assert clean["duracion_estimada"] == int(duracion)
        else:
            with pytest.raises(ValidationError) as exc_info:
                model._validate(data)
            assert "duracion_estimada" in exc_info.value.errors

    @patch.object(ServiceModel, "_sucursal_exists", return_value=False)
    def test_validate_nonexistent_sucursal_tamper_fails(self, mock_suc_exists, model):
        data = {
            "nombre": "Servicio Test",
            "precio": 30.00,
            "tipo": "general",
            "sucursal_ids": [999]
        }
        with pytest.raises(ValidationError) as exc_info:
            model._validate(data)
        assert exc_info.value.errors.get("sucursal_id") == SELECT_TAMPER_MESSAGE

    @patch.object(ServiceModel, "_sucursal_exists", return_value=True)
    def test_validate_sucursal_ids_from_comma_string_and_single_id(self, mock_suc_exists, model):
        # Caso 1: String separado por comas "1, 2"
        data_str = {
            "nombre": "Servicio Coma",
            "precio": 15.00,
            "tipo": "general",
            "sucursal_ids": "1,2"
        }
        clean_str = model._validate(data_str)
        assert clean_str["sucursal_ids"] == [1, 2]

        # Caso 2: Obtenido de sucursal_id individual
        data_single = {
            "nombre": "Servicio Single",
            "precio": 15.00,
            "tipo": "general",
            "sucursal_id": 1
        }
        clean_single = model._validate(data_single)
        assert clean_single["sucursal_ids"] == [1]


class TestServiceModelDatabaseOperations:
    """Pruebas unitarias con mocks de base de datos para operaciones CRUD de servicio."""

    @patch.object(ServiceModel, "fetch_all")
    def test_get_all(self, mock_fetch_all, model):
        mock_fetch_all.return_value = [
            {"id": 1, "nombre": "Cambio de Aceite", "precio": 20.00, "estado": 1}
        ]
        result = model.ejecutar("get_all")

        assert len(result) == 1
        assert result[0]["nombre"] == "Cambio de Aceite"
        mock_fetch_all.assert_called_once()

    @patch.object(ServiceModel, "_get_all")
    def test_get_active(self, mock_get_all, model):
        mock_get_all.return_value = [{"id": 1, "nombre": "Activo"}]
        result = model.ejecutar("get_active")
        assert result == [{"id": 1, "nombre": "Activo"}]
        mock_get_all.assert_called_once()

    @patch.object(ServiceModel, "fetch_one")
    def test_get_by_id(self, mock_fetch_one, model):
        mock_fetch_one.return_value = {"id": 1, "nombre": "Cambio de Aceite", "precio": 20.00}
        result = model.ejecutar("get_by_id", 1)

        assert result["id"] == 1
        mock_fetch_one.assert_called_once()

    @patch.object(ServiceModel, "fetch_all")
    def test_get_by_sucursal(self, mock_fetch_all, model):
        mock_fetch_all.return_value = [{"id": 1, "sucursal_nombre": "Principal"}]
        result = model.ejecutar("get_by_sucursal", 2)
        assert len(result) == 1
        mock_fetch_all.assert_called_once()

    @patch.object(ServiceModel, "_sync_sucursales")
    @patch.object(ServiceModel, "insert")
    @patch.object(ServiceModel, "_get_by_nombre")
    @patch.object(ServiceModel, "_validate")
    def test_create_new_service_success(
        self, mock_validate, mock_get_by_nombre, mock_insert, mock_sync, model
    ):
        mock_validate.return_value = {
            "nombre": "Alineación Laser",
            "descripcion": "Alineación de precisión",
            "tipo": "alineacion",
            "precio": 45.00,
            "duracion_estimada": 90,
            "sucursal_ids": [1, 2]
        }
        mock_get_by_nombre.return_value = None
        mock_insert.return_value = 5

        data = {"nombre": "Alineación Laser", "precio": 45.00, "tipo": "alineacion", "sucursal_ids": [1, 2]}
        sid = model.ejecutar("create", data)

        assert sid == 5
        mock_insert.assert_called_once()
        mock_sync.assert_called_once_with(5, [1, 2])

    @patch.object(ServiceModel, "_sync_sucursales")
    @patch.object(ServiceModel, "update")
    @patch.object(ServiceModel, "_get_by_nombre")
    @patch.object(ServiceModel, "_validate")
    def test_create_reactivates_inactive_service_with_same_name(
        self, mock_validate, mock_get_by_nombre, mock_update, mock_sync, model
    ):
        mock_validate.return_value = {
            "nombre": "Servicio Inactivo Previo",
            "descripcion": "Descripción nueva",
            "tipo": "general",
            "precio": 35.00,
            "duracion_estimada": 60,
            "sucursal_ids": [1]
        }
        mock_get_by_nombre.return_value = {"id": 10, "nombre": "Servicio Inactivo Previo", "estado": 0}
        mock_update.return_value = 1

        data = {"nombre": "Servicio Inactivo Previo", "precio": 35.00, "tipo": "general", "sucursal_ids": [1]}
        sid = model.ejecutar("create", data)

        assert sid == 10
        mock_update.assert_called_once()
        mock_sync.assert_called_once_with(10, [1])

    @patch.object(ServiceModel, "_get_by_nombre")
    @patch.object(ServiceModel, "_validate")
    def test_create_duplicate_active_service_raises_error(self, mock_validate, mock_get_by_nombre, model):
        mock_validate.return_value = {
            "nombre": "Cambio de Aceite",
            "descripcion": "",
            "tipo": "cambio_aceite",
            "precio": 20.00,
            "duracion_estimada": 60,
            "sucursal_ids": [1]
        }
        mock_get_by_nombre.return_value = {"id": 1, "nombre": "Cambio de Aceite", "estado": 1}

        data = {
            "nombre": "Cambio de Aceite",
            "precio": 20.00,
            "tipo": "cambio_aceite",
            "sucursal_ids": [1]
        }
        with pytest.raises(ValidationError) as exc_info:
            model.ejecutar("create", data)

        assert "nombre" in exc_info.value.errors

    @patch.object(ServiceModel, "_sync_sucursales")
    @patch.object(ServiceModel, "update")
    @patch.object(ServiceModel, "_nombre_exists")
    @patch.object(ServiceModel, "_validate")
    def test_update_service_success(
        self, mock_validate, mock_nombre_exists, mock_update, mock_sync, model
    ):
        mock_validate.return_value = {
            "nombre": "Alineación Actualizada",
            "descripcion": "Detalles nuevos",
            "tipo": "alineacion",
            "precio": 40.00,
            "duracion_estimada": 45,
            "sucursal_ids": [2]
        }
        mock_nombre_exists.return_value = False
        mock_update.return_value = 1

        data = {"nombre": "Alineación Actualizada", "precio": 40.00, "tipo": "alineacion", "sucursal_ids": [2]}
        result = model.ejecutar("update_service", 3, data)

        assert result == 1
        mock_update.assert_called_once()
        mock_sync.assert_called_once_with(3, [2])

    @patch.object(ServiceModel, "_nombre_exists", return_value=True)
    @patch.object(ServiceModel, "_validate")
    def test_update_service_duplicate_name_fails(self, mock_validate, mock_nombre_exists, model):
        mock_validate.return_value = {
            "nombre": "Nombre Repetido",
            "tipo": "general",
            "precio": 10.00,
            "sucursal_ids": [1]
        }
        data = {"nombre": "Nombre Repetido"}
        with pytest.raises(ValidationError) as exc_info:
            model.ejecutar("update_service", 3, data)
        assert "nombre" in exc_info.value.errors

    @patch.object(ServiceModel, "update")
    def test_soft_delete(self, mock_update, model):
        mock_update.return_value = 1
        result = model.ejecutar("soft_delete", 1)

        assert result == 1
        mock_update.assert_called_once()

    @patch.object(ServiceModel, "_soft_delete")
    def test_toggle_estado(self, mock_soft_delete, model):
        mock_soft_delete.return_value = 1
        result = model.ejecutar("toggle_estado", 1)
        assert result == 1
        mock_soft_delete.assert_called_once_with(1)

    @patch.object(ServiceModel, "update")
    def test_reactivar(self, mock_update, model):
        mock_update.return_value = 1
        result = model.ejecutar("reactivar", 5)
        assert result == 1
        mock_update.assert_called_once()
        query = mock_update.call_args[0][1]
        assert "estado = 1" in query

    @patch.object(ServiceModel, "insert")
    @patch.object(ServiceModel, "update")
    def test_sync_sucursales_filters_duplicates_and_invalids(self, mock_update, mock_insert, model):
        model._sync_sucursales(1, ["1", "invalido", 1, 2, "2"])
        mock_update.assert_called_once()  # DELETE previa
        assert mock_insert.call_count == 2  # Solo 1 y 2 una vez cada uno

    def test_ejecutar_invalid_action(self, model):
        with pytest.raises(ValueError) as exc_info:
            model.ejecutar("accion_inexistente")

        assert "Accion no permitida" in str(exc_info.value)


class TestServiceModelHelperChecks:
    """Pruebas unitarias para métodos de consulta y existencia."""

    @patch.object(ServiceModel, "fetch_one")
    def test_sucursal_exists(self, mock_fetch_one, model):
        mock_fetch_one.return_value = {"id_sucursal": 1}
        assert model.ejecutar("sucursal_exists", 1) is True

        mock_fetch_one.return_value = None
        assert model.ejecutar("sucursal_exists", 999) is False

    @patch.object(ServiceModel, "fetch_one")
    def test_nombre_exists_with_and_without_exclude(self, mock_fetch_one, model):
        mock_fetch_one.return_value = {"id_servicio": 1}
        assert model.ejecutar("nombre_exists", "Alineación", exclude_id=2) is True
        query = mock_fetch_one.call_args[0][1]
        assert "AND id_servicio != %s" in query

        mock_fetch_one.return_value = None
        assert model.ejecutar("nombre_exists", "No Existe") is False

    @patch.object(ServiceModel, "fetch_one")
    def test_get_by_nombre(self, mock_fetch_one, model):
        mock_fetch_one.return_value = {"id_servicio": 1, "nombre": "Frenos"}
        res = model.ejecutar("get_by_nombre", "Frenos")
        assert res["nombre"] == "Frenos"
