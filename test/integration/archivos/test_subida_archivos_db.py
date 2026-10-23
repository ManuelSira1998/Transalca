import os
import uuid

import pytest

from helpers.api_client import unique_letters
from helpers.archivos import EJECUTABLE, PNG_1X1, SCRIPT_HTML, archivo, png

BUG_UPL_01 = pytest.mark.xfail(strict=True, reason="BUG-UPL-01: no se verifica el contenido; un ejecutable con nombre y tipo de imagen se guarda como imagen")
BUG_UPL_02 = pytest.mark.xfail(strict=True, reason="BUG-UPL-02: el carnet acepta el archivo si la extension O el tipo MIME parecen de imagen (deberian cumplirse ambos)")


def _archivos(carpeta):
    return sorted(p.name for p in carpeta.rglob("*") if p.is_file())


@pytest.fixture
def carpeta(tmp_path, monkeypatch):
    for modulo in ("profile_controller", "vehicle_controller", "category_controller", "product_controller", "order_controller"):
        monkeypatch.setattr(f"controller.{modulo}.UPLOAD_FOLDER", str(tmp_path))
    return tmp_path


@pytest.fixture
def vehiculo(cliente_a):
    placa = "F" + uuid.uuid4().hex[:6].upper()
    response = cliente_a.post("/api/vehicles/", json={
        "marca": "Kia", "modelo": "Rio", "anio": 2016, "placa": placa, "cliente_cedula": cliente_a.info["cedula"],
    })
    assert response.status_code == 201
    return placa


def _subir(cliente, url, campo, contenido, extra=None):
    data = dict(extra or {})
    data[campo] = contenido
    return cliente.post(url, data=data, content_type="multipart/form-data")


class TestFotoDePerfil:

    def test_imagen_valida_se_guarda_y_se_asocia_al_usuario(self, cliente_a, db, carpeta):
        response = _subir(cliente_a, "/api/profile/photo", "photo", png())
        assert response.status_code == 200
        nombre = response.get_json()["filename"]
        assert _archivos(carpeta) == [nombre]
        assert (carpeta / nombre).read_bytes() == PNG_1X1
        with db["mantenimiento"].cursor() as cursor:
            cursor.execute("SELECT foto_perfil FROM usuarios WHERE email = %s", (cliente_a.info["email"],))
            assert cursor.fetchone()["foto_perfil"] == nombre

    @pytest.mark.parametrize("contenido", [
        archivo(EJECUTABLE, "programa.exe", "application/x-msdownload"),
        archivo(PNG_1X1, "foto.png", "application/octet-stream"),
        archivo(SCRIPT_HTML, "foto.svg", "image/svg+xml"),
        archivo(SCRIPT_HTML, "pagina.html", "text/html"),
        archivo(PNG_1X1, "sin_extension", "image/png"),
        archivo(PNG_1X1, "", "image/png"),
    ])
    def test_archivos_no_permitidos_se_rechazan_sin_guardar(self, cliente_a, carpeta, contenido):
        assert _subir(cliente_a, "/api/profile/photo", "photo", contenido).status_code == 400
        assert _archivos(carpeta) == []

    def test_sin_archivo_devuelve_400(self, cliente_a, carpeta):
        assert cliente_a.post("/api/profile/photo", data={}, content_type="multipart/form-data").status_code == 400

    def test_nombre_con_ruta_no_sale_de_la_carpeta(self, cliente_a, carpeta):
        response = _subir(cliente_a, "/api/profile/photo", "photo", png("../../../app.png"))
        assert response.status_code == 200
        nombre = response.get_json()["filename"]
        assert "/" not in nombre and "\\" not in nombre and ".." not in nombre
        assert _archivos(carpeta) == [nombre]

    @BUG_UPL_01
    def test_ejecutable_disfrazado_de_imagen_se_rechaza(self, cliente_a, carpeta):
        response = _subir(cliente_a, "/api/profile/photo", "photo", archivo(EJECUTABLE, "foto.png", "image/png"))
        assert response.status_code == 400
        assert _archivos(carpeta) == []


class TestCarnetDelVehiculo:

    def test_imagen_valida_se_guarda_y_se_registra(self, cliente_a, db, carpeta, vehiculo):
        response = _subir(cliente_a, f"/api/vehicles/{vehiculo}/carnet", "imagen", png("carnet.png"))
        assert response.status_code == 200
        nombre = response.get_json()["filename"]
        assert nombre.startswith(f"carnet_{vehiculo}_") and nombre.endswith(".png")
        assert _archivos(carpeta) == [nombre]
        with db["transalca"].cursor() as cursor:
            cursor.execute("SELECT titulo_vehiculo FROM vehiculos WHERE placa_vehiculo = %s", (vehiculo,))
            assert cursor.fetchone()["titulo_vehiculo"] == nombre

    def test_html_se_rechaza(self, cliente_a, carpeta, vehiculo):
        response = _subir(cliente_a, f"/api/vehicles/{vehiculo}/carnet", "imagen", archivo(SCRIPT_HTML, "carnet.html", "text/html"))
        assert response.status_code == 400
        assert _archivos(carpeta) == []

    def test_no_se_puede_subir_al_vehiculo_de_otro(self, cliente_b, carpeta, vehiculo):
        assert _subir(cliente_b, f"/api/vehicles/{vehiculo}/carnet", "imagen", png()).status_code == 403
        assert _archivos(carpeta) == []

    @pytest.mark.parametrize("contenido", [
        pytest.param(archivo(EJECUTABLE, "programa.exe", "image/png"), marks=BUG_UPL_02),
        pytest.param(archivo(EJECUTABLE, "carnet.png", "application/x-msdownload"), marks=BUG_UPL_02),
        pytest.param(archivo(EJECUTABLE, "carnet.png", "image/png"), marks=BUG_UPL_01),
    ])
    def test_archivos_disfrazados_se_rechazan(self, cliente_a, carpeta, vehiculo, contenido):
        assert _subir(cliente_a, f"/api/vehicles/{vehiculo}/carnet", "imagen", contenido).status_code == 400
        assert _archivos(carpeta) == []


class TestImagenesDelCatalogo:

    def test_categoria_con_imagen_valida(self, admin, db, carpeta):
        nombre = "Categoria " + unique_letters()
        response = _subir(admin, "/api/categories/", "imagen", png(), {"nombre": nombre})
        assert response.status_code == 200
        archivos = _archivos(carpeta)
        assert len(archivos) == 1
        with db["transalca"].cursor() as cursor:
            cursor.execute("SELECT imagen_categoria FROM categorias WHERE nombre_categoria = %s", (nombre,))
            assert cursor.fetchone()["imagen_categoria"] == archivos[0]

    def test_categoria_con_imagen_mayor_a_2mb_se_rechaza(self, admin, db, carpeta):
        nombre = "Categoria " + unique_letters()
        grande = archivo(PNG_1X1 + b"\x00" * (2 * 1024 * 1024 + 10), "grande.png", "image/png")
        response = _subir(admin, "/api/categories/", "imagen", grande, {"nombre": nombre})
        assert response.status_code == 400
        assert _archivos(carpeta) == []
        with db["transalca"].cursor() as cursor:
            cursor.execute("SELECT COUNT(*) AS n FROM categorias WHERE nombre_categoria = %s", (nombre,))
            assert cursor.fetchone()["n"] == 0

    @pytest.mark.parametrize("contenido", [
        archivo(PNG_1X1, "animacion.gif", "image/gif"),
        archivo(EJECUTABLE, "programa.exe", "application/x-msdownload"),
        archivo(PNG_1X1, "foto.png", "text/plain"),
    ])
    def test_producto_con_imagen_no_permitida_no_se_crea(self, admin, db, carpeta, contenido):
        codigo = "TST-" + uuid.uuid4().hex[:6].upper()
        datos = {"codigo": codigo, "nombre": "Producto de prueba", "precio": "10.00",
                 "categoria": "Baterias", "marca": "15W40 / 20W50 SEMI SINTETICO FC GARRAFA", "sucursal_ids": "1"}
        response = _subir(admin, "/api/products/", "imagen", contenido, datos)
        assert response.status_code == 400
        assert "imagen" in response.get_json()["errors"]
        assert _archivos(carpeta) == []
        with db["transalca"].cursor() as cursor:
            cursor.execute("SELECT COUNT(*) AS n FROM productos WHERE codigo = %s", (codigo,))
            assert cursor.fetchone()["n"] == 0

    def test_producto_con_imagen_valida(self, admin, carpeta):
        codigo = "TST-" + uuid.uuid4().hex[:6].upper()
        datos = {"codigo": codigo, "nombre": "Producto de prueba", "precio": "10.00",
                 "categoria": "Baterias", "marca": "15W40 / 20W50 SEMI SINTETICO FC GARRAFA", "sucursal_ids": "1"}
        response = _subir(admin, "/api/products/", "imagen", png(), datos)
        assert response.status_code == 200, response.get_json()
        archivos = _archivos(carpeta)
        assert len(archivos) == 1 and archivos[0].startswith(f"prod_{codigo}")


class TestFotoDeMecanico:

    @pytest.fixture
    def directorio(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        return tmp_path

    def _datos(self):
        return {"cedula": "V-" + str(uuid.uuid4().int % 90000000 + 10000000), "nombre": "Pedro",
                "apellido": "Lopez", "telefono": "04141112233", "especialidad": "Frenos"}

    def test_foto_valida(self, admin, directorio):
        response = _subir(admin, "/api/mechanics/", "foto_perfil", png("perfil.png"), self._datos())
        assert response.status_code == 200
        assert len(_archivos(directorio / "public" / "assets" / "profile_pics")) == 1

    def test_foto_no_permitida(self, admin, directorio):
        contenido = archivo(EJECUTABLE, "perfil.exe", "application/x-msdownload")
        assert _subir(admin, "/api/mechanics/", "foto_perfil", contenido, self._datos()).status_code == 400
        assert not (directorio / "public").exists() or _archivos(directorio / "public") == []


class TestComprobanteDePago:

    @pytest.fixture
    def con_carrito(self, cliente_a, db):
        with db["transalca"].cursor() as cursor:
            cursor.execute("SELECT codigo FROM productos WHERE estado = 1 ORDER BY codigo LIMIT 1")
            codigo = cursor.fetchone()["codigo"]
        cliente_a.post("/api/orders/cart/add", json={"item_id": codigo, "cantidad": 1})
        return cliente_a

    def test_comprobante_pdf_se_acepta(self, con_carrito, carpeta):
        response = _subir(con_carrito, "/api/orders/checkout", "comprobante", archivo(b"%PDF-1.4\n%%EOF", "pago.pdf", "application/pdf"), {"metodo_pago": "efectivo"})
        assert response.status_code == 200
        assert len(_archivos(carpeta)) == 1

    @pytest.mark.parametrize("contenido", [
        archivo(PNG_1X1, "pago.png", "text/plain"),
        archivo(SCRIPT_HTML, "pago.html", "text/html"),
    ])
    def test_comprobante_no_permitido_no_crea_la_orden(self, con_carrito, db, carpeta, contenido):
        response = _subir(con_carrito, "/api/orders/checkout", "comprobante", contenido, {"metodo_pago": "efectivo"})
        assert response.status_code == 400
        assert _archivos(carpeta) == []
        assert con_carrito.get("/api/orders/cart").get_json()["data"] != []


class TestRespaldos:

    @pytest.fixture
    def carpeta_respaldos(self, tmp_path, monkeypatch):
        from controller import backup_controller
        monkeypatch.setattr(backup_controller.model, "backup_folder", str(tmp_path))
        return tmp_path

    def _nombre(self, test_databases):
        return f"{test_databases['transalca']}_20261023_120000.sql"

    def test_respaldo_valido_se_importa_en_la_carpeta(self, admin, carpeta_respaldos, test_databases):
        nombre = self._nombre(test_databases)
        contenido = archivo(b"-- Transalca backup\n-- Database: prueba\n", nombre, "application/sql")
        response = _subir(admin, "/api/backup/upload", "backup", contenido)
        assert response.status_code == 200
        assert response.get_json()["filename"] == nombre
        assert _archivos(carpeta_respaldos) == [nombre]

    def test_nombre_con_ruta_se_guarda_dentro_de_la_carpeta(self, admin, carpeta_respaldos, test_databases):
        nombre = self._nombre(test_databases)
        contenido = archivo(b"-- Transalca backup\n", "../../" + nombre, "application/sql")
        response = _subir(admin, "/api/backup/upload", "backup", contenido)
        assert response.status_code == 200
        assert _archivos(carpeta_respaldos) == [nombre]
        assert not os.path.exists(os.path.join(str(carpeta_respaldos.parent.parent), nombre))

    @pytest.mark.parametrize("nombre, contenido", [
        ("respaldo.txt", b"-- Transalca backup\n"),
        ("otra_base_20261023.sql", b"-- Transalca backup\n"),
        ("{db}_1.sql", b"DROP DATABASE prueba;"),
        ("{db}_2.sql", EJECUTABLE),
        ("{db}_3.sql", b""),
    ])
    def test_respaldos_invalidos_se_rechazan(self, admin, carpeta_respaldos, test_databases, nombre, contenido):
        nombre = nombre.format(db=test_databases["transalca"])
        response = _subir(admin, "/api/backup/upload", "backup", archivo(contenido, nombre, "application/sql"))
        assert response.status_code == 400
        assert _archivos(carpeta_respaldos) == []

    def test_sin_archivo_devuelve_400(self, admin, carpeta_respaldos):
        assert admin.post("/api/backup/upload", data={}, content_type="multipart/form-data").status_code == 400
