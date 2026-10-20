import pytest


class TestSucursalIntegration:
    """Pruebas de integración para el módulo de Sucursales (/api/sucursales/).

    Valida el ciclo de vida completo de sedes operativas, reglas de unicidad,
    control de acceso y la integración con la disponibilidad de servicios (/api/services/sucursal/).
    """

    def test_unauthorized_access_rejected(self, client):
        """Verifica que las rutas protegidas exijan usuario autenticado (guard_public_access)."""
        # Creación sin sesión
        res_post = client.post("/api/sucursales/", json={"nombre": "Sede Nueva"})
        assert res_post.status_code == 401

        # Modificación sin sesión
        res_put = client.put("/api/sucursales/1", json={"nombre": "Sede Modificada"})
        assert res_put.status_code == 401

        # Eliminación sin sesión
        res_del = client.delete("/api/sucursales/1")
        assert res_del.status_code == 401

        # Detalle sin sesión
        res_get = client.get("/api/sucursales/1")
        assert res_get.status_code == 401

        # Check unique sin sesión
        res_chk = client.post("/api/sucursales/check-unique", json={"field": "nombre", "value": "Sede"})
        assert res_chk.status_code == 401

        # Disponibilidad de servicios por sucursal sin sesión
        res_svc = client.get("/api/services/sucursal/1")
        assert res_svc.status_code == 401

    def test_get_all_and_active_sucursales(self, client, auth_client):
        """Verifica la consulta de sucursales activas en el sistema tanto pública como autenticada."""
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
        # La sede inactiva (estado = 0) no debe figurar en active
        assert "Sede Inactiva" not in nombres

        # Consulta autenticada de todas las sucursales
        res_all = auth_client.get("/api/sucursales/")
        assert res_all.status_code == 200
        assert res_all.get_json()["status"] == "success"

    def test_get_sucursal_detail_found(self, auth_client):
        """Verifica la obtención autenticada del detalle de una sucursal existente."""
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
        """Verifica que consultar un id inexistente retorne 404."""
        response = auth_client.get("/api/sucursales/99999")
        assert response.status_code == 404
        data = response.get_json()
        assert data["status"] == "error"
        assert "no encontrada" in data["message"].lower()

    def test_check_unique_nombre_and_email(self, auth_client):
        """Verifica el endpoint /check-unique para validación de nombres y correos no duplicados."""
        # 1. Nombre existente
        res_nom = auth_client.post("/api/sucursales/check-unique", json={"field": "nombre", "value": "Sede Central"})
        assert res_nom.status_code == 200
        assert res_nom.get_json()["exists"] is True

        # 2. Nombre existente pero excluyendo el propio ID
        res_nom_excl = auth_client.post("/api/sucursales/check-unique", json={"field": "nombre", "value": "Sede Central", "exclude": 1})
        assert res_nom_excl.status_code == 200
        assert res_nom_excl.get_json()["exists"] is False

        # 3. Nombre libre
        res_nom_free = auth_client.post("/api/sucursales/check-unique", json={"field": "nombre", "value": "Sede Totalmente Nueva"})
        assert res_nom_free.status_code == 200
        assert res_nom_free.get_json()["exists"] is False

        # 4. Email existente
        res_em = auth_client.post("/api/sucursales/check-unique", json={"field": "email", "value": "central@transalca.com"})
        assert res_em.status_code == 200
        assert res_em.get_json()["exists"] is True

        # 5. Email nuevo
        res_em_free = auth_client.post("/api/sucursales/check-unique", json={"field": "email", "value": "nueva.sucursal@transalca.com"})
        assert res_em_free.status_code == 200
        assert res_em_free.get_json()["exists"] is False

    def test_create_sucursal_lifecycle(self, auth_client, mock_db):
        """Prueba la creación exitosa de una nueva sucursal y su persistencia en memoria."""
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

        # Consultar la sucursal recién creada
        res_get = auth_client.get(f"/api/sucursales/{sid}")
        assert res_get.status_code == 200
        suc = res_get.get_json()["data"]
        assert suc["nombre"] == "Sede Barquisimeto Este"
        assert suc["email"] == "este@transalca.com"

    def test_create_sucursal_validation_errors(self, auth_client):
        """Verifica rechazo con código 400 si faltan campos obligatorios o formato inválido."""
        # Nombre muy corto
        res_short = auth_client.post("/api/sucursales/", json={"nombre": "AB"})
        assert res_short.status_code == 400
        assert res_short.get_json()["status"] == "error"

        # Dirección con caracteres inválidos
        res_bad_dir = auth_client.post("/api/sucursales/", json={"nombre": "Sede Oeste", "direccion": "Av. $$$ ### %%%"})
        assert res_bad_dir.status_code == 400

    def test_update_sucursal_success(self, auth_client, mock_db):
        """Prueba la modificación de datos de una sucursal existente."""
        payload = {
            "nombre": "Sede Central Modificada",
            "direccion": "Av. Principal Renovada",
            "telefono": "04141112233",
            "email": "central@transalca.com"
        }
        response = auth_client.put("/api/sucursales/1", json=payload)
        assert response.status_code == 200
        assert response.get_json()["status"] == "success"

        # Verificar cambio persistido
        res_get = auth_client.get("/api/sucursales/1")
        assert res_get.status_code == 200
        suc = res_get.get_json()["data"]
        assert suc["nombre"] == "Sede Central Modificada"
        assert suc["direccion"] == "Av. Principal Renovada"

    def test_soft_delete_sucursal(self, auth_client, mock_db):
        """Verifica la desactivación lógica de una sucursal y su exclusión del listado activo."""
        # Desactivar sede 2
        res_del = auth_client.delete("/api/sucursales/2")
        assert res_del.status_code == 200
        assert res_del.get_json()["status"] == "success"

        # Verificar que ya no aparezca en /api/sucursales/active
        res_active = auth_client.get("/api/sucursales/active")
        active_names = [s["nombre"] for s in res_active.get_json()["data"]]
        assert "Sede Norte" not in active_names

    def test_sucursal_servicios_integration(self, auth_client):
        """Verifica la relación de integración entre Sucursales y Servicios:

        La disponibilidad de servicios (/api/services/sucursal/<id>) filtra
        exactamente los servicios asignados a esa sede a través de servicio_sucursal.
        """
        # Sede 1 tiene asignados servicios 1 y 2
        res_s1 = auth_client.get("/api/services/sucursal/1")
        assert res_s1.status_code == 200
        data1 = res_s1.get_json()["data"]
        s1_names = [s["nombre"] for s in data1]
        assert "Alineación Computarizada" in s1_names
        assert "Balanceo Dinámico" in s1_names

        # Sede 2 solo tiene asignado servicio 1
        res_s2 = auth_client.get("/api/services/sucursal/2")
        assert res_s2.status_code == 200
        data2 = res_s2.get_json()["data"]
        s2_names = [s["nombre"] for s in data2]
        assert "Alineación Computarizada" in s2_names
        assert "Balanceo Dinámico" not in s2_names
