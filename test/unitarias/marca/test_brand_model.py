import pytest
from unittest.mock import patch, MagicMock
from model.brand_model import BrandModel
from config.validation import ValidationError


@pytest.fixture
def model():
    """Fixture para obtener una instancia limpia de BrandModel."""
    return BrandModel()


class TestBrandModelHelpersAndValidation:
    """Pruebas unitarias con Data Provider (@pytest.mark.parametrize) para propiedades y validaciones de marcas."""

    # DATA PROVIDER: Propiedades del modelo de marca
    @pytest.mark.parametrize("prop_name, input_val, expected_val", [
        ("nombre", "  Bosch  ", "Bosch"),
        ("descripcion", "  Tecnologia alemana  ", "Tecnologia alemana"),
    ])
    def test_brand_properties_data_provider(self, model, prop_name, input_val, expected_val):
        setattr(model, prop_name, input_val)
        assert getattr(model, prop_name) == expected_val

    def test_property_setters_none(self, model):
        model.nombre = None
        model.descripcion = None
        assert model.nombre is None
        assert model.descripcion is None

    # DATA PROVIDER: Validaciones de campos de marca
    @pytest.mark.parametrize("data, is_valid, expected_error_field", [
        # Caso valido
        ({"nombre": "Bosch", "descripcion": "Repuestos automotrices"}, True, None),
        # Nombre muy corto (< 2 chars)
        ({"nombre": "B", "descripcion": "Repuestos automotrices"}, False, "nombre"),
        # Nombre vacio
        ({"nombre": "", "descripcion": "Repuestos automotrices"}, False, "nombre"),
        # Nombre muy largo (> 30 chars)
        ({"nombre": "M" * 35, "descripcion": "Valido"}, False, "nombre"),
        # Descripcion muy larga (> 150 chars)
        ({"nombre": "Monroe", "descripcion": "D" * 155}, False, "descripcion"),
    ])
    def test_validate_data_provider(self, model, data, is_valid, expected_error_field):
        if is_valid:
            clean = model._validate(data)
            assert clean["nombre"] == data["nombre"]
        else:
            with pytest.raises(ValidationError) as exc_info:
                model._validate(data)
            assert expected_error_field in exc_info.value.errors


class TestBrandModelDatabaseOperations:
    """Pruebas unitarias para consultas y operaciones CRUD de marcas."""

    @patch.object(BrandModel, "fetch_all")
    def test_get_all(self, mock_fetch_all, model):
        mock_fetch_all.return_value = [
            {"nombre": "Bosch", "descripcion": "Repuestos", "total_productos": 15}
        ]
        result = model.ejecutar("get_all")

        assert len(result) == 1
        assert result[0]["nombre"] == "Bosch"

    @patch.object(BrandModel, "fetch_all")
    def test_get_active(self, mock_fetch_all, model):
        mock_fetch_all.return_value = [
            {"nombre": "Castrol", "descripcion": "Lubricantes"}
        ]
        result = model.ejecutar("get_active")

        assert len(result) == 1
        assert result[0]["nombre"] == "Castrol"

    @patch.object(BrandModel, "fetch_one")
    def test_get_by_nombre(self, mock_fetch_one, model):
        mock_fetch_one.return_value = {"nombre": "Denso", "descripcion": "Bujias"}
        result = model.ejecutar("get_by_nombre", "Denso")

        assert result["nombre"] == "Denso"

    @patch.object(BrandModel, "insert", return_value="Monroe")
    @patch.object(BrandModel, "_get_by_nombre", return_value=None)
    @patch.object(BrandModel, "_validate")
    def test_create_new_brand(self, mock_validate, mock_get_by_nom, mock_insert, model):
        mock_validate.return_value = {"nombre": "Monroe", "descripcion": "Amortiguadores"}
        nombre = model.ejecutar("create", {"nombre": "Monroe"})

        assert nombre == "Monroe"
        mock_insert.assert_called_once()

    @patch.object(BrandModel, "update", return_value=1)
    @patch.object(BrandModel, "_get_by_nombre", return_value={"nombre": "Monroe", "estado": 0})
    @patch.object(BrandModel, "_validate")
    def test_create_reactivate_inactive_brand(self, mock_validate, mock_get, mock_update, model):
        mock_validate.return_value = {"nombre": "Monroe", "descripcion": "Amortiguadores"}
        nombre = model.ejecutar("create", {"nombre": "Monroe"})

        assert nombre == "Monroe"
        mock_update.assert_called_once()

    @patch.object(BrandModel, "_get_by_nombre", return_value={"nombre": "Monroe", "estado": 1})
    @patch.object(BrandModel, "_validate", return_value={"nombre": "Monroe"})
    def test_create_already_active_raises_error(self, mock_validate, mock_get, model):
        with pytest.raises(ValidationError) as exc_info:
            model.ejecutar("create", {"nombre": "Monroe"})

        assert "nombre" in exc_info.value.errors

    def test_update_brand_empty_old_nombre_fails(self, model):
        with pytest.raises(ValidationError) as exc_info:
            model.ejecutar("update_brand", "", {"nombre": "Nuevo"})
        assert "old_nombre" in exc_info.value.errors

    @patch.object(BrandModel, "update", return_value=1)
    @patch.object(BrandModel, "_nombre_exists", return_value=False)
    @patch.object(BrandModel, "_validate")
    def test_update_brand_success(self, mock_validate, mock_exists, mock_update, model):
        mock_validate.return_value = {"nombre": "Monroe Actualizada", "descripcion": "Desc"}
        res = model.ejecutar("update_brand", "Monroe", {"nombre": "Monroe Actualizada"})

        assert res == 1
        mock_update.assert_called_once()

    @patch.object(BrandModel, "_nombre_exists", return_value=True)
    @patch.object(BrandModel, "_validate", return_value={"nombre": "Bosch"})
    def test_update_brand_duplicate_name_fails(self, mock_validate, mock_exists, model):
        with pytest.raises(ValidationError) as exc_info:
            model.ejecutar("update_brand", "Monroe", {"nombre": "Bosch"})

        assert "nombre" in exc_info.value.errors

    @patch.object(BrandModel, "update", return_value=1)
    def test_soft_delete_and_toggle(self, mock_update, model):
        res = model.ejecutar("soft_delete", "Bosch")
        assert res == 1

        toggle_res = model.ejecutar("toggle_estado", "Bosch")
        assert toggle_res == 1

    @patch.object(BrandModel, "fetch_one")
    def test_nombre_exists_with_and_without_exclude(self, mock_fetch_one, model):
        mock_fetch_one.return_value = {"nombre_marca": "Bosch"}
        assert model.ejecutar("nombre_exists", "Bosch", exclude_nombre="Denso") is True
        query = mock_fetch_one.call_args[0][1]
        assert "AND nombre_marca != %s" in query

        mock_fetch_one.return_value = None
        assert model.ejecutar("nombre_exists", "NoExiste") is False

    @patch.object(BrandModel, "update", return_value=1)
    def test_reactivar(self, mock_update, model):
        res = model.ejecutar("reactivar", "Bosch")
        assert res == 1

    def test_ejecutar_invalid_action(self, model):
        with pytest.raises(ValueError) as exc_info:
            model.ejecutar("accion_inexistente")

        assert "Accion no permitida" in str(exc_info.value)
