import pytest
from unittest.mock import patch
from model.modulo_model import ModuloModel
from config.validation import ValidationError


@pytest.fixture
def model():
    """Fixture para obtener una instancia limpia de ModuloModel."""
    return ModuloModel()


class TestModuloModelValidation:
    """Pruebas unitarias con Data Provider (@pytest.mark.parametrize) para la clave y ruta de módulos."""

    # DATA PROVIDER: Pruebas con claves de módulo válidas (SLUG)
    @pytest.mark.parametrize("valid_nombre, valid_ruta", [
        ("ordenes_compra", "/admin/ordenes-compra"),
        ("clientes", "/admin/clientes"),
        ("gestion_inventario_1", "/admin/inventario"),
    ])
    @patch.object(ModuloModel, "_ruta_exists", return_value=False)
    @patch.object(ModuloModel, "_nombre_exists", return_value=False)
    def test_validate_valid_module_data_provider(
        self, mock_name_exists, mock_route_exists, model, valid_nombre, valid_ruta
    ):
        data = {
            "nombre": valid_nombre,
            "titulo": "Título de Prueba",
            "ruta": valid_ruta,
            "grupo": "Sistema"
        }
        clean = model._validate(data)
        assert clean["nombre"] == valid_nombre
        assert clean["ruta"] == valid_ruta

    # DATA PROVIDER: Pruebas con claves de módulo inválidas
    @pytest.mark.parametrize("invalid_nombre", [
        "Modulo Con Espacios",
        "CLAVE-MAYUSCULA",
        "123_inicial_numero",
        "",
    ])
    def test_validate_invalid_slug_data_provider(self, model, invalid_nombre):
        data = {
            "nombre": invalid_nombre,
            "titulo": "Título de Prueba",
            "ruta": "/admin/prueba",
            "grupo": "Sistema"
        }
        with pytest.raises(ValidationError) as exc_info:
            model._validate(data)
        assert "nombre" in exc_info.value.errors

    # DATA PROVIDER: Pruebas con rutas de módulo inválidas
    @pytest.mark.parametrize("invalid_ruta", [
        "admin/sin_slash_inicial",
        "http://sitio_externo.com",
        "/ruta con espacios",
        "",
    ])
    def test_validate_invalid_route_data_provider(self, model, invalid_ruta):
        data = {
            "nombre": "modulo_prueba",
            "titulo": "Título de Prueba",
            "ruta": invalid_ruta,
            "grupo": "Sistema"
        }
        with pytest.raises(ValidationError) as exc_info:
            model._validate(data)
        assert "ruta" in exc_info.value.errors


class TestModuloModelDatabaseOperations:
    """Pruebas unitarias con mocks de base de datos para operaciones del módulo dinámico de módulos."""

    @patch.object(ModuloModel, "fetch_all")
    def test_get_all(self, mock_fetch_all, model):
        mock_fetch_all.return_value = [
            {"id": 1, "nombre": "clientes", "titulo": "Clientes", "ruta": "/admin/clientes", "estado": 1}
        ]
        result = model.ejecutar("get_all")

        assert len(result) == 1
        assert result[0]["nombre"] == "clientes"
        mock_fetch_all.assert_called_once()

    @patch.object(ModuloModel, "fetch_one")
    def test_get_by_id(self, mock_fetch_one, model):
        mock_fetch_one.return_value = {"id": 1, "nombre": "clientes", "titulo": "Clientes"}
        result = model.ejecutar("get_by_id", 1)

        assert result["id"] == 1
        mock_fetch_one.assert_called_once()

    @patch.object(ModuloModel, "fetch_one")
    def test_get_by_nombre(self, mock_fetch_one, model):
        mock_fetch_one.return_value = {"id": 2, "nombre": "reportes"}
        res = model.ejecutar("get_by_nombre", "reportes")
        assert res["nombre"] == "reportes"

    @patch.object(ModuloModel, "fetch_one")
    def test_get_by_ruta(self, mock_fetch_one, model):
        mock_fetch_one.return_value = {"id": 3, "ruta": "/admin/stock"}
        res = model.ejecutar("get_by_ruta", "/admin/stock")
        assert res["ruta"] == "/admin/stock"

    @patch.object(ModuloModel, "fetch_all")
    def test_get_sidebar_modules(self, mock_fetch_all, model):
        mock_fetch_all.return_value = [
            {"nombre": "clientes", "titulo": "Clientes", "ruta": "/admin/clientes", "icono": "bi bi-people"}
        ]
        result = model.ejecutar("get_sidebar_modules")

        assert len(result) == 1
        assert result[0]["icono"] == "bi bi-people"

    @patch.object(ModuloModel, "fetch_all")
    def test_get_permission_modules(self, mock_fetch_all, model):
        mock_fetch_all.return_value = [{"modulo": "ventas", "titulo": "Ventas", "grupo": "Operaciones"}]
        res = model.ejecutar("get_permission_modules")
        assert len(res) == 1
        assert res[0]["modulo"] == "ventas"

    @patch.object(ModuloModel, "insert")
    @patch.object(ModuloModel, "_get_by_nombre", return_value=None)
    @patch.object(ModuloModel, "_validate")
    def test_create_module_success(self, mock_validate, mock_get_by_name, mock_insert, model):
        mock_validate.return_value = {
            "nombre": "nuevo_mod", "titulo": "Nuevo", "descripcion": "Desc", "ruta": "/admin/nuevo",
            "icono": "bi bi-star", "grupo": "Extra", "orden": 1, "en_sidebar": 1, "publico": 0, "estado": 1
        }
        mock_insert.return_value = 10
        data = {"nombre": "nuevo_mod", "titulo": "Nuevo", "ruta": "/admin/nuevo", "grupo": "Extra"}
        res = model.ejecutar("create", data)
        assert res == 10
        mock_insert.assert_called_once()

    @patch.object(ModuloModel, "update")
    @patch.object(ModuloModel, "_get_by_nombre", return_value={"id": 5, "estado": 0})
    @patch.object(ModuloModel, "_validate")
    def test_create_reactivates_inactive_module(self, mock_validate, mock_get_by_name, mock_update, model):
        mock_validate.return_value = {
            "nombre": "mod_inactivo", "titulo": "Reactivado", "descripcion": "", "ruta": "/admin/reactivado",
            "icono": "bi bi-app", "grupo": "General", "orden": 2, "en_sidebar": 1, "publico": 0, "estado": 1
        }
        mock_update.return_value = 1
        data = {"nombre": "mod_inactivo", "titulo": "Reactivado", "ruta": "/admin/reactivado", "grupo": "General"}
        res = model.ejecutar("create", data)
        assert res == 1
        mock_update.assert_called_once()

    @patch.object(ModuloModel, "update")
    @patch.object(ModuloModel, "_validate")
    def test_update_modulo_success(self, mock_validate, mock_update, model):
        mock_validate.return_value = {
            "nombre": "mod_actualizado", "titulo": "Mod", "descripcion": None, "ruta": "/admin/mod",
            "icono": "bi bi-app", "grupo": "General", "orden": 0, "en_sidebar": 1, "publico": 0, "estado": 1
        }
        mock_update.return_value = 1
        data = {"nombre": "mod_actualizado", "titulo": "Mod", "ruta": "/admin/mod", "grupo": "General"}
        res = model.ejecutar("update_modulo", 4, data)
        assert res == 1
        mock_update.assert_called_once()

    @patch.object(ModuloModel, "update")
    @patch.object(ModuloModel, "_get_by_id")
    def test_soft_delete(self, mock_get_by_id, mock_update, model):
        # Inexistente
        mock_get_by_id.return_value = None
        assert model.ejecutar("soft_delete", 999) is None

        # Existente
        mock_get_by_id.return_value = {"id": 1, "nombre": "clientes"}
        mock_update.return_value = 1
        assert model.ejecutar("soft_delete", 1) == 0

    @patch.object(ModuloModel, "update")
    def test_reactivar(self, mock_update, model):
        mock_update.return_value = 1
        res = model.ejecutar("reactivar", 2)
        assert res == 1
        mock_update.assert_called_once_with(
            "mantenimiento", "UPDATE modulos SET estado_modulo = 1 WHERE id_modulo = %s", (2,)
        )

    @patch.object(ModuloModel, "fetch_one")
    def test_nombre_exists_with_and_without_exclude(self, mock_fetch_one, model):
        mock_fetch_one.return_value = {"id_modulo": 1}
        assert model.ejecutar("nombre_exists", "clientes", exclude_id=2) is True
        query = mock_fetch_one.call_args[0][1]
        assert "AND id_modulo != %s" in query

        mock_fetch_one.return_value = None
        assert model.ejecutar("nombre_exists", "inexistente") is False

    @patch.object(ModuloModel, "fetch_one")
    def test_ruta_exists_with_and_without_exclude(self, mock_fetch_one, model):
        mock_fetch_one.return_value = {"id_modulo": 1}
        assert model.ejecutar("ruta_exists", "/admin/clientes", exclude_id=5) is True
        query = mock_fetch_one.call_args[0][1]
        assert "AND id_modulo != %s" in query

        mock_fetch_one.return_value = None
        assert model.ejecutar("ruta_exists", "/ruta/libre") is False

    def test_ejecutar_invalid_action(self, model):
        with pytest.raises(ValueError) as exc_info:
            model.ejecutar("accion_inexistente")

        assert "Accion no permitida" in str(exc_info.value)
