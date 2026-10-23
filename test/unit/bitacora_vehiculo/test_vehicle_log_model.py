from datetime import date, datetime, timedelta

import pytest

from model.vehicle_log_model import VehicleLogModel


@pytest.fixture
def modelo(mocker):
    m = VehicleLogModel()
    m.fetch_one = mocker.MagicMock(return_value=None)
    m.fetch_all = mocker.MagicMock(return_value=[])
    m.insert = mocker.MagicMock(return_value=10)
    m.update = mocker.MagicMock(return_value=1)
    return m


class TestPrioridad:

    @pytest.mark.parametrize("dias, prioridad, estado", [
        (-1, "critica", "vencida"), (0, "alta", "activa"), (14, "alta", "activa"),
        (15, "media", "activa"), (45, "media", "activa"), (46, "baja", "activa"),
    ])
    def test_limites_de_prioridad(self, modelo, dias, prioridad, estado):
        estimada = date.today() + timedelta(days=dias)
        modelo._upsert_prediction("ABC123", "aceite", date.today(), estimada, "ref", "base")
        valores = modelo.insert.call_args.args[2]
        assert valores[-2:] == (prioridad, estado)

    def test_prediccion_atendida_con_la_misma_fecha_no_se_toca(self, modelo):
        estimada = date.today() + timedelta(days=30)
        modelo.fetch_one.return_value = {"id": 5, "fecha_estimada": estimada, "estado": "atendida", "notificado": 1}
        assert modelo._upsert_prediction("ABC123", "aceite", date.today(), estimada, "ref", "base") == 5
        modelo.update.assert_not_called()
        modelo.insert.assert_not_called()

    def test_nueva_fecha_reinicia_la_notificacion(self, modelo):
        modelo.fetch_one.return_value = {"id": 5, "fecha_estimada": date.today(), "estado": "activa", "notificado": 1}
        modelo._upsert_prediction("ABC123", "aceite", date.today(), date.today() + timedelta(days=60), "ref", "base")
        assert modelo.update.call_args.args[2][6] == 1

    def test_misma_fecha_conserva_la_notificacion(self, modelo):
        estimada = date.today() + timedelta(days=60)
        modelo.fetch_one.return_value = {"id": 5, "fecha_estimada": estimada.isoformat(), "estado": "activa", "notificado": 1}
        modelo._upsert_prediction("ABC123", "aceite", date.today(), estimada, "ref", "base")
        assert modelo.update.call_args.args[2][6] == 0


class TestAuxiliares:

    @pytest.mark.parametrize("valor, esperado", [
        (None, None), ("", None), ("2026-10-23", date(2026, 10, 23)), ("2026-10-23 15:30:00", date(2026, 10, 23)),
        (datetime(2026, 10, 23, 8, 0), date(2026, 10, 23)), (date(2026, 1, 1), date(2026, 1, 1)), ("23/10/2026", None),
    ])
    def test_as_date(self, modelo, valor, esperado):
        assert modelo._as_date(valor) == esperado

    @pytest.mark.parametrize("fila, esperado", [(None, 6), ({"valor": "12"}, 12), ({"valor": "doce"}, 6), ({"valor": None}, 6)])
    def test_config_int(self, modelo, fila, esperado):
        modelo.fetch_one.return_value = fila
        assert modelo._config_int("vida_util_aceite_meses", 6) == esperado

    def test_placa_vacia_o_inexistente(self, modelo):
        assert modelo._vehicle_plate("") is None
        assert modelo._vehicle_plate("  abc123 ") is None
        assert modelo.fetch_one.call_args.args[2] == ("ABC123",)

    def test_sin_datos_de_servicio_no_consulta(self, modelo):
        assert modelo._service_mechanic_id({}) is None
        modelo.fetch_one.assert_not_called()
        assert modelo._service_mechanic_id({"servicio_mecanico_id": 7}) == 7

    def test_el_ciclo_no_se_cae_si_falla_un_paso(self, modelo, mocker):
        mocker.patch.object(VehicleLogModel, "_sync_from_services", side_effect=RuntimeError("bd caida"))
        mocker.patch("model.inventory_model.InventoryModel.ejecutar", return_value=3)
        assert modelo.ejecutar("run_automatic_cycle") == {"sincronizados": 0, "predicciones": 0, "notificaciones": 0, "stock_bajo": 3}

    def test_accion_no_permitida(self, modelo):
        with pytest.raises(ValueError):
            modelo.ejecutar("borrar")
