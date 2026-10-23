import uuid
from datetime import date, timedelta

import pytest


@pytest.fixture
def vehiculo(cliente_a):
    placa = "P" + uuid.uuid4().hex[:6].upper()
    response = cliente_a.post("/api/vehicles/", json={
        "marca": "Mazda", "modelo": "3", "anio": 2014, "placa": placa,
        "kilometraje_actual": 90000, "cliente_cedula": cliente_a.info["cedula"],
    })
    assert response.status_code == 201
    return placa


def _registrar_cambio_de_aceite(cliente, db, placa, cedula, hace_dias):
    lid = cliente.post("/api/vehicle-log/", json={
        "vehiculo_id": placa, "cliente_cedula": cedula, "descripcion": "Cambio de aceite", "aceite_usado": "20W50",
    }).get_json()["id"]
    with db["transalca"].cursor() as cursor:
        cursor.execute("UPDATE bitacora_vehiculo SET fecha_bitacora = %s WHERE id_bitacora_vehiculo = %s",
                       (date.today() - timedelta(days=hace_dias), lid))
    return lid


def _prediccion(db, placa, tipo):
    with db["transalca"].cursor() as cursor:
        cursor.execute("SELECT * FROM bitacora_prediccion WHERE vehiculo_placa = %s AND tipo_prediccion = %s", (placa, tipo))
        return cursor.fetchone()


class TestCicloDePredicciones:

    def test_aceite_vencido_genera_prediccion_critica_y_notifica(self, admin, cliente_a, db, vehiculo):
        _registrar_cambio_de_aceite(cliente_a, db, vehiculo, cliente_a.info["cedula"], hace_dias=200)
        response = admin.post("/api/vehicle-log/run-cycle")
        assert response.status_code == 200
        assert response.get_json()["data"]["predicciones"] >= 2

        aceite = _prediccion(db, vehiculo, "aceite")
        assert aceite["fecha_base"] == date.today() - timedelta(days=200)
        assert aceite["fecha_estimada"] == date.today() - timedelta(days=20)
        assert (aceite["prioridad_prediccion"], aceite["estado"], aceite["notificado"]) == ("critica", "vencida", 1)
        titulos = [n.get("titulo") or "" for n in cliente_a.get("/api/notifications/").get_json()["data"]]
        assert any("Cambio de aceite" in t and "vencido" in t for t in titulos)

    @pytest.mark.parametrize("hace_dias, prioridad", [(175, "alta"), (150, "media"), (30, "baja")])
    def test_prioridad_segun_dias_restantes(self, admin, cliente_a, db, vehiculo, hace_dias, prioridad):
        _registrar_cambio_de_aceite(cliente_a, db, vehiculo, cliente_a.info["cedula"], hace_dias=hace_dias)
        admin.post("/api/vehicle-log/run-cycle")
        aceite = _prediccion(db, vehiculo, "aceite")
        assert (aceite["prioridad_prediccion"], aceite["estado"]) == (prioridad, "activa")

    def test_repetir_el_ciclo_no_duplica_ni_renotifica(self, admin, cliente_a, db, vehiculo):
        _registrar_cambio_de_aceite(cliente_a, db, vehiculo, cliente_a.info["cedula"], hace_dias=200)
        admin.post("/api/vehicle-log/run-cycle")
        notificaciones = len(cliente_a.get("/api/notifications/").get_json()["data"])
        admin.post("/api/vehicle-log/run-cycle")
        with db["transalca"].cursor() as cursor:
            cursor.execute("SELECT COUNT(*) AS n FROM bitacora_prediccion WHERE vehiculo_placa = %s AND tipo_prediccion = 'aceite'", (vehiculo,))
            assert cursor.fetchone()["n"] == 1
        assert len(cliente_a.get("/api/notifications/").get_json()["data"]) == notificaciones

    def test_el_cliente_ve_sus_predicciones_y_las_atendidas_desaparecen(self, admin, cliente_a, db, vehiculo):
        _registrar_cambio_de_aceite(cliente_a, db, vehiculo, cliente_a.info["cedula"], hace_dias=200)
        admin.post("/api/vehicle-log/run-cycle")
        propias = cliente_a.get(f"/api/vehicle-log/predictions/client/{cliente_a.info['cedula']}").get_json()["data"]
        aceite = next(p for p in propias if p["tipo_prediccion"] == "aceite" and p["vehiculo_placa"] == vehiculo)
        assert aceite["tipo_label"] == "Cambio de aceite"

        assert admin.put(f"/api/vehicle-log/predictions/{aceite['id']}/attend").status_code == 200
        restantes = cliente_a.get(f"/api/vehicle-log/predictions/client/{cliente_a.info['cedula']}").get_json()["data"]
        assert aceite["id"] not in [p["id"] for p in restantes]

    def test_una_prediccion_atendida_no_se_reactiva_si_no_hay_registros_nuevos(self, admin, cliente_a, db, vehiculo):
        _registrar_cambio_de_aceite(cliente_a, db, vehiculo, cliente_a.info["cedula"], hace_dias=200)
        admin.post("/api/vehicle-log/run-cycle")
        pid = _prediccion(db, vehiculo, "aceite")["id_bitacora_prediccion"]
        admin.put(f"/api/vehicle-log/predictions/{pid}/attend")
        admin.post("/api/vehicle-log/run-cycle")
        assert _prediccion(db, vehiculo, "aceite")["estado"] == "atendida"

    def test_un_registro_nuevo_reprograma_la_prediccion(self, admin, cliente_a, db, vehiculo):
        _registrar_cambio_de_aceite(cliente_a, db, vehiculo, cliente_a.info["cedula"], hace_dias=200)
        admin.post("/api/vehicle-log/run-cycle")
        _registrar_cambio_de_aceite(cliente_a, db, vehiculo, cliente_a.info["cedula"], hace_dias=1)
        admin.post("/api/vehicle-log/run-cycle")
        aceite = _prediccion(db, vehiculo, "aceite")
        assert aceite["fecha_estimada"] == date.today() + timedelta(days=179)
        assert (aceite["estado"], aceite["notificado"]) == ("activa", 0)


class TestAccesoAPredicciones:

    def test_solo_empleados_ejecutan_el_ciclo_y_ven_todas(self, cliente_a):
        assert cliente_a.post("/api/vehicle-log/run-cycle").status_code == 403
        assert cliente_a.get("/api/vehicle-log/predictions").status_code == 403
        assert cliente_a.put("/api/vehicle-log/predictions/1/attend").status_code == 403

    def test_otro_cliente_no_ve_las_predicciones(self, cliente_a, cliente_b):
        assert cliente_b.get(f"/api/vehicle-log/predictions/client/{cliente_a.info['cedula']}").status_code == 403

    def test_filtros_del_listado_de_empleados(self, admin, cliente_a, db, vehiculo):
        _registrar_cambio_de_aceite(cliente_a, db, vehiculo, cliente_a.info["cedula"], hace_dias=200)
        admin.post("/api/vehicle-log/run-cycle")
        filtradas = admin.get("/api/vehicle-log/predictions", query_string={"vehiculo": vehiculo, "prioridad": "critica"}).get_json()["data"]
        assert filtradas and all(p["vehiculo_placa"] == vehiculo and p["prioridad"] == "critica" for p in filtradas)
