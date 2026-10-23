import pytest

from app import app as flask_app

ADMIN = {"user_id": 1, "user_cedula": "V-10000000", "user_tipo": "admin"}
CLIENTE = {"user_id": 2, "user_cedula": "V-12345678", "user_tipo": "cliente"}


@pytest.fixture
def client():
    previo = {clave: flask_app.config.get(clave) for clave in ("TESTING", "SECRET_KEY")}
    flask_app.config.update(TESTING=True, SECRET_KEY="test-secret")
    with flask_app.test_client() as test_client:
        yield test_client
    flask_app.config.update(previo)


def _con_sesion(client, **datos):
    with client.session_transaction() as sess:
        sess.update(datos)
    return client


@pytest.fixture
def auth_admin(client):
    return _con_sesion(client, **ADMIN)


@pytest.fixture
def auth_client(auth_admin):
    return auth_admin


@pytest.fixture
def auth_employee_client(auth_admin):
    return auth_admin


@pytest.fixture
def auth_admin_user(auth_admin):
    return auth_admin


@pytest.fixture
def auth_admin_client(client):
    return _con_sesion(client, roles=["Administrador"], **ADMIN)


@pytest.fixture
def auth_regular_client(client):
    return _con_sesion(client, **CLIENTE)


@pytest.fixture
def auth_client_user(auth_regular_client):
    return auth_regular_client
