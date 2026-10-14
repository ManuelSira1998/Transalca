import pytest
from unittest.mock import patch, MagicMock
from model.category_model import CategoryModel
from config.validation import ValidationError


@pytest.fixture
def model():
    """Fixture para obtener una instancia limpia de CategoryModel."""
    return CategoryModel()


class TestCategoryModelHelpersAndValidation:
    """Pruebas unitarias con Data Provider (@pytest.mark.parametrize) para propiedades y validaciones de categorias."""

    # DATA PROVIDER: Propiedades del modelo de categoria
    @pytest.mark.parametrize("prop_name, input_val, expected_val", [
        ("nombre", "  Lubricantes  ", "Lubricantes"),
        ("descripcion", "  Aceites de motor  ", "Aceites de motor"),
    ])
    def test_category_properties_data_provider(self, model, prop_name, input_val, expected_val):
        setattr(model, prop_name, input_val)
        assert getattr(model, prop_name) == expected_val

    def test_property_setters_none(self, model):
        model.nombre = None
        model.descripcion = None
        assert model.nombre is None
        assert model.descripcion is None

    # DATA PROVIDER: Validaciones de campos de categoria
    @pytest.mark.parametrize("data, is_valid, expected_error_field", [
        # Caso valido
        ({"nombre": "Frenos", "descripcion": "Sistemas de frenado"}, True, None),
        # Nombre muy corto (< 3 chars)
        ({"nombre": "Fr", "descripcion": "Sistemas de frenado"}, False, "nombre"),
        # Nombre vacio
        ({"nombre": "", "descripcion": "Sistemas de frenado"}, False, "nombre"),
        # Nombre excesivamente largo (> 30 chars)
        ({"nombre": "A" * 35, "descripcion": "Valido"}, False, "nombre"),
        # Descripcion excesivamente larga (> 150 chars)
        ({"nombre": "Frenos", "descripcion": "D" * 155}, False, "descripcion"),
    ])
    def test_validate_data_provider(self, model, data, is_valid, expected_error_field):
        if is_valid:
            clean = model._validate(data)
            assert clean["nombre"] == data["nombre"]
        else:
            with pytest.raises(ValidationError) as exc_info:
                model._validate(data)
            assert expected_error_field in exc_info.value.errors


class TestCategoryModelDatabaseOperations:
    """Pruebas unitarias para consultas y operaciones CRUD de categorias."""

    @patch.object(CategoryModel, "fetch_all")
    def test_get_all(self, mock_fetch_all, model):
        mock_fetch_all.return_value = [
            {"nombre": "Lubricantes", "descripcion": "Aceites", "total_productos": 10}
        ]
        result = model.ejecutar("get_all")

        assert len(result) == 1
        assert result[0]["nombre"] == "Lubricantes"

    @patch.object(CategoryModel, "fetch_all")
    def test_get_active(self, mock_fetch_all, model):
        mock_fetch_all.return_value = [
            {"nombre": "Frenos", "descripcion": "Pastillas"}
        ]
        result = model.ejecutar("get_active")

        assert len(result) == 1
        assert result[0]["nombre"] == "Frenos"

    @patch.object(CategoryModel, "fetch_one")
    def test_get_by_nombre(self, mock_fetch_one, model):
        mock_fetch_one.return_value = {"nombre": "Motor", "descripcion": "Partes de motor"}
        result = model.ejecutar("get_by_nombre", "Motor")

        assert result["nombre"] == "Motor"

    @patch.object(CategoryModel, "insert", return_value="Suspension")
    @patch.object(CategoryModel, "_get_by_nombre", return_value=None)
    @patch.object(CategoryModel, "_validate")
    def test_create_new_category(self, mock_validate, mock_get_by_nom, mock_insert, model):
        mock_validate.return_value = {"nombre": "Suspension", "descripcion": "Amortiguadores"}
        nombre = model.ejecutar("create", {"nombre": "Suspension"})

        assert nombre == "Suspension"
        mock_insert.assert_called_once()

    @patch.object(CategoryModel, "update", return_value=1)
    @patch.object(CategoryModel, "_get_by_nombre", return_value={"nombre": "Suspension", "estado": 0})
    @patch.object(CategoryModel, "_validate")
    def test_create_reactivate_inactive_category(self, mock_validate, mock_get, mock_update, model):
        mock_validate.return_value = {"nombre": "Suspension", "descripcion": "Amortiguadores"}
        nombre = model.ejecutar("create", {"nombre": "Suspension"})

        assert nombre == "Suspension"
        mock_update.assert_called_once()

    @patch.object(CategoryModel, "_get_by_nombre", return_value={"nombre": "Suspension", "estado": 1})
    @patch.object(CategoryModel, "_validate", return_value={"nombre": "Suspension"})
    def test_create_already_active_raises_error(self, mock_validate, mock_get, model):
        with pytest.raises(ValidationError) as exc_info:
            model.ejecutar("create", {"nombre": "Suspension"})

        assert "nombre" in exc_info.value.errors

    def test_update_category_empty_old_nombre_fails(self, model):
        with pytest.raises(ValidationError) as exc_info:
            model.ejecutar("update_category", "", {"nombre": "Nuevo"})
        assert "old_nombre" in exc_info.value.errors

    @patch.object(CategoryModel, "update", return_value=1)
    @patch.object(CategoryModel, "_nombre_exists", return_value=False)
    @patch.object(CategoryModel, "_validate")
    def test_update_category_success(self, mock_validate, mock_exists, mock_update, model):
        mock_validate.return_value = {"nombre": "Suspension Modificada", "descripcion": "Desc"}
        res = model.ejecutar("update_category", "Suspension", {"nombre": "Suspension Modificada"})

        assert res == 1
        mock_update.assert_called_once()

    @patch.object(CategoryModel, "_nombre_exists", return_value=True)
    @patch.object(CategoryModel, "_validate", return_value={"nombre": "Frenos"})
    def test_update_category_duplicate_name_fails(self, mock_validate, mock_exists, model):
        with pytest.raises(ValidationError) as exc_info:
            model.ejecutar("update_category", "Suspension", {"nombre": "Frenos"})

        assert "nombre" in exc_info.value.errors

    @patch.object(CategoryModel, "update", return_value=1)
    def test_soft_delete_and_toggle(self, mock_update, model):
        res = model.ejecutar("soft_delete", "Frenos")
        assert res == 1

        toggle_res = model.ejecutar("toggle_estado", "Frenos")
        assert toggle_res == 1

    @patch.object(CategoryModel, "fetch_one")
    def test_nombre_exists_with_and_without_exclude(self, mock_fetch_one, model):
        mock_fetch_one.return_value = {"nombre_categoria": "Frenos"}
        assert model.ejecutar("nombre_exists", "Frenos", exclude_nombre="Aceites") is True
        query = mock_fetch_one.call_args[0][1]
        assert "AND nombre_categoria != %s" in query

        mock_fetch_one.return_value = None
        assert model.ejecutar("nombre_exists", "NoExiste") is False

    @patch.object(CategoryModel, "update", return_value=1)
    def test_reactivar(self, mock_update, model):
        res = model.ejecutar("reactivar", "Frenos")
        assert res == 1

    def test_ejecutar_invalid_action(self, model):
        with pytest.raises(ValueError) as exc_info:
            model.ejecutar("accion_inexistente")

        assert "Accion no permitida" in str(exc_info.value)
