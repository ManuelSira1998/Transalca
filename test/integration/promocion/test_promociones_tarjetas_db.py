from datetime import date, timedelta

import pytest

from helpers.api_client import unique_letters
from helpers.archivos import EJECUTABLE, archivo, png


def _promo(**overrides):
    data = {
        "nombre": "Promo " + unique_letters(),
        "descripcion": "Cambio de aceite gratis",
        "tipo": "puntos",
        "puntos_requeridos": 3,
        "recompensa": "Un cambio de aceite",
        "fecha_inicio": date.today().isoformat(),
        "fecha_fin": (date.today() + timedelta(days=60)).isoformat(),
    }
    data.update(overrides)
    return data


@pytest.fixture
def promocion(admin):
    response = admin.post("/api/promotions/", json=_promo())
    assert response.status_code == 200, response.get_json()
    return response.get_json()["id"]


@pytest.fixture
def tarjeta(admin, cliente_a, promocion):
    response = admin.post("/api/promotions/assign-card", json={"cliente_cedula": cliente_a.info["cedula"], "promocion_id": promocion})
    assert response.status_code == 200, response.get_json()
    return response.get_json()["id"]


class TestPromociones:

    def test_crear_y_consultar(self, admin, promocion):
        datos = admin.get(f"/api/promotions/{promocion}").get_json()["data"]
        assert int(datos["puntos_requeridos"]) == 3

    @pytest.mark.parametrize("campo, valor", [
        ("nombre", ""), ("nombre", "ab"), ("tipo", "regalo"), ("tipo", ""),
        ("puntos_requeridos", -1), ("puntos_requeridos", "tres"), ("puntos_requeridos", 1000000),
        ("fecha_inicio", "23/10/2026"), ("fecha_fin", "mañana"),
        pytest.param("puntos_requeridos", 0, marks=pytest.mark.xfail(
            strict=True, reason="BUG-PROMO-01: puntos_requeridos 0 se convierte en 1 sin error (data.get(...) or 1)")),
        ("fecha_fin", "2026-02-30"),
    ])
    def test_datos_invalidos_devuelven_400(self, admin, campo, valor):
        response = admin.post("/api/promotions/", json=_promo(**{campo: valor}))
        assert response.status_code == 400
        assert campo in response.get_json()["errors"]

    def test_fecha_fin_anterior_al_inicio(self, admin):
        response = admin.post("/api/promotions/", json=_promo(fecha_inicio="2026-12-01", fecha_fin="2026-11-01"))
        assert response.status_code == 400
        assert "fecha_fin" in response.get_json()["errors"]

    def test_promocion_inexistente(self, admin):
        assert admin.get("/api/promotions/99999999").status_code == 404

    def test_cliente_no_crea_promociones(self, cliente_a):
        assert cliente_a.post("/api/promotions/", json=_promo()).status_code == 403


class TestTarjetasDePuntos:

    def test_asignar_dos_veces_devuelve_la_misma_tarjeta(self, admin, cliente_a, promocion, tarjeta):
        response = admin.post("/api/promotions/assign-card", json={"cliente_cedula": cliente_a.info["cedula"], "promocion_id": promocion})
        assert response.get_json()["id"] == tarjeta

    def test_acumular_puntos_hasta_canjear(self, admin, tarjeta):
        resultados = [admin.post(f"/api/promotions/cards/{tarjeta}/add-point", json={"descripcion": "Visita"}).get_json()["data"] for _ in range(3)]
        assert resultados == [
            {"puntos_acumulados": 1, "canjeada": 0},
            {"puntos_acumulados": 2, "canjeada": 0},
            {"puntos_acumulados": 3, "canjeada": 1},
        ]
        assert admin.post(f"/api/promotions/cards/{tarjeta}/add-point", json={}).status_code == 400
        historial = admin.get(f"/api/promotions/cards/{tarjeta}/history").get_json()["data"]
        assert len(historial) == 3

    def test_el_cliente_ve_su_tarjeta_con_puntos(self, admin, cliente_a, tarjeta):
        admin.post(f"/api/promotions/cards/{tarjeta}/add-point", json={})
        mias = cliente_a.get("/api/promotions/cards/my").get_json()["data"]
        assert tarjeta in [t["id"] for t in mias]
        assert cliente_a.get(f"/api/promotions/cards/{tarjeta}").status_code == 200
        assert cliente_a.get(f"/api/promotions/cards/{tarjeta}/history").status_code == 200

    def test_otro_cliente_no_ve_la_tarjeta(self, admin, cliente_a, cliente_b, tarjeta):
        admin.post(f"/api/promotions/cards/{tarjeta}/add-point", json={})
        assert cliente_b.get(f"/api/promotions/cards/{tarjeta}").status_code == 403
        assert cliente_b.get(f"/api/promotions/cards/{tarjeta}/history").status_code == 403
        assert cliente_b.get(f"/api/promotions/cards/client/{cliente_a.info['cedula']}").status_code == 403
        assert tarjeta not in [t["id"] for t in cliente_b.get("/api/promotions/cards/my").get_json()["data"]]

    def test_el_cliente_no_puede_sumarse_puntos(self, cliente_a, tarjeta):
        assert cliente_a.post(f"/api/promotions/cards/{tarjeta}/add-point", json={}).status_code == 403

    def test_tarjeta_inexistente(self, admin):
        assert admin.post("/api/promotions/cards/99999999/add-point", json={}).status_code == 400

    @pytest.mark.parametrize("payload", [{}, {"cliente_cedula": "V-12345678"}, {"promocion_id": 1}])
    def test_asignacion_incompleta(self, admin, payload):
        assert admin.post("/api/promotions/assign-card", json=payload).status_code == 400

    def test_asignar_a_cliente_inexistente(self, admin, promocion):
        response = admin.post("/api/promotions/assign-card", json={"cliente_cedula": "V-00000999", "promocion_id": promocion})
        assert response.status_code == 400

    @pytest.mark.xfail(strict=True, reason="BUG-PROMO-02: assign-card no verifica que la promocion exista; la FK falla y responde 500")
    def test_asignar_a_promocion_inexistente(self, admin, cliente_a):
        response = admin.post("/api/promotions/assign-card", json={"cliente_cedula": cliente_a.info["cedula"], "promocion_id": 99999999})
        assert response.status_code == 400


class TestImagenDePromocion:

    @pytest.fixture
    def carpeta(self, tmp_path, monkeypatch):
        monkeypatch.setattr("controller.promotion_controller.UPLOAD_FOLDER", str(tmp_path))
        return tmp_path

    def test_imagen_valida(self, admin, promocion, carpeta):
        response = admin.post(f"/api/promotions/{promocion}/image", data={"image": png()}, content_type="multipart/form-data")
        assert response.status_code == 200
        assert [p.name for p in carpeta.iterdir()] == [response.get_json()["filename"]]

    def test_imagen_no_permitida(self, admin, promocion, carpeta):
        contenido = archivo(EJECUTABLE, "promo.exe", "application/x-msdownload")
        response = admin.post(f"/api/promotions/{promocion}/image", data={"image": contenido}, content_type="multipart/form-data")
        assert response.status_code == 400
        assert list(carpeta.iterdir()) == []

    def test_reemplazar_la_imagen_borra_la_anterior(self, admin, promocion, carpeta):
        admin.post(f"/api/promotions/{promocion}/image", data={"image": png("a.png")}, content_type="multipart/form-data")
        segunda = admin.post(f"/api/promotions/{promocion}/image", data={"image": png("b.png")}, content_type="multipart/form-data")
        assert [p.name for p in carpeta.iterdir()] == [segunda.get_json()["filename"]]
