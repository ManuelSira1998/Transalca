import pytest
from unittest.mock import patch


@pytest.fixture
def auth_client(client):
    with client.session_transaction() as sess:
        sess['user_id'] = 1
        sess['user_cedula'] = 'V-12345678'
        sess['user_tipo'] = 'admin'
    return client


class TestMechanicController:

    @patch("model.mechanic_model.MechanicModel._get_all")
    def test_get_all_mechanics(self, mock_get_all, auth_client):
        mock_get_all.return_value = [
            {"cedula": "V-12345678", "nombre": "Carlos", "apellido": "Pérez"}
        ]
        response = auth_client.get('/api/mechanics/')
        json_data = response.get_json()

        assert response.status_code == 200
        assert json_data["status"] == "success"
        assert len(json_data["data"]) == 1

    @patch("model.mechanic_model.MechanicModel._get_by_cedula")
    def test_get_one_mechanic_found(self, mock_get_by_cedula, auth_client):
        mock_get_by_cedula.return_value = {"cedula": "V-12345678", "nombre": "Carlos"}
        response = auth_client.get('/api/mechanics/V-12345678')
        json_data = response.get_json()

        assert response.status_code == 200
        assert json_data["status"] == "success"
        assert json_data["data"]["cedula"] == "V-12345678"

    @patch("model.mechanic_model.MechanicModel._get_by_cedula")
    def test_get_one_mechanic_not_found(self, mock_get_by_cedula, auth_client):
        mock_get_by_cedula.return_value = None
        response = auth_client.get('/api/mechanics/V-99999999')
        json_data = response.get_json()

        assert response.status_code == 404
        assert json_data["status"] == "error"

    def test_create_unauthorized_fails(self, client):
        response = client.post('/api/mechanics/', data={
            "cedula": "V-12345678",
            "nombre": "Carlos",
            "apellido": "Pérez"
        })
        json_data = response.get_json()

        assert response.status_code == 401
        assert json_data["status"] == "error"
        assert response.get_json() == {"status": "error", "message": "Debe iniciar sesion."}

    @patch("model.mechanic_model.MechanicModel._create")
    @patch("model.mechanic_model.MechanicModel._get_by_cedula")
    def test_create_authorized_success(self, mock_get_by_cedula, mock_create, auth_client):
        mock_get_by_cedula.return_value = None
        mock_create.return_value = "V-12345678"

        response = auth_client.post('/api/mechanics/', data={
            "cedula": "V-12345678",
            "nombre": "Carlos",
            "apellido": "Pérez"
        })
        json_data = response.get_json()

        assert response.status_code == 200
        assert json_data["status"] == "success"
        assert json_data["cedula"] == "V-12345678"
