import pytest


class TestModuloIntegration:
    """Pruebas de integración para el módulo de Módulos del Sistema (/api/modulos/).

    Valida la configuración dinámica del sistema, filtrado RBAC del menú sidebar,
    validaciones de slugs y rutas internas, y ciclo de vida de los módulos.
    """

    def test_get_modulos_unauthenticated_returns_401(self, client):
        """Verifica que sin sesión activa no se puedan listar los módulos del sistema."""
        response = client.get("/api/modulos/")
        assert response.status_code in (401, 302)

    def test_get_all_modulos_with_admin_permission(self, auth_client):
        """Verifica que un usuario con permiso de lectura (o admin) obtenga el catálogo de módulos activos."""
        response = auth_client.get("/api/modulos/")
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "success"
        modules = data["data"]
        assert len(modules) >= 1
        assert any(m.get("nombre") == "modulos" or m.get("nombre_modulo") == "modulos" for m in modules)

    def test_sidebar_filtering_for_admin_vs_operator(self, auth_client, operator_client, mock_db):
        """Verifica que el menú lateral (/sidebar) filtre dinámicamente los módulos según el RBAC

        del usuario logueado (admin ve todos, operador solo los que tiene permiso).
        """
        # 1. Admin ve todos los módulos activos del sidebar
        res_admin = auth_client.get("/api/modulos/sidebar")
        assert res_admin.status_code == 200
        sidebar_admin = res_admin.get_json()["data"]
        admin_names = [m["nombre"] for m in sidebar_admin]
        assert "modulos" in admin_names

        # 2. Configurar permisos del operador sin acceso al módulo 'modulos'
        with operator_client.session_transaction() as sess:
            sess["permisos"] = {
                "usuarios": {"crear": 0, "leer": 1, "actualizar": 0, "eliminar": 0}
            }

        res_op = operator_client.get("/api/modulos/sidebar")
        assert res_op.status_code == 200
        sidebar_op = res_op.get_json()["data"]
        op_names = [m["nombre"] for m in sidebar_op]
        assert "modulos" not in op_names
        assert "usuarios" in op_names

    def test_permissions_list_endpoint(self, auth_client):
        """Verifica el endpoint /permissions-list utilizado para renderizar la matriz de permisos."""
        response = auth_client.get("/api/modulos/permissions-list")
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "success"
        items = data["data"]
        assert len(items) >= 1
        assert any(m.get("modulo") == "modulos" or m.get("nombre_modulo") == "modulos" for m in items)

    def test_check_unique_slug_and_route(self, auth_client):
        """Verifica la validación en tiempo real de unicidad de nombre (slug) y ruta interna."""
        # 1. Clave existente
        res_slug_taken = auth_client.get("/api/modulos/check-unique?field=nombre&value=modulos")
        assert res_slug_taken.status_code == 200
        assert res_slug_taken.get_json()["unique"] is False

        # 2. Clave libre
        res_slug_free = auth_client.get("/api/modulos/check-unique?field=nombre&value=modulo_nuevo_totalmente")
        assert res_slug_free.status_code == 200
        assert res_slug_free.get_json()["unique"] is True

        # 3. Clave existente pero excluida por su propio ID
        res_slug_excl = auth_client.get("/api/modulos/check-unique?field=nombre&value=modulos&exclude=1")
        assert res_slug_excl.status_code == 200
        assert res_slug_excl.get_json()["unique"] is True

        # 4. Ruta existente
        res_ruta_taken = auth_client.get("/api/modulos/check-unique?field=ruta&value=/admin/modulos")
        assert res_ruta_taken.status_code == 200
        assert res_ruta_taken.get_json()["unique"] is False

        # 5. Ruta libre
        res_ruta_free = auth_client.get("/api/modulos/check-unique?field=ruta&value=/admin/ruta_libre")
        assert res_ruta_free.status_code == 200
        assert res_ruta_free.get_json()["unique"] is True

    def test_get_single_modulo_detail(self, auth_client):
        """Verifica la consulta de un módulo por ID."""
        # Módulo existente
        res_found = auth_client.get("/api/modulos/1")
        assert res_found.status_code == 200
        mod = res_found.get_json()["data"]
        assert mod["id_modulo"] == 1 or mod["id"] == 1

        # Módulo inexistente
        res_not_found = auth_client.get("/api/modulos/99999")
        assert res_not_found.status_code == 404
        assert res_not_found.get_json()["status"] == "error"

    def test_create_modulo_success(self, auth_client, mock_db):
        """Verifica la creación exitosa de un nuevo módulo en el sistema."""
        payload = {
            "nombre": "ordenes_trabajo",
            "titulo": "Órdenes de Trabajo",
            "descripcion": "Gestión de órdenes operativas de taller",
            "ruta": "/admin/ordenes-trabajo",
            "icono": "bi bi-tools",
            "grupo": "Taller",
            "orden": 5,
            "en_sidebar": 1,
            "publico": 0
        }
        response = auth_client.post("/api/modulos/", json=payload)
        assert response.status_code == 200
        assert response.get_json()["status"] == "success"

        # Verificar persistencia en mock_db.modulos
        created = next((m for m in mock_db.modulos.values() if m["nombre_modulo"] == "ordenes_trabajo"), None)
        assert created is not None
        assert created["titulo_modulo"] == "Órdenes de Trabajo"
        assert created["grupo_modulo"] == "Taller"
        assert created["estado_modulo"] == 1

    def test_create_modulo_validation_failures(self, auth_client):
        """Verifica que claves inválidas, rutas inseguras o títulos vacíos sean rechazados con 400."""
        # 1. Clave con mayúsculas o espacios (no slug)
        bad_slug = {
            "nombre": "Modulo Con Espacios",
            "titulo": "Prueba",
            "ruta": "/admin/prueba",
            "grupo": "General"
        }
        res1 = auth_client.post("/api/modulos/", json=bad_slug)
        assert res1.status_code == 400
        assert "nombre" in res1.get_json()["errors"]

        # 2. Ruta no segura (intento de path traversal)
        bad_route = {
            "nombre": "modulo_seguro",
            "titulo": "Prueba",
            "ruta": "/admin/../hack",
            "grupo": "General"
        }
        res2 = auth_client.post("/api/modulos/", json=bad_route)
        assert res2.status_code == 400
        assert "ruta" in res2.get_json()["errors"]

        # 3. Falta título
        bad_title = {
            "nombre": "modulo_sin_titulo",
            "ruta": "/admin/sin-titulo",
            "grupo": "General"
        }
        res3 = auth_client.post("/api/modulos/", json=bad_title)
        assert res3.status_code == 400
        assert "titulo" in res3.get_json()["errors"]

    def test_create_modulo_duplicate_slug_or_route_fails(self, auth_client):
        """Verifica que intentar registrar una clave o ruta ya existente retorne 400."""
        # Clave duplicada ('modulos')
        dup_slug = {
            "nombre": "modulos",
            "titulo": "Módulos Duplicados",
            "ruta": "/admin/modulos-otro",
            "grupo": "Sistema"
        }
        res_dup_slug = auth_client.post("/api/modulos/", json=dup_slug)
        assert res_dup_slug.status_code == 400
        assert "nombre" in res_dup_slug.get_json()["errors"]

        # Ruta duplicada ('/admin/modulos')
        dup_route = {
            "nombre": "modulos_nuevo_slug",
            "titulo": "Módulos Duplicados Ruta",
            "ruta": "/admin/modulos",
            "grupo": "Sistema"
        }
        res_dup_route = auth_client.post("/api/modulos/", json=dup_route)
        assert res_dup_route.status_code == 400
        assert "ruta" in res_dup_route.get_json()["errors"]

    def test_update_modulo_success(self, auth_client, mock_db):
        """Verifica la actualización de información de un módulo."""
        update_payload = {
            "nombre": "modulos",
            "titulo": "Módulos del Sistema Modificado",
            "descripcion": "Gestión actualizada",
            "ruta": "/admin/modulos",
            "icono": "bi bi-grid-fill",
            "grupo": "Configuración",
            "orden": 2,
            "en_sidebar": 1,
            "publico": 0
        }
        response = auth_client.put("/api/modulos/1", json=update_payload)
        assert response.status_code == 200
        assert response.get_json()["status"] == "success"

        # Verificar actualización
        mod_1 = mock_db.modulos[1]
        assert mod_1["titulo_modulo"] == "Módulos del Sistema Modificado"
        assert mod_1["grupo_modulo"] == "Configuración"
        assert mod_1["icono_modulo"] == "bi bi-grid-fill"

    def test_soft_delete_modulo_success_and_404(self, auth_client, mock_db):
        """Verifica el soft delete de un módulo y manejo de 404 si no existe."""
        # 1. Crear módulo temporal
        mid = mock_db.next_modulo_id
        mock_db.next_modulo_id += 1
        mock_db.modulos[mid] = {
            "id": mid,
            "id_modulo": mid,
            "nombre_modulo": "temporal_delete",
            "titulo_modulo": "Temporal",
            "ruta_modulo": "/admin/temporal",
            "estado_modulo": 1
        }

        # 2. Eliminar módulo
        res_del = auth_client.delete(f"/api/modulos/{mid}")
        assert res_del.status_code == 200
        assert res_del.get_json()["status"] == "success"
        assert mock_db.modulos[mid]["estado_modulo"] == 0

        # 3. Eliminar módulo inexistente retorna 404
        res_not_found = auth_client.delete("/api/modulos/99999")
        assert res_not_found.status_code == 404
        assert res_not_found.get_json()["status"] == "error"
