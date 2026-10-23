import pytest


class TestServiceMechanicIntegration:

    def test_unauthorized_access_rejected(self, client):
        res_create = client.post("/api/service-mechanics/", json={"servicio_id": 1})
        assert res_create.status_code == 401

        res_mech = client.put("/api/service-mechanics/1/mechanic", json={"mecanico_cedula": "V-12345678"})
        assert res_mech.status_code == 401

        res_st = client.put("/api/service-mechanics/1/status", json={"estado": "en_proceso"})
        assert res_st.status_code == 401

        res_put = client.put("/api/service-mechanics/1", json={"servicio_id": 1})
        assert res_put.status_code == 401

        res_del = client.delete("/api/service-mechanics/1")
        assert res_del.status_code == 401
        assert res_create.get_json() == {"status": "error", "message": "Debe iniciar sesion."}

    def test_get_all_assignments_integration(self, auth_client):
        response = auth_client.get("/api/service-mechanics/")
        assert response.status_code == 200
        data = response.get_json()

        assert data["status"] == "success"
        items = data["data"]
        assert isinstance(items, list)
        assert len(items) >= 1

        first = items[0]
        assert first["id"] == 1
        assert first["servicio_nombre"] == "Alineación Computarizada"
        assert "Carlos Pérez" in first["mecanico_nombre"]
        assert first["cliente_cedula"] == "V-87654321"
        assert first["vehiculo_placa"] == "ABC123D"
        assert first["estado"] == "en_proceso"

    def test_get_one_assignment_found(self, auth_client):
        response = auth_client.get("/api/service-mechanics/1")
        assert response.status_code == 200
        data = response.get_json()

        assert data["status"] == "success"
        item = data["data"]
        assert item["id"] == 1
        assert item["servicio_nombre"] == "Alineación Computarizada"
        assert item["cliente_nombre"] == "Juan"
        assert item["vehiculo_marca"] == "Toyota"
        assert item["mecanico_cedula"] == "V-12345678"

    def test_get_one_assignment_not_found(self, auth_client):
        response = auth_client.get("/api/service-mechanics/99999")
        assert response.status_code == 404
        data = response.get_json()
        assert data["status"] == "error"
        assert "no encontrada" in data["message"].lower()

    def test_create_assignment_full_integration(self, auth_client, mock_db):
        payload = {
            "servicio_id": 2,
            "mecanico_cedula": "V-87654321",
            "cliente_cedula": "V-87654321",
            "vehiculo_placa": "ABC123D",
            "observaciones": "Balanceo preventivo",
            "porcentaje_comision": 18.0
        }
        response = auth_client.post("/api/service-mechanics/", json=payload)
        assert response.status_code == 200
        data = response.get_json()

        assert data["status"] == "success"
        aid = data["id"]
        assert aid is not None

        get_res = auth_client.get(f"/api/service-mechanics/{aid}")
        assert get_res.status_code == 200
        saved = get_res.get_json()["data"]
        assert saved["servicio_id"] == 2
        assert saved["mecanico_cedula"] == "V-87654321"
        assert saved["estado"] == "asignado"
        assert saved["observaciones"] == "Balanceo preventivo"

        assert aid in mock_db.comisiones_mecanico
        assert mock_db.comisiones_mecanico[aid]["porcentaje_comision"] == 18.0

    def test_create_assignment_without_mechanic_defaults_to_sin_asignar(self, auth_client):
        payload = {
            "servicio_id": 2,
            "mecanico_cedula": "",
            "cliente_cedula": "V-87654321",
            "vehiculo_placa": "ABC123D",
            "observaciones": "Esperando mecánico disponible"
        }
        response = auth_client.post("/api/service-mechanics/", json=payload)
        assert response.status_code == 200
        aid = response.get_json()["id"]

        get_res = auth_client.get(f"/api/service-mechanics/{aid}")
        saved = get_res.get_json()["data"]
        assert saved["mecanico_cedula"] is None
        assert saved["estado"] == "sin_asignar"

    def test_cross_module_validations_rejected(self, auth_client):
        res_serv = auth_client.post("/api/service-mechanics/", json={
            "servicio_id": 9999,
            "cliente_cedula": "V-87654321",
            "vehiculo_placa": "ABC123D"
        })
        assert res_serv.status_code == 400

        res_serv_inact = auth_client.post("/api/service-mechanics/", json={
            "servicio_id": 3,
            "cliente_cedula": "V-87654321",
            "vehiculo_placa": "ABC123D"
        })
        assert res_serv_inact.status_code == 400

        res_mech_inact = auth_client.post("/api/service-mechanics/", json={
            "servicio_id": 1,
            "mecanico_cedula": "V-11111111",
            "cliente_cedula": "V-87654321",
            "vehiculo_placa": "ABC123D"
        })
        assert res_mech_inact.status_code == 400

        res_cli = auth_client.post("/api/service-mechanics/", json={
            "servicio_id": 1,
            "cliente_cedula": "V-00000000",
            "vehiculo_placa": "ABC123D"
        })
        assert res_cli.status_code == 400

        res_veh = auth_client.post("/api/service-mechanics/", json={
            "servicio_id": 1,
            "cliente_cedula": "V-87654321",
            "vehiculo_placa": "PLACA999"
        })
        assert res_veh.status_code == 400

    def test_mechanic_busy_conflict_detection_and_confirmation(self, auth_client, mock_db):
        post_res = auth_client.post("/api/service-mechanics/", json={
            "servicio_id": 2,
            "mecanico_cedula": "",
            "cliente_cedula": "V-87654321",
            "vehiculo_placa": "ABC123D"
        })
        aid2 = post_res.get_json()["id"]

        res_conflict = auth_client.put(f"/api/service-mechanics/{aid2}/mechanic", json={
            "mecanico_cedula": "V-12345678",
            "porcentaje_comision": 20.0
        })
        assert res_conflict.status_code == 200
        data_conflict = res_conflict.get_json()
        assert data_conflict["status"] == "confirm"
        assert "ya se encuentra asignado" in data_conflict["message"]

        res_confirmed = auth_client.put(f"/api/service-mechanics/{aid2}/mechanic", json={
            "mecanico_cedula": "V-12345678",
            "porcentaje_comision": 20.0,
            "confirmar": True
        })
        assert res_confirmed.status_code == 200
        assert res_confirmed.get_json()["status"] == "success"

        check_res = auth_client.get(f"/api/service-mechanics/{aid2}")
        assert check_res.get_json()["data"]["mecanico_cedula"] == "V-12345678"

    def test_update_status_business_rules(self, auth_client):
        create_res = auth_client.post("/api/service-mechanics/", json={
            "servicio_id": 2,
            "mecanico_cedula": "",
            "cliente_cedula": "V-87654321",
            "vehiculo_placa": "ABC123D"
        })
        aid = create_res.get_json()["id"]

        res_fail = auth_client.put(f"/api/service-mechanics/{aid}/status", json={"estado": "en_proceso"})
        assert res_fail.status_code == 400
        assert res_fail.get_json()["status"] == "error"

        auth_client.put(f"/api/service-mechanics/{aid}/mechanic", json={
            "mecanico_cedula": "V-87654321",
            "porcentaje_comision": 15.0
        })

        res_ok = auth_client.put(f"/api/service-mechanics/{aid}/status", json={"estado": "en_proceso"})
        assert res_ok.status_code == 200
        assert res_ok.get_json()["status"] == "success"

    def test_complete_service_generates_commission_integration(self, auth_client, mock_db):
        res_complete = auth_client.put("/api/service-mechanics/1/status", json={
            "estado": "completado",
            "porcentaje_comision": 22.5
        })
        assert res_complete.status_code == 200
        data = res_complete.get_json()
        assert data["status"] == "success"
        assert "commission_id" in data
        assert data["commission_id"] == 1

        assert mock_db.comisiones_mecanico[1]["porcentaje_comision"] == 22.5

    def test_delete_assignment_integration(self, auth_client, mock_db):
        assert 1 in mock_db.servicio_mecanico

        del_res = auth_client.delete("/api/service-mechanics/1")
        assert del_res.status_code == 200
        assert del_res.get_json()["status"] == "success"

        assert 1 not in mock_db.servicio_mecanico
        get_res = auth_client.get("/api/service-mechanics/1")
        assert get_res.status_code == 404

    def test_full_cross_module_end_to_end_flow(self, auth_client):
        serv_res = auth_client.post("/api/services/", json={
            "nombre": "Mantenimiento Integral E2E",
            "descripcion": "Prueba de flujo integral",
            "tipo": "general",
            "precio": 50.00,
            "duracion_estimada": 90,
            "sucursal_ids": [1]
        })
        assert serv_res.status_code == 200
        new_serv_id = serv_res.get_json()["id"]

        mec_res = auth_client.post("/api/mechanics/", data={
            "cedula": "V-33444555",
            "nombre": "Gabriel",
            "apellido": "Mendoza",
            "telefono": "04123344555",
            "especialidad": "Mantenimiento General"
        })
        assert mec_res.status_code == 200
        new_mec_cedula = mec_res.get_json()["cedula"]

        status_initial = auth_client.get(f"/api/mechanics/{new_mec_cedula}").get_json()["data"]
        assert status_initial["estado_operativo"] == "Disponible"

        assign_res = auth_client.post("/api/service-mechanics/", json={
            "servicio_id": new_serv_id,
            "mecanico_cedula": new_mec_cedula,
            "cliente_cedula": "V-87654321",
            "vehiculo_placa": "ABC123D",
            "observaciones": "Inicio de servicio E2E",
            "porcentaje_comision": 20.0
        })
        assert assign_res.status_code == 200
        new_assign_id = assign_res.get_json()["id"]

        status_busy = auth_client.get(f"/api/mechanics/{new_mec_cedula}").get_json()["data"]
        assert status_busy["estado_operativo"] == "Ocupado"

        prog_res = auth_client.put(f"/api/service-mechanics/{new_assign_id}/status", json={"estado": "en_proceso"})
        assert prog_res.status_code == 200

        comp_res = auth_client.put(f"/api/service-mechanics/{new_assign_id}/status", json={
            "estado": "completado",
            "porcentaje_comision": 20.0
        })
        assert comp_res.status_code == 200

        status_free = auth_client.get(f"/api/mechanics/{new_mec_cedula}").get_json()["data"]
        assert status_free["estado_operativo"] == "Disponible"

        hist_res = auth_client.get(f"/api/mechanics/history/{new_mec_cedula}")
        assert hist_res.status_code == 200
        history = hist_res.get_json()["data"]
        assert len(history) == 1
        assert history[0]["servicio_nombre"] == "Mantenimiento Integral E2E"
        assert history[0]["estado"] == "completado"

    def test_update_non_existent_assignment_routes_return_404(self, auth_client):
        res_mech = auth_client.put("/api/service-mechanics/99999/mechanic", json={
            "mecanico_cedula": "V-12345678",
            "porcentaje_comision": 15.0
        })
        assert res_mech.status_code == 404
        assert res_mech.get_json()["status"] == "error"

        res_st = auth_client.put("/api/service-mechanics/99999/status", json={"estado": "cancelado"})
        assert res_st.status_code == 404

        res_put = auth_client.put("/api/service-mechanics/99999", json={
            "servicio_id": 1,
            "cliente_cedula": "V-87654321",
            "vehiculo_placa": "ABC123D"
        })
        assert res_put.status_code == 404

        res_del = auth_client.delete("/api/service-mechanics/99999")
        assert res_del.status_code == 404

    def test_commission_percentage_boundary_validations(self, auth_client):
        res_zero = auth_client.put("/api/service-mechanics/1/mechanic", json={
            "mecanico_cedula": "V-12345678",
            "porcentaje_comision": 0.0,
            "confirmar": True
        })
        assert res_zero.status_code == 400
        assert "porcentaje_comision" in res_zero.get_json().get("errors", {})

        res_neg = auth_client.put("/api/service-mechanics/1/mechanic", json={
            "mecanico_cedula": "V-12345678",
            "porcentaje_comision": -5.0,
            "confirmar": True
        })
        assert res_neg.status_code == 400

        res_high = auth_client.put("/api/service-mechanics/1/mechanic", json={
            "mecanico_cedula": "V-12345678",
            "porcentaje_comision": 105.0,
            "confirmar": True
        })
        assert res_high.status_code == 400

    def test_observaciones_content_and_security_validation(self, auth_client):
        res_script = auth_client.post("/api/service-mechanics/", json={
            "servicio_id": 1,
            "cliente_cedula": "V-87654321",
            "vehiculo_placa": "ABC123D",
            "observaciones": "<script>alert('XSS')</script>"
        })
        assert res_script.status_code == 400
        assert "observaciones" in res_script.get_json().get("errors", {})

        res_spaces = auth_client.post("/api/service-mechanics/", json={
            "servicio_id": 1,
            "cliente_cedula": "V-87654321",
            "vehiculo_placa": "ABC123D",
            "observaciones": "     "
        })
        assert res_spaces.status_code == 400
        assert "observaciones" in res_spaces.get_json().get("errors", {})

        res_valid = auth_client.post("/api/service-mechanics/", json={
            "servicio_id": 1,
            "cliente_cedula": "V-87654321",
            "vehiculo_placa": "ABC123D",
            "observaciones": "Revisión general, cambio de pastillas - ok."
        })
        assert res_valid.status_code == 200

    def test_unassign_mechanic_via_full_update(self, auth_client, mock_db):
        assert auth_client.get("/api/mechanics/V-12345678").get_json()["data"]["estado_operativo"] == "Ocupado"

        update_res = auth_client.put("/api/service-mechanics/1", json={
            "servicio_id": 1,
            "mecanico_cedula": "",
            "cliente_cedula": "V-87654321",
            "vehiculo_placa": "ABC123D",
            "estado": "sin_asignar"
        })
        assert update_res.status_code == 200

        item = auth_client.get("/api/service-mechanics/1").get_json()["data"]
        assert item["mecanico_cedula"] is None
        assert item["estado"] == "sin_asignar"

        assert auth_client.get("/api/mechanics/V-12345678").get_json()["data"]["estado_operativo"] == "Disponible"

    def test_reassign_mechanic_updates_commission_percentage(self, auth_client, mock_db):
        reassign_res = auth_client.put("/api/service-mechanics/1/mechanic", json={
            "mecanico_cedula": "V-87654321",
            "porcentaje_comision": 25.0
        })
        assert reassign_res.status_code == 200
        assert reassign_res.get_json()["status"] == "success"

        item = auth_client.get("/api/service-mechanics/1").get_json()["data"]
        assert item["mecanico_cedula"] == "V-87654321"
        assert mock_db.comisiones_mecanico[1]["porcentaje_comision"] == 25.0

    def test_status_transition_cancelado_frees_mechanic(self, auth_client):
        assert auth_client.get("/api/mechanics/V-12345678").get_json()["data"]["estado_operativo"] == "Ocupado"

        cancel_res = auth_client.put("/api/service-mechanics/1/status", json={"estado": "cancelado"})
        assert cancel_res.status_code == 200

        assert auth_client.get("/api/mechanics/V-12345678").get_json()["data"]["estado_operativo"] == "Disponible"

    def test_full_assignment_update_all_fields_simultaneously(self, auth_client):
        payload = {
            "servicio_id": 2,
            "mecanico_cedula": "V-87654321",
            "cliente_cedula": "V-99999999",
            "vehiculo_placa": "XYZ789E",
            "observaciones": "Actualización completa de orden",
            "estado": "asignado",
            "porcentaje_comision": 30.0
        }
        res = auth_client.put("/api/service-mechanics/1", json=payload)
        assert res.status_code == 200
        assert res.get_json()["status"] == "success"

        updated = auth_client.get("/api/service-mechanics/1").get_json()["data"]
        assert updated["servicio_id"] == 2
        assert updated["servicio_nombre"] == "Balanceo Dinámico"
        assert updated["cliente_cedula"] == "V-99999999"
        assert updated["vehiculo_placa"] == "XYZ789E"
        assert updated["observaciones"] == "Actualización completa de orden"

    def test_concurrent_assignments_multiple_mechanics(self, auth_client):
        res2 = auth_client.post("/api/service-mechanics/", json={
            "servicio_id": 2,
            "mecanico_cedula": "V-87654321",
            "cliente_cedula": "V-87654321",
            "vehiculo_placa": "ABC123D"
        })
        aid2 = res2.get_json()["id"]

        assert auth_client.get("/api/mechanics/V-12345678").get_json()["data"]["estado_operativo"] == "Ocupado"
        assert auth_client.get("/api/mechanics/V-87654321").get_json()["data"]["estado_operativo"] == "Ocupado"

        auth_client.put("/api/service-mechanics/1/status", json={"estado": "completado"})
        assert auth_client.get("/api/mechanics/V-12345678").get_json()["data"]["estado_operativo"] == "Disponible"
        assert auth_client.get("/api/mechanics/V-87654321").get_json()["data"]["estado_operativo"] == "Ocupado"

        auth_client.put(f"/api/service-mechanics/{aid2}/status", json={"estado": "completado"})
        assert auth_client.get("/api/mechanics/V-87654321").get_json()["data"]["estado_operativo"] == "Disponible"

    def test_complete_service_retains_registered_commission_percentage(self, auth_client, mock_db):
        mock_db.comisiones_mecanico[1]["porcentaje_comision"] = 17.5

        res = auth_client.put("/api/service-mechanics/1/status", json={"estado": "completado"})
        assert res.status_code == 200
        assert res.get_json()["status"] == "success"

        assert mock_db.comisiones_mecanico[1]["porcentaje_comision"] == 17.5

    def test_invalid_status_value_rejected(self, auth_client):
        response = auth_client.put("/api/service-mechanics/1/status", json={"estado": "estado_inexistente"})
        assert response.status_code == 400
        data = response.get_json()
        assert data["status"] == "error"
        assert "estado" in data.get("errors", {})

