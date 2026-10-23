from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from model import bcv_sync_model, pricing_model
from model.bcv_sync_model import BCVAutoSyncScheduler, sync_bcv_rate_if_needed
from model.pricing_model import PricingModel


def _caracas(hora, minuto=0):
    return datetime(2026, 10, 23, hora, minuto, tzinfo=bcv_sync_model.CARACAS_TZ)


@pytest.fixture
def tasas(monkeypatch):
    instancia = MagicMock()
    respuestas = {"get_by_date": None, "upsert_from_scraping": {"action": "inserted", "id": 77}}
    instancia.ejecutar.side_effect = lambda accion, *a, **k: respuestas[accion]
    monkeypatch.setattr(bcv_sync_model, "TasaCambioModel", lambda: instancia)
    instancia.respuestas = respuestas
    return instancia


@pytest.fixture
def bcv(mocker):
    return mocker.patch("model.bcv_rate_model.get_bcv_rates", return_value={"usd": 40.5})


class TestSincronizacionBcv:

    def test_antes_de_las_16_no_sincroniza(self, tasas, bcv):
        resultado = sync_bcv_rate_if_needed(now=_caracas(15, 59))
        assert resultado == {"synced": False, "action": "skipped", "reason": "before_schedule", "id": None, "fecha": "2026-10-23", "monto": None}
        tasas.ejecutar.assert_not_called()
        bcv.assert_not_called()

    def test_despues_de_las_16_guarda_la_tasa_del_dia(self, tasas, bcv):
        resultado = sync_bcv_rate_if_needed(now=_caracas(16, 5))
        assert resultado["synced"] is True
        assert (resultado["action"], resultado["id"], resultado["monto"]) == ("inserted", 77, 40.5)
        tasas.ejecutar.assert_any_call("upsert_from_scraping", 40.5, fecha="2026-10-23", fuente="BCV automatico")

    def test_usa_la_hora_de_caracas(self, tasas, bcv):
        assert sync_bcv_rate_if_needed(now=datetime(2026, 10, 23, 19, 30, tzinfo=timezone.utc))["reason"] == "before_schedule"
        assert sync_bcv_rate_if_needed(now=datetime(2026, 10, 23, 20, 30, tzinfo=timezone.utc))["synced"] is True

    def test_si_ya_hay_tasa_automatica_no_vuelve_a_consultar(self, tasas, bcv):
        tasas.respuestas["get_by_date"] = {"id": 5, "fuente": "BCV Automatico", "monto": "39.9"}
        resultado = sync_bcv_rate_if_needed(now=_caracas(17))
        assert (resultado["reason"], resultado["id"], resultado["monto"]) == ("already_synced", 5, 39.9)
        bcv.assert_not_called()

    def test_una_tasa_manual_se_reemplaza_por_la_oficial(self, tasas, bcv):
        tasas.respuestas["get_by_date"] = {"id": 5, "fuente": "Manual admin", "monto": "39.9"}
        assert sync_bcv_rate_if_needed(now=_caracas(17))["synced"] is True
        bcv.assert_called_once()

    def test_forzar_ignora_horario_y_tasa_existente(self, tasas, bcv):
        tasas.respuestas["get_by_date"] = {"id": 5, "fuente": "BCV automatico", "monto": "39.9"}
        assert sync_bcv_rate_if_needed(force=True, now=_caracas(8))["synced"] is True

    @pytest.mark.parametrize("respuesta", [{"usd": 0}, {}, {"usd": None}])
    def test_tasa_invalida_lanza_error(self, tasas, bcv, respuesta):
        bcv.return_value = respuesta
        with pytest.raises(ValueError):
            sync_bcv_rate_if_needed(now=_caracas(17))

    def test_bloqueo_ocupado(self, tasas, bcv):
        tasas.respuestas["upsert_from_scraping"] = {"action": "lock_busy"}
        resultado = sync_bcv_rate_if_needed(now=_caracas(17))
        assert (resultado["synced"], resultado["reason"]) == (False, "lock_busy")

    def test_monto_existente_no_numerico(self, tasas, bcv):
        tasas.respuestas["get_by_date"] = {"id": 5, "fuente": "BCV automatico", "monto": "n/d"}
        assert sync_bcv_rate_if_needed(now=_caracas(17))["monto"] is None


class TestProgramadorBcv:

    def test_intervalo_minimo(self):
        assert BCVAutoSyncScheduler(interval_seconds=1).interval_seconds == 30

    def test_solo_corre_una_vez_al_dia_despues_de_las_16(self, monkeypatch):
        llamadas = []
        monkeypatch.setattr(bcv_sync_model, "sync_bcv_rate_if_needed", lambda **k: llamadas.append(k) or {"synced": True})
        horas = iter([_caracas(16, 0), _caracas(16, 1), _caracas(18)])

        class Reloj(datetime):
            @classmethod
            def now(cls, tz=None):
                return next(horas)

        monkeypatch.setattr(bcv_sync_model, "datetime", Reloj)
        programador = BCVAutoSyncScheduler()
        programador._run_once()
        assert llamadas == []
        programador._run_once()
        programador._run_once()
        assert len(llamadas) == 1
        assert llamadas[0]["force"] is True

    def test_un_error_no_detiene_el_programador(self, monkeypatch):
        monkeypatch.setattr(bcv_sync_model, "sync_bcv_rate_if_needed", MagicMock(side_effect=RuntimeError("sin red")))

        class Reloj(datetime):
            @classmethod
            def now(cls, tz=None):
                return _caracas(17)

        monkeypatch.setattr(bcv_sync_model, "datetime", Reloj)
        programador = BCVAutoSyncScheduler()
        programador._run_once()
        assert programador._last_completed_date is None

    def test_no_arranca_dos_hilos(self):
        programador = BCVAutoSyncScheduler(interval_seconds=3600)
        try:
            assert programador.start() is True
            assert programador.start() is False
        finally:
            programador.stop()
            programador._thread.join(timeout=5)
        assert not programador._thread.is_alive()


@pytest.fixture
def modelo(mocker):
    m = PricingModel()
    m.fetch_one = mocker.MagicMock(return_value=None)
    m.fetch_all = mocker.MagicMock(return_value=[])
    m.insert = mocker.MagicMock(return_value=1)
    m.update = mocker.MagicMock(return_value=1)
    return m


def _reloj(monkeypatch, momento):
    class Reloj(datetime):
        @classmethod
        def now(cls, tz=None):
            return momento
    monkeypatch.setattr(pricing_model, "datetime", Reloj)


class TestCalculoDePrecios:

    @pytest.mark.parametrize("precio, margen, redondeo, esperado", [
        (10, 0, 0, 400.0),
        (10, 3, 0, 412.0),
        (10.33, 3, 0.5, 426.0),
        (1, 0, 1, 40.0),
        (0.01, 0, 0, 0.4),
    ])
    def test_precio_en_bolivares(self, modelo, mocker, precio, margen, redondeo, esperado):
        mocker.patch.object(PricingModel, "_get_active_rate", return_value={"id": 1, "monto": 40.0, "tipo": "bcv", "frozen": False})
        mocker.patch.object(PricingModel, "_get_all_settings", return_value={"margen_seguridad_pct": margen, "redondeo_bs": redondeo})
        resultado = modelo.ejecutar("calculate_price_bs", precio)
        assert resultado["precio_bs"] == pytest.approx(esperado)
        assert resultado["tasa_base"] == 40.0
        assert resultado["margen_pct"] == float(margen)

    def test_sin_tasa_devuelve_none(self, modelo, mocker):
        mocker.patch.object(PricingModel, "_get_active_rate", return_value=None)
        assert modelo.ejecutar("calculate_price_bs", 10) is None

    def test_accion_no_permitida(self, modelo):
        with pytest.raises(ValueError):
            modelo.ejecutar("borrar_todo")


class TestTasaActiva:

    def _config(self, modelo, **valores):
        base = {"tasa_referencia_activa": "bcv", "hora_congelamiento": "16:00"}
        base.update(valores)
        modelo.fetch_all.return_value = [{"clave": k, "valor": v} for k, v in base.items()] + [{"clave": "otra", "valor": "x"}]

    def test_despues_del_congelamiento_usa_la_tasa_del_dia(self, modelo, monkeypatch):
        self._config(modelo)
        _reloj(monkeypatch, datetime(2026, 10, 23, 17, 0))
        modelo.fetch_one.return_value = {"id": 9, "monto": "41.5", "fecha": "2026-10-23"}
        tasa = modelo.ejecutar("get_active_rate")
        assert tasa == {"id": 9, "monto": 41.5, "tipo": "bcv", "frozen": True, "fecha": "2026-10-23"}

    def test_antes_del_congelamiento_usa_la_ultima_tasa(self, modelo, monkeypatch):
        self._config(modelo)
        _reloj(monkeypatch, datetime(2026, 10, 23, 9, 0))
        modelo.fetch_one.return_value = {"id": 8, "monto": "40", "fecha": "2026-10-22"}
        assert modelo.ejecutar("get_active_rate")["frozen"] is False

    def test_hora_de_congelamiento_invalida(self, modelo, monkeypatch):
        self._config(modelo, hora_congelamiento="tarde")
        _reloj(monkeypatch, datetime(2026, 10, 23, 17, 0))
        modelo.fetch_one.return_value = {"id": 8, "monto": "40", "fecha": "2026-10-22"}
        assert modelo.ejecutar("get_active_rate")["frozen"] is False

    def test_sin_tasas(self, modelo, monkeypatch):
        self._config(modelo)
        _reloj(monkeypatch, datetime(2026, 10, 23, 9, 0))
        assert modelo.ejecutar("get_active_rate") is None

    def test_configuracion_filtra_claves_desconocidas(self, modelo):
        self._config(modelo)
        assert "otra" not in modelo.ejecutar("get_all_settings")


class TestActualizacionDeTasas:

    @pytest.mark.parametrize("actual, nueva, esperado", [
        (None, 40.0, True), ({"monto": "0"}, 40.0, True), ({"monto": "40"}, 40.5, False), ({"monto": "40"}, 41.0, True), ({"monto": "40"}, 39.0, True),
    ])
    def test_banda_de_variacion(self, modelo, mocker, actual, nueva, esperado):
        mocker.patch.object(PricingModel, "_get_all_settings", return_value={"banda_variacion_pct": 2})
        mocker.patch.object(PricingModel, "_get_latest_rate", return_value=actual)
        assert modelo.ejecutar("should_update_rate", nueva) is esperado

    def test_guardar_tasa_actualiza_la_del_dia(self, modelo, mocker):
        mocker.patch.object(PricingModel, "_get_rate_by_type", return_value={"id": 4})
        modelo.ejecutar("save_rate", "bcv", "41.2", "Manual")
        modelo.update.assert_called_once()
        assert modelo.update.call_args.args[2] == (41.2, "Manual", 4)
        modelo.insert.assert_not_called()

    def test_guardar_tasa_nueva(self, modelo, mocker):
        mocker.patch.object(PricingModel, "_get_rate_by_type", return_value=None)
        modelo.ejecutar("save_rate", "usdt", 45, "Binance")
        assert modelo.insert.call_args.args[2][1:] == ("usdt", 45.0, "Binance")

    def test_configuracion_existente_se_actualiza_y_nueva_se_inserta(self, modelo):
        modelo.fetch_one.return_value = {"clave": "redondeo_bs"}
        modelo.ejecutar("update_setting", "redondeo_bs", "1")
        modelo.update.assert_called_once()
        modelo.fetch_one.return_value = None
        modelo.ejecutar("update_setting", "nueva", "x")
        modelo.insert.assert_called_once()
