import pytest


class TestSucursalIntegration:

    def test_unauthorized_access_rejected(self, client):
        res_post = client.post("/api/sucursales/", json={"nombre": "Sede Nueva"})
        assert res_post.status_code == 401

        res_put = client.put("/api/sucursales/1", json={"nombre": "Sede Modificada"})
        assert res_put.status_code == 401

        res_del = client.delete("/api/sucursales/1")
        assert res_del.status_code == 401

        res_get = client.get("/api/sucursales/1")
        assert res_get.status_code == 401

        res_chk = client.post("/api/sucursales/check-unique", json={"field": "nombre", "value": "Sede"})
        assert res_chk.status_code == 401

        res_svc = client.get("/api/services/sucursal/1")
        assert res_svc.status_code == 401
        assert res_post.get_json() == {"status": "error", "message": "Debe iniciar sesion."}

    def test_get_all_and_active_sucursales(self, client, auth_client):
        response = client.get("/api/sucursales/active")
        assert response.status_code == 200
        data = response.get_json()

        assert data["status"] == "success"
        items = data["data"]
        assert isinstance(items, list)
        assert len(items) >= 2

        nombres = [s["nombre"] for s in items]
        assert "Sede Central" in nombres
        assert "Sede Norte" in nombres
        assert "Sede Inactiva" not in nombres

        res_all = auth_client.get("/api/sucursales/")
        assert res_all.status_code == 200
        assert res_all.get_json()["status"] == "success"

    def test_get_sucursal_detail_found(self, auth_client):
        response = auth_client.get("/api/sucursales/1")
        assert response.status_code == 200
        data = response.get_json()

        assert data["status"] == "success"
        sucursal = data["data"]
        assert sucursal["id"] == 1
        assert sucursal["nombre"] == "Sede Central"
        assert sucursal["direccion"] == "Av. Intercomunal"
        assert sucursal["telefono"] == "04141112233"
        assert sucursal["email"] == "central@transalca.com"

    def test_get_sucursal_detail_not_found(self, auth_client):
        response = auth_client.get("/api/sucursales/99999")
        assert response.status_code == 404
        data = response.get_json()
        assert data["status"] == "error"
        assert "no encontrada" in data["message"].lower()

    def test_check_unique_nombre_and_email(self, auth_client):
        res_nom = auth_client.post("/api/sucursales/check-unique", json={"field": "nombre", "value": "Sede Central"})
        assert res_nom.status_code == 200
        assert res_nom.get_json()["exists"] is True

        res_nom_excl = auth_client.post("/api/sucursales/check-unique", json={"field": "nombre", "value": "Sede Central", "exclude": 1})
        assert res_nom_excl.status_code == 200
        assert res_nom_excl.get_json()["exists"] is False

        res_nom_free = auth_client.post("/api/sucursales/check-unique", json={"field": "nombre", "value": "Sede Totalmente Nueva"})
        assert res_nom_free.status_code == 200
        assert res_nom_free.get_json()["exists"] is False

        res_em = auth_client.post("/api/sucursales/check-unique", json={"field": "email", "value": "central@transalca.com"})
        assert res_em.status_code == 200
        assert res_em.get_json()["exists"] is True

        res_em_free = auth_client.post("/api/sucursales/check-unique", json={"field": "email", "value": "nueva.sucursal@transalca.com"})
        assert res_em_free.status_code == 200
        assert res_em_free.get_json()["exists"] is False

    def test_create_sucursal_lifecycle(self, auth_client, mock_db):
        payload = {
            "nombre": "Sede Barquisimeto Este",
            "direccion": "Av. Los Leones",
            "telefono": "04145558899",
            "email": "este@transalca.com"
        }
        res_create = auth_client.post("/api/sucursales/", json=payload)
        assert res_create.status_code == 200
        data = res_create.get_json()
        assert data["status"] == "success"
        sid = data["id"]
        assert sid is not None

        res_get = auth_client.get(f"/api/sucursales/{sid}")
        assert res_get.status_code == 200
        suc = res_get.get_json()["data"]
        assert suc["nombre"] == "Sede Barquisimeto Este"
        assert suc["email"] == "este@transalca.com"

    def test_create_sucursal_validation_errors(self, auth_client):
        res_short = auth_client.post("/api/sucursales/", json={"nombre": "AB"})
        assert res_short.status_code == 400
        assert res_short.get_json()["status"] == "error"

        res_bad_dir = auth_client.post("/api/sucursales/", json={"nombre": "Sede Oeste", "direccion": "Av. $$$ ### %%%"})
        assert res_bad_dir.status_code == 400

    def test_update_sucursal_success(self, auth_client, mock_db):
        payload = {
            "nombre": "Sede Central Modificada",
            "direccion": "Av. Principal Renovada",
            "telefono": "04141112233",
            "email": "central@transalca.com"
        }
        response = auth_client.put("/api/sucursales/1", json=payload)
        assert response.status_code == 200
        assert response.get_json()["status"] == "success"

        res_get = auth_client.get("/api/sucursales/1")
        assert res_get.status_code == 200
        suc = res_get.get_json()["data"]
        assert suc["nombre"] == "Sede Central Modificada"
        assert suc["direccion"] == "Av. Principal Renovada"

    def test_soft_delete_sucursal(self, auth_client, mock_db):
        res_del = auth_client.delete("/api/sucursales/2")
        assert res_del.status_code == 200
        assert res_del.get_json()["status"] == "success"

        res_active = auth_client.get("/api/sucursales/active")
        active_names = [s["nombre"] for s in res_active.get_json()["data"]]
        assert "Sede Norte" not in active_names

    def test_sucursal_servicios_integration(self, auth_client):
        res_s1 = auth_client.get("/api/services/sucursal/1")
        assert res_s1.status_code == 200
        data1 = res_s1.get_json()["data"]
        s1_names = [s["nombre"] for s in data1]
        assert "Alineación Computarizada" in s1_names
        assert "Balanceo Dinámico" in s1_names

        res_s2 = auth_client.get("/api/services/sucursal/2")
        assert res_s2.status_code == 200
        data2 = res_s2.get_json()["data"]
        s2_names = [s["nombre"] for s in data2]
        assert "Alineación Computarizada" in s2_names
        assert "Balanceo Dinámico" not in s2_names
