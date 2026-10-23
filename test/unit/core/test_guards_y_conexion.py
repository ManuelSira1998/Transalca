import pytest
from flask import Flask, session

from controller import _guards
from model.connection import Connection


@pytest.fixture
def ctx():
    app = Flask(__name__)
    app.secret_key = "unit"
    with app.test_request_context():
        yield session


class TestGuards:

    def test_require_login_sin_sesion_devuelve_401(self, ctx):
        response, status = _guards.require_login()
        assert status == 401
        assert response.get_json()["status"] == "error"

    def test_require_login_con_sesion_no_bloquea(self, ctx):
        ctx["user_id"] = 1
        assert _guards.require_login() is None

    @pytest.mark.parametrize("tipo, empleado, cliente", [
        ("empleado", True, False), ("admin", True, False), ("vendedor", True, False),
        ("mecanico", True, False), ("soporte", True, False), ("cliente", False, True),
        (None, False, False), ("Admin", False, False), ("", False, False),
    ])
    def test_tipos_de_usuario(self, ctx, tipo, empleado, cliente):
        ctx["user_tipo"] = tipo
        assert _guards.is_employee() is empleado
        assert _guards.is_client() is cliente

    def test_can_access_client_solo_su_propia_cedula(self, ctx):
        ctx.update(user_tipo="cliente", user_cedula="V-1")
        assert _guards.can_access_client("V-1") is True
        assert _guards.can_access_client("V-2") is False
        assert _guards.can_access_client(None) is False

    def test_empleado_accede_a_cualquier_cliente(self, ctx):
        ctx["user_tipo"] = "empleado"
        assert _guards.can_access_client("V-2") is True

    def test_has_module_permission(self, ctx):
        assert _guards.has_module_permission("usuarios") is False
        ctx.update(user_id=5, permisos={"usuarios": {"leer": 1, "crear": 0}})
        assert _guards.has_module_permission("usuarios", "leer") is True
        assert _guards.has_module_permission("usuarios", "crear") is False
        assert _guards.has_module_permission("roles", "leer") is False
        ctx["roles"] = ["Administrador"]
        assert _guards.has_module_permission("roles", "eliminar") is True

    def test_require_module_devuelve_401_o_403(self, ctx):
        assert _guards.require_module("usuarios")[1] == 401
        ctx.update(user_id=5, permisos={})
        assert _guards.require_module("usuarios")[1] == 403
        ctx["permisos"] = {"usuarios": {"leer": 1}}
        assert _guards.require_module("usuarios") is None

    def test_deny_devuelve_403(self, ctx):
        assert _guards.deny()[1] == 403


class TestConstructoresSQL:

    @pytest.fixture
    def conn(self):
        return Connection()

    def test_identificador_permitido_se_entrecomilla(self, conn):
        assert conn.sql_identifier("usuarios", {"usuarios"}) == "`usuarios`"

    @pytest.mark.parametrize("valor", [
        "usuarios; DROP TABLE x", "usu`arios", "usuarios -- ", "", None, "otra_tabla",
    ])
    def test_identificador_no_permitido_lanza_error(self, conn, valor):
        allowed = {"usuarios", "usuarios; DROP TABLE x", "usu`arios", "usuarios -- ", ""}
        with pytest.raises(ValueError):
            conn.sql_identifier(valor, allowed)

    def test_build_insert_usa_marcadores(self, conn):
        sql = conn.build_insert_sql("usuarios", ["nombre", "email"], {"usuarios"}, {"nombre", "email"})
        assert sql == "INSERT INTO `usuarios` (`nombre`, `email`) VALUES (%s, %s)"

    def test_build_update_usa_marcadores(self, conn):
        sql = conn.build_update_by_key_sql("usuarios", ["nombre"], "id", {"usuarios"}, {"nombre", "id"})
        assert sql == "UPDATE `usuarios` SET `nombre` = %s WHERE `id` = %s"

    def test_build_upsert(self, conn):
        sql = conn.build_upsert_sql("t", ["id", "valor"], "id", {"t"}, {"id", "valor"})
        assert sql == "INSERT INTO `t` (`id`, `valor`) VALUES (%s, %s) ON DUPLICATE KEY UPDATE `valor`=VALUES(`valor`)"

    def test_columna_no_permitida_en_insert(self, conn):
        with pytest.raises(ValueError):
            conn.build_insert_sql("usuarios", ["nombre", "password_hash"], {"usuarios"}, {"nombre"})

    def test_placeholders(self, conn):
        assert conn.sql_placeholders(3) == "%s, %s, %s"
        assert conn.sql_placeholders(0) == ""

    def test_email_exists_globally_parametriza_y_normaliza(self, conn, mocker):
        fetch = mocker.patch.object(Connection, "fetch_one", return_value=None)
        assert conn.email_exists_globally("  Ana@Correo.com' OR '1'='1 ") is False
        for call in fetch.call_args_list:
            _, sql, params = call.args
            assert "Ana" not in sql and "OR '1'='1" not in sql
            assert params[0] == "ana@correo.com' or '1'='1"

    def test_email_exists_globally_vacio_no_consulta(self, conn, mocker):
        fetch = mocker.patch.object(Connection, "fetch_one")
        assert conn.email_exists_globally("   ") is False
        fetch.assert_not_called()
