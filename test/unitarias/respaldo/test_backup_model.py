import pytest
import os
from unittest.mock import patch, MagicMock
from model.backup_model import BackupModel


@pytest.fixture
def model():
    """Instancia del modelo de respaldos para pruebas."""
    return BackupModel()


class TestBackupModelHelpers:
    """Pruebas unitarias con Data Provider (@pytest.mark.parametrize) para validaciones de seguridad de respaldos."""

    @pytest.mark.parametrize("identifier, is_safe", [
        ("db_transalca", True),
        ("mantenimiento_2026", True),
        ("tabla_usuarios", True),
        ("table; DROP TABLE", False),
        ("db-name", False),
        ("select * from", False),
        ("", False),
    ])
    def test_is_safe_identifier(self, model, identifier, is_safe):
        assert model._is_safe_identifier(identifier) == is_safe

    @pytest.mark.parametrize("filename, is_valid", [
        ("transalca_20260822_120000.sql", True),
        ("mantenimiento_backup.sql", True),
        ("../etc/passwd.sql", False),       # Path traversal
        ("malicioso.exe", False),           # Extensión no .sql
        ("invalido.txt", False),            # Extensión no .sql
        ("", False),                        # Nombre vacío
    ])
    def test_safe_backup_path(self, model, filename, is_valid):
        if is_valid:
            path = model._safe_backup_path(filename)
            assert path.endswith(filename)
        else:
            with pytest.raises(ValueError):
                model._safe_backup_path(filename)

    def test_quote_identifier(self, model):
        assert model._quote_identifier("usuarios") == "`usuarios`"
        with pytest.raises(ValueError):
            model._quote_identifier("usuarios; DROP TABLE")

    @pytest.mark.parametrize("header_text, is_valid", [
        ("-- Transalca backup\n-- Database: db_transalca", True),
        ("  -- Transalca backup\n-- Created: 2026", True),
        ("SELECT * FROM usuarios;\nDROP TABLE clientes;", False),
        ("DOCUMENTO DE TEXTO CUALQUIERA", False),
    ])
    def test_read_validated_backup_header(self, model, tmp_path, header_text, is_valid):
        test_file = tmp_path / "test_backup.sql"
        test_file.write_text(header_text, encoding="utf-8")

        if is_valid:
            content = model._read_validated_backup(str(test_file))
            assert "-- Transalca backup" in content
        else:
            with pytest.raises(ValueError) as exc_info:
                model._read_validated_backup(str(test_file))
            assert "no es un respaldo valido" in str(exc_info.value)


class TestBackupModelOperations:
    """Pruebas unitarias con mocks de sistema de archivos para creación y gestión de respaldos."""

    @patch("os.path.exists", return_value=True)
    @patch("os.listdir", return_value=["transalca_20260822_120000.sql"])
    @patch("os.path.getsize", return_value=1024)
    @patch("os.path.getmtime", return_value=1700000000)
    def test_list_backups(self, mock_mtime, mock_size, mock_listdir, mock_exists, model):
        backups = model.ejecutar("list_backups")
        assert len(backups) == 1
        assert backups[0]["filename"] == "transalca_20260822_120000.sql"
        assert backups[0]["size"] == 1024

    @patch("os.path.exists", return_value=True)
    @patch("os.remove")
    def test_delete_backup_success(self, mock_remove, mock_exists, model):
        result = model.ejecutar("delete_backup", "transalca_20260822_120000.sql")
        assert result is True
        mock_remove.assert_called_once()

    @patch("os.path.exists", return_value=False)
    def test_delete_backup_not_found(self, mock_exists, model):
        assert model.ejecutar("delete_backup", "transalca_20260822_120000.sql") is False

    @patch("os.path.exists", return_value=True)
    def test_get_backup_path_found(self, mock_exists, model):
        path = model.ejecutar("get_backup_path", "transalca_20260822_120000.sql")
        assert path is not None
        assert path.endswith("transalca_20260822_120000.sql")

    @patch("os.path.exists", return_value=False)
    def test_get_backup_path_not_found(self, mock_exists, model):
        assert model.ejecutar("get_backup_path", "transalca_20260822_120000.sql") is None

    def test_log_event(self, model):
        with patch.object(BackupModel, "insert", return_value=50) as mock_insert:
            log_id = model.ejecutar("log_event", 1, "CREAR", "RESPALDOS", "Respaldo manual creado", "127.0.0.1", 1)
            assert log_id == 50
            mock_insert.assert_called_once()

    @pytest.mark.parametrize("found, expected", [
        ({"1": 1}, True),
        (None, False),
    ])
    def test_has_backup_today(self, model, found, expected):
        with patch.object(BackupModel, "fetch_one", return_value=found):
            assert model.ejecutar("has_backup_today") is expected

    @pytest.mark.parametrize("found, expected", [
        ({"1": 1}, True),
        (None, False),
    ])
    def test_has_backup_last_days(self, model, found, expected):
        with patch.object(BackupModel, "fetch_one", return_value=found):
            assert model.ejecutar("has_backup_last_days", 7) is expected

    def test_cleanup_old_backups(self, model):
        with patch("os.path.exists", return_value=True), \
             patch("os.listdir", return_value=["transalca_old.sql"]), \
             patch("os.path.getmtime", return_value=0), \
             patch("os.remove") as mock_remove:
            removed = model.ejecutar("cleanup_old_backups", 1)
            assert removed == ["transalca_old.sql"]
            mock_remove.assert_called_once()

    def test_save_uploaded_backup_invalid_header(self, model):
        with patch.object(BackupModel, "_db_config_for_file", return_value={"database": "transalca"}):
            with pytest.raises(ValueError) as exc:
                model.ejecutar("save_uploaded_backup", "transalca_2026.sql", b"INVALID HEADER")
            assert "no es un respaldo valido" in str(exc.value)

    def test_ejecutar_invalid_action(self, model):
        with pytest.raises(ValueError) as exc_info:
            model.ejecutar("accion_inexistente")
        assert "Accion no permitida" in str(exc_info.value)
