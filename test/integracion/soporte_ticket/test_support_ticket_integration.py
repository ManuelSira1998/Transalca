"""
Pruebas de integración para el Clúster de Atención al Cliente y Notificaciones:
Tickets de Soporte <-> Respuestas <-> Clientes <-> Vehículos <-> Notificaciones en tiempo real.

Verifica:
1. Rechazo de accesos no autenticados en tickets y notificaciones (401).
2. Creación de tickets por parte del cliente vinculados a sus vehículos.
3. Aislamiento de privacidad: clientes solo ven sus propios tickets.
4. Consulta global y filtrado por estado y prioridad para empleados.
5. Hilo de conversación bidireccional (respuestas empleado <-> cliente).
6. Actualización de estado del ticket con despacho automático de notificación al usuario.
7. Ciclo de vida de notificaciones (no leída -> lectura individual -> eliminación).
8. Seguridad cross-client: denegación 403 al intentar acceder o responder a tickets de otro cliente.
9. Validaciones de negocio (campos obligatorios, estados y prioridades permitidas).
10. Estadísticas de soporte agrupadas por estado para empleados.
"""

import pytest


def login_as_client(client, cedula="V-87654321", user_id=4):
    """Establece la sesión del cliente en la cookie del test client."""
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["user_cedula"] = cedula
        sess["user_tipo"] = "cliente"
        sess["roles"] = ["Cliente"]
        sess["permisos"] = {}


def login_as_employee(client, cedula="V-10000000", user_id=1, user_tipo="admin"):
    """Establece la sesión de empleado/administrador en la cookie del test client."""
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
    """Suite de integración para el flujo Tickets de Soporte -> Respuestas -> Notificaciones."""

    def test_unauthenticated_ticket_and_notification_rejection(self, client):
        """Verifica que usuarios sin sesión activa no puedan acceder a tickets ni notificaciones."""
        assert client.get("/api/tickets/").status_code == 401
        assert client.post("/api/tickets/", json={"asunto": "Falla"}).status_code == 401
        assert client.get("/api/notifications/").status_code == 401
        assert client.get("/api/notifications/unread").status_code == 401

    def test_client_creates_support_ticket_with_vehicle_reference(self, client):
        """Un cliente autenticado registra un ticket de soporte asociado a su vehículo."""
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

        # Consultar el ticket creado
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
        """Verifica que al listar tickets, el cliente solo recibe los que le pertenecen."""
        # 1. Crear ticket como cliente V-87654321
        login_as_client(client, cedula="V-87654321", user_id=4)
        client.post("/api/tickets/", json={
            "asunto": "Ticket propio",
            "descripcion": "Descripción propia",
            "prioridad": "media"
        })

        # 2. Empleado crea ticket para otro cliente (V-99999999)
        login_as_employee(client)
        client.post("/api/tickets/", json={
            "cliente_cedula": "V-99999999",
            "asunto": "Ticket de otro cliente",
            "descripcion": "Caso Maria Gonzalez",
            "prioridad": "baja"
        })

        # 3. Consulta volviendo a iniciar como cliente
        login_as_client(client, cedula="V-87654321", user_id=4)
        res_cli = client.get("/api/tickets/")
        assert res_cli.status_code == 200
        tickets = res_cli.get_json()["data"]
        assert len(tickets) >= 1
        assert all(t["cliente_cedula"] == "V-87654321" for t in tickets)
        assert not any(t["asunto"] == "Ticket de otro cliente" for t in tickets)

    def test_employee_views_all_tickets_and_filters(self, client):
        """Un empleado con permisos puede ver todos los tickets y aplicar filtros de estado y prioridad."""
        # Cliente crea ticket con prioridad alta
        login_as_client(client, cedula="V-87654321", user_id=4)
        client.post("/api/tickets/", json={
            "asunto": "Emergencia mecanica",
            "descripcion": "Bote de aceite en sucursal",
            "prioridad": "alta"
        })

        # Empleado lista todos los tickets
        login_as_employee(client)
        res_all = client.get("/api/tickets/")
        assert res_all.status_code == 200
        all_tickets = res_all.get_json()["data"]
        assert len(all_tickets) >= 1

        # Filtrar por prioridad
        res_prio = client.get("/api/tickets/?prioridad=alta")
        assert res_prio.status_code == 200
        prio_tickets = res_prio.get_json()["data"]
        assert all(t["prioridad"] == "alta" for t in prio_tickets)

        # Consultar estadísticas
        res_stats = client.get("/api/tickets/stats")
        assert res_stats.status_code == 200
        assert isinstance(res_stats.get_json()["data"], list)

    def test_ticket_conversation_flow_replies(self, client):
        """Flujo completo de conversación: Empleado responde -> Cliente recibe y responde."""
        # 1. Cliente crea ticket
        login_as_client(client, cedula="V-87654321", user_id=4)
        res_create = client.post("/api/tickets/", json={
            "asunto": "Consulta de repuesto",
            "descripcion": "¿Tienen disponibilidad de pastillas de freno para Corolla?",
            "prioridad": "media"
        })
        assert res_create.status_code == 201
        tid = res_create.get_json()["id"]

        # 2. Empleado responde al ticket
        login_as_employee(client)
        res_rep_admin = client.post(f"/api/tickets/{tid}/reply", json={
            "mensaje": "Hola, sí disponemos de pastillas en la Sede Central. El costo es de $25."
        })
        assert res_rep_admin.status_code == 201
        assert res_rep_admin.get_json()["status"] == "success"

        # 3. Cliente revisa el ticket y ve la respuesta
        login_as_client(client, cedula="V-87654321", user_id=4)
        res_check_cli = client.get(f"/api/tickets/{tid}")
        assert res_check_cli.status_code == 200
        respuestas = res_check_cli.get_json()["data"]["respuestas"]
        assert len(respuestas) == 1
        assert respuestas[0]["autor_tipo"] == "admin"
        assert "sí disponemos de pastillas" in respuestas[0]["mensaje"]

        # 4. Cliente responde de vuelta
        res_rep_cli = client.post(f"/api/tickets/{tid}/reply", json={
            "mensaje": "Excelente, pasaré hoy en la tarde a instalarlas. Gracias."
        })
        assert res_rep_cli.status_code == 201

        # 5. Se verifica el hilo completo con ambas respuestas desde el admin
        login_as_employee(client)
        res_full = client.get(f"/api/tickets/{tid}")
        assert res_full.status_code == 200
        hilo = res_full.get_json()["data"]["respuestas"]
        assert len(hilo) == 2
        assert hilo[0]["autor_tipo"] == "admin"
        assert hilo[1]["autor_tipo"] == "cliente"

    def test_status_update_triggers_customer_notification(self, client):
        """
        Prueba intermodular: Al cambiar el estado de un ticket por parte del personal,
        se genera automáticamente una notificación para el cliente dueño del ticket.
        """
        # 1. Cliente crea ticket
        login_as_client(client, cedula="V-87654321", user_id=4)
        res_create = client.post("/api/tickets/", json={
            "asunto": "Revisión de garantía",
            "descripcion": "Verificación de amortiguadores.",
            "prioridad": "alta"
        })
        assert res_create.status_code == 201
        tid = res_create.get_json()["id"]

        # 2. Empleado actualiza estado a 'en_revision'
        login_as_employee(client)
        res_status = client.put(f"/api/tickets/{tid}/status", json={
            "estado": "en_revision"
        })
        assert res_status.status_code == 200
        assert res_status.get_json()["status"] == "success"

        # 3. Comprobar que el ticket ahora está en_revision
        res_ticket = client.get(f"/api/tickets/{tid}")
        assert res_ticket.get_json()["data"]["estado"] == "en_revision"

        # 4. Cliente consulta sus notificaciones no leídas
        login_as_client(client, cedula="V-87654321", user_id=4)
        res_notif = client.get("/api/notifications/unread")
        assert res_notif.status_code == 200
        notifs = res_notif.get_json()["data"]
        assert len(notifs) >= 1
        assert any("en_revision" in n["mensaje"] and "Revisión de garantía" in n["mensaje"] for n in notifs)

    def test_notification_read_and_delete_lifecycle(self, client):
        """Verifica la lectura individual y eliminación de notificaciones por parte del usuario."""
        # 1. Cliente crea ticket
        login_as_client(client, cedula="V-87654321", user_id=4)
        res_create = client.post("/api/tickets/", json={
            "asunto": "Servicio rápido",
            "descripcion": "Cambio de bombillo.",
            "prioridad": "baja"
        })
        assert res_create.status_code == 201
        tid = res_create.get_json()["id"]

        # 2. Empleado actualiza estado para generar notificación
        login_as_employee(client)
        client.put(f"/api/tickets/{tid}/status", json={"estado": "resuelto"})

        # 3. Cliente obtiene la notificación generada
        login_as_client(client, cedula="V-87654321", user_id=4)
        res_unread = client.get("/api/notifications/unread")
        assert res_unread.status_code == 200
        notifs = res_unread.get_json()["data"]
        assert len(notifs) >= 1
        target_notif = notifs[0]
        nid = target_notif["id"]

        # 4. Marcar como leída
        res_read = client.put(f"/api/notifications/{nid}/read")
        assert res_read.status_code == 200

        # 5. Eliminar la notificación
        res_del = client.delete(f"/api/notifications/{nid}")
        assert res_del.status_code == 200
        assert res_del.get_json()["status"] == "success"

    def test_cross_client_security_isolation(self, client):
        """Verifica que un cliente no pueda ver ni responder a tickets pertenecientes a otro cliente (403 Forbidden)."""
        # 1. Cliente 1 (V-87654321) crea su ticket privado
        login_as_client(client, cedula="V-87654321", user_id=4)
        res_create = client.post("/api/tickets/", json={
            "asunto": "Ticket Privado Cliente 1",
            "descripcion": "Datos confidenciales",
            "prioridad": "media"
        })
        assert res_create.status_code == 201
        tid = res_create.get_json()["id"]

        # 2. Cliente 2 (V-99999999) intenta consultar el ticket del Cliente 1
        login_as_client(client, cedula="V-99999999", user_id=99)
        res_unauthorized_get = client.get(f"/api/tickets/{tid}")
        assert res_unauthorized_get.status_code == 403

        # 3. Cliente 2 intenta responder al ticket del Cliente 1
        res_unauthorized_reply = client.post(f"/api/tickets/{tid}/reply", json={
            "mensaje": "Intrusión no autorizada"
        })
        assert res_unauthorized_reply.status_code == 403

    def test_ticket_validation_errors(self, client):
        """Verifica el rechazo ante datos inválidos o incompletos al operar tickets."""
        login_as_client(client, cedula="V-87654321", user_id=4)

        # 1. Asunto faltante
        res_no_subject = client.post("/api/tickets/", json={
            "descripcion": "Falta asunto",
            "prioridad": "media"
        })
        assert res_no_subject.status_code == 400

        # 2. Prioridad no permitida
        res_invalid_prio = client.post("/api/tickets/", json={
            "asunto": "Prioridad loca",
            "prioridad": "urgente_invalida"
        })
        assert res_invalid_prio.status_code == 400

        # 3. Mensaje vacío en respuesta
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

        # 4. Estado no permitido al actualizar (desde cuenta empleado)
        login_as_employee(client)
        res_invalid_status = client.put(f"/api/tickets/{tid}/status", json={
            "estado": "estado_fantasma"
        })
        assert res_invalid_status.status_code == 400

    def test_mark_all_notifications_as_read_flow(self, client):
        """Verifica la marcación masiva de notificaciones como leídas y persistencia en historial."""
        # 1. Cliente genera múltiples tickets y el admin los actualiza
        login_as_client(client, cedula="V-87654321", user_id=4)
        t1 = client.post("/api/tickets/", json={"asunto": "Ticket Uno", "prioridad": "baja"}).get_json()["id"]
        t2 = client.post("/api/tickets/", json={"asunto": "Ticket Dos", "prioridad": "media"}).get_json()["id"]

        login_as_employee(client)
        client.put(f"/api/tickets/{t1}/status", json={"estado": "en_revision"})
        client.put(f"/api/tickets/{t2}/status", json={"estado": "resuelto"})

        # 2. Cliente verifica conteo de no leídas >= 2
        login_as_client(client, cedula="V-87654321", user_id=4)
        res_count = client.get("/api/notifications/count")
        assert res_count.status_code == 200
        assert res_count.get_json()["count"] >= 2

        # 3. Marcar todas como leídas
        res_read_all = client.put("/api/notifications/read-all")
        assert res_read_all.status_code == 200
        assert res_read_all.get_json()["status"] == "success"

        # 4. Conteo de no leídas debe ser 0
        res_count_after = client.get("/api/notifications/count")
        assert res_count_after.get_json()["count"] == 0

        # 5. La lista completa de notificaciones conserva el historial
        res_all_notifs = client.get("/api/notifications/")
        assert res_all_notifs.status_code == 200
        historial = res_all_notifs.get_json()["data"]
        assert len(historial) >= 2

