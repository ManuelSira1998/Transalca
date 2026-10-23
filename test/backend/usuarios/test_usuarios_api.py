import pytest

from helpers.api_client import unique_cedula, unique_suffix
from helpers.http_client import ApiClient, http_login
from helpers.test_data import TEST_PASSWORD


def _empleado(**overrides):
    data = {
        "nombre": "Andrea",
        "apellido": "Torres",
        "cedula": unique_cedula(),
        "email": f"andrea.{unique_suffix()}@transalca.test",
        "telefono": "04121234567",
        "tipo": "empleado",
        "rol_id": 2,
        "password": TEST_PASSWORD,
        "confirm_password": TEST_PASSWORD,
    }
    data.update(overrides)
    return data


class TestUsuariosApi:

    def test_ciclo_de_vida_crear_login_desactivar(self, live_server, admin):
        data = _empleado()
        creado = admin.post("/api/users/", json=data)
        assert creado.status_code == 200, creado.text
        user_id = creado.json()["id"]

        detalle = admin.get(f"/api/users/{user_id}").json()["data"]
        assert detalle["email"] == data["email"]
        assert [r["nombre"] for r in detalle["roles"]] == ["Vendedor"]

        with ApiClient(live_server) as nuevo:
            http_login(nuevo, data["email"])
            assert nuevo.get("/auth/session").json()["user"]["roles"] == ["Vendedor"]

        assert admin.put(f"/api/users/{user_id}/status", json={"estado": 0}).status_code == 200
        with ApiClient(live_server) as nuevo:
            response = nuevo.post("/auth/do_login", json={"email": data["email"], "password": TEST_PASSWORD})
            assert response.status_code == 403

    @pytest.mark.parametrize("estado", ["2", "activo", None, -1])
    def test_estado_invalido_devuelve_400(self, admin, estado):
        user_id = admin.post("/api/users/", json=_empleado()).json()["id"]
        assert admin.put(f"/api/users/{user_id}/status", json={"estado": estado}).status_code == 400

    def test_check_unique_de_correo_y_cedula(self, admin):
        data = _empleado()
        admin.post("/api/users/", json=data)
        assert admin.post("/api/users/check-unique", json={"field": "email", "value": data["email"]}).json()["exists"] is True
        assert admin.post("/api/users/check-unique", json={"field": "cedula", "value": data["cedula"]}).json()["exists"] is True
        assert admin.post("/api/users/check-unique", json={"field": "email", "value": f"libre.{unique_suffix()}@x.com"}).json()["exists"] is False
        assert admin.post("/api/users/check-unique", json={"field": "password_hash", "value": "x"}).status_code == 400

    def test_listado_es_json_con_lista(self, admin):
        response = admin.get("/api/users/")
        assert response.status_code == 200
        assert response.headers["Content-Type"].startswith("application/json")
        assert isinstance(response.json()["data"], list)

    @pytest.mark.xfail(strict=True, reason="BUG-USR-01: la respuesta HTTP de GET /api/users/ incluye password_hash")
    def test_listado_no_contiene_hashes(self, admin):
        assert "password_hash" not in admin.get("/api/users/").text
