import pytest
import json
from unittest.mock import patch, MagicMock
from model.vehicle_model import VehicleModel
from config.validation import ValidationError


@pytest.fixture
def model():
    return VehicleModel()


class TestVehicleModelProperties:

    def test_property_setters_strip_and_uppercase_plate(self, model):
        model.placa = "  ab123cd  "
        model.marca = "  Toyota  "
        model.modelo = "  Corolla  "

        assert model.placa == "AB123CD"
        assert model.marca == "Toyota"
        assert model.modelo == "Corolla"

    def test_property_setters_none(self, model):
        model.placa = None
        model.marca = None
        model.modelo = None

        assert model.placa == ""
        assert model.marca is None
        assert model.modelo is None


class TestVehicleModelValidation:

    @pytest.mark.parametrize("raw_placa, expected_placa", [
        ("abc-1234", "ABC-1234"),
        ("  x789yy  ", "X789YY"),
        ("A12B34", "A12B34"),
    ])
    def test_plate_normalization(self, model, raw_placa, expected_placa):
        assert model._plate(raw_placa) == expected_placa

    @pytest.mark.parametrize("marca, modelo, anio, placa, combustible, km", [
        ("Toyota", "Yaris", 2022, "ABC-1234", "gasolina", 45000),
        ("Chevrolet", "Aveo", 2011, "X789YY", "gasoil", 120000),
        ("Ford", "Explorer", 2018, "AA123BB", "otro", 85000),
    ])
    def test_validate_valid_vehicle(self, model, marca, modelo, anio, placa, combustible, km):
        data = {
            "marca": marca,
            "modelo": modelo,
            "anio": anio,
            "placa": placa,
            "tipo_combustible": combustible,
            "kilometraje_actual": km
        }
        clean = model.ejecutar("validate", data)
        assert clean["marca"] == marca
        assert clean["modelo"] == modelo
        assert clean["placa"] == placa.upper()
        assert clean["tipo_combustible"] == combustible

    @pytest.mark.parametrize("invalid_placa", [
        "AB*12",
        "123",
        "PLACA CON ESPACIOS",
        "",
    ])
    def test_validate_invalid_plate(self, model, invalid_placa):
        data = {
            "marca": "Toyota",
            "modelo": "Corolla",
            "placa": invalid_placa
        }
        with pytest.raises(ValidationError) as exc_info:
            model.ejecutar("validate", data)
        assert "placa" in exc_info.value.errors

    @pytest.mark.parametrize("invalid_field, bad_value", [
        ("marca", ""),
        ("modelo", ""),
        ("tipo_combustible", "nuclear"),
    ])
    def test_validate_invalid_fields(self, model, invalid_field, bad_value):
        data = {
            "marca": "Toyota",
            "modelo": "Corolla",
            "placa": "ABC-1234",
            invalid_field: bad_value
        }
        with pytest.raises(ValidationError) as exc_info:
            model.ejecutar("validate", data)
        assert invalid_field in exc_info.value.errors


class TestVehicleModelDatabaseOperations:

    def test_get_all(self, model):
        with patch.object(VehicleModel, "fetch_all", return_value=[
            {"id": "ABC-1234", "placa": "ABC-1234", "marca": "Toyota", "modelo": "Corolla"}
        ]) as mock_fetch:
            vehicles = model.ejecutar("get_all")
            assert len(vehicles) == 1
            assert vehicles[0]["placa"] == "ABC-1234"
            mock_fetch.assert_called_once()

    def test_get_by_id(self, model):
        with patch.object(VehicleModel, "fetch_one", return_value={"id": "ABC-1234", "placa": "ABC-1234", "marca": "Toyota"}) as mock_fetch:
            v = model.ejecutar("get_by_id", "abc-1234")
            assert v["placa"] == "ABC-1234"
            mock_fetch.assert_called_once()

    def test_get_by_cliente(self, model):
        with patch.object(VehicleModel, "fetch_all", return_value=[{"placa": "ABC-1234"}]):
            res = model.ejecutar("get_by_cliente", "V-12345678")
            assert len(res) == 1

    def test_get_by_placa(self, model):
        with patch.object(VehicleModel, "fetch_one", return_value={"placa": "ABC-1234"}):
            res = model.ejecutar("get_by_placa", "abc-1234")
            assert res["placa"] == "ABC-1234"

    def test_create_vehicle_success(self, model):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = [None, None]
        mock_conn.cursor.return_value = mock_cursor

        data = {
            "marca": "Toyota",
            "modelo": "Corolla",
            "anio": 2020,
            "placa": "ABC-1234",
            "cliente_cedula": "V-12345678"
        }
        with patch.object(VehicleModel, "_owner_has_active_placa", return_value=False), \
             patch.object(VehicleModel, "con_transalca", return_value=mock_conn):
            res = model.ejecutar("create", data)
            assert res == "ABC-1234"
            mock_conn.commit.assert_called_once()

    def test_create_vehicle_duplicate_plate_for_owner(self, model):
        data = {
            "marca": "Toyota",
            "modelo": "Corolla",
            "placa": "ABC-1234",
            "cliente_cedula": "V-12345678"
        }
        with patch.object(VehicleModel, "_owner_has_active_placa", return_value=True):
            with pytest.raises(ValidationError) as exc:
                model.ejecutar("create", data)
            assert "placa" in exc.value.errors

    def test_update_vehicle_success(self, model):
        data = {
            "marca": "Toyota",
            "modelo": "Corolla",
            "placa": "ABC-1234"
        }
        with patch.object(VehicleModel, "_placa_exists", return_value=False), \
             patch.object(VehicleModel, "update", return_value=1) as mock_update:
            res = model.ejecutar("update_vehicle", "ABC-1234", data)
            assert res == 1
            mock_update.assert_called_once()

    def test_update_vehicle_duplicate_plate(self, model):
        data = {
            "marca": "Toyota",
            "modelo": "Corolla",
            "placa": "REPETIDA"
        }
        with patch.object(VehicleModel, "_placa_exists", return_value=True):
            with pytest.raises(ValidationError) as exc:
                model.ejecutar("update_vehicle", "ABC-1234", data)
            assert "placa" in exc.value.errors

    def test_update_kilometraje_success(self, model):
        with patch.object(VehicleModel, "fetch_one", return_value={"placa_vehiculo": "ABC-1234", "kilometraje_actual": 50000}), \
             patch.object(VehicleModel, "update", return_value=1) as mock_update, \
             patch.object(VehicleModel, "insert", return_value=1):
            result = model.ejecutar("update_kilometraje", "ABC-1234", 55000)
            assert result is True
            mock_update.assert_called_once()

    def test_update_kilometraje_lower_than_current_fails(self, model):
        with patch.object(VehicleModel, "fetch_one", return_value={"placa_vehiculo": "ABC-1234", "kilometraje_actual": 50000}):
            result = model.ejecutar("update_kilometraje", "ABC-1234", 40000)
            assert result is False

    def test_update_carnet_image(self, model):
        with patch.object(VehicleModel, "update", return_value=1):
            assert model.ejecutar("update_carnet_image", "ABC-1234", "carnet.png") == 1

    def test_soft_delete(self, model):
        with patch.object(VehicleModel, "update", return_value=1) as mock_update:
            result = model.ejecutar("soft_delete", "ABC-1234")
            assert result == 1
            mock_update.assert_called_once()

    def test_soft_delete_relationship(self, model):
        with patch.object(VehicleModel, "update", return_value=1):
            res = model.ejecutar("soft_delete_relationship", "V-12345678", "ABC-1234")
            assert res == 1

    def test_get_clients_by_vehicle(self, model):
        with patch.object(VehicleModel, "fetch_all", return_value=[{"cliente_cedula": "V-12345678"}]):
            res = model.ejecutar("get_clients_by_vehicle", "ABC-1234")
            assert res == ["V-12345678"]

    @pytest.mark.parametrize("found, expected", [
        ({"placa_vehiculo": "ABC-1234"}, True),
        (None, False),
    ])
    def test_placa_exists(self, model, found, expected):
        with patch.object(VehicleModel, "fetch_one", return_value=found):
            assert model.ejecutar("placa_exists", "ABC-1234") is expected

    def test_cauchos_operations(self, model):
        fake_cauchos = [{"id": 1, "marca_caucho": "Goodyear", "medida": "195/65R15"}]
        with patch.object(VehicleModel, "fetch_one", return_value={"cauchos_vehiculo": json.dumps(fake_cauchos)}), \
             patch.object(VehicleModel, "update", return_value=1):
            items = model.ejecutar("get_cauchos", "ABC-1234")
            assert len(items) == 1
            assert items[0]["marca_caucho"] == "Goodyear"

            new_id = model.ejecutar("add_caucho", "ABC-1234", {"marca_caucho": "Pirelli", "medida": "195/65R15"})
            assert new_id == 2

    def test_history_operations(self, model):
        with patch.object(VehicleModel, "fetch_all", return_value=[{"id": 1, "descripcion": "Cambio de aceite"}]):
            hist = model.ejecutar("get_history", "ABC-1234")
            assert len(hist) == 1

        with patch.object(VehicleModel, "fetch_one", return_value={"placa_vehiculo": "ABC-1234"}), \
             patch.object(VehicleModel, "insert", return_value=10):
            entry_id = model.ejecutar("add_history_entry", "ABC-1234", {"descripcion": "Rotación"})
            assert entry_id == 10

    def test_reactivar(self, model):
        with patch.object(VehicleModel, "update", return_value=1):
            assert model.ejecutar("reactivar", "ABC-1234") == 1

    def test_ejecutar_invalid_action(self, model):
        with pytest.raises(ValueError) as exc_info:
            model.ejecutar("accion_inexistente")
        assert "Accion no permitida" in str(exc_info.value)
