import pytest

from autoemail import AutoEmailException, EmailEnv, EmailInstance, EmailObject
from autoemail.utils import (
    detect_domain_mismatch,
    str_to_enum,
    validate_email,
)


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

    def test_emailenv_by_name(self):
        assert str_to_enum(EmailEnv, "Domain1") == EmailEnv.Domain1

    def test_emailenv_case_insensitive(self):
        assert str_to_enum(EmailEnv, "domain1") == EmailEnv.Domain1


# ── validate_email ───────────────────────────────────────────────────────────

class TestValidateEmail:
    HOST = EmailInstance(relay="r", domain="example.com")
    GOV  = EmailInstance(relay="r", domain="hr.test.gov")

    def test_valid_email_returned(self):
        assert validate_email("user@example.com", self.HOST) == "user@example.com"

    def test_strips_and_lowercases(self):
        assert validate_email("  User@Example.COM  ", self.HOST) == "user@example.com"

    def test_strips_trailing_dot(self):
        assert validate_email("user@example.com.", self.HOST) == "user@example.com"

    def test_missing_at_raises(self):
        with pytest.raises(AutoEmailException):
            validate_email("notanemail", self.HOST)

    def test_dot_before_at_raises(self):
        with pytest.raises(AutoEmailException):
            validate_email(".@example.com", self.HOST)

    def test_at_before_dot_raises(self):
        with pytest.raises(AutoEmailException):
            validate_email("user@.example.com", self.HOST)

    def test_empty_string_raises(self):
        with pytest.raises(AutoEmailException):
            validate_email("", self.HOST)

    def test_gov_email_valid(self):
        assert validate_email("user@hr.test.gov", self.GOV, gov_email=True) == "user@hr.test.gov"

    def test_gov_email_wrong_tld_raises(self):
        with pytest.raises(AutoEmailException, match=r"\.gov"):
            validate_email("user@hr.test.com", self.GOV, gov_email=True)

    def test_gov_email_wrong_domain_raises(self):
        with pytest.raises(AutoEmailException, match="must match domain"):
            validate_email("user@other.test.gov", self.GOV, gov_email=True)

    def test_bcc_skips_gov_check(self):
        # gov_email=False (BCC/reply-to path) must accept non-.gov address even on gov host
        assert validate_email("user@gmail.com", self.GOV, gov_email=False) == "user@gmail.com"


# ── detect_domain_mismatch ───────────────────────────────────────────────────

class TestDetectDomainMismatch:
    def test_matching_domain_does_not_raise(self, monkeypatch):
        monkeypatch.setattr("autoemail.utils.get_domain", lambda: "machine.hr.acme.com")
        detect_domain_mismatch(EmailEnv.Domain1)  # should not raise

    def test_mismatched_domain_raises(self, monkeypatch):
        monkeypatch.setattr("autoemail.utils.get_domain", lambda: "machine.ops.acme.com")
        with pytest.raises(AutoEmailException, match="Mismatch"):
            detect_domain_mismatch(EmailEnv.Domain1)

    def test_ci_runner_skipped(self, monkeypatch):
        monkeypatch.setattr("autoemail.utils.get_domain", lambda: "runner.github.com")
        detect_domain_mismatch(EmailEnv.Domain1)  # should not raise

    def test_single_label_hostname_skipped(self, monkeypatch):
        monkeypatch.setattr("autoemail.utils.get_domain", lambda: "localhost")
        detect_domain_mismatch(EmailEnv.Domain1)  # should not raise
