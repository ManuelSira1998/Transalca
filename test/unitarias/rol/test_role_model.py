import pytest
from unittest.mock import patch, MagicMock
from model.role_model import RoleModel
from config.validation import ValidationError


@pytest.fixture
def model():
    """Fixture para obtener una instancia limpia de RoleModel."""
    return RoleModel()


class TestRoleModelProperties:
    """Pruebas unitarias para getters y setters del modelo de rol."""

    def test_property_setters_strip_whitespace(self, model):
        model.nombre = "  Supervisión  "
        model.descripcion = "  Rol con permisos de auditoría  "

        assert model.nombre == "Supervisión"
        assert model.descripcion == "Rol con permisos de auditoría"

    def test_property_setters_none(self, model):
        model.nombre = None
        model.descripcion = None

        assert model.nombre is None
        assert model.descripcion is None


class TestRoleModelValidation:
    """Pruebas unitarias con Data Provider (@pytest.mark.parametrize) para validaciones de rol."""

    # DATA PROVIDER: Nombres de roles válidos
    @pytest.mark.parametrize("valid_nombre", [
        "Administrador",
        "Mecánico Senior",
        "Cajero Principal",
        "Vendedor de Campo",
    ])
    def test_validate_valid_nombre_data_provider(self, model, valid_nombre):
        data = {
            "nombre": valid_nombre,
            "descripcion": "Descripción opcional del rol"
        }
        clean = model._validate(data)
        assert clean["nombre"] == valid_nombre

    # DATA PROVIDER: Nombres de roles inválidos
    @pytest.mark.parametrize("invalid_nombre", [
        "",             # Nombre vacío
        "   ",          # Solo espacios
        "AB",           # Menor a 3 caracteres
        "X" * 61,       # Mayor a 60 caracteres
    ])
    def test_validate_invalid_nombre_data_provider(self, model, invalid_nombre):
        data = {
            "nombre": invalid_nombre
        }
        with pytest.raises(ValidationError) as exc_info:
            model._validate(data)
        assert "nombre" in exc_info.value.errors

    def test_validate_descripcion_exceeds_max_len_fails(self, model):
        data = {
            "nombre": "Rol Válido",
            "descripcion": "D" * 151  # Mayor a 150 caracteres
        }
        with pytest.raises(ValidationError) as exc_info:
            model._validate(data)
        assert "descripcion" in exc_info.value.errors


class TestRoleModelDatabaseOperations:
    """Pruebas unitarias con mocks de base de datos para operaciones de roles y permisos."""

    @patch.object(RoleModel, "fetch_all")
    def test_get_all(self, mock_fetch_all, model):
        mock_fetch_all.return_value = [
            {"id": 1, "nombre": "Administrador", "descripcion": "Acceso total", "estado": 1}
        ]
        result = model.ejecutar("get_all")

        assert len(result) == 1
        assert result[0]["nombre"] == "Administrador"
        mock_fetch_all.assert_called_once()

    @patch.object(RoleModel, "fetch_one")
    def test_get_by_id(self, mock_fetch_one, model):
        mock_fetch_one.return_value = {"id": 1, "nombre": "Administrador"}
        result = model.ejecutar("get_by_id", 1)

        assert result["id"] == 1
        mock_fetch_one.assert_called_once()

    @patch.object(RoleModel, "insert")
    def test_create_role_success(self, mock_insert, model):
        mock_insert.return_value = 3
        data = {"nombre": "Supervisor Taller", "descripcion": "Control de trabajos"}
        role_id = model.ejecutar("create", data)

        assert role_id == 3
        mock_insert.assert_called_once()
        args = mock_insert.call_args[0]
        params = args[2]
        assert params == ("Supervisor Taller", "Control de trabajos")

    @patch.object(RoleModel, "update")
    def test_update_role_success(self, mock_update, model):
        mock_update.return_value = 1
        data = {"nombre": "Supervisor General", "descripcion": "Descripción actualizada"}
        result = model.ejecutar("update_role", 3, data)

        assert result == 1
        mock_update.assert_called_once()
        args = mock_update.call_args[0]
        params = args[2]
        assert params == ("Supervisor General", "Descripción actualizada", 3)

    @patch.object(RoleModel, "_get_by_id")
    def test_soft_delete_administrator_protected(self, mock_get_by_id, model):
        mock_get_by_id.return_value = {"id": 1, "nombre": "Administrador", "estado": 1}
        result = model.ejecutar("soft_delete", 1)
        assert result is False

    @patch.object(RoleModel, "_get_by_id")
    def test_soft_delete_nonexistent_returns_none(self, mock_get_by_id, model):
        mock_get_by_id.return_value = None
        result = model.ejecutar("soft_delete", 999)
        assert result is None

    @patch.object(RoleModel, "update")
    @patch.object(RoleModel, "_get_by_id")
    def test_soft_delete_custom_role(self, mock_get_by_id, mock_update, model):
        mock_get_by_id.return_value = {"id": 2, "nombre": "Asistente", "estado": 1}
        mock_update.return_value = 1

        result = model.ejecutar("soft_delete", 2)
        assert result == 0
        mock_update.assert_called_once()

    @patch.object(RoleModel, "update")
    def test_update_status(self, mock_update, model):
        mock_update.return_value = 1
        result = model.ejecutar("update_status", 2, 0)
        assert result == 1
        mock_update.assert_called_once_with(
            "mantenimiento", "UPDATE roles SET estado = %s WHERE id = %s", (0, 2)
        )

    @patch.object(RoleModel, "fetch_all")
    def test_get_permissions(self, mock_fetch_all, model):
        mock_fetch_all.return_value = [
            {"id": 10, "rol_id": 1, "modulo": "clientes", "crear": 1, "leer": 1, "actualizar": 1, "eliminar": 1}
        ]
        perms = model.ejecutar("get_permissions", 1)

        assert len(perms) == 1
        assert perms[0]["modulo"] == "clientes"

    @patch.object(RoleModel, "update")
    @patch.object(RoleModel, "fetch_one")
    def test_set_permission_updates_existing(self, mock_fetch_one, mock_update, model):
        mock_fetch_one.return_value = {"id": 5}
        mock_update.return_value = 1

        res = model.ejecutar("set_permission", 1, "ventas", 1, 1, 0, 0)
        assert res == 1
        mock_update.assert_called_once()
        query = mock_update.call_args[0][1]
        assert "UPDATE permisos SET crear = %s" in query

    @patch.object(RoleModel, "insert")
    @patch.object(RoleModel, "fetch_one")
    def test_set_permission_inserts_new(self, mock_fetch_one, mock_insert, model):
        mock_fetch_one.return_value = None
        mock_insert.return_value = 12

        res = model.ejecutar("set_permission", 1, "inventario", 1, 1, 1, 1)
        assert res == 12
        mock_insert.assert_called_once()
        query = mock_insert.call_args[0][1]
        assert "INSERT INTO permisos" in query

    @patch.object(RoleModel, "insert")
    @patch.object(RoleModel, "delete")
    def test_save_all_permissions(self, mock_delete, mock_insert, model):
        permissions = [
            {"modulo": "usuarios", "crear": 1, "leer": 1, "actualizar": 1, "eliminar": 0},
            {"modulo": "reportes", "crear": 0, "leer": 1, "actualizar": 0, "eliminar": 0},
        ]
        model.ejecutar("save_all_permissions", 2, permissions)

        mock_delete.assert_called_once_with(
            "mantenimiento", "DELETE FROM permisos WHERE rol_id = %s", (2,)
        )
        assert mock_insert.call_count == 2

    @patch.object(RoleModel, "fetch_all")
    def test_get_modules(self, mock_fetch_all, model):
        mock_fetch_all.return_value = [
            {"modulo": "roles", "titulo": "Roles", "grupo": "Seguridad"}
        ]
        mods = model.ejecutar("get_modules")
        assert len(mods) == 1
        assert mods[0]["modulo"] == "roles"
        mock_fetch_all.assert_called_once()

    def test_ejecutar_invalid_action(self, model):
        with pytest.raises(ValueError) as exc_info:
            model.ejecutar("accion_inexistente")

        assert "Accion no permitida" in str(exc_info.value)
