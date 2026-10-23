import pytest


class TestClientVehicleIntegration:

    def test_unauthenticated_client_and_vehicle_management_rejected(self, client):
        res_cli = client.get("/api/clients/")
        assert res_cli.status_code == 401

        res_create_cli = client.post("/api/clients/", json={"cedula": "V-11223344", "nombre": "Test"})
        assert res_create_cli.status_code == 401

        res_veh = client.get("/api/vehicles/")
        assert res_veh.status_code == 401

        res_link = client.post("/api/clients/V-87654321/vehicles", json={"placa": "ABC123D"})
        assert res_link.status_code == 401
        assert res_cli.get_json() == {"status": "error", "message": "Debe iniciar sesion."}

    def test_client_role_authorization_and_ownership_guards(self, client_user_client):
        res_list = client_user_client.get("/api/clients/")
        assert res_list.status_code == 403

        res_self = client_user_client.get("/api/clients/V-87654321")
        assert res_self.status_code == 200, f"Error: {res_self.status_code} - {res_self.get_json()}"
        assert res_self.get_json()["status"] == "success"
        data_self = res_self.get_json()["data"]
        assert data_self["cedula"] == "V-87654321"
        assert "vehiculos" in data_self
        assert len(data_self["vehiculos"]) >= 1

        res_other = client_user_client.get("/api/clients/V-99999999")
        assert res_other.status_code == 403

        res_own_veh = client_user_client.get("/api/vehicles/ABC123D")
        assert res_own_veh.status_code == 200
        assert res_own_veh.get_json()["data"]["placa"] == "ABC123D"

        res_other_veh = client_user_client.get("/api/vehicles/XYZ789E")
        assert res_other_veh.status_code == 403

    def test_employee_can_view_all_clients_and_vehicles(self, auth_client):
        res_clients = auth_client.get("/api/clients/")
        assert res_clients.status_code == 200
        clients_data = res_clients.get_json()["data"]
        assert isinstance(clients_data, list)
        assert len(clients_data) >= 2

        res_stats = auth_client.get("/api/clients/stats")
        assert res_stats.status_code == 200
        stats = res_stats.get_json()["data"]
        assert "total" in stats
        assert "activos" in stats
        assert stats["total"] >= 2

        res_veh = auth_client.get("/api/vehicles/")
        assert res_veh.status_code == 200
        vehicles = res_veh.get_json()["data"]
        assert len(vehicles) >= 2
        first_veh = next((v for v in vehicles if v["placa"] == "ABC123D"), None)
        assert first_veh is not None
        assert first_veh["cliente_nombre"] == "Juan"
        assert first_veh["cliente_apellido"] == "Pérez"

    def test_check_unique_client_and_vehicle_validations(self, auth_client):
        res_ced = auth_client.post("/api/clients/check-unique", json={"field": "cedula", "value": "V-87654321"})
        assert res_ced.status_code == 200
        assert res_ced.get_json()["exists"] is True

        res_ced_self = auth_client.post("/api/clients/check-unique", json={"field": "cedula", "value": "V-87654321", "exclude": "V-87654321"})
        assert res_ced_self.status_code == 200
        assert res_ced_self.get_json()["exists"] is False

        res_email = auth_client.post("/api/clients/check-unique", json={"field": "email", "value": "juan.perez@email.com"})
        assert res_email.status_code == 200
        assert res_email.get_json()["exists"] is True

        res_placa = auth_client.post("/api/clients/check-unique", json={"field": "placa", "value": "ABC123D", "cedula": "V-87654321"})
        assert res_placa.status_code == 200
        assert res_placa.get_json()["exists"] is True

        res_placa_free = auth_client.post("/api/clients/check-unique", json={"field": "placa", "value": "LIB123X", "cedula": "V-87654321"})
        assert res_placa_free.status_code == 200
        assert res_placa_free.get_json()["exists"] is False

    def test_create_client_and_link_vehicle_integration(self, auth_client, mock_db):
        client_payload = {
            "cedula": "V-12398745",
            "nombre": "Roberto",
            "apellido": "Silva",
            "email": "roberto.silva@email.com",
            "telefono": "04123334455",
            "direccion": "Urb. El Parral",
            "tipo_cliente": "persona"
        }
        res_cli = auth_client.post("/api/clients/", json=client_payload)
        assert res_cli.status_code == 201
        assert res_cli.get_json()["status"] == "success"

        vehicle_payload = {
            "placa": "SIL123V",
            "marca": "Chevrolet",
            "modelo": "Cruze",
            "anio": 2017,
            "color": "Gris",
            "tipo_vehiculo": "Sedan",
            "tipo_combustible": "gasolina",
            "kilometraje_actual": 65000,
            "observaciones": "Uso particular"
        }
        res_veh = auth_client.post("/api/clients/V-12398745/vehicles", json=vehicle_payload)
        assert res_veh.status_code == 201, f"POST vehicle error: {res_veh.status_code} - {res_veh.get_json()}"
        assert res_veh.get_json()["status"] == "success"

        res_360 = auth_client.get("/api/clients/V-12398745")
        assert res_360.status_code == 200
        profile = res_360.get_json()["data"]
        assert profile["nombre"] == "Roberto"
        assert profile["apellido"] == "Silva"
        assert len(profile["vehiculos"]) == 1
        linked_vehicle = profile["vehiculos"][0]
        assert linked_vehicle["placa"] == "SIL123V"
        assert linked_vehicle["marca"] == "Chevrolet"

        res_v_det = auth_client.get("/api/vehicles/SIL123V")
        assert res_v_det.status_code == 200
        v_det = res_v_det.get_json()["data"]
        assert v_det["placa"] == "SIL123V"
        assert v_det["cliente_nombre"] == "Roberto"
        assert v_det["cliente_apellido"] == "Silva"

    def test_prevent_duplicate_plate_for_same_client(self, auth_client):
        duplicate_payload = {
            "placa": "ABC123D",
            "marca": "Toyota",
            "modelo": "Corolla",
            "anio": 2020,
            "color": "Blanco"
        }
        response = auth_client.post("/api/clients/V-87654321/vehicles", json=duplicate_payload)
        assert response.status_code == 400
        data = response.get_json()
        assert data["status"] == "error"
        assert "placa" in data.get("errors", {})

    def test_update_and_unlink_vehicle_from_client(self, auth_client, mock_db):
        update_payload = {
            "placa": "ABC123D",
            "marca": "Toyota",
            "modelo": "Corolla XEi",
            "anio": 2021,
            "color": "Plata"
        }
        res_update = auth_client.put("/api/clients/V-87654321/vehicles/ABC123D", json=update_payload)
        assert res_update.status_code == 200
        assert res_update.get_json()["status"] == "success"

        res_det = auth_client.get("/api/vehicles/ABC123D")
        assert res_det.status_code == 200
        det_data = res_det.get_json()["data"]
        assert det_data["modelo"] == "Corolla XEi"
        assert det_data["color"] == "Plata"

        res_del = auth_client.delete("/api/clients/V-87654321/vehicles/ABC123D")
        assert res_del.status_code == 200
        assert res_del.get_json()["status"] == "success"

        res_client_vehicles = auth_client.get("/api/clients/V-87654321/vehicles")
        assert res_client_vehicles.status_code == 200
        active_plates = [v["placa"] for v in res_client_vehicles.get_json()["data"]]
        assert "ABC123D" not in active_plates

    def test_soft_delete_client_lifecycle(self, auth_client):
        res_toggle = auth_client.put("/api/clients/V-99999999/toggle")
        assert res_toggle.status_code == 200
        assert res_toggle.get_json()["status"] == "success"

        res_check = auth_client.post("/api/clients/check-unique", json={"field": "cedula", "value": "V-99999999"})
        assert res_check.status_code == 200
        assert res_check.get_json()["active"] is False
