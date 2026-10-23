import pytest
from unittest.mock import MagicMock, patch
from model.company_model import CompanyModel
from config.validation import ValidationError


@pytest.fixture
def model():
    return CompanyModel()


class TestCompanyModelProperties:

    def test_property_setters_strip_whitespace(self, model):
        model.rif = "  J-123456789  "
        model.razon_social = "  Corporación Transalca C.A.  "
        model.telefono = "  02511234567  "
        model.email = "  contacto@transalca.com  "
        model.direccion = "  Zona Industrial II  "
        model.limite_credito = 5000.50
        model.dias_credito = 30

        assert model.rif == "J-123456789"
        assert model.razon_social == "Corporación Transalca C.A."
        assert model.telefono == "02511234567"
        assert model.email == "contacto@transalca.com"
        assert model.direccion == "Zona Industrial II"
        assert model.limite_credito == 5000.50
        assert model.dias_credito == 30

    def test_property_setters_none(self, model):
        model.rif = None
        model.razon_social = None
        model.limite_credito = None
        model.dias_credito = None

        assert model.rif is None
        assert model.razon_social is None
        assert model.limite_credito == 0.0
        assert model.dias_credito == 0


class TestCompanyModelValidation:

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
            "razon_social": "Inversiones Demo C.A.",
            "telefono": "04121234567",
            "email": "demo@empresa.com",
            "limite_credito": 1000,
            "dias_credito": 15
        }
        clean = model._validate(data, require_rif=True)
        assert clean["rif"] == expected_rif
        assert clean["rif_prefijo"] == expected_prefijo

    @pytest.mark.parametrize("invalid_rif", [
        "XYZ-12345",
        "123",
        "J-ABCDEFGHI",
        "",
    ])
    def test_validate_invalid_rif_data_provider(self, model, invalid_rif):
        data = {
            "rif": invalid_rif,
            "razon_social": "Inversiones Demo C.A.",
            "telefono": "04121234567"
        }
        with pytest.raises(ValidationError) as exc_info:
            model._validate(data, require_rif=True)
        assert "rif" in exc_info.value.errors

    @pytest.mark.parametrize("limite_credito, dias_credito, expected_error_field", [
        (-500, 15, "limite_credito"),
        (1000, -10, "dias_credito"),
        (1000, 400, "dias_credito"),
    ])
    def test_validate_credit_fields_data_provider(self, model, limite_credito, dias_credito, expected_error_field):
        data = {
            "rif": "J-123456789",
            "razon_social": "Inversiones Demo C.A.",
            "telefono": "04121234567",
            "limite_credito": limite_credito,
            "dias_credito": dias_credito
        }
        with pytest.raises(ValidationError) as exc_info:
            model._validate(data, require_rif=True)
        assert expected_error_field in exc_info.value.errors


class TestCompanyModelDatabaseOperations:

    @patch.object(CompanyModel, "fetch_all")
    def test_get_all(self, mock_fetch_all, model):
        mock_fetch_all.return_value = [
            {"rif": "J-123456789", "razon_social": "Transalca C.A.", "estado": 1}
        ]
        result = model.ejecutar("get_all")

        assert len(result) == 1
        assert result[0]["rif"] == "J-123456789"
        mock_fetch_all.assert_called_once()

    @patch.object(CompanyModel, "fetch_one")
    def test_get_by_rif(self, mock_fetch_one, model):
        mock_fetch_one.return_value = {"rif": "J-123456789", "razon_social": "Transalca C.A."}
        result = model.ejecutar("get_by_rif", "J-123456789")

        assert result["rif"] == "J-123456789"
        mock_fetch_one.assert_called_once()

    @patch.object(CompanyModel, "email_exists_globally", return_value=False)
    @patch.object(CompanyModel, "con_transalca")
    @patch.object(CompanyModel, "_get_by_rif", return_value=None)
    def test_create_new_company_success(self, mock_get_by_rif, mock_con, mock_email, model):
        mock_conn = MagicMock()
        mock_con.return_value = mock_conn
        with patch.object(CompanyModel, "insert", return_value=1):
            data = {
                "rif": "J-123456789",
                "razon_social": "Transalca C.A.",
                "telefono": "04121234567",
                "email": "contacto@transalca.com",
                "direccion": "Zona Industrial"
            }
            res = model.ejecutar("create", data)
            assert res["rif"] == "J-12345678-9"
            mock_conn.commit.assert_called_once()

    @patch.object(CompanyModel, "_get_by_rif")
    def test_create_duplicate_active_company_raises_error(self, mock_get_by_rif, model):
        mock_get_by_rif.return_value = {"rif": "J-12345678-9", "estado": 1}

        data = {
            "rif": "J-123456789",
            "razon_social": "Transalca C.A.",
            "telefono": "04121234567"
        }
        with pytest.raises(ValidationError) as exc_info:
            model.ejecutar("create", data)

        assert "rif" in exc_info.value.errors

    @patch.object(CompanyModel, "update")
    def test_soft_delete(self, mock_update, model):
        mock_update.return_value = 1
        result = model.ejecutar("soft_delete", "J-123456789")

        assert result == 1
        mock_update.assert_called_once()

    @patch.object(CompanyModel, "fetch_one")
    def test_get_stats(self, mock_fetch_one, model):
        mock_fetch_one.side_effect = [{"total": 12}, {"total": 10}]
        stats = model.ejecutar("get_stats")

        assert stats["total"] == 12
        assert stats["activos"] == 10

    @patch.object(CompanyModel, "fetch_all")
    def test_get_all_from_view(self, mock_fetch_all, model):
        mock_fetch_all.return_value = [
            {"rif": "J-12345678-9", "razon_social": "Transalca C.A.", "flota_count": 5, "estado_credito": "al_dia"}
        ]
        result = model.ejecutar("get_all_from_view")

        assert len(result) == 1
        assert result[0]["rif"] == "J-12345678-9"
        assert result[0]["flota_count"] == 5
        mock_fetch_all.assert_called_once()

    @patch.object(CompanyModel, "fetch_one")
    def test_get_from_view_by_rif(self, mock_fetch_one, model):
        mock_fetch_one.return_value = {
            "rif": "J-12345678-9",
            "razon_social": "Transalca C.A.",
            "estado_credito": "al_dia",
            "representantes_count": 2
        }
        result = model.ejecutar("get_from_view", "J-12345678-9")

        assert result["rif"] == "J-12345678-9"
        assert result["representantes_count"] == 2
        mock_fetch_one.assert_called_once()

    @patch.object(CompanyModel, "email_exists_globally", return_value=False)
    @patch.object(CompanyModel, "execute_query")
    def test_save_company_sp_success(self, mock_execute_query, mock_email_exists, model):
        data = {
            "rif": "J-123456789",
            "razon_social": "Transalca C.A.",
            "email": "contacto@transalca.com",
            "telefono": "04121234567",
            "direccion": "Zona Industrial",
            "sector": "Transporte",
            "limite_credito": 5000,
            "dias_credito": 30
        }
        result = model.ejecutar("save_company_sp", data)

        assert result["rif"] == "J-12345678-9"
        mock_execute_query.assert_called_once()
        args = mock_execute_query.call_args[0]
        assert args[0] == "transalca"
        assert "CALL sp_registrar_o_actualizar_empresa" in args[1]

    @patch.object(CompanyModel, "fetch_all")
    def test_get_fleet_and_orders(self, mock_fetch_all, model):
        mock_fetch_all.return_value = [{"placa": "ABC1234"}]
        fleet = model.ejecutar("get_fleet", "J-12345678-9")
        assert len(fleet) == 1

        mock_fetch_all.return_value = [{"id": 1, "total": 500}]
        orders = model.ejecutar("get_orders", "J-12345678-9")
        assert len(orders) == 1

    @patch.object(CompanyModel, "update")
    def test_toggle_representative_relation(self, mock_update, model):
        mock_update.return_value = 1
        res = model.ejecutar("toggle_representative_relation", 5, 0)
        assert res == 1

    @patch.object(CompanyModel, "fetch_one")
    def test_find_representative_by_cedula(self, mock_fetch_one, model):
        mock_fetch_one.return_value = {"id": 1, "empresa_rif": "J-12345678-9"}
        rep = model.ejecutar("find_representative_by_cedula", "V-10000000", exclude_id=2)
        assert rep["id"] == 1
        query = mock_fetch_one.call_args[0][1]
        assert "AND id_empresa_representante != %s" in query

    def test_ejecutar_invalid_action(self, model):
        with pytest.raises(ValueError) as exc_info:
            model.ejecutar("accion_inexistente")

        assert "Accion no permitida" in str(exc_info.value)
