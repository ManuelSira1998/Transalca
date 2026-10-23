import pytest
from werkzeug.security import check_password_hash

from helpers.api_client import unique_cedula, unique_letters, unique_suffix
from helpers.test_data import TEST_PASSWORD

CAMPOS_SENSIBLES = {"password_hash", "password", "token"}


def _nuevo_empleado(**overrides):
    data = {
        "nombre": "Carlos",
        "apellido": "Rivas",
        "cedula": unique_cedula(),
        "email": f"carlos.{unique_suffix()}@transalca.test",
        "telefono": "04241234567",
        "direccion": "Centro",
        "tipo": "empleado",
        "rol_id": 2,
        "password": TEST_PASSWORD,
        "confirm_password": TEST_PASSWORD,
    }
    data.update(overrides)
    return data


def _usuario(db, email):
    with db["mantenimiento"].cursor() as cursor:
        cursor.execute("SELECT * FROM usuarios WHERE email = %s", (email,))
        return cursor.fetchone()


class TestCrudUsuarios:

    def test_listar_sin_sesion_devuelve_401(self, anon):
        response = anon.get("/api/users/")
        assert response.status_code == 401
        assert response.get_json() == {"status": "error", "message": "Debe iniciar sesion."}

    def test_admin_crea_empleado_con_rol_y_clave_cifrada(self, admin, db):
        data = _nuevo_empleado()
        response = admin.post("/api/users/", json=data)

        assert response.status_code == 200
        body = response.get_json()
        assert body["status"] == "success"
        usuario = _usuario(db, data["email"])
        assert usuario["id"] == body["id"]
        assert usuario["tipo"] == "empleado"
        assert check_password_hash(usuario["password_hash"], TEST_PASSWORD)
        with db["mantenimiento"].cursor() as cursor:
            cursor.execute("SELECT rol_id FROM usuario_rol WHERE usuario_id = %s", (usuario["id"],))
            assert [r["rol_id"] for r in cursor.fetchall()] == [2]

    def test_admin_ve_el_usuario_creado_en_el_listado(self, admin):
        data = _nuevo_empleado()
        user_id = admin.post("/api/users/", json=data).get_json()["id"]
        usuarios = admin.get("/api/users/").get_json()["data"]
        assert user_id in [u["id"] for u in usuarios]

    def test_obtener_usuario_inexistente_devuelve_404(self, admin):
        response = admin.get("/api/users/99999999")
        assert response.status_code == 404

    def test_correo_duplicado_devuelve_400(self, admin):
        data = _nuevo_empleado()
        assert admin.post("/api/users/", json=data).status_code == 200
        response = admin.post("/api/users/", json=_nuevo_empleado(email=data["email"]))
        assert response.status_code == 400
        assert "email" in response.get_json()["errors"]

    @pytest.mark.parametrize("campo, valor", [
        ("rol_id", None),
        ("rol_id", "abc"),
        ("rol_id", 999999),
        ("rol_id", {"id": 1}),
        ("tipo", "superusuario"),
        ("nombre", ""),
        ("nombre", "N" * 61),
        ("email", "sin-arroba"),
        ("cedula", ""),
        ("password", "debil"),
    ])
    def test_crear_con_datos_invalidos_devuelve_400_sin_insertar(self, admin, db, campo, valor):
        data = _nuevo_empleado(**{campo: valor})
        response = admin.post("/api/users/", json=data)
        assert response.status_code == 400
        assert campo in response.get_json()["errors"]
        assert _usuario(db, data["email"]) is None

    def test_actualizar_usuario_persiste_cambios(self, admin, db):
        data = _nuevo_empleado()
        user_id = admin.post("/api/users/", json=data).get_json()["id"]
        cambios = dict(data, nombre="Carlota", direccion="Este")
        cambios.pop("password"); cambios.pop("confirm_password")
        response = admin.put(f"/api/users/{user_id}", json=cambios)
        assert response.status_code == 200
        usuario = _usuario(db, data["email"])
        assert (usuario["nombre"], usuario["direccion"]) == ("Carlota", "Este")

    def test_eliminar_usuario_es_borrado_logico(self, admin, db):
        data = _nuevo_empleado()
        user_id = admin.post("/api/users/", json=data).get_json()["id"]
        assert admin.delete(f"/api/users/{user_id}").status_code == 200
        assert _usuario(db, data["email"])["estado"] == 0
        assert user_id not in [u["id"] for u in admin.get("/api/users/").get_json()["data"]]


class TestBusquedaUsuarios:

    @pytest.mark.parametrize("q", [
        "' OR '1'='1",
        "%' OR 1=1 -- ",
        "\" UNION SELECT password_hash FROM usuarios -- ",
        "admin'; DROP TABLE usuarios; --",
    ])
    def test_busqueda_trata_la_entrada_como_texto(self, admin, db, q):
        response = admin.get("/api/users/search", query_string={"q": q})
        assert response.status_code == 200
        assert response.get_json()["data"] == []
        with db["mantenimiento"].cursor() as cursor:
            cursor.execute("SELECT COUNT(*) AS n FROM usuarios")
            assert cursor.fetchone()["n"] > 0

    def test_busqueda_trunca_consultas_largas(self, admin):
        response = admin.get("/api/users/search", query_string={"q": "a" * 5000})
        assert response.status_code == 200


class TestDatosSensibles:

    @pytest.mark.xfail(strict=True, reason="BUG-USR-01: GET /api/users/ usa SELECT u.* y devuelve password_hash")
    def test_listado_no_expone_hash_de_clave(self, admin):
        usuarios = admin.get("/api/users/").get_json()["data"]
        assert usuarios
        for usuario in usuarios:
            assert not CAMPOS_SENSIBLES & set(usuario)

    @pytest.mark.xfail(strict=True, reason="BUG-USR-01: GET /api/users/<id> usa SELECT * y devuelve password_hash")
    def test_detalle_no_expone_hash_de_clave(self, admin):
        user_id = admin.post("/api/users/", json=_nuevo_empleado()).get_json()["id"]
        usuario = admin.get(f"/api/users/{user_id}").get_json()["data"]
        assert not CAMPOS_SENSIBLES & set(usuario)

    @pytest.mark.xfail(strict=True, reason="BUG-USR-01: GET /api/users/search usa SELECT * y devuelve password_hash")
    def test_busqueda_no_expone_hash_de_clave(self, admin):
        resultados = admin.get("/api/users/search", query_string={"q": "Prueba"}).get_json()["data"]
        assert resultados
        for usuario in resultados:
            assert not CAMPOS_SENSIBLES & set(usuario)


class TestControlDeAcceso:

    @pytest.mark.xfail(strict=True, reason="BUG-AUTHZ-01: /api/users solo exige sesion; un cliente puede listar usuarios")
    def test_cliente_no_puede_listar_usuarios(self, cliente_a):
        assert cliente_a.get("/api/users/").status_code == 403

    @pytest.mark.xfail(strict=True, reason="BUG-AUTHZ-01: /api/users solo exige sesion; un cliente puede crear empleados")
    def test_cliente_no_puede_crear_usuarios(self, cliente_a, db):
        data = _nuevo_empleado(nombre="Intruso", apellido="Cliente")
        response = cliente_a.post("/api/users/", json=data)
        assert response.status_code == 403
        assert _usuario(db, data["email"]) is None

    @pytest.mark.xfail(strict=True, reason="BUG-AUTHZ-01: un empleado sin rol ni permisos puede crear usuarios")
    def test_empleado_sin_permisos_no_puede_crear_usuarios(self, empleado_sin_rol):
        response = empleado_sin_rol.post("/api/users/", json=_nuevo_empleado(apellido=unique_letters()))
        assert response.status_code == 403
