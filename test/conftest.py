import os
import socket
import threading
from pathlib import Path

import pymysql
import pytest
from werkzeug.security import generate_password_hash

from helpers.schema_loader import (
    DEV_DATABASE_NAMES,
    assert_test_database_name,
    drop_all_tables,
    load_schema,
)
from helpers.test_data import TEST_PASSWORD, TEST_USERS

TEST_DIR = Path(__file__).resolve().parent
LEVEL_BY_FOLDER = {
    TEST_DIR / "integration": "integration",
    TEST_DIR / "backend": "backend",
    TEST_DIR / "smoke": "smoke",
}

TEST_DB_HOST = os.getenv("TEST_DB_HOST", "127.0.0.1")
TEST_DB_PORT = int(os.getenv("TEST_DB_PORT", "3306"))
TEST_DB_USER = os.getenv("TEST_DB_USER", "root")
TEST_DB_PASSWORD = os.getenv("TEST_DB_PASSWORD", "")
TEST_DB_TRANSALCA = os.getenv("TEST_DB_TRANSALCA", "db_transalca_test")
TEST_DB_MANTENIMIENTO = os.getenv("TEST_DB_MANTENIMIENTO", "db_mantenimiento_test")
TEST_DB_KEEP = os.getenv("TEST_DB_KEEP", "").strip().lower() in {"1", "true", "yes"}

FAKE_RATES = {"usd": 40.0, "eur": 43.0}
FAKE_USDT_VES = 42.5


def _level(item):
    parents = Path(str(item.fspath)).resolve().parents
    for folder, level in LEVEL_BY_FOLDER.items():
        if folder in parents:
            return level
    return "unit"


MARCAS = {
    "unit": "prueba unitaria (sin base de datos ni servicios externos)",
    "integration": "prueba de integracion contra las bases de datos de prueba",
    "backend": "prueba de API por HTTP real contra un servidor de la app sobre las bases de prueba",
    "smoke": "prueba de humo rapida del sistema levantado (servicios, BD y flujos vitales)",
}


def pytest_configure(config):
    for marca, descripcion in MARCAS.items():
        config.addinivalue_line("markers", f"{marca}: {descripcion}")


def pytest_collection_modifyitems(config, items):
    for item in items:
        item.add_marker(getattr(pytest.mark, _level(item)))


@pytest.fixture(autouse=True)
def _block_database_in_unit_tests(request, monkeypatch):
    if not request.node.get_closest_marker("unit"):
        yield
        return

    def _forbidden(*args, **kwargs):
        raise pymysql.err.OperationalError(2003, "Las pruebas unitarias no pueden conectarse a la base de datos.")

    monkeypatch.setattr(pymysql, "connect", _forbidden)
    from model.connection import Connection
    for attr in ("mantenimiento", "transalca"):
        monkeypatch.setattr(Connection._local, attr, None, raising=False)
    yield


def _server_connection(database=None):
    return pymysql.connect(
        host=TEST_DB_HOST,
        port=TEST_DB_PORT,
        user=TEST_DB_USER,
        password=TEST_DB_PASSWORD,
        database=database,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )


def _database_has_tables(conn, database):
    with conn.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) AS n FROM information_schema.TABLES WHERE TABLE_SCHEMA = %s", (database,))
        return cursor.fetchone()["n"] > 0


def _seed_test_users(conn):
    password_hash = generate_password_hash(TEST_PASSWORD)
    with conn.cursor() as cursor:
        for key, user in TEST_USERS.items():
            cursor.execute(f"DELETE FROM `{TEST_DB_MANTENIMIENTO}`.usuarios WHERE email = %s OR cedula = %s", (user["email"], user["cedula"]))
            cursor.execute(
                f"INSERT INTO `{TEST_DB_MANTENIMIENTO}`.usuarios (nombre, apellido, cedula, email, telefono, direccion, password_hash, tipo, estado) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 1)",
                ("Prueba", key.capitalize(), user["cedula"], user["email"], "04140000000", "Direccion de prueba", password_hash, user["tipo"]),
            )
            user_id = cursor.lastrowid
            if user["rol"]:
                cursor.execute(f"SELECT id FROM `{TEST_DB_MANTENIMIENTO}`.roles WHERE nombre = %s", (user["rol"],))
                cursor.execute(
                    f"INSERT INTO `{TEST_DB_MANTENIMIENTO}`.usuario_rol (usuario_id, rol_id) VALUES (%s, %s)",
                    (user_id, cursor.fetchone()["id"]),
                )
            if user["tipo"] == "mecanico":
                cursor.execute(
                    f"INSERT INTO `{TEST_DB_TRANSALCA}`.mecanicos (cedula_mecanico, cedula_prefijo, nombre_mecanico, apellido_mecanico, "
                    "telefono_mecanico, especialidad_mecanico, usuario_id, estado) VALUES (%s, 'V', 'Prueba', 'Mecanico', '04140000000', 'General', %s, 1) "
                    "ON DUPLICATE KEY UPDATE usuario_id = VALUES(usuario_id), estado = 1",
                    (user["cedula"], user_id),
                )
    conn.commit()


@pytest.fixture(scope="session")
def test_databases():
    for name in (TEST_DB_TRANSALCA, TEST_DB_MANTENIMIENTO):
        assert_test_database_name(name)
    if {TEST_DB_TRANSALCA, TEST_DB_MANTENIMIENTO} & set(DEV_DATABASE_NAMES.values()):
        raise RuntimeError("Las bases de prueba no pueden coincidir con las de desarrollo.")

    try:
        server = _server_connection()
    except pymysql.MySQLError as exc:
        pytest.skip(f"MariaDB/MySQL de prueba no disponible en {TEST_DB_HOST}:{TEST_DB_PORT} ({exc}).")

    mapping = {
        DEV_DATABASE_NAMES["transalca"]: TEST_DB_TRANSALCA,
        DEV_DATABASE_NAMES["mantenimiento"]: TEST_DB_MANTENIMIENTO,
    }
    with server.cursor() as cursor:
        for name in (TEST_DB_TRANSALCA, TEST_DB_MANTENIMIENTO):
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci")
    server.close()

    for key, name in (("mantenimiento", TEST_DB_MANTENIMIENTO), ("transalca", TEST_DB_TRANSALCA)):
        conn = _server_connection(name)
        try:
            if not TEST_DB_KEEP or not _database_has_tables(conn, name):
                drop_all_tables(conn, name)
                load_schema(conn, key, mapping)
        finally:
            conn.close()

    conn = _server_connection(TEST_DB_MANTENIMIENTO)
    try:
        _seed_test_users(conn)
    finally:
        conn.close()

    from config import config as app_config
    from model.connection import Connection

    originals = {
        "transalca": dict(app_config.DB_CONFIG_TRANSALCA),
        "mantenimiento": dict(app_config.DB_CONFIG_MANTENIMIENTO),
    }
    overrides = {"host": TEST_DB_HOST, "port": TEST_DB_PORT, "user": TEST_DB_USER, "password": TEST_DB_PASSWORD}
    app_config.DB_CONFIG_TRANSALCA.update(overrides, database=TEST_DB_TRANSALCA)
    app_config.DB_CONFIG_MANTENIMIENTO.update(overrides, database=TEST_DB_MANTENIMIENTO)
    _reset_cached_connections(Connection)

    yield {"transalca": TEST_DB_TRANSALCA, "mantenimiento": TEST_DB_MANTENIMIENTO}

    _reset_cached_connections(Connection)
    app_config.DB_CONFIG_TRANSALCA.clear()
    app_config.DB_CONFIG_TRANSALCA.update(originals["transalca"])
    app_config.DB_CONFIG_MANTENIMIENTO.clear()
    app_config.DB_CONFIG_MANTENIMIENTO.update(originals["mantenimiento"])


def _reset_cached_connections(connection_cls):
    for attr in ("mantenimiento", "transalca"):
        conn = getattr(connection_cls._local, attr, None)
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
        setattr(connection_cls._local, attr, None)


@pytest.fixture
def db(test_databases):
    conns = {key: _server_connection(name) for key, name in test_databases.items()}
    yield conns
    for conn in conns.values():
        conn.close()


@pytest.fixture(autouse=True)
def external_services_stubbed(request, monkeypatch):
    if request.node.get_closest_marker("unit"):
        yield None
        return
    from model.mail_service import MailService

    sent = []

    def _fake_send(name):
        def _send(*args, **kwargs):
            sent.append(name)
            return True
        return staticmethod(_send)

    for name in dir(MailService):
        if name.startswith("send_") or name == "_send_mime_message":
            monkeypatch.setattr(MailService, name, _fake_send(name))
    fake_bcv = lambda *a, **k: dict(FAKE_RATES)
    fake_usdt = lambda *a, **k: FAKE_USDT_VES
    monkeypatch.setattr("model.bcv_rate_model.get_bcv_rates", fake_bcv)
    monkeypatch.setattr("model.binance_rate_model.get_usdt_rate_ves", fake_usdt)
    monkeypatch.setattr("controller.pricing_controller.get_bcv_rates", fake_bcv)
    monkeypatch.setattr("controller.pricing_controller.get_usdt_rate_ves", fake_usdt)
    yield sent


@pytest.fixture(scope="session")
def flask_app(test_databases):
    from app import app
    previous = {key: app.config.get(key) for key in ("SECRET_KEY", "TESTING")}
    app.config.update(SECRET_KEY="integration-tests-secret", TESTING=False)
    yield app
    app.config.update(previous)


@pytest.fixture(autouse=True)
def _app_config_for_server_tests(request):
    if request.node.get_closest_marker("unit"):
        yield
        return
    flask_app = request.getfixturevalue("flask_app")
    flask_app.config.update(SECRET_KEY="integration-tests-secret", TESTING=False)
    from controller import auth_controller
    auth_controller.login_throttle._attempts.clear()
    auth_controller.recovery_throttle.clear()
    yield


def _free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="session")
def live_server(flask_app):
    from werkzeug.serving import make_server

    port = _free_port()
    server = make_server("127.0.0.1", port, flask_app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, name="transalca-live-server", daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()
    thread.join(timeout=10)
