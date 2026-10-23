import uuid

import pytest


@pytest.fixture
def vehiculo(cliente_a):
    placa = "B" + uuid.uuid4().hex[:6].upper()
    response = cliente_a.post("/api/vehicles/", json={
        "marca": "Chevrolet", "modelo": "Aveo", "anio": 2010, "placa": placa,
        "kilometraje_actual": 150000, "cliente_cedula": cliente_a.info["cedula"],
    })
    assert response.status_code == 201, response.get_json()
    return placa


def _registro(cliente, placa, cedula, **extra):
    data = {
        "vehiculo_id": placa,
        "cliente_cedula": cedula,
        "descripcion": "Cambio de aceite y filtro",
        "kilometraje": 151000,
        "aceite_usado": "15W40",
        "filtros_usados": "Filtro de aceite",
    }
    data.update(extra)
    return cliente.post("/api/vehicle-log/", json=data)


class TestHistorial:

    def test_registrar_mantenimiento_y_consultarlo(self, cliente_a, vehiculo):
        response = _registro(cliente_a, vehiculo, cliente_a.info["cedula"])
        assert response.status_code == 201
        lid = response.get_json()["id"]

        historial = cliente_a.get(f"/api/vehicle-log/vehicle/{vehiculo}").get_json()["data"]
        assert lid in [r["id"] for r in historial]
        detalle = cliente_a.get(f"/api/vehicle-log/{lid}").get_json()["data"]
        assert detalle["descripcion"] == "Cambio de aceite y filtro"
        assert int(detalle["kilometraje"]) == 151000

    def test_el_historial_del_cliente_incluye_el_registro(self, cliente_a, vehiculo):
        lid = _registro(cliente_a, vehiculo, cliente_a.info["cedula"]).get_json()["id"]
        datos = cliente_a.get(f"/api/vehicle-log/client/{cliente_a.info['cedula']}").get_json()["data"]
        assert lid in [r["id"] for r in datos]

    def test_el_empleado_puede_registrar_para_cualquier_cliente(self, admin, cliente_a, vehiculo):
        assert _registro(admin, vehiculo, cliente_a.info["cedula"]).status_code == 201

    @pytest.mark.parametrize("faltante", ["vehiculo_id", "cliente_cedula"])
    def test_datos_incompletos_devuelven_400(self, cliente_a, vehiculo, faltante):
        response = _registro(cliente_a, vehiculo, cliente_a.info["cedula"], **{faltante: ""})
        assert response.status_code == 400

    def test_vehiculo_inexistente_devuelve_404(self, cliente_a):
        assert _registro(cliente_a, "NOEXISTE9", cliente_a.info["cedula"]).status_code == 404

    @pytest.mark.parametrize("kilometraje", [
        pytest.param("ciento mil", marks=pytest.mark.xfail(strict=True, reason="BUG-VLOG-01: el kilometraje no se valida; un texto falla en la base de datos y responde 500")),
        pytest.param(-500, marks=pytest.mark.xfail(strict=True, reason="BUG-VLOG-01: el kilometraje no se valida; se guardan valores negativos")),
    ])
    def test_kilometraje_invalido_devuelve_400(self, cliente_a, vehiculo, kilometraje):
        response = _registro(cliente_a, vehiculo, cliente_a.info["cedula"], kilometraje=kilometraje)
        assert response.status_code == 400


class TestPropiedadDelHistorial:

    def test_otro_cliente_no_ve_el_historial(self, cliente_a, cliente_b, vehiculo):
        lid = _registro(cliente_a, vehiculo, cliente_a.info["cedula"]).get_json()["id"]
        assert cliente_b.get(f"/api/vehicle-log/{lid}").status_code == 403
        assert cliente_b.get(f"/api/vehicle-log/vehicle/{vehiculo}").status_code == 403
        assert cliente_b.get(f"/api/vehicle-log/client/{cliente_a.info['cedula']}").status_code == 403

    def test_otro_cliente_no_puede_escribir_en_el_historial_ajeno(self, cliente_a, cliente_b, vehiculo):
        assert _registro(cliente_b, vehiculo, cliente_a.info["cedula"]).status_code == 403
        assert _registro(cliente_b, vehiculo, cliente_b.info["cedula"]).status_code in (400, 403)

    def test_el_listado_administrativo_es_solo_para_empleados(self, cliente_a, admin):
        assert cliente_a.get("/api/vehicle-log/admin").status_code == 403
        assert admin.get("/api/vehicle-log/admin").status_code == 200
