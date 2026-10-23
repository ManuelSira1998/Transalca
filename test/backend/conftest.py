import pytest

from helpers.http_client import ApiClient, http_login, http_register
from helpers.test_data import TEST_USERS


@pytest.fixture
def anon(live_server):
    with ApiClient(live_server) as client:
        yield client


@pytest.fixture
def admin(live_server):
    with ApiClient(live_server) as client:
        yield http_login(client, TEST_USERS["admin"]["email"])


@pytest.fixture
def empleado_sin_rol(live_server):
    with ApiClient(live_server) as client:
        yield http_login(client, TEST_USERS["empleado"]["email"])


@pytest.fixture
def vendedor(live_server):
    with ApiClient(live_server) as client:
        yield http_login(client, TEST_USERS["vendedor"]["email"])


@pytest.fixture
def mecanico(live_server):
    with ApiClient(live_server) as client:
        yield http_login(client, TEST_USERS["mecanico"]["email"])


def _cliente(live_server):
    client = ApiClient(live_server)
    http_register(client)
    return http_login(client, client.info["email"])


@pytest.fixture
def cliente_a(live_server):
    with _cliente(live_server) as client:
        yield client


@pytest.fixture
def cliente_b(live_server):
    with _cliente(live_server) as client:
        yield client


@pytest.fixture(scope="session")
def cliente_compartido(live_server):
    with _cliente(live_server) as client:
        yield client
