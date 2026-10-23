import pytest
from unittest.mock import patch


class TestCompanyController:

    def test_get_all_unauthorized_fails(self, client):
        response = client.get('/api/companies/')
        json_data = response.get_json()

        assert response.status_code == 401
        assert json_data["status"] == "error"
        assert response.get_json() == {"status": "error", "message": "Debe iniciar sesion."}

    def test_get_all_regular_client_denied(self, auth_regular_client):
        response = auth_regular_client.get('/api/companies/')
        json_data = response.get_json()

        assert response.status_code == 403
        assert json_data["status"] == "error"

    @patch("model.company_model.CompanyModel._get_all")
    def test_get_all_employee_authorized_success(self, mock_get_all, auth_employee_client):
        mock_get_all.return_value = [
            {"rif": "J-123456789", "razon_social": "Transalca C.A.", "telefono": "02511234567"}
        ]
        response = auth_employee_client.get('/api/companies/')
        json_data = response.get_json()

        assert response.status_code == 200
        assert json_data["status"] == "success"
        assert len(json_data["data"]) == 1

    @patch("model.company_model.CompanyModel._get_stats")
    def test_get_stats_employee_success(self, mock_get_stats, auth_employee_client):
        mock_get_stats.return_value = {"total": 10, "activos": 8}
        response = auth_employee_client.get('/api/companies/stats')
        json_data = response.get_json()

        assert response.status_code == 200
        assert json_data["status"] == "success"
        assert json_data["data"]["total"] == 10

    @patch("model.company_model.CompanyModel._get_representatives")
    @patch("model.company_model.CompanyModel._get_orders")
    @patch("model.company_model.CompanyModel._get_fleet")
    @patch("model.company_model.CompanyModel._get_by_rif")
    def test_get_one_company_found(
        self, mock_get_by_rif, mock_get_fleet, mock_get_orders,
        mock_get_representatives, auth_employee_client
    ):
        mock_get_by_rif.return_value = {"cedula": "J-123456789", "rif": "J-123456789", "razon_social": "Transalca C.A."}
        mock_get_fleet.return_value = []
        mock_get_orders.return_value = []
        mock_get_representatives.return_value = []

        response = auth_employee_client.get('/api/companies/J-123456789')
        json_data = response.get_json()

        assert response.status_code == 200
        assert json_data["status"] == "success"
        assert json_data["data"]["rif"] == "J-123456789"

    @patch("model.company_model.CompanyModel._create")
    @patch("model.company_model.CompanyModel._get_by_rif")
    def test_create_company_success(self, mock_get_by_rif, mock_create, auth_employee_client):
        mock_get_by_rif.return_value = None
        mock_create.return_value = {"rif": "J-123456789", "reactivated": False}

        response = auth_employee_client.post('/api/companies/', json={
            "rif": "J-123456789",
            "razon_social": "Transalca C.A.",
            "telefono": "04121234567"
        })
        json_data = response.get_json()

        assert response.status_code == 201
        assert json_data["status"] == "success"
        assert json_data["id"] == "J-123456789"

    @patch("model.company_model.CompanyModel._soft_delete")
    def test_delete_company_success(self, mock_soft_delete, auth_employee_client):
        mock_soft_delete.return_value = 1
        response = auth_employee_client.put('/api/companies/J-123456789/toggle')
        json_data = response.get_json()

        assert response.status_code == 200
        assert json_data["status"] == "success"
        mock_soft_delete.assert_called_once()
