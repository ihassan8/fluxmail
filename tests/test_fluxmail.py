import pytest
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

        with patch("fluxmail.fluxmail.smtplib.SMTP", mock_cls):
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

        with patch("fluxmail.fluxmail.smtplib.SMTP", mock_cls):
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
