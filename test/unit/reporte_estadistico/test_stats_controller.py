import pytest
from unittest.mock import patch


class TestStatsController:

    def test_revenue_timeline_unauthorized_fails(self, client):
        response = client.get('/api/stats/revenue')
        json_data = response.get_json()

        assert response.status_code == 401
        assert json_data["status"] == "error"
        assert response.get_json() == {"status": "error", "message": "Debe iniciar sesion."}

    @patch("model.stats_model.StatsModel._get_revenue_timeline")
    def test_revenue_timeline_authorized_success(self, mock_get_timeline, auth_employee_client):
        mock_get_timeline.return_value = {"labels": ["2026-08-20"], "data": [1500.00]}
        response = auth_employee_client.get('/api/stats/revenue?days=30')
        json_data = response.get_json()

        assert response.status_code == 200
        assert json_data["status"] == "success"
        assert json_data["data"]["labels"] == ["2026-08-20"]

    @patch("model.stats_model.StatsModel._get_top_performing_products")
    def test_top_products_authorized_success(self, mock_get_top_products, auth_employee_client):
        mock_get_top_products.return_value = {"labels": ["Aceite Mineral"], "data": [45]}
        response = auth_employee_client.get('/api/stats/products?limit=5')
        json_data = response.get_json()

        assert response.status_code == 200
        assert json_data["status"] == "success"
        assert json_data["data"]["labels"] == ["Aceite Mineral"]

    @patch("model.stats_model.StatsModel._get_order_status_distribution")
    def test_order_status_distribution_authorized_success(self, mock_get_dist, auth_employee_client):
        mock_get_dist.return_value = {"labels": ["Aprobada"], "data": [15]}
        response = auth_employee_client.get('/api/stats/status')
        json_data = response.get_json()

        assert response.status_code == 200
        assert json_data["status"] == "success"
        assert json_data["data"]["labels"] == ["Aprobada"]

    @patch("model.stats_model.StatsModel._get_payments_distribution")
    def test_payments_distribution_authorized_success(self, mock_get_pay_dist, auth_employee_client):
        mock_get_pay_dist.return_value = {"labels": ["Pago móvil"], "data": [25]}
        response = auth_employee_client.get('/api/stats/payments')
        json_data = response.get_json()

        assert response.status_code == 200
        assert json_data["status"] == "success"
        assert json_data["data"]["labels"] == ["Pago móvil"]

    @patch("model.stats_model.StatsModel._get_top_services")
    def test_top_services_authorized_success(self, mock_get_top_services, auth_employee_client):
        mock_get_top_services.return_value = {
            "labels": ["Cambio de Aceite"],
            "data": [40],
            "ingresos": [600.00]
        }
        response = auth_employee_client.get('/api/stats/services?limit=5')
        json_data = response.get_json()

        assert response.status_code == 200
        assert json_data["status"] == "success"
        assert json_data["data"]["ingresos"] == [600.00]
