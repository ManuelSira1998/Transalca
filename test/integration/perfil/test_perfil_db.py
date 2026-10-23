import pytest

from helpers.api_client import login
from helpers.test_data import TEST_PASSWORD


class TestPerfil:

    def test_perfil_devuelve_solo_los_datos_del_usuario_sin_hash(self, cliente_a):
        response = cliente_a.get("/api/profile/")
        assert response.status_code == 200
        perfil = response.get_json()["data"]
        assert perfil["email"] == cliente_a.info["email"]
        assert perfil["cedula"] == cliente_a.info["cedula"]
        assert "password_hash" not in perfil

    def test_perfil_sin_sesion_devuelve_401(self, anon):
        assert anon.get("/api/profile/").status_code == 401

    def test_cambio_de_clave_con_clave_actual_incorrecta_devuelve_400(self, cliente_a):
        response = cliente_a.put("/api/profile/password", json={
            "old_password": "Incorrecta123!", "new_password": "NuevaClave123!", "confirm_password": "NuevaClave123!",
        })
        assert response.status_code == 400
        assert "old_password" in response.get_json()["errors"]

    @pytest.mark.parametrize("nueva, confirmacion, campo", [
        ("corta", "corta", "new_password"),
        ("SinNumero!!", "SinNumero!!", "new_password"),
        ("NuevaClave123!", "Otra123!", "confirm_password"),
    ])
    def test_cambio_de_clave_valida_la_nueva_clave(self, cliente_a, nueva, confirmacion, campo):
        response = cliente_a.put("/api/profile/password", json={
            "old_password": TEST_PASSWORD, "new_password": nueva, "confirm_password": confirmacion,
        })
        assert response.status_code == 400
        assert campo in response.get_json()["errors"]

    def test_cambio_de_clave_correcto_permite_login_con_la_nueva(self, flask_app, cliente_a):
        nueva = "CambioClave123!"
        response = cliente_a.put("/api/profile/password", json={
            "old_password": TEST_PASSWORD, "new_password": nueva, "confirm_password": nueva,
        })
        assert response.status_code == 200
        otro = flask_app.test_client()
        assert otro.post("/auth/do_login", json={"email": cliente_a.info["email"], "password": TEST_PASSWORD}).status_code == 401
        login(otro, cliente_a.info["email"], nueva)

    def test_no_puede_tomar_el_correo_de_otro_usuario(self, cliente_a, cliente_b):
        response = cliente_a.put("/api/profile/email", json={"email": cliente_b.info["email"]})
        assert response.status_code == 400
        assert cliente_a.get("/api/profile/").get_json()["data"]["email"] == cliente_a.info["email"]
