import pytest


class TestAuthIntegration:
    """Pruebas de integración para el módulo de Autenticación (Auth).

    Valida el inicio de sesión, poblamiento de sesión con roles y permisos,
    registro de eventos en bitácora, registro de clientes con sincronización
    cruzada a Transalca, y recuperación/reinicio de contraseña.
    """

    def test_login_success_populates_session_and_logs(self, client, mock_db):
        """Verifica que el login exitoso configure la sesión, asigne roles/permisos

        y registre el evento en la bitácora de auditoría.
        """
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

        # Verificar endpoint de sesión
        sess_res = client.get("/auth/session")
        assert sess_res.status_code == 200
        sess_data = sess_res.get_json()["user"]
        assert sess_data["email"] == "admin@transalca.com"
        assert "Administrador" in sess_data["roles"]
        assert "usuarios" in sess_data["permisos"]

        # Verificar que se registró el evento en la bitácora
        last_log = mock_db.bitacora[-1]
        assert last_log["accion"] == "LOGIN"
        assert last_log["modulo"] == "AUTH"
        assert "admin@transalca.com" in last_log["descripcion"]

    def test_login_invalid_password_fails_401(self, client):
        """Verifica que credenciales erróneas retornen 401."""
        response = client.post("/auth/do_login", json={
            "email": "admin@transalca.com",
            "password": "PasswordEquivocada99*"
        })
        assert response.status_code == 401
        assert response.get_json()["status"] == "error"

    def test_login_inactive_user_rejected_403(self, client):
        """Verifica que un usuario inactivo (estado = 0) no pueda iniciar sesión."""
        response = client.post("/auth/do_login", json={
            "email": "inactivo@transalca.com",
            "password": "Inactivo123*"
        })
        assert response.status_code == 403
        data = response.get_json()
        assert data["status"] == "error"
        assert "inactivo" in data["message"].lower()

    def test_client_login_redirects_to_client_portal(self, client):
        """Verifica que el login de un usuario tipo cliente redirija a /client/home."""
        response = client.post("/auth/do_login", json={
            "email": "cliente@transalca.com",
            "password": "Cliente123*"
        })
        assert response.status_code == 200
        data = response.get_json()
        assert data["redirect"] == "/client/home"
        assert data["user"]["tipo"] == "cliente"

    def test_session_unauthenticated_returns_401(self, client):
        """Verifica que consultar la sesión sin login activo retorne 401."""
        response = client.get("/auth/session")
        assert response.status_code == 401
        assert response.get_json()["status"] == "error"

    def test_logout_clears_session_and_logs_event(self, client, mock_db):
        """Verifica que el cierre de sesión limpie las cookies de sesión y registre en bitácora."""
        # 1. Iniciar sesión
        client.post("/auth/do_login", json={"email": "admin@transalca.com", "password": "Admin123*"})
        assert client.get("/auth/session").status_code == 200

        # 2. Cerrar sesión
        res_logout = client.post("/auth/logout")
        assert res_logout.status_code == 200
        assert res_logout.get_json()["status"] == "success"

        # 3. La sesión ya no existe
        assert client.get("/auth/session").status_code == 401

        # 4. Se registró el evento LOGOUT
        last_log = mock_db.bitacora[-1]
        assert last_log["accion"] == "LOGOUT"
        assert last_log["modulo"] == "AUTH"

    def test_register_client_with_cross_module_transalca_sync(self, client, mock_db):
        """Prueba de integración cruzada: al registrarse un cliente en Auth, se crea

        su cuenta de usuario en db_mantenimiento y simultáneamente su perfil en la tabla
        cliente de db_transalca.
        """
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

        # 1. Verificar persistencia en usuarios (mantenimiento)
        created_user = next((u for u in mock_db.usuarios.values() if u["email"] == "elena.rivas@correo.com"), None)
        assert created_user is not None
        assert created_user["tipo"] == "cliente"
        assert created_user["cedula"] == "V-55667788"

        # 2. Verificar sincronización en cliente (transalca)
        assert "V-55667788" in mock_db.clientes
        cli_record = mock_db.clientes["V-55667788"]
        assert cli_record["nombre_cliente"] == "Elena"
        assert cli_record["correo_cliente"] == "elena.rivas@correo.com"

        # 3. Iniciar sesión inmediatamente con la nueva cuenta
        login_res = client.post("/auth/do_login", json={
            "email": "elena.rivas@correo.com",
            "password": "Password123*"
        })
        assert login_res.status_code == 200
        assert login_res.get_json()["user"]["nombre"] == "Elena"

    def test_check_unique_endpoint_integration(self, client):
        """Verifica la comprobación en tiempo real de email y cédula."""
        # Email existente
        res_email_taken = client.post("/auth/check-unique", json={"field": "email", "value": "admin@transalca.com"})
        assert res_email_taken.status_code == 200
        assert res_email_taken.get_json()["exists"] is True

        # Email nuevo
        res_email_free = client.post("/auth/check-unique", json={"field": "email", "value": "nuevo@transalca.com"})
        assert res_email_free.status_code == 200
        assert res_email_free.get_json()["exists"] is False

        # Cédula existente
        res_ced_taken = client.post("/auth/check-unique", json={"field": "cedula", "value": "V-10000000"})
        assert res_ced_taken.status_code == 200
        assert res_ced_taken.get_json()["exists"] is True

        # Cédula libre
        res_ced_free = client.post("/auth/check-unique", json={"field": "cedula", "value": "V-99999999"})
        assert res_ced_free.status_code == 200
        assert res_ced_free.get_json()["exists"] is False

    def test_password_recovery_and_reset_integration_flow(self, client, mock_db):
        """Flujo completo de recuperación de contraseña:

        1. Solicitud de token vía /do_recover.
        2. Verificación de generación de token en tokens_recuperacion.
        3. Restablecimiento exitoso vía /do_reset con validación de complejidad.
        4. Comprobación de que el token queda marcado como 'usado'.
        5. Login con la nueva contraseña.
        """
        email = "operador@transalca.com"

        # 1. Solicitar recuperación
        rec_res = client.post("/auth/do_recover", json={"email": email})
        assert rec_res.status_code == 200
        assert rec_res.get_json()["status"] == "success"

        # 2. Extraer token generado
        user_tokens = [t for t in mock_db.tokens_recuperacion.values() if t["usuario_id"] == 2 and t["usado"] == 0]
        assert len(user_tokens) == 1
        recovery_token = user_tokens[0]["token"]

        # 3. Restablecer con contraseña que cumple políticas de seguridad
        reset_res = client.post("/auth/do_reset", json={
            "token": recovery_token,
            "password": "NuevaPassword123*",
            "confirm_password": "NuevaPassword123*"
        })
        assert reset_res.status_code == 200
        assert reset_res.get_json()["status"] == "success"

        # 4. El token ahora está marcado como usado (usado = 1)
        assert user_tokens[0]["usado"] == 1

        # 5. Intentar login con la contraseña antigua -> Falla 401
        old_login = client.post("/auth/do_login", json={"email": email, "password": "Operador123*"})
        assert old_login.status_code == 401

        # 6. Intentar login con la nueva contraseña -> Éxito 200
        new_login = client.post("/auth/do_login", json={"email": email, "password": "NuevaPassword123*"})
        assert new_login.status_code == 200
        assert new_login.get_json()["user"]["nombre"] == "Operador"
