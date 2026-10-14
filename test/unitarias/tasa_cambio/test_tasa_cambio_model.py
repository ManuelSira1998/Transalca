import pytest
from unittest.mock import patch, MagicMock
from datetime import date
from model.tasa_cambio_model import TasaCambioModel
from config.validation import ValidationError


@pytest.fixture
def model():
    """Instancia del modelo de tasa de cambio para pruebas."""
    return TasaCambioModel()


class TestTasaCambioModelProperties:
    """Pruebas unitarias para getters y setters del modelo de tasa de cambio."""

    def test_property_setters_strip_and_convert(self, model):
        model.fecha = "  2026-08-22  "
        model.monto = "36.50"
        model.fuente = "  BCV Oficial  "

        assert model.fecha == "2026-08-22"
        assert model.monto == 36.50
        assert model.fuente == "BCV Oficial"

    def test_property_setters_none(self, model):
        model.fecha = None
        model.fuente = None

        assert model.fecha is None
        assert model.fuente is None


class TestTasaCambioModelValidation:
    """Pruebas unitarias con Data Provider (@pytest.mark.parametrize) para validaciones de tasa de cambio."""

    @pytest.mark.parametrize("monto_valido, fecha_valida, fuente_valida", [
        (36.50, "2026-08-22", "BCV Oficial"),
        ("40.00", "2026-01-01", "Paralelo"),
        (1, "2026-12-31", "Banco Central"),
    ])
    def test_validate_valid_tasa(self, model, monto_valido, fecha_valida, fuente_valida):
        data = {
            "monto": monto_valido,
            "fecha": fecha_valida,
            "fuente": fuente_valida
        }
        clean = model._validate(data, require_fecha=True)
        assert clean["monto"] == float(monto_valido)
        assert clean["fecha"] == fecha_valida
        assert clean["fuente"] == fuente_valida.strip()

    @pytest.mark.parametrize("invalid_monto", [
        0,              # Cero
        -5.5,           # Negativo
        "no_numerico",  # Texto
    ])
    def test_validate_invalid_monto(self, model, invalid_monto):
        data = {
            "monto": invalid_monto,
            "fecha": "2026-08-22",
            "fuente": "BCV"
        }
        with pytest.raises(ValidationError) as exc_info:
            model._validate(data, require_fecha=True)
        assert "monto" in exc_info.value.errors

    @pytest.mark.parametrize("invalid_fecha", [
        "22-08-2026",      # DD-MM-YYYY
        "2026/08/22",      # Con slashes
        "fecha_invalida",  # Texto
        "",                # Vacía cuando es requerida
    ])
    def test_validate_invalid_fecha(self, model, invalid_fecha):
        data = {
            "monto": 36.5,
            "fecha": invalid_fecha,
            "fuente": "BCV"
        }
        with pytest.raises(ValidationError) as exc_info:
            model._validate(data, require_fecha=True)
        assert "fecha" in exc_info.value.errors

    @pytest.mark.parametrize("invalid_fuente", [
        "",
        " ",
        "A",  # Menor a 2 caracteres
    ])
    def test_validate_invalid_fuente(self, model, invalid_fuente):
        data = {
            "monto": 36.5,
            "fecha": "2026-08-22",
            "fuente": invalid_fuente
        }
        with pytest.raises(ValidationError) as exc_info:
            model._validate(data, require_fecha=True)
        assert "fuente" in exc_info.value.errors


class TestTasaCambioModelDatabaseOperations:
    """Pruebas unitarias con mocks de base de datos para operaciones de tasa de cambio."""

    def test_get_all(self, model):
        with patch.object(TasaCambioModel, "fetch_all", return_value=[
            {"id": 1, "monto": 36.5, "fecha": "2026-08-22", "tipo": "bcv"}
        ]) as mock_fetch:
            result = model.ejecutar("get_all", 10)
            assert len(result) == 1
            assert result[0]["monto"] == 36.5
            mock_fetch.assert_called_once()

    def test_get_by_date(self, model):
        with patch.object(TasaCambioModel, "fetch_one", return_value={"id": 2, "monto": 36.6, "fecha": "2026-08-20"}):
            res = model.ejecutar("get_by_date", "2026-08-20")
            assert res["id"] == 2
            assert res["monto"] == 36.6

    def test_get_today(self, model):
        today = date.today().isoformat()
        with patch.object(TasaCambioModel, "fetch_one", return_value={"id": 3, "monto": 36.7, "fecha": today}):
            res = model.ejecutar("get_today")
            assert res["id"] == 3
            assert res["fecha"] == today

    @pytest.mark.parametrize("found, expected", [
        ({"id": 1}, True),
        (None, False),
    ])
    def test_exists_today(self, model, found, expected):
        with patch.object(TasaCambioModel, "_get_today", return_value=found):
            assert model.ejecutar("exists_today") is expected

    def test_get_latest(self, model):
        with patch.object(TasaCambioModel, "fetch_one", return_value={"id": 5, "monto": 37.10, "fecha": "2026-08-22"}):
            result = model.ejecutar("get_latest")
            assert result["id"] == 5
            assert result["monto"] == 37.10

    def test_create_tasa(self, model):
        data = {
            "monto": 36.80,
            "fecha": "2026-08-22",
            "fuente": "BCV Manual"
        }
        with patch.object(TasaCambioModel, "insert", return_value=10) as mock_insert:
            result = model.ejecutar("create", data)
            assert result == 10
            mock_insert.assert_called_once()

    @pytest.mark.parametrize("has_fecha", [True, False])
    def test_update_tasa(self, model, has_fecha):
        data = {"monto": 37.20, "fuente": "BCV Oficial"}
        if has_fecha:
            data["fecha"] = "2026-08-23"

        with patch.object(TasaCambioModel, "update", return_value=1) as mock_update:
            res = model.ejecutar("update_tasa", 1, data)
            assert res == 1
            mock_update.assert_called_once()

    def test_delete_tasa(self, model):
        with patch.object(TasaCambioModel, "delete", return_value=1) as mock_delete:
            result = model.ejecutar("delete_tasa", 1)
            assert result == 1
            mock_delete.assert_called_once()

    def test_register_from_scraping_already_exists(self, model):
        with patch.object(TasaCambioModel, "_exists_today", return_value=True):
            res = model.ejecutar("register_from_scraping", 36.5)
            assert res is None

    def test_register_from_scraping_new(self, model):
        with patch.object(TasaCambioModel, "_exists_today", return_value=False), \
             patch.object(TasaCambioModel, "_create", return_value=15) as mock_create:
            res = model.ejecutar("register_from_scraping", 36.5)
            assert res == 15
            mock_create.assert_called_once()

    def test_upsert_from_scraping_lock_busy(self, model):
        with patch.object(TasaCambioModel, "fetch_one", return_value={"acquired": 0}):
            res = model.ejecutar("upsert_from_scraping", 37.0)
            assert res["action"] == "lock_busy"
            assert res["id"] is None

    def test_upsert_from_scraping_existing_updates(self, model):
        with patch.object(TasaCambioModel, "fetch_one", side_effect=[
            {"acquired": 1},  # Lock acquired
            {"released": 1}   # Lock released in finally
        ]), patch.object(TasaCambioModel, "_get_by_date", return_value={"id": 7, "monto": 36.0}), \
            patch.object(TasaCambioModel, "_update_tasa", return_value=1) as mock_update:
            res = model.ejecutar("upsert_from_scraping", 37.5, fecha="2026-08-25")
            assert res["action"] == "updated"
            assert res["id"] == 7
            mock_update.assert_called_once()

    def test_upsert_from_scraping_new_creates(self, model):
        with patch.object(TasaCambioModel, "fetch_one", side_effect=[
            {"acquired": 1},  # Lock acquired
            {"released": 1}   # Lock released in finally
        ]), patch.object(TasaCambioModel, "_get_by_date", return_value=None), \
            patch.object(TasaCambioModel, "_create", return_value=20) as mock_create:
            res = model.ejecutar("upsert_from_scraping", 37.5, fecha="2026-08-25")
            assert res["action"] == "created"
            assert res["id"] == 20
            mock_create.assert_called_once()

    def test_ejecutar_invalid_action(self, model):
        with pytest.raises(ValueError) as exc_info:
            model.ejecutar("accion_inexistente")
        assert "Accion no permitida" in str(exc_info.value)
