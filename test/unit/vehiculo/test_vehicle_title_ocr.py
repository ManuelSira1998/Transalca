import io

import pytest
from werkzeug.datastructures import FileStorage

from helpers.archivos import EJECUTABLE, PNG_1X1
from model import vehicle_title_ocr_model as ocr
from model.vehicle_title_ocr_model import OCRError, parse_vehicle_title_image


def _caja(x, y, ancho=160, alto=20):
    return [[x, y], [x + ancho, y], [x + ancho, y + alto], [x, y + alto]]


TITULO = [
    (_caja(10, 10), "PLACA: AB123CD", 0.95),
    (_caja(10, 40), "MARCA: TOYOTA", 0.93),
    (_caja(10, 70), "MODELO: COROLLA", 0.92),
    (_caja(10, 100), "AÑO: 2015", 0.9),
    (_caja(10, 130), "COLOR: GRIS PLATA", 0.9),
    (_caja(10, 160), "TIPO: SEDAN", 0.88),
    (_caja(10, 190), "COMBUSTIBLE: GASOLINA", 0.9),
    (_caja(10, 220), "SERIAL CARROCERIA: 8XA53ZEC5F2000123", 0.85),
    (_caja(10, 250), "CEDULA: V-12345678", 0.9),
]


def _imagen(contenido=PNG_1X1):
    return FileStorage(stream=io.BytesIO(contenido), filename="titulo.png", content_type="image/png")


@pytest.fixture
def motor(monkeypatch):
    def _usar(resultado):
        llamadas = []

        def falso(_arreglo):
            llamadas.append(1)
            if isinstance(resultado, Exception):
                raise resultado
            return resultado, None

        monkeypatch.setattr(ocr, "_OCR_ENGINE", falso)
        return llamadas
    return _usar


class TestNormalizadores:

    @pytest.mark.parametrize("texto, esperado", [
        ("AB123CD", "AB123CD"), ("ab 123 cd", "AB123CD"), ("Placa: A12-BC3", ""), ("AB-123-CD", "AB123CD"), ("", ""), (None, ""),
    ])
    def test_placa(self, texto, esperado):
        assert ocr._to_plate(texto) == esperado

    @pytest.mark.parametrize("texto, esperado", [
        ("2015", 2015), ("Año 1999 modelo", 1999), ("1949", None), ("3000", None), ("sin año", None), (None, None),
    ])
    def test_anio(self, texto, esperado):
        assert ocr._to_year(texto) == esperado

    @pytest.mark.parametrize("texto, esperado", [
        ("GASOLINA", "gasolina"), ("gas0lina", "gasolina"), ("GASOIL", "gasoil"), ("Diesel", "gasoil"),
        ("Otro", "otro"), ("electrico", ""), ("", ""),
    ])
    def test_combustible(self, texto, esperado):
        assert ocr._to_fuel(texto) == esperado

    @pytest.mark.parametrize("texto, esperado", [
        ("V-12345678", "V-12345678"), ("v 12345678", "V12345678"), ("12345678", "12345678"), ("12", ""),
    ])
    def test_cedula(self, texto, esperado):
        assert ocr._to_cedula(texto) == esperado

    @pytest.mark.parametrize("texto, esperado", [("8xa-53zec5f2000123", "8XA53ZEC5F2000123"), ("ABC12", "")])
    def test_vin(self, texto, esperado):
        assert ocr._to_vin(texto) == esperado

    def test_texto_legible(self):
        assert ocr._beautify_text("  gris   plata 4x4 ") == "Gris Plata 4x4"
        assert ocr._plain("  AÑO\t\tMODELO  ") == "ano modelo"
        assert ocr._strip_accents("Ñandú") == "Nandu"

    def test_recorta_en_la_siguiente_etiqueta(self):
        assert ocr._trim_with_next_labels("TOYOTA MODELO COROLLA") == "TOYOTA"

    @pytest.mark.parametrize("texto, es_etiqueta", [("placa", True), ("marca:", True), ("x", True), ("", True), ("toyota", False)])
    def test_reconoce_etiquetas(self, texto, es_etiqueta):
        assert ocr._looks_like_label(texto) is es_etiqueta

    def test_puntaje_de_alias(self):
        assert ocr._alias_match_score("placa", "placa") == 1.0
        assert ocr._alias_match_score("placa: ab123cd", "placa") == 0.95
        assert ocr._alias_match_score("la placa es", "placa") == 0.75
        assert ocr._alias_match_score("marca", "placa") == 0.0


class TestLecturaDelTitulo:

    def test_extrae_los_datos_principales(self, motor):
        motor(TITULO)
        datos, texto = parse_vehicle_title_image(_imagen())
        assert datos["placa"] == "AB123CD"
        assert datos["marca"] == "TOYOTA"
        assert datos["modelo"] == "COROLLA"
        assert datos["anio"] == 2015
        assert datos["color"] == "GRIS PLATA"
        assert datos["tipo_combustible"] == "gasolina"
        assert datos["vin"] == "8XA53ZEC5F2000123"
        assert datos["propietario_cedula"] == "V-12345678"
        assert "PLACA: AB123CD" in texto

    def test_etiqueta_y_valor_en_cajas_separadas(self, motor):
        motor([
            (_caja(10, 10, 60), "MARCA", 0.9), (_caja(90, 10, 100), "FORD", 0.9),
            (_caja(10, 50, 60), "PLACA", 0.9), (_caja(10, 75, 100), "XY987ZW", 0.9),
        ])
        datos, _ = parse_vehicle_title_image(_imagen())
        assert datos["marca"] == "FORD"
        assert datos["placa"] == "XY987ZW"

    def test_combustible_por_defecto_gasolina(self, motor):
        motor([(_caja(10, 10), "MARCA: FIAT", 0.9)])
        datos, _ = parse_vehicle_title_image(_imagen())
        assert datos["tipo_combustible"] == "gasolina"

    def test_detiene_la_busqueda_cuando_el_resultado_es_completo(self, motor):
        llamadas = motor(TITULO)
        parse_vehicle_title_image(_imagen())
        assert len(llamadas) < len(ocr._build_variants(ocr._read_as_rgb_array(_imagen())))

    def test_archivo_que_no_es_imagen(self, motor):
        motor(TITULO)
        with pytest.raises(OCRError, match="No se pudo abrir"):
            parse_vehicle_title_image(_imagen(EJECUTABLE))

    @pytest.mark.parametrize("resultado", [[], None, RuntimeError("fallo del motor")])
    def test_sin_texto_detectado(self, motor, resultado):
        motor(resultado)
        with pytest.raises(OCRError, match="No se detecto texto"):
            parse_vehicle_title_image(_imagen())

    def test_texto_sin_datos_del_vehiculo(self, motor):
        motor([(_caja(10, 10), "REPUBLICA BOLIVARIANA", 0.9)])
        with pytest.raises(OCRError, match="No se pudieron detectar datos"):
            parse_vehicle_title_image(_imagen())

    def test_entradas_vacias_o_incompletas_se_ignoran(self, motor):
        motor([None, [_caja(0, 0)], (_caja(0, 0), "   ", 0.9), (_caja(10, 10), "MARCA: KIA", "no-numero")])
        datos, _ = parse_vehicle_title_image(_imagen())
        assert datos["marca"] == "KIA"


class TestEndpointDeEscaneo:

    @pytest.fixture
    def cliente(self):
        from app import app
        app.config["SECRET_KEY"] = "unit"
        with app.test_client() as c:
            with c.session_transaction() as s:
                s.update(user_id=1, user_tipo="cliente", user_cedula="V-1")
            yield c

    def test_devuelve_los_datos_extraidos(self, cliente, mocker):
        mocker.patch("controller.vehicle_controller.parse_vehicle_title_image", return_value=({"placa": "AB123CD"}, "texto"))
        response = cliente.post("/api/vehicles/scan-title", data={"imagen": (io.BytesIO(PNG_1X1), "t.png", "image/png")},
                                content_type="multipart/form-data")
        assert response.status_code == 200
        assert response.get_json()["data"] == {"placa": "AB123CD"}

    def test_error_de_ocr_devuelve_400(self, cliente, mocker):
        mocker.patch("controller.vehicle_controller.parse_vehicle_title_image", side_effect=OCRError("No se detecto texto en la imagen"))
        response = cliente.post("/api/vehicles/scan-title", data={"imagen": (io.BytesIO(PNG_1X1), "t.png", "image/png")},
                                content_type="multipart/form-data")
        assert response.status_code == 400
        assert response.get_json()["message"] == "No se detecto texto en la imagen"

    def test_sin_imagen_o_archivo_no_permitido(self, cliente):
        assert cliente.post("/api/vehicles/scan-title", data={}, content_type="multipart/form-data").status_code == 400
        response = cliente.post("/api/vehicles/scan-title", data={"imagen": (io.BytesIO(b"x"), "doc.txt", "text/plain")},
                                content_type="multipart/form-data")
        assert response.status_code == 400
