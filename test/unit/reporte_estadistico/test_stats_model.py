import pytest
from unittest.mock import patch
from datetime import datetime
from model.stats_model import StatsModel


@pytest.fixture
def model():
    return StatsModel()


class TestStatsModelQueries:

    @pytest.mark.parametrize("days_param", [7, 30, 90])
    def test_get_revenue_timeline(self, model, days_param):
        with patch.object(StatsModel, "fetch_all", return_value=[
            {"fecha_corta": datetime(2026, 8, 20), "total": 1500.00},
            {"fecha_corta": datetime(2026, 8, 21), "total": 2300.50},
        ]) as mock_fetch_all:
            result = model.ejecutar("get_revenue_timeline", days=days_param)
            assert len(result["labels"]) == 2
            assert result["labels"][0] == "2026-08-20"
            assert result["data"][0] == 1500.00
            mock_fetch_all.assert_called_once()

    def test_get_revenue_timeline_empty(self, model):
        with patch.object(StatsModel, "fetch_all", return_value=[]):
            result = model.ejecutar("get_revenue_timeline")
            assert result["labels"] == []
            assert result["data"] == []

    @pytest.mark.parametrize("limit_param", [3, 5, 10])
    def test_get_top_performing_products(self, model, limit_param):
        with patch.object(StatsModel, "fetch_all", return_value=[
            {"nombre": "Aceite 20W50 Mineral Sella", "total_vendido": 45},
            {"nombre": "Filtro Aceite PH3593A", "total_vendido": 30},
        ]) as mock_fetch_all:
            result = model.ejecutar("get_top_performing_products", limit=limit_param)
            assert len(result["labels"]) == 2
            assert result["labels"][0] == "Aceite 20W50 Mi"
            assert result["data"][0] == 45
            mock_fetch_all.assert_called_once()


class TestStatsModelDatabaseOperations:

    def test_get_order_status_distribution(self, model):
        with patch.object(StatsModel, "fetch_all", return_value=[
            {"estado": "aprobada", "cantidad": 15},
            {"estado": "pendiente", "cantidad": 5},
        ]):
            result = model.ejecutar("get_order_status_distribution")
            assert result["labels"] == ["Aprobada", "Pendiente"]
            assert result["data"] == [15, 5]

    def test_get_payments_distribution(self, model):
        with patch.object(StatsModel, "fetch_all", return_value=[
            {"metodo": "Pago Móvil", "cantidad": 25},
            {"metodo": "Zelle", "cantidad": 10},
        ]):
            result = model.ejecutar("get_payments_distribution")
            assert result["labels"] == ["Pago móvil", "Zelle"]
            assert result["data"] == [25, 10]

    def test_get_top_services(self, model):
        with patch.object(StatsModel, "fetch_all", return_value=[
            {"nombre": "Cambio de Aceite de Motor", "total_solicitados": 40, "ingreso": 600.00}
        ]):
            result = model.ejecutar("get_top_services", 5)
            assert result["labels"][0] == "Cambio de Aceite de "
            assert result["data"][0] == 40
            assert result["ingresos"][0] == 600.00

    def test_ejecutar_invalid_action(self, model):
        with pytest.raises(ValueError) as exc_info:
            model.ejecutar("accion_inexistente")
        assert "Accion no permitida" in str(exc_info.value)
