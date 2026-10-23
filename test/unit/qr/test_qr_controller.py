import pytest
from unittest.mock import patch


class TestQRController:

    def test_get_all_unauthorized_fails(self, client):
        response = client.get('/api/qr/')
        json_data = response.get_json()

        assert response.status_code == 401
        assert json_data["status"] == "error"
        assert response.get_json() == {"status": "error", "message": "Debe iniciar sesion."}

    @patch("model.qr_model.QRModel._get_all_qrs")
    def test_get_all_authorized_success(self, mock_get_all_qrs, auth_employee_client):
        mock_get_all_qrs.return_value = [
            {"id": 1, "tipo": "pago", "usuario_cedula": "V-12345678"}
        ]
        response = auth_employee_client.get('/api/qr/')
        json_data = response.get_json()

        assert response.status_code == 200
        assert json_data["status"] == "success"
        assert len(json_data["data"]) == 1

    def test_my_qrs_non_client_denied(self, auth_employee_client):
        response = auth_employee_client.get('/api/qr/my')
        json_data = response.get_json()

        assert response.status_code == 403
        assert json_data["status"] == "error"
        assert "solo clientes" in json_data["message"].lower()

    @patch("model.qr_model.QRModel._get_user_qrs")
    def test_my_qrs_client_success(self, mock_get_user_qrs, auth_client_user):
        mock_get_user_qrs.return_value = [
            {"id": 1, "tipo": "promocion", "usuario_cedula": "V-12345678"}
        ]
        response = auth_client_user.get('/api/qr/my')
        json_data = response.get_json()

        assert response.status_code == 200
        assert json_data["status"] == "success"
        assert len(json_data["data"]) == 1

    @patch("model.qr_model.QRModel._get_by_id")
    def test_get_one_qr_found(self, mock_get_by_id, auth_employee_client):
        mock_get_by_id.return_value = {"id": 1, "tipo": "info"}
        response = auth_employee_client.get('/api/qr/1')
        json_data = response.get_json()

        assert response.status_code == 200
        assert json_data["status"] == "success"
        assert json_data["data"]["id"] == 1

    @patch("model.qr_model.QRModel._create_qr")
    def test_create_qr_success(self, mock_create_qr, auth_client_user):
        mock_create_qr.return_value = 5
        response = auth_client_user.post('/api/qr/', json={
            "tipo": "info",
            "utilidad_tipo": "catalogo",
            "contenido": "Información general"
        })
        json_data = response.get_json()

        assert response.status_code == 200
        assert json_data["status"] == "success"
        assert json_data["id"] == 5

    @patch("model.qr_model.QRModel._delete_qr")
    def test_delete_qr_success(self, mock_delete_qr, auth_client_user):
        mock_delete_qr.return_value = 1
        response = auth_client_user.delete('/api/qr/1')
        json_data = response.get_json()

        assert response.status_code == 200
        assert json_data["status"] == "success"
        mock_delete_qr.assert_called_once()

    @patch("model.qr_model.QRModel._get_qr_data")
    def test_scan_qr_success(self, mock_get_qr_data, auth_employee_client):
        mock_get_qr_data.return_value = {
            "qr": {"id": 1, "tipo": "pago"},
            "usuario": {"nombre": "Carlos", "cedula": "V-12345678"}
        }
        response = auth_employee_client.get('/api/qr/scan/1')
        json_data = response.get_json()

        assert response.status_code == 200
        assert json_data["status"] == "success"
        assert json_data["data"]["usuario"]["nombre"] == "Carlos"
