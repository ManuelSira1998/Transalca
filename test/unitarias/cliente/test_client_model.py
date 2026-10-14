import pytest
from unittest.mock import MagicMock, patch
from model.client_model import ClientModel
from config.validation import ValidationError


@pytest.fixture
def model():
    """Fixture para obtener una instancia limpia de ClientModel."""
    return ClientModel()


class TestClientModelProperties:
    """Pruebas unitarias para getters y setters del modelo de cliente."""

    def test_property_setters_strip_whitespace(self, model):
        model.cedula = "  V-12345678  "
        model.nombre = "  Ana  "
        model.apellido = "  López  "
        model.email = "  cliente@ejemplo.com  "
        model.telefono = "  04121234567  "
        model.direccion = "  Av. Principal  "

        assert model.cedula == "V-12345678"
        assert model.nombre == "Ana"
        assert model.apellido == "López"
        assert model.email == "cliente@ejemplo.com"
        assert model.telefono == "04121234567"
        assert model.direccion == "Av. Principal"

    def test_property_setters_none(self, model):
        model.cedula = None
        model.nombre = None
        model.apellido = None
        model.email = None
        model.telefono = None
        model.direccion = None

        assert model.cedula is None
        assert model.nombre is None
        assert model.apellido is None
        assert model.email is None
        assert model.telefono is None
        assert model.direccion is None

    def test_full_name_static_method(self):
        assert ClientModel._full_name({"nombre": "Juan", "apellido": "Pérez"}) == "Juan Pérez"
        assert ClientModel._full_name({"nombre": "Empresa C.A.", "apellido": ""}) == "Empresa C.A."


class TestClientModelValidation:
    """Pruebas unitarias con Data Provider (@pytest.mark.parametrize) para validaciones de cliente."""

    # DATA PROVIDER: Pruebas con diferentes formatos de cédula válidos
    @pytest.mark.parametrize("input_cedula, expected_cedula, expected_prefijo", [
        ("V-12345678", "V-12345678", "V"),
        ("E-87654321", "E-87654321", "E"),
        ("J-12345678", "J-12345678", "J"),
        ("v 12345678", "V-12345678", "V"),
        ("V12345678", "V-12345678", "V"),
    ])
    def test_validate_valid_cedulas_data_provider(self, model, input_cedula, expected_cedula, expected_prefijo):
        data = {
            "cedula": input_cedula,
            "nombre": "Ana",
            "apellido": "López",
            "telefono": "04141234567",
            "email": "ana@ejemplo.com"
        }
        clean = model._validate(data)
        assert clean["cedula"] == expected_cedula
        assert clean["cedula_prefijo"] == expected_prefijo

    # DATA PROVIDER: Pruebas con formatos de cédulas inválidos
    @pytest.mark.parametrize("invalid_cedula", [
        "XYZ-99999",
        "123",            # Cédula muy corta
        "V-ABCDEFGH",     # Letras en parte numérica
        "",               # Cédula vacía
    ])
    def test_validate_invalid_cedulas_data_provider(self, model, invalid_cedula):
        data = {
            "cedula": invalid_cedula,
            "nombre": "Ana",
            "telefono": "04141234567"
        }
        with pytest.raises(ValidationError) as exc_info:
            model._validate(data, require_cedula=True)
        assert "cedula" in exc_info.value.errors

    # DATA PROVIDER: Validaciones de campos de teléfono y correo
    @pytest.mark.parametrize("telefono, email, expected_error_field", [
        ("123", "ana@ejemplo.com", "telefono"),             # Teléfono inválido
        ("04141234567", "correo_invalido", "email"),         # Correo inválido
        ("04141234567", "sin_arroba.com", "email"),          # Correo sin @
    ])
    def test_validate_contact_fields_data_provider(self, model, telefono, email, expected_error_field):
        data = {
            "cedula": "V-12345678",
            "nombre": "Ana",
            "telefono": telefono,
            "email": email
        }
        with pytest.raises(ValidationError) as exc_info:
            model._validate(data)
        assert expected_error_field in exc_info.value.errors


class TestClientModelDatabaseOperations:
    """Pruebas unitarias con mocks de base de datos para operaciones CRUD de cliente."""

    @patch.object(ClientModel, "fetch_all")
    def test_get_all(self, mock_fetch_all, model):
        mock_fetch_all.return_value = [
            {"cedula": "V-12345678", "nombre": "Ana López", "telefono": "04141234567", "estado": 1}
        ]
        result = model.ejecutar("get_all")

        assert len(result) == 1
        assert result[0]["cedula"] == "V-12345678"
        mock_fetch_all.assert_called_once()

    @patch.object(ClientModel, "fetch_one")
    def test_get_by_cedula(self, mock_fetch_one, model):
        mock_fetch_one.return_value = {"cedula": "V-12345678", "nombre": "Ana López"}
        result = model.ejecutar("get_by_cedula", "V-12345678")

        assert result["cedula"] == "V-12345678"
        mock_fetch_one.assert_called_once()

    @patch.object(ClientModel, "con_transalca")
    @patch.object(ClientModel, "_user_by_cedula", return_value=None)
    @patch.object(ClientModel, "email_exists_globally", return_value=False)
    @patch.object(ClientModel, "_get_by_cedula", return_value=None)
    def test_create_new_client_success(
        self, mock_get_by_cedula, mock_email_exists, mock_user, mock_con, model
    ):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.lastrowid = 1
        mock_conn.cursor.return_value = mock_cursor
        mock_con.return_value = mock_conn

        data = {
            "cedula": "V-12345678",
            "nombre": "Ana",
            "apellido": "López",
            "email": "ana@ejemplo.com",
            "telefono": "04141234567",
            "direccion": "Av. Principal"
        }
        res = model.ejecutar("create", data)
        assert res["cedula"] == "V-12345678"
        assert res["reactivated"] is False
        mock_conn.commit.assert_called_once()

    @patch.object(ClientModel, "_get_by_cedula")
    def test_create_duplicate_active_client_raises_error(self, mock_get_by_cedula, model):
        mock_get_by_cedula.return_value = {"cedula": "V-12345678", "estado": 1}

        data = {
            "cedula": "V-12345678",
            "nombre": "Ana",
            "telefono": "04141234567"
        }
        with pytest.raises(ValidationError) as exc_info:
            model.ejecutar("create", data)

        assert "cedula" in exc_info.value.errors

    @patch.object(ClientModel, "update")
    @patch.object(ClientModel, "_get_by_cedula", return_value={"id_cliente": 1, "cedula": "V-12345678", "email": "ana@ejemplo.com"})
    @patch.object(ClientModel, "email_exists_globally", return_value=False)
    @patch.object(ClientModel, "fetch_one")
    def test_update_client_success(self, mock_fetch_one, mock_email_exists, mock_get_by_cedula, mock_update, model):
        mock_fetch_one.return_value = None  # No cedula duplicate
        mock_update.return_value = 1

        data = {
            "cedula": "V-12345678",
            "nombre": "Ana Modificada",
            "email": "ana_nueva@ejemplo.com",
            "telefono": "04141234567"
        }
        res = model.ejecutar("update_client", "V-12345678", data)
        assert res == 1
        mock_update.assert_called_once()

    @patch.object(ClientModel, "email_exists_globally", return_value=True)
    def test_update_client_duplicate_email_fails(self, mock_email_exists, model):
        data = {
            "cedula": "V-12345678",
            "nombre": "Ana",
            "email": "repetido@ejemplo.com",
            "telefono": "04141234567"
        }
        with pytest.raises(ValidationError) as exc_info:
            model.ejecutar("update_client", "V-12345678", data)
        assert "email" in exc_info.value.errors

    @patch.object(ClientModel, "update")
    @patch.object(ClientModel, "_get_by_cedula")
    def test_soft_delete(self, mock_get_by_cedula, mock_update, model):
        mock_get_by_cedula.return_value = {"cedula": "V-12345678", "estado": 0}
        mock_update.return_value = 1

        result = model.ejecutar("soft_delete", "V-12345678")

        assert result == 0
        mock_update.assert_called_once()

    @patch.object(ClientModel, "update")
    @patch.object(ClientModel, "_get_by_cedula")
    def test_toggle_estado(self, mock_get_by_cedula, mock_update, model):
        # Inexistente
        mock_get_by_cedula.return_value = None
        assert model.ejecutar("toggle_estado", "V-00000000") == 0

        # Existente deshabilitado
        mock_get_by_cedula.return_value = {"cedula": "V-12345678", "estado": 0}
        assert model.ejecutar("toggle_estado", "V-12345678") == 0

    @patch.object(ClientModel, "fetch_one")
    def test_get_stats(self, mock_fetch_one, model):
        mock_fetch_one.side_effect = [{"total": 10}, {"total": 8}]
        stats = model.ejecutar("get_stats", "persona")

        assert stats["total"] == 10
        assert stats["activos"] == 8

    @patch.object(ClientModel, "fetch_all")
    def test_get_related_entities(self, mock_fetch_all, model):
        mock_fetch_all.return_value = [{"id": 1}]

        assert len(model.ejecutar("get_vehicles", "V-12345678")) == 1
        assert len(model.ejecutar("get_services", "V-12345678")) == 1
        assert len(model.ejecutar("get_tickets", "V-12345678")) == 1
        assert len(model.ejecutar("get_orders", "V-12345678")) == 1

    @patch.object(ClientModel, "fetch_all")
    def test_get_bitacora(self, mock_fetch_all, model):
        mock_fetch_all.return_value = [{"id": 5, "evento": "Cambio de frenos"}]
        bitacora = model.ejecutar("get_bitacora", "V-12345678")
        assert len(bitacora) == 1

    @patch.object(ClientModel, "fetch_one")
    def test_email_exists_globally(self, mock_fetch_one, model):
        mock_fetch_one.return_value = {"id": 1}
        assert model.ejecutar("email_exists_globally", "test@transalca.com") is True

        mock_fetch_one.return_value = None
        assert model.ejecutar("email_exists_globally", "nadie@transalca.com") is False

    def test_ejecutar_invalid_action(self, model):
        with pytest.raises(ValueError) as exc_info:
            model.ejecutar("accion_inexistente")

        assert "Accion no permitida" in str(exc_info.value)
