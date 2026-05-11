from unittest.mock import MagicMock, patch

import pytest

from fluxmail import FluxMail, FluxMailException, EmailInstance
from fluxmail.bulk import BulkSender

HOST = EmailInstance(relay="smtp.example.com")


def make_messages(n=3):
    return [
        {"subject": f"Msg {i}", "recipients": ["a@b.com"], "body": str(i)}
        for i in range(n)
    ]


class TestSendBatch:
    def test_all_succeed(self):
        mock_conn = MagicMock()
        mock_cls = MagicMock(return_value=mock_conn)
        with patch("fluxmail._transport.smtplib.SMTP", mock_cls):
            mailer = FluxMail(object_type="smtp", host=HOST, username="u@example.com")
            result = BulkSender(mailer).send_batch(make_messages(), progress=False)
        assert result == {"sent": 3, "failed": 0, "total": 3, "errors": []}

    def test_partial_failure_counted(self):
        mock_conn = MagicMock()
        mock_cls = MagicMock(return_value=mock_conn)
        messages = [
            {"subject": "Good", "recipients": ["a@b.com"], "body": "ok"},
            {"subject": "Bad",  "recipients": ["not-valid"], "body": "fail"},
            {"subject": "Good2","recipients": ["b@b.com"], "body": "ok"},
        ]
        with patch("fluxmail._transport.smtplib.SMTP", mock_cls):
            mailer = FluxMail(object_type="smtp", host=HOST, username="u@example.com")
            result = BulkSender(mailer).send_batch(messages, progress=False)
        assert result["sent"] == 2
        assert result["failed"] == 1
        assert len(result["errors"]) == 1
        assert result["errors"][0][0] == 1  # index of failing message
        assert isinstance(result["errors"][0][1], FluxMailException)

    def test_on_success_callback_called(self):
        successes = []
        mock_conn = MagicMock()
        with patch("fluxmail._transport.smtplib.SMTP", MagicMock(return_value=mock_conn)):
            mailer = FluxMail(object_type="smtp", host=HOST, username="u@example.com")
            BulkSender(mailer).send_batch(
                [{"subject": "Hi", "recipients": ["a@b.com"], "body": "Hello"}],
                on_success=lambda i, r: successes.append((i, r)),
                progress=False,
            )
        assert len(successes) == 1
        assert successes[0][0] == 0

    def test_on_error_callback_called(self):
        errors = []
        mock_conn = MagicMock()
        with patch("fluxmail._transport.smtplib.SMTP", MagicMock(return_value=mock_conn)):
            mailer = FluxMail(object_type="smtp", host=HOST, username="u@example.com")
            BulkSender(mailer).send_batch(
                [{"subject": "Hi", "recipients": ["bad-email"], "body": "Hello"}],
                on_error=lambda i, e: errors.append((i, e)),
                progress=False,
            )
        assert len(errors) == 1
        assert isinstance(errors[0][1], FluxMailException)

    def test_single_connection_reused(self):
        mock_conn = MagicMock()
        mock_cls = MagicMock(return_value=mock_conn)
        with patch("fluxmail._transport.smtplib.SMTP", mock_cls):
            mailer = FluxMail(object_type="smtp", host=HOST, username="u@example.com")
            BulkSender(mailer).send_batch(make_messages(5), progress=False)
        mock_cls.assert_called_once()

    def test_errors_list_empty_on_full_success(self):
        mock_conn = MagicMock()
        with patch("fluxmail._transport.smtplib.SMTP", MagicMock(return_value=mock_conn)):
            mailer = FluxMail(object_type="smtp", host=HOST, username="u@example.com")
            result = BulkSender(mailer).send_batch(make_messages(2), progress=False)
        assert result["errors"] == []
