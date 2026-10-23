import pytest

from helpers.api_client import unique_letters


def _datos(**overrides):
    data = {"nombre": "Metodo " + unique_letters(), "datos_pago": "Banco Prueba 0102", "moneda": "usd", "permite_credito": False}
    data.update(overrides)
    return data


def _fila(db, method_id):
    with db["transalca"].cursor() as cursor:
        cursor.execute("SELECT nombre_metodo_pago, moneda, permite_credito, datos_metodo_pago, estado FROM metodos_pago WHERE id_metodo_pago = %s", (method_id,))
        return cursor.fetchone()


class TestCrud:

    def test_crear_y_consultar(self, admin, db):
        data = _datos(moneda="bolivares", permite_credito="on")
        response = admin.post("/api/payment-methods/", json=data)
        assert response.status_code == 201
        method_id = response.get_json()["id"]
        assert _fila(db, method_id) == {
            "nombre_metodo_pago": data["nombre"], "moneda": "bs", "permite_credito": 1,
            "datos_metodo_pago": "Banco Prueba 0102", "estado": 1,
        }
        detalle = admin.get(f"/api/payment-methods/{method_id}").get_json()["data"]
        assert detalle["nombre"] == data["nombre"]
        assert detalle["moneda"] == "bs"

    def test_actualizar(self, admin, db):
        method_id = admin.post("/api/payment-methods/", json=_datos()).get_json()["id"]
        nuevo = _datos(moneda="ves")
        assert admin.put(f"/api/payment-methods/{method_id}", json=nuevo).status_code == 200
        fila = _fila(db, method_id)
        assert (fila["nombre_metodo_pago"], fila["moneda"]) == (nuevo["nombre"], "bs")

    def test_eliminar_y_volver_a_crear_reactiva_el_mismo_registro(self, admin, db):
        data = _datos()
        method_id = admin.post("/api/payment-methods/", json=data).get_json()["id"]
        assert admin.delete(f"/api/payment-methods/{method_id}").status_code == 200
        assert _fila(db, method_id)["estado"] == 0
        assert method_id not in [m["id"] for m in admin.get("/api/payment-methods/active").get_json()["data"]]
        assert admin.post("/api/payment-methods/", json=data).get_json()["id"] == method_id
        assert _fila(db, method_id)["estado"] == 1

    def test_nombre_duplicado_sin_distinguir_mayusculas(self, admin):
        data = _datos()
        admin.post("/api/payment-methods/", json=data)
        response = admin.post("/api/payment-methods/", json=_datos(nombre=data["nombre"].upper()))
        assert response.status_code == 400
        assert "nombre" in response.get_json()["errors"]

    def test_actualizar_con_nombre_de_otro_metodo(self, admin):
        primero = _datos()
        admin.post("/api/payment-methods/", json=primero)
        segundo = admin.post("/api/payment-methods/", json=_datos()).get_json()["id"]
        response = admin.put(f"/api/payment-methods/{segundo}", json=_datos(nombre=primero["nombre"]))
        assert response.status_code == 400

    def test_check_unique(self, admin):
        data = _datos()
        method_id = admin.post("/api/payment-methods/", json=data).get_json()["id"]
        assert admin.get("/api/payment-methods/check-unique", query_string={"value": data["nombre"]}).get_json()["unique"] is False
        assert admin.get("/api/payment-methods/check-unique", query_string={"value": data["nombre"], "exclude": method_id}).get_json()["unique"] is True

    @pytest.mark.parametrize("method", ["GET", "PUT", "DELETE"])
    def test_metodo_inexistente_devuelve_404(self, admin, method):
        assert admin.open("/api/payment-methods/99999999", method=method, json=_datos()).status_code == 404


class TestValidaciones:

    @pytest.mark.parametrize("campo, valor", [
        ("nombre", ""), ("nombre", "ab"), ("nombre", "N" * 101), ("nombre", "<b>Zelle</b>"),
        ("datos_pago", ""), ("datos_pago", "D" * 81),
        ("moneda", "eur"), ("moneda", "bitcoin"),
        pytest.param("moneda", 5, marks=pytest.mark.xfail(
            strict=True, reason="BUG-PM-01: una moneda no textual hace fallar .strip() en el modelo y responde 500")),
    ])
    def test_datos_invalidos_devuelven_400(self, admin, campo, valor):
        response = admin.post("/api/payment-methods/", json=_datos(**{campo: valor}))
        assert response.status_code == 400
        assert campo in response.get_json()["errors"]


class TestAcceso:

    def test_cliente_ve_los_activos_pero_no_administra(self, cliente_a):
        assert cliente_a.get("/api/payment-methods/active").status_code == 200
        assert cliente_a.get("/api/payment-methods/").status_code == 403
        assert cliente_a.post("/api/payment-methods/", json=_datos()).status_code == 403
        assert cliente_a.delete("/api/payment-methods/1").status_code == 403

    def test_sin_sesion(self, anon):
        assert anon.get("/api/payment-methods/active").status_code == 401
