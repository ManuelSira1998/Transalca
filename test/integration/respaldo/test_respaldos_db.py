import pytest


class TestRespaldos:

    def test_sin_sesion_devuelve_401(self, anon):
        assert anon.get("/api/backup/download/x.sql").status_code == 401
        assert anon.post("/api/backup/restore", json={"filename": "x.sql"}).status_code == 401

    def test_cliente_no_puede_restaurar(self, cliente_a):
        assert cliente_a.post("/api/backup/restore", json={"filename": "x.sql"}).status_code == 403

    def test_cliente_no_puede_crear_respaldos(self, cliente_a):
        assert cliente_a.post("/api/backup/create").status_code == 403

    @pytest.mark.parametrize("nombre", [
        "..%2F..%2Fconfig%2Fconfig.py",
        "no_existe.sql",
        pytest.param("..\\..\\app.py", marks=pytest.mark.xfail(
            strict=True,
            reason="BUG-BAK-01: el modelo rechaza el nombre con ValueError pero /api/backup/download no lo captura y responde 500",
        )),
    ])
    def test_descarga_de_nombres_no_validos_no_entrega_archivos(self, admin, nombre):
        response = admin.get(f"/api/backup/download/{nombre}")
        assert response.status_code in (400, 404)
        assert b"import" not in response.data

    @pytest.mark.xfail(strict=True, reason="BUG-AUTHZ-03: GET /api/backup/download solo exige sesion; un cliente puede descargar respaldos")
    def test_cliente_no_puede_descargar_respaldos(self, cliente_a):
        assert cliente_a.get("/api/backup/download/no_existe.sql").status_code == 403

    @pytest.mark.xfail(strict=True, reason="BUG-AUTHZ-03: DELETE /api/backup/delete solo exige sesion; un cliente puede borrar respaldos")
    def test_cliente_no_puede_borrar_respaldos(self, cliente_a):
        assert cliente_a.delete("/api/backup/delete/no_existe.sql").status_code == 403
