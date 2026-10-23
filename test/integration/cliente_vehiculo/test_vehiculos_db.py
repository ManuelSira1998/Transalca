import uuid

import pytest


def _placa():
    return "T" + uuid.uuid4().hex[:6].upper()


def _vehiculo(cliente, **overrides):
    data = {
        "marca": "Toyota",
        "modelo": "Corolla",
        "anio": 2015,
        "placa": _placa(),
        "color": "Gris",
        "tipo_combustible": "gasolina",
        "kilometraje_actual": 120000,
        "cliente_cedula": cliente.info["cedula"],
    }
    data.update(overrides)
    return data


def _registrar(cliente, **overrides):
    data = _vehiculo(cliente, **overrides)
    response = cliente.post("/api/vehicles/", json=data)
    assert response.status_code == 201, response.get_json()
    return data


class TestRegistroVehiculo:

    def test_cliente_registra_su_vehiculo_y_queda_vinculado(self, cliente_a, db):
        data = _registrar(cliente_a)
        with db["transalca"].cursor() as cursor:
            cursor.execute("SELECT marca_vehiculo, modelo_vehiculo, kilometraje_actual FROM vehiculos WHERE placa_vehiculo = %s", (data["placa"],))
            fila = cursor.fetchone()
            cursor.execute("SELECT cliente_cedula FROM cliente_vehiculo WHERE vehiculo_placa = %s", (data["placa"],))
            vinculos = [r["cliente_cedula"] for r in cursor.fetchall()]
        assert fila == {"marca_vehiculo": "Toyota", "modelo_vehiculo": "Corolla", "kilometraje_actual": 120000}
        assert vinculos == [cliente_a.info["cedula"]]

    def test_el_vehiculo_aparece_en_el_listado_del_cliente(self, cliente_a):
        data = _registrar(cliente_a)
        placas = [v.get("placa") or v.get("placa_vehiculo") for v in cliente_a.get("/api/vehicles/").get_json()["data"]]
        assert data["placa"] in placas

    def test_placa_duplicada_devuelve_400(self, cliente_a):
        data = _registrar(cliente_a)
        response = cliente_a.post("/api/vehicles/", json=_vehiculo(cliente_a, placa=data["placa"]))
        assert response.status_code == 400
        assert "placa" in response.get_json()["errors"]

    @pytest.mark.parametrize("campo, valor", [
        ("marca", ""),
        ("modelo", None),
        ("anio", 1800),
        ("anio", 3000),
        ("anio", "dos mil"),
        ("placa", "AB"),
        ("placa", "ABC 123!"),
        ("placa", "' OR 1=1 --"),
        ("tipo_combustible", "nuclear"),
        ("kilometraje_actual", -5),
        ("kilometraje_actual", 10 ** 9),
    ])
    def test_datos_invalidos_devuelven_400(self, cliente_a, campo, valor):
        response = cliente_a.post("/api/vehicles/", json=_vehiculo(cliente_a, **{campo: valor}))
        assert response.status_code == 400
        assert campo in response.get_json()["errors"]

    def test_sin_sesion_devuelve_401(self, anon):
        assert anon.post("/api/vehicles/", json={"placa": _placa()}).status_code == 401


class TestPropiedadVehiculo:

    def test_cliente_no_puede_registrar_vehiculo_a_nombre_de_otro(self, cliente_a, cliente_b, db):
        data = _vehiculo(cliente_a, cliente_cedula=cliente_b.info["cedula"])
        response = cliente_a.post("/api/vehicles/", json=data)
        assert response.status_code == 403
        with db["transalca"].cursor() as cursor:
            cursor.execute("SELECT COUNT(*) AS n FROM vehiculos WHERE placa_vehiculo = %s", (data["placa"],))
            assert cursor.fetchone()["n"] == 0

    def test_cliente_no_puede_ver_vehiculo_ajeno(self, cliente_a, cliente_b):
        data = _registrar(cliente_a)
        assert cliente_b.get(f"/api/vehicles/{data['placa']}").status_code == 403

    def test_cliente_no_puede_modificar_ni_borrar_vehiculo_ajeno(self, cliente_a, cliente_b, db):
        data = _registrar(cliente_a)
        assert cliente_b.put(f"/api/vehicles/{data['placa']}", json=dict(data, color="Rojo")).status_code == 403
        assert cliente_b.delete(f"/api/vehicles/{data['placa']}").status_code == 403
        with db["transalca"].cursor() as cursor:
            cursor.execute("SELECT color_vehiculo, estado FROM vehiculos WHERE placa_vehiculo = %s", (data["placa"],))
            assert cursor.fetchone() == {"color_vehiculo": "Gris", "estado": 1}

    def test_listado_de_un_cliente_no_incluye_vehiculos_de_otro(self, cliente_a, cliente_b):
        data = _registrar(cliente_a)
        placas_b = [v.get("placa") or v.get("placa_vehiculo") for v in cliente_b.get("/api/vehicles/").get_json()["data"]]
        assert data["placa"] not in placas_b

    def test_parametro_cliente_es_ignorado_para_clientes(self, cliente_a, cliente_b):
        data = _registrar(cliente_a)
        response = cliente_b.get("/api/vehicles/", query_string={"cliente": cliente_a.info["cedula"]})
        placas = [v.get("placa") or v.get("placa_vehiculo") for v in response.get_json()["data"]]
        assert data["placa"] not in placas

    def test_empleado_puede_consultar_cualquier_vehiculo(self, cliente_a, admin):
        data = _registrar(cliente_a)
        assert admin.get(f"/api/vehicles/{data['placa']}").status_code == 200
