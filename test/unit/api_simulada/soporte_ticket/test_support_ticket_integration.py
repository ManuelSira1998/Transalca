import pytest


def login_as_client(client, cedula="V-87654321", user_id=4):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["user_cedula"] = cedula
        sess["user_tipo"] = "cliente"
        sess["roles"] = ["Cliente"]
        sess["permisos"] = {}


def login_as_employee(client, cedula="V-10000000", user_id=1, user_tipo="admin"):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["user_cedula"] = cedula
        sess["user_tipo"] = user_tipo
        sess["roles"] = ["Administrador"]
        sess["permisos"] = {
            "tickets": {"crear": 1, "leer": 1, "actualizar": 1, "eliminar": 1},
            "notificaciones": {"crear": 1, "leer": 1, "actualizar": 1, "eliminar": 1},
        }


class TestSupportTicketIntegration:

    def test_unauthenticated_ticket_and_notification_rejection(self, client):
        assert client.get("/api/tickets/").status_code == 401
        assert client.post("/api/tickets/", json={"asunto": "Falla"}).status_code == 401
        assert client.get("/api/notifications/").status_code == 401
        assert client.get("/api/notifications/unread").status_code == 401

    def test_client_creates_support_ticket_with_vehicle_reference(self, client):
        login_as_client(client, cedula="V-87654321", user_id=4)
        ticket_data = {
            "asunto": "Ruido inusual en frenos delanteros",
            "descripcion": "Luego del mantenimiento preventivo, se escucha un chirrido al frenar.",
            "prioridad": "alta",
            "referencia_tipo": "vehiculo",
            "vehiculo_placa": "ABC123D"
        }
        res = client.post("/api/tickets/", json=ticket_data)
        assert res.status_code == 201
        payload = res.get_json()
        assert payload["status"] == "success"
        ticket_id = payload["id"]
        assert ticket_id is not None

        res_get = client.get(f"/api/tickets/{ticket_id}")
        assert res_get.status_code == 200
        t = res_get.get_json()["data"]
        assert t["id"] == ticket_id
        assert t["asunto"] == "Ruido inusual en frenos delanteros"
        assert t["prioridad"] == "alta"
        assert t["estado"] == "abierto"
        assert t["cliente_cedula"] == "V-87654321"
        assert t["vehiculo_placa"] == "ABC123D"

    def test_client_can_only_view_own_tickets(self, client):
        login_as_client(client, cedula="V-87654321", user_id=4)
        client.post("/api/tickets/", json={
            "asunto": "Ticket propio",
            "descripcion": "Descripción propia",
            "prioridad": "media"
        })

        login_as_employee(client)
        client.post("/api/tickets/", json={
            "cliente_cedula": "V-99999999",
            "asunto": "Ticket de otro cliente",
            "descripcion": "Caso Maria Gonzalez",
            "prioridad": "baja"
        })

        login_as_client(client, cedula="V-87654321", user_id=4)
        res_cli = client.get("/api/tickets/")
        assert res_cli.status_code == 200
        tickets = res_cli.get_json()["data"]
        assert len(tickets) >= 1
        assert all(t["cliente_cedula"] == "V-87654321" for t in tickets)
        assert not any(t["asunto"] == "Ticket de otro cliente" for t in tickets)

    def test_employee_views_all_tickets_and_filters(self, client):
        login_as_client(client, cedula="V-87654321", user_id=4)
        client.post("/api/tickets/", json={
            "asunto": "Emergencia mecanica",
            "descripcion": "Bote de aceite en sucursal",
            "prioridad": "alta"
        })

        login_as_employee(client)
        res_all = client.get("/api/tickets/")
        assert res_all.status_code == 200
        all_tickets = res_all.get_json()["data"]
        assert len(all_tickets) >= 1

        res_prio = client.get("/api/tickets/?prioridad=alta")
        assert res_prio.status_code == 200
        prio_tickets = res_prio.get_json()["data"]
        assert all(t["prioridad"] == "alta" for t in prio_tickets)

        res_stats = client.get("/api/tickets/stats")
        assert res_stats.status_code == 200
        assert isinstance(res_stats.get_json()["data"], list)

    def test_ticket_conversation_flow_replies(self, client):
        login_as_client(client, cedula="V-87654321", user_id=4)
        res_create = client.post("/api/tickets/", json={
            "asunto": "Consulta de repuesto",
            "descripcion": "¿Tienen disponibilidad de pastillas de freno para Corolla?",
            "prioridad": "media"
        })
        assert res_create.status_code == 201
        tid = res_create.get_json()["id"]

        login_as_employee(client)
        res_rep_admin = client.post(f"/api/tickets/{tid}/reply", json={
            "mensaje": "Hola, sí disponemos de pastillas en la Sede Central. El costo es de $25."
        })
        assert res_rep_admin.status_code == 201
        assert res_rep_admin.get_json()["status"] == "success"

        login_as_client(client, cedula="V-87654321", user_id=4)
        res_check_cli = client.get(f"/api/tickets/{tid}")
        assert res_check_cli.status_code == 200
        respuestas = res_check_cli.get_json()["data"]["respuestas"]
        assert len(respuestas) == 1
        assert respuestas[0]["autor_tipo"] == "admin"
        assert "sí disponemos de pastillas" in respuestas[0]["mensaje"]

        res_rep_cli = client.post(f"/api/tickets/{tid}/reply", json={
            "mensaje": "Excelente, pasaré hoy en la tarde a instalarlas. Gracias."
        })
        assert res_rep_cli.status_code == 201

        login_as_employee(client)
        res_full = client.get(f"/api/tickets/{tid}")
        assert res_full.status_code == 200
        hilo = res_full.get_json()["data"]["respuestas"]
        assert len(hilo) == 2
        assert hilo[0]["autor_tipo"] == "admin"
        assert hilo[1]["autor_tipo"] == "cliente"

    def test_status_update_triggers_customer_notification(self, client):
        login_as_client(client, cedula="V-87654321", user_id=4)
        res_create = client.post("/api/tickets/", json={
            "asunto": "Revisión de garantía",
            "descripcion": "Verificación de amortiguadores.",
            "prioridad": "alta"
        })
        assert res_create.status_code == 201
        tid = res_create.get_json()["id"]

        login_as_employee(client)
        res_status = client.put(f"/api/tickets/{tid}/status", json={
            "estado": "en_revision"
        })
        assert res_status.status_code == 200
        assert res_status.get_json()["status"] == "success"

        res_ticket = client.get(f"/api/tickets/{tid}")
        assert res_ticket.get_json()["data"]["estado"] == "en_revision"

        login_as_client(client, cedula="V-87654321", user_id=4)
        res_notif = client.get("/api/notifications/unread")
        assert res_notif.status_code == 200
        notifs = res_notif.get_json()["data"]
        assert len(notifs) >= 1
        assert any("en_revision" in n["mensaje"] and "Revisión de garantía" in n["mensaje"] for n in notifs)

    def test_notification_read_and_delete_lifecycle(self, client):
        login_as_client(client, cedula="V-87654321", user_id=4)
        res_create = client.post("/api/tickets/", json={
            "asunto": "Servicio rápido",
            "descripcion": "Cambio de bombillo.",
            "prioridad": "baja"
        })
        assert res_create.status_code == 201
        tid = res_create.get_json()["id"]

        login_as_employee(client)
        client.put(f"/api/tickets/{tid}/status", json={"estado": "resuelto"})

        login_as_client(client, cedula="V-87654321", user_id=4)
        res_unread = client.get("/api/notifications/unread")
        assert res_unread.status_code == 200
        notifs = res_unread.get_json()["data"]
        assert len(notifs) >= 1
        target_notif = notifs[0]
        nid = target_notif["id"]

        res_read = client.put(f"/api/notifications/{nid}/read")
        assert res_read.status_code == 200

        res_del = client.delete(f"/api/notifications/{nid}")
        assert res_del.status_code == 200
        assert res_del.get_json()["status"] == "success"

    def test_cross_client_security_isolation(self, client):
        login_as_client(client, cedula="V-87654321", user_id=4)
        res_create = client.post("/api/tickets/", json={
            "asunto": "Ticket Privado Cliente 1",
            "descripcion": "Datos confidenciales",
            "prioridad": "media"
        })
        assert res_create.status_code == 201
        tid = res_create.get_json()["id"]

        login_as_client(client, cedula="V-99999999", user_id=99)
        res_unauthorized_get = client.get(f"/api/tickets/{tid}")
        assert res_unauthorized_get.status_code == 403

        res_unauthorized_reply = client.post(f"/api/tickets/{tid}/reply", json={
            "mensaje": "Intrusión no autorizada"
        })
        assert res_unauthorized_reply.status_code == 403

    def test_ticket_validation_errors(self, client):
        login_as_client(client, cedula="V-87654321", user_id=4)

        res_no_subject = client.post("/api/tickets/", json={
            "descripcion": "Falta asunto",
            "prioridad": "media"
        })
        assert res_no_subject.status_code == 400

        res_invalid_prio = client.post("/api/tickets/", json={
            "asunto": "Prioridad loca",
            "prioridad": "urgente_invalida"
        })
        assert res_invalid_prio.status_code == 400

        res_create = client.post("/api/tickets/", json={
            "asunto": "Para prueba de mensaje vacío",
            "prioridad": "baja"
        })
        assert res_create.status_code == 201
        tid = res_create.get_json()["id"]

        res_empty_reply = client.post(f"/api/tickets/{tid}/reply", json={
            "mensaje": ""
        })
        assert res_empty_reply.status_code == 400

        login_as_employee(client)
        res_invalid_status = client.put(f"/api/tickets/{tid}/status", json={
            "estado": "estado_fantasma"
        })
        assert res_invalid_status.status_code == 400

    def test_mark_all_notifications_as_read_flow(self, client):
        login_as_client(client, cedula="V-87654321", user_id=4)
        t1 = client.post("/api/tickets/", json={"asunto": "Ticket Uno", "prioridad": "baja"}).get_json()["id"]
        t2 = client.post("/api/tickets/", json={"asunto": "Ticket Dos", "prioridad": "media"}).get_json()["id"]

        login_as_employee(client)
        client.put(f"/api/tickets/{t1}/status", json={"estado": "en_revision"})
        client.put(f"/api/tickets/{t2}/status", json={"estado": "resuelto"})

        login_as_client(client, cedula="V-87654321", user_id=4)
        res_count = client.get("/api/notifications/count")
        assert res_count.status_code == 200
        assert res_count.get_json()["count"] >= 2

        res_read_all = client.put("/api/notifications/read-all")
        assert res_read_all.status_code == 200
        assert res_read_all.get_json()["status"] == "success"

        res_count_after = client.get("/api/notifications/count")
        assert res_count_after.get_json()["count"] == 0

        res_all_notifs = client.get("/api/notifications/")
        assert res_all_notifs.status_code == 200
        historial = res_all_notifs.get_json()["data"]
        assert len(historial) >= 2

