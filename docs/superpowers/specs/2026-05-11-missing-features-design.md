# FluxMail — Missing Features Design

**Date:** 2026-05-11
**Status:** Approved for implementation

---

## Overview

Implements nine features identified in the post-review backlog:

1. Connection timeout
2. Implicit TLS (`SMTP_SSL`, port 465)
3. SSL context parameter
4. `FluxMailException` structured error codes
5. Auto `Message-ID` generation
6. `send_async()` via aiosmtplib
7. Retry logic via tenacity
8. `EmailTemplate` via Jinja2
9. `BulkSender` with Rich progress bar

All new runtime dependencies (`aiosmtplib`, `tenacity`, `jinja2`) are added to `requirements.txt` as required dependencies. The public API is fully backward compatible.

---

## Architecture

### New files

| File | Purpose |
|---|---|
| `src/fluxmail/_transport.py` | `_SMTPTransport` — owns all SMTP connection logic |
| `src/fluxmail/template.py` | `EmailTemplate` — Jinja2 body renderer |
| `src/fluxmail/bulk.py` | `BulkSender` — batch sender with progress bar |

### Modified files

| File | Change summary |
|---|---|
| `src/fluxmail/fluxmail.py` | New constructor params, `_transport` slot, `send_async()`, `_handle_message_id()`, retry in `send()` |
| `src/fluxmail/utils.py` | `FluxMailException(message, code=None)` |
| `src/fluxmail/__init__.py` | Export `EmailTemplate`, `BulkSender` |
| `src/fluxmail/fluxmail_cli.py` | `--ssl`, `--timeout`, `--max-retries`, `--retry-delay` flags |
| `src/fluxmail/testing.py` | Update patch path to `fluxmail._transport.smtplib.SMTP` |
| `requirements.txt` | Add `aiosmtplib>=3.0`, `tenacity>=8.0`, `jinja2>=3.1` |
| `requirements-dev.txt` | Add `pytest-asyncio>=0.23` |
| `pyproject.toml` | Add `asyncio_mode = "auto"` to `[tool.pytest.ini_options]` |
| `CLAUDE.md` | Update architecture table |

---

## `_SMTPTransport` (private)

**File:** `src/fluxmail/_transport.py`

Central connection manager used by both `send()` and `send_async()`. Eliminates the SSL/TLS/timeout branching that would otherwise be duplicated across two code paths.

```
_make_connection() → smtplib.SMTP or SMTP_SSL, applies starttls + login, returns raw connection
send(message)      → persistent conn if open, else transient via try/finally conn.quit()
send_async(message)→ aiosmtplib.send() with matching kwargs
open()             → stores persistent connection (called by FluxMail.__enter__)
close()            → calls quit() + clears conn (called by FluxMail.__exit__)
```

### `_make_connection()` detail

```python
def _make_connection(self) -> smtplib.SMTP:
    if self._use_ssl:
        conn = smtplib.SMTP_SSL(relay, port, context=ssl_context, timeout=timeout)
    else:
        conn = smtplib.SMTP(relay, port, timeout=timeout)
        if self._use_tls:
            conn.starttls(context=ssl_context)
    if username and password:
        conn.login(username, password)
    return conn
```

### `send()` — transient path uses explicit `quit()` (not context manager `__exit__`)

`smtplib.SMTP.__exit__` calls `close()`, skipping the `QUIT` handshake. To send `QUIT` consistently on transient sends. `quit()` is wrapped in its own `try/except` so a dropped connection after send does not mask the original send exception:

```python
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
```

### `send_async()` — aiosmtplib parameter mapping

| FluxMail param | aiosmtplib param | Notes |
|---|---|---|
| `use_ssl=True` | `use_tls=True` | Implicit TLS (port 465) |
| `use_tls=True` | `start_tls=True` | STARTTLS (port 587) |
| `use_tls=False` | `start_tls=None` | No STARTTLS — must be `None`, not `False`, to avoid disabling auto-detect |
| `ssl_context` | `tls_context=ssl_context` | |
| `timeout` | `timeout=timeout` | |

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

---

## `FluxMail` changes

### New `__slots__` entries

```
"use_ssl"       - bool
"ssl_context"   - Optional[ssl.SSLContext]
"timeout"       - int
"max_retries"   - int
"retry_delay"   - float
"_transport"    - Optional[_SMTPTransport]
```

`_smtp_conn` slot is **removed** — persistent connection state moves into `_SMTPTransport._conn`.

### New constructor parameters

```python
use_ssl: bool = False,
ssl_context: Optional[ssl.SSLContext] = None,
timeout: int = 30,
max_retries: int = 0,
retry_delay: float = 1.0,
```

Mutual exclusion guard (raised before transport is constructed):

```python
if use_ssl and use_tls:
    raise FluxMailException(
        "use_ssl and use_tls are mutually exclusive — use use_ssl for port 465 "
        "implicit TLS, or use_tls for port 587 STARTTLS.",
        code="invalid_config",
    )
```

Transport initialisation — SMTP only:

```python
self._transport = (
    _SMTPTransport(relay=..., port=..., use_ssl=..., use_tls=...,
                   ssl_context=..., timeout=..., username=..., password=...)
    if self.is_smtp() else None
)
```

### `_handle_message_id()`

New private method called from `create()` between `_validate_parameters()` and `_handle_sender()`:

```python
def _handle_message_id(self) -> None:
    if self.is_smtp():
        self.message["Message-ID"] = make_msgid()
```

Import: `from email.utils import make_msgid`

### `send()` — retry wrapper

```python
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
```

Imports: `from tenacity import Retrying, stop_after_attempt, wait_fixed`

### `send_async()` — new method

Same guards as `send()` (not_created, no_relay). Delegates to `_transport.send_async()`. Outlook raises with `code="outlook_no_async"`. Retry is **not** supported in `send_async()` (documented limitation).

### `__enter__` / `__exit__`

Delegate to `_transport.open()` / `_transport.close()`. Guard on `_transport is not None` (the Outlook invariant — `_transport` is always `None` for Outlook):

```python
def __enter__(self):
    if self._transport is not None:
        self._transport.open()
    return self

def __exit__(self, exc_type, exc_val, exc_tb):
    if self._transport is not None:
        self._transport.close()
    return False
```

### Error codes added throughout

| Location | Code |
|---|---|
| `__init__` use_ssl+use_tls | `"invalid_config"` |
| `send()` / `send_async()` not created | `"not_created"` |
| `send()` / `send_async()` no relay | `"no_relay"` |
| `send()` / `send_async()` SMTP failure | `"send_failed"` |
| `send()` Outlook no-send | `"outlook_no_send"` |
| `send_async()` Outlook no-async | `"outlook_no_async"` |
| `display()` not created | `"not_created"` |
| `display()` failure | `"display_failed"` |
| `_handle_sender()` no sender | `"sender_required"` |
| `_handle_sender()` Outlook sender | `"outlook_no_sender"` |
| `_validate_parameters()` empty subject | `"invalid_params"` |
| `_validate_parameters()` non-list / empty recipients | `"invalid_params"` |
| `_validate_parameters()` non-list cc | `"invalid_params"` |
| `_validate_parameters()` non-list bcc | `"invalid_params"` |
| `_validate_parameters()` non-list attachments | `"invalid_params"` |
| `_validate_parameters()` bad priority | `"invalid_priority"` |
| `_attach_files()` file not found | `"attachment_not_found"` |
| `_read_file()` read error | `"read_error"` |
| `validate_email()` invalid format | `"invalid_email"` |
| `validate_email()` empty input | `"no_email"` |

---

## `FluxMailException` changes

**File:** `src/fluxmail/utils.py`

```python
class FluxMailException(Exception):
    def __init__(self, message: str, code: Optional[str] = None) -> None:
        super().__init__(message)
        self.code = code
```

Fully backward compatible — `FluxMailException("msg")` continues to work; `exc.code` is `None` when no code is passed.

---

## `EmailTemplate`

**File:** `src/fluxmail/template.py`

```python
class EmailTemplate:
    def __init__(self, template: str, autoescape: bool = False) -> None: ...
    def render(self, **context: Any) -> str: ...
    @classmethod
    def from_file(cls, path: str, autoescape: bool = False) -> "EmailTemplate": ...
```

- `autoescape=False` default — plain-text templates are common; HTML callers opt-in explicitly
- `from_file` reads with `encoding="utf-8"`
- Exported from `fluxmail.__init__`

---

## `BulkSender`

**File:** `src/fluxmail/bulk.py`

```python
class BulkSender:
    def __init__(self, mailer: FluxMail) -> None: ...

    def send_batch(
        self,
        messages: List[Dict[str, Any]],
        *,
        on_success: Optional[Callable[[int, str], None]] = None,
        on_error: Optional[Callable[[int, FluxMailException], None]] = None,
        progress: bool = True,
    ) -> Dict[str, Any]: ...
```

### Return value

```python
{
    "sent":   int,
    "failed": int,
    "total":  int,
    "errors": List[Tuple[int, FluxMailException]],   # (index, exception) for each failure
}
```

`errors` list is always present (empty when all succeed), so callers can inspect failures without providing `on_error`.

### Connection reuse

Uses `with self._mailer:` — opens one persistent SMTP connection for the entire batch, which calls `_transport.open()` / `_transport.close()`.

### Progress bar

`rich.Progress` with `SpinnerColumn`, `BarColumn`, `TaskProgressColumn`. Suppressed with `progress=False`. `rich` is available via the existing `typer[all]` dependency.

---

## CLI additions

**File:** `src/fluxmail/fluxmail_cli.py`

New flags added to the `send` command:

| Flag | Type | Default | Passed to |
|---|---|---|---|
| `--ssl/--no-ssl` | bool | False | `FluxMail(use_ssl=...)` |
| `--timeout` | int | 30 | `FluxMail(timeout=...)` |
| `--max-retries` | int | 0 | `FluxMail(max_retries=...)` |
| `--retry-delay` | float | 1.0 | `FluxMail(retry_delay=...)` |

`ssl_context` is not exposed via CLI (requires a Python object).

---

## `testing.py` — `mock_smtp()` redesign

Two changes are required, not just a path update.

### Why the behaviour must change

The old `send()` used `with smtplib.SMTP(...) as smtp:` — a context manager — so the relevant mock surface was `mock_cls.return_value.__enter__.return_value`. The new `_transport.send()` calls `conn = self._make_connection()` without a context manager, so the relevant surface is `mock_cls.return_value` (the raw constructor return value).

Tests that do `smtp.send_message.assert_called_once()` would silently pass with 0 calls if `mock_smtp()` still yields the `__enter__` result.

### New `mock_smtp()` implementation

```python
@contextmanager
def mock_smtp():
    mock_instance = MagicMock()
    mock_cls = MagicMock(return_value=mock_instance)

    with patch("fluxmail._transport.smtplib.SMTP", mock_cls):
        yield mock_instance
```

Changes from the old version:
1. Patch path: `fluxmail.fluxmail.smtplib.SMTP` → `fluxmail._transport.smtplib.SMTP`
2. Yields `mock_cls.return_value` (the raw construction result) instead of `mock_cls.return_value.__enter__.return_value`
3. `__enter__`/`__exit__` setup removed — no longer needed

### Manual patches in `TestContextManager`

The two `TestContextManager` tests that call `patch("fluxmail.fluxmail.smtplib.SMTP", ...)` directly also need the path updated to `"fluxmail._transport.smtplib.SMTP"`. Their assertion on `mock_conn.send_message.call_count` remains correct because `_transport.send()` calls `self._conn.send_message()` on the persistent connection object, which is `mock_conn`.

All `TestSend` tests use `mock_smtp()` and will automatically get the correct mock surface once `mock_smtp()` is updated.

---

## Tests

### New test files

| File | Covers |
|---|---|
| `tests/test_transport.py` | `_SMTPTransport`: SMTP vs SMTP_SSL, starttls, login, transient send (QUIT called), persistent open/close, async send |
| `tests/test_template.py` | `EmailTemplate`: render with vars, from_file, autoescape on/off |
| `tests/test_bulk.py` | `BulkSender`: all succeed, partial failure, errors list populated, on_success/on_error callbacks, progress=False |

### Additions to existing test files

**`test_fluxmail.py`:**
- `use_ssl=True` uses `SMTP_SSL` (transport path)
- `use_ssl=True, use_tls=True` raises `FluxMailException(code="invalid_config")`
- `timeout=60` stored on instance
- `Message-ID` header present after `create()`
- `send_async()` calls `_transport.send_async()` (mocked)
- `send_async()` before `create()` raises
- `max_retries=2` retries on failure, succeeds on third attempt

**`test_utils.py`:**
- `FluxMailException("msg", code="x").code == "x"`
- `FluxMailException("msg").code is None`

---

## Known limitations

- `send_async()` does not support retry (`max_retries` is ignored for async sends)
- `ssl_context` is not configurable via the CLI
- `BulkSender` does not support async batch sending

---

## Dependencies

### `requirements.txt` additions
```
aiosmtplib>=3.0
tenacity>=8.0
jinja2>=3.1
```

### `requirements-dev.txt` additions
```
pytest-asyncio>=0.23
```

### `pyproject.toml`
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```
