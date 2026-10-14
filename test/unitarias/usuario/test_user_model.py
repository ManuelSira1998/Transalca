import pytest
from unittest.mock import patch, MagicMock
from model.user_model import UserModel
from config.validation import ValidationError


@pytest.fixture
def model():
    """Instancia del modelo de usuario para pruebas."""
    return UserModel()


class TestUserModelProperties:
    """Pruebas unitarias para getters y setters del modelo de usuario."""

    def test_property_setters_strip_whitespace(self, model):
        model.cedula = "  V-12345678  "
        model.nombre = "  María  "
        model.apellido = "  Delgado  "
        model.email = "  maria@ejemplo.com  "
        model.telefono = "  04161234567  "
        model.direccion = "  Calle Principal  "

        assert model.cedula == "V-12345678"
        assert model.nombre == "María"
        assert model.apellido == "Delgado"
        assert model.email == "maria@ejemplo.com"
        assert model.telefono == "04161234567"
        assert model.direccion == "Calle Principal"

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


class TestUserModelValidation:
    """Pruebas unitarias con Data Provider (@pytest.mark.parametrize) para validaciones de usuario."""

    @pytest.mark.parametrize("password, is_valid", [
        ("Clave123!", True),
        ("Admin2026#", True),
        ("Pass.1234", True),
        ("corta1!", False),            # Menos de 8 caracteres
        ("sinmayus1!", False),         # Sin mayúscula
        ("SINMINUS1!", False),         # Sin minúscula
        ("SinNumero!", False),         # Sin número
        ("SinEspecial123", False),    # Sin carácter especial
    ])
    def test_validate_password(self, model, password, is_valid):
        data = {
            "nombre": "María",
            "apellido": "Delgado",
            "cedula": "V-12345678",
            "email": "maria@ejemplo.com",
            "rol_id": 1,
            "tipo": "empleado",
            "password": password,
            "confirm_password": password
        }
        with patch.object(UserModel, "_role_exists", return_value=True):
            if is_valid:
                clean = model.ejecutar("validate", data, require_password=True)
                assert clean["password"] == password
            else:
                with pytest.raises(ValidationError) as exc_info:
                    model.ejecutar("validate", data, require_password=True)
                assert "password" in exc_info.value.errors

    @pytest.mark.parametrize("password, confirm_password", [
        ("Clave123!", "Clave1234!"),
        ("Admin2026#", "admin2026#"),
    ])
    def test_validate_password_mismatch(self, model, password, confirm_password):
        data = {
            "nombre": "María",
            "apellido": "Delgado",
            "cedula": "V-12345678",
            "email": "maria@ejemplo.com",
            "rol_id": 1,
            "tipo": "empleado",
            "password": password,
            "confirm_password": confirm_password
        }
        with patch.object(UserModel, "_role_exists", return_value=True):
            with pytest.raises(ValidationError) as exc_info:
                model.ejecutar("validate", data, require_password=True)
            assert "confirm_password" in exc_info.value.errors

    @pytest.mark.parametrize("invalid_rol_id", [None, "", 0, "0", "abc"])
    def test_validate_invalid_role(self, model, invalid_rol_id):
        data = {
            "nombre": "María",
            "apellido": "Delgado",
            "cedula": "V-12345678",
            "email": "maria@ejemplo.com",
            "rol_id": invalid_rol_id,
            "tipo": "empleado"
        }
        with pytest.raises(ValidationError) as exc_info:
            model.ejecutar("validate", data)
        assert "rol_id" in exc_info.value.errors

    @pytest.mark.parametrize("invalid_cedula", [
        "12345678",        # Sin prefijo
        "X-12345678",      # Prefijo invalido
        "V-abc",           # Letras
        "",                # Vacia
    ])
    def test_validate_invalid_cedula(self, model, invalid_cedula):
        data = {
            "nombre": "María",
            "apellido": "Delgado",
            "cedula": invalid_cedula,
            "email": "maria@ejemplo.com",
            "rol_id": 1,
            "tipo": "empleado"
        }
        with pytest.raises(ValidationError) as exc_info:
            model.ejecutar("validate", data)
        assert "cedula" in exc_info.value.errors


class TestUserModelDatabaseOperations:
    """Pruebas unitarias con mocks de base de datos para operaciones de usuario."""

    @pytest.mark.parametrize("tipo", [None, "empleado", "cliente"])
    def test_get_all(self, model, tipo):
        with patch.object(UserModel, "fetch_all", return_value=[
            {"id": 1, "nombre": "María", "apellido": "Delgado", "email": "maria@ejemplo.com", "estado": 1}
        ]) as mock_fetch:
            result = model.ejecutar("get_all", tipo)
            assert len(result) == 1
            assert result[0]["nombre"] == "María"
            mock_fetch.assert_called_once()

    def test_get_all_invalid_tipo_raises_error(self, model):
        with pytest.raises(ValidationError) as exc_info:
            model.ejecutar("get_all", "tipo_invalido")
        assert "tipo" in exc_info.value.errors

    def test_get_by_id(self, model):
        with patch.object(UserModel, "fetch_one", return_value={"id": 1, "nombre": "María", "cedula": "V-12345678"}) as mock_fetch:
            result = model.ejecutar("get_by_id", 1)
            assert result["id"] == 1
            assert result["nombre"] == "María"
            mock_fetch.assert_called_once()

    def test_get_by_cedula(self, model):
        with patch.object(UserModel, "fetch_one", return_value={"id": 1, "cedula": "V-12345678"}):
            res = model.ejecutar("get_by_cedula", "V-12345678")
            assert res["id"] == 1

    def test_get_by_email(self, model):
        with patch.object(UserModel, "fetch_one", return_value={"id": 1, "email": "test@mail.com"}):
            res = model.ejecutar("get_by_email", "test@mail.com")
            assert res["id"] == 1

    @pytest.mark.parametrize("estado_val", [0, 1, "0", "1"])
    def test_update_status_success(self, model, estado_val):
        with patch.object(UserModel, "update", return_value=1) as mock_update:
            result = model.ejecutar("update_status", 1, estado_val)
            assert result == 1
            mock_update.assert_called_once()

    def test_update_status_invalid_value_raises_error(self, model):
        with pytest.raises(ValidationError) as exc_info:
            model.ejecutar("update_status", 1, 99)
        assert "estado" in exc_info.value.errors

    def test_soft_delete_last_admin_fails(self, model):
        with patch.object(UserModel, "fetch_one") as mock_fetch_one:
            mock_fetch_one.side_effect = [
                {"id": 1},                 # es admin
                {"total": 1}               # total administradores = 1
            ]
            result = model.ejecutar("soft_delete", 1)
            assert result is False

    def test_soft_delete_normal_user_success(self, model):
        with patch.object(UserModel, "fetch_one", return_value=None), \
             patch.object(UserModel, "update", return_value=1) as mock_update:
            res = model.ejecutar("soft_delete", 2)
            assert res == 1
            mock_update.assert_called_once()

    def test_create_user_new_success(self, model):
        data = {
            "nombre": "Pedro",
            "apellido": "Perez",
            "cedula": "V-12345678",
            "email": "pedro@ejemplo.com",
            "rol_id": 2,
            "tipo": "empleado",
            "password": "Password123!",
            "confirm_password": "Password123!"
        }
        with patch.object(UserModel, "_role_exists", return_value=True), \
             patch.object(UserModel, "_get_by_cedula", return_value=None), \
             patch.object(UserModel, "_get_by_email", return_value=None), \
             patch.object(UserModel, "email_exists_globally", return_value=False), \
             patch.object(UserModel, "_insert_user", return_value=10), \
             patch.object(UserModel, "_assign_role", return_value=1):
            user_id = model.ejecutar("create", data)
            assert user_id == 10

    def test_create_user_duplicate_active_cedula(self, model):
        data = {
            "nombre": "Pedro",
            "apellido": "Perez",
            "cedula": "V-12345678",
            "email": "pedro@ejemplo.com",
            "rol_id": 2,
            "tipo": "empleado",
            "password": "Password123!",
            "confirm_password": "Password123!"
        }
        with patch.object(UserModel, "_role_exists", return_value=True), \
             patch.object(UserModel, "_get_by_cedula", return_value={"id": 1, "estado": 1}):
            with pytest.raises(ValidationError) as exc:
                model.ejecutar("create", data)
            assert "cedula" in exc.value.errors

    def test_create_user_duplicate_active_email(self, model):
        data = {
            "nombre": "Pedro",
            "apellido": "Perez",
            "cedula": "V-12345678",
            "email": "pedro@ejemplo.com",
            "rol_id": 2,
            "tipo": "empleado",
            "password": "Password123!",
            "confirm_password": "Password123!"
        }
        with patch.object(UserModel, "_role_exists", return_value=True), \
             patch.object(UserModel, "_get_by_cedula", return_value=None), \
             patch.object(UserModel, "_get_by_email", return_value={"id": 1, "estado": 1}):
            with pytest.raises(ValidationError) as exc:
                model.ejecutar("create", data)
            assert "email" in exc.value.errors

    def test_create_user_reactivates_inactive_user(self, model):
        data = {
            "nombre": "Pedro",
            "apellido": "Perez",
            "cedula": "V-12345678",
            "email": "pedro@ejemplo.com",
            "rol_id": 2,
            "tipo": "empleado",
            "password": "Password123!",
            "confirm_password": "Password123!"
        }
        inactive_user = {"id": 5, "estado": 0}
        with patch.object(UserModel, "_role_exists", return_value=True), \
             patch.object(UserModel, "_get_by_cedula", return_value=inactive_user), \
             patch.object(UserModel, "_get_by_email", return_value=None), \
             patch.object(UserModel, "email_exists_globally", return_value=False), \
             patch.object(UserModel, "_update_info"), \
             patch.object(UserModel, "_reactivar"), \
             patch.object(UserModel, "_get_user_roles", return_value=[{"id": 1}]), \
             patch.object(UserModel, "_remove_role"), \
             patch.object(UserModel, "_assign_role"):
            res = model.ejecutar("create", data)
            assert res == 5

    def test_update_user_success(self, model):
        data = {
            "nombre": "Pedro",
            "apellido": "Perez",
            "cedula": "V-12345678",
            "email": "pedro@ejemplo.com",
            "rol_id": 2,
            "tipo": "empleado"
        }
        with patch.object(UserModel, "_role_exists", return_value=True), \
             patch.object(UserModel, "_get_user_roles", return_value=[]), \
             patch.object(UserModel, "_email_exists", return_value=False), \
             patch.object(UserModel, "_cedula_exists", return_value=False), \
             patch.object(UserModel, "_update_info"), \
             patch.object(UserModel, "_assign_role"):
            res = model.ejecutar("update_user", 1, data)
            assert res is True

    def test_update_user_duplicate_email(self, model):
        data = {
            "nombre": "Pedro",
            "apellido": "Perez",
            "cedula": "V-12345678",
            "email": "duplicado@ejemplo.com",
            "rol_id": 2,
            "tipo": "empleado"
        }
        with patch.object(UserModel, "_role_exists", return_value=True), \
             patch.object(UserModel, "_get_user_roles", return_value=[]), \
             patch.object(UserModel, "_email_exists", return_value=True):
            with pytest.raises(ValidationError) as exc:
                model.ejecutar("update_user", 1, data)
            assert "email" in exc.value.errors

    def test_update_user_cannot_demote_last_admin(self, model):
        data = {
            "nombre": "Pedro",
            "apellido": "Perez",
            "cedula": "V-12345678",
            "email": "admin@ejemplo.com",
            "rol_id": 2,  # Cambio a rol distinto de admin
            "tipo": "empleado"
        }
        with patch.object(UserModel, "_role_exists", return_value=True), \
             patch.object(UserModel, "_get_user_roles", return_value=[{"id": 1, "nombre": "Administrador"}]), \
             patch.object(UserModel, "_email_exists", return_value=False), \
             patch.object(UserModel, "_cedula_exists", return_value=False), \
             patch.object(UserModel, "_get_role_name", return_value={"nombre": "Vendedor"}), \
             patch.object(UserModel, "_count_active_admins", return_value={"total": 1}):
            with pytest.raises(ValidationError) as exc:
                model.ejecutar("update_user", 1, data)
            assert "rol_id" in exc.value.errors

    def test_assign_and_remove_role(self, model):
        with patch.object(UserModel, "fetch_one", side_effect=[None, {"nombre": "Cliente"}]), \
             patch.object(UserModel, "update", return_value=1), \
             patch.object(UserModel, "insert", return_value=10):
            res = model.ejecutar("assign_role", 1, 3)
            assert res == 10

        with patch.object(UserModel, "delete", return_value=1):
            assert model.ejecutar("remove_role", 1, 3) == 1

    def test_update_photo(self, model):
        with patch.object(UserModel, "update", return_value=1):
            assert model.ejecutar("update_photo", 1, "profile.jpg") == 1

    def test_search(self, model):
        with patch.object(UserModel, "fetch_all", return_value=[{"id": 1, "nombre": "Maria"}]):
            res = model.ejecutar("search", "Maria")
            assert len(res) == 1

    def test_ejecutar_invalid_action(self, model):
        with pytest.raises(ValueError) as exc_info:
            model.ejecutar("accion_inexistente")
        assert "Accion no permitida" in str(exc_info.value)
