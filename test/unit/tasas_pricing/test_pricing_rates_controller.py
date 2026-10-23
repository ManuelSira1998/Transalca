import pytest

from app import app as flask_app
from controller import rates_controller
from model.pricing_model import PricingModel


@pytest.fixture
def client():
    flask_app.config["SECRET_KEY"] = "unit"
    with flask_app.test_client() as c:
        yield c


def _sesion(client, tipo):
    with client.session_transaction() as s:
        s.update(user_id=1, user_tipo=tipo, user_cedula="V-1", roles=[], permisos={})
    return client


@pytest.fixture
def tasa_activa(mocker):
    mocker.patch.object(PricingModel, "_get_active_rate", return_value={"id": 1, "monto": 40.0, "tipo": "bcv", "frozen": False})
    mocker.patch.object(PricingModel, "_get_all_settings", return_value={"margen_seguridad_pct": 0, "redondeo_bs": 0})


class TestCalcularPrecio:

    def test_calcula_precio_en_bolivares(self, client, tasa_activa):
        _sesion(client, "cliente")
        response = client.post("/api/pricing/calculate", json={"precio_usd": 10})
        assert response.status_code == 200
        data = response.get_json()["data"]
        assert data["precio_usd"] == 10.0
        assert data["precio_bs"] == 400.0
        assert data["tasa_base"] == 40.0

    def test_sin_precio_devuelve_400(self, client, tasa_activa):
        _sesion(client, "cliente")
        assert client.post("/api/pricing/calculate", json={}).status_code == 400

    def test_sin_tasa_disponible_devuelve_404(self, client, mocker):
        _sesion(client, "cliente")
        mocker.patch.object(PricingModel, "_get_active_rate", return_value=None)
        mocker.patch.object(PricingModel, "_get_all_settings", return_value={})
        assert client.post("/api/pricing/calculate", json={"precio_usd": 5}).status_code == 404

    @pytest.mark.parametrize("precio", ["abc", "", [], {"usd": 1}])
    @pytest.mark.xfail(strict=True, reason="BUG-PRC-01: /api/pricing/calculate no valida precio_usd; un valor no numerico responde 500")
    def test_precio_no_numerico_devuelve_400(self, client, tasa_activa, precio):
        _sesion(client, "cliente")
        assert client.post("/api/pricing/calculate", json={"precio_usd": precio}).status_code == 400

    @pytest.mark.parametrize("precio", [-10, 0])
    @pytest.mark.xfail(strict=True, reason="BUG-PRC-02: /api/pricing/calculate acepta precios negativos o cero")
    def test_precio_negativo_o_cero_devuelve_400(self, client, tasa_activa, precio):
        _sesion(client, "cliente")
        assert client.post("/api/pricing/calculate", json={"precio_usd": precio}).status_code == 400


class TestTasaManual:

    def test_cliente_no_puede_guardar_tasas(self, client, mocker):
        guardar = mocker.patch.object(PricingModel, "ejecutar")
        _sesion(client, "cliente")
        assert client.post("/api/pricing/rates/manual", json={"monto": 50}).status_code == 403
        guardar.assert_not_called()

    def test_empleado_guarda_tasa_manual(self, client, mocker):
        guardar = mocker.patch.object(PricingModel, "ejecutar")
        _sesion(client, "empleado")
        assert client.post("/api/pricing/rates/manual", json={"monto": "50.5"}).status_code == 200
        guardar.assert_called_once_with("save_rate", "interna", 50.5, "Manual admin")

    @pytest.mark.parametrize("payload", [{}, {"monto": 0}, {"monto": None}, {"monto": ""}])
    def test_sin_monto_devuelve_400(self, client, mocker, payload):
        mocker.patch.object(PricingModel, "ejecutar")
        _sesion(client, "empleado")
        assert client.post("/api/pricing/rates/manual", json=payload).status_code == 400

    @pytest.mark.xfail(strict=True, reason="BUG-PRC-03: /api/pricing/rates/manual no valida 'monto'; un texto provoca 500")
    def test_monto_no_numerico_devuelve_400(self, client, mocker):
        mocker.patch.object(PricingModel, "ejecutar")
        _sesion(client, "empleado")
        assert client.post("/api/pricing/rates/manual", json={"monto": "abc"}).status_code == 400

    @pytest.mark.xfail(strict=True, reason="BUG-PRC-03: /api/pricing/rates/manual guarda tasas negativas")
    def test_monto_negativo_no_se_guarda(self, client, mocker):
        guardar = mocker.patch.object(PricingModel, "ejecutar")
        _sesion(client, "empleado")
        assert client.post("/api/pricing/rates/manual", json={"monto": -40}).status_code == 400
        guardar.assert_not_called()


class TestTasasPublicas:

    @pytest.fixture(autouse=True)
    def _sin_cache(self):
        rates_controller._cache["data"] = None
        rates_controller._cache["timestamp"] = 0
        yield
        rates_controller._cache["data"] = None
        rates_controller._cache["timestamp"] = 0

    def test_tasas_publicas_sin_sesion(self, client, mocker):
        mocker.patch("model.bcv_rate_model.get_bcv_rates", return_value={"usd": 40.12346, "eur": 43.5})
        mocker.patch("model.binance_rate_model.get_usdt_rate_ves", return_value=45.678)
        response = client.get("/api/rates/")
        assert response.status_code == 200
        body = response.get_json()
        assert body["cached"] is False
        assert body["data"]["bcv"] == {"usd": 40.1235, "eur": 43.5, "error": None}
        assert body["data"]["binance"] == {"usdt_ves": 45.68, "error": None}
        assert client.get("/api/rates/").get_json()["cached"] is True

    def test_fallo_del_scraper_no_tumba_la_respuesta(self, client, mocker):
        mocker.patch("model.bcv_rate_model.get_bcv_rates", side_effect=RuntimeError("timeout"))
        mocker.patch("model.binance_rate_model.get_usdt_rate_ves", side_effect=RuntimeError("timeout"))
        response = client.get("/api/rates/")
        assert response.status_code == 200
        assert "timeout" not in response.get_data(as_text=True)

    @pytest.mark.xfail(strict=True, reason="BUG-NET-01: rates_controller consulta el BCV con verify=False (sin verificar el certificado TLS)")
    def test_consulta_al_bcv_verifica_tls(self, client, mocker):
        bcv = mocker.patch("model.bcv_rate_model.get_bcv_rates", return_value={"usd": 1, "eur": 1})
        mocker.patch("model.binance_rate_model.get_usdt_rate_ves", return_value=1)
        client.get("/api/rates/")
        assert bcv.call_args.kwargs.get("verify", True) is not False
