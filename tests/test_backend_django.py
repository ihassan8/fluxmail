"""Tests for the Django email backend.

Django settings are configured at module level so no Django project is required.
"""
from unittest.mock import MagicMock, patch

import pytest
import django
from django.conf import settings

if not settings.configured:
    settings.configure(
        EMAIL_HOST="smtp.example.com",
        EMAIL_PORT=587,
        EMAIL_HOST_USER="u@example.com",
        EMAIL_HOST_PASSWORD="secret",
        EMAIL_USE_TLS=True,
        EMAIL_USE_SSL=False,
        EMAIL_TIMEOUT=30,
        EMAIL_FLUXMAIL_MAX_RETRIES=0,
        EMAIL_FLUXMAIL_RETRY_DELAY=1.0,
        USE_TZ=True,
    )

from fluxmail.backends.django import FluxMailBackend  # noqa: E402

SMTP_MOCK = "fluxmail._transport.smtplib.SMTP"


def make_backend(fail_silently=False):
    return FluxMailBackend(fail_silently=fail_silently)


class TestFluxMailBackend:
    def test_send_messages_returns_sent_count(self):
        backend = make_backend()
        stdlib_msg = MagicMock()
        django_msg = MagicMock()
        django_msg.message.return_value = stdlib_msg
        mock_conn = MagicMock()
        with patch(SMTP_MOCK, MagicMock(return_value=mock_conn)):
            result = backend.send_messages([django_msg, django_msg])
        assert result == 2

    def test_send_messages_calls_transport_send(self):
        backend = make_backend()
        stdlib_msg = MagicMock()
        django_msg = MagicMock()
        django_msg.message.return_value = stdlib_msg
        mock_conn = MagicMock()
        with patch(SMTP_MOCK, MagicMock(return_value=mock_conn)):
            backend.send_messages([django_msg])
        mock_conn.send_message.assert_called_once_with(stdlib_msg)

    def test_fail_silently_suppresses_exception(self):
        backend = make_backend(fail_silently=True)
        django_msg = MagicMock()
        django_msg.message.return_value = MagicMock()
        with patch.object(backend._mailer._transport, "send", side_effect=Exception("fail")):
            result = backend.send_messages([django_msg])
        assert result == 0

    def test_fail_silently_false_raises(self):
        backend = make_backend(fail_silently=False)
        django_msg = MagicMock()
        django_msg.message.return_value = MagicMock()
        with patch.object(backend._mailer._transport, "send", side_effect=Exception("fail")):
            with pytest.raises(Exception, match="fail"):
                backend.send_messages([django_msg])

    def test_open_returns_true_first_call(self):
        backend = make_backend()
        mock_conn = MagicMock()
        with patch(SMTP_MOCK, MagicMock(return_value=mock_conn)):
            result = backend.open()
        assert result is True
        assert backend._connection_open is True

    def test_open_returns_false_when_already_open(self):
        backend = make_backend()
        mock_conn = MagicMock()
        with patch(SMTP_MOCK, MagicMock(return_value=mock_conn)):
            backend.open()
            result = backend.open()
        assert result is False

    def test_close_resets_connection_state(self):
        backend = make_backend()
        mock_conn = MagicMock()
        with patch(SMTP_MOCK, MagicMock(return_value=mock_conn)):
            backend.open()
        backend.close()
        assert backend._connection_open is False

    def test_close_is_noop_when_not_open(self):
        backend = make_backend()
        backend.close()  # must not raise
        assert backend._connection_open is False

    def test_settings_map_correctly(self):
        backend = make_backend()
        assert backend._mailer.host.relay == "smtp.example.com"
        assert backend._mailer.port == 587
        assert backend._mailer.use_tls is True
        assert backend._mailer.timeout == 30

    def test_backends_package_export(self):
        # fluxmail.backends.__init__ exports FluxMailBackend directly
        from fluxmail.backends import FluxMailBackend as BackendFromPackage
        assert BackendFromPackage is FluxMailBackend
