from datetime import date, timedelta

import pytest

EMPRESA = "J-55656666-5"


def _crear_credito(admin, total="100.00", **overrides):
    data = {
        "cliente_cedula": EMPRESA,
        "total": total,
        "fecha_inicio": date.today().isoformat(),
        "fecha_fin": (date.today() + timedelta(days=30)).isoformat(),
    }
    data.update(overrides)
    return admin.post("/api/credit/", json=data)


@pytest.fixture
def credito(admin):
    response = _crear_credito(admin)
    assert response.status_code == 200, response.get_json()
    return response.get_json()["data"]["id"]


def _estado(db, orden):
    with db["transalca"].cursor() as cursor:
        cursor.execute("SELECT estado_credito FROM creditos_orden_venta WHERE orden_venta_id = %s", (orden,))
        return cursor.fetchone()["estado_credito"]


def _abonar(admin, orden, monto):
    return admin.put(f"/api/credit/{orden}/payment", json={"monto": monto})


class TestAbonos:

    def test_abono_parcial_reduce_la_deuda(self, admin, db, credito):
        response = _abonar(admin, credito, "40")
        assert response.status_code == 200
        assert response.get_json()["data"] == {"monto_deuda": "60.00", "pagado": False}
        assert _estado(db, credito) == "activo"
        pagos = admin.get(f"/api/credit/{credito}/payments").get_json()["data"]
        assert [float(p["monto_pago"]) for p in pagos] == [40.0]

    def test_abono_mayor_a_la_deuda_se_rechaza(self, admin, db, credito):
        _abonar(admin, credito, "40")
        response = _abonar(admin, credito, "70")
        assert response.status_code == 400
        assert _estado(db, credito) == "activo"

    def test_pagar_el_saldo_completo_marca_pagado(self, admin, db, credito):
        _abonar(admin, credito, "40")
        assert _abonar(admin, credito, "60").status_code == 200
        assert _estado(db, credito) == "pagado"
        assert _abonar(admin, credito, "1").status_code == 400

    @pytest.mark.parametrize("monto", ["0", "-10", "abc", "", None, pytest.param("NaN", marks=pytest.mark.xfail(
        strict=True, reason="BUG-VAL-02: el abono 'NaN' pasa el redondeo y la comparacion 'monto <= 0' lanza InvalidOperation (500)"))])
    def test_monto_invalido_devuelve_400(self, admin, credito, monto):
        response = _abonar(admin, credito, monto)
        assert response.status_code == 400
        assert "monto" in response.get_json()["errors"]

    def test_abono_con_coma_decimal(self, admin, credito):
        response = _abonar(admin, credito, "10,50")
        assert response.status_code == 200
        assert response.get_json()["data"]["monto_deuda"] == "89.50"


class TestReversionYAnulacion:

    def test_revertir_el_ultimo_abono_restaura_la_deuda(self, admin, db, credito):
        _abonar(admin, credito, "40")
        _abonar(admin, credito, "60")
        assert _estado(db, credito) == "pagado"
        assert admin.put(f"/api/credit/{credito}/revert").status_code == 200
        assert _estado(db, credito) == "activo"
        pagos_vigentes = [p for p in admin.get(f"/api/credit/{credito}/payments").get_json()["data"] if not p.get("revertido")]
        assert [float(p["monto_pago"]) for p in pagos_vigentes] == [40.0]

    def test_revertir_sin_abonos_devuelve_400(self, admin, credito):
        assert admin.put(f"/api/credit/{credito}/revert").status_code == 400

    def test_anular_bloquea_nuevas_operaciones(self, admin, db, credito):
        assert admin.put(f"/api/credit/{credito}/anular").status_code == 200
        assert _estado(db, credito) == "anulado"
        assert _abonar(admin, credito, "10").status_code == 400
        assert admin.put(f"/api/credit/{credito}/anular").status_code == 400

    def test_no_se_puede_anular_un_credito_pagado(self, admin, db, credito):
        _abonar(admin, credito, "100")
        assert admin.put(f"/api/credit/{credito}/anular").status_code == 400
        assert _estado(db, credito) == "pagado"

    def test_credito_inexistente_devuelve_404(self, admin):
        assert _abonar(admin, 99999999, "10").status_code == 404


class TestCreacionDeCredito:

    @pytest.mark.parametrize("campo, valor", [
        ("total", "0"), ("total", "-50"), ("total", "cien"),
        ("fecha_inicio", "2026-13-40"), ("fecha_fin", "ayer"),
        ("cliente_cedula", ""),
    ])
    def test_datos_invalidos_devuelven_400(self, admin, campo, valor):
        response = _crear_credito(admin, **{campo: valor})
        assert response.status_code == 400

    def test_fecha_fin_anterior_al_inicio(self, admin):
        response = _crear_credito(admin, fecha_inicio="2026-10-10", fecha_fin="2026-10-01")
        assert response.status_code == 400
        assert "fecha_fin" in response.get_json()["errors"]

    def test_solo_empresas_pueden_tener_credito(self, admin, cliente_a):
        response = _crear_credito(admin, cliente_cedula=cliente_a.info["cedula"])
        assert response.status_code == 400

    def test_cliente_no_puede_ver_ni_operar_creditos(self, cliente_a, credito):
        assert cliente_a.get("/api/credit/").status_code == 403
        assert _abonar(cliente_a, credito, "10").status_code == 403
