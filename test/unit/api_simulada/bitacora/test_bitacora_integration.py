import pytest


class TestBitacoraIntegration:

    def test_get_bitacora_unauthenticated_returns_401(self, client):
        response = client.get("/api/bitacora/")
        assert response.status_code == 401
        assert response.get_json()["status"] == "error"

    def test_get_all_bitacora_with_pagination(self, auth_client, mock_db):
        if not mock_db.bitacora:
            mock_db.bitacora.append({
                "id": 1,
                "usuario_id": 1,
                "accion": "LOGIN",
                "modulo": "AUTH",
                "descripcion": "Inicio de sesion",
                "ip": "127.0.0.1",
                "fecha": "2026-10-19 10:00:00"
            })

        response = auth_client.get("/api/bitacora/?page=1&limit=10")
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "success"
        assert "data" in data
        assert "total" in data
        assert data["page"] == 1

        logs = data["data"]
        assert len(logs) >= 1
        first_log = logs[0]
        assert "accion" in first_log
        assert "modulo" in first_log
        assert "nombre" in first_log

    def test_get_bitacora_by_user(self, auth_client, mock_db):
        mock_db.bitacora.append({
            "id": len(mock_db.bitacora) + 1,
            "usuario_id": 2,
            "accion": "UPDATE",
            "modulo": "SERVICIOS",
            "descripcion": "Modificación de servicio de prueba",
            "ip": "127.0.0.1",
            "fecha": "2026-10-19 11:30:00"
        })

        response = auth_client.get("/api/bitacora/user/2")
        assert response.status_code == 200
        logs = response.get_json()["data"]
        assert len(logs) >= 1
        assert all(log["usuario_id"] == 2 for log in logs)

        res_unauth = auth_client.application.test_client().get("/api/bitacora/user/2")
        assert res_unauth.status_code == 401

    def test_get_bitacora_by_module(self, auth_client, mock_db):
        mock_db.bitacora.append({
            "id": len(mock_db.bitacora) + 1,
            "usuario_id": 1,
            "accion": "INSERT",
            "modulo": "MECANICOS",
            "descripcion": "Registro de nuevo mecánico",
            "ip": "127.0.0.1",
            "fecha": "2026-10-19 12:15:00"
        })

        response = auth_client.get("/api/bitacora/module/MECANICOS")
        assert response.status_code == 200
        logs = response.get_json()["data"]
        assert len(logs) >= 1
        assert all(log["modulo"].upper() == "MECANICOS" for log in logs)

    def test_search_bitacora_by_text(self, auth_client, mock_db):
        unique_token = "TOKEN_DE_AUDITORIA_ESPECIAL"
        mock_db.bitacora.append({
            "id": len(mock_db.bitacora) + 1,
            "usuario_id": 1,
            "accion": "SECURITY_ALERT",
            "modulo": "AUTH",
            "descripcion": f"Evento de seguridad con {unique_token}",
            "ip": "192.168.1.50",
            "fecha": "2026-10-19 13:00:00"
        })

        res_found = auth_client.get(f"/api/bitacora/search?q={unique_token}")
        assert res_found.status_code == 200
        logs = res_found.get_json()["data"]
        assert len(logs) == 1
        assert unique_token in logs[0]["descripcion"]

        res_empty = auth_client.get("/api/bitacora/search?q=TerminoInexistente999XYZ")
        assert res_empty.status_code == 200
        assert len(res_empty.get_json()["data"]) == 0

    def test_filter_bitacora_by_date_range(self, auth_client, mock_db):
        mock_db.bitacora.append({
            "id": len(mock_db.bitacora) + 1,
            "usuario_id": 1,
            "accion": "BACKUP",
            "modulo": "SISTEMA",
            "descripcion": "Respaldo diario",
            "ip": "127.0.0.1",
            "fecha": "2026-10-15 04:00:00"
        })

        res_range = auth_client.get("/api/bitacora/filter?start=2026-10-01&end=2026-10-31")
        assert res_range.status_code == 200
        logs = res_range.get_json()["data"]
        assert len(logs) >= 1

        res_bad = auth_client.get("/api/bitacora/filter?start=2026-10-01")
        assert res_bad.status_code == 400
        assert res_bad.get_json()["status"] == "error"

    def test_cross_module_audit_trail_upon_auth_action(self, client, auth_client, mock_db):
        login_res = client.post("/auth/do_login", json={"email": "admin@transalca.com", "password": "Admin123*"})
        assert login_res.status_code == 200

        bitacora_res = auth_client.get("/api/bitacora/module/AUTH")
        assert bitacora_res.status_code == 200
        logs = bitacora_res.get_json()["data"]

        login_logs = [l for l in logs if l["accion"] == "LOGIN" and "admin@transalca.com" in l["descripcion"]]
        assert len(login_logs) >= 1
