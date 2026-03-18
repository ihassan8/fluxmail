# Plan 2: New Feature Modules — EmailTemplate, Async, Retry, BulkSender

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the four new modules specified in the approved design spec: Jinja2-based body templating, async SMTP, retry logic, and a bulk-send loop with a progress bar.

**Architecture:** Each feature lives in its own new file (`template.py`, `bulk.py`) or as new methods on `AutoEmail` (`send_async`, retry via `tenacity`). New public classes (`EmailTemplate`, `BulkSender`) are exported from `__init__.py`; `mock_smtp()` from Plan 1 is reused throughout. The async method lives on `AutoEmail` itself since it shares all constructor state.

**Tech Stack:** `jinja2>=3.0`, `aiosmtplib>=3.0`, `tenacity>=8.0`, `rich` (already available via `typer[all]`)

**Prerequisite:** Plan 1 must be complete — this plan's tests use `mock_smtp()` and the shared fixtures from `conftest.py`.

---

## File Map

| Action | Path | Responsibility |
|--------|------|---------------|
| Modify | `requirements.txt` | Add `jinja2`, `aiosmtplib`, `tenacity` |
| Create | `src/autoemail/template.py` | `EmailTemplate` class |
| Create | `src/autoemail/bulk.py` | `BulkSender` class |
| Modify | `src/autoemail/autoemail.py` | Add `max_retries`, `retry_delay` slots + `send_async()` |
| Modify | `src/autoemail/__init__.py` | Export `EmailTemplate`, `BulkSender` |
| Create | `tests/test_template.py` | Tests for `EmailTemplate` |
| Create | `tests/test_async.py` | Tests for `send_async()` |
| Create | `tests/test_bulk.py` | Tests for `BulkSender` |
| Modify | `tests/test_autoemail.py` | Tests for retry logic |

### New `__slots__` entries on `AutoEmail`

`"max_retries"`, `"retry_delay"` — initialised to `0` and `1.0` respectively in `__init__`.

---

## Task 1: Add Runtime Dependencies

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Append new deps to `requirements.txt`**

```
jinja2>=3.0
aiosmtplib>=3.0
tenacity>=8.0
```

- [ ] **Step 2: Install and verify**

```bash
pip install -r requirements.txt
python -c "import jinja2, aiosmtplib, tenacity; print('ok')"
```
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add requirements.txt
git commit -m "chore: add jinja2, aiosmtplib, tenacity dependencies"
```

---

## Task 2: `EmailTemplate`

**Files:**
- Create: `src/autoemail/template.py`
- Create: `tests/test_template.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_template.py
import pytest
from autoemail import EmailTemplate
from autoemail.utils import AutoEmailException


class TestEmailTemplate:
    def test_render_string_template(self):
        t = EmailTemplate("Hello, {{ name }}!")
        assert t.render(name="World") == "Hello, World!"

    def test_render_multiline(self):
        t = EmailTemplate("Dear {{ name }},\n\nRegards")
        result = t.render(name="Alice")
        assert "Alice" in result

    def test_missing_variable_raises(self):
        t = EmailTemplate("Hello {{ name }}")
        with pytest.raises(AutoEmailException, match="Template render failed"):
            t.render()  # name not provided — Jinja2 will raise UndefinedError

    def test_from_file(self, tmp_path):
        tpl = tmp_path / "email.html"
        tpl.write_text("<h1>{{ title }}</h1>")
        t = EmailTemplate.from_file(str(tpl))
        assert t.render(title="Report") == "<h1>Report</h1>"

    def test_from_file_not_found_raises(self):
        with pytest.raises(AutoEmailException, match="not found"):
            EmailTemplate.from_file("/nonexistent/template.html")

    def test_repr_contains_class_name(self):
        t = EmailTemplate("Hello")
        assert "EmailTemplate" in repr(t)
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/test_template.py -v
```
Expected: FAIL (cannot import `EmailTemplate`).

- [ ] **Step 3: Implement `src/autoemail/template.py`**

```python
"""Jinja2-based email body templating."""
from typing import Any

from jinja2 import Environment, StrictUndefined, UndefinedError

from .utils import AutoEmailException


class EmailTemplate:
    """Render email bodies from Jinja2 templates.

    Parameters
    ----------
    template_string : str
        A Jinja2 template string.

    Examples
    --------
    >>> t = EmailTemplate("Hello, {{ name }}!")
    >>> t.render(name="Alice")
    'Hello, Alice!'
    """

    def __init__(self, template_string: str) -> None:
        self._env = Environment(undefined=StrictUndefined)
        self._template = self._env.from_string(template_string)
        self._source = template_string

    @classmethod
    def from_file(cls, path: str) -> "EmailTemplate":
        """Load a template from a file on disk.

        Parameters
        ----------
        path : str
            Absolute or relative path to the template file.

        Raises
        ------
        AutoEmailException
            If the file is not found or cannot be read.
        """
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return cls(fh.read())
        except FileNotFoundError:
            raise AutoEmailException(f"Template file not found: '{path}'")
        except OSError as exc:
            raise AutoEmailException(f"Cannot read template file '{path}': {exc}")

    def render(self, **kwargs: Any) -> str:
        """Render the template with the given variables.

        Parameters
        ----------
        **kwargs
            Template context variables.

        Returns
        -------
        str
            Rendered string.

        Raises
        ------
        AutoEmailException
            If a required variable is missing or rendering fails.
        """
        try:
            return self._template.render(**kwargs)
        except UndefinedError as exc:
            raise AutoEmailException(f"Template render failed: {exc}")
        except Exception as exc:
            raise AutoEmailException(f"Template render error: {exc}")

    def __repr__(self) -> str:
        preview = self._source[:40].replace("\n", " ")
        return f"EmailTemplate({preview!r}{'...' if len(self._source) > 40 else ''})"
```

- [ ] **Step 4: Export from `__init__.py`**

```python
from .template import EmailTemplate
```

Add `"EmailTemplate"` to `__all__`.

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_template.py -v
```
Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add src/autoemail/template.py src/autoemail/__init__.py tests/test_template.py
git commit -m "feat: add EmailTemplate for Jinja2-based body templating"
```

---

## Task 3: Retry Logic

**Files:**
- Modify: `src/autoemail/autoemail.py`
- Modify: `tests/test_autoemail.py`

**Background:** `tenacity` wraps the send attempt with configurable retries and exponential/fixed delay. The retry count and delay are constructor params so one instance can be configured once and reused.

- [ ] **Step 1: Write failing tests**

Add to `tests/test_autoemail.py`:

```python
class TestRetry:
    def test_send_succeeds_first_attempt_no_retry(self):
        with mock_smtp() as smtp:
            e = AutoEmail(object_type="smtp", host=EmailEnv.Domain1, max_retries=3)
            e.create(subject="Hi", recipients=["a@b.com"], body="Hello").send()
        assert smtp.send_message.call_count == 1

    def test_send_retries_on_failure(self):
        from unittest.mock import patch, MagicMock
        call_count = {"n": 0}

        def flaky_send_message(msg):
            call_count["n"] += 1
            if call_count["n"] < 3:
                raise ConnectionError("transient")

        with mock_smtp() as smtp:
            smtp.send_message.side_effect = flaky_send_message
            e = AutoEmail(
                object_type="smtp", host=EmailEnv.Domain1,
                max_retries=3, retry_delay=0.0,
            )
            e.create(subject="Hi", recipients=["a@b.com"], body="Hello").send()

        assert call_count["n"] == 3

    def test_exhausted_retries_raises(self):
        with mock_smtp() as smtp:
            smtp.send_message.side_effect = ConnectionError("always fails")
            e = AutoEmail(
                object_type="smtp", host=EmailEnv.Domain1,
                max_retries=2, retry_delay=0.0,
            )
            e.create(subject="Hi", recipients=["a@b.com"], body="Hello")
            with pytest.raises(AutoEmailException):
                e.send()
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/test_autoemail.py::TestRetry -v
```
Expected: FAIL (`max_retries` unexpected keyword argument).

- [ ] **Step 3: Add `max_retries` and `retry_delay` to `__slots__` and `__init__`**

In `__slots__`:

```python
"max_retries",
"retry_delay",
```

In `__init__` signature:

```python
max_retries: int = 0,
retry_delay: float = 1.0,
```

In `__init__` body:

```python
self.max_retries = max_retries
self.retry_delay = retry_delay
```

- [ ] **Step 4: Add retry import and `_send_smtp()` helper**

At the top of `autoemail.py`:

```python
from tenacity import retry, stop_after_attempt, wait_fixed, RetryError
```

Extract the SMTP send into a private helper and wrap it with retry:

```python
def _send_smtp_once(self, smtp_client) -> None:
    """Send self.message via the given smtplib client object."""
    smtp_client.send_message(self.message)

def _send_with_retry(self, smtp_client) -> None:
    """Call _send_smtp_once, retrying up to max_retries times on any exception."""
    if self.max_retries < 1:
        self._send_smtp_once(smtp_client)
        return

    attempt_fn = retry(
        stop=stop_after_attempt(self.max_retries + 1),
        wait=wait_fixed(self.retry_delay),
        reraise=True,
    )(self._send_smtp_once)

    try:
        attempt_fn(smtp_client)
    except Exception as exc:
        raise AutoEmailException(f"Send failed after {self.max_retries} retries: {exc}")
```

- [ ] **Step 5: Update `send()` to call `_send_with_retry()`**

Replace both `smtp.send_message(self.message)` call sites in `send()`:

- In the `_smtp_conn` (context manager) branch: `self._send_with_retry(self._smtp_conn)`
- In the `with smtplib.SMTP(...)` branch: `self._send_with_retry(smtp)`

- [ ] **Step 6: Run all tests**

```bash
pytest tests/ -v
```
Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add src/autoemail/autoemail.py tests/test_autoemail.py
git commit -m "feat: add max_retries/retry_delay via tenacity"
```

---

## Task 4: `send_async()`

**Files:**
- Modify: `src/autoemail/autoemail.py`
- Modify: `requirements-dev.txt`
- Create: `tests/test_async.py`

- [ ] **Step 1: Add `pytest-asyncio` to dev deps**

```
pytest-asyncio>=0.23
```

Append `asyncio_mode = "auto"` to `[tool.pytest.ini_options]` in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

Install: `pip install -r requirements-dev.txt`

- [ ] **Step 2: Write failing tests**

```python
# tests/test_async.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from autoemail import AutoEmail, EmailEnv, AutoEmailException


@pytest.fixture
def async_email():
    return AutoEmail(object_type="smtp", host=EmailEnv.Domain1)


async def test_send_async_calls_send_message(async_email):
    mock_smtp = AsyncMock()
    mock_cls = MagicMock()
    mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_smtp)
    mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

    with patch("autoemail.autoemail.aiosmtplib.SMTP", mock_cls):
        async_email.create(subject="Hi", recipients=["a@b.com"], body="Hello")
        result = await async_email.send_async()

    assert "sent successfully" in result
    mock_smtp.send_message.assert_awaited_once()


async def test_send_async_with_tls(async_email):
    mock_smtp = AsyncMock()
    mock_cls = MagicMock()
    mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_smtp)
    mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

    e = AutoEmail(object_type="smtp", host=EmailEnv.Domain1, use_tls=True)
    with patch("autoemail.autoemail.aiosmtplib.SMTP", mock_cls):
        e.create(subject="Hi", recipients=["a@b.com"], body="Hello")
        await e.send_async()

    mock_smtp.starttls.assert_awaited_once()


async def test_send_async_before_create_raises(async_email):
    with pytest.raises(AutoEmailException, match="create()"):
        await async_email.send_async()


async def test_send_async_on_outlook_raises():
    from autoemail import EmailObject
    import platform
    if platform.system() != "Windows":
        pytest.skip("Outlook only on Windows")
    e = AutoEmail(object_type=EmailObject.OUTLOOK, host=EmailEnv.Domain1)
    with pytest.raises(AutoEmailException):
        await e.send_async()
```

- [ ] **Step 3: Run to confirm failure**

```bash
pytest tests/test_async.py -v
```
Expected: FAIL (`send_async` attribute does not exist).

- [ ] **Step 4: Add `aiosmtplib` import to `autoemail.py`**

```python
import aiosmtplib
```

- [ ] **Step 5: Implement `send_async()`**

```python
async def send_async(self) -> str:
    """Send the email asynchronously via aiosmtplib.

    Returns
    -------
    str
        Success message.

    Raises
    ------
    AutoEmailException
        If ``create()`` has not been called, if used with Outlook, or on send failure.
    """
    if not self.is_created:
        raise AutoEmailException("Call create() before send_async().")
    if self.is_outlook():
        raise AutoEmailException("Outlook does not support async sending.")

    try:
        async with aiosmtplib.SMTP(hostname=self.host.relay, port=self.port) as smtp:
            if self.use_tls:
                await smtp.starttls()
            if self.username and self.password:
                await smtp.login(self.username, self.password)
            await smtp.send_message(self.message)
        return "Email sent successfully via async SMTP."
    except AutoEmailException:
        raise
    except Exception as exc:
        msg = f"Async send failed: {exc}"
        self.logger.error(msg)
        raise AutoEmailException(msg)
```

- [ ] **Step 6: Run all tests**

```bash
pytest tests/ -v
```
Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add src/autoemail/autoemail.py tests/test_async.py requirements-dev.txt pyproject.toml
git commit -m "feat: add send_async() via aiosmtplib"
```

---

## Task 5: `BulkSender`

**Files:**
- Create: `src/autoemail/bulk.py`
- Create: `tests/test_bulk.py`
- Modify: `src/autoemail/__init__.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_bulk.py
import pytest
from autoemail import BulkSender, EmailEnv, EmailObject, AutoEmailException
from autoemail.testing import mock_smtp


class TestBulkSender:
    def test_sends_to_each_recipient(self):
        recipients = ["a@b.com", "c@d.com", "e@f.com"]
        with mock_smtp() as smtp:
            bs = BulkSender(
                object_type=EmailObject.SMTP,
                host=EmailEnv.Domain1,
                subject="Hello",
                body="Hi there",
                recipients=recipients,
            )
            results = bs.send_all()

        assert smtp.send_message.call_count == 3
        assert len(results) == 3
        assert all(r["status"] == "sent" for r in results)

    def test_results_contain_recipient(self):
        with mock_smtp():
            bs = BulkSender(
                object_type=EmailObject.SMTP,
                host=EmailEnv.Domain1,
                subject="Hi",
                body="Hello",
                recipients=["a@b.com"],
            )
            results = bs.send_all()

        assert results[0]["recipient"] == "a@b.com"

    def test_failed_sends_recorded_not_raised(self):
        from unittest.mock import patch, MagicMock

        mock_conn = MagicMock()
        mock_conn.send_message.side_effect = ConnectionError("refused")
        mock_cls = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)

        with patch("autoemail.autoemail.smtplib.SMTP", mock_cls):
            bs = BulkSender(
                object_type=EmailObject.SMTP,
                host=EmailEnv.Domain1,
                subject="Hi",
                body="Hello",
                recipients=["a@b.com", "c@d.com"],
            )
            results = bs.send_all()

        assert all(r["status"] == "failed" for r in results)
        assert all("error" in r for r in results)

    def test_empty_recipients_raises(self):
        with pytest.raises(AutoEmailException, match="recipients"):
            BulkSender(
                object_type=EmailObject.SMTP,
                host=EmailEnv.Domain1,
                subject="Hi",
                body="Hello",
                recipients=[],
            )
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/test_bulk.py -v
```
Expected: FAIL (cannot import `BulkSender`).

- [ ] **Step 3: Implement `src/autoemail/bulk.py`**

```python
"""BulkSender — send one email per recipient with a progress bar."""
import logging
from typing import Any, Dict, List, Optional, Union

from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from .autoemail import AutoEmail
from .utils import AutoEmailException, EmailEnv, EmailInstance, EmailObject


class BulkSender:
    """Send individual personalised emails to a list of recipients.

    Each recipient receives a separate SMTP transaction (not a single
    message with multiple To addresses). A ``rich`` progress bar is
    displayed during sending.

    Parameters
    ----------
    object_type : Union[EmailObject, str]
        Email protocol — ``"smtp"`` only (Outlook is not supported).
    host : Union[EmailEnv, EmailInstance, str]
        SMTP relay host.
    subject : str
        Email subject. May contain ``{recipient}`` which is replaced with
        the current address.
    body : str
        Email body. May contain ``{recipient}`` which is replaced with the
        current address.
    recipients : List[str]
        Non-empty list of recipient addresses.
    show_progress : bool, optional
        Display a ``rich`` progress bar. Default: ``True``.
    **kwargs
        All remaining keyword arguments are forwarded to ``AutoEmail.__init__``
        (e.g. ``port``, ``use_tls``, ``username``, ``password``, ``max_retries``).

    Examples
    --------
    >>> bs = BulkSender(
    ...     object_type="smtp",
    ...     host=EmailEnv.Domain1,
    ...     subject="Hello {recipient}",
    ...     body="Hi there",
    ...     recipients=["a@hr.acme.com", "b@hr.acme.com"],
    ... )
    >>> results = bs.send_all()
    """

    def __init__(
        self,
        object_type: Union[EmailObject, str],
        host: Union[EmailEnv, EmailInstance, str],
        subject: str,
        body: str,
        recipients: List[str],
        show_progress: bool = True,
        **kwargs: Any,
    ) -> None:
        if not recipients:
            raise AutoEmailException("BulkSender requires a non-empty recipients list.")
        self.object_type = object_type
        self.host = host
        self.subject = subject
        self.body = body
        self.recipients = recipients
        self.show_progress = show_progress
        self._kwargs = kwargs

    def send_all(self) -> List[Dict[str, Any]]:
        """Send to every recipient and return a results list.

        Returns
        -------
        list of dict
            Each entry has keys ``recipient`` (str), ``status`` (``"sent"`` or
            ``"failed"``), and optionally ``error`` (str) on failure.
        """
        results: List[Dict[str, Any]] = []

        with AutoEmail(object_type=self.object_type, host=self.host,
                       **self._kwargs) as mailer:
            progress_ctx = Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                disable=not self.show_progress,
            )
            with progress_ctx as progress:
                task = progress.add_task(
                    "Sending emails...", total=len(self.recipients)
                )
                for recipient in self.recipients:
                    subject = self.subject.replace("{recipient}", recipient)
                    body = self.body.replace("{recipient}", recipient)
                    try:
                        mailer.create(
                            subject=subject,
                            recipients=[recipient],
                            body=body,
                        ).send()
                        results.append({"recipient": recipient, "status": "sent"})
                    except AutoEmailException as exc:
                        results.append({
                            "recipient": recipient,
                            "status": "failed",
                            "error": str(exc),
                        })
                    progress.advance(task)

        return results
```

- [ ] **Step 4: Export from `__init__.py`**

```python
from .bulk import BulkSender
```

Add `"BulkSender"` to `__all__`.

- [ ] **Step 5: Run all tests**

```bash
pytest tests/ -v
```
Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add src/autoemail/bulk.py src/autoemail/__init__.py tests/test_bulk.py
git commit -m "feat: add BulkSender with per-recipient send loop and progress bar"
```

---

## Task 6: Final Run & Docs Update

- [ ] **Step 1: Run full test suite**

```bash
pytest tests/ -v --tb=short
```
Expected: all green.

- [ ] **Step 2: Update `docs/getting-started/usage.md`** — add sections:

```markdown
## EmailTemplate

```python
from autoemail import EmailTemplate, AutoEmail, EmailEnv, EmailObject

template = EmailTemplate("Dear {{ name }},\n\n{{ body }}")
rendered = template.render(name="Alice", body="Your report is attached.")

AutoEmail(object_type=EmailObject.SMTP, host=EmailEnv.Domain1).create(
    subject="Your Report",
    recipients=["alice@hr.acme.com"],
    body=rendered,
).send()
```

## Async Send

```python
import asyncio
from autoemail import AutoEmail, EmailEnv

async def main():
    email = AutoEmail(object_type="smtp", host=EmailEnv.Domain1)
    email.create(subject="Hi", recipients=["user@hr.acme.com"], body="Hello")
    await email.send_async()

asyncio.run(main())
```

## Retry on Failure

```python
email = AutoEmail(
    object_type="smtp",
    host=EmailEnv.Domain1,
    max_retries=3,
    retry_delay=2.0,   # seconds between attempts
)
email.create(...).send()
```

## Bulk Send

```python
from autoemail import BulkSender, EmailEnv

bs = BulkSender(
    object_type="smtp",
    host=EmailEnv.Domain1,
    subject="Weekly Update",
    body="Hi, see this week's update below.",
    recipients=["alice@hr.acme.com", "bob@hr.acme.com"],
)
results = bs.send_all()
for r in results:
    print(r["recipient"], r["status"])
```
```

- [ ] **Step 3: Commit docs**

```bash
git add docs/
git commit -m "docs: document Plan 2 features"
```
