import pytest


def _crear_ticket(cliente, **overrides):
    data = {"asunto": "Consulta de prueba", "descripcion": "Detalle del problema", "prioridad": "media"}
    data.update(overrides)
    return cliente.post("/api/tickets/", json=data)


def _ticket_id(response):
    assert response.status_code == 201, response.get_json()
    return response.get_json()["id"]


class TestTickets:

    def test_cliente_crea_ticket_asociado_a_su_cedula(self, cliente_a, db):
        tid = _ticket_id(_crear_ticket(cliente_a))
        with db["transalca"].cursor() as cursor:
            cursor.execute("SELECT cliente_cedula, prioridad_ticket FROM tickets_soporte WHERE id_ticket_soporte = %s", (tid,))
            assert cursor.fetchone() == {"cliente_cedula": cliente_a.info["cedula"], "prioridad_ticket": "media"}

    def test_cliente_no_puede_crear_ticket_a_nombre_de_otro(self, cliente_a, cliente_b, db):
        tid = _ticket_id(_crear_ticket(cliente_a, cliente_cedula=cliente_b.info["cedula"]))
        with db["transalca"].cursor() as cursor:
            cursor.execute("SELECT cliente_cedula FROM tickets_soporte WHERE id_ticket_soporte = %s", (tid,))
            assert cursor.fetchone()["cliente_cedula"] == cliente_a.info["cedula"]

    @pytest.mark.parametrize("payload, esperado", [
        ({"asunto": ""}, 400),
        ({"asunto": None}, 400),
        ({"asunto": "Valido", "prioridad": "urgentisima"}, 400),
    ])
    def test_datos_invalidos_devuelven_400(self, cliente_a, payload, esperado):
        assert cliente_a.post("/api/tickets/", json=payload).status_code == esperado

    def test_cliente_no_puede_ver_ni_responder_ticket_ajeno(self, cliente_a, cliente_b):
        tid = _ticket_id(_crear_ticket(cliente_a))
        assert cliente_b.get(f"/api/tickets/{tid}").status_code == 403
        assert cliente_b.post(f"/api/tickets/{tid}/reply", json={"mensaje": "hola"}).status_code == 403

    def test_listado_del_cliente_solo_incluye_sus_tickets(self, cliente_a, cliente_b):
        tid = _ticket_id(_crear_ticket(cliente_a))
        ids_b = [t["id"] for t in cliente_b.get("/api/tickets/").get_json()["data"]]
        assert tid not in ids_b
        ids_a = [t["id"] for t in cliente_a.get("/api/tickets/").get_json()["data"]]
        assert tid in ids_a

    def test_cliente_no_puede_cambiar_el_estado(self, cliente_a):
        tid = _ticket_id(_crear_ticket(cliente_a))
        assert cliente_a.put(f"/api/tickets/{tid}/status", json={"estado": "cerrado"}).status_code == 403

    def test_empleado_cambia_el_estado_y_se_persiste(self, cliente_a, admin, db):
        tid = _ticket_id(_crear_ticket(cliente_a))
        assert admin.put(f"/api/tickets/{tid}/status", json={"estado": "resuelto"}).status_code == 200
        with db["transalca"].cursor() as cursor:
            cursor.execute("SELECT estado FROM tickets_soporte WHERE id_ticket_soporte = %s", (tid,))
            assert cursor.fetchone()["estado"] == "resuelto"

    def test_estado_invalido_devuelve_400(self, cliente_a, admin):
        tid = _ticket_id(_crear_ticket(cliente_a))
        assert admin.put(f"/api/tickets/{tid}/status", json={"estado": "inventado"}).status_code == 400
