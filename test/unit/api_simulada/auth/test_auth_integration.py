import pytest


class TestAuthIntegration:

    def test_login_success_populates_session_and_logs(self, client, mock_db):
        payload = {
            "email": "admin@transalca.com",
            "password": "Admin123*"
        }
        response = client.post("/auth/do_login", json=payload)
        assert response.status_code == 200
        data = response.get_json()

        assert data["status"] == "success"
        assert data["redirect"] == "/admin/dashboard"
        assert data["user"]["nombre"] == "Admin"
        assert data["user"]["tipo"] == "admin"

        sess_res = client.get("/auth/session")
        assert sess_res.status_code == 200
        sess_data = sess_res.get_json()["user"]
        assert sess_data["email"] == "admin@transalca.com"
        assert "Administrador" in sess_data["roles"]
        assert "usuarios" in sess_data["permisos"]

        last_log = mock_db.bitacora[-1]
        assert last_log["accion"] == "LOGIN"
        assert last_log["modulo"] == "AUTH"
        assert "admin@transalca.com" in last_log["descripcion"]

    def test_login_invalid_password_fails_401(self, client):
        response = client.post("/auth/do_login", json={
            "email": "admin@transalca.com",
            "password": "PasswordEquivocada99*"
        })
        assert response.status_code == 401
        assert response.get_json()["status"] == "error"

    def test_login_inactive_user_rejected_403(self, client):
        response = client.post("/auth/do_login", json={
            "email": "inactivo@transalca.com",
            "password": "Inactivo123*"
        })
        assert response.status_code == 403
        data = response.get_json()
        assert data["status"] == "error"
        assert "inactivo" in data["message"].lower()

    def test_client_login_redirects_to_client_portal(self, client):
        response = client.post("/auth/do_login", json={
            "email": "cliente@transalca.com",
            "password": "Cliente123*"
        })
        assert response.status_code == 200
        data = response.get_json()
        assert data["redirect"] == "/client/home"
        assert data["user"]["tipo"] == "cliente"

    def test_session_unauthenticated_returns_401(self, client):
        response = client.get("/auth/session")
        assert response.status_code == 401
        assert response.get_json()["status"] == "error"

    def test_logout_clears_session_and_logs_event(self, client, mock_db):
        client.post("/auth/do_login", json={"email": "admin@transalca.com", "password": "Admin123*"})
        assert client.get("/auth/session").status_code == 200

        res_logout = client.post("/auth/logout")
        assert res_logout.status_code == 200
        assert res_logout.get_json()["status"] == "success"

        assert client.get("/auth/session").status_code == 401

        last_log = mock_db.bitacora[-1]
        assert last_log["accion"] == "LOGOUT"
        assert last_log["modulo"] == "AUTH"

    def test_register_client_with_cross_module_transalca_sync(self, client, mock_db):
        payload = {
            "nombre": "Elena",
            "apellido": "Rivas",
            "cedula": "V-55667788",
            "email": "elena.rivas@correo.com",
            "telefono": "04125556677",
            "direccion": "Av. Los Próceres",
            "password": "Password123*",
            "confirm_password": "Password123*"
        }
        response = client.post("/auth/do_register", json=payload)
        assert response.status_code == 200
        assert response.get_json()["status"] == "success"

        created_user = next((u for u in mock_db.usuarios.values() if u["email"] == "elena.rivas@correo.com"), None)
        assert created_user is not None
        assert created_user["tipo"] == "cliente"
        assert created_user["cedula"] == "V-55667788"

        assert "V-55667788" in mock_db.clientes
        cli_record = mock_db.clientes["V-55667788"]
        assert cli_record["nombre_cliente"] == "Elena"
        assert cli_record["correo_cliente"] == "elena.rivas@correo.com"

        login_res = client.post("/auth/do_login", json={
            "email": "elena.rivas@correo.com",
            "password": "Password123*"
        })
        assert login_res.status_code == 200
        assert login_res.get_json()["user"]["nombre"] == "Elena"

    def test_check_unique_endpoint_integration(self, client):
        res_email_taken = client.post("/auth/check-unique", json={"field": "email", "value": "admin@transalca.com"})
        assert res_email_taken.status_code == 200
        assert res_email_taken.get_json()["exists"] is True

        res_email_free = client.post("/auth/check-unique", json={"field": "email", "value": "nuevo@transalca.com"})
        assert res_email_free.status_code == 200
        assert res_email_free.get_json()["exists"] is False

        res_ced_taken = client.post("/auth/check-unique", json={"field": "cedula", "value": "V-10000000"})
        assert res_ced_taken.status_code == 200
        assert res_ced_taken.get_json()["exists"] is True

        res_ced_free = client.post("/auth/check-unique", json={"field": "cedula", "value": "V-99999999"})
        assert res_ced_free.status_code == 200
        assert res_ced_free.get_json()["exists"] is False

    def test_password_recovery_and_reset_integration_flow(self, client, mock_db):
        email = "operador@transalca.com"

        rec_res = client.post("/auth/do_recover", json={"email": email})
        assert rec_res.status_code == 200
        assert rec_res.get_json()["status"] == "success"

        user_tokens = [t for t in mock_db.tokens_recuperacion.values() if t["usuario_id"] == 2 and t["usado"] == 0]
        assert len(user_tokens) == 1
        recovery_token = user_tokens[0]["token"]

        reset_res = client.post("/auth/do_reset", json={
            "token": recovery_token,
            "password": "NuevaPassword123*",
            "confirm_password": "NuevaPassword123*"
        })
        assert reset_res.status_code == 200
        assert reset_res.get_json()["status"] == "success"

        assert user_tokens[0]["usado"] == 1

        old_login = client.post("/auth/do_login", json={"email": email, "password": "Operador123*"})
        assert old_login.status_code == 401

        new_login = client.post("/auth/do_login", json={"email": email, "password": "NuevaPassword123*"})
        assert new_login.status_code == 200
        assert new_login.get_json()["user"]["nombre"] == "Operador"
