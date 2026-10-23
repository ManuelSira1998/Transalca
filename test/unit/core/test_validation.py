from decimal import Decimal, InvalidOperation
from unittest.mock import patch

import pytest

from config.validation import (
    LoginThrottle,
    RecoveryThrottle,
    ValidationError,
    clean_string,
    has_unsafe_content,
    normalize_cedula,
    normalize_decimal,
    normalize_email,
    normalize_int,
    normalize_phone,
    normalize_rif,
    optional_text,
    raise_if_errors,
    require_text,
    safe_display,
    validate_choice,
)


class TestTextoBasico:

    @pytest.mark.parametrize("valor, esperado", [(None, ""), ("  hola ", "hola"), (123, "123"), (False, "False"), ("", "")])
    def test_clean_string(self, valor, esperado):
        assert clean_string(valor) == esperado

    @pytest.mark.parametrize("valor", [
        "<script>alert(1)</script>",
        "< script >",
        "<img src=x onerror=alert(1)>",
        "texto onclick=hacer()",
        "javascript:alert(1)",
        "data:text/html;base64,AAAA",
        "<b>negrita</b>",
    ])
    def test_has_unsafe_content_detecta_html_y_scripts(self, valor):
        assert has_unsafe_content(valor) is True

    @pytest.mark.parametrize("valor", ["Cauchos 205/55 R16", "María José", "precio < 10", "", None, "🚗 Toyota"])
    def test_has_unsafe_content_acepta_texto_normal(self, valor):
        assert has_unsafe_content(valor) is False

    def test_safe_display_escapa_html(self):
        assert safe_display(' <a href="x">\'') == "&lt;a href=&quot;x&quot;&gt;&#x27;"

    def test_raise_if_errors(self):
        raise_if_errors({})
        with pytest.raises(ValidationError) as exc:
            raise_if_errors({"campo": "malo"})
        assert exc.value.errors == {"campo": "malo"}
        assert exc.value.message


class TestRequireText:

    def test_valor_valido_se_recorta(self):
        errors = {}
        assert require_text(errors, "nombre", "  Ana  ", "El nombre") == "Ana"
        assert errors == {}

    @pytest.mark.parametrize("valor, fragmento", [
        ("", "obligatorio"),
        ("   ", "obligatorio"),
        (None, "obligatorio"),
        ("a", "al menos"),
        ("x" * 11, "no puede superar"),
        ("<b>x</b>", "no permitidos"),
    ])
    def test_valores_invalidos(self, valor, fragmento):
        errors = {}
        assert require_text(errors, "f", valor, "El campo", min_len=2, max_len=10) == ""
        assert fragmento in errors["f"]

    @pytest.mark.parametrize("valor", ["Ana2", "José_Luis", "Ana  Maria", "123"])
    def test_person_solo_letras(self, valor):
        errors = {}
        require_text(errors, "nombre", valor, "El nombre", person=True)
        assert "solo puede contener letras" in errors["nombre"]

    @pytest.mark.parametrize("valor", ["María", "José Luis", "O'Brien", "Ana-María", "Ñandú"])
    def test_person_acepta_nombres_reales(self, valor):
        errors = {}
        assert require_text(errors, "nombre", valor, "El nombre", person=True) == valor
        assert errors == {}

    def test_rechaza_texto_con_forma_de_serial_salvo_que_se_permita(self):
        errors = {}
        require_text(errors, "f", "ABC12345", "El campo")
        assert "serial" in errors["f"]
        errors = {}
        assert require_text(errors, "f", "ABC12345", "El campo", allow_serial=True) == "ABC12345"


class TestOptionalText:

    @pytest.mark.parametrize("valor", [None, "", "   "])
    def test_vacio_es_valido(self, valor):
        errors = {}
        assert optional_text(errors, "d", valor, "La direccion") == ""
        assert errors == {}

    def test_longitud_maxima(self):
        errors = {}
        assert optional_text(errors, "d", "x" * 40, "La direccion", max_len=40) == "x" * 40
        optional_text(errors, "d", "x" * 41, "La direccion", max_len=40)
        assert "no puede superar" in errors["d"]


class TestTelefonoYCorreo:

    @pytest.mark.parametrize("valor, esperado", [
        ("04141234567", "04141234567"),
        ("0414-123-4567", "04141234567"),
        ("(0414) 123 4567", "04141234567"),
    ])
    def test_telefono_valido_se_normaliza(self, valor, esperado):
        errors = {}
        assert normalize_phone(errors, valor) == esperado
        assert errors == {}

    @pytest.mark.parametrize("valor", ["0214123456", "0414123456", "041412345678", "04141234abc", "+584141234567", "1234"])
    def test_telefono_invalido(self, valor):
        errors = {}
        assert normalize_phone(errors, valor) == ""
        assert "telefono" in errors

    def test_telefono_opcional(self):
        errors = {}
        assert normalize_phone(errors, "", required=False) == ""
        assert errors == {}
        normalize_phone(errors, "")
        assert "obligatorio" in errors["telefono"]

    @pytest.mark.parametrize("valor, esperado", [
        ("  Ana@Correo.COM ", "ana@correo.com"),
        ("a.b+c@sub.dominio.co", "a.b+c@sub.dominio.co"),
    ])
    def test_correo_valido_se_normaliza(self, valor, esperado):
        errors = {}
        assert normalize_email(errors, valor) == esperado
        assert errors == {}

    @pytest.mark.parametrize("valor", [
        "sin-arroba", "a@b", "a@b.c", "@dominio.com", "a b@c.com", "a@dominio.com<script>",
        "x" * 141 + "@correo.com", "ana@correo.com' OR '1'='1",
    ])
    def test_correo_invalido(self, valor):
        errors = {}
        assert normalize_email(errors, valor) == ""
        assert errors["email"] == "Ingrese un correo valido."


class TestDocumentos:

    @pytest.mark.parametrize("data, esperado", [
        ({"cedula": "V-12345678"}, ("V-12345678", "V", "12345678")),
        ({"cedula": "v12.345.678"}, ("V-12345678", "V", "12345678")),
        ({"cedula": "E-1234567"}, ("E-1234567", "E", "1234567")),
        ({"cedula_prefijo": "v", "cedula_numero": "12345678"}, ("V-12345678", "V", "12345678")),
    ])
    def test_cedula_valida(self, data, esperado):
        errors = {}
        assert normalize_cedula(errors, data) == esperado
        assert errors == {}

    @pytest.mark.parametrize("data", [
        {"cedula": "12345678"}, {"cedula": "X-12345678"}, {"cedula": "V-123456"},
        {"cedula": "V-123456789"}, {"cedula": "V-abc"}, {"cedula": "V"},
    ])
    def test_cedula_invalida(self, data):
        errors = {}
        assert normalize_cedula(errors, data) == ("", "", "")
        assert "cedula" in errors

    def test_cedula_obligatoria_u_opcional(self):
        errors = {}
        normalize_cedula(errors, {})
        assert errors["cedula"] == "La cedula es obligatoria."
        errors = {}
        assert normalize_cedula(errors, {}, required=False) == ("", "", "")
        assert errors == {}

    @pytest.mark.parametrize("raw, esperado", [("J-12345678-9", "J-12345678-9"), ("g123456789", "G-12345678-9")])
    def test_rif_valido(self, raw, esperado):
        errors = {}
        assert normalize_rif(errors, {"rif": raw})[0] == esperado
        assert errors == {}

    @pytest.mark.parametrize("raw", ["J-1234567-8", "X-12345678-9", "J-1234567890", ""])
    def test_rif_invalido(self, raw):
        errors = {}
        normalize_rif(errors, {"rif": raw})
        assert "rif" in errors


class TestNumeros:

    @pytest.mark.parametrize("valor, esperado", [("10", Decimal("10")), ("0.01", Decimal("0.01")), (99.5, Decimal("99.5"))])
    def test_decimal_valido(self, valor, esperado):
        errors = {}
        assert normalize_decimal(errors, "precio", valor, "El precio") == esperado
        assert errors == {}

    @pytest.mark.parametrize("valor", ["abc", "", None, "0", "-1", "0.001", "100000000", "1,5", "Infinity"])
    def test_decimal_invalido(self, valor):
        errors = {}
        assert normalize_decimal(errors, "precio", valor, "El precio") is None
        assert "precio" in errors

    @pytest.mark.xfail(strict=True, raises=InvalidOperation, reason="BUG-VAL-01: normalize_decimal('NaN') lanza InvalidOperation al comparar en vez de registrar un error de validacion")
    def test_decimal_nan_es_error_de_validacion(self):
        errors = {}
        assert normalize_decimal(errors, "precio", "NaN", "El precio") is None
        assert "precio" in errors

    @pytest.mark.parametrize("valor, esperado", [("1", 1), (" 42 ", 42), (999999, 999999)])
    def test_entero_valido(self, valor, esperado):
        errors = {}
        assert normalize_int(errors, "n", valor, "El numero") == esperado

    @pytest.mark.parametrize("valor", ["0", "-3", "1000000", "1.5", "abc", "", None, "1e3", True])
    def test_entero_invalido(self, valor):
        errors = {}
        assert normalize_int(errors, "n", valor, "El numero") is None
        assert "n" in errors

    def test_validate_choice(self):
        errors = {}
        assert validate_choice(errors, "tipo", " empleado ", ["empleado", "admin"]) == "empleado"
        assert validate_choice(errors, "tipo", "root", ["empleado", "admin"]) == ""
        assert "tipo" in errors


class TestThrottles:

    def test_login_throttle_bloquea_tras_max_intentos_y_se_limpia(self):
        throttle = LoginThrottle(max_attempts=3, window_seconds=60)
        for _ in range(3):
            assert throttle.is_locked("1.1.1.1", "a@b.com") is False
            throttle.register_failure("1.1.1.1", "a@b.com")
        assert throttle.is_locked("1.1.1.1", "A@B.com ") is True
        assert throttle.is_locked("2.2.2.2", "a@b.com") is False
        throttle.clear("1.1.1.1", "a@b.com")
        assert throttle.is_locked("1.1.1.1", "a@b.com") is False

    def test_login_throttle_olvida_intentos_fuera_de_la_ventana(self):
        throttle = LoginThrottle(max_attempts=1, window_seconds=10)
        with patch("config.validation.time.time", return_value=1000.0):
            throttle.register_failure("ip", "a@b.com")
            assert throttle.is_locked("ip", "a@b.com") is True
        with patch("config.validation.time.time", return_value=1011.0):
            assert throttle.is_locked("ip", "a@b.com") is False

    def test_recovery_throttle_aplica_enfriamiento(self):
        throttle = RecoveryThrottle()
        allowed, _, _ = throttle.check("ip", "a@b.com")
        assert allowed is True
        cooldown, count = throttle.register_success("ip", "a@b.com")
        assert count == 1 and cooldown > 0
        allowed, remaining, mensaje = throttle.check("ip", "a@b.com")
        assert allowed is False and remaining > 0 and mensaje
