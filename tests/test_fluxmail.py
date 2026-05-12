import smtplib
import sys

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from fluxmail import FluxMail, FluxMailException, EmailInstance, EmailObject
from fluxmail.testing import mock_smtp

HOST = EmailInstance(relay="smtp.example.com")


# ── __init__ ─────────────────────────────────────────────────────────────────

class TestInit:
    def test_smtp_object_type(self):
        e = FluxMail(object_type=EmailObject.SMTP, host=HOST)
        assert e.is_smtp()
        assert not e.is_outlook()

    def test_string_type_accepted(self):
        e = FluxMail(object_type="smtp", host=HOST)
        assert e.is_smtp()

    def test_emailinstance_host(self):
        e = FluxMail(object_type="smtp", host=HOST)
        assert e.host == HOST

    def test_bare_string_host(self):
        e = FluxMail(object_type="smtp", host="smtp.example.com")
        assert e.host.relay == "smtp.example.com"
        assert e.host.domain == ""

    def test_relay_colon_domain_string_host(self):
        e = FluxMail(object_type="smtp", host="smtp.example.com:example.com")
        assert e.host.relay == "smtp.example.com"
        assert e.host.domain == "example.com"

    def test_invalid_type_raises(self):
        with pytest.raises(ValueError):
            FluxMail(object_type="fax", host=HOST)

    def test_invalid_host_type_raises(self):
        with pytest.raises(TypeError):
            FluxMail(object_type="smtp", host=12345)

    def test_invalid_logger_raises(self):
        with pytest.raises(FluxMailException):
            FluxMail(object_type="smtp", host=HOST, logger="not-a-logger")

    def test_default_port(self):
        e = FluxMail(object_type="smtp", host=HOST)
        assert e.port == 25

    def test_custom_port(self):
        e = FluxMail(object_type="smtp", host=HOST, port=587)
        assert e.port == 587

    @pytest.mark.skipif(sys.platform == "win32", reason="verifies non-Windows guard only")
    def test_outlook_raises_on_non_windows(self):
        with pytest.raises(FluxMailException) as exc_info:
            FluxMail(object_type="outlook", host=EmailInstance(relay=""))
        assert exc_info.value.code == "invalid_config"
        assert "Windows" in str(exc_info.value)


# ── create() ─────────────────────────────────────────────────────────────────

class TestCreate:
    def test_returns_self(self, smtp_email):
        result = smtp_email.create(subject="Hi", recipients=["a@b.com"], body="Hello")
        assert result is smtp_email

    def test_is_created_true_after_call(self, smtp_email):
        smtp_email.create(subject="Hi", recipients=["a@b.com"], body="Hello")
        assert smtp_email.is_created

    def test_empty_subject_raises(self, smtp_email):
        with pytest.raises(FluxMailException):
            smtp_email.create(subject="", recipients=["a@b.com"], body="Hello")

    def test_empty_recipients_raises(self, smtp_email):
        with pytest.raises(FluxMailException):
            smtp_email.create(subject="Hi", recipients=[], body="Hello")

    def test_string_recipients_raises(self, smtp_email):
        with pytest.raises(FluxMailException):
            smtp_email.create(subject="Hi", recipients="a@b.com", body="Hello")

    def test_string_cc_raises(self, smtp_email):
        with pytest.raises(FluxMailException):
            smtp_email.create(subject="Hi", recipients=["a@b.com"], body="Hi", cc="a@b.com")

    def test_string_bcc_raises(self, smtp_email):
        with pytest.raises(FluxMailException):
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

    # ── sender logic ──────────────────────────────────────────────────────────

    def test_sender_defaults_to_username_when_email(self):
        e = FluxMail(object_type="smtp", host=HOST, username="me@example.com")
        e.create(subject="Hi", recipients=["a@b.com"], body="Hi")
        assert e.message["From"] == "me@example.com"

    def test_explicit_sender_used_over_username(self):
        e = FluxMail(object_type="smtp", host=HOST, username="auth@example.com")
        e.create(subject="Hi", recipients=["a@b.com"], body="Hi",
                 sender="noreply@example.com")
        assert e.message["From"] == "noreply@example.com"

    def test_sender_raises_when_username_not_email(self):
        e = FluxMail(object_type="smtp", host=HOST, username="apikey")
        with pytest.raises(FluxMailException, match="sender is required"):
            e.create(subject="Hi", recipients=["a@b.com"], body="Hi")

    def test_sender_raises_when_no_username(self):
        e = FluxMail(object_type="smtp", host=HOST)
        with pytest.raises(FluxMailException, match="sender is required"):
            e.create(subject="Hi", recipients=["a@b.com"], body="Hi")

    def test_explicit_sender_set_on_message(self, smtp_email):
        smtp_email.create(subject="Hi", recipients=["a@b.com"], body="Hi",
                          sender="custom@example.com")
        assert smtp_email.message["From"] == "custom@example.com"

    def test_any_recipient_domain_accepted(self, smtp_email):
        # Previously non-Domain1 hosts enforced .gov recipients — now any domain works
        smtp_email.create(subject="Hi", recipients=["user@gmail.com"], body="Hi")
        assert "user@gmail.com" in smtp_email.message["To"]


# ── send() ───────────────────────────────────────────────────────────────────

class TestSend:
    def test_send_before_create_raises(self, smtp_email):
        with pytest.raises(FluxMailException, match=r"create\(\)"):
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
            e = FluxMail(object_type="smtp", host=HOST, use_tls=True,
                          username="u@example.com")
            e.create(subject="Hi", recipients=["a@b.com"], body="Hello")
            e.send()
        smtp.starttls.assert_called_once()

    def test_send_without_tls_does_not_starttls(self):
        with mock_smtp() as smtp:
            e = FluxMail(object_type="smtp", host=HOST, use_tls=False,
                          username="u@example.com")
            e.create(subject="Hi", recipients=["a@b.com"], body="Hello")
            e.send()
        smtp.starttls.assert_not_called()

    def test_send_with_credentials_calls_login(self):
        with mock_smtp() as smtp:
            e = FluxMail(object_type="smtp", host=HOST,
                          username="u@example.com", password="p")
            e.create(subject="Hi", recipients=["a@b.com"], body="Hello")
            e.send()
        smtp.login.assert_called_once_with("u@example.com", "p")

    def test_send_without_credentials_skips_login(self):
        with mock_smtp() as smtp:
            e = FluxMail(object_type="smtp", host=HOST, username="u@example.com")
            e.create(subject="Hi", recipients=["a@b.com"], body="Hello")
            e.send()
        smtp.login.assert_not_called()

    def test_smtp_exception_raises_fluxmail_exception(self, smtp_email):
        with mock_smtp() as smtp:
            smtp.send_message.side_effect = ConnectionRefusedError("refused")
            smtp_email.create(subject="Hi", recipients=["a@b.com"], body="Hello")
            with pytest.raises(FluxMailException, match="Send failed"):
                smtp_email.send()


# ── multipart ────────────────────────────────────────────────────────────────

class TestMultipart:
    def test_html_with_plain_body_creates_multipart(self, smtp_email):
        smtp_email.create(
            subject="Hi", recipients=["a@b.com"],
            body="<h1>Hello</h1>",
            html_body=True,
            plain_body="Hello",
        )
        assert isinstance(smtp_email.message.get_payload(), list)

    def test_html_without_plain_body_is_not_multipart(self, smtp_email):
        smtp_email.create(
            subject="Hi", recipients=["a@b.com"],
            body="<h1>Hello</h1>",
            html_body=True,
        )
        assert isinstance(smtp_email.message.get_payload(), str)

    def test_plain_body_ignored_when_html_body_false(self, smtp_email):
        smtp_email.create(
            subject="Hi", recipients=["a@b.com"],
            body="Hello",
            html_body=False,
            plain_body="ignored",
        )
        assert isinstance(smtp_email.message.get_payload(), str)


# ── threading headers ─────────────────────────────────────────────────────────

class TestThreadingHeaders:
    def test_in_reply_to_set(self, smtp_email):
        smtp_email.create(
            subject="Re: Hi", recipients=["a@b.com"], body="Reply",
            in_reply_to="<abc123@example.com>",
        )
        assert smtp_email.message["In-Reply-To"] == "<abc123@example.com>"

    def test_references_set(self, smtp_email):
        smtp_email.create(
            subject="Re: Hi", recipients=["a@b.com"], body="Reply",
            references=["<msg1@example.com>", "<msg2@example.com>"],
        )
        assert "<msg1@example.com>" in smtp_email.message["References"]
        assert "<msg2@example.com>" in smtp_email.message["References"]

    def test_no_threading_headers_by_default(self, smtp_email):
        smtp_email.create(subject="Hi", recipients=["a@b.com"], body="Hi")
        assert smtp_email.message["In-Reply-To"] is None
        assert smtp_email.message["References"] is None


# ── priority headers ──────────────────────────────────────────────────────────

class TestPriorityHeaders:
    def test_high_priority_sets_headers(self, smtp_email):
        smtp_email.create(
            subject="URGENT", recipients=["a@b.com"], body="Hi", priority="high"
        )
        assert smtp_email.message["X-Priority"] == "1"
        assert smtp_email.message["Importance"] == "High"
        assert smtp_email.message["X-MSMail-Priority"] == "High"

    def test_low_priority(self, smtp_email):
        smtp_email.create(
            subject="FYI", recipients=["a@b.com"], body="Hi", priority="low"
        )
        assert smtp_email.message["X-Priority"] == "5"

    def test_invalid_priority_raises(self, smtp_email):
        with pytest.raises(FluxMailException, match="priority"):
            smtp_email.create(
                subject="Hi", recipients=["a@b.com"], body="Hi", priority="urgent"
            )

    def test_no_priority_headers_by_default(self, smtp_email):
        smtp_email.create(subject="Hi", recipients=["a@b.com"], body="Hi")
        assert smtp_email.message["X-Priority"] is None


# ── context manager ───────────────────────────────────────────────────────────

class TestContextManager:
    def test_context_manager_reuses_connection(self):
        from unittest.mock import patch, MagicMock
        mock_conn = MagicMock()
        mock_cls = MagicMock(return_value=mock_conn)

        with patch("fluxmail._transport.smtplib.SMTP", mock_cls):
            with FluxMail(object_type="smtp", host=HOST,
                           username="u@example.com") as mailer:
                mailer.create(subject="A", recipients=["a@b.com"], body="1").send()
                mailer.create(subject="B", recipients=["a@b.com"], body="2").send()

        mock_cls.assert_called_once()
        assert mock_conn.send_message.call_count == 2

    def test_context_manager_calls_quit_on_exit(self):
        from unittest.mock import patch, MagicMock
        mock_conn = MagicMock()
        mock_cls = MagicMock(return_value=mock_conn)

        with patch("fluxmail._transport.smtplib.SMTP", mock_cls):
            with FluxMail(object_type="smtp", host=HOST,
                           username="u@example.com") as mailer:
                mailer.create(subject="A", recipients=["a@b.com"], body="1").send()

        mock_conn.quit.assert_called_once()

    def test_send_outside_context_still_works(self):
        with mock_smtp() as smtp:
            e = FluxMail(object_type="smtp", host=HOST, username="u@example.com")
            e.create(subject="Hi", recipients=["a@b.com"], body="Hello").send()
        smtp.send_message.assert_called_once()


# ── display() ────────────────────────────────────────────────────────────────

class TestDisplay:
    def test_display_before_create_raises(self, smtp_email):
        with pytest.raises(FluxMailException, match=r"create\(\)"):
            smtp_email.display()

    def test_display_returns_string(self, smtp_email):
        smtp_email.create(subject="Hi", recipients=["a@b.com"], body="Hello")
        result = smtp_email.display()
        assert isinstance(result, str)
        assert "Email Preview" in result


# ── attachments ───────────────────────────────────────────────────────────────

class TestAttachments:
    def test_attach_existing_file(self, smtp_email, tmp_path):
        f = tmp_path / "note.txt"
        f.write_text("hello")
        smtp_email.create(subject="Hi", recipients=["a@b.com"], body="Hi",
                          attachments=[str(f)])
        assert smtp_email.is_created

    def test_missing_attachment_raises(self, smtp_email, tmp_path):
        with pytest.raises(FluxMailException, match="Attachment not found"):
            smtp_email.create(subject="Hi", recipients=["a@b.com"], body="Hi",
                              attachments=[str(tmp_path / "missing.pdf")])

    def test_send_with_attachment(self, smtp_email, tmp_path):
        f = tmp_path / "report.pdf"
        f.write_bytes(b"%PDF fake")
        with mock_smtp() as smtp:
            smtp_email.create(subject="Hi", recipients=["a@b.com"], body="Hi",
                              attachments=[str(f)])
            smtp_email.send()
        smtp.send_message.assert_called_once()

    def test_string_attachments_raises(self, smtp_email):
        with pytest.raises(FluxMailException):
            smtp_email.create(subject="Hi", recipients=["a@b.com"], body="Hi",
                              attachments="file.txt")


# ── instance reuse ────────────────────────────────────────────────────────────

class TestInstanceReuse:
    def test_create_twice_resets_message(self, smtp_email):
        smtp_email.create(subject="First", recipients=["a@b.com"], body="1")
        smtp_email.create(subject="Second", recipients=["b@c.com"], body="2")
        assert smtp_email.message["Subject"] == "Second"
        assert "b@c.com" in smtp_email.message["To"]
        assert smtp_email.message["Subject"] != "First"

    def test_send_twice_without_context_manager(self):
        with mock_smtp() as smtp:
            e = FluxMail(object_type="smtp", host=HOST, username="u@example.com")
            e.create(subject="A", recipients=["a@b.com"], body="1").send()
            e.create(subject="B", recipients=["a@b.com"], body="2").send()
        assert smtp.send_message.call_count == 2


# ── empty relay ───────────────────────────────────────────────────────────────

class TestEmptyRelay:
    def test_send_with_empty_relay_raises(self):
        e = FluxMail(object_type="smtp", host=EmailInstance(relay=""),
                     username="u@example.com")
        e.create(subject="Hi", recipients=["a@b.com"], body="Hi")
        with pytest.raises(FluxMailException, match="relay"):
            e.send()


# ── repr ──────────────────────────────────────────────────────────────────────

class TestRepr:
    def test_repr_contains_type_and_host(self, smtp_email):
        result = repr(smtp_email)
        assert "FluxMail" in result
        assert "smtp" in result.lower()


class TestNewConstructorParams:
    def test_timeout_default(self):
        e = FluxMail(object_type="smtp", host=HOST)
        assert e.timeout == 30

    def test_custom_timeout(self):
        e = FluxMail(object_type="smtp", host=HOST, timeout=60)
        assert e.timeout == 60

    def test_use_ssl_false_by_default(self):
        e = FluxMail(object_type="smtp", host=HOST)
        assert e.use_ssl is False

    def test_max_retries_default(self):
        e = FluxMail(object_type="smtp", host=HOST)
        assert e.max_retries == 0

    def test_retry_delay_default(self):
        e = FluxMail(object_type="smtp", host=HOST)
        assert e.retry_delay == 1.0

    def test_use_ssl_and_use_tls_raises_invalid_config(self):
        with pytest.raises(FluxMailException) as exc_info:
            FluxMail(object_type="smtp", host=HOST, use_ssl=True, use_tls=True)
        assert exc_info.value.code == "invalid_config"

    def test_use_ssl_uses_smtp_ssl(self):
        with patch("fluxmail._transport.smtplib.SMTP_SSL") as mock_ssl:
            mock_ssl.return_value = MagicMock()
            e = FluxMail(
                object_type="smtp", host=HOST,
                username="u@example.com", use_ssl=True,
            )
            e.create(subject="Hi", recipients=["a@b.com"], body="Hi").send()
        mock_ssl.assert_called_once()


class TestMessageID:
    def test_message_id_set_after_create(self, smtp_email):
        smtp_email.create(subject="Hi", recipients=["a@b.com"], body="Hello")
        assert smtp_email.message["Message-ID"] is not None

    def test_message_id_is_string(self, smtp_email):
        smtp_email.create(subject="Hi", recipients=["a@b.com"], body="Hello")
        assert isinstance(smtp_email.message["Message-ID"], str)


class TestErrorCodes:
    def test_send_before_create_has_not_created_code(self, smtp_email):
        with pytest.raises(FluxMailException) as exc_info:
            smtp_email.send()
        assert exc_info.value.code == "not_created"

    def test_empty_relay_has_no_relay_code(self):
        e = FluxMail(object_type="smtp", host=EmailInstance(relay=""),
                     username="u@example.com")
        e.create(subject="Hi", recipients=["a@b.com"], body="Hi")
        with pytest.raises(FluxMailException) as exc_info:
            e.send()
        assert exc_info.value.code == "no_relay"

    def test_sender_required_code(self):
        e = FluxMail(object_type="smtp", host=HOST, username="apikey")
        with pytest.raises(FluxMailException) as exc_info:
            e.create(subject="Hi", recipients=["a@b.com"], body="Hi")
        assert exc_info.value.code == "sender_required"

    def test_invalid_priority_code(self, smtp_email):
        with pytest.raises(FluxMailException) as exc_info:
            smtp_email.create(subject="Hi", recipients=["a@b.com"],
                              body="Hi", priority="urgent")
        assert exc_info.value.code == "invalid_priority"

    def test_missing_attachment_code(self, smtp_email):
        with pytest.raises(FluxMailException) as exc_info:
            smtp_email.create(subject="Hi", recipients=["a@b.com"],
                              body="Hi", attachments=["/nonexistent/file.pdf"])
        assert exc_info.value.code == "attachment_not_found"

    def test_invalid_email_code(self):
        from fluxmail.utils import validate_email
        with pytest.raises(FluxMailException) as exc_info:
            validate_email("not-an-email")
        assert exc_info.value.code == "invalid_email"


# ── send_async() ──────────────────────────────────────────────────────────────

class TestSendAsync:
    async def test_send_async_before_create_raises(self, smtp_email):
        with pytest.raises(FluxMailException) as exc_info:
            await smtp_email.send_async()
        assert exc_info.value.code == "not_created"

    async def test_send_async_delegates_to_transport(self, smtp_email):
        smtp_email.create(subject="Hi", recipients=["a@b.com"], body="Hello")
        with patch.object(smtp_email._transport, "send_async",
                          new_callable=AsyncMock) as mock_async:
            await smtp_email.send_async()
        mock_async.assert_called_once_with(smtp_email.message)

    async def test_send_async_returns_success_string(self, smtp_email):
        smtp_email.create(subject="Hi", recipients=["a@b.com"], body="Hello")
        with patch.object(smtp_email._transport, "send_async",
                          new_callable=AsyncMock):
            result = await smtp_email.send_async()
        assert "sent successfully" in result

    async def test_send_async_dry_run_returns_preview(self, smtp_email):
        smtp_email.create(subject="Hi", recipients=["a@b.com"], body="Hello")
        result = await smtp_email.send_async(dry_run=True)
        assert "Email Preview" in result

    async def test_send_async_empty_relay_raises(self):
        e = FluxMail(object_type="smtp", host=EmailInstance(relay=""),
                     username="u@example.com")
        e.create(subject="Hi", recipients=["a@b.com"], body="Hi")
        with pytest.raises(FluxMailException) as exc_info:
            await e.send_async()
        assert exc_info.value.code == "no_relay"


# ── retry ─────────────────────────────────────────────────────────────────────

class TestRetry:
    def test_retries_on_failure_then_succeeds(self):
        call_count = 0

        def failing_then_ok(message):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise smtplib.SMTPException("transient")

        e = FluxMail(object_type="smtp", host=HOST,
                     username="u@example.com", max_retries=3, retry_delay=0)
        e.create(subject="Hi", recipients=["a@b.com"], body="Hello")
        with patch.object(e._transport, "send", side_effect=failing_then_ok):
            result = e.send()
        assert call_count == 3
        assert "sent successfully" in result

    def test_raises_after_exhausting_all_retries(self):
        e = FluxMail(object_type="smtp", host=HOST,
                     username="u@example.com", max_retries=2, retry_delay=0)
        e.create(subject="Hi", recipients=["a@b.com"], body="Hello")
        with patch.object(e._transport, "send",
                          side_effect=smtplib.SMTPException("always fails")):
            with pytest.raises(FluxMailException) as exc_info:
                e.send()
        assert exc_info.value.code == "send_failed"

    def test_no_retry_when_max_retries_zero(self):
        call_count = 0

        def count_and_fail(message):
            nonlocal call_count
            call_count += 1
            raise smtplib.SMTPException("fail")

        e = FluxMail(object_type="smtp", host=HOST,
                     username="u@example.com", max_retries=0)
        e.create(subject="Hi", recipients=["a@b.com"], body="Hello")
        with patch.object(e._transport, "send", side_effect=count_and_fail):
            with pytest.raises(FluxMailException):
                e.send()
        assert call_count == 1


class TestFromEnv:
    def test_reads_smtp_config(self, monkeypatch):
        monkeypatch.setenv("FLUXMAIL_HOST", "smtp.example.com")
        monkeypatch.setenv("FLUXMAIL_USERNAME", "u@example.com")
        monkeypatch.delenv("FLUXMAIL_TYPE", raising=False)
        e = FluxMail.from_env()
        assert e.host.relay == "smtp.example.com"
        assert e.username == "u@example.com"
        assert e.object_type == EmailObject.SMTP

    def test_missing_host_raises_invalid_config(self, monkeypatch):
        monkeypatch.setenv("FLUXMAIL_TYPE", "smtp")
        monkeypatch.delenv("FLUXMAIL_HOST", raising=False)
        with pytest.raises(FluxMailException) as exc_info:
            FluxMail.from_env()
        assert exc_info.value.code == "invalid_config"
        assert "FLUXMAIL_HOST" in str(exc_info.value)

    def test_tls_parsed_true(self, monkeypatch):
        monkeypatch.setenv("FLUXMAIL_HOST", "smtp.example.com")
        monkeypatch.setenv("FLUXMAIL_TLS", "true")
        monkeypatch.delenv("FLUXMAIL_SSL", raising=False)
        e = FluxMail.from_env()
        assert e.use_tls is True

    def test_tls_parsed_false(self, monkeypatch):
        monkeypatch.setenv("FLUXMAIL_HOST", "smtp.example.com")
        monkeypatch.setenv("FLUXMAIL_TLS", "false")
        e = FluxMail.from_env()
        assert e.use_tls is False

    def test_custom_port_and_timeout(self, monkeypatch):
        monkeypatch.setenv("FLUXMAIL_HOST", "smtp.example.com")
        monkeypatch.setenv("FLUXMAIL_PORT", "587")
        monkeypatch.setenv("FLUXMAIL_TIMEOUT", "60")
        e = FluxMail.from_env()
        assert e.port == 587
        assert e.timeout == 60

    @pytest.mark.skipif(sys.platform == "win32", reason="Outlook connects on Windows")
    def test_outlook_type_no_host_required(self, monkeypatch):
        monkeypatch.setenv("FLUXMAIL_TYPE", "outlook")
        monkeypatch.delenv("FLUXMAIL_HOST", raising=False)
        with pytest.raises(FluxMailException) as exc_info:
            FluxMail.from_env()
        # Should raise platform error, NOT missing-host error
        assert "FLUXMAIL_HOST" not in str(exc_info.value)
        assert "Windows" in str(exc_info.value)


class TestTestConnection:
    def test_returns_diagnostics_dict(self, smtp_email):
        mock_conn = MagicMock()
        with patch.object(smtp_email._transport, "_make_connection", return_value=mock_conn):
            result = smtp_email.test_connection()
        assert result["ok"] is True
        assert result["relay"] == smtp_email.host.relay
        assert result["port"] == smtp_email.port
        assert isinstance(result["latency_ms"], int)
        assert result["latency_ms"] >= 0
        mock_conn.quit.assert_called_once()

    def test_quit_failure_does_not_mask_success(self, smtp_email):
        mock_conn = MagicMock()
        mock_conn.quit.side_effect = Exception("already closed")
        with patch.object(smtp_email._transport, "_make_connection", return_value=mock_conn):
            result = smtp_email.test_connection()  # must not raise
        assert result["ok"] is True

    def test_raises_connection_failed_on_error(self, smtp_email):
        with patch.object(
            smtp_email._transport, "_make_connection",
            side_effect=OSError("connection refused")
        ):
            with pytest.raises(FluxMailException) as exc_info:
                smtp_email.test_connection()
        assert exc_info.value.code == "connection_failed"

    @pytest.mark.skipif(sys.platform != "win32", reason="Outlook only on Windows")
    def test_outlook_raises_outlook_no_connect(self):
        e = FluxMail(object_type="outlook", host=EmailInstance(relay=""))
        with pytest.raises(FluxMailException) as exc_info:
            e.test_connection()
        assert exc_info.value.code == "outlook_no_connect"


class TestUnsubscribeHeader:
    def test_headers_set_when_url_provided(self, smtp_email):
        smtp_email.create(
            subject="Newsletter", recipients=["a@b.com"], body="Hi",
            unsubscribe_url="https://example.com/unsub?token=abc",
        )
        assert smtp_email.message["List-Unsubscribe"] == "<https://example.com/unsub?token=abc>"
        assert smtp_email.message["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"

    def test_no_headers_by_default(self, smtp_email):
        smtp_email.create(subject="Hi", recipients=["a@b.com"], body="Hello")
        assert smtp_email.message["List-Unsubscribe"] is None
        assert smtp_email.message["List-Unsubscribe-Post"] is None

    def test_smtp_header_is_set(self, smtp_email):
        # Rename of old misnamed test — confirms SMTP header is set
        smtp_email.create(
            subject="Hi", recipients=["a@b.com"], body="Hello",
            unsubscribe_url="https://example.com/unsub",
        )
        assert smtp_email.message["List-Unsubscribe"] is not None

    def test_non_https_url_raises(self, smtp_email):
        with pytest.raises(FluxMailException) as exc_info:
            smtp_email.create(
                subject="Hi", recipients=["a@b.com"], body="Hello",
                unsubscribe_url="http://example.com/unsub",
            )
        assert exc_info.value.code == "invalid_params"

    def test_ignored_when_no_url(self, smtp_email):
        # No unsubscribe_url — _handle_unsubscribe is a no-op
        smtp_email.create(subject="Hi", recipients=["a@b.com"], body="Hello")
        assert smtp_email.message["List-Unsubscribe"] is None


class TestInlineImages:
    def test_inline_image_attaches_with_content_id(self, smtp_email, tmp_path):
        img = tmp_path / "logo.png"
        img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 50)
        smtp_email.create(
            subject="Hi", recipients=["a@b.com"],
            body='<img src="cid:logo">Hello', html_body=True,
            inline_images={"logo": str(img)},
        )
        payload = smtp_email.message.get_payload()
        content_ids = [
            str(part.get("Content-ID", ""))
            for part in (payload if isinstance(payload, list) else [smtp_email.message])
        ]
        assert any("logo" in cid for cid in content_ids)

    def test_missing_inline_image_raises(self, smtp_email, tmp_path):
        with pytest.raises(FluxMailException) as exc_info:
            smtp_email.create(
                subject="Hi", recipients=["a@b.com"],
                body="<b>hi</b>", html_body=True,
                inline_images={"logo": str(tmp_path / "missing.png")},
            )
        assert exc_info.value.code == "attachment_not_found"

    def test_non_dict_inline_images_raises(self, smtp_email):
        with pytest.raises(FluxMailException) as exc_info:
            smtp_email.create(
                subject="Hi", recipients=["a@b.com"], body="Hi",
                inline_images=["logo.png"],
            )
        assert exc_info.value.code == "invalid_params"

    def test_inline_images_without_html_body_raises(self, smtp_email):
        with pytest.raises(FluxMailException) as exc_info:
            smtp_email.create(
                subject="Hi", recipients=["a@b.com"], body="Plain text",
                html_body=False, inline_images={"logo": "/any/path.png"},
            )
        assert exc_info.value.code == "invalid_params"

    def test_inline_images_outlook_raises(self, smtp_email):
        with patch.object(FluxMail, "is_outlook", return_value=True), \
             patch.object(FluxMail, "is_smtp", return_value=False):
            smtp_email.create(subject="Hi", recipients=["a@b.com"], body="Hi")
            smtp_email.inline_images = {"logo": "/fake/logo.png"}
            with pytest.raises(FluxMailException) as exc_info:
                smtp_email._attach_inline_images()
        assert exc_info.value.code == "invalid_params"

    def test_no_inline_images_by_default(self, smtp_email):
        smtp_email.create(subject="Hi", recipients=["a@b.com"], body="Hello")
        assert smtp_email.is_created  # no error


class TestCSSInlining:
    def test_css_inlined_when_html_true(self, smtp_email):
        smtp_email.create(
            subject="Hi", recipients=["a@b.com"],
            body='<p style="color: red">Hello</p>',
            html_body=True, inline_css=True,
        )
        assert smtp_email.is_created

    def test_inline_css_ignored_when_not_html(self, smtp_email):
        # inline_css=True with html_body=False must not raise
        smtp_email.create(
            subject="Hi", recipients=["a@b.com"],
            body="Plain text", html_body=False, inline_css=True,
        )
        assert smtp_email.is_created

    def test_premailer_failure_raises_css_inline_failed(self, smtp_email):
        with patch("fluxmail.fluxmail.premailer.transform", side_effect=Exception("bad html")):
            with pytest.raises(FluxMailException) as exc_info:
                smtp_email.create(
                    subject="Hi", recipients=["a@b.com"],
                    body="<bad>", html_body=True, inline_css=True,
                )
        assert exc_info.value.code == "css_inline_failed"

    def test_inline_css_false_by_default(self, smtp_email):
        smtp_email.create(
            subject="Hi", recipients=["a@b.com"],
            body='<style>p{color:red}</style><p>Hi</p>', html_body=True,
        )
        assert smtp_email.is_created
