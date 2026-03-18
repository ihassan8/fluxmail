"""Test utilities for AutoEmail — not exported from __init__.py."""
from contextlib import contextmanager
from unittest.mock import MagicMock, patch


@contextmanager
def mock_smtp():
    """Patch smtplib.SMTP so tests never open real network connections.

    Yields the mock SMTP instance so callers can assert on calls such as
    ``send_message``, ``starttls``, and ``login``.

    Examples
    --------
    >>> from autoemail.testing import mock_smtp
    >>> from autoemail import AutoEmail, EmailInstance, EmailObject
    >>> with mock_smtp() as smtp:
    ...     AutoEmail(
    ...         object_type=EmailObject.SMTP,
    ...         host=EmailInstance(relay="smtp.example.com"),
    ...         username="sender@example.com",
    ...     ).create(subject="Hi", recipients=["a@b.com"], body="Hello").send()
    ...     smtp.send_message.assert_called_once()
    """
    mock_instance = MagicMock()
    mock_cls = MagicMock()
    mock_cls.return_value.__enter__ = MagicMock(return_value=mock_instance)
    mock_cls.return_value.__exit__ = MagicMock(return_value=False)

    with patch("autoemail.autoemail.smtplib.SMTP", mock_cls):
        yield mock_instance
