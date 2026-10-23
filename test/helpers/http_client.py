import requests

from helpers.api_client import unique_cedula, unique_suffix
from helpers.test_data import TEST_PASSWORD

DEFAULT_TIMEOUT = 15


class ApiClient(requests.Session):

    def __init__(self, base_url):
        super().__init__()
        self.base_url = base_url.rstrip("/")
        self.info = {}

    def request(self, method, url, *args, **kwargs):
        if url.startswith("/"):
            url = self.base_url + url
        kwargs.setdefault("timeout", DEFAULT_TIMEOUT)
        kwargs["allow_redirects"] = kwargs.pop("follow_redirects", False)
        return super().request(method, url, *args, **kwargs)


def http_login(client, email, password=TEST_PASSWORD):
    response = client.post("/auth/do_login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return client


def http_register(client):
    data = {
        "nombre": "Cliente",
        "apellido": "Backend",
        "cedula": unique_cedula(),
        "telefono": "04141234567",
        "email": f"backend.{unique_suffix()}@transalca.test",
        "direccion": "Barquisimeto",
        "password": TEST_PASSWORD,
        "confirm_password": TEST_PASSWORD,
    }
    response = client.post("/auth/do_register", json=data)
    assert response.status_code == 200, response.text
    client.info = {"cedula": data["cedula"], "email": data["email"]}
    return client
