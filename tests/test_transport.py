import logging
import smtplib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from fluxmail._transport import _SMTPTransport

HOST = "smtp.example.com"
PORT = 587

_NULL_LOGGER = logging.getLogger("test_transport")
_NULL_LOGGER.addHandler(logging.NullHandler())


def make_transport(**kwargs):
    defaults = dict(
        relay=HOST, port=PORT,
        use_ssl=False, use_tls=False,
        ssl_context=None, timeout=30,
        username=None, password=None,
        logger=_NULL_LOGGER,
    )
    defaults.update(kwargs)
    return _SMTPTransport(**defaults)


class TestMakeConnection:
    def test_uses_smtp_by_default(self):
        t = make_transport()
        with patch("fluxmail._transport.smtplib.SMTP") as mock_cls:
            mock_cls.return_value = MagicMock()
            t._make_connection()
        mock_cls.assert_called_once_with(HOST, PORT, timeout=30)

    def test_uses_smtp_ssl_when_use_ssl(self):
        t = make_transport(use_ssl=True)
        with patch("fluxmail._transport.smtplib.SMTP_SSL") as mock_cls:
            mock_cls.return_value = MagicMock()
            t._make_connection()
        mock_cls.assert_called_once_with(HOST, PORT, context=None, timeout=30)

    def test_calls_starttls_when_use_tls(self):
        t = make_transport(use_tls=True)
        mock_conn = MagicMock()
        with patch("fluxmail._transport.smtplib.SMTP", return_value=mock_conn):
            t._make_connection()
        mock_conn.starttls.assert_called_once_with(context=None)

    def test_no_starttls_without_use_tls(self):
        t = make_transport()
        mock_conn = MagicMock()
        with patch("fluxmail._transport.smtplib.SMTP", return_value=mock_conn):
            t._make_connection()
        mock_conn.starttls.assert_not_called()

    def test_calls_login_with_credentials(self):
        t = make_transport(username="u@example.com", password="secret")
        mock_conn = MagicMock()
        with patch("fluxmail._transport.smtplib.SMTP", return_value=mock_conn):
            t._make_connection()
        mock_conn.login.assert_called_once_with("u@example.com", "secret")

    def test_no_login_without_credentials(self):
        t = make_transport()
        mock_conn = MagicMock()
        with patch("fluxmail._transport.smtplib.SMTP", return_value=mock_conn):
            t._make_connection()
        mock_conn.login.assert_not_called()

    def test_timeout_passed_to_smtp(self):
        t = make_transport(timeout=60)
        with patch("fluxmail._transport.smtplib.SMTP") as mock_cls:
            mock_cls.return_value = MagicMock()
            t._make_connection()
        mock_cls.assert_called_once_with(HOST, PORT, timeout=60)

    def test_ssl_context_passed_to_smtp_ssl(self):
        import ssl
        ctx = ssl.create_default_context()
        t = make_transport(use_ssl=True, ssl_context=ctx)
        with patch("fluxmail._transport.smtplib.SMTP_SSL") as mock_cls:
            mock_cls.return_value = MagicMock()
            t._make_connection()
        mock_cls.assert_called_once_with(HOST, PORT, context=ctx, timeout=30)


class TestSend:
    def test_transient_send_calls_send_message(self):
        t = make_transport(username="u@example.com")
        mock_conn = MagicMock()
        msg = MagicMock()
        with patch("fluxmail._transport.smtplib.SMTP", return_value=mock_conn):
            t.send(msg)
        mock_conn.send_message.assert_called_once_with(msg)

    def test_transient_send_calls_quit(self):
        t = make_transport()
        mock_conn = MagicMock()
        with patch("fluxmail._transport.smtplib.SMTP", return_value=mock_conn):
            t.send(MagicMock())
        mock_conn.quit.assert_called_once()

    def test_quit_called_even_when_send_message_raises(self):
        t = make_transport()
        mock_conn = MagicMock()
        mock_conn.send_message.side_effect = smtplib.SMTPException("fail")
        with patch("fluxmail._transport.smtplib.SMTP", return_value=mock_conn):
            with pytest.raises(smtplib.SMTPException):
                t.send(MagicMock())
        mock_conn.quit.assert_called_once()

    def test_quit_failure_does_not_mask_send_failure(self):
        t = make_transport()
        mock_conn = MagicMock()
        mock_conn.send_message.side_effect = smtplib.SMTPException("original")
        mock_conn.quit.side_effect = Exception("quit failed")
        with patch("fluxmail._transport.smtplib.SMTP", return_value=mock_conn):
            with pytest.raises(smtplib.SMTPException, match="original"):
                t.send(MagicMock())

    def test_persistent_send_uses_existing_conn(self):
        t = make_transport()
        mock_conn = MagicMock()
        t._conn = mock_conn
        t.send(MagicMock())
        mock_conn.send_message.assert_called_once()
        mock_conn.quit.assert_not_called()


class TestOpenClose:
    def test_open_sets_conn(self):
        t = make_transport()
        mock_conn = MagicMock()
        with patch("fluxmail._transport.smtplib.SMTP", return_value=mock_conn):
            t.open()
        assert t._conn is mock_conn

    def test_close_calls_quit(self):
        t = make_transport()
        mock_conn = MagicMock()
        t._conn = mock_conn
        t.close()
        mock_conn.quit.assert_called_once()

    def test_close_clears_conn(self):
        t = make_transport()
        t._conn = MagicMock()
        t.close()
        assert t._conn is None

    def test_close_noop_when_no_conn(self):
        t = make_transport()
        t.close()  # must not raise

    def test_close_swallows_quit_exception(self):
        t = make_transport()
        mock_conn = MagicMock()
        mock_conn.quit.side_effect = Exception("already closed")
        t._conn = mock_conn
        t.close()  # must not raise
        assert t._conn is None


class TestSendAsync:
    async def test_calls_aiosmtplib_send(self):
        t = make_transport(username="u@example.com", password="pass")
        msg = MagicMock()
        with patch("fluxmail._transport.aiosmtplib.send", new_callable=AsyncMock) as mock_send:
            await t.send_async(msg)
        mock_send.assert_called_once_with(
            msg,
            hostname=HOST,
            port=PORT,
            use_tls=False,
            start_tls=None,
            username="u@example.com",
            password="pass",
            timeout=30,
            tls_context=None,
        )

    async def test_use_ssl_maps_to_use_tls_true(self):
        t = make_transport(use_ssl=True, username="u@example.com", password="pass")
        with patch("fluxmail._transport.aiosmtplib.send", new_callable=AsyncMock) as mock_send:
            await t.send_async(MagicMock())
        _, kwargs = mock_send.call_args
        assert kwargs["use_tls"] is True
        assert kwargs["start_tls"] is None

    async def test_use_tls_maps_to_start_tls_true(self):
        t = make_transport(use_tls=True, username="u@example.com", password="pass")
        with patch("fluxmail._transport.aiosmtplib.send", new_callable=AsyncMock) as mock_send:
            await t.send_async(MagicMock())
        _, kwargs = mock_send.call_args
        assert kwargs["use_tls"] is False
        assert kwargs["start_tls"] is True

    async def test_no_credentials_passes_none(self):
        t = make_transport()
        with patch("fluxmail._transport.aiosmtplib.send", new_callable=AsyncMock) as mock_send:
            await t.send_async(MagicMock())
        _, kwargs = mock_send.call_args
        assert kwargs["username"] is None
        assert kwargs["password"] is None
