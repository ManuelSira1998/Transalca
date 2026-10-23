import pytest


class TestServiceIntegration:

    def test_unauthorized_access_rejected(self, client):
        res_post = client.post("/api/services/", json={"nombre": "Servicio X", "precio": 25.0, "tipo": "general"})
        assert res_post.status_code == 401

        res_put = client.put("/api/services/1", json={"nombre": "Servicio Modificado"})
        assert res_put.status_code == 401

        res_toggle = client.put("/api/services/1/toggle")
        assert res_toggle.status_code == 401

        res_del = client.delete("/api/services/1")
        assert res_del.status_code == 401
        assert res_post.get_json() == {"status": "error", "message": "Debe iniciar sesion."}

    def test_get_active_services_public(self, client):
        response = client.get("/api/services/active")
        assert response.status_code == 200
        data = response.get_json()

        assert data["status"] == "success"
        services = data["data"]
        assert isinstance(services, list)
        assert len(services) >= 2

        service_names = [s["nombre"] for s in services]
        assert "Alineación Computarizada" in service_names
        assert "Balanceo Dinámico" in service_names
        assert "Servicio Desactivado" not in service_names

    def test_get_all_services_authenticated(self, auth_client):
        response = auth_client.get("/api/services/")
        assert response.status_code == 200
        data = response.get_json()

        assert data["status"] == "success"
        services = data["data"]
        assert len(services) >= 2

        s1 = next(s for s in services if s["id"] == 1)
        assert s1["nombre"] == "Alineación Computarizada"
        assert s1["precio"] == 35.00
        assert "sucursal_ids" in s1
        assert "1,2" in s1["sucursal_ids"] or "1" in s1["sucursal_ids"]
        assert "Sede Central" in (s1["sucursal_nombre"] or "")

    def test_get_one_service_found(self, auth_client):
        response = auth_client.get("/api/services/1")
        assert response.status_code == 200
        data = response.get_json()

        assert data["status"] == "success"
        service = data["data"]
        assert service["id"] == 1
        assert service["nombre"] == "Alineación Computarizada"
        assert service["tipo"] == "alineacion"
        assert service["precio"] == 35.00

    def test_get_one_service_not_found(self, auth_client):
        response = auth_client.get("/api/services/99999")
        assert response.status_code == 404
        data = response.get_json()
        assert data["status"] == "error"
        assert "no encontrado" in data["message"].lower()

    def test_get_services_by_sucursal(self, auth_client):
        response = auth_client.get("/api/services/sucursal/2")
        assert response.status_code == 200
        data = response.get_json()

        assert data["status"] == "success"
        services = data["data"]
        service_ids = [s["id"] for s in services]
        assert 1 in service_ids
        assert 2 not in service_ids

    def test_check_unique_service_name(self, auth_client):
        res_taken = auth_client.get("/api/services/check-unique?value=Alineación Computarizada")
        assert res_taken.status_code == 200
        assert res_taken.get_json()["unique"] is False

        res_free = auth_client.get("/api/services/check-unique?value=Cambio de Filtro de Aire")
        assert res_free.status_code == 200
        assert res_free.get_json()["unique"] is True

        res_excl = auth_client.get("/api/services/check-unique?value=Alineación Computarizada&exclude=1")
        assert res_excl.status_code == 200
        assert res_excl.get_json()["unique"] is True

    def test_create_service_with_branch_sync_success(self, auth_client, mock_db):
        payload = {
            "nombre": "Rotación de Neumáticos",
            "descripcion": "Rotación en X para desgaste uniforme",
            "tipo": "rotacion",
            "precio": 18.50,
            "duracion_estimada": 40,
            "sucursal_ids": [1, 2]
        }
        response = auth_client.post("/api/services/", json=payload)
        assert response.status_code == 200
        data = response.get_json()

        assert data["status"] == "success"
        new_id = data["id"]
        assert new_id is not None

        get_res = auth_client.get(f"/api/services/{new_id}")
        assert get_res.status_code == 200
        saved = get_res.get_json()["data"]
        assert saved["nombre"] == "Rotación de Neumáticos"
        assert saved["precio"] == 18.50
        assert saved["tipo"] == "rotacion"
        assert "1" in saved["sucursal_ids"]
        assert "2" in saved["sucursal_ids"]

    def test_create_service_validation_errors(self, auth_client):
        payload_bad_type = {
            "nombre": "Servicio Invalido",
            "precio": 50.0,
            "tipo": "tipo_falso",
            "sucursal_ids": [1]
        }
        res_type = auth_client.post("/api/services/", json=payload_bad_type)
        assert res_type.status_code == 400
        assert res_type.get_json()["status"] == "error"

        payload_bad_suc = {
            "nombre": "Servicio Sucursal Inexistente",
            "precio": 50.0,
            "tipo": "general",
            "sucursal_ids": [9999]
        }
        res_suc = auth_client.post("/api/services/", json=payload_bad_suc)
        assert res_suc.status_code == 400

        payload_no_suc = {
            "nombre": "Servicio Sin Sucursal",
            "precio": 50.0,
            "tipo": "general",
            "sucursal_ids": []
        }
        res_no_suc = auth_client.post("/api/services/", json=payload_no_suc)
        assert res_no_suc.status_code == 400

    def test_create_duplicate_active_service_fails(self, auth_client):
        payload = {
            "nombre": "Alineación Computarizada",
            "precio": 40.0,
            "tipo": "alineacion",
            "sucursal_ids": [1]
        }
        response = auth_client.post("/api/services/", json=payload)
        assert response.status_code == 400
        data = response.get_json()
        assert data["status"] == "error"
        assert "ya existe un servicio" in data["errors"].get("nombre", "").lower()

    def test_create_existing_inactive_service_reactivates(self, auth_client, mock_db):
        assert mock_db.servicios[3]["estado"] == 0

        payload = {
            "nombre": "Servicio Desactivado",
            "descripcion": "Reactivado y actualizado",
            "tipo": "general",
            "precio": 25.00,
            "duracion_estimada": 35,
            "sucursal_ids": [1]
        }
        response = auth_client.post("/api/services/", json=payload)
        assert response.status_code == 200

        assert mock_db.servicios[3]["estado"] == 1
        assert mock_db.servicios[3]["precio_servicio"] == 25.00

        active_res = auth_client.get("/api/services/active")
        active_names = [s["nombre"] for s in active_res.get_json()["data"]]
        assert "Servicio Desactivado" in active_names

    def test_update_service_and_sync_branches(self, auth_client):
        payload = {
            "nombre": "Balanceo Láser Dinámico",
            "descripcion": "Calibración de alta precisión",
            "tipo": "balanceo",
            "precio": 28.00,
            "duracion_estimada": 50,
            "sucursal_ids": [2]
        }
        response = auth_client.put("/api/services/2", json=payload)
        assert response.status_code == 200
        assert response.get_json()["status"] == "success"

        get_res = auth_client.get("/api/services/2")
        data = get_res.get_json()["data"]
        assert data["nombre"] == "Balanceo Láser Dinámico"
        assert data["precio"] == 28.00
        assert data["sucursal_ids"] == "2"

    def test_toggle_service_status_integration(self, auth_client, mock_db):
        assert mock_db.servicios[1]["estado"] == 1

        res1 = auth_client.put("/api/services/1/toggle")
        assert res1.status_code == 200
        assert mock_db.servicios[1]["estado"] == 0

        active_res = auth_client.get("/api/services/active")
        active_ids = [s["id"] for s in active_res.get_json()["data"]]
        assert 1 not in active_ids

    def test_soft_delete_service_integration(self, auth_client, mock_db):
        response = auth_client.delete("/api/services/2")
        assert response.status_code == 200
        assert response.get_json()["status"] == "success"

        assert mock_db.servicios[2]["estado"] == 0

    def test_update_non_existent_service_returns_404(self, auth_client):
        response = auth_client.put("/api/services/99999", json={
            "nombre": "Inexistente",
            "tipo": "general",
            "precio": 50.0,
            "sucursal_ids": [1]
        })
        assert response.status_code == 404
        assert response.get_json()["status"] == "error"

    def test_toggle_non_existent_service_returns_404(self, auth_client):
        response = auth_client.put("/api/services/99999/toggle")
        assert response.status_code == 404
        assert response.get_json()["status"] == "error"

    def test_delete_non_existent_service_returns_404(self, auth_client):
        response = auth_client.delete("/api/services/99999")
        assert response.status_code == 404
        assert response.get_json()["status"] == "error"

    def test_create_service_all_allowed_types_integration(self, auth_client):
        allowed_types = ["alineacion", "rotacion", "balanceo", "cambio_aceite", "general"]
        for idx, tipo in enumerate(allowed_types):
            payload = {
                "nombre": f"Servicio Tipo {tipo.capitalize()} {idx}",
                "tipo": tipo,
                "precio": 20.0 + idx,
                "sucursal_ids": [1]
            }
            res = auth_client.post("/api/services/", json=payload)
            assert res.status_code == 200
            sid = res.get_json()["id"]

            saved = auth_client.get(f"/api/services/{sid}").get_json()["data"]
            assert saved["tipo"] == tipo

    def test_create_service_price_validation_boundaries(self, auth_client):
        res_neg = auth_client.post("/api/services/", json={
            "nombre": "Servicio Negativo",
            "tipo": "general",
            "precio": -15.00,
            "sucursal_ids": [1]
        })
        assert res_neg.status_code == 400
        assert "precio" in res_neg.get_json().get("errors", {})

        res_str = auth_client.post("/api/services/", json={
            "nombre": "Servicio No Numerico",
            "tipo": "general",
            "precio": "gratis",
            "sucursal_ids": [1]
        })
        assert res_str.status_code == 400
        assert "precio" in res_str.get_json().get("errors", {})

    def test_create_service_duration_boundaries(self, auth_client):
        res_neg = auth_client.post("/api/services/", json={
            "nombre": "Servicio Duracion Negativa",
            "tipo": "general",
            "precio": 25.0,
            "duracion_estimada": -10,
            "sucursal_ids": [1]
        })
        assert res_neg.status_code == 400
        assert "duracion_estimada" in res_neg.get_json().get("errors", {})

        res_high = auth_client.post("/api/services/", json={
            "nombre": "Servicio Duracion Alta",
            "tipo": "general",
            "precio": 25.0,
            "duracion_estimada": 1500,
            "sucursal_ids": [1]
        })
        assert res_high.status_code == 400

        res_ok = auth_client.post("/api/services/", json={
            "nombre": "Servicio 2 Horas",
            "tipo": "general",
            "precio": 25.0,
            "duracion_estimada": 120,
            "sucursal_ids": [1]
        })
        assert res_ok.status_code == 200
        sid = res_ok.get_json()["id"]
        assert auth_client.get(f"/api/services/{sid}").get_json()["data"]["duracion_estimada"] == 120

    def test_create_service_name_length_boundaries(self, auth_client):
        res_short = auth_client.post("/api/services/", json={
            "nombre": "AB",
            "tipo": "general",
            "precio": 25.0,
            "sucursal_ids": [1]
        })
        assert res_short.status_code == 400
        assert "nombre" in res_short.get_json().get("errors", {})

        res_long = auth_client.post("/api/services/", json={
            "nombre": "S" * 205,
            "tipo": "general",
            "precio": 25.0,
            "sucursal_ids": [1]
        })
        assert res_long.status_code == 400
        assert "nombre" in res_long.get_json().get("errors", {})

    def test_update_service_change_name_collision_fails(self, auth_client):
        response = auth_client.put("/api/services/2", json={
            "nombre": "Alineación Computarizada",
            "tipo": "balanceo",
            "precio": 25.0,
            "sucursal_ids": [1]
        })
        assert response.status_code == 400
        data = response.get_json()
        assert "ya existe un servicio" in data["errors"].get("nombre", "").lower()

    def test_update_service_same_name_different_attributes_succeeds(self, auth_client):
        response = auth_client.put("/api/services/1", json={
            "nombre": "Alineación Computarizada",
            "descripcion": "Descripción actualizada",
            "tipo": "alineacion",
            "precio": 45.00,
            "sucursal_ids": [1, 2]
        })
        assert response.status_code == 200
        assert response.get_json()["status"] == "success"

        item = auth_client.get("/api/services/1").get_json()["data"]
        assert item["precio"] == 45.00
        assert item["descripcion"] == "Descripción actualizada"

    def test_get_services_by_sucursal_empty_or_invalid(self, auth_client):
        response = auth_client.get("/api/services/sucursal/999")
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "success"
        assert data["data"] == []

    def test_check_unique_empty_value_returns_true(self, auth_client):
        response = auth_client.get("/api/services/check-unique?value=")
        assert response.status_code == 200
        assert response.get_json()["unique"] is True

    def test_toggle_service_reactivation_cycle(self, auth_client, mock_db):
        assert mock_db.servicios[1]["estado"] == 1

        res_off = auth_client.put("/api/services/1/toggle")
        assert res_off.status_code == 200
        assert "eliminado" in res_off.get_json()["message"].lower()
        assert mock_db.servicios[1]["estado"] == 0

        active_list = auth_client.get("/api/services/active").get_json()["data"]
        assert 1 not in [s["id"] for s in active_list]

