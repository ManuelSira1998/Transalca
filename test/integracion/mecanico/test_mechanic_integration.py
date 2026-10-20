import io
import os
import pytest


class TestMechanicIntegration:
    """Pruebas de integración para el módulo de Mecánicos.

    Valida la interacción completa entre las rutas HTTP, el controlador,
    el modelo MechanicModel, las validaciones de negocio y la base de datos.
    """

    def test_unauthorized_access_rejected(self, client):
        """Verifica que las rutas de modificación rechacen peticiones sin sesión autenticada."""
        # Creación sin sesión
        res_post = client.post("/api/mechanics/", data={"cedula": "V-30000001", "nombre": "Test", "apellido": "User"})
        assert res_post.status_code == 401
        assert res_post.get_json()["status"] == "error"

        # Modificación sin sesión
        res_put = client.put("/api/mechanics/update", data={"old_cedula": "V-12345678", "cedula": "V-12345678", "nombre": "Nuevo"})
        assert res_put.status_code == 401

        # Eliminación sin sesión
        res_del = client.delete("/api/mechanics/delete", json={"cedula": "V-12345678"})
        assert res_del.status_code == 401

    def test_get_all_mechanics_integration(self, auth_client):
        """Verifica que el listado de mecánicos cargue los registros activos con su estado operativo y total de servicios."""
        response = auth_client.get("/api/mechanics/")
        assert response.status_code == 200
        data = response.get_json()

        assert data["status"] == "success"
        mechanics = data["data"]
        assert isinstance(mechanics, list)
        assert len(mechanics) >= 2

        # Verificar que solo retorne mecánicos activos
        cedulas = [m["cedula"] for m in mechanics]
        assert "V-12345678" in cedulas
        assert "V-87654321" in cedulas
        assert "V-11111111" not in cedulas  # Mecánico inactivo

        # Verificar estructura e información integrada
        mec = next(m for m in mechanics if m["cedula"] == "V-12345678")
        assert mec["nombre"] == "Carlos"
        assert mec["apellido"] == "Pérez"
        assert "estado_operativo" in mec
        assert "total_servicios" in mec

    def test_get_one_mechanic_found(self, auth_client):
        """Verifica la consulta individual de un mecánico existente por su cédula."""
        response = auth_client.get("/api/mechanics/V-12345678")
        assert response.status_code == 200
        data = response.get_json()

        assert data["status"] == "success"
        item = data["data"]
        assert item["cedula"] == "V-12345678"
        assert item["nombre"] == "Carlos"
        assert item["apellido"] == "Pérez"
        assert item["especialidad"] == "Frenos y Motor"

    def test_get_one_mechanic_not_found(self, auth_client):
        """Verifica que solicitar una cédula inexistente retorne código 404."""
        response = auth_client.get("/api/mechanics/V-99999999")
        assert response.status_code == 404
        data = response.get_json()
        assert data["status"] == "error"
        assert "no encontrado" in data["message"].lower()

    def test_create_mechanic_success_and_normalization(self, auth_client, mock_db):
        """Prueba el registro exitoso de un mecánico con normalización de cédula y teléfono."""
        payload = {
            "cedula": "  v-20999888  ",
            "nombre": "Roberto",
            "apellido": "Morales",
            "telefono": "0424-5556677",
            "especialidad": "Diagnóstico Computarizado"
        }
        response = auth_client.post("/api/mechanics/", data=payload)
        assert response.status_code == 200
        data = response.get_json()

        assert data["status"] == "success"
        assert data["cedula"] == "V-20999888"

        # Verificar persistencia en el estado y consulta posterior
        get_res = auth_client.get("/api/mechanics/V-20999888")
        assert get_res.status_code == 200
        saved = get_res.get_json()["data"]
        assert saved["nombre"] == "Roberto"
        assert saved["apellido"] == "Morales"
        assert saved["telefono"] == "04245556677"
        assert saved["especialidad"] == "Diagnóstico Computarizado"
        assert saved["estado_operativo"] == "Disponible"

    def test_create_mechanic_validation_errors(self, auth_client):
        """Verifica que fallas de validación retornen código 400 con diccionario de errores."""
        invalid_payload = {
            "cedula": "invalida",
            "nombre": "123",  # Nombre numérico inválido
            "apellido": "",
            "telefono": "1234"  # Teléfono incompleto
        }
        response = auth_client.post("/api/mechanics/", data=invalid_payload)
        assert response.status_code == 400
        data = response.get_json()

        assert data["status"] == "error"
        assert "errors" in data
        assert "cedula" in data["errors"]
        assert "nombre" in data["errors"]

    def test_create_duplicate_active_mechanic_fails(self, auth_client):
        """Verifica que registrar una cédula ya existente y activa sea rechazado con 400."""
        payload = {
            "cedula": "V-12345678",
            "nombre": "Duplicado",
            "apellido": "Pérez",
            "telefono": "04141234567"
        }
        response = auth_client.post("/api/mechanics/", data=payload)
        assert response.status_code == 400
        data = response.get_json()
        assert data["status"] == "error"
        assert "ya esta registrada" in data["errors"].get("cedula", "")

    def test_create_existing_inactive_mechanic_reactivates(self, auth_client, mock_db):
        """Verifica que si un mecánico fue desactivado, registrarlo nuevamente lo reactiva y actualiza."""
        assert mock_db.mecanicos["V-11111111"]["estado"] == 0

        payload = {
            "cedula": "V-11111111",
            "nombre": "Mecánico",
            "apellido": "Reactivado",
            "telefono": "04161112233",
            "especialidad": "Electricidad Automotriz"
        }
        response = auth_client.post("/api/mechanics/", data=payload)
        assert response.status_code == 200

        # Ahora debe figurar como activo
        assert mock_db.mecanicos["V-11111111"]["estado"] == 1
        assert mock_db.mecanicos["V-11111111"]["apellido_mecanico"] == "Reactivado"

        # Y aparecer en la lista de activos
        list_res = auth_client.get("/api/mechanics/")
        cedulas = [m["cedula"] for m in list_res.get_json()["data"]]
        assert "V-11111111" in cedulas

    def test_check_unique_endpoint(self, auth_client):
        """Prueba la validación asíncrona de unicidad de cédula."""
        # Cédula existente
        res_exists = auth_client.post("/api/mechanics/check-unique", json={"value": "V-12345678"})
        assert res_exists.status_code == 200
        assert res_exists.get_json()["exists"] is True

        # Cédula disponible
        res_new = auth_client.post("/api/mechanics/check-unique", json={"value": "V-77777777"})
        assert res_new.status_code == 200
        assert res_new.get_json()["exists"] is False

        # Cédula existente pero excluida (edición del mismo registro)
        res_excl = auth_client.post("/api/mechanics/check-unique", json={"value": "V-12345678", "exclude": "V-12345678"})
        assert res_excl.status_code == 200
        assert res_excl.get_json()["exists"] is False

    def test_update_mechanic_integration(self, auth_client):
        """Verifica la modificación de un mecánico existente."""
        payload = {
            "old_cedula": "V-87654321",
            "cedula": "V-87654321",
            "nombre": "Andrés Modificado",
            "apellido": "Gómez Silva",
            "telefono": "04129998877",
            "especialidad": "Tren Delantero"
        }
        response = auth_client.put("/api/mechanics/update", data=payload)
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "success"

        # Verificar persistencia consultando de nuevo
        get_res = auth_client.get("/api/mechanics/V-87654321")
        item = get_res.get_json()["data"]
        assert item["nombre"] == "Andrés Modificado"
        assert item["apellido"] == "Gómez Silva"
        assert item["especialidad"] == "Tren Delantero"

    def test_soft_delete_mechanic_integration(self, auth_client, mock_db):
        """Verifica la eliminación lógica (soft delete) del mecánico."""
        response = auth_client.delete("/api/mechanics/delete", json={"cedula": "V-87654321"})
        assert response.status_code == 200
        assert response.get_json()["status"] == "success"

        # Verificar que su estado interno sea 0
        assert mock_db.mecanicos["V-87654321"]["estado"] == 0

        # Verificar que ya no se liste en activos
        list_res = auth_client.get("/api/mechanics/")
        cedulas = [m["cedula"] for m in list_res.get_json()["data"]]
        assert "V-87654321" not in cedulas

    def test_mechanic_operational_status_with_service_mechanic(self, auth_client):
        """Prueba de integración cruzada: el estado operativo cambia dinámicamente

        entre 'Ocupado' y 'Disponible' según los servicios activos en servicio_mecanico.
        """
        # V-12345678 tiene un servicio activo 'en_proceso' asignado inicialmente
        res_busy = auth_client.get("/api/mechanics/V-12345678")
        assert res_busy.status_code == 200
        assert res_busy.get_json()["data"]["estado_operativo"] == "Ocupado"

        # V-87654321 no tiene ningún servicio asignado -> Disponible
        res_free = auth_client.get("/api/mechanics/V-87654321")
        assert res_free.status_code == 200
        assert res_free.get_json()["data"]["estado_operativo"] == "Disponible"

        # Al completar el servicio mecánico #1, V-12345678 pasa a estar Disponible
        status_res = auth_client.put("/api/service-mechanics/1/status", json={"estado": "completado"})
        assert status_res.status_code == 200

        res_free_now = auth_client.get("/api/mechanics/V-12345678")
        assert res_free_now.get_json()["data"]["estado_operativo"] == "Disponible"

    def test_mechanic_service_history_integration(self, auth_client):
        """Prueba de integración: consulta del historial de servicios asociados al mecánico."""
        response = auth_client.get("/api/mechanics/history/V-12345678")
        assert response.status_code == 200
        data = response.get_json()

        assert data["status"] == "success"
        history = data["data"]
        assert isinstance(history, list)
        assert len(history) >= 1

        service_entry = history[0]
        assert service_entry["id"] == 1
        assert service_entry["servicio_nombre"] == "Alineación Computarizada"
        assert service_entry["mecanico_cedula"] == "V-12345678"

    def test_create_mechanic_with_photo_upload_success(self, auth_client):
        """Verifica la subida exitosa de foto de perfil (PNG) asociada al mecánico."""
        file_content = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4"
        payload = {
            "cedula": "V-55667788",
            "nombre": "Foto",
            "apellido": "Tester",
            "telefono": "04141122334",
            "especialidad": "Frenos",
            "foto_perfil": (io.BytesIO(file_content), "avatar.png", "image/png")
        }
        response = auth_client.post("/api/mechanics/", data=payload, content_type="multipart/form-data")
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "success"

        # Verificar que se guardó un nombre de archivo que empieza con 'mec_'
        get_res = auth_client.get("/api/mechanics/V-55667788")
        saved_photo = get_res.get_json()["data"]["foto_perfil"]
        assert saved_photo.startswith("mec_")
        assert saved_photo.endswith(".png")

        # Limpiar archivo generado en disco si existe
        disk_path = os.path.join("public", "assets", "profile_pics", saved_photo)
        if os.path.exists(disk_path):
            os.remove(disk_path)

    def test_create_mechanic_invalid_photo_extension_fails(self, auth_client):
        """Verifica que subir un archivo que no sea imagen (e.g. .txt o .exe) sea rechazado con 400."""
        payload = {
            "cedula": "V-55667799",
            "nombre": "Foto",
            "apellido": "Invalida",
            "telefono": "04141122334",
            "foto_perfil": (io.BytesIO(b"fake script"), "malicious.txt", "text/plain")
        }
        response = auth_client.post("/api/mechanics/", data=payload, content_type="multipart/form-data")
        assert response.status_code == 400
        data = response.get_json()
        assert data["status"] == "error"
        assert "debe ser una imagen" in data["message"].lower()

    def test_update_mechanic_remove_photo(self, auth_client, mock_db):
        """Verifica que enviar foto_perfil_remove: '1' restablezca la foto a 'default.png'."""
        mock_db.mecanicos["V-12345678"]["foto_perfil"] = "mec_custom.png"
        mock_db.mecanicos["V-12345678"]["foto_perfil_mecanico"] = "mec_custom.png"

        payload = {
            "old_cedula": "V-12345678",
            "cedula": "V-12345678",
            "nombre": "Carlos",
            "apellido": "Pérez",
            "foto_perfil_remove": "1"
        }
        response = auth_client.put("/api/mechanics/update", data=payload)
        assert response.status_code == 200

        get_res = auth_client.get("/api/mechanics/V-12345678")
        assert get_res.get_json()["data"]["foto_perfil"] == "default.png"

    def test_create_mechanic_foreigner_and_legal_cedula_integration(self, auth_client):
        """Verifica la creación con prefijos E- (Extranjero) y J- (Jurídico)."""
        # Prefijo Extranjero
        res_e = auth_client.post("/api/mechanics/", data={
            "cedula": "e 88776655",
            "nombre": "Jean",
            "apellido": "Valjean"
        })
        assert res_e.status_code == 200
        assert res_e.get_json()["cedula"] == "E-88776655"

        item_e = auth_client.get("/api/mechanics/E-88776655").get_json()["data"]
        assert item_e["cedula_prefijo"] == "E"

        # Prefijo Jurídico
        res_j = auth_client.post("/api/mechanics/", data={
            "cedula": "J12345678",
            "nombre": "Taller",
            "apellido": "Asociado"
        })
        assert res_j.status_code == 200
        assert res_j.get_json()["cedula"] == "J-12345678"

    def test_create_mechanic_name_length_boundaries(self, auth_client):
        """Verifica los límites de longitud de nombres (mínimo 2 caracteres, máximo 60)."""
        # Nombre de 1 carácter -> Error 400
        res_short = auth_client.post("/api/mechanics/", data={
            "cedula": "V-40111222",
            "nombre": "A",
            "apellido": "Pérez"
        })
        assert res_short.status_code == 400
        assert "nombre" in res_short.get_json().get("errors", {})

        # Nombre de 2 caracteres -> Éxito 200
        res_min = auth_client.post("/api/mechanics/", data={
            "cedula": "V-40111222",
            "nombre": "Al",
            "apellido": "Pérez"
        })
        assert res_min.status_code == 200

        # Nombre mayor a 60 caracteres -> Error 400
        res_long = auth_client.post("/api/mechanics/", data={
            "cedula": "V-40111333",
            "nombre": "A" * 65,
            "apellido": "Pérez"
        })
        assert res_long.status_code == 400

    def test_create_mechanic_alphabetic_name_enforcement(self, auth_client):
        """Verifica que nombres con dígitos o caracteres no permitidos sean rechazados."""
        res_digits = auth_client.post("/api/mechanics/", data={
            "cedula": "V-40111444",
            "nombre": "Carlos123",
            "apellido": "Pérez"
        })
        assert res_digits.status_code == 400
        assert "nombre" in res_digits.get_json()["errors"]

        res_symbols = auth_client.post("/api/mechanics/", data={
            "cedula": "V-40111444",
            "nombre": "Carlos",
            "apellido": "Pérez#$"
        })
        assert res_symbols.status_code == 400
        assert "apellido" in res_symbols.get_json()["errors"]

    def test_update_mechanic_missing_old_cedula_fails(self, auth_client):
        """Verifica que intentar actualizar sin especificar 'old_cedula' retorne 400."""
        payload = {
            "cedula": "V-12345678",
            "nombre": "Carlos",
            "apellido": "Pérez"
        }
        response = auth_client.put("/api/mechanics/update", data=payload)
        assert response.status_code == 400
        data = response.get_json()
        assert "Identificador requerido" in data["errors"].get("old_cedula", "")

    def test_update_mechanic_cedula_collision_fails(self, auth_client):
        """Verifica que intentar cambiar la cédula a una ya ocupada por otro mecánico retorne 400."""
        payload = {
            "old_cedula": "V-87654321",
            "cedula": "V-12345678",  # Cédula perteneciente al otro mecánico
            "nombre": "Andrés",
            "apellido": "Gómez"
        }
        response = auth_client.put("/api/mechanics/update", data=payload)
        assert response.status_code == 400
        data = response.get_json()
        assert "ya esta registrada" in data["errors"].get("cedula", "")

    def test_soft_delete_non_existent_mechanic_returns_404(self, auth_client):
        """Verifica que intentar eliminar un mecánico que no existe retorne 404."""
        response = auth_client.delete("/api/mechanics/delete", json={"cedula": "V-99999999"})
        assert response.status_code == 404
        assert response.get_json()["status"] == "error"

    def test_operational_status_multiple_services_lifecycle(self, auth_client, mock_db):
        """Verifica el cálculo de 'estado_operativo' cuando un mecánico tiene múltiples servicios."""
        ced = "V-87654321"

        # Inicialmente libre
        assert auth_client.get(f"/api/mechanics/{ced}").get_json()["data"]["estado_operativo"] == "Disponible"

        # Asignar primer servicio
        res1 = auth_client.post("/api/service-mechanics/", json={
            "servicio_id": 1,
            "mecanico_cedula": ced,
            "cliente_cedula": "V-87654321",
            "vehiculo_placa": "ABC123D"
        })
        aid1 = res1.get_json()["id"]
        assert auth_client.get(f"/api/mechanics/{ced}").get_json()["data"]["estado_operativo"] == "Ocupado"

        # Asignar segundo servicio (confirmar asignación múltiple)
        res2 = auth_client.post("/api/service-mechanics/", json={
            "servicio_id": 2,
            "mecanico_cedula": ced,
            "cliente_cedula": "V-87654321",
            "vehiculo_placa": "ABC123D"
        })
        aid2 = res2.get_json()["id"]
        assert auth_client.get(f"/api/mechanics/{ced}").get_json()["data"]["estado_operativo"] == "Ocupado"

        # Completar servicio #1 -> Debe seguir 'Ocupado' porque el servicio #2 sigue activo
        auth_client.put(f"/api/service-mechanics/{aid1}/status", json={"estado": "completado"})
        assert auth_client.get(f"/api/mechanics/{ced}").get_json()["data"]["estado_operativo"] == "Ocupado"

        # Cancelar servicio #2 -> Ahora debe pasar a 'Disponible'
        auth_client.put(f"/api/service-mechanics/{aid2}/status", json={"estado": "cancelado"})
        assert auth_client.get(f"/api/mechanics/{ced}").get_json()["data"]["estado_operativo"] == "Disponible"

    def test_mechanic_service_history_multiple_items_and_ordering(self, auth_client):
        """Verifica que el historial muestre todos los servicios completados y cancelados en orden."""
        ced = "V-12345678"

        # Registrar un segundo servicio para el mismo mecánico
        auth_client.post("/api/service-mechanics/", json={
            "servicio_id": 2,
            "mecanico_cedula": ced,
            "cliente_cedula": "V-87654321",
            "vehiculo_placa": "ABC123D",
            "observaciones": "Segundo servicio del mecánico"
        })

        hist_res = auth_client.get(f"/api/mechanics/history/{ced}")
        assert hist_res.status_code == 200
        history = hist_res.get_json()["data"]
        assert len(history) >= 2
        service_names = [h["servicio_nombre"] for h in history]
        assert "Alineación Computarizada" in service_names
        assert "Balanceo Dinámico" in service_names

    def test_check_unique_invalid_or_empty_cedula_returns_400(self, auth_client):
        """Verifica que enviar un valor vacío o inválido a /check-unique retorne error 400."""
        response = auth_client.post("/api/mechanics/check-unique", json={"value": ""})
        assert response.status_code == 400
        data = response.get_json()
        assert data["status"] == "error"

