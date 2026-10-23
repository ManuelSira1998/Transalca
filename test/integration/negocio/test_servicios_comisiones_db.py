import uuid

import pytest

from helpers.test_data import MECANICO_AJENO, TEST_USERS

SERVICIO = 4
PRECIO_SERVICIO = 50.0
MECANICO = TEST_USERS["mecanico"]["cedula"]


@pytest.fixture
def vehiculo(cliente_a):
    placa = "S" + uuid.uuid4().hex[:6].upper()
    response = cliente_a.post("/api/vehicles/", json={
        "marca": "Ford", "modelo": "Fiesta", "anio": 2012, "placa": placa,
        "cliente_cedula": cliente_a.info["cedula"],
    })
    assert response.status_code == 201, response.get_json()
    return {"placa": placa, "cliente": cliente_a.info["cedula"]}


def _asignar(admin, vehiculo, mecanico=MECANICO, **extra):
    data = {
        "servicio_id": SERVICIO,
        "mecanico_cedula": mecanico,
        "cliente_cedula": vehiculo["cliente"],
        "vehiculo_placa": vehiculo["placa"],
        "observaciones": "Revision general",
    }
    data.update(extra)
    response = admin.post("/api/service-mechanics/", json=data)
    assert response.status_code == 200, response.get_json()
    return response.get_json()["id"]


def _completar(admin, aid, **extra):
    return admin.put(f"/api/service-mechanics/{aid}/status", json={"estado": "completado", **extra})


def _comision(db, aid):
    with db["transalca"].cursor() as cursor:
        cursor.execute("SELECT precio_servicio_comision, porcentaje_comision FROM comisiones_mecanico WHERE servicio_mecanico_id = %s", (aid,))
        return cursor.fetchone()


class TestAsignacionYEstado:

    def test_asignar_con_mecanico_queda_asignado(self, admin, db, vehiculo):
        aid = _asignar(admin, vehiculo)
        with db["transalca"].cursor() as cursor:
            cursor.execute("SELECT estado_servicio, mecanico_cedula FROM servicio_mecanico WHERE id_servicio_mecanico = %s", (aid,))
            assert cursor.fetchone() == {"estado_servicio": "asignado", "mecanico_cedula": MECANICO}

    def test_sin_mecanico_queda_sin_asignar_y_no_puede_completarse(self, admin, db, vehiculo):
        aid = _asignar(admin, vehiculo, mecanico="")
        response = _completar(admin, aid)
        assert response.status_code == 400
        assert "mecanico_cedula" in response.get_json()["errors"]
        assert _comision(db, aid) is None

    @pytest.mark.parametrize("campo, valor", [
        ("servicio_id", 99999999), ("mecanico_cedula", "V-00000001"), ("vehiculo_placa", "NOEXISTE1"),
        ("cliente_cedula", ""), ("observaciones", "   "), ("estado", "terminado"),
    ])
    def test_asignacion_invalida_devuelve_400(self, admin, vehiculo, campo, valor):
        data = {
            "servicio_id": SERVICIO, "mecanico_cedula": MECANICO,
            "cliente_cedula": vehiculo["cliente"], "vehiculo_placa": vehiculo["placa"], campo: valor,
        }
        response = admin.post("/api/service-mechanics/", json=data)
        assert response.status_code == 400
        assert campo in response.get_json()["errors"]

    def test_estado_invalido_devuelve_400(self, admin, vehiculo):
        aid = _asignar(admin, vehiculo)
        assert admin.put(f"/api/service-mechanics/{aid}/status", json={"estado": "listo"}).status_code == 400

    def test_asignacion_inexistente_devuelve_404(self, admin):
        assert _completar(admin, 99999999).status_code == 404


class TestComisiones:

    def test_completar_genera_comision_con_el_porcentaje_indicado(self, admin, db, vehiculo):
        aid = _asignar(admin, vehiculo)
        response = _completar(admin, aid, porcentaje_comision=20)
        assert response.status_code == 200
        assert response.get_json()["commission_id"] == aid
        comision = _comision(db, aid)
        assert float(comision["precio_servicio_comision"]) == PRECIO_SERVICIO
        assert float(comision["porcentaje_comision"]) == 20.0
        detalle = admin.get(f"/api/commissions/{aid}").get_json()["data"]
        assert float(detalle["monto_comision"]) == 10.0

    def test_sin_porcentaje_usa_el_porcentaje_por_defecto(self, admin, db, vehiculo):
        aid = _asignar(admin, vehiculo)
        _completar(admin, aid)
        assert float(_comision(db, aid)["porcentaje_comision"]) == 30.0

    def test_el_resumen_del_mecanico_suma_sus_comisiones(self, admin, vehiculo):
        antes = admin.get(f"/api/commissions/summary/{MECANICO}").get_json()["data"]
        aid = _asignar(admin, vehiculo)
        _completar(admin, aid, porcentaje_comision=10)
        despues = admin.get(f"/api/commissions/summary/{MECANICO}").get_json()["data"]
        assert int(despues["total_servicios"]) == int(antes["total_servicios"]) + 1
        assert float(despues["total"]) == pytest.approx(float(antes["total"]) + 5.0)

    def test_recompletar_no_duplica_la_comision(self, admin, db, vehiculo):
        aid = _asignar(admin, vehiculo)
        _completar(admin, aid, porcentaje_comision=10)
        _completar(admin, aid)
        with db["transalca"].cursor() as cursor:
            cursor.execute("SELECT COUNT(*) AS n FROM comisiones_mecanico WHERE servicio_mecanico_id = %s", (aid,))
            assert cursor.fetchone()["n"] == 1
        assert float(_comision(db, aid)["porcentaje_comision"]) == 10.0

    @pytest.mark.parametrize("porcentaje", [-10, 150])
    @pytest.mark.xfail(strict=True, reason="BUG-COM-01: el porcentaje de comision no se valida; se aceptan valores negativos o mayores a 100")
    def test_porcentaje_fuera_de_rango_devuelve_400(self, admin, db, vehiculo, porcentaje):
        aid = _asignar(admin, vehiculo)
        response = _completar(admin, aid, porcentaje_comision=porcentaje)
        assert response.status_code == 400
        assert _comision(db, aid) is None


class TestRolMecanico:

    def test_el_mecanico_solo_ve_sus_comisiones(self, admin, mecanico, vehiculo):
        _completar(admin, _asignar(admin, vehiculo), porcentaje_comision=10)
        _completar(admin, _asignar(admin, vehiculo, mecanico=MECANICO_AJENO), porcentaje_comision=10)
        propias = mecanico.get("/api/commissions/").get_json()["data"]
        assert propias
        assert {c["mecanico_cedula"] for c in propias} == {MECANICO}

    def test_el_mecanico_no_ve_el_resumen_de_otro(self, mecanico):
        assert mecanico.get(f"/api/commissions/summary/{MECANICO_AJENO}").status_code == 403
        assert mecanico.get(f"/api/commissions/summary/{MECANICO}").status_code == 200

    def test_el_mecanico_no_ve_la_comision_de_otro(self, admin, mecanico, vehiculo):
        ajena = _asignar(admin, vehiculo, mecanico=MECANICO_AJENO)
        _completar(admin, ajena, porcentaje_comision=10)
        assert mecanico.get(f"/api/commissions/{ajena}").status_code == 403

    @pytest.mark.xfail(strict=True, reason="BUG-AUTHZ-04: los permisos por modulo no se aplican; un mecanico (solo lectura en comisiones) cambia el porcentaje de su propia comision")
    def test_el_mecanico_no_puede_cambiar_porcentajes(self, admin, mecanico, vehiculo):
        aid = _asignar(admin, vehiculo)
        _completar(admin, aid, porcentaje_comision=10)
        response = mecanico.put(f"/api/commissions/{aid}/percentage", json={"porcentaje_comision": 90})
        assert response.status_code == 403

    def test_un_cliente_no_ve_comisiones(self, cliente_a):
        assert cliente_a.get("/api/commissions/").status_code == 403
        assert cliente_a.get(f"/api/commissions/summary/{MECANICO}").status_code == 403
