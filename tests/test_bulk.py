from unittest.mock import AsyncMock, MagicMock, patch

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
            {"subject": "Bad", "recipients": ["not-valid"], "body": "fail"},
            {"subject": "Good2", "recipients": ["b@b.com"], "body": "ok"},
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
        with patch(
            "fluxmail._transport.smtplib.SMTP", MagicMock(return_value=mock_conn)
        ):
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
        with patch(
            "fluxmail._transport.smtplib.SMTP", MagicMock(return_value=mock_conn)
        ):
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
        with patch(
            "fluxmail._transport.smtplib.SMTP", MagicMock(return_value=mock_conn)
        ):
            mailer = FluxMail(object_type="smtp", host=HOST, username="u@example.com")
            result = BulkSender(mailer).send_batch(make_messages(2), progress=False)
        assert result["errors"] == []

    def test_non_fluxmail_exception_does_not_abort_batch(self):
        # A bad kwarg (typo) causes TypeError in create(); the remaining messages
        # must still be sent and the error must be recorded, not propagated.
        mock_conn = MagicMock()
        messages = [
            {"subject": "Good", "recipients": ["a@b.com"], "body": "ok"},
            {
                "subject": "Bad",
                "recipients": ["a@b.com"],
                "body": "ok",
                "bad_kwarg": True,
            },
            {"subject": "Good2", "recipients": ["b@b.com"], "body": "ok"},
        ]
        with patch(
            "fluxmail._transport.smtplib.SMTP", MagicMock(return_value=mock_conn)
        ):
            mailer = FluxMail(object_type="smtp", host=HOST, username="u@example.com")
            result = BulkSender(mailer).send_batch(messages, progress=False)
        assert result["sent"] == 2
        assert result["failed"] == 1
        assert result["total"] == 3
        assert len(result["errors"]) == 1
        assert result["errors"][0][0] == 1
        assert result["errors"][0][1].code == "send_failed"


class TestSendBatchAsync:
    async def test_all_succeed(self):
        mock_smtp = AsyncMock()
        mock_smtp.__aenter__ = AsyncMock(return_value=mock_smtp)
        mock_smtp.__aexit__ = AsyncMock(return_value=False)
        with patch(
            "fluxmail._transport.aiosmtplib.SMTP", MagicMock(return_value=mock_smtp)
        ):
            mailer = FluxMail(object_type="smtp", host=HOST, username="u@example.com")
            result = await BulkSender(mailer).send_batch_async(
                make_messages(3), progress=False
            )
        assert result["sent"] == 3
        assert result["failed"] == 0
        assert result["total"] == 3
        assert result["errors"] == []

    async def test_partial_failure_isolated(self):
        mock_smtp = AsyncMock()
        mock_smtp.__aenter__ = AsyncMock(return_value=mock_smtp)
        mock_smtp.__aexit__ = AsyncMock(return_value=False)
        messages = [
            {"subject": "Good", "recipients": ["a@b.com"], "body": "ok"},
            {"subject": "Bad", "recipients": ["not-valid"], "body": "fail"},
            {"subject": "Good2", "recipients": ["b@b.com"], "body": "ok"},
        ]
        with patch(
            "fluxmail._transport.aiosmtplib.SMTP", MagicMock(return_value=mock_smtp)
        ):
            mailer = FluxMail(object_type="smtp", host=HOST, username="u@example.com")
            result = await BulkSender(mailer).send_batch_async(messages, progress=False)
        assert result["sent"] == 2
        assert result["failed"] == 1
        assert len(result["errors"]) == 1
        assert result["errors"][0][0] == 1

    async def test_rate_limiting_sleeps(self):
        mock_smtp = AsyncMock()
        mock_smtp.__aenter__ = AsyncMock(return_value=mock_smtp)
        mock_smtp.__aexit__ = AsyncMock(return_value=False)
        with patch(
            "fluxmail._transport.aiosmtplib.SMTP", MagicMock(return_value=mock_smtp)
        ):
            with patch(
                "fluxmail.bulk.asyncio.sleep", new_callable=AsyncMock
            ) as mock_sleep:
                mailer = FluxMail(
                    object_type="smtp", host=HOST, username="u@example.com"
                )
                await BulkSender(mailer).send_batch_async(
                    make_messages(2), progress=False, max_per_second=10
                )
        # 2 messages → sleep after message 0 only (not after the last)
        assert mock_sleep.call_count == 1
        mock_sleep.assert_called_with(pytest.approx(0.1, rel=1e-3))

    async def test_negative_max_per_second_raises(self):
        mailer = FluxMail(object_type="smtp", host=HOST, username="u@example.com")
        with pytest.raises(FluxMailException) as exc_info:
            await BulkSender(mailer).send_batch_async(
                [], progress=False, max_per_second=-1
            )
        assert exc_info.value.code == "invalid_config"

    async def test_outlook_mailer_raises_invalid_config(self):
        # send_batch_async() is SMTP-only — guard checked before any connection
        mailer = FluxMail(object_type="smtp", host=HOST, username="u@example.com")
        with patch.object(FluxMail, "is_smtp", return_value=False):
            with pytest.raises(FluxMailException) as exc_info:
                await BulkSender(mailer).send_batch_async([], progress=False)
        assert exc_info.value.code == "invalid_config"

    async def test_on_error_callback_called(self):
        errors = []
        mock_smtp = AsyncMock()
        mock_smtp.__aenter__ = AsyncMock(return_value=mock_smtp)
        mock_smtp.__aexit__ = AsyncMock(return_value=False)
        with patch(
            "fluxmail._transport.aiosmtplib.SMTP", MagicMock(return_value=mock_smtp)
        ):
            mailer = FluxMail(object_type="smtp", host=HOST, username="u@example.com")
            await BulkSender(mailer).send_batch_async(
                [{"subject": "Hi", "recipients": ["bad"], "body": "Hello"}],
                on_error=lambda i, e: errors.append((i, e)),
                progress=False,
            )
        assert len(errors) == 1
        assert isinstance(errors[0][1], FluxMailException)
