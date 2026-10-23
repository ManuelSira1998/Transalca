import pytest


@pytest.fixture
def notificacion(db, cliente_a):
    with db["transalca"].cursor() as cursor:
        cursor.execute(
            "INSERT INTO notificaciones (cliente_cedula, tipo_notificacion, titulo_notificacion, mensaje_notificacion) "
            "VALUES (%s, 'sistema', 'Aviso de prueba', 'Mensaje de prueba')",
            (cliente_a.info["cedula"],),
        )
        return cursor.lastrowid


def _fila(db, nid):
    with db["transalca"].cursor() as cursor:
        cursor.execute("SELECT leida FROM notificaciones WHERE id_notificacion = %s", (nid,))
        return cursor.fetchone()


class TestNotificaciones:

    def test_el_cliente_ve_su_notificacion_sin_leer(self, cliente_a, notificacion):
        ids = [n["id"] for n in cliente_a.get("/api/notifications/").get_json()["data"]]
        assert notificacion in ids
        assert notificacion in [n["id"] for n in cliente_a.get("/api/notifications/unread").get_json()["data"]]
        assert cliente_a.get("/api/notifications/count").get_json()["count"] >= 1

    def test_marcar_como_leida(self, cliente_a, db, notificacion):
        assert cliente_a.put(f"/api/notifications/{notificacion}/read").status_code == 200
        assert _fila(db, notificacion)["leida"] == 1

    def test_marcar_todas_como_leidas(self, cliente_a, db, notificacion):
        assert cliente_a.put("/api/notifications/read-all").status_code == 200
        assert _fila(db, notificacion)["leida"] == 1
        assert cliente_a.get("/api/notifications/count").get_json()["count"] == 0

    def test_eliminar_la_propia(self, cliente_a, db, notificacion):
        assert cliente_a.delete(f"/api/notifications/{notificacion}").status_code == 200
        assert _fila(db, notificacion) is None

    def test_otro_cliente_no_la_ve(self, cliente_b, notificacion):
        ids = [n["id"] for n in cliente_b.get("/api/notifications/").get_json()["data"]]
        assert notificacion not in ids

    def test_otro_cliente_no_puede_marcarla_ni_borrarla(self, cliente_b, db, notificacion):
        cliente_b.put(f"/api/notifications/{notificacion}/read")
        cliente_b.put("/api/notifications/read-all")
        cliente_b.delete(f"/api/notifications/{notificacion}")
        assert _fila(db, notificacion) == {"leida": 0}

    def test_sin_sesion_devuelve_401(self, anon):
        assert anon.get("/api/notifications/").status_code == 401
