import pytest

from helpers.api_client import login, register_client
from helpers.test_data import TEST_USERS


@pytest.fixture
def anon(flask_app):
    return flask_app.test_client()


@pytest.fixture
def admin(flask_app):
    return login(flask_app.test_client(), TEST_USERS["admin"]["email"])


@pytest.fixture
def empleado_sin_rol(flask_app):
    return login(flask_app.test_client(), TEST_USERS["empleado"]["email"])


@pytest.fixture
def vendedor(flask_app):
    return login(flask_app.test_client(), TEST_USERS["vendedor"]["email"])


@pytest.fixture
def mecanico(flask_app):
    return login(flask_app.test_client(), TEST_USERS["mecanico"]["email"])


@pytest.fixture
def cliente_a(flask_app):
    client = flask_app.test_client()
    client.info = register_client(client)
    return login(client, client.info["email"])


@pytest.fixture
def cliente_b(flask_app):
    client = flask_app.test_client()
    client.info = register_client(client)
    return login(client, client.info["email"])
