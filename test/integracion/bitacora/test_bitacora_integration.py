import pytest


class TestBitacoraIntegration:
    """Pruebas de integración para el módulo de Auditoría y Bitácora (/api/bitacora/).

    Valida la captura cronológica de eventos, trazabilidad por usuario y módulo,
    paginación, búsquedas contextuales y rangos de fecha.
    """

    def test_get_bitacora_unauthenticated_returns_401(self, client):
        """Verifica que sin sesión activa no se pueda consultar la bitácora."""
        response = client.get("/api/bitacora/")
        assert response.status_code == 401
        assert response.get_json()["status"] == "error"

    def test_get_all_bitacora_with_pagination(self, auth_client, mock_db):
        """Verifica la consulta paginada de eventos de auditoría y los metadatos de paginación."""
        # Asegurar que existan registros
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
        assert "nombre" in first_log  # Enriquecido con JOIN a usuarios

    def test_get_bitacora_by_user(self, auth_client, mock_db):
        """Verifica el filtrado de eventos de bitácora por un usuario específico."""
        # Agregar evento del usuario 2
        mock_db.bitacora.append({
            "id": len(mock_db.bitacora) + 1,
            "usuario_id": 2,
            "accion": "UPDATE",
            "modulo": "SERVICIOS",
            "descripcion": "Modificación de servicio de prueba",
            "ip": "127.0.0.1",
            "fecha": "2026-10-19 11:30:00"
        })

        # 1. Consultar eventos del usuario 2
        response = auth_client.get("/api/bitacora/user/2")
        assert response.status_code == 200
        logs = response.get_json()["data"]
        assert len(logs) >= 1
        assert all(log["usuario_id"] == 2 for log in logs)

        # 2. Sin autenticación retorna 401
        res_unauth = auth_client.application.test_client().get("/api/bitacora/user/2")
        assert res_unauth.status_code == 401

    def test_get_bitacora_by_module(self, auth_client, mock_db):
        """Verifica el filtrado de eventos de bitácora por clave de módulo."""
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
        """Verifica la búsqueda de eventos por coincidencia en acción, módulo o descripción."""
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

        # 1. Búsqueda con resultado
        res_found = auth_client.get(f"/api/bitacora/search?q={unique_token}")
        assert res_found.status_code == 200
        logs = res_found.get_json()["data"]
        assert len(logs) == 1
        assert unique_token in logs[0]["descripcion"]

        # 2. Búsqueda sin resultado
        res_empty = auth_client.get("/api/bitacora/search?q=TerminoInexistente999XYZ")
        assert res_empty.status_code == 200
        assert len(res_empty.get_json()["data"]) == 0

    def test_filter_bitacora_by_date_range(self, auth_client, mock_db):
        """Verifica el filtrado de eventos por rango de fechas (start y end)."""
        mock_db.bitacora.append({
            "id": len(mock_db.bitacora) + 1,
            "usuario_id": 1,
            "accion": "BACKUP",
            "modulo": "SISTEMA",
            "descripcion": "Respaldo diario",
            "ip": "127.0.0.1",
            "fecha": "2026-10-15 04:00:00"
        })

        # 1. Consulta válida por rango
        res_range = auth_client.get("/api/bitacora/filter?start=2026-10-01&end=2026-10-31")
        assert res_range.status_code == 200
        logs = res_range.get_json()["data"]
        assert len(logs) >= 1

        # 2. Rango con fechas faltantes retorna 400
        res_bad = auth_client.get("/api/bitacora/filter?start=2026-10-01")
        assert res_bad.status_code == 400
        assert res_bad.get_json()["status"] == "error"

    def test_cross_module_audit_trail_upon_auth_action(self, client, auth_client, mock_db):
        """Prueba de integración cruzada: una acción en Auth (login) genera un evento auditable

        inmediatamente consultable a través de la API de Bitácora.
        """
        # 1. Login vía /auth/do_login
        login_res = client.post("/auth/do_login", json={"email": "admin@transalca.com", "password": "Admin123*"})
        assert login_res.status_code == 200

        # 2. Consultar Bitácora para verificar el registro del evento LOGIN
        bitacora_res = auth_client.get("/api/bitacora/module/AUTH")
        assert bitacora_res.status_code == 200
        logs = bitacora_res.get_json()["data"]

        login_logs = [l for l in logs if l["accion"] == "LOGIN" and "admin@transalca.com" in l["descripcion"]]
        assert len(login_logs) >= 1
