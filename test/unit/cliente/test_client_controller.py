import pytest
from unittest.mock import patch


class TestClientController:

    def test_get_all_unauthorized_fails(self, client):
        response = client.get('/api/clients/')
        json_data = response.get_json()

        assert response.status_code == 401
        assert json_data["status"] == "error"
        assert response.get_json() == {"status": "error", "message": "Debe iniciar sesion."}

    def test_get_all_regular_client_denied(self, auth_regular_client):
        response = auth_regular_client.get('/api/clients/')
        json_data = response.get_json()

        assert response.status_code == 403
        assert json_data["status"] == "error"

    @patch("model.client_model.ClientModel._get_all")
    def test_get_all_employee_authorized_success(self, mock_get_all, auth_employee_client):
        mock_get_all.return_value = [
            {"cedula": "V-12345678", "nombre": "Ana López", "telefono": "04141234567"}
        ]
        response = auth_employee_client.get('/api/clients/')
        json_data = response.get_json()

        assert response.status_code == 200
        assert json_data["status"] == "success"
        assert len(json_data["data"]) == 1

    @patch("model.client_model.ClientModel._get_stats")
    def test_get_stats_employee_success(self, mock_get_stats, auth_employee_client):
        mock_get_stats.return_value = {"total": 15, "activos": 12}
        response = auth_employee_client.get('/api/clients/stats')
        json_data = response.get_json()

        assert response.status_code == 200
        assert json_data["status"] == "success"
        assert json_data["data"]["total"] == 15

    @patch("model.client_model.ClientModel._get_bitacora")
    @patch("model.client_model.ClientModel._get_notifications")
    @patch("model.client_model.ClientModel._get_orders")
    @patch("model.client_model.ClientModel._get_tickets")
    @patch("model.client_model.ClientModel._get_services")
    @patch("model.client_model.ClientModel._get_vehicles")
    @patch("model.client_model.ClientModel._get_by_cedula")
    def test_get_one_client_found(
        self, mock_get_by_cedula, mock_get_vehicles, mock_get_services,
        mock_get_tickets, mock_get_orders, mock_get_notifications,
        mock_get_bitacora, auth_employee_client
    ):
        mock_get_by_cedula.return_value = {"cedula": "V-12345678", "nombre": "Ana López"}
        mock_get_vehicles.return_value = []
        mock_get_services.return_value = []
        mock_get_tickets.return_value = []
        mock_get_orders.return_value = []
        mock_get_notifications.return_value = []
        mock_get_bitacora.return_value = []

        response = auth_employee_client.get('/api/clients/V-12345678')
        json_data = response.get_json()

        assert response.status_code == 200
        assert json_data["status"] == "success"
        assert json_data["data"]["cedula"] == "V-12345678"

    @patch("model.client_model.ClientModel._create")
    @patch("model.client_model.ClientModel._get_by_cedula")
    def test_create_client_success(self, mock_get_by_cedula, mock_create, auth_employee_client):
        mock_get_by_cedula.return_value = None
        mock_create.return_value = {"cedula": "V-12345678", "reactivated": False}

        response = auth_employee_client.post('/api/clients/', json={
            "cedula": "V-12345678",
            "nombre": "Ana",
            "apellido": "López",
            "telefono": "04141234567"
        })
        json_data = response.get_json()

        assert response.status_code == 201
        assert json_data["status"] == "success"
        assert json_data["id"] == "V-12345678"
