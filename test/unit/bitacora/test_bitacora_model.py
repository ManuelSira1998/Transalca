import pytest
from unittest.mock import patch
from app import app as flask_app
from model.bitacora_model import BitacoraModel


@pytest.fixture
def model():
    return BitacoraModel()


class TestBitacoraModelHelpers:

    @pytest.mark.parametrize("limit_input, expected_limit", [
        (50, 50),
        (200, 100),
        (-10, 1),
        ("30", 30),
        ("invalido", 100),
        ("", 100),
    ])
    def test_request_limit_data_provider(self, limit_input, expected_limit):
        from controller.bitacora_controller import _request_limit
        with flask_app.test_request_context(f"/?limit={limit_input}"):
            assert _request_limit() == expected_limit


class TestBitacoraModelDatabaseOperations:

    @patch.object(BitacoraModel, "fetch_all")
    def test_get_all(self, mock_fetch_all, model):
        mock_fetch_all.return_value = [
            {"id": 1, "usuario_id": 1, "nombre": "Admin", "apellido": "Sistema", "accion": "LOGIN", "modulo": "auth"}
        ]
        logs = model.ejecutar("get_all", 50, 0)

        assert len(logs) == 1
        assert logs[0]["accion"] == "LOGIN"
        mock_fetch_all.assert_called_once()

    @patch.object(BitacoraModel, "fetch_all")
    def test_get_by_user(self, mock_fetch_all, model):
        mock_fetch_all.return_value = [
            {"id": 1, "usuario_id": 5, "nombre": "Carlos", "apellido": "Mendoza", "accion": "UPDATE"}
        ]
        logs = model.ejecutar("get_by_user", 5, 50)

        assert len(logs) == 1
        assert logs[0]["usuario_id"] == 5

    @patch.object(BitacoraModel, "fetch_all")
    def test_get_by_module(self, mock_fetch_all, model):
        mock_fetch_all.return_value = [
            {"id": 2, "modulo": "clientes", "accion": "CREATE_CLIENT"}
        ]
        logs = model.ejecutar("get_by_module", "clientes", 50)

        assert len(logs) == 1
        assert logs[0]["modulo"] == "clientes"

    @patch.object(BitacoraModel, "fetch_all")
    def test_get_by_date_range(self, mock_fetch_all, model):
        mock_fetch_all.return_value = [
            {"id": 3, "fecha": "2026-08-01 10:00:00", "accion": "LOGIN"}
        ]
        logs = model.ejecutar("get_by_date_range", "2026-08-01", "2026-08-02")
        assert len(logs) == 1
        assert logs[0]["id"] == 3
        mock_fetch_all.assert_called_once()

    @patch.object(BitacoraModel, "insert")
    def test_log_action_custom_ip(self, mock_insert, model):
        mock_insert.return_value = 100
        log_id = model.ejecutar("log_action", 1, "INSERT", "proveedores", "Registro de nuevo proveedor", "192.168.1.10")

        assert log_id == 100
        mock_insert.assert_called_once()
        args = mock_insert.call_args[0]
        assert args[2] == (1, "INSERT", "proveedores", "Registro de nuevo proveedor", "192.168.1.10")

    @patch.object(BitacoraModel, "insert")
    def test_log_action_default_ip(self, mock_insert, model):
        mock_insert.return_value = 101
        log_id = model.ejecutar("log_action", 2, "DELETE", "usuarios", "Eliminar usuario")

        assert log_id == 101
        mock_insert.assert_called_once()
        args = mock_insert.call_args[0]
        assert args[2][4] == "127.0.0.1"

    @patch.object(BitacoraModel, "fetch_one")
    def test_count_all_returns_total(self, mock_fetch_one, model):
        mock_fetch_one.return_value = {"total": 250}
        total = model.ejecutar("count_all")
        assert total == 250

    @patch.object(BitacoraModel, "fetch_one")
    def test_count_all_returns_zero_when_none(self, mock_fetch_one, model):
        mock_fetch_one.return_value = None
        total = model.ejecutar("count_all")
        assert total == 0

    @patch.object(BitacoraModel, "fetch_all")
    def test_search(self, mock_fetch_all, model):
        mock_fetch_all.return_value = [
            {"id": 3, "accion": "DELETE", "modulo": "usuarios", "descripcion": "Eliminación de usuario"}
        ]
        results = model.ejecutar("search", "usuario")

        assert len(results) == 1
        assert results[0]["accion"] == "DELETE"

    def test_ejecutar_invalid_action(self, model):
        with pytest.raises(ValueError) as exc_info:
            model.ejecutar("accion_inexistente")

        assert "Accion no permitida" in str(exc_info.value)
