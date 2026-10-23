import uuid

import pytest

from helpers.api_client import unique_letters


def _rif():
    return "J-" + str(uuid.uuid4().int % 90000000 + 10000000) + "-" + str(uuid.uuid4().int % 10)


class TestSucursales:

    def test_ciclo_de_vida_completo(self, admin):
        nombre = "Sucursal " + unique_letters()
        creada = admin.post("/api/sucursales/", json={"nombre": nombre, "direccion": "Av Principal", "telefono": "04141112233"})
        assert creada.status_code == 200, creada.text
        sid = creada.json()["id"]

        detalle = admin.get(f"/api/sucursales/{sid}")
        assert detalle.status_code == 200
        assert detalle.json()["data"]["nombre"] == nombre

        actualizada = admin.put(f"/api/sucursales/{sid}", json={"nombre": nombre, "direccion": "Calle Nueva"})
        assert actualizada.status_code == 200
        assert admin.get(f"/api/sucursales/{sid}").json()["data"]["direccion"] == "Calle Nueva"

        assert admin.put(f"/api/sucursales/{sid}/toggle").status_code == 200
        activas = [s["id"] for s in admin.get("/api/sucursales/active").json()["data"]]
        assert sid not in activas

    def test_sucursal_inexistente_devuelve_404(self, admin):
        assert admin.get("/api/sucursales/99999999").status_code == 404

    @pytest.mark.parametrize("payload, campo", [
        ({"nombre": ""}, "nombre"),
        ({"nombre": "ab"}, "nombre"),
        ({"nombre": "Sucursal Valida", "telefono": "123"}, "telefono"),
        ({"nombre": "Sucursal Valida", "email": "no-correo"}, "email"),
        ({"nombre": "Sucursal Valida", "direccion": "D" * 41}, "direccion"),
        ({"nombre": "<script>x</script>"}, "nombre"),
    ])
    def test_validaciones(self, admin, payload, campo):
        response = admin.post("/api/sucursales/", json=payload)
        assert response.status_code == 400
        assert campo in response.json()["errors"]


class TestServicios:

    def _payload(self, **overrides):
        data = {
            "nombre": "Servicio " + unique_letters(),
            "descripcion": "Servicio de prueba",
            "precio": "25.50",
            "duracion_estimada": 45,
            "tipo": "general",
            "sucursal_ids": [1],
        }
        data.update(overrides)
        return data

    def test_crear_consultar_y_desactivar(self, admin):
        data = self._payload()
        creado = admin.post("/api/services/", json=data)
        assert creado.status_code == 200, creado.text
        sid = creado.json()["id"]
        servicio = admin.get(f"/api/services/{sid}").json()["data"]
        assert servicio["nombre"] == data["nombre"]
        assert float(servicio["precio"]) == 25.5
        assert admin.put(f"/api/services/{sid}/toggle").status_code == 200
        assert sid not in [s["id"] for s in admin.get("/api/services/active").json()["data"]]

    @pytest.mark.parametrize("campo, valor", [
        ("precio", "0"), ("precio", "-5"), ("precio", "abc"), ("precio", "10.999"), ("precio", "100000000"),
        pytest.param("duracion_estimada", 0, marks=pytest.mark.xfail(
            strict=True, reason="BUG-SRV-01: duracion_estimada 0 se convierte en 60 sin error (data.get(...) or 60)")),
        ("duracion_estimada", -10), ("duracion_estimada", 1441), ("duracion_estimada", "rapido"),
        ("tipo", "inventado"), ("tipo", ""),
        ("sucursal_ids", ["uno"]),
        ("nombre", "S" * 201),
    ])
    def test_validaciones(self, admin, campo, valor):
        response = admin.post("/api/services/", json=self._payload(**{campo: valor}))
        assert response.status_code == 400
        errores = response.json()["errors"]
        assert campo in errores or (campo == "sucursal_ids" and "sucursal_id" in errores)

    def test_servicios_activos_son_publicos(self, anon):
        response = anon.get("/api/services/active")
        assert response.status_code == 200
        assert isinstance(response.json()["data"], list)


class TestProveedores:

    def test_crear_y_consultar_por_rif(self, admin):
        rif = _rif()
        nombre = "Proveedor " + unique_letters()
        creado = admin.post("/api/suppliers/", json={"rif": rif, "nombre": nombre, "telefono": "04241234567", "email": f"{unique_letters()}@proveedor.test"})
        assert creado.status_code == 200, creado.text
        detalle = admin.get(f"/api/suppliers/{rif}")
        assert detalle.status_code == 200
        assert detalle.json()["data"]["nombre"] == nombre

    def test_rif_duplicado_devuelve_400(self, admin):
        rif = _rif()
        payload = {"rif": rif, "nombre": "Proveedor " + unique_letters()}
        assert admin.post("/api/suppliers/", json=payload).status_code == 200
        response = admin.post("/api/suppliers/", json=dict(payload, nombre="Proveedor " + unique_letters()))
        assert response.status_code == 400

    @pytest.mark.parametrize("rif", ["", "12345678", "X-12345678-9", "J-1234-5"])
    def test_rif_invalido_devuelve_400(self, admin, rif):
        response = admin.post("/api/suppliers/", json={"rif": rif, "nombre": "Proveedor " + unique_letters()})
        assert response.status_code == 400
        assert "rif" in response.json()["errors"]
