import pytest
from unittest.mock import patch
from model.sucursal_model import SucursalModel
from config.validation import ValidationError


@pytest.fixture
def model():
    return SucursalModel()


class TestSucursalModelProperties:

    def test_property_setters_strip_whitespace(self, model):
        model.nombre = "  Sucursal Barquisimeto Este  "
        model.direccion = "  Av. Lara con Av. Los Leones  "
        model.telefono = "  04145551234  "
        model.email = "  barquisimeto@transalca.com  "

        assert model.nombre == "Sucursal Barquisimeto Este"
        assert model.direccion == "Av. Lara con Av. Los Leones"
        assert model.telefono == "04145551234"
        assert model.email == "barquisimeto@transalca.com"

    def test_property_setters_none(self, model):
        model.nombre = None
        model.direccion = None
        model.telefono = None
        model.email = None

        assert model.nombre is None
        assert model.direccion is None
        assert model.telefono is None
        assert model.email is None


class TestSucursalModelValidation:

    @pytest.mark.parametrize("valid_nombre", [
        "Sucursal Centro",
        "Sucursal Barquisimeto Este",
        "Sucursal Cabudare",
        "Sucursal Principal No 1",
    ])
    def test_validate_valid_nombre(self, model, valid_nombre):
        data = {
            "nombre": valid_nombre,
            "direccion": "Av. Principal 123",
            "telefono": "04121234567",
            "email": "sucursal@transalca.com"
        }
        clean = model._validate(data)
        assert clean["nombre"] == valid_nombre

    @pytest.mark.parametrize("invalid_nombre, expected_err", [
        ("", "nombre"),
        ("AB", "nombre"),
        ("ABC1234567", "nombre"),
        ("<script>", "nombre"),
    ])
    def test_validate_invalid_nombre(self, model, invalid_nombre, expected_err):
        data = {
            "nombre": invalid_nombre,
            "direccion": "Av. Principal 123"
        }
        with pytest.raises(ValidationError) as exc_info:
            model._validate(data)
        assert expected_err in exc_info.value.errors

    @pytest.mark.parametrize("invalid_direccion", [
        "   ",
        "Dirección con <script>",
        "A" * 45,
    ])
    def test_validate_invalid_direccion(self, model, invalid_direccion):
        data = {
            "nombre": "Sucursal Centro",
            "direccion": invalid_direccion
        }
        with pytest.raises(ValidationError) as exc_info:
            model._validate(data)
        assert "direccion" in exc_info.value.errors

    @pytest.mark.parametrize("invalid_email", [
        "correo-sin-arroba",
        "correo@sin-tld",
    ])
    def test_validate_invalid_email(self, model, invalid_email):
        data = {
            "nombre": "Sucursal Centro",
            "email": invalid_email
        }
        with pytest.raises(ValidationError) as exc_info:
            model._validate(data)
        assert "email" in exc_info.value.errors


class TestSucursalModelDatabaseOperations:

    def test_get_all(self, model):
        with patch.object(SucursalModel, "fetch_all", return_value=[
            {"id": 1, "nombre": "Sucursal Centro", "direccion": "Av. Vargas", "estado": 1}
        ]) as mock_fetch:
            result = model.ejecutar("get_all")
            assert len(result) == 1
            assert result[0]["nombre"] == "Sucursal Centro"
            mock_fetch.assert_called_once()

    def test_get_active(self, model):
        with patch.object(SucursalModel, "fetch_all", return_value=[{"id": 1, "nombre": "Sucursal Activa"}]) as mock_fetch:
            result = model.ejecutar("get_active")
            assert len(result) == 1
            mock_fetch.assert_called_once()

    def test_get_by_id(self, model):
        with patch.object(SucursalModel, "fetch_one", return_value={"id": 1, "nombre": "Sucursal Centro"}) as mock_fetch:
            result = model.ejecutar("get_by_id", 1)
            assert result["id"] == 1
            mock_fetch.assert_called_once()

    def test_get_by_nombre(self, model):
        with patch.object(SucursalModel, "fetch_one", return_value={"id": 1, "nombre": "Sucursal Centro"}):
            result = model.ejecutar("get_by_nombre", "Sucursal Centro")
            assert result["id"] == 1

    @pytest.mark.parametrize("exclude_id, query_result, expected", [
        (None, {"id_sucursal": 1}, True),
        (None, None, False),
        (2, {"id_sucursal": 1}, True),
        (2, None, False),
    ])
    def test_nombre_exists(self, model, exclude_id, query_result, expected):
        with patch.object(SucursalModel, "fetch_one", return_value=query_result):
            res = model.ejecutar("nombre_exists", "Sucursal Centro", exclude_id)
            assert res is expected

    def test_create_new_success(self, model):
        data = {
            "nombre": "Sucursal Oeste",
            "direccion": "Av. Los Horcones",
            "telefono": "04121234567",
            "email": "oeste@transalca.com"
        }
        with patch.object(SucursalModel, "_get_by_nombre", return_value=None), \
             patch.object(SucursalModel, "email_exists_globally", return_value=False), \
             patch.object(SucursalModel, "insert", return_value=5) as mock_insert:
            res = model.ejecutar("create", data)
            assert res == 5
            mock_insert.assert_called_once()

    def test_create_reactivates_inactive_branch(self, model):
        data = {
            "nombre": "Sucursal Oeste",
            "direccion": "Av. Los Horcones",
            "telefono": "04121234567",
            "email": "oeste@transalca.com"
        }
        existing = {"id": 2, "nombre": "Sucursal Oeste", "estado": 0}
        with patch.object(SucursalModel, "_get_by_nombre", return_value=existing), \
             patch.object(SucursalModel, "email_exists_globally", return_value=False), \
             patch.object(SucursalModel, "update", return_value=1) as mock_update:
            res = model.ejecutar("create", data)
            assert res == 2
            mock_update.assert_called_once()

    def test_create_reactivates_duplicate_email_error(self, model):
        data = {
            "nombre": "Sucursal Oeste",
            "email": "oeste@transalca.com"
        }
        existing = {"id": 2, "nombre": "Sucursal Oeste", "estado": 0}
        with patch.object(SucursalModel, "_get_by_nombre", return_value=existing), \
             patch.object(SucursalModel, "email_exists_globally", return_value=True):
            with pytest.raises(ValidationError) as exc:
                model.ejecutar("create", data)
            assert "email" in exc.value.errors

    def test_create_duplicate_active_sucursal_raises_error(self, model):
        with patch.object(SucursalModel, "_get_by_nombre", return_value={"id": 1, "nombre": "Sucursal Centro", "estado": 1}):
            data = {"nombre": "Sucursal Centro", "direccion": "Av. Vargas"}
            with pytest.raises(ValidationError) as exc_info:
                model.ejecutar("create", data)
            assert "nombre" in exc_info.value.errors

    def test_create_duplicate_email_new_branch_raises_error(self, model):
        with patch.object(SucursalModel, "_get_by_nombre", return_value=None), \
             patch.object(SucursalModel, "email_exists_globally", return_value=True):
            data = {"nombre": "Sucursal Nueva", "email": "duplicado@transalca.com"}
            with pytest.raises(ValidationError) as exc:
                model.ejecutar("create", data)
            assert "email" in exc.value.errors

    def test_update_sucursal_success(self, model):
        data = {
            "nombre": "Sucursal Actualizada",
            "direccion": "Calle 20",
            "telefono": "04141234567",
            "email": "actualizada@transalca.com"
        }
        with patch.object(SucursalModel, "_nombre_exists", return_value=False), \
             patch.object(SucursalModel, "email_exists_globally", return_value=False), \
             patch.object(SucursalModel, "update", return_value=1) as mock_update:
            res = model.ejecutar("update_sucursal", 1, data)
            assert res == 1
            mock_update.assert_called_once()

    def test_update_sucursal_duplicate_nombre_error(self, model):
        data = {"nombre": "Sucursal Repetida"}
        with patch.object(SucursalModel, "_nombre_exists", return_value=True):
            with pytest.raises(ValidationError) as exc:
                model.ejecutar("update_sucursal", 1, data)
            assert "nombre" in exc.value.errors

    def test_update_sucursal_duplicate_email_error(self, model):
        data = {"nombre": "Sucursal Valida", "email": "duplicado@transalca.com"}
        with patch.object(SucursalModel, "_nombre_exists", return_value=False), \
             patch.object(SucursalModel, "email_exists_globally", return_value=True):
            with pytest.raises(ValidationError) as exc:
                model.ejecutar("update_sucursal", 1, data)
            assert "email" in exc.value.errors

    def test_toggle_estado(self, model):
        with patch.object(SucursalModel, "update", return_value=1) as mock_update:
            res = model.ejecutar("toggle_estado", 1)
            assert res == 1
            mock_update.assert_called_once()

    def test_soft_delete(self, model):
        with patch.object(SucursalModel, "update", return_value=1) as mock_update:
            res = model.ejecutar("soft_delete", 1)
            assert res == 1
            mock_update.assert_called_once()

    def test_reactivar(self, model):
        with patch.object(SucursalModel, "update", return_value=1) as mock_update:
            res = model.ejecutar("reactivar", 1)
            assert res == 1
            mock_update.assert_called_once()

    def test_ejecutar_invalid_action(self, model):
        with pytest.raises(ValueError) as exc_info:
            model.ejecutar("accion_inexistente")
        assert "Accion no permitida" in str(exc_info.value)
