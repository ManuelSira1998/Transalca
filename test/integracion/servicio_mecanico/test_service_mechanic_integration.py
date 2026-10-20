import pytest


class TestServiceMechanicIntegration:
    """Pruebas de integración para el módulo de Servicio Mecánico.

    Valida la orquestación entre servicios, mecánicos, clientes, vehículos
    y comisiones, incluyendo reglas de negocio, ciclo de vida de asignaciones
    y detección de conflictos por mecánicos ocupados.
    """

    def test_unauthorized_access_rejected(self, client):
        """Verifica que todas las operaciones de modificación requieran usuario autenticado."""
        # Creación sin sesión
        res_create = client.post("/api/service-mechanics/", json={"servicio_id": 1})
        assert res_create.status_code == 401

        # Reasignación de mecánico sin sesión
        res_mech = client.put("/api/service-mechanics/1/mechanic", json={"mecanico_cedula": "V-12345678"})
        assert res_mech.status_code == 401

        # Cambio de estado sin sesión
        res_st = client.put("/api/service-mechanics/1/status", json={"estado": "en_proceso"})
        assert res_st.status_code == 401

        # Modificación general sin sesión
        res_put = client.put("/api/service-mechanics/1", json={"servicio_id": 1})
        assert res_put.status_code == 401

        # Eliminación sin sesión
        res_del = client.delete("/api/service-mechanics/1")
        assert res_del.status_code == 401

    def test_get_all_assignments_integration(self, auth_client):
        """Verifica que el listado de servicios mecánicos retorne datos consolidados

        con nombres de servicios, mecánicos, clientes y vehículos.
        """
        response = auth_client.get("/api/service-mechanics/")
        assert response.status_code == 200
        data = response.get_json()

        assert data["status"] == "success"
        items = data["data"]
        assert isinstance(items, list)
        assert len(items) >= 1

        first = items[0]
        assert first["id"] == 1
        assert first["servicio_nombre"] == "Alineación Computarizada"
        assert "Carlos Pérez" in first["mecanico_nombre"]
        assert first["cliente_cedula"] == "V-87654321"
        assert first["vehiculo_placa"] == "ABC123D"
        assert first["estado"] == "en_proceso"

    def test_get_one_assignment_found(self, auth_client):
        """Verifica la consulta individual de una asignación con detalle completo."""
        response = auth_client.get("/api/service-mechanics/1")
        assert response.status_code == 200
        data = response.get_json()

        assert data["status"] == "success"
        item = data["data"]
        assert item["id"] == 1
        assert item["servicio_nombre"] == "Alineación Computarizada"
        assert item["cliente_nombre"] == "Juan"
        assert item["vehiculo_marca"] == "Toyota"
        assert item["mecanico_cedula"] == "V-12345678"

    def test_get_one_assignment_not_found(self, auth_client):
        """Verifica que consultar una asignación inexistente retorne 404."""
        response = auth_client.get("/api/service-mechanics/99999")
        assert response.status_code == 404
        data = response.get_json()
        assert data["status"] == "error"
        assert "no encontrada" in data["message"].lower()

    def test_create_assignment_full_integration(self, auth_client, mock_db):
        """Prueba la creación exitosa de un servicio mecánico con asignación inicial

        de mecánico y porcentaje de comisión.
        """
        payload = {
            "servicio_id": 2,
            "mecanico_cedula": "V-87654321",
            "cliente_cedula": "V-87654321",
            "vehiculo_placa": "ABC123D",
            "observaciones": "Balanceo preventivo",
            "porcentaje_comision": 18.0
        }
        response = auth_client.post("/api/service-mechanics/", json=payload)
        assert response.status_code == 200
        data = response.get_json()

        assert data["status"] == "success"
        aid = data["id"]
        assert aid is not None

        # Verificar persistencia en base de datos en memoria
        get_res = auth_client.get(f"/api/service-mechanics/{aid}")
        assert get_res.status_code == 200
        saved = get_res.get_json()["data"]
        assert saved["servicio_id"] == 2
        assert saved["mecanico_cedula"] == "V-87654321"
        assert saved["estado"] == "asignado"
        assert saved["observaciones"] == "Balanceo preventivo"

        # Verificar que la comisión se registró correctamente
        assert aid in mock_db.comisiones_mecanico
        assert mock_db.comisiones_mecanico[aid]["porcentaje_comision"] == 18.0

    def test_create_assignment_without_mechanic_defaults_to_sin_asignar(self, auth_client):
        """Verifica que si no se asigna mecánico, el estado por defecto sea 'sin_asignar'."""
        payload = {
            "servicio_id": 2,
            "mecanico_cedula": "",
            "cliente_cedula": "V-87654321",
            "vehiculo_placa": "ABC123D",
            "observaciones": "Esperando mecánico disponible"
        }
        response = auth_client.post("/api/service-mechanics/", json=payload)
        assert response.status_code == 200
        aid = response.get_json()["id"]

        get_res = auth_client.get(f"/api/service-mechanics/{aid}")
        saved = get_res.get_json()["data"]
        assert saved["mecanico_cedula"] is None
        assert saved["estado"] == "sin_asignar"

    def test_cross_module_validations_rejected(self, auth_client):
        """Verifica que relaciones con entidades inactivas o inexistentes sean rechazadas con 400."""
        # 1. Servicio inexistente
        res_serv = auth_client.post("/api/service-mechanics/", json={
            "servicio_id": 9999,
            "cliente_cedula": "V-87654321",
            "vehiculo_placa": "ABC123D"
        })
        assert res_serv.status_code == 400

        # 2. Servicio inactivo (ID 3 tiene estado = 0)
        res_serv_inact = auth_client.post("/api/service-mechanics/", json={
            "servicio_id": 3,
            "cliente_cedula": "V-87654321",
            "vehiculo_placa": "ABC123D"
        })
        assert res_serv_inact.status_code == 400

        # 3. Mecánico inactivo (V-11111111 tiene estado = 0)
        res_mech_inact = auth_client.post("/api/service-mechanics/", json={
            "servicio_id": 1,
            "mecanico_cedula": "V-11111111",
            "cliente_cedula": "V-87654321",
            "vehiculo_placa": "ABC123D"
        })
        assert res_mech_inact.status_code == 400

        # 4. Cliente inexistente
        res_cli = auth_client.post("/api/service-mechanics/", json={
            "servicio_id": 1,
            "cliente_cedula": "V-00000000",
            "vehiculo_placa": "ABC123D"
        })
        assert res_cli.status_code == 400

        # 5. Vehículo inexistente
        res_veh = auth_client.post("/api/service-mechanics/", json={
            "servicio_id": 1,
            "cliente_cedula": "V-87654321",
            "vehiculo_placa": "PLACA999"
        })
        assert res_veh.status_code == 400

    def test_mechanic_busy_conflict_detection_and_confirmation(self, auth_client, mock_db):
        """Prueba la lógica de detección de mecánico ocupado:

        Si el mecánico ya está asignado a otro servicio activo, la API solicita confirmación
        (status 'confirm') a menos que se envíe 'confirmar: true'.
        """
        # Crear una segunda asignación sin asignar
        post_res = auth_client.post("/api/service-mechanics/", json={
            "servicio_id": 2,
            "mecanico_cedula": "",
            "cliente_cedula": "V-87654321",
            "vehiculo_placa": "ABC123D"
        })
        aid2 = post_res.get_json()["id"]

        # Intentar asignar al mecánico 'V-12345678' (que ya está ocupado en la asignación #1)
        res_conflict = auth_client.put(f"/api/service-mechanics/{aid2}/mechanic", json={
            "mecanico_cedula": "V-12345678",
            "porcentaje_comision": 20.0
        })
        assert res_conflict.status_code == 200
        data_conflict = res_conflict.get_json()
        assert data_conflict["status"] == "confirm"
        assert "ya se encuentra asignado" in data_conflict["message"]

        # Reintentar enviando la confirmación explícita
        res_confirmed = auth_client.put(f"/api/service-mechanics/{aid2}/mechanic", json={
            "mecanico_cedula": "V-12345678",
            "porcentaje_comision": 20.0,
            "confirmar": True
        })
        assert res_confirmed.status_code == 200
        assert res_confirmed.get_json()["status"] == "success"

        # Verificar que quedó efectivamente asignado
        check_res = auth_client.get(f"/api/service-mechanics/{aid2}")
        assert check_res.get_json()["data"]["mecanico_cedula"] == "V-12345678"

    def test_update_status_business_rules(self, auth_client):
        """Verifica que no se pueda avanzar a 'en_proceso' o 'completado' sin mecánico asignado."""
        # Crear asignación sin mecánico
        create_res = auth_client.post("/api/service-mechanics/", json={
            "servicio_id": 2,
            "mecanico_cedula": "",
            "cliente_cedula": "V-87654321",
            "vehiculo_placa": "ABC123D"
        })
        aid = create_res.get_json()["id"]

        # Intentar pasar a 'en_proceso' sin mecánico debe fallar con 400
        res_fail = auth_client.put(f"/api/service-mechanics/{aid}/status", json={"estado": "en_proceso"})
        assert res_fail.status_code == 400
        assert res_fail.get_json()["status"] == "error"

        # Asignar mecánico
        auth_client.put(f"/api/service-mechanics/{aid}/mechanic", json={
            "mecanico_cedula": "V-87654321",
            "porcentaje_comision": 15.0
        })

        # Ahora pasar a 'en_proceso' debe tener éxito
        res_ok = auth_client.put(f"/api/service-mechanics/{aid}/status", json={"estado": "en_proceso"})
        assert res_ok.status_code == 200
        assert res_ok.get_json()["status"] == "success"

    def test_complete_service_generates_commission_integration(self, auth_client, mock_db):
        """Verifica que completar un servicio mecánico dispare la liquidación de comisión

        a través del CommissionModel.
        """
        # La asignación 1 está en_proceso con mecánico V-12345678
        res_complete = auth_client.put("/api/service-mechanics/1/status", json={
            "estado": "completado",
            "porcentaje_comision": 22.5
        })
        assert res_complete.status_code == 200
        data = res_complete.get_json()
        assert data["status"] == "success"
        assert "commission_id" in data
        assert data["commission_id"] == 1

        # Verificar el porcentaje de comisión guardado
        assert mock_db.comisiones_mecanico[1]["porcentaje_comision"] == 22.5

    def test_delete_assignment_integration(self, auth_client, mock_db):
        """Verifica la eliminación de una asignación y la liberación de la clave foránea en memoria."""
        # Asignación #1 existe
        assert 1 in mock_db.servicio_mecanico

        del_res = auth_client.delete("/api/service-mechanics/1")
        assert del_res.status_code == 200
        assert del_res.get_json()["status"] == "success"

        # Debe haber desaparecido
        assert 1 not in mock_db.servicio_mecanico
        get_res = auth_client.get("/api/service-mechanics/1")
        assert get_res.status_code == 404

    def test_full_cross_module_end_to_end_flow(self, auth_client):
        """Prueba integral de extremo a extremo que conecta los 3 módulos:

        1. Crea un nuevo servicio (módulo Servicio).
        2. Registra un nuevo mecánico (módulo Mecánico).
        3. Comprueba que el mecánico inicia 'Disponible'.
        4. Asigna el nuevo servicio al nuevo mecánico (módulo Servicio Mecánico).
        5. Comprueba que el mecánico pasa automáticamente a 'Ocupado'.
        6. Avanza el flujo de trabajo: 'en_proceso' -> 'completado'.
        7. Comprueba que el mecánico vuelve a 'Disponible'.
        8. Comprueba que el historial del mecánico registra el servicio completado.
        """
        # 1. Crear nuevo servicio
        serv_res = auth_client.post("/api/services/", json={
            "nombre": "Mantenimiento Integral E2E",
            "descripcion": "Prueba de flujo integral",
            "tipo": "general",
            "precio": 50.00,
            "duracion_estimada": 90,
            "sucursal_ids": [1]
        })
        assert serv_res.status_code == 200
        new_serv_id = serv_res.get_json()["id"]

        # 2. Registrar nuevo mecánico
        mec_res = auth_client.post("/api/mechanics/", data={
            "cedula": "V-33444555",
            "nombre": "Gabriel",
            "apellido": "Mendoza",
            "telefono": "04123344555",
            "especialidad": "Mantenimiento General"
        })
        assert mec_res.status_code == 200
        new_mec_cedula = mec_res.get_json()["cedula"]

        # 3. Verificar estado inicial: Disponible
        status_initial = auth_client.get(f"/api/mechanics/{new_mec_cedula}").get_json()["data"]
        assert status_initial["estado_operativo"] == "Disponible"

        # 4. Asignar el servicio al mecánico
        assign_res = auth_client.post("/api/service-mechanics/", json={
            "servicio_id": new_serv_id,
            "mecanico_cedula": new_mec_cedula,
            "cliente_cedula": "V-87654321",
            "vehiculo_placa": "ABC123D",
            "observaciones": "Inicio de servicio E2E",
            "porcentaje_comision": 20.0
        })
        assert assign_res.status_code == 200
        new_assign_id = assign_res.get_json()["id"]

        # 5. Verificar que el mecánico ahora está Ocupado
        status_busy = auth_client.get(f"/api/mechanics/{new_mec_cedula}").get_json()["data"]
        assert status_busy["estado_operativo"] == "Ocupado"

        # 6. Transición de estado a 'en_proceso'
        prog_res = auth_client.put(f"/api/service-mechanics/{new_assign_id}/status", json={"estado": "en_proceso"})
        assert prog_res.status_code == 200

        # Transición a 'completado'
        comp_res = auth_client.put(f"/api/service-mechanics/{new_assign_id}/status", json={
            "estado": "completado",
            "porcentaje_comision": 20.0
        })
        assert comp_res.status_code == 200

        # 7. Verificar que el mecánico vuelve a estar Disponible
        status_free = auth_client.get(f"/api/mechanics/{new_mec_cedula}").get_json()["data"]
        assert status_free["estado_operativo"] == "Disponible"

        # 8. Verificar historial del mecánico
        hist_res = auth_client.get(f"/api/mechanics/history/{new_mec_cedula}")
        assert hist_res.status_code == 200
        history = hist_res.get_json()["data"]
        assert len(history) == 1
        assert history[0]["servicio_nombre"] == "Mantenimiento Integral E2E"
        assert history[0]["estado"] == "completado"

    def test_update_non_existent_assignment_routes_return_404(self, auth_client):
        """Verifica que todas las rutas de actualización retornen 404 para un ID inexistente."""
        # 1. Reasignar mecánico en ID inexistente
        res_mech = auth_client.put("/api/service-mechanics/99999/mechanic", json={
            "mecanico_cedula": "V-12345678",
            "porcentaje_comision": 15.0
        })
        assert res_mech.status_code == 404
        assert res_mech.get_json()["status"] == "error"

        # 2. Actualizar estado en ID inexistente
        res_st = auth_client.put("/api/service-mechanics/99999/status", json={"estado": "cancelado"})
        assert res_st.status_code == 404

        # 3. Actualización general en ID inexistente
        res_put = auth_client.put("/api/service-mechanics/99999", json={
            "servicio_id": 1,
            "cliente_cedula": "V-87654321",
            "vehiculo_placa": "ABC123D"
        })
        assert res_put.status_code == 404

        # 4. Eliminación en ID inexistente
        res_del = auth_client.delete("/api/service-mechanics/99999")
        assert res_del.status_code == 404

    def test_commission_percentage_boundary_validations(self, auth_client):
        """Verifica que porcentajes de comisión menores o iguales a 0 o mayores a 100 sean rechazados."""
        # Porcentaje 0% -> Error 400
        res_zero = auth_client.put("/api/service-mechanics/1/mechanic", json={
            "mecanico_cedula": "V-12345678",
            "porcentaje_comision": 0.0,
            "confirmar": True
        })
        assert res_zero.status_code == 400
        assert "porcentaje_comision" in res_zero.get_json().get("errors", {})

        # Porcentaje negativo -> Error 400
        res_neg = auth_client.put("/api/service-mechanics/1/mechanic", json={
            "mecanico_cedula": "V-12345678",
            "porcentaje_comision": -5.0,
            "confirmar": True
        })
        assert res_neg.status_code == 400

        # Porcentaje > 100% -> Error 400
        res_high = auth_client.put("/api/service-mechanics/1/mechanic", json={
            "mecanico_cedula": "V-12345678",
            "porcentaje_comision": 105.0,
            "confirmar": True
        })
        assert res_high.status_code == 400

    def test_observaciones_content_and_security_validation(self, auth_client):
        """Verifica que observaciones con etiquetas HTML/scripts o solo espacios sean rechazadas con 400."""
        # Inyección de script o caracteres no permitidos
        res_script = auth_client.post("/api/service-mechanics/", json={
            "servicio_id": 1,
            "cliente_cedula": "V-87654321",
            "vehiculo_placa": "ABC123D",
            "observaciones": "<script>alert('XSS')</script>"
        })
        assert res_script.status_code == 400
        assert "observaciones" in res_script.get_json().get("errors", {})

        # Solo espacios en blanco
        res_spaces = auth_client.post("/api/service-mechanics/", json={
            "servicio_id": 1,
            "cliente_cedula": "V-87654321",
            "vehiculo_placa": "ABC123D",
            "observaciones": "     "
        })
        assert res_spaces.status_code == 400
        assert "observaciones" in res_spaces.get_json().get("errors", {})

        # Observación válida con texto y puntuación permitida
        res_valid = auth_client.post("/api/service-mechanics/", json={
            "servicio_id": 1,
            "cliente_cedula": "V-87654321",
            "vehiculo_placa": "ABC123D",
            "observaciones": "Revisión general, cambio de pastillas - ok."
        })
        assert res_valid.status_code == 200

    def test_unassign_mechanic_via_full_update(self, auth_client, mock_db):
        """Verifica que desasignar el mecánico mediante actualización general

        convierta el estado a 'sin_asignar' y libere al mecánico.
        """
        # La asignación 1 tiene a Carlos (V-12345678) asignado
        assert auth_client.get("/api/mechanics/V-12345678").get_json()["data"]["estado_operativo"] == "Ocupado"

        # Actualizar la asignación removiendo el mecánico
        update_res = auth_client.put("/api/service-mechanics/1", json={
            "servicio_id": 1,
            "mecanico_cedula": "",
            "cliente_cedula": "V-87654321",
            "vehiculo_placa": "ABC123D",
            "estado": "sin_asignar"
        })
        assert update_res.status_code == 200

        # Verificar que el estado ahora es 'sin_asignar' y el mecánico quedó libre
        item = auth_client.get("/api/service-mechanics/1").get_json()["data"]
        assert item["mecanico_cedula"] is None
        assert item["estado"] == "sin_asignar"

        # Carlos ahora debe estar Disponible
        assert auth_client.get("/api/mechanics/V-12345678").get_json()["data"]["estado_operativo"] == "Disponible"

    def test_reassign_mechanic_updates_commission_percentage(self, auth_client, mock_db):
        """Verifica que reasignar mecánico actualice tanto la cédula como la comisión asociada."""
        # Asignar a V-87654321 con 25% de comisión
        reassign_res = auth_client.put("/api/service-mechanics/1/mechanic", json={
            "mecanico_cedula": "V-87654321",
            "porcentaje_comision": 25.0
        })
        assert reassign_res.status_code == 200
        assert reassign_res.get_json()["status"] == "success"

        # Verificar en servicio_mecanico y comisiones_mecanico
        item = auth_client.get("/api/service-mechanics/1").get_json()["data"]
        assert item["mecanico_cedula"] == "V-87654321"
        assert mock_db.comisiones_mecanico[1]["porcentaje_comision"] == 25.0

    def test_status_transition_cancelado_frees_mechanic(self, auth_client):
        """Verifica que cancelar un servicio libere al mecánico inmediatamente."""
        # Asignación #1 está en_proceso con V-12345678
        assert auth_client.get("/api/mechanics/V-12345678").get_json()["data"]["estado_operativo"] == "Ocupado"

        # Cancelar servicio
        cancel_res = auth_client.put("/api/service-mechanics/1/status", json={"estado": "cancelado"})
        assert cancel_res.status_code == 200

        # El mecánico ahora está Disponible
        assert auth_client.get("/api/mechanics/V-12345678").get_json()["data"]["estado_operativo"] == "Disponible"

    def test_full_assignment_update_all_fields_simultaneously(self, auth_client):
        """Verifica la actualización simultánea de servicio, cliente, vehículo y notas."""
        payload = {
            "servicio_id": 2,
            "mecanico_cedula": "V-87654321",
            "cliente_cedula": "V-99999999",
            "vehiculo_placa": "XYZ789E",
            "observaciones": "Actualización completa de orden",
            "estado": "asignado",
            "porcentaje_comision": 30.0
        }
        res = auth_client.put("/api/service-mechanics/1", json=payload)
        assert res.status_code == 200
        assert res.get_json()["status"] == "success"

        updated = auth_client.get("/api/service-mechanics/1").get_json()["data"]
        assert updated["servicio_id"] == 2
        assert updated["servicio_nombre"] == "Balanceo Dinámico"
        assert updated["cliente_cedula"] == "V-99999999"
        assert updated["vehiculo_placa"] == "XYZ789E"
        assert updated["observaciones"] == "Actualización completa de orden"

    def test_concurrent_assignments_multiple_mechanics(self, auth_client):
        """Verifica la consistencia al manejar múltiples asignaciones concurrentes para diferentes mecánicos."""
        # Asignación #1 tiene a V-12345678
        # Crear asignación #2 para V-87654321
        res2 = auth_client.post("/api/service-mechanics/", json={
            "servicio_id": 2,
            "mecanico_cedula": "V-87654321",
            "cliente_cedula": "V-87654321",
            "vehiculo_placa": "ABC123D"
        })
        aid2 = res2.get_json()["id"]

        # Ambos mecánicos deben figurar como Ocupados
        assert auth_client.get("/api/mechanics/V-12345678").get_json()["data"]["estado_operativo"] == "Ocupado"
        assert auth_client.get("/api/mechanics/V-87654321").get_json()["data"]["estado_operativo"] == "Ocupado"

        # Completar asignación #1 -> V-12345678 pasa a Disponible, pero V-87654321 sigue Ocupado
        auth_client.put("/api/service-mechanics/1/status", json={"estado": "completado"})
        assert auth_client.get("/api/mechanics/V-12345678").get_json()["data"]["estado_operativo"] == "Disponible"
        assert auth_client.get("/api/mechanics/V-87654321").get_json()["data"]["estado_operativo"] == "Ocupado"

        # Completar asignación #2 -> V-87654321 pasa también a Disponible
        auth_client.put(f"/api/service-mechanics/{aid2}/status", json={"estado": "completado"})
        assert auth_client.get("/api/mechanics/V-87654321").get_json()["data"]["estado_operativo"] == "Disponible"

    def test_complete_service_retains_registered_commission_percentage(self, auth_client, mock_db):
        """Verifica que si no se envía nuevo porcentaje al completar, se conserve el porcentaje original."""
        mock_db.comisiones_mecanico[1]["porcentaje_comision"] = 17.5

        # Completar sin enviar 'porcentaje_comision'
        res = auth_client.put("/api/service-mechanics/1/status", json={"estado": "completado"})
        assert res.status_code == 200
        assert res.get_json()["status"] == "success"

        # El porcentaje debe seguir siendo 17.5
        assert mock_db.comisiones_mecanico[1]["porcentaje_comision"] == 17.5

    def test_invalid_status_value_rejected(self, auth_client):
        """Verifica que enviar un estado no contemplado en el catálogo retorne código 400."""
        response = auth_client.put("/api/service-mechanics/1/status", json={"estado": "estado_inexistente"})
        assert response.status_code == 400
        data = response.get_json()
        assert data["status"] == "error"
        assert "estado" in data.get("errors", {})

