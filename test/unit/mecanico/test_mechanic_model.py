import pytest
from unittest.mock import patch, MagicMock
from model.mechanic_model import MechanicModel
from config.validation import ValidationError


@pytest.fixture
def model():
    return MechanicModel()


class TestMechanicModelProperties:

    def test_property_setters_strip_whitespace(self, model):
        model.cedula = "  V-12345678  "
        model.nombre = "  Carlos  "
        model.apellido = "  Pérez  "
        model.telefono = "  04141234567  "
        model.especialidad = "  Motor y Frenos  "

        assert model.cedula == "V-12345678"
        assert model.nombre == "Carlos"
        assert model.apellido == "Pérez"
        assert model.telefono == "04141234567"
        assert model.especialidad == "Motor y Frenos"

    def test_property_setters_none(self, model):
        model.cedula = None
        model.nombre = None
        model.apellido = None
        model.telefono = None
        model.especialidad = None

        assert model.cedula is None
        assert model.nombre is None
        assert model.apellido is None
        assert model.telefono is None
        assert model.especialidad is None


class TestMechanicModelValidation:

    @pytest.mark.parametrize("input_cedula, expected_cedula, expected_prefijo", [
        ("V-12345678", "V-12345678", "V"),
        ("E-87654321", "E-87654321", "E"),
        ("J-12345678", "J-12345678", "J"),
        ("v 12345678", "V-12345678", "V"),
        ("V12345678", "V-12345678", "V"),
    ])
    def test_validate_valid_cedula_data_provider(self, model, input_cedula, expected_cedula, expected_prefijo):
        data = {
            "cedula": input_cedula,
            "nombre": "Carlos",
            "apellido": "Pérez"
        }
        clean = model.ejecutar("validate", data)
        assert clean["cedula"] == expected_cedula
        assert clean["cedula_prefijo"] == expected_prefijo

    @pytest.mark.parametrize("invalid_cedula", [
        "XYZ-99999",
        "ABC",
        "123",
        "V-ABCDEFGH",
        "",
    ])
    def test_validate_invalid_cedula_data_provider(self, model, invalid_cedula):
        data = {
            "cedula": invalid_cedula,
            "nombre": "Carlos",
            "apellido": "Pérez"
        }
        with pytest.raises(ValidationError) as exc_info:
            model.ejecutar("validate", data)
        assert "cedula" in exc_info.value.errors

    @pytest.mark.parametrize("nombre, apellido, expected_error_field", [
        ("", "Pérez", "nombre"),
        ("A", "Pérez", "nombre"),
        ("Carlos123", "Pérez", "nombre"),
        ("Carlos", "", "apellido"),
        ("Carlos", "P", "apellido"),
        ("Carlos", "Pérez99", "apellido"),
    ])
    def test_validate_invalid_names_data_provider(self, model, nombre, apellido, expected_error_field):
        data = {
            "cedula": "V-12345678",
            "nombre": nombre,
            "apellido": apellido
        }
        with pytest.raises(ValidationError) as exc_info:
            model.ejecutar("validate", data)
        assert expected_error_field in exc_info.value.errors

    @pytest.mark.parametrize("telefono, is_valid", [
        ("04141234567", True),
        ("0424-7654321", True),
        ("", True),
        (None, True),
        ("12345", False),
        ("0414abcdefg", False),
    ])
    def test_validate_phone_formats_data_provider(self, model, telefono, is_valid):
        data = {
            "cedula": "V-12345678",
            "nombre": "Carlos",
            "apellido": "Pérez",
            "telefono": telefono
        }
        if is_valid:
            clean = model.ejecutar("validate", data)
            assert "cedula" in clean
        else:
            with pytest.raises(ValidationError) as exc_info:
                model.ejecutar("validate", data)
            assert "telefono" in exc_info.value.errors

    def test_validate_especialidad_exceeds_max_len_fails(self, model):
        data = {
            "cedula": "V-12345678",
            "nombre": "Carlos",
            "apellido": "Pérez",
            "especialidad": "A" * 121
        }
        with pytest.raises(ValidationError) as exc_info:
            model.ejecutar("validate", data)
        assert "especialidad" in exc_info.value.errors


class TestMechanicModelDatabaseOperations:

    @patch.object(MechanicModel, "fetch_all")
    def test_get_all(self, mock_fetch_all, model):
        mock_fetch_all.return_value = [
            {"cedula": "V-12345678", "nombre": "Carlos", "apellido": "Pérez", "estado_operativo": "Disponible"}
        ]
        result = model.ejecutar("get_all")

        assert len(result) == 1
        assert result[0]["nombre"] == "Carlos"
        mock_fetch_all.assert_called_once()

    @patch.object(MechanicModel, "fetch_one")
    def test_get_by_cedula(self, mock_fetch_one, model):
        mock_fetch_one.return_value = {"cedula": "V-12345678", "nombre": "Carlos"}
        result = model.ejecutar("get_by_cedula", "V-12345678")

        assert result["cedula"] == "V-12345678"
        mock_fetch_one.assert_called_once()

    @patch.object(MechanicModel, "fetch_all")
    def test_get_active(self, mock_fetch_all, model):
        mock_fetch_all.return_value = [{"cedula": "V-12345678", "estado": 1}]
        result = model.ejecutar("get_active")
        assert len(result) == 1
        mock_fetch_all.assert_called_once()

    @patch.object(MechanicModel, "insert")
    @patch.object(MechanicModel, "_get_by_cedula")
    def test_create_new_mechanic(self, mock_get_by_cedula, mock_insert, model):
        mock_get_by_cedula.return_value = None
        mock_insert.return_value = 1

        data = {
            "cedula": "V-87654321",
            "nombre": "Pedro",
            "apellido": "Ramírez",
            "telefono": "04149876543",
            "especialidad": "Transmisiones"
        }
        cedula = model.ejecutar("create", data)

        assert cedula == "V-87654321"
        mock_insert.assert_called_once()

    @patch.object(MechanicModel, "_get_by_cedula")
    def test_create_duplicate_active_mechanic_raises_error(self, mock_get_by_cedula, model):
        mock_get_by_cedula.return_value = {"cedula": "V-12345678", "estado": 1}

        data = {
            "cedula": "V-12345678",
            "nombre": "Pedro",
            "apellido": "Ramírez"
        }
        with pytest.raises(ValidationError) as exc_info:
            model.ejecutar("create", data)

        assert "cedula" in exc_info.value.errors

    @patch.object(MechanicModel, "update")
    @patch.object(MechanicModel, "_get_by_cedula")
    def test_create_reactivates_inactive_mechanic_with_photo(
        self, mock_get_by_cedula, mock_update, model
    ):
        mock_get_by_cedula.return_value = {"cedula": "V-12345678", "estado": 0}
        mock_update.return_value = 1

        data = {
            "cedula": "V-12345678",
            "nombre": "Carlos",
            "apellido": "Pérez",
            "foto_perfil": "mecanico_custom.jpg"
        }
        cedula = model.ejecutar("create", data)
        assert cedula == "V-12345678"
        mock_update.assert_called_once()
        query = mock_update.call_args[0][1]
        assert "foto_perfil_mecanico=%s, estado=1" in query

    @patch.object(MechanicModel, "update")
    @patch.object(MechanicModel, "_get_by_cedula")
    def test_create_reactivates_inactive_mechanic_without_photo(
        self, mock_get_by_cedula, mock_update, model
    ):
        mock_get_by_cedula.return_value = {"cedula": "V-12345678", "estado": 0}
        mock_update.return_value = 1

        data = {
            "cedula": "V-12345678",
            "nombre": "Carlos",
            "apellido": "Pérez"
        }
        cedula = model.ejecutar("create", data)
        assert cedula == "V-12345678"
        mock_update.assert_called_once()

    def test_update_mechanic_empty_old_cedula_fails(self, model):
        data = {"cedula": "V-12345678", "nombre": "Carlos", "apellido": "Pérez"}
        with pytest.raises(ValidationError) as exc_info:
            model.ejecutar("update_mechanic", "", data)
        assert "old_cedula" in exc_info.value.errors

    @patch.object(MechanicModel, "_cedula_exists", return_value=True)
    def test_update_mechanic_duplicate_cedula_fails(self, mock_cedula_exists, model):
        data = {"cedula": "V-87654321", "nombre": "Carlos", "apellido": "Pérez"}
        with pytest.raises(ValidationError) as exc_info:
            model.ejecutar("update_mechanic", "V-12345678", data)
        assert "cedula" in exc_info.value.errors

    @patch.object(MechanicModel, "update")
    @patch.object(MechanicModel, "_cedula_exists", return_value=False)
    def test_update_mechanic_success_with_and_without_photo(
        self, mock_cedula_exists, mock_update, model
    ):
        mock_update.return_value = 1
        data_foto = {
            "cedula": "V-12345678",
            "nombre": "Carlos",
            "apellido": "Pérez",
            "foto_perfil": "nueva_foto.png"
        }
        res1 = model.ejecutar("update_mechanic", "V-12345678", data_foto)
        assert res1 == 1

        data_sin_foto = {
            "cedula": "V-12345678",
            "nombre": "Carlos",
            "apellido": "Pérez",
            "foto_perfil": None
        }
        res2 = model.ejecutar("update_mechanic", "V-12345678", data_sin_foto)
        assert res2 == 1

    @patch.object(MechanicModel, "update")
    def test_soft_delete(self, mock_update, model):
        mock_update.return_value = 1
        result = model.ejecutar("soft_delete", "V-12345678")

        assert result == 1
        mock_update.assert_called_once()

    @patch.object(MechanicModel, "update")
    @patch.object(MechanicModel, "_get_by_cedula")
    def test_toggle_estado(self, mock_get_by_cedula, mock_update, model):
        mock_get_by_cedula.return_value = None
        assert model.ejecutar("toggle_estado", "V-00000000") is None

        mock_get_by_cedula.return_value = {"cedula": "V-12345678", "estado": 1}
        mock_update.return_value = 1
        assert model.ejecutar("toggle_estado", "V-12345678") == 0

        mock_get_by_cedula.return_value = {"cedula": "V-12345678", "estado": 0}
        assert model.ejecutar("toggle_estado", "V-12345678") == 1

    @patch.object(MechanicModel, "update")
    def test_reactivar(self, mock_update, model):
        mock_update.return_value = 1
        result = model.ejecutar("reactivar", "V-12345678")
        assert result == 1
        mock_update.assert_called_once()
        query = mock_update.call_args[0][1]
        assert "estado = 1" in query

    @patch.object(MechanicModel, "fetch_all")
    def test_get_service_history(self, mock_fetch_all, model):
        mock_fetch_all.return_value = [
            {"id": 1, "estado": "completado", "servicio_nombre": "Alineación"}
        ]
        history = model.ejecutar("get_service_history", "V-12345678")
        assert len(history) == 1
        assert history[0]["servicio_nombre"] == "Alineación"
        mock_fetch_all.assert_called_once()

    def test_ejecutar_invalid_action(self, model):
        with pytest.raises(ValueError) as exc_info:
            model.ejecutar("accion_inexistente")
        
        assert "Accion no permitida" in str(exc_info.value)


class TestMechanicModelHelperChecks:

    @patch.object(MechanicModel, "fetch_one")
    def test_cedula_exists_with_and_without_exclude(self, mock_fetch_one, model):
        mock_fetch_one.return_value = {"cedula_mecanico": "V-12345678"}
        assert model.ejecutar("cedula_exists", "V-12345678", exclude_cedula="V-87654321") is True
        query = mock_fetch_one.call_args[0][1]
        assert "AND cedula_mecanico != %s" in query

        mock_fetch_one.return_value = None
        assert model.ejecutar("cedula_exists", "V-99999999") is False
