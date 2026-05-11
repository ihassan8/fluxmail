import pytest

from fluxmail import FluxMailException, EmailInstance, EmailObject
from fluxmail.utils import str_to_enum, validate_email


# ── EmailInstance ─────────────────────────────────────────────────────────────

class TestEmailInstance:
    def test_relay_required(self):
        e = EmailInstance(relay="smtp.example.com")
        assert e.relay == "smtp.example.com"

    def test_domain_defaults_to_empty(self):
        e = EmailInstance(relay="smtp.example.com")
        assert e.domain == ""

    def test_domain_explicit(self):
        e = EmailInstance(relay="smtp.example.com", domain="example.com")
        assert e.domain == "example.com"


# ── str_to_enum ──────────────────────────────────────────────────────────────

class TestStrToEnum:
    def test_by_name_lowercase(self):
        assert str_to_enum(EmailObject, "smtp") == EmailObject.SMTP

    def test_by_name_uppercase(self):
        assert str_to_enum(EmailObject, "SMTP") == EmailObject.SMTP

    def test_by_name_mixed_case(self):
        assert str_to_enum(EmailObject, "Smtp") == EmailObject.SMTP

    def test_passthrough_enum_member(self):
        assert str_to_enum(EmailObject, EmailObject.SMTP) == EmailObject.SMTP

    def test_invalid_string_raises_value_error(self):
        with pytest.raises(ValueError, match="Invalid value"):
            str_to_enum(EmailObject, "fax")

    def test_non_string_non_enum_raises_type_error(self):
        with pytest.raises(TypeError):
            str_to_enum(EmailObject, 123)


# ── validate_email ───────────────────────────────────────────────────────────

class TestValidateEmail:
    def test_valid_email_returned(self):
        assert validate_email("user@example.com") == "user@example.com"

    def test_strips_and_lowercases(self):
        assert validate_email("  User@Example.COM  ") == "user@example.com"

    def test_strips_trailing_dot(self):
        assert validate_email("user@example.com.") == "user@example.com"

    def test_missing_at_raises(self):
        with pytest.raises(FluxMailException):
            validate_email("notanemail")

    def test_dot_before_at_raises(self):
        with pytest.raises(FluxMailException):
            validate_email(".@example.com")

    def test_at_before_dot_raises(self):
        with pytest.raises(FluxMailException):
            validate_email("user@.example.com")

    def test_empty_string_raises(self):
        with pytest.raises(FluxMailException):
            validate_email("")

    def test_any_domain_accepted(self):
        # Previously only .gov was enforced for gov hosts — now any domain passes
        assert validate_email("user@gmail.com") == "user@gmail.com"
        assert validate_email("user@company.org") == "user@company.org"

    def test_leading_dot_raises(self):
        with pytest.raises(FluxMailException):
            validate_email(".user@example.com")


# ── FluxMailException ─────────────────────────────────────────────────────────

class TestFluxMailExceptionCode:
    def test_code_stored(self):
        exc = FluxMailException("something broke", code="send_failed")
        assert exc.code == "send_failed"

    def test_code_defaults_to_none(self):
        exc = FluxMailException("something broke")
        assert exc.code is None

    def test_message_unaffected(self):
        exc = FluxMailException("oops", code="x")
        assert str(exc) == "oops"
