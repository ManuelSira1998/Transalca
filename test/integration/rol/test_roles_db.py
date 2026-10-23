import pytest

from helpers.api_client import unique_letters


def _rol(db, nombre):
    with db["mantenimiento"].cursor() as cursor:
        cursor.execute("SELECT * FROM roles WHERE nombre = %s", (nombre,))
        return cursor.fetchone()


class TestRoles:

    def test_admin_crea_rol_con_permisos(self, admin, db):
        nombre = "Rol " + unique_letters()
        permisos = [{"modulo": "productos", "crear": 1, "leer": 1, "actualizar": 0, "eliminar": 0}]
        response = admin.post("/api/roles/", json={"nombre": nombre, "descripcion": "Rol de prueba", "permisos": permisos})
        assert response.status_code == 200
        rol = _rol(db, nombre)
        assert rol["id"] == response.get_json()["id"]
        with db["mantenimiento"].cursor() as cursor:
            cursor.execute("SELECT modulo, crear, leer, actualizar, eliminar FROM permisos WHERE rol_id = %s", (rol["id"],))
            assert cursor.fetchall() == [{"modulo": "productos", "crear": 1, "leer": 1, "actualizar": 0, "eliminar": 0}]

    def test_detalle_de_rol_incluye_permisos(self, admin):
        response = admin.get("/api/roles/1")
        assert response.status_code == 200
        data = response.get_json()["data"]
        assert data["nombre"] == "Administrador"
        assert isinstance(data["permisos"], list)

    def test_rol_inexistente_devuelve_404(self, admin):
        assert admin.get("/api/roles/99999999").status_code == 404

    @pytest.mark.parametrize("nombre", ["", "ab", "R" * 61, None, "   "])
    def test_nombre_invalido_devuelve_400(self, admin, db, nombre):
        response = admin.post("/api/roles/", json={"nombre": nombre})
        assert response.status_code == 400
        assert "nombre" in response.get_json()["errors"]

    def test_sin_sesion_devuelve_401(self, anon):
        assert anon.post("/api/roles/", json={"nombre": "Rol anonimo"}).status_code == 401

    @pytest.mark.xfail(strict=True, reason="BUG-AUTHZ-01: /api/roles solo exige sesion; un cliente puede crear roles")
    def test_cliente_no_puede_crear_roles(self, cliente_a, db):
        nombre = "Rol " + unique_letters()
        response = cliente_a.post("/api/roles/", json={"nombre": nombre})
        assert response.status_code == 403
        assert _rol(db, nombre) is None

    @pytest.mark.xfail(strict=True, reason="BUG-AUTHZ-01: /api/roles/<id>/permissions solo exige sesion; un cliente puede cambiar permisos")
    def test_cliente_no_puede_modificar_permisos(self, cliente_a, admin):
        nombre = "Rol " + unique_letters()
        role_id = admin.post("/api/roles/", json={"nombre": nombre}).get_json()["id"]
        response = cliente_a.post(f"/api/roles/{role_id}/permissions", json={"permisos": [
            {"modulo": "usuarios", "crear": 1, "leer": 1, "actualizar": 1, "eliminar": 1},
        ]})
        assert response.status_code == 403
