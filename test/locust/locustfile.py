# ==============================================================================
# ARCHIVO DE PRUEBA DE CARGA CON LOCUST - MÓDULO DE PRODUCTOS (CRUD COMPLETO)
# Métodos HTTP cubiertos: GET (Read), POST (Create), PUT (Update), DELETE (Delete)
# Proyecto: Transalca C.A.
# Ubicación: test/locust/locustfile.py
# ==============================================================================
#
# ¿CÓMO EJECUTAR ESTA PRUEBA?
# ---------------------------
# 1. Con interfaz web (UI en http://localhost:8089):
#    locust -f test/locust/locustfile.py --host=http://127.0.0.1:5000
#
# 2. Por consola (modo headless / sin interfaz gráfica):
#    locust -f test/locust/locustfile.py --headless -u 50 -r 5 -t 1m --host=http://127.0.0.1:5000
#
# EXPLICACIÓN DE PARÁMETROS CLAVE DEL USUARIO VIRTUAL:
# ----------------------------------------------------
# - Número total de usuarios (-u / --users):
#   Cantidad máxima de usuarios virtuales concurrentes que simularán tráfico
#   simultáneo contra el módulo de productos (ejemplo: 50 usuarios).
#
# - Tasa de generación de usuarios (-r / --spawn-rate):
#   Indica cuántos nuevos usuarios virtuales se crean por segundo hasta alcanzar
#   el número total de usuarios (-u). Por ejemplo, con -u 50 y -r 5, Locust
#   iniciará 5 usuarios cada segundo y tardará 10 segundos (50 / 5 = 10s) en
#   llegar a la carga máxima (rampa de subida o "ramp-up").
#
# - Tiempo de espera entre tareas (wait_time = between(1, 3)):
#   Simula el "tiempo de reflexión" (think time) de un usuario humano real:
#   cada usuario virtual espera aleatoriamente entre 1 y 3 segundos después
#   de completar una operación antes de ejecutar la siguiente tarea.
#
# MÉTODOS HTTP SOPORTADOS POR `self.client` EN LOCUST (Documentación Oficial):
# ----------------------------------------------------------------------------
# En Locust, `self.client` es una instancia de `HttpSession` (basada en `requests.Session`)
# y soporta todos los verbos estándar del protocolo HTTP para un CRUD:
#   - self.client.get()     -> READ   (Consultar registros)
#   - self.client.post()    -> CREATE (Crear nuevos registros)
#   - self.client.put()     -> UPDATE (Actualizar registros completos / cambio de estado)
#   - self.client.patch()   -> UPDATE (Actualización parcial en APIs REST)
#   - self.client.delete()  -> DELETE (Eliminación física/lógica en APIs REST)
#   - self.client.head() / self.client.options() -> Verificación de cabeceras y CORS
# ==============================================================================

import os
import random
import uuid
from locust import HttpUser, task, between


class ProductoCRUDUser(HttpUser):
    """
    Clase que define el comportamiento del Usuario Virtual (HttpUser) en Locust.
    Simula las operaciones CRUD completas (Create, Read, Update, Delete) sobre
    el módulo de Productos (`/api/products`).
    """

    # Host base por defecto hacia el servidor Flask de Transalca
    host = os.getenv("LOCUST_HOST", "http://127.0.0.1:5000")

    # Tiempo de espera aleatorio (en segundos) entre cada tarea ejecutada por un mismo usuario.
    # between(1, 3) significa que el usuario virtual esperará entre 1 y 3 segundos entre peticiones.
    wait_time = between(1, 3)

    def on_start(self):
        """
        Método del ciclo de vida de Locust que se ejecuta UNA SOLA VEZ por cada
        usuario virtual cuando este es generado (según el spawn rate).
        1. Autentica al usuario mediante POST /auth/do_login para obtener la cookie `session`.
        2. Inicializa la lista de códigos creados por este usuario virtual para usarlos
           posteriormente en las tareas de consulta individual (GET), actualización (PUT)
           y eliminación (DELETE / PUT toggle).
        """
        # Lista propia de cada usuario virtual para almacenar los códigos de productos creados
        self.codigos_creados = []

        # Valores base por defecto para relaciones foráneas (se actualizan dinámicamente abajo)
        self.categoria_default = "Filtros"
        self.marca_default = "Generica"
        self.sucursal_id_default = 1

        # Credenciales de prueba (pueden sobreescribirse por variables de entorno)
        credenciales = {
            "email": os.getenv("LOCUST_USER_EMAIL", "admin@transalca.com"),
            "password": os.getenv("LOCUST_USER_PASSWORD", "Admin123!"),
        }

        # 1. Iniciar sesión con POST para obtener la cookie de sesión de Flask
        with self.client.post(
            "/auth/do_login",
            json=credenciales,
            name="00_Auth - [POST] Iniciar Sesión (on_start)",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Error al iniciar sesión: HTTP {response.status_code}")

        # 2. Cargar dinámicamente una categoría, marca y sucursal activas existentes en la BD
        #    para garantizar que los POST y PUT del CRUD utilicen datos válidos.
        self._cargar_datos_referencia()

    def _cargar_datos_referencia(self):
        """
        Obtiene una categoría, marca y sucursal activas desde la API al iniciar el usuario
        para usarlas al crear (POST) y actualizar (PUT) productos.
        """
        # Obtener categoría activa
        resp_cat = self.client.get("/api/categories/active", name="00_Init - [GET] Categorías Activas")
        if resp_cat.status_code == 200:
            cats = resp_cat.json().get("data") or []
            if cats:
                self.categoria_default = cats[0].get("nombre_categoria") or cats[0].get("nombre") or self.categoria_default

        # Obtener marca activa
        resp_brand = self.client.get("/api/brands/active", name="00_Init - [GET] Marcas Activas")
        if resp_brand.status_code == 200:
            brands = resp_brand.json().get("data") or []
            if brands:
                self.marca_default = brands[0].get("nombre_marca") or brands[0].get("nombre") or self.marca_default

        # Obtener sucursal activa
        resp_suc = self.client.get("/api/sucursales/active", name="00_Init - [GET] Sucursales Activas")
        if resp_suc.status_code == 200:
            sucs = resp_suc.json().get("data") or []
            if sucs:
                self.sucursal_id_default = int(sucs[0].get("id_sucursal") or sucs[0].get("id") or 1)

    # ==========================================================================
    # 1. OPERACIONES "READ" DEL CRUD — MÉTODO HTTP GET (@task con mayor peso)
    # ==========================================================================
    # En pruebas de carga reales, las consultas (GET) tienen mayor peso (@task(4), @task(3))
    # porque los usuarios consultan el catálogo con más frecuencia de la que crean o borran.
    # ==========================================================================

    @task(4)
    def leer_productos_activos_catalogo(self):
        """
        [READ - GET] Tarea con peso 4 (alta probabilidad):
        Consulta el catálogo público de productos activos paginados (`GET /api/products/active`).
        """
        with self.client.get(
            "/api/products/active?page=1&per_page=10",
            name="01_CRUD_READ - [GET] Consultar Activos (/api/products/active)",
            catch_response=True,
        ) as response:
            if response.status_code == 200 and response.json().get("status") == "success":
                response.success()
            else:
                response.failure(f"Fallo en GET activos: HTTP {response.status_code}")

    @task(3)
    def leer_listado_general_productos(self):
        """
        [READ - GET] Tarea con peso 3 (frecuencia media-alta):
        Consulta el listado administrativo paginado (`GET /api/products/?page=1&per_page=10`).
        """
        with self.client.get(
            "/api/products/?page=1&per_page=10",
            name="02_CRUD_READ - [GET] Listar Productos Paginados (/api/products/)",
            catch_response=True,
        ) as response:
            if response.status_code == 200 and response.json().get("status") == "success":
                # Si aún no tenemos códigos guardados, tomamos uno existente para pruebas de detalle
                datos = response.json().get("data") or []
                if datos and not self.codigos_creados:
                    codigo_existente = datos[0].get("codigo")
                    if codigo_existente:
                        self.codigos_creados.append(codigo_existente)
                response.success()
            else:
                response.failure(f"Fallo en GET listado: HTTP {response.status_code}")

    @task(2)
    def leer_detalle_y_busqueda_producto(self):
        """
        [READ - GET] Tarea con peso 2 (frecuencia media):
        Busca productos por coincidencia (`GET /api/products/search?q=...`) y, si existe
        algún código registrado en memoria, consulta su detalle (`GET /api/products/detail/<codigo>`).
        """
        # 1. Búsqueda por texto
        with self.client.get(
            "/api/products/search?q=filtro",
            name="03_CRUD_READ - [GET] Buscar Productos (/api/products/search)",
            catch_response=True,
        ) as response:
            if response.status_code == 200 and response.json().get("status") == "success":
                response.success()
            else:
                response.failure(f"Fallo en GET búsqueda: HTTP {response.status_code}")

        # 2. Consulta de detalle individual por código (si hay códigos en la lista)
        if self.codigos_creados:
            codigo = random.choice(self.codigos_creados)
            with self.client.get(
                f"/api/products/detail/{codigo}",
                name="04_CRUD_READ - [GET] Detalle por Código (/api/products/detail/[codigo])",
                catch_response=True,
            ) as response:
                if response.status_code in (200, 404):
                    response.success()
                else:
                    response.failure(f"Fallo en GET detalle: HTTP {response.status_code}")

    # ==========================================================================
    # 2. OPERACIÓN "CREATE" DEL CRUD — MÉTODO HTTP POST (@task(2))
    # ==========================================================================

    @task(2)
    def crear_producto_post(self):
        """
        [CREATE - POST] Tarea con peso 2:
        Envía una petición `POST /api/products/` con un payload JSON para registrar
        un nuevo producto en la base de datos.
        """
        # Generamos un código único para evitar colisiones entre usuarios virtuales concurrentes
        sufijo_unico = uuid.uuid4().hex[:6].upper()
        codigo_nuevo = f"LOC-{sufijo_unico}"

        nuevo_producto = {
            "codigo": codigo_nuevo,
            "nombre": "Repuesto Prueba Carga Locust",
            "descripcion": f"Producto generado automaticamente por Locust ({codigo_nuevo})",
            "precio": str(round(random.uniform(10.0, 250.0), 2)),
            "categoria": self.categoria_default,
            "marca": self.marca_default,
            "sucursal_ids": [self.sucursal_id_default],
        }

        with self.client.post(
            "/api/products/",
            json=nuevo_producto,
            name="05_CRUD_CREATE - [POST] Crear Producto (/api/products/)",
            catch_response=True,
        ) as response:
            if response.status_code == 200 and response.json().get("status") == "success":
                # Guardamos el código recién creado para poder actualizarlo (PUT) o eliminarlo después
                self.codigos_creados.append(codigo_nuevo)
                response.success()
            else:
                response.failure(f"Fallo en POST crear producto: HTTP {response.status_code} - {response.text[:120]}")

    # ==========================================================================
    # 3. OPERACIÓN "UPDATE" DEL CRUD — MÉTODO HTTP PUT (@task(2))
    # ==========================================================================

    @task(2)
    def actualizar_producto_put(self):
        """
        [UPDATE - PUT] Tarea con peso 2:
        Envía una petición `PUT /api/products/update` para modificar los datos (nombre,
        descripción y precio) de un producto existente previamente creado por el usuario virtual.
        """
        if not self.codigos_creados:
            # Si aún no hay un producto creado en esta sesión, creamos uno primero
            self.crear_producto_post()
            return

        codigo_objetivo = random.choice(self.codigos_creados)
        datos_actualizados = {
            "old_codigo": codigo_objetivo,
            "codigo": codigo_objetivo,
            "nombre": "Repuesto Actualizado por Locust",
            "descripcion": f"Descripcion modificada mediante metodo PUT para {codigo_objetivo}",
            "precio": str(round(random.uniform(15.0, 300.0), 2)),
            "categoria": self.categoria_default,
            "marca": self.marca_default,
            "sucursal_ids": [self.sucursal_id_default],
        }

        with self.client.put(
            "/api/products/update",
            json=datos_actualizados,
            name="06_CRUD_UPDATE - [PUT] Actualizar Producto (/api/products/update)",
            catch_response=True,
        ) as response:
            if response.status_code == 200 and response.json().get("status") == "success":
                response.success()
            else:
                response.failure(f"Fallo en PUT actualizar producto: HTTP {response.status_code} - {response.text[:120]}")

    # ==========================================================================
    # 4. OPERACIÓN "DELETE" DEL CRUD — MÉTODOS HTTP PUT (Soft Delete) Y DELETE (@task(1))
    # ==========================================================================

    @task(1)
    def eliminar_producto_crud(self):
        """
        [DELETE - PUT / DELETE] Tarea con peso 1 (menor frecuencia):
        Ejecuta la eliminación del producto dentro del flujo CRUD:
        1. En el backend de Transalca (`product_controller.py`), la eliminación de productos
           es un borrado lógico (soft delete: `estado = 0`) implementado con `PUT /api/products/toggle`.
        2. Adicionalmente se demuestra el uso del método nativo `self.client.delete()` de Locust
           para ilustrar cómo se invoca el verbo HTTP `DELETE` estándar en pruebas de carga.
        """
        if not self.codigos_creados:
            return

        # Extraemos el último código creado para darlo de baja
        codigo_eliminar = self.codigos_creados.pop()

        # Parte A: Eliminación lógica real del módulo de productos (PUT /api/products/toggle)
        with self.client.put(
            "/api/products/toggle",
            json={"codigo": codigo_eliminar},
            name="07_CRUD_DELETE - [PUT] Eliminar/Desactivar Producto (/api/products/toggle)",
            catch_response=True,
        ) as response:
            if response.status_code in (200, 404):
                response.success()
            else:
                response.failure(f"Fallo al desactivar producto: HTTP {response.status_code}")

        # Parte B: Demostración del verbo HTTP DELETE con `self.client.delete()` en Locust.
        # Nota: Como `/api/products/` no define una ruta con methods=['DELETE'], Flask responde 404/405;
        # usamos `catch_response=True` para validar que el servidor rechace correctamente el verbo no habilitado
        # y dejar documentado el uso de `self.client.delete()` en las métricas de Locust.
        with self.client.delete(
            f"/api/products/{codigo_eliminar}",
            name="08_CRUD_DELETE - [DELETE] Petición HTTP DELETE (/api/products/[codigo])",
            catch_response=True,
        ) as response:
            if response.status_code in (200, 204, 404, 405):
                response.success()
            else:
                response.failure(f"Error inesperado en petición DELETE: HTTP {response.status_code}")

    @task(2)
    def actualizar_producto_put(self):
        """
        [UPDATE - PUT] Tarea con peso 2:
        Envía una petición `PUT /api/products/update` para modificar los datos (nombre,
        descripción y precio) de un producto existente previamente creado por el usuario virtual.
        """
        if not self.codigos_creados:
            # Si aún no hay un producto creado en esta sesión, creamos uno primero
            self.crear_producto_post()
            return

        codigo_objetivo = random.choice(self.codigos_creados)
        datos_actualizados = {
            "old_codigo": codigo_objetivo,
            "codigo": codigo_objetivo,
            "nombre": "Repuesto Actualizado por Locust",
            "descripcion": f"Descripcion modificada mediante metodo PUT para {codigo_objetivo}",
            "precio": str(round(random.uniform(15.0, 300.0), 2)),
            "categoria": self.categoria_default,
            "marca": self.marca_default,
            "sucursal_ids": [self.sucursal_id_default],
        }

        with self.client.put(
            "/api/products/update",
            json=datos_actualizados,
            name="06_CRUD_UPDATE - [PUT] Actualizar Producto (/api/products/update)",
            catch_response=True,
        ) as response:
            if response.status_code == 200 and response.json().get("status") == "success":
                response.success()
            else:
                response.failure(f"Fallo en PUT actualizar producto: HTTP {response.status_code} - {response.text[:120]}")

    # ==========================================================================
    # 4. OPERACIÓN "DELETE" DEL CRUD — MÉTODOS HTTP PUT (Soft Delete) Y DELETE (@task(1))
    # ==========================================================================

    @task(1)
    def eliminar_producto_crud(self):
        """
        [DELETE - PUT / DELETE] Tarea con peso 1 (menor frecuencia):
        Ejecuta la eliminación del producto dentro del flujo CRUD:
        1. En el backend de Transalca (`product_controller.py`), la eliminación de productos
           es un borrado lógico (soft delete: `estado = 0`) implementado con `PUT /api/products/toggle`.
        2. Adicionalmente se demuestra el uso del método nativo `self.client.delete()` de Locust
           para ilustrar cómo se invoca el verbo HTTP `DELETE` estándar en pruebas de carga.
        """
        if not self.codigos_creados:
            return

        # Extraemos el último código creado para darlo de baja
        codigo_eliminar = self.codigos_creados.pop()

        # Parte A: Eliminación lógica real del módulo de productos (PUT /api/products/toggle)
        with self.client.put(
            "/api/products/toggle",
            json={"codigo": codigo_eliminar},
            name="07_CRUD_DELETE - [PUT] Eliminar/Desactivar Producto (/api/products/toggle)",
            catch_response=True,
        ) as response:
            if response.status_code in (200, 404):
                response.success()
            else:
                response.failure(f"Fallo al desactivar producto: HTTP {response.status_code}")

        # Parte B: Demostración del verbo HTTP DELETE con `self.client.delete()` en Locust.
        # Nota: Como `/api/products/` no define una ruta con methods=['DELETE'], Flask responde 404/405;
        # usamos `catch_response=True` para validar que el servidor rechace correctamente el verbo no habilitado
        # y dejar documentado el uso de `self.client.delete()` en las métricas de Locust.
        with self.client.delete(
            f"/api/products/{codigo_eliminar}",
            name="08_CRUD_DELETE - [DELETE] Petición HTTP DELETE (/api/products/[codigo])",
            catch_response=True,
        ) as response:
            if response.status_code in (200, 204, 404, 405):
                response.success()
            else:
                response.failure(f"Error inesperado en petición DELETE: HTTP {response.status_code}")

