import pytest


class TestRoleIntegration:
    """Pruebas de integración para el módulo de Roles y Permisos (/api/roles/).

    Valida la gestión de roles, protección del rol 'Administrador',
    asignación granular de permisos por módulo y validaciones de datos.
    """

    def test_get_roles_unauthenticated_returns_401(self, client):
        """Verifica que sin sesión activa no se puedan listar roles."""
        response = client.get("/api/roles/")
        assert response.status_code == 401
        assert response.get_json()["status"] == "error"

    def test_get_all_active_roles(self, auth_client):
        """Verifica que un usuario autenticado pueda listar los roles activos."""
        response = auth_client.get("/api/roles/")
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "success"
        roles = data["data"]
        assert len(roles) >= 3

        # Los roles activos deben incluir Administrador y Operador
        nombres = [r["nombre"] for r in roles]
        assert "Administrador" in nombres
        assert "Operador" in nombres
        # El rol inactivo (estado = 0) no debe aparecer
        assert "Rol Inactivo" not in nombres

    def test_get_single_role_with_permissions(self, auth_client):
        """Verifica la consulta de un rol específico con su matriz de permisos."""
        # 1. Rol existente (Administrador)
        res_admin = auth_client.get("/api/roles/1")
        assert res_admin.status_code == 200
        data = res_admin.get_json()["data"]
        assert data["id"] == 1
        assert data["nombre"] == "Administrador"
        assert "permisos" in data
        assert len(data["permisos"]) >= 1

        # 2. Rol inexistente retorna 404
        res_none = auth_client.get("/api/roles/99999")
        assert res_none.status_code == 404
        assert res_none.get_json()["status"] == "error"

    def test_create_role_with_granular_permissions(self, auth_client, mock_db):
        """Verifica la creación de un nuevo rol con asignación atómica de permisos por módulo."""
        payload = {
            "nombre": "Auditor Interno",
            "descripcion": "Rol con permisos de solo lectura para auditoría",
            "permisos": [
                {"modulo": "bitacora", "crear": 0, "leer": 1, "actualizar": 0, "eliminar": 0},
                {"modulo": "usuarios", "crear": 0, "leer": 1, "actualizar": 0, "eliminar": 0}
            ]
        }
        response = auth_client.post("/api/roles/", json=payload)
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "success"
        role_id = data["id"]

        # Verificar en mock_db.roles
        assert role_id in mock_db.roles
        new_role = mock_db.roles[role_id]
        assert new_role["nombre"] == "Auditor Interno"
        assert new_role["estado"] == 1

        # Verificar en mock_db.permisos
        role_perms = [p for p in mock_db.permisos if p["rol_id"] == role_id]
        assert len(role_perms) == 2
        mod_names = [p["modulo"] for p in role_perms]
        assert "bitacora" in mod_names
        assert "usuarios" in mod_names

    def test_create_role_validation_failure(self, auth_client):
        """Verifica que nombres de rol inválidos o vacíos retornen 400 con mensaje de error."""
        # Nombre demasiado corto (< 3 caracteres)
        bad_payload = {"nombre": "No", "descripcion": "Rol inválido"}
        response = auth_client.post("/api/roles/", json=bad_payload)
        assert response.status_code == 400
        data = response.get_json()
        assert data["status"] == "error"
        assert "nombre" in data["errors"]

    def test_update_role_and_permissions(self, auth_client, mock_db):
        """Verifica la actualización de nombre, descripción y permisos de un rol existente."""
        # Crear un rol temporal para actualizar
        new_rid = mock_db.next_role_id
        mock_db.next_role_id += 1
        mock_db.roles[new_rid] = {
            "id": new_rid,
            "nombre": "Rol Temporal",
            "descripcion": "Descripción inicial",
            "estado": 1
        }

        update_payload = {
            "nombre": "Rol Modificado",
            "descripcion": "Nueva descripción actualizada",
            "permisos": [
                {"modulo": "mecanicos", "crear": 1, "leer": 1, "actualizar": 1, "eliminar": 0}
            ]
        }
        response = auth_client.put(f"/api/roles/{new_rid}", json=update_payload)
        assert response.status_code == 200
        assert response.get_json()["status"] == "success"

        # Verificar cambios en el rol
        updated = mock_db.roles[new_rid]
        assert updated["nombre"] == "Rol Modificado"
        assert updated["descripcion"] == "Nueva descripción actualizada"

        # Verificar permisos actualizados
        perms = [p for p in mock_db.permisos if p["rol_id"] == new_rid]
        assert len(perms) == 1
        assert perms[0]["modulo"] == "mecanicos"
        assert perms[0]["crear"] == 1

    def test_prevent_deleting_administrator_role(self, auth_client, mock_db):
        """Regla de seguridad crítica: el rol 'Administrador' (id: 1) jamás puede ser eliminado."""
        response = auth_client.delete("/api/roles/1")
        assert response.status_code == 400
        data = response.get_json()
        assert data["status"] == "error"
        assert "no se puede eliminar el rol administrador" in data["message"].lower()

        # Asegurar que sigue activo en la base de datos
        assert mock_db.roles[1]["estado"] == 1

    def test_delete_non_existent_role_returns_404(self, auth_client):
        """Verifica que intentar eliminar un rol que no existe retorne 404."""
        response = auth_client.delete("/api/roles/99999")
        assert response.status_code == 404
        assert response.get_json()["status"] == "error"

    def test_soft_delete_custom_role(self, auth_client, mock_db):
        """Verifica el soft delete exitoso de un rol secundario (estado cambia a 0)."""
        # Crear rol secundario
        new_rid = mock_db.next_role_id
        mock_db.next_role_id += 1
        mock_db.roles[new_rid] = {
            "id": new_rid,
            "nombre": "Rol a Eliminar",
            "descripcion": "Rol prescindible",
            "estado": 1
        }

        response = auth_client.delete(f"/api/roles/{new_rid}")
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "success"

        # Debe tener estado = 0
        assert mock_db.roles[new_rid]["estado"] == 0

    def test_get_and_save_role_permissions_endpoints(self, auth_client, mock_db):
        """Verifica los endpoints dedicados de consulta y guardado masivo de permisos para un rol."""
        # 1. Consultar permisos actuales del rol Operador (id 2)
        res_get = auth_client.get("/api/roles/2/permissions")
        assert res_get.status_code == 200
        assert res_get.get_json()["status"] == "success"

        # 2. Guardar nuevos permisos masivos vía POST /api/roles/<id>/permissions
        new_perms = [
            {"modulo": "servicios", "crear": 0, "leer": 1, "actualizar": 0, "eliminar": 0},
            {"modulo": "mecanicos", "crear": 0, "leer": 1, "actualizar": 0, "eliminar": 0}
        ]
        res_save = auth_client.post("/api/roles/2/permissions", json={"permisos": new_perms})
        assert res_save.status_code == 200

        # Verificar que mock_db.permisos refleja los nuevos permisos
        saved_perms = [p for p in mock_db.permisos if p["rol_id"] == 2]
        assert len(saved_perms) == 2
        modulos_saved = {p["modulo"] for p in saved_perms}
        assert modulos_saved == {"servicios", "mecanicos"}

    def test_get_available_modules_for_roles(self, auth_client):
        """Verifica el endpoint GET /api/roles/modules que provee los módulos disponibles para configuración de RBAC."""
        response = auth_client.get("/api/roles/modules")
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "success"
        modules = data["data"]
        assert len(modules) >= 1
        assert any(m.get("modulo") == "modulos" or m.get("nombre_modulo") == "modulos" for m in modules)
