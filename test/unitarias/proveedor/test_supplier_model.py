import pytest
from unittest.mock import patch
from model.supplier_model import SupplierModel
from config.validation import ValidationError


@pytest.fixture
def model():
    """Fixture para obtener una instancia limpia de SupplierModel."""
    return SupplierModel()


class TestSupplierModelProperties:
    """Pruebas unitarias para getters y setters del modelo de proveedor."""

    def test_property_setters_strip_whitespace(self, model):
        model.rif = "  J-123456789  "
        model.nombre = "  Distribuidora Automotriz C.A.  "
        model.telefono = "  04141234567  "
        model.email = "  contacto@distribuidora.com  "
        model.direccion = "  Av. Las Industrias  "

        assert model.rif == "J-123456789"
        assert model.nombre == "Distribuidora Automotriz C.A."
        assert model.telefono == "04141234567"
        assert model.email == "contacto@distribuidora.com"
        assert model.direccion == "Av. Las Industrias"

    def test_property_setters_none(self, model):
        model.rif = None
        model.nombre = None
        model.telefono = None
        model.email = None
        model.direccion = None

        assert model.rif is None
        assert model.nombre is None
        assert model.telefono is None
        assert model.email is None
        assert model.direccion is None


class TestSupplierModelValidation:
    """Pruebas unitarias con Data Provider (@pytest.mark.parametrize) para validaciones de proveedor."""

    # DATA PROVIDER: Pruebas con formatos de RIF válidos
    @pytest.mark.parametrize("input_rif, expected_rif, expected_prefijo", [
        ("J-123456789", "J-12345678-9", "J"),
        ("G-987654321", "G-98765432-1", "G"),
        ("V-123456789", "V-12345678-9", "V"),
        ("j 123456789", "J-12345678-9", "J"),
        ("J123456789", "J-12345678-9", "J"),
    ])
    def test_validate_valid_rif_data_provider(self, model, input_rif, expected_rif, expected_prefijo):
        data = {
            "rif": input_rif,
            "nombre": "Proveedor Repuestos C.A.",
            "telefono": "04121234567",
            "email": "ventas@proveedor.com"
        }
        clean = model._validate(data)
        assert clean["rif"] == expected_rif
        assert clean["rif_prefijo"] == expected_prefijo

    # DATA PROVIDER: Pruebas con formatos de RIF inválidos
    @pytest.mark.parametrize("invalid_rif", [
        "XYZ-99999",
        "123",            # RIF muy corto
        "J-ABCDEFGHI",    # Caracteres no numéricos
        "",               # Vacío
    ])
    def test_validate_invalid_rif_data_provider(self, model, invalid_rif):
        data = {
            "rif": invalid_rif,
            "nombre": "Proveedor Repuestos C.A.",
            "telefono": "04121234567"
        }
        with pytest.raises(ValidationError) as exc_info:
            model._validate(data)
        assert "rif" in exc_info.value.errors

    # DATA PROVIDER: Validación de nombres de proveedor
    @pytest.mark.parametrize("invalid_nombre", [
        "",
        "   ",
        "AB",             # Menor a 3 caracteres
        "A" * 151,        # Mayor a 150 caracteres
    ])
    def test_validate_invalid_name_data_provider(self, model, invalid_nombre):
        data = {
            "rif": "J-123456789",
            "nombre": invalid_nombre
        }
        with pytest.raises(ValidationError) as exc_info:
            model._validate(data)
        assert "nombre" in exc_info.value.errors

    def test_validate_direccion_only_spaces_fails(self, model):
        data = {
            "rif": "J-123456789",
            "nombre": "Proveedor Válido",
            "direccion": "   "
        }
        with pytest.raises(ValidationError) as exc_info:
            model._validate(data)
        assert "direccion" in exc_info.value.errors


class TestSupplierModelDatabaseOperations:
    """Pruebas unitarias con mocks de base de datos para operaciones CRUD de proveedores."""

    @patch.object(SupplierModel, "fetch_all")
    def test_get_all(self, mock_fetch_all, model):
        mock_fetch_all.return_value = [
            {"rif": "J-12345678-9", "nombre": "Proveedor A", "telefono": "04141234567", "total_ordenes": 5}
        ]
        result = model.ejecutar("get_all")

        assert len(result) == 1
        assert result[0]["nombre"] == "Proveedor A"
        mock_fetch_all.assert_called_once()

    @patch.object(SupplierModel, "fetch_all")
    def test_get_active(self, mock_fetch_all, model):
        mock_fetch_all.return_value = [{"rif": "J-12345678-9", "nombre": "Proveedor A"}]
        res = model.ejecutar("get_active")
        assert len(res) == 1
        mock_fetch_all.assert_called_once()

    @patch.object(SupplierModel, "fetch_one")
    def test_get_by_rif(self, mock_fetch_one, model):
        mock_fetch_one.return_value = {"rif": "J-12345678-9", "nombre": "Proveedor A"}
        result = model.ejecutar("get_by_rif", "J-12345678-9")

        assert result["rif"] == "J-12345678-9"
        mock_fetch_one.assert_called_once()

    @patch.object(SupplierModel, "email_exists_globally", return_value=False)
    @patch.object(SupplierModel, "insert")
    @patch.object(SupplierModel, "_get_by_rif", return_value=None)
    def test_create_new_supplier_success(self, mock_get_by_rif, mock_insert, mock_email, model):
        mock_insert.return_value = 1
        data = {
            "rif": "J-123456789",
            "nombre": "Distribuidora Repuestos",
            "telefono": "04141234567",
            "email": "ventas@distribuidora.com"
        }
        res = model.ejecutar("create", data)
        assert res == "J-12345678-9"
        mock_insert.assert_called_once()

    @patch.object(SupplierModel, "email_exists_globally", return_value=False)
    @patch.object(SupplierModel, "update")
    @patch.object(SupplierModel, "_get_by_rif", return_value={"rif": "J-12345678-9", "estado": 0})
    def test_create_reactivates_inactive_supplier(self, mock_get_by_rif, mock_update, mock_email, model):
        mock_update.return_value = 1
        data = {
            "rif": "J-123456789",
            "nombre": "Distribuidora Repuestos",
            "telefono": "04141234567"
        }
        res = model.ejecutar("create", data)
        assert res == "J-12345678-9"
        mock_update.assert_called_once()

    @patch.object(SupplierModel, "_get_by_rif")
    def test_create_duplicate_active_supplier_raises_error(self, mock_get_by_rif, model):
        mock_get_by_rif.return_value = {"rif": "J-12345678-9", "estado": 1}

        data = {
            "rif": "J-123456789",
            "nombre": "Distribuidora Repuestos"
        }
        with pytest.raises(ValidationError) as exc_info:
            model.ejecutar("create", data)

        assert "rif" in exc_info.value.errors

    def test_update_supplier_empty_old_rif_fails(self, model):
        data = {"rif": "J-123456789", "nombre": "Nuevo"}
        with pytest.raises(ValidationError) as exc_info:
            model.ejecutar("update_supplier", "", data)
        assert "old_rif" in exc_info.value.errors

    @patch.object(SupplierModel, "_rif_exists", return_value=True)
    def test_update_supplier_duplicate_rif_fails(self, mock_rif_exists, model):
        data = {"rif": "J-999999999", "nombre": "Nuevo"}
        with pytest.raises(ValidationError) as exc_info:
            model.ejecutar("update_supplier", "J-12345678-9", data)
        assert "rif" in exc_info.value.errors

    @patch.object(SupplierModel, "email_exists_globally", return_value=False)
    @patch.object(SupplierModel, "_rif_exists", return_value=False)
    @patch.object(SupplierModel, "update")
    def test_update_supplier_success(self, mock_update, mock_rif_exists, mock_email, model):
        mock_update.return_value = 1
        data = {
            "rif": "J-123456789",
            "nombre": "Nombre Modificado",
            "telefono": "04120000000",
            "email": "nuevo@proveedor.com"
        }
        res = model.ejecutar("update_supplier", "J-12345678-9", data)
        assert res == 1
        mock_update.assert_called_once()

    @patch.object(SupplierModel, "update")
    def test_soft_delete_and_toggle(self, mock_update, model):
        mock_update.return_value = 1
        assert model.ejecutar("soft_delete", "J-12345678-9") == 1
        assert model.ejecutar("toggle_estado", "J-12345678-9") == 1

    @patch.object(SupplierModel, "update")
    def test_reactivar(self, mock_update, model):
        mock_update.return_value = 1
        assert model.ejecutar("reactivar", "J-12345678-9") == 1
        mock_update.assert_called_once_with(
            "transalca", "UPDATE proveedores SET estado = 1 WHERE rif_proveedor = %s", ("J-12345678-9",)
        )

    @patch.object(SupplierModel, "fetch_one")
    def test_rif_exists_with_and_without_exclude(self, mock_fetch_one, model):
        mock_fetch_one.return_value = {"rif_proveedor": "J-12345678-9"}
        assert model.ejecutar("rif_exists", "J-12345678-9", exclude_rif="J-99999999-9") is True
        query = mock_fetch_one.call_args[0][1]
        assert "AND rif_proveedor != %s" in query

        mock_fetch_one.return_value = None
        assert model.ejecutar("rif_exists", "J-00000000-0") is False

    @patch.object(SupplierModel, "fetch_one")
    def test_email_exists_globally(self, mock_fetch_one, model):
        mock_fetch_one.return_value = {"id": 1}
        assert model.ejecutar("email_exists_globally", "admin@transalca.com") is True

        mock_fetch_one.return_value = None
        assert model.ejecutar("email_exists_globally", "libre@transalca.com") is False

    def test_ejecutar_invalid_action(self, model):
        with pytest.raises(ValueError) as exc_info:
            model.ejecutar("accion_inexistente")

        assert "Accion no permitida" in str(exc_info.value)
