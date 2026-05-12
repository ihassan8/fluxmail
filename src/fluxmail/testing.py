"""Test utilities for FluxMail — not exported from __init__.py."""

from contextlib import contextmanager
from unittest.mock import MagicMock, patch


@contextmanager
def mock_smtp():
    """Patch smtplib.SMTP in the transport layer so tests never open real connections.

    Yields the mock SMTP instance (the raw return value of smtplib.SMTP()) so
    callers can assert on send_message, starttls, login, and quit.

    Examples
    --------
    >>> from fluxmail.testing import mock_smtp
    >>> from fluxmail import FluxMail, EmailInstance, EmailObject
    >>> with mock_smtp() as smtp:
    ...     FluxMail(
    ...         object_type=EmailObject.SMTP,
    ...         host=EmailInstance(relay="smtp.example.com"),
    ...         username="sender@example.com",
    ...     ).create(subject="Hi", recipients=["a@b.com"], body="Hello").send()
    ...     smtp.send_message.assert_called_once()
    """
    mock_instance = MagicMock()
    mock_cls = MagicMock(return_value=mock_instance)

    with patch("fluxmail._transport.smtplib.SMTP", mock_cls):
        yield mock_instance
