import pytest


class TestUserIntegration:
    """Pruebas de integración para el módulo de Gestión de Usuarios (/api/users/).

    Valida el ciclo completo de vida del usuario, RBAC, reglas de integridad
    (prevención de eliminación/degradación del último administrador),
    validaciones y búsqueda.
    """

    def test_get_users_unauthenticated_returns_401(self, client):
        """Verifica que sin sesión activa no se puedan listar usuarios."""
        response = client.get("/api/users/")
        assert response.status_code == 401
        assert response.get_json()["status"] == "error"

    def test_get_all_users_authenticated_with_roles(self, auth_client, mock_db):
        """Verifica que un usuario autenticado pueda listar los usuarios activos con sus roles concatenados."""
        response = auth_client.get("/api/users/")
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "success"
        users = data["data"]
        assert len(users) >= 2

        # Administrador inicial debe tener su rol asignado
        admin = next((u for u in users if u["id"] == 1), None)
        assert admin is not None
        assert "Administrador" in admin["roles"]

    def test_get_users_filtered_by_tipo(self, auth_client):
        """Verifica el filtrado de usuarios por tipo (empleado vs cliente)."""
        # 1. Filtro por empleado
        res_emp = auth_client.get("/api/users/?tipo=empleado")
        assert res_emp.status_code == 200
        emps = res_emp.get_json()["data"]
        assert all(u["tipo"] == "empleado" for u in emps)

        # 2. Filtro por cliente
        res_cli = auth_client.get("/api/users/?tipo=cliente")
        assert res_cli.status_code == 200
        clis = res_cli.get_json()["data"]
        assert all(u["tipo"] == "cliente" for u in clis)

        # 3. Tipo inválido retorna 400
        res_inv = auth_client.get("/api/users/?tipo=hacker")
        assert res_inv.status_code == 400
        assert res_inv.get_json()["status"] == "error"

    def test_get_single_user_found_and_not_found(self, auth_client):
        """Verifica la obtención de detalle de usuario por ID con roles asociados."""
        # Usuario existente
        res_found = auth_client.get("/api/users/1")
        assert res_found.status_code == 200
        user = res_found.get_json()["data"]
        assert user["id"] == 1
        assert user["email"] == "admin@transalca.com"
        assert any(r["nombre"] == "Administrador" for r in user["roles"])

        # Usuario inexistente
        res_not_found = auth_client.get("/api/users/99999")
        assert res_not_found.status_code == 404
        assert res_not_found.get_json()["status"] == "error"

    def test_check_unique_endpoint_integration(self, auth_client):
        """Verifica la validación de unicidad de email y cédula considerando exclusión por ID."""
        # 1. Email ocupado
        res_email = auth_client.post("/api/users/check-unique", json={"field": "email", "value": "admin@transalca.com"})
        assert res_email.status_code == 200
        assert res_email.get_json()["exists"] is True

        # 2. Email del propio usuario (excluyendo su ID) no debe dar ocupado
        res_email_excl = auth_client.post("/api/users/check-unique", json={"field": "email", "value": "admin@transalca.com", "exclude": 1})
        assert res_email_excl.status_code == 200
        assert res_email_excl.get_json()["exists"] is False

        # 3. Cédula ocupada
        res_ced = auth_client.post("/api/users/check-unique", json={"field": "cedula", "value": "V-10000000"})
        assert res_ced.status_code == 200
        assert res_ced.get_json()["exists"] is True

        # 4. Cédula libre
        res_ced_free = auth_client.post("/api/users/check-unique", json={"field": "cedula", "value": "V-99988877"})
        assert res_ced_free.status_code == 200
        assert res_ced_free.get_json()["exists"] is False

    def test_create_employee_success_assigns_role(self, auth_client, mock_db):
        """Verifica la creación exitosa de un empleado y la asignación atómica de su rol."""
        payload = {
            "nombre": "Carlos",
            "apellido": "Mendoza",
            "cedula": "V-22334455",
            "email": "carlos.mendoza@transalca.com",
            "telefono": "04121112233",
            "direccion": "Zona Industrial II",
            "tipo": "empleado",
            "rol_id": 2,  # Operador
            "password": "Password123*",
            "confirm_password": "Password123*"
        }
        response = auth_client.post("/api/users/", json=payload)
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "success"
        user_id = data["id"]

        # Verificar en usuarios
        assert user_id in mock_db.usuarios
        created = mock_db.usuarios[user_id]
        assert created["nombre"] == "Carlos"
        assert created["email"] == "carlos.mendoza@transalca.com"
        assert created["estado"] == 1

        # Verificar en usuario_rol
        assigned_role = next((ur for ur in mock_db.usuario_rol if ur["usuario_id"] == user_id), None)
        assert assigned_role is not None
        assert assigned_role["rol_id"] == 2

    def test_create_user_validation_failures(self, auth_client):
        """Verifica que errores de validación (contraseña débil, correo inválido, rol inexistente) retornen 400."""
        # 1. Contraseña débil
        bad_pw_payload = {
            "nombre": "Pedro",
            "apellido": "Pérez",
            "cedula": "V-33445566",
            "email": "pedro@transalca.com",
            "rol_id": 2,
            "password": "123",  # Débil
            "confirm_password": "123"
        }
        res_pw = auth_client.post("/api/users/", json=bad_pw_payload)
        assert res_pw.status_code == 400
        assert "password" in res_pw.get_json()["errors"]

        # 2. Correo inválido
        bad_email_payload = {
            "nombre": "Pedro",
            "apellido": "Pérez",
            "cedula": "V-33445566",
            "email": "correo_no_valido",
            "rol_id": 2,
            "password": "Password123*",
            "confirm_password": "Password123*"
        }
        res_em = auth_client.post("/api/users/", json=bad_email_payload)
        assert res_em.status_code == 400
        assert "email" in res_em.get_json()["errors"]

        # 3. Rol inexistente
        bad_rol_payload = {
            "nombre": "Pedro",
            "apellido": "Pérez",
            "cedula": "V-33445566",
            "email": "pedro@transalca.com",
            "rol_id": 99999,  # Inexistente
            "password": "Password123*",
            "confirm_password": "Password123*"
        }
        res_rol = auth_client.post("/api/users/", json=bad_rol_payload)
        assert res_rol.status_code == 400
        assert "rol_id" in res_rol.get_json()["errors"]

    def test_create_user_duplicate_cedula_or_email_fails(self, auth_client):
        """Verifica que intentar registrar cédula o email duplicados sea rechazado con 400."""
        # Cédula duplicada
        dup_ced = {
            "nombre": "Clon",
            "apellido": "Admin",
            "cedula": "V-10000000",  # Ya pertenece al admin
            "email": "otro.correo@transalca.com",
            "rol_id": 2,
            "password": "Password123*",
            "confirm_password": "Password123*"
        }
        res1 = auth_client.post("/api/users/", json=dup_ced)
        assert res1.status_code == 400
        assert "cedula" in res1.get_json()["errors"]

        # Email duplicado
        dup_em = {
            "nombre": "Clon",
            "apellido": "Admin",
            "cedula": "V-77889900",
            "email": "admin@transalca.com",  # Ya pertenece al admin
            "rol_id": 2,
            "password": "Password123*",
            "confirm_password": "Password123*"
        }
        res2 = auth_client.post("/api/users/", json=dup_em)
        assert res2.status_code == 400
        assert "email" in res2.get_json()["errors"]

    def test_update_user_info_and_role_change(self, auth_client, mock_db):
        """Verifica la actualización de datos de un usuario y el cambio de rol."""
        update_payload = {
            "nombre": "Operador",
            "apellido": "Actualizado",
            "cedula": "V-20000000",
            "email": "operador.modificado@transalca.com",
            "telefono": "04149998877",
            "direccion": "Calle Central",
            "tipo": "empleado",
            "rol_id": 1  # Promover a Administrador
        }
        response = auth_client.put("/api/users/2", json=update_payload)
        assert response.status_code == 200
        assert response.get_json()["status"] == "success"

        # Verificar persistencia en mock_db
        user_2 = mock_db.usuarios[2]
        assert user_2["apellido"] == "Actualizado"
        assert user_2["email"] == "operador.modificado@transalca.com"

        # Verificar que el rol fue cambiado a Administrador (rol_id 1)
        roles_user_2 = [ur["rol_id"] for ur in mock_db.usuario_rol if ur["usuario_id"] == 2]
        assert 1 in roles_user_2

    def test_prevent_demoting_last_active_admin(self, auth_client, mock_db):
        """Regla de seguridad crítica: el último administrador activo no puede ser degradado a otro rol."""
        # Asegurar que solo hay un administrador (usuario 1)
        mock_db.usuario_rol = [ur for ur in mock_db.usuario_rol if not (ur["rol_id"] == 1 and ur["usuario_id"] != 1)]

        demote_payload = {
            "nombre": "Admin",
            "apellido": "Sistema",
            "cedula": "V-10000000",
            "email": "admin@transalca.com",
            "telefono": "04141234567",
            "direccion": "Sede Principal",
            "tipo": "empleado",
            "rol_id": 2  # Intentar degradar a Operador
        }
        response = auth_client.put("/api/users/1", json=demote_payload)
        assert response.status_code == 400
        assert "rol_id" in response.get_json()["errors"]
        assert "último administrador" in response.get_json()["errors"]["rol_id"].lower()

    def test_toggle_user_status(self, auth_client, mock_db):
        """Verifica el cambio de estado (activar / desactivar) vía PUT /api/users/<id>/status."""
        # 1. Desactivar usuario 2
        res_deact = auth_client.put("/api/users/2/status", json={"estado": 0})
        assert res_deact.status_code == 200
        assert mock_db.usuarios[2]["estado"] == 0

        # 2. Reactivar usuario 2
        res_act = auth_client.put("/api/users/2/status", json={"estado": 1})
        assert res_act.status_code == 200
        assert mock_db.usuarios[2]["estado"] == 1

        # 3. Estado inválido retorna 400
        res_bad = auth_client.put("/api/users/2/status", json={"estado": "invalido"})
        assert res_bad.status_code == 400

    def test_soft_delete_prevents_deleting_last_admin(self, auth_client, mock_db):
        """Regla de seguridad crítica: no se puede eliminar mediante soft delete al último administrador."""
        # Asegurar que solo el usuario 1 es administrador
        mock_db.usuario_rol = [ur for ur in mock_db.usuario_rol if not (ur["rol_id"] == 1 and ur["usuario_id"] != 1)]

        response = auth_client.delete("/api/users/1")
        assert response.status_code == 400
        assert "ultimo administrador" in response.get_json()["message"].lower()
        assert mock_db.usuarios[1]["estado"] == 1  # Sigue activo

    def test_soft_delete_user_success(self, auth_client, mock_db):
        """Verifica el soft delete exitoso de un usuario ordinario."""
        response = auth_client.delete("/api/users/2")
        assert response.status_code == 200
        assert response.get_json()["status"] == "success"
        assert mock_db.usuarios[2]["estado"] == 0

    def test_search_users_by_query(self, auth_client):
        """Verifica la búsqueda de usuarios por coincidencia en nombre, apellido o email."""
        # Coincidencia con admin
        res_admin = auth_client.get("/api/users/search?q=Admin")
        assert res_admin.status_code == 200
        results = res_admin.get_json()["data"]
        assert any(u["email"] == "admin@transalca.com" for u in results)

        # Sin coincidencias
        res_none = auth_client.get("/api/users/search?q=NoExisteNunca99")
        assert res_none.status_code == 200
        assert len(res_none.get_json()["data"]) == 0

    def test_reactivate_inactive_user_upon_create(self, auth_client, mock_db):
        """Verifica que si se crea un usuario con la cédula de uno previamente inactivo,

        el sistema lo reactiva con la nueva contraseña y el nuevo rol.
        """
        # Usuario 3 está inactivo en mock_db (inactivo@transalca.com, V-30000000)
        assert mock_db.usuarios[3]["estado"] == 0

        reactivate_payload = {
            "nombre": "Usuario",
            "apellido": "Reactivado",
            "cedula": "V-30000000",
            "email": "reactivado@transalca.com",
            "telefono": "04123334455",
            "direccion": "Sede Nueva",
            "tipo": "empleado",
            "rol_id": 2,
            "password": "NuevaPassword123*",
            "confirm_password": "NuevaPassword123*"
        }
        response = auth_client.post("/api/users/", json=reactivate_payload)
        assert response.status_code == 200
        data = response.get_json()
        assert data["id"] == 3

        # Verificar que el usuario 3 ahora está activo y con sus datos actualizados
        u3 = mock_db.usuarios[3]
        assert u3["estado"] == 1
        assert u3["nombre"] == "Usuario"
        assert u3["apellido"] == "Reactivado"
