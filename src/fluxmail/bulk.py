import asyncio
from typing import Any, Callable, Dict, List, Optional, Tuple

from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn

from .fluxmail import FluxMail
from .utils import FluxMailException


class BulkSender:
    """Send a batch of emails over a single persistent SMTP connection."""

    def __init__(self, mailer: FluxMail) -> None:
        self._mailer = mailer

    def send_batch(
        self,
        messages: List[Dict[str, Any]],
        *,
        on_success: Optional[Callable[[int, str], None]] = None,
        on_error: Optional[Callable[[int, FluxMailException], None]] = None,
        progress: bool = True,
    ) -> Dict[str, Any]:
        """Send a list of message kwargs through one SMTP connection.

        Parameters
        ----------
        messages : list of dict
            Each dict is unpacked as keyword arguments to ``FluxMail.create()``.
        on_success : callable, optional
            Called with ``(index, result_string)`` after each successful send.
        on_error : callable, optional
            Called with ``(index, exception)`` after each failed send.
        progress : bool, optional
            Show a Rich progress bar. Default: ``True``.

        Returns
        -------
        dict
            ``{"sent": int, "failed": int, "total": int,
               "errors": List[Tuple[int, FluxMailException]]}``
        """
        sent = 0
        failed = 0
        total = len(messages)
        errors: List[Tuple[int, FluxMailException]] = []

        def _execute(prog=None, task_id=None):
            nonlocal sent, failed
            with self._mailer:
                for i, kwargs in enumerate(messages):
                    try:
                        result = self._mailer.create(**kwargs).send()
                        sent += 1
                        if on_success:
                            on_success(i, result)
                    except Exception as exc:
                        failed += 1
                        err = (
                            exc if isinstance(exc, FluxMailException)
                            else FluxMailException(f"Message {i} failed: {exc}", code="send_failed")
                        )
                        errors.append((i, err))
                        if on_error:
                            on_error(i, err)
                    if prog is not None:
                        prog.advance(task_id)

        if progress:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
            ) as prog:
                task_id = prog.add_task("Sending…", total=total)
                _execute(prog, task_id)
        else:
            _execute()

        return {"sent": sent, "failed": failed, "total": total, "errors": errors}

    async def send_batch_async(
        self,
        messages: List[Dict[str, Any]],
        *,
        on_success: Optional[Callable[[int, str], None]] = None,
        on_error: Optional[Callable[[int, FluxMailException], None]] = None,
        progress: bool = True,
        max_per_second: float = 0,
    ) -> Dict[str, Any]:
        """Send a batch of emails over one persistent async SMTP connection.

        Parameters
        ----------
        messages : list of dict
            Each dict is unpacked as keyword arguments to ``FluxMail.create()``.
        on_success : callable, optional
            Called with ``(index, result_string)`` after each successful send.
        on_error : callable, optional
            Called with ``(index, exception)`` after each failed send.
        progress : bool, optional
            Show a Rich progress bar. Default: ``True``.
        max_per_second : float, optional
            Maximum sends per second. ``0`` disables rate limiting. Default: ``0``.

        Returns
        -------
        dict
            ``{"sent": int, "failed": int, "total": int,
               "errors": List[Tuple[int, FluxMailException]]}``
        """
        if not self._mailer.is_smtp():
            raise FluxMailException(
                "send_batch_async() is only supported for SMTP.", code="invalid_config"
            )
        if max_per_second < 0:
            raise FluxMailException(
                "max_per_second must be >= 0.", code="invalid_config"
            )

        sent = 0
        failed = 0
        total = len(messages)
        errors: List[Tuple[int, FluxMailException]] = []

        async def _execute(prog=None, task_id=None):
            nonlocal sent, failed
            async with self._mailer._transport.async_connection() as smtp:
                for i, kwargs in enumerate(messages):
                    try:
                        self._mailer.create(**kwargs)
                        await smtp.send_message(self._mailer.message)
                        sent += 1
                        if on_success:
                            on_success(i, "Email sent successfully via SMTP.")
                        if max_per_second > 0 and i < total - 1:
                            await asyncio.sleep(1 / max_per_second)
                    except Exception as exc:
                        failed += 1
                        err = (
                            exc if isinstance(exc, FluxMailException)
                            else FluxMailException(
                                f"Message {i} failed: {exc}", code="send_failed"
                            )
                        )
                        errors.append((i, err))
                        if on_error:
                            on_error(i, err)
                    if prog is not None:
                        prog.advance(task_id)

        if progress:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
            ) as prog:
                task_id = prog.add_task("Sending…", total=total)
                await _execute(prog, task_id)
        else:
            await _execute()

        return {"sent": sent, "failed": failed, "total": total, "errors": errors}
