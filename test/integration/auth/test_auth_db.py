import pytest
from werkzeug.security import check_password_hash

from helpers.api_client import login, register_client, unique_cedula, unique_suffix
from helpers.test_data import TEST_PASSWORD


def _payload(**overrides):
    data = {
        "nombre": "Laura",
        "apellido": "Gomez",
        "cedula": unique_cedula(),
        "telefono": "04141234567",
        "email": f"laura.{unique_suffix()}@transalca.test",
        "direccion": "Cabudare",
        "password": TEST_PASSWORD,
        "confirm_password": TEST_PASSWORD,
    }
    data.update(overrides)
    return data


def _usuario(db, email):
    with db["mantenimiento"].cursor() as cursor:
        cursor.execute("SELECT * FROM usuarios WHERE email = %s", (email,))
        return cursor.fetchone()


class TestRegistro:

    def test_registro_crea_usuario_cliente_con_hash_y_rol(self, anon, db):
        data = _payload()
        response = anon.post("/auth/do_register", json=data)

        assert response.status_code == 200
        assert response.get_json()["status"] == "success"
        usuario = _usuario(db, data["email"])
        assert usuario["tipo"] == "cliente"
        assert usuario["cedula"] == data["cedula"]
        assert usuario["password_hash"] != TEST_PASSWORD
        assert check_password_hash(usuario["password_hash"], TEST_PASSWORD)
        with db["mantenimiento"].cursor() as cursor:
            cursor.execute(
                "SELECT r.nombre FROM usuario_rol ur JOIN roles r ON r.id = ur.rol_id WHERE ur.usuario_id = %s",
                (usuario["id"],),
            )
            assert [r["nombre"] for r in cursor.fetchall()] == ["Cliente"]
        with db["transalca"].cursor() as cursor:
            cursor.execute("SELECT correo_cliente, tipo_cliente, estado FROM cliente WHERE identificador_cliente = %s", (data["cedula"],))
            cliente = cursor.fetchone()
        assert cliente == {"correo_cliente": data["email"], "tipo_cliente": "natural", "estado": 1}

    def test_registro_no_permite_elegir_tipo_de_usuario(self, anon, db):
        data = _payload(tipo="admin")
        assert anon.post("/auth/do_register", json=data).status_code == 200
        assert _usuario(db, data["email"])["tipo"] == "cliente"

    def test_registro_con_correo_duplicado_devuelve_400(self, anon, db):
        data = _payload()
        assert anon.post("/auth/do_register", json=data).status_code == 200
        response = anon.post("/auth/do_register", json=_payload(email=data["email"]))
        assert response.status_code == 400
        assert "email" in response.get_json()["errors"]

    def test_registro_con_cedula_duplicada_devuelve_400(self, anon):
        data = _payload()
        assert anon.post("/auth/do_register", json=data).status_code == 200
        response = anon.post("/auth/do_register", json=_payload(cedula=data["cedula"]))
        assert response.status_code == 400
        assert "cedula" in response.get_json()["errors"]

    @pytest.mark.parametrize("campo, valor", [
        ("nombre", ""),
        ("nombre", "   "),
        ("nombre", None),
        ("nombre", 12345),
        ("nombre", "A" * 101),
        ("apellido", "<script>alert(1)</script>"),
        ("email", "no-es-un-correo"),
        ("email", "a@b"),
        ("cedula", "12345678"),
        ("cedula", "X-123"),
        ("telefono", "123"),
        ("telefono", "0414abcdefg"),
        ("password", "corta1!"),
        ("password", "sinnumeros!A"),
        ("confirm_password", "Distinta123!"),
        ("direccion", "D" * 41),
    ])
    def test_registro_rechaza_entradas_invalidas_sin_escribir_en_bd(self, anon, db, campo, valor):
        data = _payload(**{campo: valor})
        response = anon.post("/auth/do_register", json=data)

        assert response.status_code == 400
        body = response.get_json()
        assert body["status"] == "error"
        assert body["errors"]
        assert _usuario(db, data["email"]) is None

    @pytest.mark.xfail(strict=True, reason="BUG-API-01: un cuerpo que no es JSON hace fallar request.get_json() y el controlador responde 500 en vez de 400/415")
    def test_registro_con_cuerpo_no_json_devuelve_error_controlado(self, anon):
        response = anon.post("/auth/do_register", data="no json", content_type="text/plain")
        assert response.status_code in (400, 415)


class TestLogin:

    def test_login_correcto_crea_sesion_sin_datos_sensibles(self, anon):
        cuenta = register_client(anon)
        login(anon, cuenta["email"])

        response = anon.get("/auth/session")
        assert response.status_code == 200
        user = response.get_json()["user"]
        assert user["email"] == cuenta["email"]
        assert user["tipo"] == "cliente"
        assert user["roles"] == ["Cliente"]
        assert "password_hash" not in user and "password" not in user

    def test_login_con_clave_incorrecta_devuelve_401(self, anon):
        cuenta = register_client(anon)
        response = anon.post("/auth/do_login", json={"email": cuenta["email"], "password": "Incorrecta123!"})
        assert response.status_code == 401
        assert anon.get("/auth/session").status_code == 401

    def test_login_con_correo_inexistente_devuelve_401(self, anon):
        response = anon.post("/auth/do_login", json={"email": f"nadie.{unique_suffix()}@transalca.test", "password": TEST_PASSWORD})
        assert response.status_code == 401

    @pytest.mark.parametrize("payload", [
        {},
        {"email": "", "password": ""},
        {"email": "   ", "password": TEST_PASSWORD},
        {"email": "admin.test@transalca.test"},
        {"email": "no-es-correo", "password": TEST_PASSWORD},
    ])
    def test_login_con_campos_faltantes_devuelve_400(self, anon, payload):
        response = anon.post("/auth/do_login", json=payload)
        assert response.status_code == 400
        assert response.get_json()["status"] == "error"

    @pytest.mark.parametrize("email", [
        "' OR '1'='1",
        "admin.test@transalca.test' -- ",
        "admin.test@transalca.test' OR 1=1 #",
    ])
    def test_login_no_es_vulnerable_a_inyeccion_sql(self, anon, email):
        response = anon.post("/auth/do_login", json={"email": email, "password": "x"})
        assert response.status_code in (400, 401)
        assert anon.get("/auth/session").status_code == 401

    def test_usuario_inactivo_no_puede_iniciar_sesion(self, anon, db):
        cuenta = register_client(anon)
        with db["mantenimiento"].cursor() as cursor:
            cursor.execute("UPDATE usuarios SET estado = 0 WHERE email = %s", (cuenta["email"],))
        response = anon.post("/auth/do_login", json={"email": cuenta["email"], "password": TEST_PASSWORD})
        assert response.status_code == 403
        assert anon.get("/auth/session").status_code == 401

    def test_bloqueo_tras_cinco_intentos_fallidos(self, anon):
        cuenta = register_client(anon)
        for _ in range(5):
            assert anon.post("/auth/do_login", json={"email": cuenta["email"], "password": "Mala1234!"}).status_code == 401
        response = anon.post("/auth/do_login", json={"email": cuenta["email"], "password": TEST_PASSWORD})
        assert response.status_code == 429

    def test_logout_elimina_la_sesion(self, cliente_a):
        assert cliente_a.get("/auth/session").status_code == 200
        assert cliente_a.post("/auth/logout").status_code == 200
        assert cliente_a.get("/auth/session").status_code == 401
        assert cliente_a.get("/api/vehicles/").status_code == 401


class TestRecuperacion:

    @pytest.fixture(autouse=True)
    def _limpiar_throttle(self):
        from controller import auth_controller
        auth_controller.recovery_throttle.clear()
        yield

    def test_flujo_completo_de_recuperacion_de_clave(self, anon, db):
        cuenta = register_client(anon)
        assert anon.post("/auth/do_recover", json={"email": cuenta["email"]}).status_code == 200
        usuario = _usuario(db, cuenta["email"])
        with db["mantenimiento"].cursor() as cursor:
            cursor.execute("SELECT token FROM tokens_recuperacion WHERE usuario_id = %s AND usado = 0 ORDER BY id DESC", (usuario["id"],))
            token = cursor.fetchone()["token"]

        nueva = "NuevaClave123!"
        response = anon.post("/auth/do_reset", json={"token": token, "password": nueva, "confirm_password": nueva})
        assert response.status_code == 200
        login(anon, cuenta["email"], nueva)

        reutilizado = anon.post("/auth/do_reset", json={"token": token, "password": "OtraClave123!", "confirm_password": "OtraClave123!"})
        assert reutilizado.status_code == 400

    @pytest.mark.parametrize("token", ["", "token-inventado", "' OR '1'='1"])
    def test_reset_con_token_invalido_devuelve_400(self, anon, token):
        response = anon.post("/auth/do_reset", json={"token": token, "password": "NuevaClave123!", "confirm_password": "NuevaClave123!"})
        assert response.status_code == 400

    @pytest.mark.xfail(strict=True, reason="BUG-AUTH-01: /auth/do_recover responde 404 cuando el correo no existe y revela que cuentas estan registradas")
    def test_recuperacion_no_revela_si_el_correo_existe(self, anon):
        response = anon.post("/auth/do_recover", json={"email": f"nadie.{unique_suffix()}@transalca.test"})
        assert response.status_code == 200
