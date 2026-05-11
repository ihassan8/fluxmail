# FluxMail Missing Features Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement nine missing features — transport layer refactor, timeout/SSL params, error codes, Message-ID, async send, retry, EmailTemplate, BulkSender, and CLI flags.

**Architecture:** A private `_SMTPTransport` class absorbs all SMTP connection logic (sync + async, SSL variants, timeout), eliminating duplication between `send()` and `send_async()`. `EmailTemplate` and `BulkSender` are independent new files. All changes are backward-compatible.

**Tech Stack:** Python 3.8+, smtplib, aiosmtplib, tenacity, jinja2, rich (via typer[all]), pytest-asyncio

**Spec:** `docs/superpowers/specs/2026-05-11-missing-features-design.md`

---

## File Map

| Action | File | Responsibility |
|---|---|---|
| **Create** | `src/fluxmail/_transport.py` | All SMTP connection logic — sync and async |
| **Create** | `src/fluxmail/template.py` | Jinja2 body renderer |
| **Create** | `src/fluxmail/bulk.py` | Batch sender with Rich progress bar |
| **Create** | `tests/test_transport.py` | `_SMTPTransport` unit tests |
| **Create** | `tests/test_template.py` | `EmailTemplate` unit tests |
| **Create** | `tests/test_bulk.py` | `BulkSender` unit tests |
| **Modify** | `src/fluxmail/utils.py` | Add `code` param to `FluxMailException` |
| **Modify** | `src/fluxmail/fluxmail.py` | New constructor params, transport wiring, `send_async()`, `_handle_message_id()`, error codes |
| **Modify** | `src/fluxmail/__init__.py` | Export `EmailTemplate`, `BulkSender` |
| **Modify** | `src/fluxmail/fluxmail_cli.py` | `--ssl`, `--timeout`, `--max-retries`, `--retry-delay` |
| **Modify** | `src/fluxmail/testing.py` | Redesign `mock_smtp()` for transport layer |
| **Modify** | `requirements.txt` | Add aiosmtplib, tenacity, jinja2 |
| **Modify** | `requirements-dev.txt` | Add pytest-asyncio |
| **Modify** | `pyproject.toml` | Add `asyncio_mode = "auto"` |
| **Modify** | `CLAUDE.md` | Update architecture table |

---

### Task 1: FluxMailException error codes

**Files:**
- Modify: `src/fluxmail/utils.py`
- Test: `tests/test_utils.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_utils.py`:

```python
class TestFluxMailExceptionCode:
    def test_code_stored(self):
        exc = FluxMailException("something broke", code="send_failed")
        assert exc.code == "send_failed"

    def test_code_defaults_to_none(self):
        exc = FluxMailException("something broke")
        assert exc.code is None

    def test_message_unaffected(self):
        exc = FluxMailException("oops", code="x")
        assert str(exc) == "oops"
```

- [ ] **Step 2: Run — expect FAIL**

```
pytest tests/test_utils.py::TestFluxMailExceptionCode -v
```
Expected: `TypeError: __init__() got an unexpected keyword argument 'code'`

- [ ] **Step 3: Implement**

In `src/fluxmail/utils.py`, add `Optional` to the typing import and replace the `FluxMailException` class:

```python
from typing import Optional, Type, TypeVar, Union   # add Optional
```

```python
class FluxMailException(Exception):
    """Custom exception class for FluxMail errors."""

    def __init__(self, message: str, code: Optional[str] = None) -> None:
        super().__init__(message)
        self.code = code
```

- [ ] **Step 4: Run — expect PASS**

```
pytest tests/test_utils.py -v
```
Expected: all pass

- [ ] **Step 5: Commit**

```
git add src/fluxmail/utils.py tests/test_utils.py
git commit -m "feat: add structured error code to FluxMailException"
```

---

### Task 2: Add dependencies and configure pytest asyncio

**Files:**
- Modify: `requirements.txt`, `requirements-dev.txt`, `pyproject.toml`

- [ ] **Step 1: Update requirements.txt** — append these three lines:

```
aiosmtplib>=3.0
tenacity>=8.0
jinja2>=3.1
```

- [ ] **Step 2: Update requirements-dev.txt** — append:

```
pytest-asyncio>=0.23
```

- [ ] **Step 3: Update pyproject.toml** — replace the `[tool.pytest.ini_options]` section:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

- [ ] **Step 4: Install**

```
pip install -r requirements.txt -r requirements-dev.txt
```

- [ ] **Step 5: Run full suite — expect all still pass**

```
pytest tests/ -v
```

- [ ] **Step 6: Commit**

```
git add requirements.txt requirements-dev.txt pyproject.toml
git commit -m "feat: add aiosmtplib/tenacity/jinja2 deps, configure asyncio_mode=auto"
```

---

### Task 3: `_SMTPTransport` — sync path

**Files:**
- Create: `src/fluxmail/_transport.py`
- Create: `tests/test_transport.py`

- [ ] **Step 1: Write failing tests** — create `tests/test_transport.py`:

```python
import smtplib
from unittest.mock import MagicMock, patch

import pytest

from fluxmail._transport import _SMTPTransport

HOST = "smtp.example.com"
PORT = 587


def make_transport(**kwargs):
    defaults = dict(
        relay=HOST, port=PORT,
        use_ssl=False, use_tls=False,
        ssl_context=None, timeout=30,
        username=None, password=None,
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
```

- [ ] **Step 2: Run — expect FAIL**

```
pytest tests/test_transport.py -v
```
Expected: `ModuleNotFoundError: No module named 'fluxmail._transport'`

- [ ] **Step 3: Create `src/fluxmail/_transport.py`**

```python
import smtplib
import ssl as _ssl
from typing import Optional


class _SMTPTransport:
    """Private SMTP connection manager — sync path only (async added separately)."""

    def __init__(
        self,
        relay: str,
        port: int,
        *,
        use_ssl: bool,
        use_tls: bool,
        ssl_context: Optional[_ssl.SSLContext],
        timeout: int,
        username: Optional[str],
        password: Optional[str],
    ) -> None:
        self._relay = relay
        self._port = port
        self._use_ssl = use_ssl
        self._use_tls = use_tls
        self._ssl_context = ssl_context
        self._timeout = timeout
        self._username = username
        self._password = password
        self._conn: Optional[smtplib.SMTP] = None

    def _make_connection(self) -> smtplib.SMTP:
        if self._use_ssl:
            conn: smtplib.SMTP = smtplib.SMTP_SSL(
                self._relay, self._port,
                context=self._ssl_context,
                timeout=self._timeout,
            )
        else:
            conn = smtplib.SMTP(self._relay, self._port, timeout=self._timeout)
            if self._use_tls:
                conn.starttls(context=self._ssl_context)
        if self._username and self._password:
            conn.login(self._username, self._password)
        return conn

    def send(self, message) -> None:
        if self._conn is not None:
            self._conn.send_message(message)
        else:
            conn = self._make_connection()
            try:
                conn.send_message(message)
            finally:
                try:
                    conn.quit()
                except Exception:
                    pass

    def open(self) -> None:
        self._conn = self._make_connection()

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.quit()
            except Exception:
                pass
            self._conn = None
```

- [ ] **Step 4: Run — expect PASS**

```
pytest tests/test_transport.py -v
```

- [ ] **Step 5: Commit**

```
git add src/fluxmail/_transport.py tests/test_transport.py
git commit -m "feat: add _SMTPTransport sync path"
```

---

### Task 4: `_SMTPTransport` — async path

**Files:**
- Modify: `src/fluxmail/_transport.py`
- Modify: `tests/test_transport.py`

- [ ] **Step 1: Write failing tests** — append to `tests/test_transport.py`:

```python
from unittest.mock import AsyncMock


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
```

- [ ] **Step 2: Run — expect FAIL**

```
pytest tests/test_transport.py::TestSendAsync -v
```
Expected: `AttributeError: '_SMTPTransport' object has no attribute 'send_async'`

- [ ] **Step 3: Implement** — add to `src/fluxmail/_transport.py`:

At the top, add import after `import smtplib`:
```python
import aiosmtplib
```

Add this method to `_SMTPTransport` after `close()`:

```python
    async def send_async(self, message) -> None:
        await aiosmtplib.send(
            message,
            hostname=self._relay,
            port=self._port,
            use_tls=self._use_ssl,
            start_tls=True if self._use_tls else None,
            username=self._username if (self._username and self._password) else None,
            password=self._password if (self._username and self._password) else None,
            timeout=self._timeout,
            tls_context=self._ssl_context,
        )
```

- [ ] **Step 4: Run — expect PASS**

```
pytest tests/test_transport.py -v
```

- [ ] **Step 5: Commit**

```
git add src/fluxmail/_transport.py tests/test_transport.py
git commit -m "feat: add _SMTPTransport async path via aiosmtplib"
```

---

### Task 5: Redesign `mock_smtp()` and fix test patch paths

**Files:**
- Modify: `src/fluxmail/testing.py`
- Modify: `tests/test_fluxmail.py`

- [ ] **Step 1: Update `src/fluxmail/testing.py`**

Replace the entire file content:

```python
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
```

- [ ] **Step 2: Fix `TestContextManager` patch paths in `tests/test_fluxmail.py`**

Find and update both manual `patch` calls inside `TestContextManager`. Change:
```python
with patch("fluxmail.fluxmail.smtplib.SMTP", mock_cls):
```
To:
```python
with patch("fluxmail._transport.smtplib.SMTP", mock_cls):
```
This appears in `test_context_manager_reuses_connection` and `test_context_manager_calls_quit_on_exit`.

- [ ] **Step 3: Run full suite — all 95 tests must pass**

```
pytest tests/ -v
```
Expected: 95 passed. If any test fails at this step, the mock redesign has a gap — do not proceed.

- [ ] **Step 4: Commit**

```
git add src/fluxmail/testing.py tests/test_fluxmail.py
git commit -m "fix: redesign mock_smtp() for transport layer; update patch paths"
```

---

### Task 6: Wire `_SMTPTransport` into `FluxMail`

**Files:**
- Modify: `src/fluxmail/fluxmail.py`
- Modify: `tests/test_fluxmail.py`

- [ ] **Step 1: Write new failing tests** — append to `tests/test_fluxmail.py`:

```python
import smtplib  # add to top-level imports in test_fluxmail.py


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
```

Also add `from unittest.mock import patch, MagicMock` to the imports at the top of `tests/test_fluxmail.py` (they are currently inside individual test methods; move them to module level for the new tests above).

- [ ] **Step 2: Run — expect FAIL**

```
pytest tests/test_fluxmail.py::TestNewConstructorParams tests/test_fluxmail.py::TestMessageID tests/test_fluxmail.py::TestErrorCodes -v
```
Expected: `AttributeError: 'FluxMail' object has no attribute 'timeout'`

- [ ] **Step 3: Implement — update `src/fluxmail/fluxmail.py`**

**3a — Add imports** (replace existing import block at the top):

```python
import logging
import mimetypes
import os
import platform
import ssl
from email.message import EmailMessage
from email.utils import make_msgid
from typing import List, Optional, Tuple, Union

# Windows-only dependency for Outlook
if platform.system() == "Windows":
    import win32com.client as win32
else:
    win32 = None

from pylogshield import get_logger
from tenacity import Retrying, stop_after_attempt, wait_fixed

from ._transport import _SMTPTransport
from .utils import (
    FluxMailException,
    EMAIL_REGEX,
    EmailInstance,
    EmailObject,
    str_to_enum,
    validate_email,
)
```

Note: `import smtplib` is removed — it now lives only in `_transport.py`.

**3b — Replace `__slots__`** (remove `"_smtp_conn"`, add six new entries):

```python
    __slots__ = (
        "object_type",
        "host",
        "logger",
        "log_level",
        "message",
        "is_created",
        "subject",
        "recipients",
        "body",
        "plain_body",
        "sender",
        "cc",
        "bcc",
        "reply_to",
        "input_path",
        "html_body",
        "port",
        "username",
        "password",
        "use_tls",
        "use_ssl",
        "ssl_context",
        "timeout",
        "max_retries",
        "retry_delay",
        "in_reply_to",
        "references",
        "priority",
        "_transport",
    )
```

**3c — Replace `__init__` signature** (add five new params after `use_tls`):

```python
    def __init__(
        self,
        object_type: Union[EmailObject, str],
        host: Union[EmailInstance, str],
        logger: Optional[logging.Logger] = None,
        log_level: str = "WARNING",
        port: int = 25,
        username: Optional[str] = None,
        password: Optional[str] = None,
        use_tls: bool = False,
        use_ssl: bool = False,
        ssl_context: Optional[ssl.SSLContext] = None,
        timeout: int = 30,
        max_retries: int = 0,
        retry_delay: float = 1.0,
    ):
```

**3d — Update `__init__` body** — replace everything from `self.object_type = ...` to the end of `__init__`:

```python
        if use_ssl and use_tls:
            raise FluxMailException(
                "use_ssl and use_tls are mutually exclusive — use use_ssl for port 465 "
                "implicit TLS, or use_tls for port 587 STARTTLS.",
                code="invalid_config",
            )

        self.object_type = str_to_enum(EmailObject, object_type)
        self.port = port
        self.username = username
        self.password = password
        self.use_tls = use_tls
        self.use_ssl = use_ssl
        self.ssl_context = ssl_context
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        if isinstance(host, EmailInstance):
            self.host = host
        elif isinstance(host, str):
            if ":" in host:
                relay, domain = host.split(":", 1)
                self.host = EmailInstance(relay=relay.strip(), domain=domain.strip())
            else:
                self.host = EmailInstance(relay=host.strip())
        else:
            raise TypeError(
                f"host must be an EmailInstance or a string, got {type(host).__name__}"
            )

        if logger and not isinstance(logger, logging.Logger):
            raise FluxMailException(
                "logger must be an instance of logging.Logger. "
                "Use get_logger() from pylogshield or Python's standard logging module.",
                code="invalid_config",
            )

        self.logger = logger or get_logger("fluxmail", log_level=log_level)
        self.log_level = log_level
        self.message = None
        self.is_created = False
        self.plain_body = None
        self.in_reply_to = None
        self.references = None
        self.priority = None

        self.logger.debug("Initializing FluxMail instance...")

        if self.is_smtp():
            self.message = EmailMessage()
            self._transport = _SMTPTransport(
                relay=self.host.relay,
                port=self.port,
                use_ssl=use_ssl,
                use_tls=use_tls,
                ssl_context=ssl_context,
                timeout=timeout,
                username=username,
                password=password,
            )
        elif self.is_outlook():
            self._transport = None
            if win32 is None:
                raise FluxMailException(
                    "Outlook is only supported on Windows OS.",
                    code="invalid_config",
                )
            ol_app = win32.Dispatch("outlook.application")
            self.message = ol_app.CreateItem(0)
```

**3e — Add `_handle_message_id()` method** (insert after `is_outlook()`):

```python
    def _handle_message_id(self) -> None:
        if self.is_smtp():
            self.message["Message-ID"] = make_msgid()
```

**3f — Update `create()` call chain** — insert `self._handle_message_id()` between `_validate_parameters()` and `_handle_sender()`:

```python
        self._validate_parameters()
        self._handle_message_id()
        self._handle_sender()
        self._handle_recipient()
        self._handle_cc()
        self._handle_bcc()
        self._handle_reply_to()
        self._handle_threading()
        self._handle_priority()
        self._set_content_type()
        self._attach_files()
        self.is_created = True
        return self
```

**3g — Add error codes to `_validate_parameters()`** — replace the method body:

```python
    def _validate_parameters(self):
        if not self.subject:
            raise FluxMailException("Subject is required.", code="invalid_params")
        if not isinstance(self.recipients, list) or not self.recipients:
            raise FluxMailException("Recipients must be a non-empty list.", code="invalid_params")
        if self.cc and not isinstance(self.cc, list):
            raise FluxMailException("CC must be a list.", code="invalid_params")
        if self.bcc and not isinstance(self.bcc, list):
            raise FluxMailException("BCC must be a list.", code="invalid_params")
        if self.input_path and not isinstance(self.input_path, list):
            raise FluxMailException("Attachments must be a list.", code="invalid_params")
        if self.priority and self.priority not in _PRIORITY_MAP:
            raise FluxMailException(
                f"priority must be one of {list(_PRIORITY_MAP.keys())}, got '{self.priority}'",
                code="invalid_priority",
            )

        if self.is_smtp():
            self.message["Subject"] = self.subject
        elif self.is_outlook():
            self.message.Subject = self.subject
```

**3h — Add error codes to `_handle_sender()`** — replace the two `raise` statements:

```python
            else:
                raise FluxMailException(
                    "sender is required. Pass sender= explicitly, or set username= "
                    "to a valid email address so it can be used as the From address.",
                    code="sender_required",
                )
```

```python
        elif self.is_outlook() and self.sender:
            msg = "Outlook does not support setting the sender address."
            self.logger.error(msg)
            raise FluxMailException(msg, code="outlook_no_sender")
```

**3i — Add error code to `_attach_files()`** — replace the raise:

```python
                if not os.path.isfile(file_path):
                    raise FluxMailException(
                        f"Attachment not found: {file_path}",
                        code="attachment_not_found",
                    )
```

**3j — Add error code to `_read_file()`** — the `from e` is already present; add `code`:

```python
            raise FluxMailException(msg, code="read_error") from e
```

**3k — Add error codes to `display()`** — replace both raises:

```python
        if not self.is_created:
            raise FluxMailException("Call create() before display().", code="not_created")
```

```python
            raise FluxMailException(msg, code="display_failed") from e
```

**3l — Replace `send()`** (full method):

```python
    def send(self, dry_run: bool = False) -> str:
        """Sends or previews the email."""
        if not self.is_created:
            raise FluxMailException("Call create() before send().", code="not_created")
        if dry_run:
            return self.display()
        if self.is_smtp() and not self.host.relay:
            raise FluxMailException("No SMTP relay configured.", code="no_relay")

        try:
            if self.is_smtp():
                if self.max_retries > 0:
                    for attempt in Retrying(
                        stop=stop_after_attempt(self.max_retries + 1),
                        wait=wait_fixed(self.retry_delay),
                        reraise=True,
                    ):
                        with attempt:
                            self._transport.send(self.message)
                else:
                    self._transport.send(self.message)
                return "Email sent successfully via SMTP."
            elif self.is_outlook():
                raise FluxMailException(
                    "Outlook requires user interaction to send emails and cannot "
                    "send programmatically.",
                    code="outlook_no_send",
                )
        except FluxMailException:
            raise
        except Exception as e:
            msg = f"Send failed: {e}"
            self.logger.error(msg)
            raise FluxMailException(msg, code="send_failed") from e
```

**3m — Replace `__enter__` and `__exit__`**:

```python
    def __enter__(self) -> "FluxMail":
        """Open a persistent SMTP connection for reuse across multiple sends."""
        if self._transport is not None:
            self._transport.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        if self._transport is not None:
            self._transport.close()
        return False
```

**3n — Add error codes to `validate_email()` in `src/fluxmail/utils.py`**:

```python
    if not item:
        raise FluxMailException("No email address provided.", code="no_email")
    ...
    if email.startswith(".") or ".@" in email or "@" not in email or "@." in email:
        raise FluxMailException(f"Invalid email '{email}': format issue.", code="invalid_email")

    if not EMAIL_REGEX.match(email):
        raise FluxMailException(
            f"Invalid email '{email}': does not match expected pattern.",
            code="invalid_email",
        )
```

- [ ] **Step 4: Run full suite — all tests must pass**

```
pytest tests/ -v
```
Expected: all existing + new tests pass. Fix any failures before proceeding.

- [ ] **Step 5: Commit**

```
git add src/fluxmail/fluxmail.py src/fluxmail/utils.py tests/test_fluxmail.py
git commit -m "feat: wire _SMTPTransport into FluxMail; add timeout/use_ssl/ssl_context/retry params; Message-ID; error codes throughout"
```

---

### Task 7: `send_async()` on `FluxMail`

**Files:**
- Modify: `src/fluxmail/fluxmail.py`
- Modify: `tests/test_fluxmail.py`

- [ ] **Step 1: Write failing tests** — append to `tests/test_fluxmail.py`:

```python
from unittest.mock import AsyncMock  # add to existing top-level mock imports


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
```

- [ ] **Step 2: Run — expect FAIL**

```
pytest tests/test_fluxmail.py::TestSendAsync -v
```
Expected: `AttributeError: 'FluxMail' object has no attribute 'send_async'`

- [ ] **Step 3: Implement** — add `send_async()` to `FluxMail` in `src/fluxmail/fluxmail.py`, after `send()`:

```python
    async def send_async(self, dry_run: bool = False) -> str:
        """Sends or previews the email asynchronously (SMTP only).

        Note: retry (max_retries) is not supported for async sends.
        """
        if not self.is_created:
            raise FluxMailException(
                "Call create() before send_async().", code="not_created"
            )
        if dry_run:
            return self.display()
        if self.is_smtp() and not self.host.relay:
            raise FluxMailException("No SMTP relay configured.", code="no_relay")

        try:
            if self.is_smtp():
                await self._transport.send_async(self.message)
                return "Email sent successfully via SMTP."
            elif self.is_outlook():
                raise FluxMailException(
                    "Outlook does not support async sending.",
                    code="outlook_no_async",
                )
        except FluxMailException:
            raise
        except Exception as e:
            msg = f"Async send failed: {e}"
            self.logger.error(msg)
            raise FluxMailException(msg, code="send_failed") from e
```

- [ ] **Step 4: Run — expect PASS**

```
pytest tests/test_fluxmail.py::TestSendAsync -v
```

- [ ] **Step 5: Run full suite**

```
pytest tests/ -v
```

- [ ] **Step 6: Commit**

```
git add src/fluxmail/fluxmail.py tests/test_fluxmail.py
git commit -m "feat: add send_async() to FluxMail via _SMTPTransport"
```

---

### Task 8: Retry tests

**Files:**
- Modify: `tests/test_fluxmail.py`

- [ ] **Step 1: Write tests** — append to `tests/test_fluxmail.py`:

```python
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
```

- [ ] **Step 2: Run — expect PASS** (retry is already implemented in `send()` from Task 6)

```
pytest tests/test_fluxmail.py::TestRetry -v
```

- [ ] **Step 3: Run full suite**

```
pytest tests/ -v
```

- [ ] **Step 4: Commit**

```
git add tests/test_fluxmail.py
git commit -m "test: add retry behaviour coverage"
```

---

### Task 9: `EmailTemplate`

**Files:**
- Create: `src/fluxmail/template.py`
- Create: `tests/test_template.py`
- Modify: `src/fluxmail/__init__.py`

- [ ] **Step 1: Write failing tests** — create `tests/test_template.py`:

```python
import pytest
from fluxmail.template import EmailTemplate


class TestEmailTemplate:
    def test_render_substitutes_variable(self):
        tmpl = EmailTemplate("Hello, {{ name }}!")
        assert tmpl.render(name="Alice") == "Hello, Alice!"

    def test_render_multiple_variables(self):
        tmpl = EmailTemplate("Dear {{ first }} {{ last }},")
        assert tmpl.render(first="John", last="Doe") == "Dear John Doe,"

    def test_render_no_variables(self):
        tmpl = EmailTemplate("No placeholders here.")
        assert tmpl.render() == "No placeholders here."

    def test_from_file_reads_template(self, tmp_path):
        f = tmp_path / "tmpl.txt"
        f.write_text("Hi {{ user }}", encoding="utf-8")
        tmpl = EmailTemplate.from_file(str(f))
        assert tmpl.render(user="Bob") == "Hi Bob"

    def test_autoescape_off_by_default(self):
        tmpl = EmailTemplate("<b>{{ value }}</b>")
        result = tmpl.render(value="<script>alert(1)</script>")
        assert "<script>" in result

    def test_autoescape_on_escapes_html(self):
        tmpl = EmailTemplate("<b>{{ value }}</b>", autoescape=True)
        result = tmpl.render(value="<script>alert(1)</script>")
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_from_file_with_autoescape(self, tmp_path):
        f = tmp_path / "tmpl.html"
        f.write_text("{{ content }}", encoding="utf-8")
        tmpl = EmailTemplate.from_file(str(f), autoescape=True)
        result = tmpl.render(content="<b>bold</b>")
        assert "&lt;b&gt;" in result
```

- [ ] **Step 2: Run — expect FAIL**

```
pytest tests/test_template.py -v
```
Expected: `ModuleNotFoundError: No module named 'fluxmail.template'`

- [ ] **Step 3: Create `src/fluxmail/template.py`**

```python
from typing import Any

from jinja2 import BaseLoader, Environment, select_autoescape


class EmailTemplate:
    """Jinja2-based email body renderer."""

    def __init__(self, template: str, autoescape: bool = False) -> None:
        env = Environment(
            loader=BaseLoader(),
            autoescape=select_autoescape(["html", "xml"]) if autoescape else False,
        )
        self._template = env.from_string(template)

    def render(self, **context: Any) -> str:
        """Render the template with the given context variables."""
        return self._template.render(**context)

    @classmethod
    def from_file(cls, path: str, autoescape: bool = False) -> "EmailTemplate":
        """Load a template from a file (UTF-8 encoding)."""
        with open(path, "r", encoding="utf-8") as f:
            return cls(f.read(), autoescape=autoescape)
```

- [ ] **Step 4: Run — expect PASS**

```
pytest tests/test_template.py -v
```

- [ ] **Step 5: Export from `src/fluxmail/__init__.py`**

Add to the existing import and `__all__`:

```python
from .template import EmailTemplate
```

```python
__all__ = [
    "FluxMail",
    "FluxMailException",
    "EmailInstance",
    "EmailObject",
    "EmailTemplate",
    "BulkSender",      # added in Task 10
    "__version__",
]
```

Note: add `"BulkSender"` to `__all__` in Task 10, not here. For now just add `EmailTemplate`.

- [ ] **Step 6: Run full suite**

```
pytest tests/ -v
```

- [ ] **Step 7: Commit**

```
git add src/fluxmail/template.py src/fluxmail/__init__.py tests/test_template.py
git commit -m "feat: add EmailTemplate with Jinja2 rendering"
```

---

### Task 10: `BulkSender`

**Files:**
- Create: `src/fluxmail/bulk.py`
- Create: `tests/test_bulk.py`
- Modify: `src/fluxmail/__init__.py`

- [ ] **Step 1: Write failing tests** — create `tests/test_bulk.py`:

```python
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
```

- [ ] **Step 2: Run — expect FAIL**

```
pytest tests/test_bulk.py -v
```
Expected: `ModuleNotFoundError: No module named 'fluxmail.bulk'`

- [ ] **Step 3: Create `src/fluxmail/bulk.py`**

```python
from typing import Any, Callable, Dict, List, Optional, Tuple

from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn

from .fluxmail import FluxMail, FluxMailException


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
                    except FluxMailException as e:
                        failed += 1
                        errors.append((i, e))
                        if on_error:
                            on_error(i, e)
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
```

- [ ] **Step 4: Run — expect PASS**

```
pytest tests/test_bulk.py -v
```

- [ ] **Step 5: Export `BulkSender` from `src/fluxmail/__init__.py`**

Add after the `EmailTemplate` import:
```python
from .bulk import BulkSender
```

Add `"BulkSender"` to `__all__`.

Full updated `__init__.py`:

```python
from ._version import __version__
from .bulk import BulkSender
from .fluxmail import FluxMail
from .template import EmailTemplate
from .utils import FluxMailException, EmailInstance, EmailObject

__all__ = [
    "FluxMail",
    "FluxMailException",
    "EmailInstance",
    "EmailObject",
    "EmailTemplate",
    "BulkSender",
    "__version__",
]
```

- [ ] **Step 6: Run full suite**

```
pytest tests/ -v
```

- [ ] **Step 7: Commit**

```
git add src/fluxmail/bulk.py src/fluxmail/__init__.py tests/test_bulk.py
git commit -m "feat: add BulkSender with Rich progress bar"
```

---

### Task 11: CLI flags

**Files:**
- Modify: `src/fluxmail/fluxmail_cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing tests** — append to `tests/test_cli.py`:

```python
def test_ssl_flag():
    with patch("fluxmail._transport.smtplib.SMTP_SSL") as mock_ssl:
        mock_ssl.return_value = MagicMock()
        result = runner.invoke(app, BASE + ["--ssl"])
    assert result.exit_code == 0


def test_timeout_flag():
    with mock_smtp():
        result = runner.invoke(app, BASE + ["--timeout", "60"])
    assert result.exit_code == 0


def test_max_retries_flag():
    with mock_smtp():
        result = runner.invoke(app, BASE + ["--max-retries", "2"])
    assert result.exit_code == 0


def test_retry_delay_flag():
    with mock_smtp():
        result = runner.invoke(app, BASE + ["--retry-delay", "0.5"])
    assert result.exit_code == 0


def test_ssl_and_tls_together_exits_2():
    result = runner.invoke(app, BASE + ["--ssl", "--tls"])
    assert result.exit_code == 2
```

Add `from unittest.mock import MagicMock, patch` to `tests/test_cli.py` imports.

- [ ] **Step 2: Run — expect FAIL**

```
pytest tests/test_cli.py::test_ssl_flag tests/test_cli.py::test_timeout_flag -v
```
Expected: `Error: No such option: --ssl`

- [ ] **Step 3: Implement** — update `src/fluxmail/fluxmail_cli.py`

In the `send` function signature, add four new parameters after the existing `tls` param (before the `version` param):

```python
    ssl: Annotated[
        bool,
        typer.Option("--ssl/--no-ssl",
                     help="Use implicit TLS (port 465). Mutually exclusive with --tls."),
    ] = False,
    timeout: Annotated[
        int,
        typer.Option(help="SMTP connection timeout in seconds."),
    ] = 30,
    max_retries: Annotated[
        int,
        typer.Option("--max-retries", help="Number of send retries on failure."),
    ] = 0,
    retry_delay: Annotated[
        float,
        typer.Option("--retry-delay", help="Seconds to wait between retries."),
    ] = 1.0,
```

Update the `FluxMail(...)` constructor call in the same function to pass the new params:

```python
        email = FluxMail(
            object_type=email_obj,
            host=host,
            port=port,
            username=username,
            password=password,
            use_tls=tls,
            use_ssl=ssl,
            timeout=timeout,
            max_retries=max_retries,
            retry_delay=retry_delay,
        )
```

- [ ] **Step 4: Run — expect PASS**

```
pytest tests/test_cli.py -v
```

- [ ] **Step 5: Run full suite**

```
pytest tests/ -v
```

- [ ] **Step 6: Commit**

```
git add src/fluxmail/fluxmail_cli.py tests/test_cli.py
git commit -m "feat: add --ssl, --timeout, --max-retries, --retry-delay CLI flags"
```

---

### Task 12: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update the architecture table** — replace the existing source layout table with:

```markdown
**Source layout** (`src/fluxmail/`):

| File | Role |
|------|------|
| `fluxmail.py` | `FluxMail` class — email creation, send, send_async, retry |
| `_transport.py` | `_SMTPTransport` — all SMTP connection logic (sync + async, SSL variants) |
| `utils.py` | `EmailObject`, `EmailInstance`, `FluxMailException`, `validate_email`, `str_to_enum` |
| `template.py` | `EmailTemplate` — Jinja2 body renderer |
| `bulk.py` | `BulkSender` — batch sender with Rich progress bar |
| `fluxmail_cli.py` | Typer-based CLI; calls `FluxMail` |
| `__init__.py` | Public exports: `FluxMail`, `FluxMailException`, `EmailInstance`, `EmailObject`, `EmailTemplate`, `BulkSender`, `__version__` |
| `__main__.py` | `python -m fluxmail` entry point |
| `testing.py` | `mock_smtp()` context manager for tests (patches `fluxmail._transport.smtplib.SMTP`) |
```

- [ ] **Step 2: Remove the "Planned Features" section** (all four items are now implemented)

- [ ] **Step 3: Add new constructor params to key design decisions**

Append to the key design decisions list:
```markdown
- `use_ssl=True` uses `smtplib.SMTP_SSL` (port 465 implicit TLS). Mutually exclusive with `use_tls=True`.
- `timeout` (default `30`) is passed to every SMTP connection.
- `ssl_context` accepts a custom `ssl.SSLContext` for cert customisation.
- `max_retries` / `retry_delay` configure automatic retry via tenacity. Not applied to `send_async()`.
- `send_async()` uses `aiosmtplib` and accepts the same TLS/timeout params as `send()`.
- `EmailTemplate(template_str)` renders Jinja2 templates; use the result as `body=` in `create()`.
- `BulkSender(mailer).send_batch(messages)` sends a list-of-dicts batch over one connection.
```

- [ ] **Step 4: Commit**

```
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md for new features and architecture"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Task |
|---|---|
| Connection timeout | Task 6 (constructor param), Task 11 (CLI) |
| Implicit TLS (`SMTP_SSL`) | Task 3 (`_make_connection`), Task 6 (FluxMail), Task 11 (CLI) |
| SSL context parameter | Task 3, Task 6 |
| `FluxMailException` error codes | Task 1, Task 6 (codes throughout) |
| Auto `Message-ID` | Task 6 (`_handle_message_id`) |
| `send_async()` | Task 4 (transport), Task 7 (FluxMail) |
| Retry logic | Task 6 (`send()` retry wrapper), Task 8 (tests) |
| `EmailTemplate` | Task 9 |
| `BulkSender` | Task 10 |
| `mock_smtp()` redesign | Task 5 |
| `__enter__`/`__exit__` guard on `_transport is not None` | Task 6 (step 3m) |
| `start_tls=True if use_tls else None` | Task 4 (step 3) |
| `quit()` in try/except inside finally | Task 3 (step 3) |
| `errors` list in `BulkSender` return | Task 10 |
| All `_validate_parameters()` error codes | Task 6 (step 3g) |
| CLI flags | Task 11 |
| CLAUDE.md | Task 12 |

**Placeholder scan:** No TBDs. All code blocks are complete.

**Type consistency:** `_SMTPTransport` constructed in Task 3 and used in Task 6 with the same keyword-only signature. `send_async()` added to transport in Task 4 and called in Task 7 as `self._transport.send_async(self.message)`. `BulkSender.send_batch()` return dict shape defined in Task 10 and tested in Task 10. All consistent.
