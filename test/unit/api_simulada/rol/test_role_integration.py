import pytest


class TestRoleIntegration:

    def test_get_roles_unauthenticated_returns_401(self, client):
        response = client.get("/api/roles/")
        assert response.status_code == 401
        assert response.get_json()["status"] == "error"

    def test_get_all_active_roles(self, auth_client):
        response = auth_client.get("/api/roles/")
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "success"
        roles = data["data"]
        assert len(roles) >= 3

        nombres = [r["nombre"] for r in roles]
        assert "Administrador" in nombres
        assert "Operador" in nombres
        assert "Rol Inactivo" not in nombres

    def test_get_single_role_with_permissions(self, auth_client):
        res_admin = auth_client.get("/api/roles/1")
        assert res_admin.status_code == 200
        data = res_admin.get_json()["data"]
        assert data["id"] == 1
        assert data["nombre"] == "Administrador"
        assert "permisos" in data
        assert len(data["permisos"]) >= 1

        res_none = auth_client.get("/api/roles/99999")
        assert res_none.status_code == 404
        assert res_none.get_json()["status"] == "error"

    def test_create_role_with_granular_permissions(self, auth_client, mock_db):
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

        assert role_id in mock_db.roles
        new_role = mock_db.roles[role_id]
        assert new_role["nombre"] == "Auditor Interno"
        assert new_role["estado"] == 1

        role_perms = [p for p in mock_db.permisos if p["rol_id"] == role_id]
        assert len(role_perms) == 2
        mod_names = [p["modulo"] for p in role_perms]
        assert "bitacora" in mod_names
        assert "usuarios" in mod_names

    def test_create_role_validation_failure(self, auth_client):
        bad_payload = {"nombre": "No", "descripcion": "Rol inválido"}
        response = auth_client.post("/api/roles/", json=bad_payload)
        assert response.status_code == 400
        data = response.get_json()
        assert data["status"] == "error"
        assert "nombre" in data["errors"]

    def test_update_role_and_permissions(self, auth_client, mock_db):
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

        updated = mock_db.roles[new_rid]
        assert updated["nombre"] == "Rol Modificado"
        assert updated["descripcion"] == "Nueva descripción actualizada"

        perms = [p for p in mock_db.permisos if p["rol_id"] == new_rid]
        assert len(perms) == 1
        assert perms[0]["modulo"] == "mecanicos"
        assert perms[0]["crear"] == 1

    def test_prevent_deleting_administrator_role(self, auth_client, mock_db):
        response = auth_client.delete("/api/roles/1")
        assert response.status_code == 400
        data = response.get_json()
        assert data["status"] == "error"
        assert "no se puede eliminar el rol administrador" in data["message"].lower()

        assert mock_db.roles[1]["estado"] == 1

    def test_delete_non_existent_role_returns_404(self, auth_client):
        response = auth_client.delete("/api/roles/99999")
        assert response.status_code == 404
        assert response.get_json()["status"] == "error"

    def test_soft_delete_custom_role(self, auth_client, mock_db):
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

        assert mock_db.roles[new_rid]["estado"] == 0

    def test_get_and_save_role_permissions_endpoints(self, auth_client, mock_db):
        res_get = auth_client.get("/api/roles/2/permissions")
        assert res_get.status_code == 200
        assert res_get.get_json()["status"] == "success"

        new_perms = [
            {"modulo": "servicios", "crear": 0, "leer": 1, "actualizar": 0, "eliminar": 0},
            {"modulo": "mecanicos", "crear": 0, "leer": 1, "actualizar": 0, "eliminar": 0}
        ]
        res_save = auth_client.post("/api/roles/2/permissions", json={"permisos": new_perms})
        assert res_save.status_code == 200

        saved_perms = [p for p in mock_db.permisos if p["rol_id"] == 2]
        assert len(saved_perms) == 2
        modulos_saved = {p["modulo"] for p in saved_perms}
        assert modulos_saved == {"servicios", "mecanicos"}

    def test_get_available_modules_for_roles(self, auth_client):
        response = auth_client.get("/api/roles/modules")
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "success"
        modules = data["data"]
        assert len(modules) >= 1
        assert any(m.get("modulo") == "modulos" or m.get("nombre_modulo") == "modulos" for m in modules)
