import pytest
from autoemail import AutoEmail, AutoEmailException, EmailEnv, EmailInstance, EmailObject
from autoemail.testing import mock_smtp


GOV_HOST = EmailInstance(relay="smtp.test.gov", domain="hr.test.gov")


# ── __init__ ─────────────────────────────────────────────────────────────────

class TestInit:
    def test_smtp_object_type(self):
        e = AutoEmail(object_type=EmailObject.SMTP, host=EmailEnv.Domain1)
        assert e.is_smtp()
        assert not e.is_outlook()

    def test_string_type_accepted(self):
        e = AutoEmail(object_type="smtp", host=EmailEnv.Domain1)
        assert e.is_smtp()

    def test_custom_emailinstance_host(self):
        e = AutoEmail(object_type="smtp", host=GOV_HOST)
        assert e.host == GOV_HOST

    def test_invalid_type_raises(self):
        with pytest.raises(ValueError):
            AutoEmail(object_type="fax", host=EmailEnv.Domain1)

    def test_invalid_logger_raises(self):
        with pytest.raises(AutoEmailException):
            AutoEmail(object_type="smtp", host=EmailEnv.Domain1, logger="not-a-logger")

    def test_default_port(self):
        e = AutoEmail(object_type="smtp", host=EmailEnv.Domain1)
        assert e.port == 25

    def test_custom_port(self):
        e = AutoEmail(object_type="smtp", host=EmailEnv.Domain1, port=587)
        assert e.port == 587


# ── create() ─────────────────────────────────────────────────────────────────

class TestCreate:
    def test_returns_self(self, smtp_email):
        result = smtp_email.create(subject="Hi", recipients=["a@b.com"], body="Hello")
        assert result is smtp_email

    def test_is_created_true_after_call(self, smtp_email):
        smtp_email.create(subject="Hi", recipients=["a@b.com"], body="Hello")
        assert smtp_email.is_created

    def test_empty_subject_raises(self, smtp_email):
        with pytest.raises(AutoEmailException):
            smtp_email.create(subject="", recipients=["a@b.com"], body="Hello")

    def test_empty_recipients_raises(self, smtp_email):
        with pytest.raises(AutoEmailException):
            smtp_email.create(subject="Hi", recipients=[], body="Hello")

    def test_string_recipients_raises(self, smtp_email):
        with pytest.raises(AutoEmailException):
            smtp_email.create(subject="Hi", recipients="a@b.com", body="Hello")

    def test_string_cc_raises(self, smtp_email):
        with pytest.raises(AutoEmailException):
            smtp_email.create(subject="Hi", recipients=["a@b.com"], body="Hi", cc="a@b.com")

    def test_string_bcc_raises(self, smtp_email):
        with pytest.raises(AutoEmailException):
            smtp_email.create(subject="Hi", recipients=["a@b.com"], body="Hi", bcc="a@b.com")

    def test_subject_set_on_message(self, smtp_email):
        smtp_email.create(subject="Test Subject", recipients=["a@b.com"], body="Hi")
        assert smtp_email.message["Subject"] == "Test Subject"

    def test_recipients_set_on_message(self, smtp_email):
        smtp_email.create(subject="Hi", recipients=["alice@b.com", "bob@b.com"], body="Hi")
        assert "alice@b.com" in smtp_email.message["To"]
        assert "bob@b.com" in smtp_email.message["To"]

    def test_cc_set_on_message(self, smtp_email):
        smtp_email.create(subject="Hi", recipients=["a@b.com"], body="Hi", cc=["cc@b.com"])
        assert "cc@b.com" in smtp_email.message["Cc"]

    def test_bcc_set_on_message(self, smtp_email):
        smtp_email.create(subject="Hi", recipients=["a@b.com"], body="Hi", bcc=["bcc@b.com"])
        assert "bcc@b.com" in smtp_email.message["Bcc"]

    def test_reply_to_set_on_message(self, smtp_email):
        smtp_email.create(
            subject="Hi", recipients=["a@b.com"], body="Hi", reply_to="r@b.com"
        )
        assert "r@b.com" in smtp_email.message["Reply-To"]

    def test_sender_validated_when_explicit(self, gov_host):
        e = AutoEmail(object_type="smtp", host=gov_host)
        e.create(subject="Hi", recipients=["user@hr.test.gov"], body="Hi",
                 sender="sender@hr.test.gov")
        assert e.message["From"] == "sender@hr.test.gov"

    def test_explicit_sender_wrong_domain_raises(self, gov_host):
        e = AutoEmail(object_type="smtp", host=gov_host)
        with pytest.raises(AutoEmailException):
            e.create(subject="Hi", recipients=["user@hr.test.gov"], body="Hi",
                     sender="sender@other.gov")


# ── send() ───────────────────────────────────────────────────────────────────

class TestSend:
    def test_send_before_create_raises(self, smtp_email):
        with pytest.raises(AutoEmailException, match=r"create\(\)"):
            smtp_email.send()

    def test_dry_run_returns_preview_string(self, smtp_email):
        smtp_email.create(subject="Hi", recipients=["a@b.com"], body="Hello")
        result = smtp_email.send(dry_run=True)
        assert "Email Preview" in result

    def test_send_calls_send_message(self, smtp_email):
        with mock_smtp() as smtp:
            smtp_email.create(subject="Hi", recipients=["a@b.com"], body="Hello")
            result = smtp_email.send()
        assert "sent successfully" in result
        smtp.send_message.assert_called_once()

    def test_send_with_tls_calls_starttls(self):
        with mock_smtp() as smtp:
            e = AutoEmail(object_type="smtp", host=EmailEnv.Domain1, use_tls=True)
            e.create(subject="Hi", recipients=["a@b.com"], body="Hello")
            e.send()
        smtp.starttls.assert_called_once()

    def test_send_without_tls_does_not_starttls(self):
        with mock_smtp() as smtp:
            e = AutoEmail(object_type="smtp", host=EmailEnv.Domain1, use_tls=False)
            e.create(subject="Hi", recipients=["a@b.com"], body="Hello")
            e.send()
        smtp.starttls.assert_not_called()

    def test_send_with_credentials_calls_login(self):
        with mock_smtp() as smtp:
            e = AutoEmail(object_type="smtp", host=EmailEnv.Domain1,
                          username="u", password="p")
            e.create(subject="Hi", recipients=["a@b.com"], body="Hello")
            e.send()
        smtp.login.assert_called_once_with("u", "p")

    def test_send_without_credentials_skips_login(self):
        with mock_smtp() as smtp:
            e = AutoEmail(object_type="smtp", host=EmailEnv.Domain1)
            e.create(subject="Hi", recipients=["a@b.com"], body="Hello")
            e.send()
        smtp.login.assert_not_called()

    def test_smtp_exception_raises_autoemail_exception(self, smtp_email):
        with mock_smtp() as smtp:
            smtp.send_message.side_effect = ConnectionRefusedError("refused")
            smtp_email.create(subject="Hi", recipients=["a@b.com"], body="Hello")
            with pytest.raises(AutoEmailException, match="Send failed"):
                smtp_email.send()


# ── display() ────────────────────────────────────────────────────────────────

class TestDisplay:
    def test_display_before_create_raises(self, smtp_email):
        with pytest.raises(AutoEmailException, match=r"create\(\)"):
            smtp_email.display()

    def test_display_returns_string(self, smtp_email):
        smtp_email.create(subject="Hi", recipients=["a@b.com"], body="Hello")
        result = smtp_email.display()
        assert isinstance(result, str)
        assert "Email Preview" in result
