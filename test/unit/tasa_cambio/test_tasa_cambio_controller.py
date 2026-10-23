import pytest
from unittest.mock import patch


class TestTasaCambioController:

    @patch("controller.tasa_cambio_controller.sync_bcv_rate_if_needed")
    @patch("model.tasa_cambio_model.TasaCambioModel._get_all")
    def test_get_all_tasas(self, mock_get_all, mock_sync, auth_employee_client):
        mock_get_all.return_value = [
            {"id": 1, "monto": 36.50, "fecha": "2026-08-22"}
        ]
        response = auth_employee_client.get('/api/tasas/')
        json_data = response.get_json()

        assert response.status_code == 200
        assert json_data["status"] == "success"
        assert len(json_data["data"]) == 1

    @patch("controller.tasa_cambio_controller.sync_bcv_rate_if_needed")
    @patch("model.tasa_cambio_model.TasaCambioModel._get_today")
    def test_get_today_found(self, mock_get_today, mock_sync, auth_employee_client):
        mock_get_today.return_value = {"id": 1, "monto": 36.50, "fecha": "2026-08-22"}
        response = auth_employee_client.get('/api/tasas/today')
        json_data = response.get_json()

        assert response.status_code == 200
        assert json_data["status"] == "success"
        assert json_data["data"]["monto"] == 36.50

    @patch("controller.tasa_cambio_controller.sync_bcv_rate_if_needed")
    @patch("model.tasa_cambio_model.TasaCambioModel._get_today")
    def test_get_today_not_found(self, mock_get_today, mock_sync, auth_employee_client):
        mock_get_today.return_value = None
        response = auth_employee_client.get('/api/tasas/today')
        json_data = response.get_json()

        assert response.status_code == 404
        assert json_data["status"] == "error"

    @patch("controller.tasa_cambio_controller.sync_bcv_rate_if_needed")
    @patch("model.tasa_cambio_model.TasaCambioModel._get_latest")
    def test_get_latest_found(self, mock_get_latest, mock_sync, auth_employee_client):
        mock_get_latest.return_value = {"id": 5, "monto": 37.10, "fecha": "2026-08-22"}
        response = auth_employee_client.get('/api/tasas/latest')
        json_data = response.get_json()

        assert response.status_code == 200
        assert json_data["status"] == "success"
        assert json_data["data"]["monto"] == 37.10

    def test_create_unauthorized_fails(self, client):
        response = client.post('/api/tasas/', json={"monto": 36.5, "fecha": "2026-08-22", "fuente": "BCV"})
        json_data = response.get_json()

        assert response.status_code == 401
        assert json_data["status"] == "error"
        assert response.get_json() == {"status": "error", "message": "Debe iniciar sesion."}

    @patch("model.tasa_cambio_model.TasaCambioModel._create")
    def test_create_authorized_success(self, mock_create, auth_employee_client):
        mock_create.return_value = 10
        response = auth_employee_client.post('/api/tasas/', json={
            "monto": 36.80,
            "fecha": "2026-08-22",
            "fuente": "BCV Manual"
        })
        json_data = response.get_json()

        assert response.status_code == 200
        assert json_data["status"] == "success"
        assert json_data["id"] == 10

    @patch("model.tasa_cambio_model.TasaCambioModel._delete_tasa")
    def test_delete_authorized_success(self, mock_delete_tasa, auth_employee_client):
        mock_delete_tasa.return_value = 1
        response = auth_employee_client.delete('/api/tasas/10')
        json_data = response.get_json()

        assert response.status_code == 200
        assert json_data["status"] == "success"
        mock_delete_tasa.assert_called_once()

    @patch("controller.tasa_cambio_controller.sync_bcv_rate_if_needed")
    def test_sync_scraping_success(self, mock_sync, auth_employee_client):
        mock_sync.return_value = {
            "synced": True,
            "action": "created",
            "monto": 36.90,
            "id": 12
        }
        response = auth_employee_client.post('/api/tasas/sync-scraping')
        json_data = response.get_json()

        assert response.status_code == 200
        assert json_data["status"] == "success"
        assert "registrada" in json_data["message"].lower()
