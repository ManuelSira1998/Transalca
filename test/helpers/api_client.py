import uuid

from helpers.test_data import TEST_PASSWORD


def unique_suffix():
    return uuid.uuid4().hex[:8]


def unique_cedula():
    return "V-" + str(uuid.uuid4().int % 90000000 + 10000000)


def login(client, email, password=TEST_PASSWORD):
    response = client.post("/auth/do_login", json={"email": email, "password": password})
    assert response.status_code == 200, response.get_json()
    return client


def register_client(client):
    cedula = unique_cedula()
    email = f"cliente.{unique_suffix()}@transalca.test"
    payload = {
        "nombre": "Cliente",
        "apellido": "Prueba",
        "cedula": cedula,
        "telefono": "04141234567",
        "email": email,
        "direccion": "Barquisimeto",
        "password": TEST_PASSWORD,
        "confirm_password": TEST_PASSWORD,
    }
    response = client.post("/auth/do_register", json=payload)
    assert response.status_code == 200, response.get_json()
    return {"cedula": cedula, "email": email}


def unique_letters(length=8):
    alphabet = "abcdefghijklmnopqrstuvwxyz"
    value = uuid.uuid4().int
    letters = []
    for _ in range(length):
        value, index = divmod(value, len(alphabet))
        letters.append(alphabet[index])
    return "".join(letters)
