from unittest.mock import MagicMock

import pytest
import requests

from model import bcv_rate_model, binance_rate_model
from model.bcv_rate_model import ScraperError, get_bcv_rates
from model.binance_rate_model import get_usdt_rate_ves

HTML_BCV = """
<html><body>
  <div class="centrado"><span>EUR</span><strong> 43,51234567 </strong></div>
  <div class="centrado"><span>USD</span><strong> 40,12345678 </strong></div>
</body></html>
"""


def _respuesta(texto="", json_data=None, status=200):
    respuesta = MagicMock()
    respuesta.text = texto
    respuesta.json.return_value = json_data
    if status >= 400:
        respuesta.raise_for_status.side_effect = requests.HTTPError(f"{status}")
    return respuesta


class TestBcv:

    def test_extrae_dolar_y_euro(self, mocker):
        get = mocker.patch("model.bcv_rate_model.requests.get", return_value=_respuesta(HTML_BCV))
        assert get_bcv_rates() == {"usd": 40.12345678, "eur": 43.51234567}
        assert get.call_args.args[0] == "https://www.bcv.org.ve"
        assert get.call_args.kwargs["timeout"] == 10

    def test_solo_las_monedas_pedidas(self, mocker):
        mocker.patch("model.bcv_rate_model.requests.get", return_value=_respuesta(HTML_BCV))
        assert get_bcv_rates(targets=["USD"]) == {"usd": 40.12345678}

    def test_moneda_ausente_lanza_error(self, mocker):
        html = '<div class="centrado"><span>USD</span><strong>40,1</strong></div>'
        mocker.patch("model.bcv_rate_model.requests.get", return_value=_respuesta(html))
        with pytest.raises(ScraperError, match="eur"):
            get_bcv_rates()

    @pytest.mark.parametrize("fallo", [requests.ConnectionError("sin red"), requests.Timeout("lento")])
    def test_error_de_red_lanza_scraper_error(self, mocker, fallo):
        mocker.patch("model.bcv_rate_model.requests.get", side_effect=fallo)
        with pytest.raises(ScraperError, match="No se pudo obtener"):
            get_bcv_rates()

    def test_error_http_lanza_scraper_error(self, mocker):
        mocker.patch("model.bcv_rate_model.requests.get", return_value=_respuesta("", status=503))
        with pytest.raises(ScraperError):
            get_bcv_rates()

    def test_pagina_sin_tasas(self, mocker):
        mocker.patch("model.bcv_rate_model.requests.get", return_value=_respuesta("<html><body>Mantenimiento</body></html>"))
        with pytest.raises(ScraperError, match="No se encontraron"):
            get_bcv_rates()

    def test_respaldo_por_posicion(self, mocker):
        bloques = "".join(f'<div class="centrado"><strong>{v}</strong></div>' for v in ("1,0", "2,0", "3,0", "4,0", "40,5", "43,5"))
        mocker.patch("model.bcv_rate_model.requests.get", return_value=_respuesta(bloques))
        assert get_bcv_rates() == {"usd": 40.5, "eur": 43.5}

    def test_sin_beautifulsoup(self, monkeypatch):
        monkeypatch.setattr(bcv_rate_model, "BeautifulSoup", None)
        with pytest.raises(ScraperError, match="beautifulsoup4"):
            get_bcv_rates()

    @pytest.mark.parametrize("texto, esperado", [("36,50", 36.5), ("1.234,56", 1234.56), ("Bs. 40,1234", 40.1234)])
    def test_numeros_con_formato_venezolano(self, texto, esperado):
        assert bcv_rate_model._normalize_number(texto) == esperado

    def test_texto_sin_numero(self):
        with pytest.raises(ValueError):
            bcv_rate_model._normalize_number("sin tasa")

    @pytest.mark.xfail(strict=True, reason="BUG-NET-01: get_bcv_rates usa verify=False por defecto (no verifica el certificado TLS del BCV)")
    def test_verifica_tls_por_defecto(self, mocker):
        get = mocker.patch("model.bcv_rate_model.requests.get", return_value=_respuesta(HTML_BCV))
        get_bcv_rates()
        assert get.call_args.kwargs["verify"] is True


class TestBinance:

    def _anuncios(self, *precios):
        return {"data": [{"adv": {"price": str(p)}} for p in precios]}

    def test_mediana_de_precios_unicos(self, mocker):
        post = mocker.patch("model.binance_rate_model.requests.post", return_value=_respuesta(json_data=self._anuncios(41, 42, 42, 45)))
        assert get_usdt_rate_ves() == 42.0
        cuerpo = post.call_args.kwargs["json"]
        assert (cuerpo["asset"], cuerpo["fiat"], cuerpo["tradeType"]) == ("USDT", "VES", "BUY")

    def test_mediana_con_cantidad_par(self, mocker):
        mocker.patch("model.binance_rate_model.requests.post", return_value=_respuesta(json_data=self._anuncios(40, 42, 44, 46)))
        assert get_usdt_rate_ves() == 43.0

    def test_ignora_precios_invalidos(self, mocker):
        datos = {"data": [{"adv": {"price": "abc"}}, {"adv": {}}, {"adv": {"price": "-5"}}, {"adv": {"price": "44"}}]}
        mocker.patch("model.binance_rate_model.requests.post", return_value=_respuesta(json_data=datos))
        assert get_usdt_rate_ves() == 44.0

    @pytest.mark.parametrize("datos", [{"data": []}, {"data": "error"}, {}, {"data": [{"adv": {"price": "0"}}]}])
    def test_sin_precios_devuelve_cero(self, mocker, datos):
        mocker.patch("model.binance_rate_model.requests.post", return_value=_respuesta(json_data=datos))
        assert get_usdt_rate_ves() == 0

    @pytest.mark.parametrize("fallo", [requests.ConnectionError("sin red"), ValueError("json invalido")])
    def test_errores_devuelven_cero(self, mocker, fallo):
        mocker.patch("model.binance_rate_model.requests.post", side_effect=fallo)
        assert get_usdt_rate_ves() == 0

    def test_error_http_devuelve_cero(self, mocker):
        mocker.patch("model.binance_rate_model.requests.post", return_value=_respuesta(status=429))
        assert get_usdt_rate_ves() == 0

    def test_mediana_auxiliar(self):
        assert binance_rate_model._median([]) == 0
        assert binance_rate_model._median([3, 1, 2]) == 2
