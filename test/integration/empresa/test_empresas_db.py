import uuid
from datetime import date, timedelta

import pytest

from helpers.api_client import unique_letters


def _rif():
    return "J-" + str(uuid.uuid4().int % 90000000 + 10000000) + "-" + str(uuid.uuid4().int % 10)


def _empresa(**overrides):
    data = {
        "rif": _rif(),
        "razon_social": "Transportes " + unique_letters(),
        "nombre_comercial": "Flota Prueba",
        "telefono": "04241234567",
        "email": f"{unique_letters()}@empresa.test",
        "direccion": "Zona Industrial",
        "sector": "Transporte",
        "limite_credito": "5000",
        "dias_credito": 30,
    }
    data.update(overrides)
    return data


@pytest.fixture
def empresa(admin):
    data = _empresa()
    response = admin.post("/api/companies/", json=data)
    assert response.status_code == 201, response.get_json()
    return data


class TestEmpresas:

    def test_crear_y_consultar_por_rif(self, admin, db, empresa):
        detalle = admin.get(f"/api/companies/{empresa['rif']}").get_json()["data"]
        assert detalle["razon_social"] == empresa["razon_social"]
        assert detalle["flota"] == [] and detalle["ordenes"] == []
        with db["transalca"].cursor() as cursor:
            cursor.execute(
                "SELECT c.tipo_cliente, j.dias_credito FROM cliente c JOIN cliente_juridico j ON j.id_cliente = c.id_cliente "
                "WHERE c.identificador_cliente = %s", (empresa["rif"],))
            assert cursor.fetchone() == {"tipo_cliente": "juridica", "dias_credito": 30}

    def test_rif_duplicado(self, admin, empresa):
        response = admin.post("/api/companies/", json=_empresa(rif=empresa["rif"]))
        assert response.status_code == 400
        assert "rif" in response.get_json()["errors"]

    def test_correo_de_otra_cuenta(self, admin, empresa):
        response = admin.post("/api/companies/", json=_empresa(email=empresa["email"]))
        assert response.status_code == 400
        assert "email" in response.get_json()["errors"]

    @pytest.mark.parametrize("campo, valor", [
        ("rif", "12345678"), ("rif", "J-123"), ("razon_social", ""), ("razon_social", "R" * 61),
        ("telefono", "555"), ("email", "sin-arroba"), ("limite_credito", "-1"), ("limite_credito", "mucho"),
        ("dias_credito", 366), ("dias_credito", -5), ("direccion", "D" * 41),
    ])
    def test_datos_invalidos(self, admin, campo, valor):
        response = admin.post("/api/companies/", json=_empresa(**{campo: valor}))
        assert response.status_code == 400
        assert campo in response.get_json()["errors"]

    def test_actualizar(self, admin, empresa):
        cambios = dict(empresa, sector="Construccion", dias_credito=15)
        assert admin.put(f"/api/companies/{empresa['rif']}", json=cambios).status_code == 200
        detalle = admin.get(f"/api/companies/{empresa['rif']}").get_json()["data"]
        assert detalle["sector"] == "Construccion"

    def test_desactivar(self, admin, empresa):
        assert admin.put(f"/api/companies/{empresa['rif']}/toggle").status_code == 200
        activas = [e.get("rif") for e in admin.get("/api/companies/", query_string={"estado": "1"}).get_json()["data"]]
        assert empresa["rif"] not in activas

    def test_check_unique_de_rif(self, admin, empresa):
        assert admin.post("/api/companies/check-unique", json={"field": "rif", "value": empresa["rif"]}).get_json()["exists"] is True
        assert admin.post("/api/companies/check-unique", json={"field": "rif", "value": _rif()}).get_json()["exists"] is False
        assert admin.post("/api/companies/check-unique", json={"field": "otro", "value": "x"}).status_code == 400

    def test_empresa_inexistente(self, admin):
        assert admin.get(f"/api/companies/{_rif()}").status_code == 404

    def test_estadisticas(self, admin, empresa):
        datos = admin.get("/api/companies/stats").get_json()["data"]
        assert int(datos.get("total", 0)) >= 1

    def test_la_empresa_nueva_puede_recibir_credito(self, admin, empresa):
        response = admin.post("/api/credit/", json={
            "cliente_cedula": empresa["rif"], "total": "250",
            "fecha_inicio": date.today().isoformat(), "fecha_fin": (date.today() + timedelta(days=30)).isoformat(),
        })
        assert response.status_code == 200

    def test_cliente_no_accede_a_empresas(self, cliente_a, empresa):
        assert cliente_a.get("/api/companies/").status_code == 403
        assert cliente_a.get(f"/api/companies/{empresa['rif']}").status_code == 403
        assert cliente_a.post("/api/companies/", json=_empresa()).status_code == 403
