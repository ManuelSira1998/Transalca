import pytest
import re
from datetime import datetime, timedelta
from functools import lru_cache
from werkzeug.security import generate_password_hash as _generate_password_hash, check_password_hash


@lru_cache(maxsize=None)
def generate_password_hash(password):
    return _generate_password_hash(password)
from app import app as flask_app
from model.connection import Connection
from model.mail_service import MailService
import controller.vehicle_controller
from controller._guards import is_client
controller.vehicle_controller.is_client = is_client


class MockCursor:

    def __init__(self, db, db_name="transalca"):
        self.db = db
        self.db_name = db_name
        self.lastrowid = 1
        self.rowcount = 0
        self._rows = []
        self._pos = 0

    def execute(self, sql, params=None):
        sql_s = (sql or "").strip()
        sql_u = sql_s.upper()
        self.lastrowid = 1
        self.rowcount = 0
        self._rows = []
        self._pos = 0

        if sql_u.startswith("SET ") or "SET @" in sql_u:
            return 0
        if sql_u.startswith("SELECT") or sql_u.startswith("SHOW"):
            res = self.db.fetch_all(self.db_name, sql, params)
            if not res and ("LIMIT 1" in sql_u or "COUNT(" in sql_u or "WHERE" in sql_u):
                one = self.db.fetch_one(self.db_name, sql, params)
                if one:
                    res = [one]
            self._rows = res if isinstance(res, list) else ([res] if res else [])
            self.rowcount = len(self._rows)
            return self.rowcount
        elif sql_u.startswith("INSERT"):
            self.lastrowid = self.db.insert(self.db_name, sql, params)
            self.rowcount = 1
            return 1
        elif sql_u.startswith("UPDATE"):
            self.rowcount = self.db.update(self.db_name, sql, params) or 1
            return self.rowcount
        elif sql_u.startswith("DELETE"):
            self.rowcount = self.db.delete(self.db_name, sql, params) or 1
            return self.rowcount
        else:
            self.db.execute_query(self.db_name, sql, params)
            return 0

    def fetchone(self):
        if self._pos < len(self._rows):
            row = self._rows[self._pos]
            self._pos += 1
            return dict(row) if isinstance(row, dict) else row
        return None

    def fetchall(self):
        res = [dict(r) if isinstance(r, dict) else r for r in self._rows[self._pos:]]
        self._pos = len(self._rows)
        return res

    def close(self):
        pass


class MockConnectionObj:

    def __init__(self, db, db_name="transalca"):
        self.db = db
        self.db_name = db_name
        self.open = True

    def cursor(self, cursorclass=None):
        return MockCursor(self.db, self.db_name)

    def begin(self):
        pass

    def commit(self):
        pass

    def rollback(self):
        pass

    def ping(self, reconnect=True):
        pass

    def close(self):
        pass


class MockDatabase:

    def __init__(self):
        self.reset()

    def reset(self):
        self.next_service_id = 10
        self.next_assignment_id = 10
        self.next_commission_id = 10
        self.next_user_id = 10
        self.next_role_id = 10
        self.next_modulo_id = 10
        self.next_bitacora_id = 10
        self.next_token_id = 10
        self.next_sucursal_id = 10
        self.next_cliente_id = 10
        self.next_vehiculo_id = 10
        self.next_cliente_vehiculo_id = 10

        self.mecanicos = {
            "V-12345678": {
                "cedula": "V-12345678",
                "cedula_mecanico": "V-12345678",
                "cedula_prefijo": "V",
                "nombre": "Carlos",
                "nombre_mecanico": "Carlos",
                "apellido": "Pérez",
                "apellido_mecanico": "Pérez",
                "telefono": "04141234567",
                "telefono_mecanico": "04141234567",
                "especialidad": "Frenos y Motor",
                "especialidad_mecanico": "Frenos y Motor",
                "foto_perfil": "default.png",
                "foto_perfil_mecanico": "default.png",
                "usuario_id": 1,
                "estado": 1,
                "created_at": "2026-01-01 10:00:00",
            },
            "V-87654321": {
                "cedula": "V-87654321",
                "cedula_mecanico": "V-87654321",
                "cedula_prefijo": "V",
                "nombre": "Andrés",
                "nombre_mecanico": "Andrés",
                "apellido": "Gómez",
                "apellido_mecanico": "Gómez",
                "telefono": "04129876543",
                "telefono_mecanico": "04129876543",
                "especialidad": "Suspensión y Alineación",
                "especialidad_mecanico": "Suspensión y Alineación",
                "foto_perfil": "default.png",
                "foto_perfil_mecanico": "default.png",
                "usuario_id": 2,
                "estado": 1,
                "created_at": "2026-01-01 10:00:00",
            },
            "V-11111111": {
                "cedula": "V-11111111",
                "cedula_mecanico": "V-11111111",
                "cedula_prefijo": "V",
                "nombre": "Mecánico",
                "nombre_mecanico": "Mecánico",
                "apellido": "Inactivo",
                "apellido_mecanico": "Inactivo",
                "telefono": "04160000000",
                "telefono_mecanico": "04160000000",
                "especialidad": "Electricidad",
                "especialidad_mecanico": "Electricidad",
                "foto_perfil": "default.png",
                "foto_perfil_mecanico": "default.png",
                "usuario_id": 3,
                "estado": 0,
                "created_at": "2026-01-01 10:00:00",
            }
        }

        self.sucursales = {
            1: {
                "id_sucursal": 1,
                "nombre_sucursal": "Sede Central",
                "direccion_sucursal": "Av. Intercomunal",
                "telefono_sucursal": "04141112233",
                "email_sucursal": "central@transalca.com",
                "estado": 1,
            },
            2: {
                "id_sucursal": 2,
                "nombre_sucursal": "Sede Norte",
                "direccion_sucursal": "Zona Industrial Norte",
                "telefono_sucursal": "04122223344",
                "email_sucursal": "norte@transalca.com",
                "estado": 1,
            },
            3: {
                "id_sucursal": 3,
                "nombre_sucursal": "Sede Inactiva",
                "direccion_sucursal": "Sector Centro",
                "telefono_sucursal": "04163334455",
                "email_sucursal": "inactiva@transalca.com",
                "estado": 0,
            },
        }

        self.categorias = {
            "Cauchos": {
                "nombre_categoria": "Cauchos",
                "descripcion_categoria": "Neumáticos y cauchos para vehículos",
                "imagen_categoria": "product-default-parts.png",
                "estado": 1,
            },
            "Baterías": {
                "nombre_categoria": "Baterías",
                "descripcion_categoria": "Baterías para autos y camionetas",
                "imagen_categoria": "product-default-parts.png",
                "estado": 1,
            },
            "Lubricantes": {
                "nombre_categoria": "Lubricantes",
                "descripcion_categoria": "Aceites de motor y fluidos",
                "imagen_categoria": "product-default-parts.png",
                "estado": 1,
            },
            "Inactiva": {
                "nombre_categoria": "Inactiva",
                "descripcion_categoria": "Categoría inactiva para pruebas",
                "imagen_categoria": "product-default-parts.png",
                "estado": 0,
            },
        }

        self.marcas = {
            "Pirelli": {
                "nombre_marca": "Pirelli",
                "descripcion_marca": "Neumáticos de alta gama",
                "estado": 1,
            },
            "Goodyear": {
                "nombre_marca": "Goodyear",
                "descripcion_marca": "Neumáticos de durabilidad",
                "estado": 1,
            },
            "Duncan": {
                "nombre_marca": "Duncan",
                "descripcion_marca": "Baterías selladas",
                "estado": 1,
            },
            "Marca Inactiva": {
                "nombre_marca": "Marca Inactiva",
                "descripcion_marca": "Marca desactivada",
                "estado": 0,
            },
        }

        self.productos = {
            "CAU-001": {
                "codigo": "CAU-001",
                "nombre_producto": "Caucho 185/65 R15",
                "descripcion_producto": "Caucho radial para turismo",
                "precio_producto": 65.00,
                "categoria": "Cauchos",
                "marca": "Pirelli",
                "imagen_producto": "default_product.png",
                "estado": 1,
            },
            "BAT-001": {
                "codigo": "BAT-001",
                "nombre_producto": "Batería 800 AMP",
                "descripcion_producto": "Batería sellada libre de mantenimiento",
                "precio_producto": 95.00,
                "categoria": "Baterías",
                "marca": "Duncan",
                "imagen_producto": "default_product.png",
                "estado": 1,
            },
            "PROD-INACTIVO": {
                "codigo": "PROD-INACTIVO",
                "nombre_producto": "Producto Inactivo",
                "descripcion_producto": "Desactivado para pruebas",
                "precio_producto": 10.00,
                "categoria": "Lubricantes",
                "marca": "Pirelli",
                "imagen_producto": "default_product.png",
                "estado": 0,
            },
        }

        self.stock = [
            {"producto_codigo": "CAU-001", "sucursal_id": 1, "stock": 10},
            {"producto_codigo": "CAU-001", "sucursal_id": 2, "stock": 5},
            {"producto_codigo": "BAT-001", "sucursal_id": 1, "stock": 8},
        ]

        self.servicios = {
            1: {
                "id": 1,
                "id_servicio": 1,
                "nombre": "Alineación Computarizada",
                "nombre_servicio": "Alineación Computarizada",
                "descripcion": "Alineación de tren delantero y trasero",
                "descripcion_servicio": "Alineación de tren delantero y trasero",
                "tipo": "alineacion",
                "tipo_servicio": "alineacion",
                "precio": 35.00,
                "precio_servicio": 35.00,
                "duracion_estimada": 60,
                "estado": 1,
            },
            2: {
                "id": 2,
                "id_servicio": 2,
                "nombre": "Balanceo Dinámico",
                "nombre_servicio": "Balanceo Dinámico",
                "descripcion": "Balanceo de neumáticos de 4 ruedas",
                "descripcion_servicio": "Balanceo de neumáticos de 4 ruedas",
                "tipo": "balanceo",
                "tipo_servicio": "balanceo",
                "precio": 20.00,
                "precio_servicio": 20.00,
                "duracion_estimada": 45,
                "estado": 1,
            },
            3: {
                "id": 3,
                "id_servicio": 3,
                "nombre": "Servicio Desactivado",
                "nombre_servicio": "Servicio Desactivado",
                "descripcion": "Inactivo para pruebas",
                "descripcion_servicio": "Inactivo para pruebas",
                "tipo": "general",
                "tipo_servicio": "general",
                "precio": 15.00,
                "precio_servicio": 15.00,
                "duracion_estimada": 30,
                "estado": 0,
            }
        }

        self.servicio_sucursal = [
            {"servicio_id": 1, "sucursal_id": 1, "estado": 1},
            {"servicio_id": 1, "sucursal_id": 2, "estado": 1},
            {"servicio_id": 2, "sucursal_id": 1, "estado": 1},
        ]

        self.clientes = {
            "V-87654321": {
                "id_cliente": 1,
                "identificador_cliente": "V-87654321",
                "nombre_cliente": "Juan",
                "apellido_cliente": "Pérez",
                "correo_cliente": "juan.perez@email.com",
                "telefono_cliente": "04121234567",
                "direccion_cliente": "Calle Central 10",
                "tipo_cliente": "natural",
                "usuario_id": 4,
                "id_natural": 1,
                "origen_registro": "admin",
                "estado": 1,
                "created_at": "2026-01-01 10:00:00",
            },
            "V-99999999": {
                "id_cliente": 2,
                "identificador_cliente": "V-99999999",
                "nombre_cliente": "María",
                "apellido_cliente": "González",
                "correo_cliente": "maria.gonzalez@email.com",
                "telefono_cliente": "04149999999",
                "direccion_cliente": "Av. Los Andes",
                "tipo_cliente": "natural",
                "usuario_id": None,
                "id_natural": 2,
                "origen_registro": "admin",
                "estado": 1,
                "created_at": "2026-01-01 10:00:00",
            },
            "J-123456789": {
                "id_cliente": 3,
                "identificador_cliente": "J-123456789",
                "nombre_cliente": "Transportes Venezuela C.A.",
                "apellido_cliente": "",
                "correo_cliente": "contacto@transven.com",
                "telefono_cliente": "02512223344",
                "direccion_cliente": "Zona Industrial",
                "tipo_cliente": "juridica",
                "usuario_id": None,
                "id_natural": None,
                "origen_registro": "admin",
                "estado": 1,
                "created_at": "2026-01-01 10:00:00",
            },
        }

        self.vehiculos = {
            "ABC123D": {
                "id_vehiculo": 1,
                "placa_vehiculo": "ABC123D",
                "marca_vehiculo": "Toyota",
                "modelo_vehiculo": "Corolla",
                "anio_vehiculo": 2020,
                "color_vehiculo": "Blanco",
                "tipo_vehiculo": "Sedan",
                "tipo_combustible": "gasolina",
                "kilometraje_actual": 45000,
                "observaciones_vehiculo": "En perfecto estado",
                "cliente_cedula": "V-87654321",
                "estado": 1,
                "created_at": "2026-01-01 10:00:00",
            },
            "XYZ789E": {
                "id_vehiculo": 2,
                "placa_vehiculo": "XYZ789E",
                "marca_vehiculo": "Ford",
                "modelo_vehiculo": "Focus",
                "anio_vehiculo": 2018,
                "color_vehiculo": "Azul",
                "tipo_vehiculo": "Hatchback",
                "tipo_combustible": "gasolina",
                "kilometraje_actual": 82000,
                "observaciones_vehiculo": "Servicios al día",
                "cliente_cedula": "V-99999999",
                "estado": 1,
                "created_at": "2026-01-01 10:00:00",
            },
        }

        self.cliente_vehiculo = [
            {"id_cliente_vehiculo": 1, "cliente_cedula": "V-87654321", "vehiculo_placa": "ABC123D", "estado": 1, "created_at": "2026-01-01 10:00:00"},
            {"id_cliente_vehiculo": 2, "cliente_cedula": "V-99999999", "vehiculo_placa": "XYZ789E", "estado": 1, "created_at": "2026-01-01 10:00:00"},
        ]

        self.bitacora_vehiculo = [
            {
                "id_bitacora_vehiculo": 1,
                "vehiculo_placa": "ABC123D",
                "descripcion_bitacora": "Servicio de alineación",
                "kilometraje": 40000,
                "aceite_usado": "10W40",
                "observaciones_bitacora": "Alineación ok",
                "cauchos_usados": "185/65 R15",
                "fecha_bitacora": "2026-08-15 14:00:00",
            }
        ]

        self.servicio_mecanico = {
            1: {
                "id": 1,
                "id_servicio_mecanico": 1,
                "servicio_id": 1,
                "mecanico_cedula": "V-12345678",
                "orden_venta_id": None,
                "observaciones_servicio": "Revisión inicial completada",
                "cliente_cedula": "V-87654321",
                "vehiculo_placa": "ABC123D",
                "estado_servicio": "en_proceso",
                "fecha_servicio": "2026-10-19T10:00:00",
            }
        }

        self.comisiones_mecanico = {
            1: {
                "id_comision": 1,
                "servicio_mecanico_id": 1,
                "precio_servicio_comision": 35.00,
                "porcentaje_comision": 20.0,
            }
        }

        self.proveedores = {
            "J-12345678-0": {
                "rif_proveedor": "J-12345678-0",
                "rif_prefijo": "J",
                "nombre_proveedor": "Distribuidora Repuestos Los Andes C.A.",
                "telefono_proveedor": "04121112233",
                "email_proveedor": "ventas@losandes.com",
                "direccion_proveedor": "Zona Industrial Castillito",
                "estado": 1,
            },
            "J-98765432-1": {
                "rif_proveedor": "J-98765432-1",
                "rif_prefijo": "J",
                "nombre_proveedor": "Importadora Global Auto C.A.",
                "telefono_proveedor": "04145556677",
                "email_proveedor": "contacto@globalauto.com",
                "direccion_proveedor": "Av. Principal Los Guayos",
                "estado": 1,
            }
        }

        self.next_orden_compra_id = 1
        self.ordenes_compra = {}
        self.detalle_orden_compra = []

        self.next_ticket_id = 1
        self.tickets_soporte = {}
        self.ticket_respuestas = []

        self.next_notif_id = 1
        self.notificaciones = []

        self.usuarios = {
            1: {
                "id": 1,
                "cedula": "V-10000000",
                "cedula_prefijo": "V",
                "nombre": "Admin",
                "apellido": "Transalca",
                "email": "admin@transalca.com",
                "password_hash": generate_password_hash("Admin123*"),
                "telefono": "04121112233",
                "direccion": "Av. Principal",
                "foto_perfil": "default.png",
                "tipo": "admin",
                "estado": 1,
                "created_at": "2026-01-01 10:00:00"
            },
            2: {
                "id": 2,
                "cedula": "V-20000000",
                "cedula_prefijo": "V",
                "nombre": "Operador",
                "apellido": "Sistema",
                "email": "operador@transalca.com",
                "password_hash": generate_password_hash("Operador123*"),
                "telefono": "04142223344",
                "direccion": "Sede Central",
                "foto_perfil": "default.png",
                "tipo": "empleado",
                "estado": 1,
                "created_at": "2026-01-01 10:00:00"
            },
            3: {
                "id": 3,
                "cedula": "V-30000000",
                "cedula_prefijo": "V",
                "nombre": "Usuario",
                "apellido": "Inactivo",
                "email": "inactivo@transalca.com",
                "password_hash": generate_password_hash("Inactivo123*"),
                "telefono": "04163334455",
                "direccion": "Calle 5",
                "foto_perfil": "default.png",
                "tipo": "empleado",
                "estado": 0,
                "created_at": "2026-01-01 10:00:00"
            },
            4: {
                "id": 4,
                "cedula": "V-40000000",
                "cedula_prefijo": "V",
                "nombre": "Cliente",
                "apellido": "Registrado",
                "email": "cliente@transalca.com",
                "password_hash": generate_password_hash("Cliente123*"),
                "telefono": "04164445566",
                "direccion": "Sector Centro",
                "foto_perfil": "default.png",
                "tipo": "cliente",
                "estado": 1,
                "created_at": "2026-01-01 10:00:00"
            }
        }

        self.roles = {
            1: {"id": 1, "nombre": "Administrador", "descripcion": "Acceso total", "estado": 1},
            2: {"id": 2, "nombre": "Operador", "descripcion": "Operaciones generales", "estado": 1},
            3: {"id": 3, "nombre": "Cliente", "descripcion": "Portal de clientes", "estado": 1},
            4: {"id": 4, "nombre": "Rol Inactivo", "descripcion": "Rol desactivado", "estado": 0},
        }

        self.usuario_rol = [
            {"usuario_id": 1, "rol_id": 1},
            {"usuario_id": 2, "rol_id": 2},
            {"usuario_id": 4, "rol_id": 3},
        ]

        self.modulos = {
            1: {
                "id": 1,
                "id_modulo": 1,
                "nombre": "modulos",
                "nombre_modulo": "modulos",
                "titulo": "Módulos",
                "titulo_modulo": "Módulos",
                "descripcion": "Gestión de módulos del sistema",
                "descripcion_modulo": "Gestión de módulos del sistema",
                "ruta": "/admin/modulos",
                "ruta_modulo": "/admin/modulos",
                "icono": "bi-grid",
                "icono_modulo": "bi-grid",
                "grupo": "Sistema",
                "grupo_modulo": "Sistema",
                "orden": 1,
                "orden_modulo": 1,
                "en_sidebar": 1,
                "publico": 0,
                "publico_modulo": 0,
                "estado": 1,
                "estado_modulo": 1,
            },
            2: {
                "id": 2,
                "id_modulo": 2,
                "nombre": "usuarios",
                "nombre_modulo": "usuarios",
                "titulo": "Usuarios",
                "titulo_modulo": "Usuarios",
                "descripcion": "Gestión de usuarios",
                "descripcion_modulo": "Gestión de usuarios",
                "ruta": "/admin/usuarios",
                "ruta_modulo": "/admin/usuarios",
                "icono": "bi-people",
                "icono_modulo": "bi-people",
                "grupo": "Seguridad",
                "grupo_modulo": "Seguridad",
                "orden": 2,
                "orden_modulo": 2,
                "en_sidebar": 1,
                "publico": 0,
                "publico_modulo": 0,
                "estado": 1,
                "estado_modulo": 1,
            },
            3: {
                "id": 3,
                "id_modulo": 3,
                "nombre": "roles",
                "nombre_modulo": "roles",
                "titulo": "Roles",
                "titulo_modulo": "Roles",
                "descripcion": "Gestión de roles y permisos",
                "descripcion_modulo": "Gestión de roles y permisos",
                "ruta": "/admin/roles",
                "ruta_modulo": "/admin/roles",
                "icono": "bi-shield-check",
                "icono_modulo": "bi-shield-check",
                "grupo": "Seguridad",
                "grupo_modulo": "Seguridad",
                "orden": 3,
                "orden_modulo": 3,
                "en_sidebar": 1,
                "publico": 0,
                "publico_modulo": 0,
                "estado": 1,
                "estado_modulo": 1,
            },
            4: {
                "id": 4,
                "id_modulo": 4,
                "nombre": "bitacora",
                "nombre_modulo": "bitacora",
                "titulo": "Bitácora",
                "titulo_modulo": "Bitácora",
                "descripcion": "Auditoría de eventos",
                "descripcion_modulo": "Auditoría de eventos",
                "ruta": "/admin/bitacora",
                "ruta_modulo": "/admin/bitacora",
                "icono": "bi-journal-text",
                "icono_modulo": "bi-journal-text",
                "grupo": "Auditoría",
                "grupo_modulo": "Auditoría",
                "orden": 4,
                "orden_modulo": 4,
                "en_sidebar": 1,
                "publico": 0,
                "publico_modulo": 0,
                "estado": 1,
                "estado_modulo": 1,
            },
            5: {
                "id": 5,
                "id_modulo": 5,
                "nombre": "catalogo_publico",
                "nombre_modulo": "catalogo_publico",
                "titulo": "Catálogo",
                "titulo_modulo": "Catálogo",
                "descripcion": "Catálogo de productos",
                "descripcion_modulo": "Catálogo de productos",
                "ruta": "/catalog",
                "ruta_modulo": "/catalog",
                "icono": "bi-shop",
                "icono_modulo": "bi-shop",
                "grupo": "General",
                "grupo_modulo": "General",
                "orden": 5,
                "orden_modulo": 5,
                "en_sidebar": 1,
                "publico": 1,
                "publico_modulo": 1,
                "estado": 1,
                "estado_modulo": 1,
            }
        }

        self.permisos = [
            {"id": 1, "rol_id": 1, "modulo": "modulos", "crear": 1, "leer": 1, "actualizar": 1, "eliminar": 1},
            {"id": 2, "rol_id": 1, "modulo": "usuarios", "crear": 1, "leer": 1, "actualizar": 1, "eliminar": 1},
            {"id": 3, "rol_id": 1, "modulo": "roles", "crear": 1, "leer": 1, "actualizar": 1, "eliminar": 1},
            {"id": 4, "rol_id": 1, "modulo": "bitacora", "crear": 1, "leer": 1, "actualizar": 1, "eliminar": 1},
            {"id": 5, "rol_id": 2, "modulo": "modulos", "crear": 0, "leer": 1, "actualizar": 0, "eliminar": 0},
            {"id": 6, "rol_id": 2, "modulo": "usuarios", "crear": 0, "leer": 1, "actualizar": 0, "eliminar": 0},
            {"id": 7, "rol_id": 2, "modulo": "roles", "crear": 0, "leer": 1, "actualizar": 0, "eliminar": 0},
            {"id": 8, "rol_id": 2, "modulo": "bitacora", "crear": 0, "leer": 1, "actualizar": 0, "eliminar": 0},
        ]

        self.tokens_recuperacion = {}

        self.bitacora = [
            {
                "id": 1,
                "usuario_id": 1,
                "accion": "LOGIN",
                "modulo": "AUTH",
                "descripcion": "Inicio de sesion: admin@transalca.com",
                "ip": "127.0.0.1",
                "fecha": "2026-10-19 10:00:00"
            },
            {
                "id": 2,
                "usuario_id": 2,
                "accion": "CREAR",
                "modulo": "USUARIOS",
                "descripcion": "Usuario creado",
                "ip": "127.0.0.1",
                "fecha": "2026-10-19 11:00:00"
            }
        ]

    def _is_mechanic_busy(self, cedula, exclude_id=None):
        cedula = (cedula or "").strip()
        if not cedula:
            return False
        for aid, item in self.servicio_mecanico.items():
            if exclude_id and int(aid) == int(exclude_id):
                continue
            if item.get("mecanico_cedula") == cedula and item.get("estado_servicio") in ("asignado", "en_proceso"):
                return True
        return False

    def _count_mechanic_services(self, cedula):
        return sum(1 for item in self.servicio_mecanico.values() if item.get("mecanico_cedula") == cedula)

    def _get_mechanic_dict(self, m):
        if not m:
            return None
        ced = m["cedula_mecanico"]
        busy = self._is_mechanic_busy(ced)
        return {
            "cedula": ced,
            "cedula_mecanico": ced,
            "cedula_prefijo": m.get("cedula_prefijo", "V"),
            "nombre": m["nombre_mecanico"],
            "nombre_mecanico": m["nombre_mecanico"],
            "apellido": m["apellido_mecanico"],
            "apellido_mecanico": m["apellido_mecanico"],
            "telefono": m.get("telefono_mecanico"),
            "telefono_mecanico": m.get("telefono_mecanico"),
            "especialidad": m.get("especialidad_mecanico"),
            "especialidad_mecanico": m.get("especialidad_mecanico"),
            "foto_perfil": m.get("foto_perfil_mecanico", "default.png"),
            "foto_perfil_mecanico": m.get("foto_perfil_mecanico", "default.png"),
            "usuario_id": m.get("usuario_id"),
            "estado": m.get("estado", 1),
            "created_at": m.get("created_at"),
            "estado_operativo": "Ocupado" if busy else "Disponible",
            "total_servicios": self._count_mechanic_services(ced),
        }

    def _get_service_dict(self, s):
        if not s:
            return None
        sid = s["id_servicio"]
        suc_links = [l["sucursal_id"] for l in self.servicio_sucursal if l["servicio_id"] == sid and l.get("estado", 1) == 1]
        suc_names = [self.sucursales[sc]["nombre_sucursal"] for sc in suc_links if sc in self.sucursales]
        return {
            "id": sid,
            "id_servicio": sid,
            "nombre": s["nombre_servicio"],
            "nombre_servicio": s["nombre_servicio"],
            "descripcion": s.get("descripcion_servicio", ""),
            "descripcion_servicio": s.get("descripcion_servicio", ""),
            "tipo": s.get("tipo_servicio", "general"),
            "tipo_servicio": s.get("tipo_servicio", "general"),
            "precio": float(s.get("precio_servicio", 0.0)),
            "precio_servicio": float(s.get("precio_servicio", 0.0)),
            "duracion_estimada": int(s.get("duracion_estimada", 60)),
            "estado": s.get("estado", 1),
            "sucursal_ids": ",".join(str(x) for x in suc_links) if suc_links else None,
            "sucursal_nombre": ", ".join(suc_names) if suc_names else None,
        }

    def _get_service_mechanic_dict(self, sm):
        if not sm:
            return None
        aid = sm["id_servicio_mecanico"]
        sid = sm.get("servicio_id")
        serv = self.servicios.get(sid, {})
        mced = sm.get("mecanico_cedula")
        mec = self.mecanicos.get(mced, {}) if mced else {}
        cced = sm.get("cliente_cedula")
        cli = self.clientes.get(cced, {}) if cced else {}
        vplaca = sm.get("vehiculo_placa")
        veh = self.vehiculos.get(vplaca, {}) if vplaca else {}
        com = self.comisiones_mecanico.get(aid, {})

        m_nom = (mec.get("nombre_mecanico") or "").strip()
        m_ape = (mec.get("apellido_mecanico") or "").strip()
        full_m = f"{m_nom} {m_ape}".strip()

        return {
            "id": aid,
            "id_servicio_mecanico": aid,
            "servicio_id": sid,
            "mecanico_cedula": mced,
            "orden_venta_id": sm.get("orden_venta_id"),
            "fecha": sm.get("fecha_servicio", "2026-10-19T10:00"),
            "fecha_servicio": sm.get("fecha_servicio", "2026-10-19T10:00"),
            "estado": sm.get("estado_servicio", "sin_asignar"),
            "estado_servicio": sm.get("estado_servicio", "sin_asignar"),
            "observaciones": sm.get("observaciones_servicio", ""),
            "observaciones_servicio": sm.get("observaciones_servicio", ""),
            "servicio_nombre": serv.get("nombre_servicio", ""),
            "precio": float(serv.get("precio_servicio", 0.0)),
            "cliente_cedula": cced,
            "vehiculo_placa": vplaca,
            "cliente_nombre": cli.get("nombre_cliente", ""),
            "cliente_apellido": cli.get("apellido_cliente", ""),
            "vehiculo_marca": veh.get("marca_vehiculo", ""),
            "vehiculo_modelo": veh.get("modelo_vehiculo", ""),
            "mecanico_nombre": full_m if full_m else "Sin asignar",
            "mecanico_nombre_base": m_nom or None,
            "mecanico_apellido_base": m_ape or None,
            "porcentaje_comision": com.get("porcentaje_comision"),
        }


    def _get_category_dict(self, cat):
        if not cat:
            return None
        nom = cat["nombre_categoria"]
        tot = sum(1 for p in self.productos.values() if p.get("categoria") == nom and p.get("estado") == 1)
        return {
            "nombre_categoria": nom,
            "nombre": nom,
            "descripcion_categoria": cat.get("descripcion_categoria", ""),
            "descripcion": cat.get("descripcion_categoria", ""),
            "imagen_categoria": cat.get("imagen_categoria", "product-default-parts.png"),
            "imagen": cat.get("imagen_categoria", "product-default-parts.png"),
            "estado": cat.get("estado", 1),
            "total_productos": tot,
        }

    def _get_brand_dict(self, b):
        if not b:
            return None
        nom = b["nombre_marca"]
        tot = sum(1 for p in self.productos.values() if p.get("marca") == nom and p.get("estado") == 1)
        return {
            "nombre_marca": nom,
            "nombre": nom,
            "descripcion_marca": b.get("descripcion_marca", ""),
            "descripcion": b.get("descripcion_marca", ""),
            "estado": b.get("estado", 1),
            "total_productos": tot,
        }

    def _get_sucursal_dict(self, s):
        if not s:
            return None
        sid = s["id_sucursal"]
        return {
            "id_sucursal": sid,
            "id": sid,
            "nombre_sucursal": s["nombre_sucursal"],
            "nombre": s["nombre_sucursal"],
            "direccion_sucursal": s.get("direccion_sucursal", ""),
            "direccion": s.get("direccion_sucursal", ""),
            "telefono_sucursal": s.get("telefono_sucursal", ""),
            "telefono": s.get("telefono_sucursal", ""),
            "email_sucursal": s.get("email_sucursal", ""),
            "email": s.get("email_sucursal", ""),
            "estado": s.get("estado", 1),
        }

    def _get_product_dict(self, p):
        if not p:
            return None
        cod = p["codigo"]
        cat_nom = p.get("categoria", "")
        cat = self.categorias.get(cat_nom, {})
        stock_entries = [st for st in self.stock if st.get("producto_codigo") == cod]
        stock_sum = sum(st.get("stock", 0) for st in stock_entries)
        suc_ids = [st["sucursal_id"] for st in stock_entries if st.get("sucursal_id") in self.sucursales]
        suc_names = [self.sucursales[sid]["nombre_sucursal"] for sid in suc_ids]
        return {
            "codigo": cod,
            "nombre_producto": p.get("nombre_producto", ""),
            "nombre": p.get("nombre_producto", ""),
            "descripcion_producto": p.get("descripcion_producto", ""),
            "descripcion": p.get("descripcion_producto", ""),
            "precio_producto": float(p.get("precio_producto", 0.0)),
            "precio": float(p.get("precio_producto", 0.0)),
            "categoria": cat_nom,
            "categoria_nombre": cat_nom,
            "categoria_imagen": cat.get("imagen_categoria", "product-default-parts.png"),
            "marca": p.get("marca", ""),
            "marca_nombre": p.get("marca", ""),
            "imagen_producto": p.get("imagen_producto", "default_product.png"),
            "imagen": p.get("imagen_producto", "default_product.png"),
            "estado": p.get("estado", 1),
            "stock": stock_sum,
            "sucursal_ids": ",".join(str(x) for x in suc_ids) if suc_ids else None,
            "sucursal_nombre": ", ".join(suc_names) if suc_names else "Sin stock",
        }

    def _get_vehicle_dict(self, v):
        if not v:
            return None
        placa = v["placa_vehiculo"]
        links = [cv for cv in self.cliente_vehiculo if cv.get("vehiculo_placa") == placa and cv.get("estado", 1) == 1]
        c_names = []
        c_apellidos = []
        c_telefonos = []
        c_emails = []
        c_cedulas = []
        for l in links:
            ced = l.get("cliente_cedula")
            cli = self.clientes.get(ced, {})
            if cli:
                c_names.append(cli.get("nombre_cliente", ""))
                c_apellidos.append(cli.get("apellido_cliente", ""))
                c_telefonos.append(cli.get("telefono_cliente", ""))
                c_emails.append(cli.get("correo_cliente", ""))
                c_cedulas.append(ced)
        return {
            "id": placa,
            "id_vehiculo": v.get("id_vehiculo", 1),
            "placa": placa,
            "placa_vehiculo": placa,
            "marca": v.get("marca_vehiculo", ""),
            "marca_vehiculo": v.get("marca_vehiculo", ""),
            "modelo": v.get("modelo_vehiculo", ""),
            "modelo_vehiculo": v.get("modelo_vehiculo", ""),
            "anio": v.get("anio_vehiculo"),
            "anio_vehiculo": v.get("anio_vehiculo"),
            "color": v.get("color_vehiculo", ""),
            "color_vehiculo": v.get("color_vehiculo", ""),
            "tipo_vehiculo": v.get("tipo_vehiculo", ""),
            "tipo_combustible": v.get("tipo_combustible", "gasolina"),
            "kilometraje_actual": v.get("kilometraje_actual", 0),
            "observaciones": v.get("observaciones_vehiculo", ""),
            "observaciones_vehiculo": v.get("observaciones_vehiculo", ""),
            "cauchos_json": "[]",
            "cliente_nombre": ", ".join(c_names) if c_names else "-",
            "cliente_apellido": ", ".join(c_apellidos) if c_apellidos else "",
            "cliente_telefono": ", ".join(c_telefonos) if c_telefonos else "",
            "cliente_email": ", ".join(c_emails) if c_emails else "",
            "cliente_cedula": ",".join(c_cedulas) if c_cedulas else (v.get("cliente_cedula") or ""),
            "estado": v.get("estado", 1),
            "created_at": v.get("created_at", "2026-01-01 10:00:00"),
        }

    def _get_client_dict(self, cli):
        if not cli:
            return None
        ced = cli["identificador_cliente"]
        v_count = sum(1 for cv in self.cliente_vehiculo if cv.get("cliente_cedula") == ced and cv.get("estado", 1) == 1 and self.vehiculos.get(cv.get("vehiculo_placa"), {}).get("estado", 1) == 1)
        return {
            "id_cliente": cli.get("id_cliente", 1),
            "identificador_cliente": ced,
            "cedula": ced,
            "nombre_cliente": cli.get("nombre_cliente", ""),
            "nombre": cli.get("nombre_cliente", ""),
            "apellido_cliente": cli.get("apellido_cliente", ""),
            "apellido": cli.get("apellido_cliente", ""),
            "correo_cliente": cli.get("correo_cliente", ""),
            "email": cli.get("correo_cliente", ""),
            "telefono_cliente": cli.get("telefono_cliente", ""),
            "telefono": cli.get("telefono_cliente", ""),
            "direccion_cliente": cli.get("direccion_cliente", ""),
            "direccion": cli.get("direccion_cliente", ""),
            "tipo_cliente": cli.get("tipo_cliente", "natural"),
            "usuario_id": cli.get("usuario_id"),
            "id_natural": cli.get("id_natural", 1),
            "origen_registro": cli.get("origen_registro", "admin"),
            "estado": cli.get("estado", 1),
            "vehiculos_count": v_count,
            "created_at": cli.get("created_at", "2026-01-01 10:00:00"),
            "updated_at": cli.get("updated_at", "2026-01-01 10:00:00"),
        }

    def _get_supplier_dict(self, p):
        if not p:
            return None
        rif = p["rif_proveedor"]
        tot = sum(1 for oc in self.ordenes_compra.values() if oc.get("proveedor_rif") == rif)
        return {
            "id": rif,
            "rif_proveedor": rif,
            "rif": rif,
            "rif_prefijo": p.get("rif_prefijo", "J"),
            "nombre_proveedor": p["nombre_proveedor"],
            "nombre": p["nombre_proveedor"],
            "telefono_proveedor": p.get("telefono_proveedor", ""),
            "telefono": p.get("telefono_proveedor", ""),
            "email_proveedor": p.get("email_proveedor", ""),
            "email": p.get("email_proveedor", ""),
            "direccion_proveedor": p.get("direccion_proveedor", ""),
            "direccion": p.get("direccion_proveedor", ""),
            "estado": p.get("estado", 1),
            "total_ordenes": tot,
        }

    def _get_ticket_dict(self, t):
        if not t:
            return None
        tid = t["id_ticket_soporte"]
        ced = t.get("cliente_cedula", "")
        cli = self.clientes.get(ced, {})
        vplaca = t.get("referencia_id") if t.get("referencia_tipo") == "vehiculo" else None
        veh = self.vehiculos.get(vplaca, {}) if vplaca else {}
        responses = [dict(r) for r in self.ticket_respuestas if r.get("ticket_id") == tid]
        return {
            "id": tid,
            "id_ticket_soporte": tid,
            "cliente_cedula": ced,
            "asunto": t.get("asunto", ""),
            "descripcion": t.get("descripcion_ticket_soporte", ""),
            "descripcion_ticket_soporte": t.get("descripcion_ticket_soporte", ""),
            "prioridad": t.get("prioridad_ticket", "media"),
            "prioridad_ticket": t.get("prioridad_ticket", "media"),
            "estado": t.get("estado", "abierto"),
            "referencia_tipo": t.get("referencia_tipo", "general"),
            "referencia_id": t.get("referencia_id"),
            "cliente_nombre": cli.get("nombre_cliente", ""),
            "cliente_apellido": cli.get("apellido_cliente", ""),
            "cliente_telefono": cli.get("telefono_cliente", ""),
            "cliente_email": cli.get("correo_cliente", ""),
            "vehiculo_placa": vplaca,
            "vehiculo_marca": veh.get("marca_vehiculo", ""),
            "vehiculo_modelo": veh.get("modelo_vehiculo", ""),
            "producto_nombre": None,
            "servicio_nombre": None,
            "respuestas": responses,
            "created_at": t.get("created_at", "2026-10-19 12:00:00"),
        }

    def fetch_one(self, db, sql, params=None):
        sql_upper = sql.upper().strip()
        params = params or ()

        if "FROM USUARIOS" in sql_upper:
            if "COUNT(*)" in sql_upper and "ADMINISTRADOR" in sql_upper:
                admin_role_id = 1
                admin_count = sum(1 for ur in self.usuario_rol if ur["rol_id"] == admin_role_id and self.usuarios.get(ur["usuario_id"], {}).get("estado") == 1)
                return {"total": admin_count}
            if "WHERE ID = %S" in sql_upper or "WHERE U.ID = %S" in sql_upper:
                uid = int(params[0])
                u = self.usuarios.get(uid)
                return dict(u) if u else None
            if "WHERE CEDULA = %S" in sql_upper:
                ced = params[0].strip().upper()
                excl_id = int(params[1]) if "AND ID != %S" in sql_upper and len(params) > 1 else None
                for u in self.usuarios.values():
                    if u.get("cedula", "").strip().upper() == ced:
                        if "ESTADO = 1" in sql_upper and u.get("estado") != 1:
                            continue
                        if excl_id is not None and u.get("id") == excl_id:
                            continue
                        return dict(u)
                return None
            if "EMAIL" in sql_upper:
                em = params[0].strip().lower()
                for u in self.usuarios.values():
                    if u.get("email", "").strip().lower() == em:
                        if "AND ID != %S" in sql_upper and len(params) > 1 and str(u.get("id")) == str(params[1]):
                            continue
                        if "AND CEDULA != %S" in sql_upper and len(params) > 1 and str(u.get("cedula")) == str(params[1]):
                            continue
                        return dict(u)
                return None

        if "FROM ROLES" in sql_upper:
            if "WHERE NOMBRE = %S AND ESTADO = 1" in sql_upper:
                nom = params[0].strip().lower()
                for r in self.roles.values():
                    if r["nombre"].strip().lower() == nom and r.get("estado") == 1:
                        return dict(r)
                return None
            if "WHERE NOMBRE = %S" in sql_upper:
                nom = params[0].strip().lower()
                for r in self.roles.values():
                    if r["nombre"].strip().lower() == nom:
                        return dict(r)
                return None
            if "WHERE ID = %S AND ESTADO = 1" in sql_upper:
                rid = int(params[0])
                r = self.roles.get(rid)
                return dict(r) if (r and r.get("estado") == 1) else None
            if "WHERE ID = %S" in sql_upper:
                rid = int(params[0])
                r = self.roles.get(rid)
                return dict(r) if r else None

        if "FROM USUARIO_ROL" in sql_upper:
            if "COUNT(*)" in sql_upper and "ADMINISTRADOR" in sql_upper:
                admin_count = sum(1 for ur in self.usuario_rol if ur["rol_id"] == 1 and self.usuarios.get(ur["usuario_id"], {}).get("estado") == 1)
                return {"total": admin_count}
            if "ADMINISTRADOR" in sql_upper:
                uid = int(params[0])
                for ur in self.usuario_rol:
                    if ur["usuario_id"] == uid and ur["rol_id"] == 1:
                        return {"id": ur.get("id", 1)}
                return None
            if "WHERE USUARIO_ID = %S AND ROL_ID = %S" in sql_upper:
                uid, rid = int(params[0]), int(params[1])
                for ur in self.usuario_rol:
                    if ur["usuario_id"] == uid and ur["rol_id"] == rid:
                        return {"id": ur.get("id", 1)}
                return None

        if "FROM PERMISOS" in sql_upper:
            if "WHERE ROL_ID = %S AND MODULO = %S" in sql_upper:
                rid, mod = int(params[0]), params[1]
                for p in self.permisos:
                    if p["rol_id"] == rid and p["modulo"] == mod:
                        return dict(p)
                return None

        if "FROM TOKENS_RECUPERACION" in sql_upper:
            tok = params[0]
            for t in self.tokens_recuperacion.values():
                if t["token"] == tok and t["usado"] == 0:
                    return dict(t)
            return None

        if "COUNT(*)" in sql_upper and "BITACORA" in sql_upper:
            return {"total": len(self.bitacora)}

        if "FROM MODULOS" in sql_upper:
            if "WHERE ID_MODULO = %S" in sql_upper:
                mid = int(params[0])
                m = self.modulos.get(mid)
                return dict(m) if m else None
            if "WHERE NOMBRE_MODULO = %S AND ID_MODULO != %S" in sql_upper:
                nom, excl_id = params[0].strip().lower(), int(params[1])
                for mid, m in self.modulos.items():
                    if m["nombre_modulo"].strip().lower() == nom and mid != excl_id and m.get("estado_modulo") == 1:
                        return {"id_modulo": mid}
                return None
            if "WHERE NOMBRE_MODULO = %S" in sql_upper:
                nom = params[0].strip().lower()
                for mid, m in self.modulos.items():
                    if m["nombre_modulo"].strip().lower() == nom:
                        if "ESTADO_MODULO = 1" in sql_upper and m.get("estado_modulo") != 1:
                            continue
                        return dict(m)
                return None
            if "WHERE RUTA_MODULO = %S AND ID_MODULO != %S" in sql_upper:
                ruta, excl_id = params[0].strip().lower(), int(params[1])
                for mid, m in self.modulos.items():
                    if m.get("ruta_modulo", "").strip().lower() == ruta and mid != excl_id and m.get("estado_modulo") == 1:
                        return {"id_modulo": mid}
                return None
            if "WHERE RUTA_MODULO = %S" in sql_upper:
                ruta = params[0].strip().lower()
                for mid, m in self.modulos.items():
                    if m.get("ruta_modulo", "").strip().lower() == ruta:
                        if "ESTADO_MODULO = 1" in sql_upper and m.get("estado_modulo") != 1:
                            continue
                        return dict(m)
                return None

        if "FROM MECANICOS" in sql_upper:
            if "M.CEDULA_MECANICO = %S" in sql_upper:
                ced = params[0]
                m = self.mecanicos.get(ced)
                return self._get_mechanic_dict(m) if m else None
            if "CEDULA_MECANICO != %S" in sql_upper and "ESTADO = 1" in sql_upper:
                ced, excl = params[0], params[1]
                for c, m in self.mecanicos.items():
                    if c == ced and c != excl and m.get("estado") == 1:
                        return {"cedula_mecanico": c}
                return None
            if "WHERE CEDULA_MECANICO = %S AND ESTADO = 1" in sql_upper:
                ced = params[0]
                m = self.mecanicos.get(ced)
                if m and m.get("estado") == 1:
                    return {"cedula_mecanico": ced}
                return None
            if "WHERE CEDULA_MECANICO = %S" in sql_upper:
                ced = params[0]
                m = self.mecanicos.get(ced)
                return self._get_mechanic_dict(m) if m else None

        if "FROM SERVICIOS" in sql_upper:
            if "S.ID_SERVICIO = %S" in sql_upper:
                sid = int(params[0])
                s = self.servicios.get(sid)
                return self._get_service_dict(s) if s else None
            if "NOMBRE_SERVICIO = %S" in sql_upper and "ID_SERVICIO != %S" in sql_upper:
                nom, excl_id = params[0], int(params[1])
                for sid, s in self.servicios.items():
                    if s.get("nombre_servicio", "").strip().lower() == nom.strip().lower() and sid != excl_id and s.get("estado") == 1:
                        return {"id_servicio": sid}
                return None
            if "WHERE NOMBRE_SERVICIO = %S AND ESTADO = 1" in sql_upper or "WHERE S.NOMBRE_SERVICIO = %S" in sql_upper:
                nom = params[0]
                for sid, s in self.servicios.items():
                    if s.get("nombre_servicio", "").strip().lower() == nom.strip().lower():
                        if "ESTADO = 1" in sql_upper and s.get("estado") != 1:
                            continue
                        return self._get_service_dict(s)
                return None
            if "WHERE ID_SERVICIO = %S AND ESTADO = 1" in sql_upper:
                sid = int(params[0])
                s = self.servicios.get(sid)
                if s and s.get("estado") == 1:
                    return {"id_servicio": sid}
                return None

        if "FROM CATEGORIAS" in sql_upper:
            if "WHERE NOMBRE_CATEGORIA = %S" in sql_upper or "WHERE C.NOMBRE_CATEGORIA = %S" in sql_upper:
                nom = params[0].strip()
                cat = self.categorias.get(nom)
                if cat:
                    if "ESTADO = 1" in sql_upper and cat.get("estado") != 1:
                        return None
                    return self._get_category_dict(cat)
                return None

        if "FROM MARCAS" in sql_upper:
            if "WHERE NOMBRE_MARCA = %S" in sql_upper or "WHERE M.NOMBRE_MARCA = %S" in sql_upper:
                nom = params[0].strip()
                m = self.marcas.get(nom)
                if m:
                    if "ESTADO = 1" in sql_upper and m.get("estado") != 1:
                        return None
                    return self._get_brand_dict(m)
                return None

        if "FROM SUCURSALES" in sql_upper:
            if "LOWER(EMAIL_SUCURSAL) = %S" in sql_upper:
                em = params[0].strip().lower()
                excl = int(params[1]) if "AND ID_SUCURSAL != %S" in sql_upper and len(params) > 1 and params[1] is not None else None
                for s in self.sucursales.values():
                    if s.get("email_sucursal", "").strip().lower() == em and s.get("estado") == 1:
                        if excl and s.get("id_sucursal") == excl:
                            continue
                        return {"id_sucursal": s["id_sucursal"]}
                return None
            if "WHERE NOMBRE_SUCURSAL = %S" in sql_upper or "WHERE S.NOMBRE_SUCURSAL = %S" in sql_upper:
                nom = params[0].strip().lower()
                excl = None
                if ("AND ID_SUCURSAL != %S" in sql_upper or "AND S.ID_SUCURSAL != %S" in sql_upper) and len(params) > 1 and params[1] is not None:
                    try:
                        excl = int(params[1])
                    except (ValueError, TypeError):
                        excl = params[1]
                for s in self.sucursales.values():
                    if s.get("nombre_sucursal", "").strip().lower() == nom:
                        if "ESTADO = 1" in sql_upper and s.get("estado") != 1:
                            continue
                        if excl and (s.get("id_sucursal") == excl or s.get("nombre_sucursal") == excl):
                            continue
                        return {"id_sucursal": s["id_sucursal"]}
                return None
            if "ID_SUCURSAL = %S" in sql_upper:
                sc_id = int(params[0])
                sc = self.sucursales.get(sc_id)
                if sc:
                    if "ESTADO = 1" in sql_upper and sc.get("estado") != 1:
                        return None
                    return self._get_sucursal_dict(sc)
                return None

        if "FROM PRODUCTOS" in sql_upper:
            if "COUNT(DISTINCT" in sql_upper:
                active_prods = [p for p in self.productos.values() if p.get("estado") == 1]
                return {"total": len(active_prods)}
            if "WHERE CODIGO = %S" in sql_upper or "WHERE P.CODIGO = %S" in sql_upper:
                cod = params[0].strip().upper()
                excl = params[1].strip().upper() if ("AND CODIGO != %S" in sql_upper or "AND P.CODIGO != %S" in sql_upper) and len(params) > 1 and params[1] else None
                p = self.productos.get(cod)
                if p:
                    if excl and cod == excl:
                        return None
                    if "ESTADO = 1" in sql_upper and p.get("estado") != 1:
                        return None
                    return self._get_product_dict(p)
                return None

        if "FROM STOCK" in sql_upper:
            if "WHERE PRODUCTO_CODIGO = %S AND SUCURSAL_ID = %S" in sql_upper:
                cod, sid = params[0].strip().upper(), int(params[1])
                for st in self.stock:
                    if st.get("producto_codigo") == cod and int(st.get("sucursal_id")) == sid:
                        return {"1": 1, "stock": st.get("stock", 0)}
                return None

        if "FROM CLIENTE_VEHICULO" in sql_upper:
            if "WHERE CLIENTE_CEDULA = %S AND VEHICULO_PLACA = %S" in sql_upper or "WHERE CLIENTE_CEDULA=%S AND VEHICULO_PLACA=%S" in sql_upper:
                cced, vplaca = params[0].strip().upper(), params[1].strip().upper()
                for cv in self.cliente_vehiculo:
                    if cv.get("cliente_cedula", "").strip().upper() == cced and cv.get("vehiculo_placa", "").strip().upper() == vplaca:
                        if "ESTADO = 1" in sql_upper and cv.get("estado", 1) != 1:
                            continue
                        return {"id": cv.get("id_cliente_vehiculo", 1), "id_cliente_vehiculo": cv.get("id_cliente_vehiculo", 1), "estado": cv.get("estado", 1)}
                return None

        if "FROM CLIENTE " in sql_upper or "FROM CLIENTE\n" in sql_upper or "FROM CLIENTE\r" in sql_upper:
            if "COUNT(*)" in sql_upper:
                active_c = sum(1 for c in self.clientes.values() if c.get("estado", 1) == 1 and c.get("identificador_cliente") != "V-00000000")
                total_c = sum(1 for c in self.clientes.values() if c.get("identificador_cliente") != "V-00000000")
                if "ESTADO=1" in sql_upper or "ESTADO = 1" in sql_upper:
                    return {"total": active_c}
                return {"total": total_c}
            if "WHERE LOWER(CORREO_CLIENTE)" in sql_upper or "WHERE CORREO_CLIENTE" in sql_upper or "C.CORREO_CLIENTE = %S" in sql_upper:
                em = params[0].strip().lower()
                excl = params[1] if ("AND IDENTIFICADOR_CLIENTE != %S" in sql_upper or "AND C.IDENTIFICADOR_CLIENTE != %S" in sql_upper) and len(params) > 1 and params[1] else None
                for c in self.clientes.values():
                    if c.get("correo_cliente", "").strip().lower() == em:
                        if "ESTADO = 1" in sql_upper and c.get("estado", 1) != 1:
                            continue
                        if excl and c.get("identificador_cliente") == excl:
                            continue
                        return {"id_cliente": c.get("id_cliente"), "identificador_cliente": c.get("identificador_cliente")}
                return None
            ced = params[0].strip().upper() if params else ""
            cli = self.clientes.get(ced)
            if not cli:
                for c in self.clientes.values():
                    if c.get("identificador_cliente", "").strip().upper() == ced or str(c.get("id_cliente")) == str(ced):
                        cli = c
                        break
            if cli:
                if "ESTADO = 1" in sql_upper and cli.get("estado", 1) != 1:
                    return None
                return self._get_client_dict(cli)
            return None

        if "FROM VEHICULOS" in sql_upper:
            placa = params[0].strip().upper() if params else ""
            excl = params[1].strip().upper() if ("AND PLACA_VEHICULO != %S" in sql_upper or "AND PLACA_VEHICULO!=%S" in sql_upper) and len(params) > 1 else None
            if excl and placa == excl:
                return None
            veh = self.vehiculos.get(placa)
            if veh:
                if "ESTADO = 1" in sql_upper and veh.get("estado", 1) != 1:
                    return None
                return self._get_vehicle_dict(veh)
            return None

        if "FROM SERVICIO_MECANICO" in sql_upper:
            if "ESTADO_SERVICIO IN ('ASIGNADO', 'EN_PROCESO')" in sql_upper:
                ced = params[0]
                excl = params[1] if len(params) > 1 else None
                if self._is_mechanic_busy(ced, exclude_id=excl):
                    return {"is_busy": 1}
                return None
            if "WHERE SM.ID_SERVICIO_MECANICO = %S" in sql_upper:
                aid = int(params[0])
                sm = self.servicio_mecanico.get(aid)
                return self._get_service_mechanic_dict(sm) if sm else None

        if "FROM COMISIONES_MECANICO" in sql_upper:
            if "SERVICIO_MECANICO_ID = %S" in sql_upper:
                cid = int(params[0])
                c = self.comisiones_mecanico.get(cid)
                if c:
                    return {
                        **c,
                        "monto_comision": round(c["precio_servicio_comision"] * (c["porcentaje_comision"] / 100), 2)
                    }
        if "FROM PROVEEDORES" in sql_upper:
            if "WHERE LOWER(EMAIL_PROVEEDOR) = %S" in sql_upper or "WHERE EMAIL_PROVEEDOR = %S" in sql_upper:
                em = params[0].strip().lower()
                excl = params[1] if ("AND RIF_PROVEEDOR != %S" in sql_upper or "AND P.RIF_PROVEEDOR != %S" in sql_upper) and len(params) > 1 and params[1] else None
                for p in self.proveedores.values():
                    if p.get("email_proveedor", "").strip().lower() == em:
                        if "ESTADO = 1" in sql_upper and p.get("estado", 1) != 1:
                            continue
                        if excl and p.get("rif_proveedor") == excl:
                            continue
                        return {"rif_proveedor": p.get("rif_proveedor")}
                return None
            if "WHERE RIF_PROVEEDOR = %S" in sql_upper or "WHERE P.RIF_PROVEEDOR = %S" in sql_upper or "WHERE RIF_PROVEEDOR=%S" in sql_upper:
                rif = params[0].strip().upper()
                excl = params[1] if ("AND RIF_PROVEEDOR != %S" in sql_upper or "AND P.RIF_PROVEEDOR != %S" in sql_upper) and len(params) > 1 and params[1] else None
                if excl and rif == excl:
                    return None
                p = self.proveedores.get(rif)
                if p:
                    if "ESTADO = 1" in sql_upper and p.get("estado", 1) != 1:
                        return None
                    return self._get_supplier_dict(p)
                return None

        if "FROM ORDENES_COMPRA" in sql_upper:
            if "COUNT(*) AS TOTAL" in sql_upper:
                total = len(self.ordenes_compra)
                pendientes = sum(1 for o in self.ordenes_compra.values() if o.get("estado") == "pendiente")
                comprados = sum(1 for o in self.ordenes_compra.values() if o.get("estado") == "comprado")
                total_inv = sum(float(o.get("total_orden_compra", 0)) for o in self.ordenes_compra.values() if o.get("estado") == "comprado")
                return {"total": total, "pendientes": pendientes, "comprados": comprados, "total_invertido": total_inv}
            if "WHERE ID_ORDEN_COMPRA = %S" in sql_upper or "WHERE OC.ID_ORDEN_COMPRA = %S" in sql_upper:
                oid = int(params[0])
                o = self.ordenes_compra.get(oid)
                if o:
                    prif = o.get("proveedor_rif")
                    prov = self.proveedores.get(prif, {})
                    sid = o.get("sucursal_id")
                    suc = self.sucursales.get(sid, {})
                    return {
                        **o,
                        "id": oid,
                        "fecha": o.get("fecha_orden_compra", "2026-10-19T12:00:00"),
                        "total": float(o.get("total_orden_compra", 0.0)),
                        "observaciones": o.get("observaciones_orden_compra", ""),
                        "proveedor_nombre": prov.get("nombre_proveedor", ""),
                        "proveedor_telefono": prov.get("telefono_proveedor", ""),
                        "proveedor_email": prov.get("email_proveedor", ""),
                        "proveedor_direccion": prov.get("direccion_proveedor", ""),
                        "sucursal_nombre": suc.get("nombre_sucursal", ""),
                        "sucursal_direccion": suc.get("direccion_sucursal", ""),
                    }
                return None

        if "FROM TICKETS_SOPORTE" in sql_upper:
            if "COUNT(*) AS TOTAL" in sql_upper:
                ced = params[0].strip().upper() if params else ""
                tot = sum(1 for t in self.tickets_soporte.values() if t.get("cliente_cedula", "").strip().upper() == ced and t.get("estado") not in ("resuelto", "cerrado"))
                return {"total": tot}
            if "WHERE ID_TICKET_SOPORTE = %S" in sql_upper or "WHERE T.ID_TICKET_SOPORTE = %S" in sql_upper:
                tid = int(params[0])
                t = self.tickets_soporte.get(tid)
                if t:
                    return self._get_ticket_dict(t)
                return None

        if "FROM USUARIOS" in sql_upper and ("WHERE CEDULA = %S" in sql_upper or "WHERE CEDULA=%S" in sql_upper):
            ced = params[0].strip().upper()
            for u in self.usuarios.values():
                if u.get("cedula", "").strip().upper() == ced:
                    return {"id": u["id"], "nombre": u.get("nombre", ""), "apellido": u.get("apellido", "")}
            cli = self.clientes.get(ced)
            if cli and cli.get("usuario_id") in self.usuarios:
                u = self.usuarios[cli["usuario_id"]]
                return {"id": u["id"], "nombre": u.get("nombre", ""), "apellido": u.get("apellido", "")}
            return None

        if "FROM NOTIFICACIONES" in sql_upper:
            if "COUNT(*) AS TOTAL" in sql_upper or "COUNT(*)" in sql_upper:
                if len(params) >= 2:
                    uid = int(params[0]) if params[0] is not None else None
                    ced = str(params[1]).strip().upper() if params[1] else None
                    tot = sum(1 for n in self.notificaciones if n.get("leida", 0) == 0 and (
                        (uid is not None and n.get("usuario_id") == uid) or
                        (ced is not None and str(n.get("cliente_cedula") or "").strip().upper() == ced)
                    ))
                    return {"total": tot}
                elif len(params) == 1:
                    uid = int(params[0]) if params[0] is not None else None
                    tot = sum(1 for n in self.notificaciones if n.get("leida", 0) == 0 and n.get("usuario_id") == uid)
                    return {"total": tot}
            if "SELECT ID_NOTIFICACION" in sql_upper:
                return None

        return None

    def fetch_all(self, db, sql, params=None):
        sql_upper = sql.upper().strip()
        params = params or ()

        if "SHOW COLUMNS FROM USUARIOS" in sql_upper:
            cols = ["id", "cedula", "cedula_prefijo", "nombre", "apellido", "email", "telefono", "direccion", "password_hash", "foto_perfil", "tipo", "estado", "created_at"]
            return [{"Field": c} for c in cols]

        if "FROM USUARIOS" in sql_upper:
            if "GROUP_CONCAT(R.NOMBRE)" in sql_upper or "WHERE U.ESTADO = 1" in sql_upper:
                tipo_filter = params[0] if params else None
                res = []
                for uid, u in self.usuarios.items():
                    if u.get("estado") != 1:
                        continue
                    if tipo_filter and u.get("tipo") != tipo_filter:
                        continue
                    r_names = [self.roles[ur["rol_id"]]["nombre"] for ur in self.usuario_rol if ur["usuario_id"] == uid and ur["rol_id"] in self.roles]
                    res.append({
                        **u,
                        "roles": ",".join(r_names) if r_names else "Sin rol"
                    })
                res.sort(key=lambda x: x["id"], reverse=True)
                return res
            if "DISTINCT U.ID" in sql_upper or "P.MODULO = %S" in sql_upper:
                mod = params[0] if params else "notificaciones"
                admin_uids = []
                for ur in self.usuario_rol:
                    uid = ur["usuario_id"]
                    rid = ur["rol_id"]
                    if any(p.get("rol_id") == rid and p.get("modulo") == mod and p.get("leer") == 1 for p in self.permisos):
                        if uid not in admin_uids and self.usuarios.get(uid, {}).get("estado") == 1:
                            admin_uids.append(uid)
                if not admin_uids:
                    admin_uids = [1]
                return [{"id": uid} for uid in admin_uids]
            if "LIKE" in sql_upper:
                q = params[0].replace("%", "").strip().lower()
                res = []
                for u in self.usuarios.values():
                    if q in u.get("nombre", "").lower() or q in u.get("apellido", "").lower() or q in u.get("email", "").lower() or q in u.get("cedula", "").lower():
                        res.append(dict(u))
                return res

        if "FROM ROLES" in sql_upper:
            if "WHERE UR.USUARIO_ID = %S" in sql_upper:
                uid = int(params[0])
                role_ids = [ur["rol_id"] for ur in self.usuario_rol if ur["usuario_id"] == uid]
                return [dict(self.roles[rid]) for rid in role_ids if rid in self.roles]
            if "WHERE ESTADO = 1" in sql_upper or "ORDER BY ID" in sql_upper:
                res = [dict(r) for r in self.roles.values() if r.get("estado") == 1]
                res.sort(key=lambda x: x["id"])
                return res

        if "FROM PERMISOS" in sql_upper:
            if "WHERE UR.USUARIO_ID = %S" in sql_upper:
                uid = int(params[0])
                user_role_ids = [ur["rol_id"] for ur in self.usuario_rol if ur["usuario_id"] == uid]
                res = []
                for p in self.permisos:
                    if p["rol_id"] in user_role_ids:
                        res.append(dict(p))
                return res
            if "WHERE ROL_ID = %S" in sql_upper:
                rid = int(params[0])
                return [dict(p) for p in self.permisos if p["rol_id"] == rid]

        if "FROM MODULOS" in sql_upper:
            if "EN_SIDEBAR = 1" in sql_upper:
                res = [dict(m) for m in self.modulos.values() if m.get("estado_modulo") == 1 and m.get("en_sidebar") == 1]
                res.sort(key=lambda x: (x.get("orden_modulo", 0), x.get("titulo_modulo", "")))
                return res
            if "WHERE ESTADO_MODULO = 1" in sql_upper:
                res = [dict(m) for m in self.modulos.values() if m.get("estado_modulo") == 1]
                res.sort(key=lambda x: (x.get("grupo_modulo", ""), x.get("orden_modulo", 0), x.get("titulo_modulo", "")))
                return res

        if "FROM BITACORA " in sql_upper or "FROM BITACORA\n" in sql_upper or "FROM BITACORA B" in sql_upper:
            limit = 100
            offset = 0
            user_filter = None
            mod_filter = None
            search_query = None

            date_range = None
            if "WHERE B.USUARIO_ID = %S" in sql_upper:
                user_filter = int(params[0])
                limit = int(params[1]) if len(params) > 1 else 100
            elif "WHERE B.MODULO = %S" in sql_upper:
                mod_filter = params[0].upper()
                limit = int(params[1]) if len(params) > 1 else 100
            elif "BETWEEN" in sql_upper:
                date_range = (str(params[0]), str(params[1]))
            elif "LIKE" in sql_upper:
                search_query = params[0].replace("%", "").strip().lower()
            elif len(params) >= 2:
                limit = int(params[0])
                offset = int(params[1])

            res = []
            for item in self.bitacora:
                uid = item.get("usuario_id")
                u = self.usuarios.get(uid, {"nombre": "Sistema", "apellido": ""})
                entry = {
                    **item,
                    "nombre": u.get("nombre", ""),
                    "apellido": u.get("apellido", "")
                }
                if user_filter and uid != user_filter:
                    continue
                if mod_filter and item.get("modulo", "").upper() != mod_filter:
                    continue
                if date_range:
                    f = str(item.get("fecha", ""))
                    if not (date_range[0] <= f <= date_range[1] or date_range[0][:10] <= f[:10] <= date_range[1][:10]):
                        continue
                if search_query:
                    combined = f"{item.get('accion', '')} {item.get('modulo', '')} {item.get('descripcion', '')}".lower()
                    if search_query not in combined:
                        continue
                res.append(entry)

            res.sort(key=lambda x: x.get("fecha", ""), reverse=True)
            return res[offset:offset + limit]

        if "FROM MECANICOS" in sql_upper:
            if "WHERE M.ESTADO = 1" in sql_upper:
                res = [self._get_mechanic_dict(m) for m in self.mecanicos.values() if m.get("estado") == 1]
                res.sort(key=lambda x: (x["nombre"], x["apellido"]))
                return res

        if "FROM SERVICIO_MECANICO SM INNER JOIN SERVICIOS S" in sql_upper and "SM.MECANICO_CEDULA = %S" in sql_upper:
            ced = params[0]
            items = []
            for sm in self.servicio_mecanico.values():
                if sm.get("mecanico_cedula") == ced:
                    d = self._get_service_mechanic_dict(sm)
                    items.append(d)
            items.sort(key=lambda x: x.get("fecha", ""), reverse=True)
            return items

        if "FROM SERVICIOS" in sql_upper:
            if "WHERE SS.SUCURSAL_ID = %S" in sql_upper:
                suc_id = int(params[0])
                matched_sids = [l["servicio_id"] for l in self.servicio_sucursal if l["sucursal_id"] == suc_id and l.get("estado", 1) == 1]
                res = [self._get_service_dict(self.servicios[sid]) for sid in matched_sids if sid in self.servicios and self.servicios[sid].get("estado") == 1]
                res.sort(key=lambda x: x["nombre"])
                return res
            if "WHERE S.ESTADO = 1" in sql_upper:
                res = [self._get_service_dict(s) for s in self.servicios.values() if s.get("estado") == 1]
                res.sort(key=lambda x: x["nombre"])
                return res

        if "FROM SERVICIO_MECANICO" in sql_upper:
            res = [self._get_service_mechanic_dict(sm) for sm in self.servicio_mecanico.values()]
            res.sort(key=lambda x: x.get("fecha", ""), reverse=True)
            return res

        if "SHOW COLUMNS FROM PRODUCTOS" in sql_upper:
            cols = ["codigo", "nombre_producto", "descripcion_producto", "precio_producto", "categoria", "marca", "imagen_producto", "estado"]
            return [{"Field": c} for c in cols]

        if "FROM CATEGORIAS" in sql_upper:
            res = [self._get_category_dict(c) for c in self.categorias.values() if c.get("estado", 1) == 1]
            res.sort(key=lambda x: x["nombre"])
            return res

        if "FROM MARCAS" in sql_upper:
            res = [self._get_brand_dict(m) for m in self.marcas.values() if m.get("estado", 1) == 1]
            res.sort(key=lambda x: x["nombre"])
            return res

        if "FROM SUCURSALES" in sql_upper:
            res = [self._get_sucursal_dict(s) for s in self.sucursales.values() if s.get("estado", 1) == 1]
            res.sort(key=lambda x: x["nombre"])
            return res

        if "FROM STOCK" in sql_upper:
            if "WHERE PRODUCTO_CODIGO = %S AND SUCURSAL_ID = %S" in sql_upper:
                cod = params[0].strip().upper()
                sid = int(params[1])
                return [{"stock": st.get("stock", 0), "sucursal_id": st["sucursal_id"], "producto_codigo": st["producto_codigo"]} for st in self.stock if st.get("producto_codigo") == cod and int(st.get("sucursal_id")) == sid]
            if "WHERE PRODUCTO_CODIGO = %S" in sql_upper:
                cod = params[0].strip().upper()
                return [{"sucursal_id": st["sucursal_id"], "stock": st.get("stock", 0), "producto_codigo": st["producto_codigo"]} for st in self.stock if st.get("producto_codigo") == cod]
            return [dict(st) for st in self.stock]

        if "FROM PRODUCTOS" in sql_upper:
            res = []
            cat_filter = None
            brand_filter = None
            suc_filter = None

            if "WHERE P.CATEGORIA = %S" in sql_upper or "WHERE CATEGORIA = %S" in sql_upper:
                cat_filter = params[0].strip()
            elif "WHERE P.MARCA = %S" in sql_upper or "WHERE MARCA = %S" in sql_upper:
                brand_filter = params[0].strip()
            elif "WHERE ST.SUCURSAL_ID = %S" in sql_upper:
                suc_filter = int(params[0])

            for p in self.productos.values():
                if "WHERE P.ESTADO = %S" in sql_upper:
                    if int(p.get("estado", 1)) != int(params[0]):
                        continue
                elif p.get("estado", 1) != 1:
                    continue

                if cat_filter and p.get("categoria") != cat_filter:
                    continue
                if brand_filter and p.get("marca") != brand_filter:
                    continue
                if suc_filter:
                    has_suc = any(st.get("producto_codigo") == p["codigo"] and int(st.get("sucursal_id")) == suc_filter for st in self.stock)
                    if not has_suc:
                        continue
                if "LIKE" in sql_upper and len(params) >= 1:
                    search_str = ""
                    for param in params:
                        if isinstance(param, str) and "%" in param:
                            search_str = param.replace("%", "").strip().lower()
                            break
                    if search_str:
                        target = f"{p.get('codigo','')} {p.get('nombre_producto','')} {p.get('descripcion_producto','')}".lower()
                        if search_str not in target:
                            continue

                res.append(self._get_product_dict(p))

            res.sort(key=lambda x: x["nombre"])
            return res

        if "SELECT CLIENTE_CEDULA FROM CLIENTE_VEHICULO" in sql_upper or ("FROM CLIENTE_VEHICULO" in sql_upper and "WHERE VEHICULO_PLACA = %S" in sql_upper):
            placa = params[0].strip().upper() if params else ""
            return [{"cliente_cedula": cv["cliente_cedula"]} for cv in self.cliente_vehiculo if cv.get("vehiculo_placa", "").strip().upper() == placa and cv.get("estado", 1) == 1]

        if "FROM CLIENTE " in sql_upper or "FROM CLIENTE\n" in sql_upper or "FROM CLIENTE\r" in sql_upper or "FROM CLIENTE C" in sql_upper:
            res = []
            for c in self.clientes.values():
                if c.get("identificador_cliente") == "V-00000000":
                    continue
                if "C.ESTADO = %S" in sql_upper or "ESTADO = %S" in sql_upper:
                    st_val = int(params[-1]) if params else 1
                    if int(c.get("estado", 1)) != st_val:
                        continue
                elif c.get("estado", 1) != 1:
                    continue
                res.append(self._get_client_dict(c))
            return res

        if "FROM VEHICULOS" in sql_upper:
            if "CV.CLIENTE_CEDULA = %S" in sql_upper or "CV.CLIENTE_CEDULA=%S" in sql_upper:
                ced = params[0].strip().upper()
                matched_plates = [cv["vehiculo_placa"] for cv in self.cliente_vehiculo if cv.get("cliente_cedula", "").strip().upper() == ced and cv.get("estado", 1) == 1]
                res = [self._get_vehicle_dict(self.vehiculos[p]) for p in matched_plates if p in self.vehiculos and self.vehiculos[p].get("estado", 1) == 1]
                return res
            if "WHERE PLACA_VEHICULO = %S" in sql_upper or "WHERE V.PLACA_VEHICULO = %S" in sql_upper or "WHERE PLACA_VEHICULO=%S" in sql_upper:
                placa = params[0].strip().upper() if params else ""
                v = self.vehiculos.get(placa)
                if v and (v.get("estado", 1) == 1 or "ESTADO = 1" not in sql_upper):
                    return [self._get_vehicle_dict(v)]
                return []
            res = [self._get_vehicle_dict(v) for v in self.vehiculos.values() if v.get("estado", 1) == 1]
            return res

        if "FROM BITACORA_VEHICULO" in sql_upper:
            if "CV.CLIENTE_CEDULA" in sql_upper:
                ced = params[0].strip().upper()
                plates = [cv["vehiculo_placa"] for cv in self.cliente_vehiculo if cv.get("cliente_cedula", "").strip().upper() == ced and cv.get("estado", 1) == 1]
                return [dict(bv) for bv in self.bitacora_vehiculo if bv.get("vehiculo_placa") in plates]
            placa = params[0].strip().upper() if params else ""
            res = [dict(bv) for bv in self.bitacora_vehiculo if bv.get("vehiculo_placa", "").strip().upper() == placa]
            return res

        if "FROM PROVEEDORES" in sql_upper:
            res = []
            for p in self.proveedores.values():
                if "WHERE P.ESTADO = 1" in sql_upper and p.get("estado", 1) != 1:
                    continue
                d = self._get_supplier_dict(p)
                res.append(d)
            res.sort(key=lambda x: (x.get("nombre") or "").lower())
            return res

        if "FROM ORDENES_COMPRA" in sql_upper:
            if "WHERE ID_ORDEN_COMPRA = %S" in sql_upper or "WHERE OC.ID_ORDEN_COMPRA = %S" in sql_upper:
                oid = int(params[0])
                o = self.ordenes_compra.get(oid)
                if o:
                    prif = o.get("proveedor_rif")
                    prov = self.proveedores.get(prif, {})
                    sid = o.get("sucursal_id")
                    suc = self.sucursales.get(sid, {})
                    return [{
                        **o,
                        "id": oid,
                        "fecha": o.get("fecha_orden_compra", "2026-10-19T12:00:00"),
                        "total": float(o.get("total_orden_compra", 0.0)),
                        "observaciones": o.get("observaciones_orden_compra", ""),
                        "proveedor_nombre": prov.get("nombre_proveedor", ""),
                        "sucursal_nombre": suc.get("nombre_sucursal", ""),
                    }]
                return []

            res = []
            q_search = None
            estado_filter = None
            if "LIKE" in sql_upper:
                for param in params:
                    if isinstance(param, str) and "%" in param:
                        q_search = param.replace("%", "").strip().lower()
                        break
            if "OC.ESTADO = %S" in sql_upper or "ESTADO = %S" in sql_upper:
                estado_filter = params[-1]

            for oid, o in self.ordenes_compra.items():
                if estado_filter and o.get("estado") != estado_filter:
                    continue
                prif = o.get("proveedor_rif")
                prov = self.proveedores.get(prif, {})
                pnom = prov.get("nombre_proveedor", "")
                sid = o.get("sucursal_id")
                suc = self.sucursales.get(sid, {})
                snom = suc.get("nombre_sucursal", "")

                if q_search:
                    target = f"{prif} {pnom} {oid}".lower()
                    if q_search not in target:
                        continue

                res.append({
                    **o,
                    "id": oid,
                    "fecha": o.get("fecha_orden_compra", "2026-10-19T12:00:00"),
                    "total": float(o.get("total_orden_compra", 0.0)),
                    "observaciones": o.get("observaciones_orden_compra", ""),
                    "proveedor_nombre": pnom,
                    "sucursal_nombre": snom,
                })
            res.sort(key=lambda x: x["id"], reverse=True)
            return res

        if "FROM DETALLE_ORDEN_COMPRA" in sql_upper:
            oid = int(params[0]) if params else 0
            res = []
            for doc in self.detalle_orden_compra:
                if doc.get("orden_compra_id") == oid:
                    prod = self.productos.get(doc.get("producto_codigo"), {})
                    res.append({
                        **doc,
                        "id": doc.get("id_detalle_orden_compra", 1),
                        "precio_unitario": float(doc.get("precio_unitario_compra", 0.0)),
                        "producto_nombre": prod.get("nombre_producto", ""),
                    })
            return res

        if "FROM TICKETS_SOPORTE" in sql_upper:
            if "GROUP BY ESTADO" in sql_upper:
                counts = {}
                for t in self.tickets_soporte.values():
                    st = t.get("estado", "abierto")
                    counts[st] = counts.get(st, 0) + 1
                return [{"estado": st, "total": cnt} for st, cnt in counts.items()]

            res = []
            client_filter = None
            estado_filter = None
            prio_filter = None

            if "WHERE T.CLIENTE_CEDULA = %S" in sql_upper:
                client_filter = params[0].strip().upper() if params else ""
            else:
                idx = 0
                if "AND T.ESTADO = %S" in sql_upper:
                    estado_filter = params[idx]
                    idx += 1
                if "AND T.PRIORIDAD_TICKET = %S" in sql_upper:
                    prio_filter = params[idx]
                    idx += 1

            for tid, t in self.tickets_soporte.items():
                if client_filter and t.get("cliente_cedula", "").strip().upper() != client_filter:
                    continue
                if estado_filter and t.get("estado") != estado_filter:
                    continue
                if prio_filter and t.get("prioridad_ticket") != prio_filter:
                    continue
                res.append(self._get_ticket_dict(t))
            res.sort(key=lambda x: x["id"], reverse=True)
            return res

        if "FROM TICKET_RESPUESTAS" in sql_upper:
            tid = int(params[0]) if params else 0
            res = []
            for r in self.ticket_respuestas:
                if r.get("ticket_id") == tid:
                    res.append({
                        **r,
                        "id": r.get("id_ticket_respuesta", 1),
                        "mensaje": r.get("mensaje_ticket_respuesta", ""),
                    })
            return res

        if "FROM NOTIFICACIONES" in sql_upper:
            res = []
            uid = None
            ced = None
            unread_only = "LEIDA = 0" in sql_upper
            if len(params) >= 2:
                uid = int(params[0]) if params[0] is not None else None
                ced = str(params[1]).strip().upper() if params[1] else None
            elif len(params) == 1:
                if isinstance(params[0], int) or str(params[0]).isdigit():
                    uid = int(params[0])
                else:
                    ced = str(params[0]).strip().upper()

            for n in self.notificaciones:
                if unread_only and n.get("leida", 0) != 0:
                    continue
                match = False
                if uid is not None and n.get("usuario_id") == uid:
                    match = True
                if ced is not None and str(n.get("cliente_cedula") or "").strip().upper() == ced:
                    match = True
                if match:
                    res.append({
                        **n,
                        "id": n.get("id_notificacion", 1),
                        "tipo": n.get("tipo_notificacion", "sistema"),
                        "titulo": n.get("titulo_notificacion", ""),
                        "mensaje": n.get("mensaje_notificacion", ""),
                        "prioridad": n.get("prioridad_notificacion", "media"),
                    })
            res.sort(key=lambda x: x.get("id", 0), reverse=True)
            return res

        if "FROM ORDENES_VENTA" in sql_upper:
            return []

        return []

    def insert(self, db, sql, params=None):
        sql_upper = sql.upper().strip()
        params = params or ()

        if "INSERT INTO USUARIOS" in sql_upper or "INSERT INTO `USUARIOS`" in sql_upper:
            new_uid = self.next_user_id
            self.next_user_id += 1
            user_data = {
                "id": new_uid,
                "cedula": "V-00000000",
                "cedula_prefijo": "V",
                "nombre": "",
                "apellido": "",
                "email": "",
                "telefono": "",
                "direccion": "",
                "password_hash": generate_password_hash("Test1234*"),
                "foto_perfil": "default.png",
                "tipo": "empleado",
                "estado": 1,
                "created_at": "2026-10-19 12:00:00"
            }
            m = re.search(r'\(([^)]+)\)\s+VALUES', sql, re.IGNORECASE)
            if m and len(params) > 0:
                cols = [c.strip(" `").lower() for c in m.group(1).split(",")]
                for idx, col in enumerate(cols):
                    if idx < len(params):
                        user_data[col] = params[idx]
            elif len(params) >= 8:
                user_data["nombre"] = params[0]
                user_data["apellido"] = params[1]
                user_data["cedula"] = params[2]
                user_data["email"] = params[3]
                user_data["telefono"] = params[4]
                user_data["direccion"] = params[5]
                user_data["password_hash"] = params[6]
                user_data["tipo"] = params[7]

            self.usuarios[new_uid] = user_data
            return new_uid

        if "INSERT INTO USUARIO_ROL" in sql_upper:
            uid, rid = int(params[0]), int(params[1])
            self.usuario_rol.append({"usuario_id": uid, "rol_id": rid})
            return 1

        if "INSERT INTO ROLES" in sql_upper:
            nom, desc = params[0], params[1]
            new_rid = self.next_role_id
            self.next_role_id += 1
            self.roles[new_rid] = {
                "id": new_rid,
                "nombre": nom,
                "descripcion": desc,
                "estado": 1
            }
            return new_rid

        if "INSERT INTO PERMISOS" in sql_upper:
            rid, mod, cr, le, ac, el = int(params[0]), params[1], int(params[2]), int(params[3]), int(params[4]), int(params[5])
            self.permisos.append({
                "id": len(self.permisos) + 1,
                "rol_id": rid,
                "modulo": mod,
                "crear": cr,
                "leer": le,
                "actualizar": ac,
                "eliminar": el
            })
            return 1

        if "INSERT INTO MODULOS" in sql_upper:
            nom = params[0]
            new_mid = self.next_modulo_id
            self.next_modulo_id += 1
            self.modulos[new_mid] = {
                "id": new_mid,
                "id_modulo": new_mid,
                "nombre_modulo": nom,
                "titulo_modulo": params[1] if len(params) > 1 else nom,
                "descripcion_modulo": params[2] if len(params) > 2 else "",
                "ruta_modulo": params[3] if len(params) > 3 else f"/admin/{nom}",
                "icono_modulo": params[4] if len(params) > 4 else "bi-app",
                "grupo_modulo": params[5] if len(params) > 5 else "General",
                "orden_modulo": int(params[6]) if len(params) > 6 else 10,
                "en_sidebar": int(params[7]) if len(params) > 7 else 1,
                "publico_modulo": int(params[8]) if len(params) > 8 else 0,
                "estado_modulo": 1
            }
            return new_mid

        if "INSERT INTO TOKENS_RECUPERACION" in sql_upper:
            uid, tok, exp = int(params[0]), params[1], params[2]
            new_tid = self.next_token_id
            self.next_token_id += 1
            self.tokens_recuperacion[new_tid] = {
                "id": new_tid,
                "usuario_id": uid,
                "token": tok,
                "expiracion": exp,
                "usado": 0
            }
            return new_tid

        if "INSERT INTO BITACORA" in sql_upper:
            uid, acc, mod, desc, ip = int(params[0]), params[1], params[2], params[3], params[4]
            new_bid = self.next_bitacora_id
            self.next_bitacora_id += 1
            self.bitacora.append({
                "id": new_bid,
                "usuario_id": uid,
                "accion": acc,
                "modulo": mod,
                "descripcion": desc,
                "ip": ip,
                "fecha": "2026-10-19 12:00:00"
            })
            return new_bid

        if "INSERT INTO MECANICOS" in sql_upper:
            ced, pref, nom, ape, tel, esp, foto = params
            self.mecanicos[ced] = {
                "cedula": ced,
                "cedula_mecanico": ced,
                "cedula_prefijo": pref,
                "nombre": nom,
                "nombre_mecanico": nom,
                "apellido": ape,
                "apellido_mecanico": ape,
                "telefono": tel,
                "telefono_mecanico": tel,
                "especialidad": esp,
                "especialidad_mecanico": esp,
                "foto_perfil": foto or "default.png",
                "foto_perfil_mecanico": foto or "default.png",
                "usuario_id": 1,
                "estado": 1,
                "created_at": "2026-10-19 12:00:00",
            }
            return 1

        if "INSERT INTO SERVICIOS" in sql_upper:
            nom, desc, tipo, precio, dur = params
            new_id = self.next_service_id
            self.next_service_id += 1
            self.servicios[new_id] = {
                "id": new_id,
                "id_servicio": new_id,
                "nombre": nom,
                "nombre_servicio": nom,
                "descripcion": desc,
                "descripcion_servicio": desc,
                "tipo": tipo,
                "tipo_servicio": tipo,
                "precio": float(precio),
                "precio_servicio": float(precio),
                "duracion_estimada": int(dur),
                "estado": 1,
            }
            return new_id

        if "INSERT INTO SERVICIO_SUCURSAL" in sql_upper:
            sid, suc_id = int(params[0]), int(params[1])
            self.servicio_sucursal.append({"servicio_id": sid, "sucursal_id": suc_id, "estado": 1})
            return 1

        if "INSERT INTO SERVICIO_MECANICO" in sql_upper:
            sid, mced, ov_id, obs, cced, vplaca, estado = params
            new_aid = self.next_assignment_id
            self.next_assignment_id += 1
            self.servicio_mecanico[new_aid] = {
                "id": new_aid,
                "id_servicio_mecanico": new_aid,
                "servicio_id": int(sid),
                "mecanico_cedula": mced,
                "orden_venta_id": ov_id,
                "observaciones_servicio": obs or "",
                "cliente_cedula": cced,
                "vehiculo_placa": vplaca,
                "estado_servicio": estado or "sin_asignar",
                "fecha_servicio": "2026-10-19T12:00:00",
            }
            return new_aid

        if "INSERT INTO COMISIONES_MECANICO" in sql_upper:
            sm_id, precio, pct = int(params[0]), float(params[1]), float(params[2])
            self.comisiones_mecanico[sm_id] = {
                "id_comision": sm_id,
                "servicio_mecanico_id": sm_id,
                "precio_servicio_comision": precio,
                "porcentaje_comision": pct,
            }
            return sm_id

        if "INSERT INTO CATEGORIAS" in sql_upper:
            nom, desc = params[0], params[1] if len(params) > 1 else ""
            img = params[2] if len(params) > 2 else "product-default-parts.png"
            self.categorias[nom] = {
                "nombre_categoria": nom,
                "descripcion_categoria": desc,
                "imagen_categoria": img,
                "estado": 1
            }
            return 1

        if "INSERT INTO MARCAS" in sql_upper:
            nom, desc = params[0], params[1] if len(params) > 1 else ""
            self.marcas[nom] = {
                "nombre_marca": nom,
                "descripcion_marca": desc,
                "estado": 1
            }
            return 1

        if "INSERT INTO SUCURSALES" in sql_upper:
            new_sid = self.next_sucursal_id
            self.next_sucursal_id += 1
            nom = params[0]
            dire = params[1] if len(params) > 1 else ""
            tel = params[2] if len(params) > 2 else ""
            email = params[3] if len(params) > 3 else ""
            self.sucursales[new_sid] = {
                "id_sucursal": new_sid,
                "nombre_sucursal": nom,
                "direccion_sucursal": dire,
                "telefono_sucursal": tel,
                "email_sucursal": email,
                "estado": 1
            }
            return new_sid

        if "INSERT INTO PRODUCTOS" in sql_upper or "INSERT INTO `PRODUCTOS`" in sql_upper:
            p_data = {
                "codigo": params[0],
                "nombre_producto": params[1],
                "descripcion_producto": params[2] if len(params) > 2 else "",
                "precio_producto": float(params[3]) if len(params) > 3 else 0.0,
                "categoria": params[4] if len(params) > 4 else None,
                "marca": params[5] if len(params) > 5 else None,
                "imagen_producto": params[6] if len(params) > 6 else "default_product.png",
                "estado": 1
            }
            self.productos[params[0]] = p_data
            return 1

        if "INSERT INTO STOCK" in sql_upper or "INSERT INTO `STOCK`" in sql_upper:
            cod, sid = params[0], int(params[1])
            qty = int(params[2]) if len(params) > 2 else 0
            self.stock = [st for st in self.stock if not (st.get("producto_codigo") == cod and int(st.get("sucursal_id")) == sid)]
            self.stock.append({"producto_codigo": cod, "sucursal_id": sid, "stock": qty})
            return 1

        if "INSERT INTO CLIENTE " in sql_upper or "INSERT INTO `CLIENTE`" in sql_upper:
            new_cid = self.next_cliente_id
            self.next_cliente_id += 1
            nom = params[0]
            ape = params[1] if len(params) > 1 else ""
            correo = params[2] if len(params) > 2 else ""
            ced = params[3] if len(params) > 3 else f"V-{new_cid}"
            tel = params[4] if len(params) > 4 else ""
            dire = params[5] if len(params) > 5 else ""
            tipo = params[6] if len(params) > 6 else "natural"
            self.clientes[ced] = {
                "id_cliente": new_cid,
                "identificador_cliente": ced,
                "nombre_cliente": nom,
                "apellido_cliente": ape,
                "correo_cliente": correo,
                "telefono_cliente": tel,
                "direccion_cliente": dire,
                "tipo_cliente": tipo,
                "usuario_id": None,
                "id_natural": new_cid,
                "origen_registro": "admin",
                "estado": 1,
                "created_at": "2026-10-19 12:00:00"
            }
            return new_cid

        if "INSERT INTO CLIENTE_NATURAL" in sql_upper or "INSERT INTO CLIENTE_JURIDICO" in sql_upper:
            return 1

        if "INSERT INTO VEHICULOS" in sql_upper or "INSERT INTO `VEHICULOS`" in sql_upper:
            new_vid = self.next_vehiculo_id
            self.next_vehiculo_id += 1
            marca, modelo, anio, placa = params[0], params[1], params[2], params[3]
            color = params[4] if len(params) > 4 else ""
            self.vehiculos[placa] = {
                "id_vehiculo": new_vid,
                "placa_vehiculo": placa,
                "marca_vehiculo": marca,
                "modelo_vehiculo": modelo,
                "anio_vehiculo": anio,
                "color_vehiculo": color,
                "tipo_vehiculo": params[5] if len(params) > 5 else "Sedan",
                "tipo_combustible": params[6] if len(params) > 6 else "gasolina",
                "kilometraje_actual": int(params[7]) if len(params) > 7 and params[7] is not None else 0,
                "observaciones_vehiculo": params[11] if len(params) > 11 else "",
                "cliente_cedula": "",
                "estado": 1,
                "created_at": "2026-10-19 12:00:00"
            }
            return placa

        if "INSERT INTO CLIENTE_VEHICULO" in sql_upper:
            new_cv_id = self.next_cliente_vehiculo_id
            self.next_cliente_vehiculo_id += 1
            cced, vplaca = params[0], params[1]
            self.cliente_vehiculo = [cv for cv in self.cliente_vehiculo if not (cv.get("cliente_cedula") == cced and cv.get("vehiculo_placa") == vplaca)]
            self.cliente_vehiculo.append({
                "id_cliente_vehiculo": new_cv_id,
                "cliente_cedula": cced,
                "vehiculo_placa": vplaca,
                "estado": 1,
                "created_at": "2026-10-19 12:00:00"
            })
            return new_cv_id

        if "INSERT INTO PROVEEDORES" in sql_upper:
            rif = params[0]
            pref = params[1] if len(params) > 1 else rif[0]
            nom = params[2] if len(params) > 2 else ""
            tel = params[3] if len(params) > 3 else ""
            email = params[4] if len(params) > 4 else ""
            dire = params[5] if len(params) > 5 else ""
            self.proveedores[rif] = {
                "rif_proveedor": rif,
                "rif_prefijo": pref,
                "nombre_proveedor": nom,
                "telefono_proveedor": tel,
                "email_proveedor": email,
                "direccion_proveedor": dire,
                "estado": 1,
            }
            return rif

        if "INSERT INTO ORDENES_COMPRA" in sql_upper:
            new_oid = self.next_orden_compra_id
            self.next_orden_compra_id += 1
            self.ordenes_compra[new_oid] = {
                "id_orden_compra": new_oid,
                "proveedor_rif": params[0],
                "sucursal_id": int(params[1]),
                "total_orden_compra": float(params[2]) if len(params) > 2 else 0.0,
                "estado": "pendiente",
                "observaciones_orden_compra": params[3] if len(params) > 3 else "",
                "fecha_orden_compra": "2026-10-19T12:00:00",
            }
            return new_oid

        if "INSERT INTO DETALLE_ORDEN_COMPRA" in sql_upper:
            new_did = len(self.detalle_orden_compra) + 1
            self.detalle_orden_compra.append({
                "id_detalle_orden_compra": new_did,
                "orden_compra_id": int(params[0]),
                "producto_codigo": params[1],
                "cantidad": int(params[2]),
                "precio_unitario_compra": float(params[3]),
                "subtotal": float(params[4]),
            })
            return new_did

        if "INSERT INTO TICKETS_SOPORTE" in sql_upper:
            new_tid = self.next_ticket_id
            self.next_ticket_id += 1
            self.tickets_soporte[new_tid] = {
                "id_ticket_soporte": new_tid,
                "cliente_cedula": params[0],
                "referencia_tipo": params[1] if len(params) > 1 else "general",
                "referencia_id": params[2] if len(params) > 2 else None,
                "asunto": params[3] if len(params) > 3 else "",
                "descripcion_ticket_soporte": params[4] if len(params) > 4 else "",
                "prioridad_ticket": params[5] if len(params) > 5 else "media",
                "estado": "abierto",
                "created_at": "2026-10-19 12:00:00",
            }
            return new_tid

        if "INSERT INTO TICKET_RESPUESTAS" in sql_upper:
            new_rid = len(self.ticket_respuestas) + 1
            self.ticket_respuestas.append({
                "id_ticket_respuesta": new_rid,
                "ticket_id": int(params[0]),
                "autor_id": int(params[1]) if params[1] else None,
                "autor_tipo": params[2] if len(params) > 2 else "admin",
                "mensaje_ticket_respuesta": params[3] if len(params) > 3 else "",
                "adjunto_url": params[4] if len(params) > 4 else None,
                "created_at": "2026-10-19 12:00:00",
            })
            return new_rid

        if "INSERT INTO NOTIFICACIONES" in sql_upper:
            new_nid = self.next_notif_id
            self.next_notif_id += 1
            self.notificaciones.append({
                "id_notificacion": new_nid,
                "usuario_id": int(params[0]) if params[0] is not None else None,
                "cliente_cedula": params[1] if len(params) > 1 and params[1] else None,
                "tipo_notificacion": params[2] if len(params) > 2 else "sistema",
                "titulo_notificacion": params[3] if len(params) > 3 else "",
                "mensaje_notificacion": params[4] if len(params) > 4 else "",
                "prioridad_notificacion": params[5] if len(params) > 5 else "media",
                "referencia": params[6] if len(params) > 6 else None,
                "leida": 0,
                "created_at": "2026-10-19 12:00:00",
            })
            return new_nid

        return 1

    def update(self, db, sql, params=None):
        sql_upper = sql.upper().strip()
        sql_clean = sql_upper.replace("`", "")
        params = params or ()

        if "UPDATE USUARIOS" in sql_clean:
            if "SET ESTADO = 0 WHERE ID = %S" in sql_clean:
                uid = int(params[0])
                if uid in self.usuarios:
                    self.usuarios[uid]["estado"] = 0
                    return 1
                return None
            if "SET ESTADO = %S WHERE ID = %S" in sql_clean:
                st, uid = int(params[0]), int(params[1])
                if uid in self.usuarios:
                    self.usuarios[uid]["estado"] = st
                    return 1
                return None
            if "SET PASSWORD_HASH = %S, ESTADO = 1 WHERE ID = %S" in sql_clean:
                pwd, uid = params[0], int(params[1])
                if uid in self.usuarios:
                    self.usuarios[uid]["password_hash"] = pwd
                    self.usuarios[uid]["estado"] = 1
                    return 1
                return None
            if "SET PASSWORD_HASH = %S WHERE ID = %S" in sql_clean:
                pwd, uid = params[0], int(params[1])
                if uid in self.usuarios:
                    self.usuarios[uid]["password_hash"] = pwd
                    return 1
                return None
            if "SET FOTO_PERFIL = %S WHERE ID = %S" in sql_clean:
                foto, uid = params[0], int(params[1])
                if uid in self.usuarios:
                    self.usuarios[uid]["foto_perfil"] = foto
                    return 1
                return None
            if "WHERE ID = %S" in sql_clean:
                uid = int(params[-1])
                u = self.usuarios.get(uid)
                if u:
                    set_match = re.search(r'SET\s+(.+?)\s+WHERE', sql_clean, re.IGNORECASE)
                    if set_match:
                        set_cols = [c.split("=")[0].strip().lower() for c in set_match.group(1).split(",")]
                        for idx, col in enumerate(set_cols):
                            if idx < len(params) - 1:
                                u[col] = params[idx]
                    return 1
                return None

        if "UPDATE ROLES" in sql_upper:
            if "SET ESTADO = 0 WHERE ID = %S" in sql_upper:
                rid = int(params[0])
                if rid in self.roles:
                    self.roles[rid]["estado"] = 0
                    return 1
                return None
            if "SET ESTADO = %S WHERE ID = %S" in sql_upper:
                st, rid = int(params[0]), int(params[1])
                if rid in self.roles:
                    self.roles[rid]["estado"] = st
                    return 1
                return None
            if "WHERE ID = %S" in sql_upper:
                rid = int(params[-1])
                r = self.roles.get(rid)
                if r:
                    r["nombre"] = params[0]
                    r["descripcion"] = params[1]
                    return 1
                return None

        if "UPDATE MODULOS" in sql_upper:
            if "ESTADO_MODULO" in sql_upper and ("= 0" in sql_upper or "=0" in sql_upper):
                mid = int(params[0])
                if mid in self.modulos:
                    self.modulos[mid]["estado_modulo"] = 0
                    return 1
                return None
            if "ID_MODULO" in sql_upper:
                mid = int(params[-1])
                m = self.modulos.get(mid)
                if m:
                    m["nombre_modulo"] = params[0]
                    m["titulo_modulo"] = params[1]
                    m["descripcion_modulo"] = params[2]
                    m["ruta_modulo"] = params[3]
                    m["icono_modulo"] = params[4]
                    m["grupo_modulo"] = params[5]
                    m["orden_modulo"] = int(params[6])
                    m["en_sidebar"] = int(params[7])
                    m["publico_modulo"] = int(params[8])
                    return 1
                return None

        if "UPDATE PERMISOS" in sql_upper:
            cr, le, ac, el, pid = int(params[0]), int(params[1]), int(params[2]), int(params[3]), int(params[4])
            for p in self.permisos:
                if p["id"] == pid:
                    p["crear"] = cr
                    p["leer"] = le
                    p["actualizar"] = ac
                    p["eliminar"] = el
                    return 1
            return 1

        if "UPDATE TOKENS_RECUPERACION" in sql_upper:
            tid = int(params[0])
            if tid in self.tokens_recuperacion:
                self.tokens_recuperacion[tid]["usado"] = 1
                return 1
            return 1

        if "UPDATE MECANICOS" in sql_upper:
            if "SET ESTADO = 0 WHERE CEDULA_MECANICO = %S" in sql_upper:
                ced = params[0]
                if ced in self.mecanicos:
                    self.mecanicos[ced]["estado"] = 0
                    return 1
                return None
            if "SET ESTADO = 1 WHERE CEDULA_MECANICO = %S" in sql_upper:
                ced = params[0]
                if ced in self.mecanicos:
                    self.mecanicos[ced]["estado"] = 1
                    return 1
                return 0
            if "SET ESTADO = %S WHERE CEDULA_MECANICO = %S" in sql_upper:
                new_st, ced = int(params[0]), params[1]
                if ced in self.mecanicos:
                    self.mecanicos[ced]["estado"] = new_st
                    return 1
                return 0
            if "WHERE CEDULA_MECANICO=%S" in sql_upper:
                old_ced = params[-1]
                m = self.mecanicos.get(old_ced)
                if m:
                    if "ESTADO=1" in sql_upper:
                        if len(params) == 7:
                            pref, nom, ape, tel, esp, foto, _ = params
                            m["foto_perfil"] = foto
                            m["foto_perfil_mecanico"] = foto
                        else:
                            pref, nom, ape, tel, esp, _ = params
                        m["cedula_prefijo"] = pref
                        m["nombre"] = nom
                        m["nombre_mecanico"] = nom
                        m["apellido"] = ape
                        m["apellido_mecanico"] = ape
                        m["telefono"] = tel
                        m["telefono_mecanico"] = tel
                        m["especialidad"] = esp
                        m["especialidad_mecanico"] = esp
                        m["estado"] = 1
                        return 1
                    else:
                        if len(params) == 8:
                            new_ced, pref, nom, ape, tel, esp, foto, _ = params
                            m["foto_perfil"] = foto
                            m["foto_perfil_mecanico"] = foto
                        else:
                            new_ced, pref, nom, ape, tel, esp, _ = params
                        m["cedula"] = new_ced
                        m["cedula_mecanico"] = new_ced
                        m["cedula_prefijo"] = pref
                        m["nombre"] = nom
                        m["nombre_mecanico"] = nom
                        m["apellido"] = ape
                        m["apellido_mecanico"] = ape
                        m["telefono"] = tel
                        m["telefono_mecanico"] = tel
                        m["especialidad"] = esp
                        m["especialidad_mecanico"] = esp
                        m["estado"] = 1
                        if new_ced != old_ced:
                            self.mecanicos[new_ced] = self.mecanicos.pop(old_ced)
                        return 1

        if "UPDATE SERVICIOS" in sql_upper:
            if "SET ESTADO = 0 WHERE ID_SERVICIO = %S" in sql_upper:
                sid = int(params[0])
                if sid in self.servicios:
                    self.servicios[sid]["estado"] = 0
                    return 1
                return 0
            if "SET ESTADO = 1 WHERE ID_SERVICIO = %S" in sql_upper:
                sid = int(params[0])
                if sid in self.servicios:
                    self.servicios[sid]["estado"] = 1
                    return 1
                return 0
            if "WHERE ID_SERVICIO=%S" in sql_upper or "WHERE ID_SERVICIO = %S" in sql_upper:
                sid = int(params[-1])
                s = self.servicios.get(sid)
                if s:
                    nom, desc, tipo, precio, dur = params[0], params[1], params[2], params[3], params[4]
                    s["nombre"] = nom
                    s["nombre_servicio"] = nom
                    s["descripcion"] = desc
                    s["descripcion_servicio"] = desc
                    s["tipo"] = tipo
                    s["tipo_servicio"] = tipo
                    s["precio"] = float(precio)
                    s["precio_servicio"] = float(precio)
                    s["duracion_estimada"] = int(dur)
                    s["estado"] = 1
                    return 1

        if "DELETE FROM SERVICIO_SUCURSAL WHERE SERVICIO_ID = %S" in sql_upper:
            sid = int(params[0])
            self.servicio_sucursal = [l for l in self.servicio_sucursal if l["servicio_id"] != sid]
            return 1

        if "UPDATE SERVICIO_MECANICO" in sql_upper:
            if "SET MECANICO_CEDULA = %S" in sql_upper:
                ced, aid = params[0], int(params[1])
                sm = self.servicio_mecanico.get(aid)
                if sm:
                    sm["mecanico_cedula"] = ced
                    if sm.get("estado_servicio") == "sin_asignar" and ced:
                        sm["estado_servicio"] = "asignado"
                    return 1
            if "SET MECANICO_CEDULA = NULL" in sql_upper:
                aid = int(params[0])
                sm = self.servicio_mecanico.get(aid)
                if sm:
                    sm["mecanico_cedula"] = None
                    if sm.get("estado_servicio") in ("asignado", "pendiente"):
                        sm["estado_servicio"] = "sin_asignar"
                    return 1
            if "SET ESTADO_SERVICIO = %S WHERE ID_SERVICIO_MECANICO = %S" in sql_upper:
                st, aid = params[0], int(params[1])
                sm = self.servicio_mecanico.get(aid)
                if sm:
                    sm["estado_servicio"] = st
                    return 1
            if "WHERE ID_SERVICIO_MECANICO = %S" in sql_upper:
                sid, mced, ov_id, obs, cced, vplaca, estado, aid = (
                    int(params[0]), params[1], params[2], params[3], params[4], params[5], params[6], int(params[7])
                )
                sm = self.servicio_mecanico.get(aid)
                if sm:
                    sm["servicio_id"] = sid
                    sm["mecanico_cedula"] = mced
                    sm["orden_venta_id"] = ov_id
                    sm["observaciones_servicio"] = obs or ""
                    sm["cliente_cedula"] = cced
                    sm["vehiculo_placa"] = vplaca
                    sm["estado_servicio"] = estado
                    return 1

        if "UPDATE COMISIONES_MECANICO" in sql_upper:
            if "SET PORCENTAJE_COMISION = %S WHERE SERVICIO_MECANICO_ID = %S" in sql_upper:
                pct, aid = float(params[0]), int(params[1])
                if aid in self.comisiones_mecanico:
                    self.comisiones_mecanico[aid]["porcentaje_comision"] = pct
                else:
                    serv_id = self.servicio_mecanico.get(aid, {}).get("servicio_id", 1)
                    precio = self.servicios.get(serv_id, {}).get("precio_servicio", 30.0)
                    self.comisiones_mecanico[aid] = {
                        "id_comision": aid,
                        "servicio_mecanico_id": aid,
                        "precio_servicio_comision": precio,
                        "porcentaje_comision": pct,
                    }
                return 1

        if "UPDATE CATEGORIAS" in sql_upper:
            if "SET ESTADO = 0" in sql_upper or "SET ESTADO = %S" in sql_upper or "SET ESTADO = 1" in sql_upper:
                nom = params[-1]
                cat = self.categorias.get(nom)
                if cat:
                    if "SET ESTADO = 0" in sql_upper:
                        cat["estado"] = 0
                    elif "SET ESTADO = 1" in sql_upper:
                        cat["estado"] = 1
                    else:
                        cat["estado"] = int(params[0])
                    return 1
                return 0
            if "SET ESTADO = 1 - ESTADO" in sql_upper:
                nom = params[-1]
                cat = self.categorias.get(nom)
                if cat:
                    cat["estado"] = 1 - cat.get("estado", 1)
                    return 1
                return 0
            if "WHERE NOMBRE_CATEGORIA = %S" in sql_upper or "WHERE NOMBRE_CATEGORIA=%S" in sql_upper:
                old_nom = params[-1]
                cat = self.categorias.get(old_nom)
                if cat:
                    new_nom = params[0]
                    cat["nombre_categoria"] = new_nom
                    cat["descripcion_categoria"] = params[1] if len(params) > 1 else cat.get("descripcion_categoria")
                    if len(params) > 3:
                        cat["imagen_categoria"] = params[2]
                    if new_nom != old_nom:
                        self.categorias[new_nom] = self.categorias.pop(old_nom)
                    return 1
                return 0

        if "UPDATE MARCAS" in sql_upper:
            if "SET ESTADO = 0" in sql_upper or "SET ESTADO = 1" in sql_upper or "SET ESTADO = %S" in sql_upper:
                nom = params[-1]
                m = self.marcas.get(nom)
                if m:
                    if "SET ESTADO = 0" in sql_upper:
                        m["estado"] = 0
                    elif "SET ESTADO = 1" in sql_upper:
                        m["estado"] = 1
                    else:
                        m["estado"] = int(params[0])
                    return 1
                return 0
            if "SET ESTADO = 1 - ESTADO" in sql_upper:
                nom = params[-1]
                m = self.marcas.get(nom)
                if m:
                    m["estado"] = 1 - m.get("estado", 1)
                    return 1
                return 0
            if "WHERE NOMBRE_MARCA = %S" in sql_upper or "WHERE NOMBRE_MARCA=%S" in sql_upper:
                old_nom = params[-1]
                m = self.marcas.get(old_nom)
                if m:
                    new_nom = params[0]
                    m["nombre_marca"] = new_nom
                    m["descripcion_marca"] = params[1] if len(params) > 1 else m.get("descripcion_marca")
                    if new_nom != old_nom:
                        self.marcas[new_nom] = self.marcas.pop(old_nom)
                    return 1
                return 0

        if "UPDATE SUCURSALES" in sql_upper:
            if "SET ESTADO = 0 WHERE ID_SUCURSAL = %S" in sql_upper:
                sid = int(params[0])
                if sid in self.sucursales:
                    self.sucursales[sid]["estado"] = 0
                    return 1
                return 0
            if "SET ESTADO = 1 WHERE ID_SUCURSAL = %S" in sql_upper:
                sid = int(params[0])
                if sid in self.sucursales:
                    self.sucursales[sid]["estado"] = 1
                    return 1
                return 0
            if "WHERE ID_SUCURSAL = %S" in sql_upper:
                sid = int(params[-1])
                s = self.sucursales.get(sid)
                if s:
                    s["nombre_sucursal"] = params[0]
                    s["direccion_sucursal"] = params[1] if len(params) > 1 else s.get("direccion_sucursal")
                    s["telefono_sucursal"] = params[2] if len(params) > 2 else s.get("telefono_sucursal")
                    s["email_sucursal"] = params[3] if len(params) > 3 else s.get("email_sucursal")
                    return 1
                return 0

        if "UPDATE PRODUCTOS" in sql_upper or "UPDATE `PRODUCTOS`" in sql_upper:
            if "SET ESTADO = 0" in sql_upper or "SET ESTADO = %S" in sql_upper:
                cod = params[-1]
                p = self.productos.get(cod)
                if p:
                    p["estado"] = 0 if "SET ESTADO = 0" in sql_upper else int(params[0])
                    return 1
                return 0
            if "SET ESTADO = 1 - ESTADO" in sql_upper:
                cod = params[-1]
                p = self.productos.get(cod)
                if p:
                    p["estado"] = 1 - p.get("estado", 1)
                    return 1
                return 0
            if "WHERE `CODIGO` = %S" in sql_upper or "WHERE CODIGO = %S" in sql_upper:
                old_cod = params[-1]
                p = self.productos.get(old_cod)
                if p:
                    if len(params) >= 6:
                        p["codigo"] = params[0]
                        p["nombre_producto"] = params[1]
                        p["descripcion_producto"] = params[2]
                        p["precio_producto"] = float(params[3])
                        p["categoria"] = params[4]
                        p["marca"] = params[5]
                        if len(params) >= 8:
                            p["imagen_producto"] = params[6]
                        if params[0] != old_cod:
                            self.productos[params[0]] = self.productos.pop(old_cod)
                    return 1
                return 0

        if "DELETE FROM STOCK" in sql_upper:
            if "AND SUCURSAL_ID = %S" in sql_upper:
                cod, sid = params[0], int(params[1])
                self.stock = [st for st in self.stock if not (st.get("producto_codigo") == cod and int(st.get("sucursal_id")) == sid)]
                return 1
            cod = params[0]
            self.stock = [st for st in self.stock if st.get("producto_codigo") != cod]
            return 1

        if "UPDATE CLIENTE_VEHICULO" in sql_upper:
            if "SET ESTADO = 0" in sql_upper or "SET ESTADO=0" in sql_upper:
                cced, vplaca = params[0].strip().upper(), params[1].strip().upper()
                for cv in self.cliente_vehiculo:
                    if cv.get("cliente_cedula", "").strip().upper() == cced and cv.get("vehiculo_placa", "").strip().upper() == vplaca:
                        cv["estado"] = 0
                        return 1
                return 0
            if "SET ESTADO = 1 WHERE ID_CLIENTE_VEHICULO = %S" in sql_upper:
                cv_id = int(params[0])
                for cv in self.cliente_vehiculo:
                    if cv.get("id_cliente_vehiculo") == cv_id:
                        cv["estado"] = 1
                        return 1
                return 0

        if "UPDATE CLIENTE " in sql_upper or "UPDATE CLIENTE\n" in sql_upper or "UPDATE `CLIENTE`" in sql_upper:
            if "SET ESTADO = 0" in sql_upper or "SET ESTADO = %S" in sql_upper:
                ced = params[-1]
                c = self.clientes.get(ced)
                if c:
                    c["estado"] = 0 if "SET ESTADO = 0" in sql_upper else int(params[0])
                    return 1
                return 0
            if "WHERE IDENTIFICADOR_CLIENTE=%S" in sql_upper or "WHERE IDENTIFICADOR_CLIENTE = %S" in sql_upper:
                ced = params[-1]
                c = self.clientes.get(ced)
                if c:
                    c["nombre_cliente"] = params[0]
                    c["apellido_cliente"] = params[1] if len(params) > 1 else c.get("apellido_cliente")
                    c["correo_cliente"] = params[2] if len(params) > 2 else c.get("correo_cliente")
                    c["telefono_cliente"] = params[3] if len(params) > 3 else c.get("telefono_cliente")
                    c["direccion_cliente"] = params[4] if len(params) > 4 else c.get("direccion_cliente")
                    return 1
                return 0

        if "UPDATE VEHICULOS" in sql_upper:
            if "SET ESTADO = 1 WHERE PLACA_VEHICULO = %S" in sql_upper:
                placa = params[0]
                if placa in self.vehiculos:
                    self.vehiculos[placa]["estado"] = 1
                    return 1
                return 0
            if "SET ESTADO = 0 WHERE PLACA_VEHICULO = %S" in sql_upper:
                placa = params[0]
                if placa in self.vehiculos:
                    self.vehiculos[placa]["estado"] = 0
                    return 1
                return 0
            if "WHERE PLACA_VEHICULO = %S" in sql_upper or "WHERE PLACA_VEHICULO=%S" in sql_upper:
                placa = params[-1]
                v = self.vehiculos.get(placa)
                if v:
                    v["marca_vehiculo"] = params[0] if len(params) > 0 else v.get("marca_vehiculo")
                    v["modelo_vehiculo"] = params[1] if len(params) > 1 else v.get("modelo_vehiculo")
                    if len(params) > 2 and params[2] is not None:
                        v["anio_vehiculo"] = params[2]
                    if len(params) > 3 and params[3]:
                        new_placa = params[3]
                        v["placa_vehiculo"] = new_placa
                        if new_placa != placa:
                            self.vehiculos[new_placa] = v
                    if len(params) > 4:
                        v["color_vehiculo"] = params[4]
                    return 1
                return 0

        if "UPDATE PROVEEDORES" in sql_clean:
            if "SET ESTADO = 0 WHERE RIF_PROVEEDOR = %S" in sql_clean:
                rif = params[0].strip().upper()
                if rif in self.proveedores:
                    self.proveedores[rif]["estado"] = 0
                    return 1
                return 0
            if "SET ESTADO = 1 WHERE RIF_PROVEEDOR = %S" in sql_clean:
                rif = params[0].strip().upper()
                if rif in self.proveedores:
                    self.proveedores[rif]["estado"] = 1
                    return 1
                return 0
            if "SET RIF_PROVEEDOR = %S" in sql_clean:
                old_rif = params[-1].strip().upper()
                p = self.proveedores.get(old_rif)
                if p:
                    new_rif = params[0].strip().upper()
                    p["rif_proveedor"] = new_rif
                    p["rif_prefijo"] = params[1]
                    p["nombre_proveedor"] = params[2]
                    p["telefono_proveedor"] = params[3]
                    p["email_proveedor"] = params[4]
                    p["direccion_proveedor"] = params[5]
                    if new_rif != old_rif:
                        self.proveedores[new_rif] = self.proveedores.pop(old_rif)
                    return 1
                return 0
            if "SET RIF_PREFIJO=%S" in sql_clean or "SET RIF_PREFIJO = %S" in sql_clean:
                rif = params[-1].strip().upper()
                p = self.proveedores.get(rif)
                if p:
                    p["rif_prefijo"] = params[0]
                    p["nombre_proveedor"] = params[1]
                    p["telefono_proveedor"] = params[2]
                    p["email_proveedor"] = params[3]
                    p["direccion_proveedor"] = params[4]
                    p["estado"] = 1
                    return 1
                return 0

        if "UPDATE ORDENES_COMPRA" in sql_clean:
            if "SET TOTAL_ORDEN_COMPRA = %S WHERE ID_ORDEN_COMPRA = %S" in sql_clean:
                tot, oid = float(params[0]), int(params[1])
                if oid in self.ordenes_compra:
                    self.ordenes_compra[oid]["total_orden_compra"] = tot
                    return 1
                return 0
            if "SET ESTADO = 'COMPRADO' WHERE ID_ORDEN_COMPRA = %S" in sql_clean or "SET ESTADO = %S WHERE ID_ORDEN_COMPRA = %S" in sql_clean:
                oid = int(params[-1])
                st = params[0] if len(params) > 1 and params[0] in ('comprado', 'cancelado', 'pendiente') else 'comprado'
                if oid in self.ordenes_compra:
                    self.ordenes_compra[oid]["estado"] = st
                    return 1
                return 0

        if "UPDATE TICKETS_SOPORTE" in sql_clean:
            if "SET ESTADO = %S WHERE ID_TICKET_SOPORTE = %S" in sql_clean:
                st, tid = params[0], int(params[1])
                if tid in self.tickets_soporte:
                    self.tickets_soporte[tid]["estado"] = st
                    return 1
                return 0

        if "UPDATE NOTIFICACIONES" in sql_clean:
            if "SET LEIDA = 1 WHERE ID_NOTIFICACION = %S" in sql_clean:
                nid = int(params[0])
                for n in self.notificaciones:
                    if n.get("id_notificacion") == nid:
                        n["leida"] = 1
                return 1
            if "SET LEIDA = 1 WHERE" in sql_clean and "LEIDA = 0" in sql_clean:
                uid = int(params[0]) if len(params) > 0 and params[0] is not None else None
                ced = str(params[1]).strip().upper() if len(params) > 1 and params[1] else None
                count = 0
                for n in self.notificaciones:
                    if n.get("leida", 0) == 0:
                        if (uid is not None and n.get("usuario_id") == uid) or (ced is not None and str(n.get("cliente_cedula") or "").strip().upper() == ced):
                            n["leida"] = 1
                            count += 1
                return count

        if "UPDATE STOCK" in sql_clean:
            if "SET STOCK = %S WHERE PRODUCTO_CODIGO = %S AND SUCURSAL_ID = %S" in sql_clean:
                qty = int(params[0])
                cod = params[1]
                sid = int(params[2])
                updated = False
                for st in self.stock:
                    if st.get("producto_codigo") == cod and int(st.get("sucursal_id")) == sid:
                        st["stock"] = qty
                        updated = True
                        break
                if not updated:
                    self.stock.append({"producto_codigo": cod, "sucursal_id": sid, "stock": qty})
                return 1

        return 1

    def delete(self, db, sql, params=None):
        sql_upper = sql.upper().strip()
        params = params or ()

        if "DELETE FROM SERVICIO_MECANICO WHERE ID_SERVICIO_MECANICO = %S" in sql_upper:
            aid = int(params[0])
            if aid in self.servicio_mecanico:
                del self.servicio_mecanico[aid]
                self.comisiones_mecanico.pop(aid, None)
                return 1
            return 0

        if "DELETE FROM USUARIO_ROL WHERE USUARIO_ID = %S" in sql_upper:
            if "AND ROL_ID = %S" in sql_upper:
                uid, rid = int(params[0]), int(params[1])
                self.usuario_rol = [ur for ur in self.usuario_rol if not (ur["usuario_id"] == uid and ur["rol_id"] == rid)]
                return 1
            uid = int(params[0])
            self.usuario_rol = [ur for ur in self.usuario_rol if ur["usuario_id"] != uid]
            return 1

        if "DELETE FROM PERMISOS WHERE ROL_ID = %S" in sql_upper:
            rid = int(params[0])
            self.permisos = [p for p in self.permisos if p["rol_id"] != rid]
            return 1

        if "DELETE FROM MODULOS WHERE ID_MODULO = %S" in sql_upper:
            mid = int(params[0])
            if mid in self.modulos:
                del self.modulos[mid]
                return 1
            return 0

        if "DELETE FROM USUARIOS WHERE ID = %S" in sql_upper:
            uid = int(params[0])
            if uid in self.usuarios:
                del self.usuarios[uid]
                return 1
            return 0

        if "DELETE FROM STOCK" in sql_upper:
            if "AND SUCURSAL_ID = %S" in sql_upper:
                cod, sid = params[0], int(params[1])
                self.stock = [st for st in self.stock if not (st.get("producto_codigo") == cod and int(st.get("sucursal_id")) == sid)]
                return 1
            cod = params[0]
            self.stock = [st for st in self.stock if st.get("producto_codigo") != cod]
            return 1

        if "DELETE FROM SUCURSALES WHERE ID_SUCURSAL = %S" in sql_upper:
            sid = int(params[0])
            if sid in self.sucursales:
                self.sucursales[sid]["estado"] = 0
                return 1
            return 0

        if "DELETE FROM CATEGORIAS" in sql_upper:
            nom = params[0]
            if nom in self.categorias:
                self.categorias[nom]["estado"] = 0
                return 1
            return 0

        if "DELETE FROM MARCAS" in sql_upper:
            nom = params[0]
            if nom in self.marcas:
                self.marcas[nom]["estado"] = 0
                return 1
            return 0

        if "DELETE FROM NOTIFICACIONES" in sql_upper:
            if "WHERE ID_NOTIFICACION = %S" in sql_upper:
                nid = int(params[0])
                uid = int(params[1]) if len(params) > 1 and params[1] is not None else None
                ced = str(params[2]).strip().upper() if len(params) > 2 and params[2] else None
                self.notificaciones = [
                    n for n in self.notificaciones
                    if not (n.get("id_notificacion") == nid and (
                        (uid is None and ced is None) or
                        (uid is not None and n.get("usuario_id") == uid) or
                        (ced is not None and str(n.get("cliente_cedula") or "").strip().upper() == ced)
                    ))
                ]
                return 1
            if "INTERVAL" in sql_upper and "HOUR" in sql_upper:
                return 0
            if "LEIDA = 1" in sql_upper:
                self.notificaciones = [n for n in self.notificaciones if n.get("leida") != 1]
                return 1
            return 1

        return 0

    def execute_query(self, db, sql, params=None):
        return None


@pytest.fixture
def mock_db(monkeypatch):
    db = MockDatabase()

    monkeypatch.setattr(Connection, "fetch_one", lambda self, d, q, p=None: db.fetch_one(d, q, p))
    monkeypatch.setattr(Connection, "fetch_all", lambda self, d, q, p=None: db.fetch_all(d, q, p))
    monkeypatch.setattr(Connection, "insert", lambda self, d, q, p=None: db.insert(d, q, p))
    monkeypatch.setattr(Connection, "update", lambda self, d, q, p=None: db.update(d, q, p))
    monkeypatch.setattr(Connection, "delete", lambda self, d, q, p=None: db.delete(d, q, p))
    monkeypatch.setattr(Connection, "execute_query", lambda self, d, q, p=None: db.execute_query(d, q, p))

    monkeypatch.setattr(Connection, "con_transalca", lambda self: MockConnectionObj(db, "transalca"))
    monkeypatch.setattr(Connection, "con_mantenimiento", lambda self: MockConnectionObj(db, "mantenimiento"))
    monkeypatch.setattr(Connection, "begin_transaction", lambda self, d: MockConnectionObj(db, d))
    monkeypatch.setattr(Connection, "commit_transaction", lambda self, d: None)
    monkeypatch.setattr(Connection, "rollback_transaction", lambda self, d: None)

    monkeypatch.setattr(MailService, "send_recovery_email", lambda *a, **k: True)
    monkeypatch.setattr(MailService, "_send_mime_message", lambda *a, **k: True)

    return db


@pytest.fixture
def client(mock_db):
    flask_app.config["TESTING"] = True
    flask_app.config["SECRET_KEY"] = "integration-test-secret"
    with flask_app.test_client() as c:
        yield c


@pytest.fixture
def auth_client(client):
    with client.session_transaction() as sess:
        sess["user_id"] = 1
        sess["user_cedula"] = "V-10000000"
        sess["user_tipo"] = "admin"
        sess["roles"] = ["Administrador"]
        sess["permisos"] = {
            "modulos": {"crear": 1, "leer": 1, "actualizar": 1, "eliminar": 1},
            "usuarios": {"crear": 1, "leer": 1, "actualizar": 1, "eliminar": 1},
            "roles": {"crear": 1, "leer": 1, "actualizar": 1, "eliminar": 1},
            "bitacora": {"crear": 1, "leer": 1, "actualizar": 1, "eliminar": 1},
            "sucursales": {"crear": 1, "leer": 1, "actualizar": 1, "eliminar": 1},
            "productos": {"crear": 1, "leer": 1, "actualizar": 1, "eliminar": 1},
            "categorias": {"crear": 1, "leer": 1, "actualizar": 1, "eliminar": 1},
            "marcas": {"crear": 1, "leer": 1, "actualizar": 1, "eliminar": 1},
            "clientes": {"crear": 1, "leer": 1, "actualizar": 1, "eliminar": 1},
            "vehiculos": {"crear": 1, "leer": 1, "actualizar": 1, "eliminar": 1},
            "proveedores": {"crear": 1, "leer": 1, "actualizar": 1, "eliminar": 1},
            "ordenes_compra": {"crear": 1, "leer": 1, "actualizar": 1, "eliminar": 1},
            "tickets": {"crear": 1, "leer": 1, "actualizar": 1, "eliminar": 1},
            "notificaciones": {"crear": 1, "leer": 1, "actualizar": 1, "eliminar": 1},
        }
    return client


@pytest.fixture
def operator_client(client):
    with client.session_transaction() as sess:
        sess["user_id"] = 2
        sess["user_cedula"] = "V-20000000"
        sess["user_tipo"] = "empleado"
        sess["roles"] = ["Operador"]
        sess["permisos"] = {
            "modulos": {"crear": 0, "leer": 1, "actualizar": 0, "eliminar": 0},
            "usuarios": {"crear": 0, "leer": 1, "actualizar": 0, "eliminar": 0},
            "roles": {"crear": 0, "leer": 1, "actualizar": 0, "eliminar": 0},
            "bitacora": {"crear": 0, "leer": 1, "actualizar": 0, "eliminar": 0},
            "proveedores": {"crear": 0, "leer": 1, "actualizar": 0, "eliminar": 0},
            "ordenes_compra": {"crear": 0, "leer": 1, "actualizar": 0, "eliminar": 0},
            "tickets": {"crear": 0, "leer": 1, "actualizar": 0, "eliminar": 0},
            "notificaciones": {"crear": 0, "leer": 1, "actualizar": 0, "eliminar": 0},
        }
    return client

@pytest.fixture
def client_user_client(client):
    with client.session_transaction() as sess:
        sess["user_id"] = 4
        sess["user_cedula"] = "V-87654321"
        sess["user_tipo"] = "cliente"
        sess["roles"] = ["Cliente"]
        sess["permisos"] = {}
    return client
