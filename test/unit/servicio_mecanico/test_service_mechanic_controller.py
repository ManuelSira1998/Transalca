import pytest
from unittest.mock import patch


class TestServiceMechanicController:

    @patch("model.service_mechanic_model.ServiceMechanicModel._get_all")
    def test_get_all_assignments(self, mock_get_all, auth_client):
        mock_get_all.return_value = [
            {
                "id": 1,
                "servicio_id": 1,
                "servicio_nombre": "Alineación",
                "mecanico_nombre": "Carlos Gómez",
                "estado": "asignado"
            }
        ]
        response = auth_client.get('/api/service-mechanics/')
        json_data = response.get_json()

        assert response.status_code == 200
        assert json_data["status"] == "success"
        assert len(json_data["data"]) == 1

    @patch("model.service_mechanic_model.ServiceMechanicModel._get_by_id")
    def test_get_one_assignment_found(self, mock_get_by_id, auth_client):
        mock_get_by_id.return_value = {
            "id": 1,
            "servicio_nombre": "Alineación",
            "mecanico_nombre": "Carlos Gómez"
        }
        response = auth_client.get('/api/service-mechanics/1')
        json_data = response.get_json()

        assert response.status_code == 200
        assert json_data["status"] == "success"
        assert json_data["data"]["id"] == 1

    @patch("model.service_mechanic_model.ServiceMechanicModel._get_by_id")
    def test_get_one_assignment_not_found(self, mock_get_by_id, auth_client):
        mock_get_by_id.return_value = None
        response = auth_client.get('/api/service-mechanics/999')
        json_data = response.get_json()

        assert response.status_code == 404
        assert json_data["status"] == "error"

    def test_create_unauthorized_fails(self, client):
        response = client.post('/api/service-mechanics/', json={
            "servicio_id": 1,
            "cliente_cedula": "V-87654321",
            "vehiculo_placa": "ABC123"
        })
        json_data = response.get_json()

        assert response.status_code == 401
        assert json_data["status"] == "error"
        assert response.get_json() == {"status": "error", "message": "Debe iniciar sesion."}

    @patch("model.service_mechanic_model.ServiceMechanicModel._assign")
    def test_create_authorized_success(self, mock_assign, auth_client):
        mock_assign.return_value = 1
        response = auth_client.post('/api/service-mechanics/', json={
            "servicio_id": 1,
            "cliente_cedula": "V-87654321",
            "vehiculo_placa": "ABC123"
        })
        json_data = response.get_json()

        assert response.status_code == 200
        assert json_data["status"] == "success"
        assert json_data["id"] == 1

    @patch("model.service_mechanic_model.ServiceMechanicModel._delete_assignment")
    @patch("model.service_mechanic_model.ServiceMechanicModel._get_by_id")
    def test_delete_assignment_success(self, mock_get_by_id, mock_delete_assignment, auth_client):
        mock_get_by_id.return_value = {"id": 1, "servicio_nombre": "Alineación"}
        mock_delete_assignment.return_value = 1

        response = auth_client.delete('/api/service-mechanics/1')
        json_data = response.get_json()

        assert response.status_code == 200
        assert json_data["status"] == "success"
        mock_delete_assignment.assert_called_once()
