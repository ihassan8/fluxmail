# FluxMail — Developer Features Design

**Date:** 2026-05-12
**Status:** Approved for implementation

---

## Overview

Implements eight features that raise FluxMail's value for developers using it in production applications.

1. `FluxMail.from_env()` — factory from environment variables
2. `test_connection()` — SMTP health check with diagnostics
3. `List-Unsubscribe` header — bulk-sender deliverability (Gmail/Yahoo policy)
4. Inline CID images — embedded images for HTML emails
5. Django email backend — drop-in `EMAIL_BACKEND` replacement
6. CSS inlining via `premailer` — automatic inline styles for HTML emails
7. `BulkSender.send_batch_async()` — async batch send over one connection
8. Rate limiting on `send_batch_async()` — `max_per_second` parameter

All new dependencies (`premailer`, `Django`) are added to `requirements.txt` as required deps (consistent with existing project policy).

---

## Dependencies

Add to `requirements.txt`:
```
premailer>=3.10
Django>=3.2
```

---

## Section 1 — Core FluxMail additions

### 1.1 `FluxMail.from_env()`

**File:** `src/fluxmail/fluxmail.py`

Classmethod. Reads the following environment variables and passes them to `FluxMail.__init__`. Missing required variables raise `FluxMailException(code="invalid_config")`.

| Env var | Constructor param | Default | Notes |
|---|---|---|---|
| `FLUXMAIL_TYPE` | `object_type` | `"smtp"` | |
| `FLUXMAIL_HOST` | `host` | — | Required when type is `"smtp"`; omitted for Outlook |
| `FLUXMAIL_PORT` | `port` | `25` | Cast to `int` |
| `FLUXMAIL_USERNAME` | `username` | — | Same var used by CLI |
| `FLUXMAIL_PASSWORD` | `password` | — | Same var used by CLI |
| `FLUXMAIL_TLS` | `use_tls` | `"false"` | Parsed as bool: `"true"` → `True` |
| `FLUXMAIL_SSL` | `use_ssl` | `"false"` | Parsed as bool |
| `FLUXMAIL_TIMEOUT` | `timeout` | `30` | Cast to `int` |
| `FLUXMAIL_MAX_RETRIES` | `max_retries` | `0` | Cast to `int` |
| `FLUXMAIL_RETRY_DELAY` | `retry_delay` | `1.0` | Cast to `float` |

**Outlook special case:** When `FLUXMAIL_TYPE=outlook`, `FLUXMAIL_HOST` is not required. The method passes `host=EmailInstance(relay="")` automatically.

**Bool parsing helper** (private, reusable): `_parse_bool(value: str) -> bool` — returns `True` for `"true"`, `"1"`, `"yes"` (case-insensitive), `False` otherwise.

```python
@classmethod
def from_env(cls) -> "FluxMail":
    object_type = os.environ.get("FLUXMAIL_TYPE", "smtp")
    host_str = os.environ.get("FLUXMAIL_HOST", "")
    if object_type.lower() == "smtp" and not host_str:
        raise FluxMailException(
            "FLUXMAIL_HOST is required when FLUXMAIL_TYPE=smtp",
            code="invalid_config",
        )
    host = host_str if host_str else EmailInstance(relay="")
    return cls(
        object_type=object_type,
        host=host,
        port=int(os.environ.get("FLUXMAIL_PORT", "25")),
        username=os.environ.get("FLUXMAIL_USERNAME"),
        password=os.environ.get("FLUXMAIL_PASSWORD"),
        use_tls=_parse_bool(os.environ.get("FLUXMAIL_TLS", "false")),
        use_ssl=_parse_bool(os.environ.get("FLUXMAIL_SSL", "false")),
        timeout=int(os.environ.get("FLUXMAIL_TIMEOUT", "30")),
        max_retries=int(os.environ.get("FLUXMAIL_MAX_RETRIES", "0")),
        retry_delay=float(os.environ.get("FLUXMAIL_RETRY_DELAY", "1.0")),
    )
```

---

### 1.2 `test_connection()`

**File:** `src/fluxmail/fluxmail.py`

Opens SMTP connection, authenticates, measures round-trip latency, closes. Does not send any email.

```python
def test_connection(self) -> dict:
    # Returns: {"ok": True, "relay": str, "port": int, "latency_ms": int}
    # Raises: FluxMailException(code="connection_failed") on any failure
    #         FluxMailException(code="outlook_no_connect") for Outlook instances
```

**Implementation:** Records `time.monotonic()` before and after `_transport._make_connection()`, then immediately calls `conn.quit()`. Returns the diagnostic dict. Any exception from `_make_connection()` is caught and re-raised as `FluxMailException(code="connection_failed") from e`.

Outlook raises immediately: `FluxMailException("Outlook does not support connection testing.", code="outlook_no_connect")`.

---

### 1.3 `List-Unsubscribe` header

**File:** `src/fluxmail/fluxmail.py`

New parameter on `create()`: `unsubscribe_url: Optional[str] = None`. SMTP only.

When set, adds two headers:
```
List-Unsubscribe: <https://example.com/unsubscribe?token=xyz>
List-Unsubscribe-Post: List-Unsubscribe=One-Click
```

`List-Unsubscribe-Post` enables RFC 8058 one-click unsubscribe, required by Gmail and Yahoo for bulk senders since February 2024.

New `__slots__` entry: `"unsubscribe_url"`

New private method `_handle_unsubscribe()` called from `create()` after `_handle_reply_to()`:
```python
def _handle_unsubscribe(self) -> None:
    if self.unsubscribe_url and self.is_smtp():
        self.message["List-Unsubscribe"] = f"<{self.unsubscribe_url}>"
        self.message["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
```

---

### 1.4 Inline CID images

**File:** `src/fluxmail/fluxmail.py`

New parameter on `create()`: `inline_images: Optional[Dict[str, str]] = None`. Maps `cid_name → file_path`. **SMTP only.**

When set, each file is attached as an inline part with:
- `Content-Disposition: inline`
- `Content-ID: <cid_name>` (angle brackets required per RFC 2392)

HTML body references images as `<img src="cid:logo">`.

**Error handling:**
- Passing `inline_images` on an Outlook instance raises `FluxMailException(code="invalid_params")`.
- A non-existent file path raises `FluxMailException(f"Inline image not found: {path}", code="attachment_not_found")`.

New `__slots__` entry: `"inline_images"`

New private method `_attach_inline_images()` called from `create()` after `_attach_files()`:
```python
def _attach_inline_images(self) -> None:
    if not self.inline_images:
        return
    if self.is_outlook():
        raise FluxMailException(
            "inline_images is not supported for Outlook.", code="invalid_params"
        )
    for cid_name, file_path in self.inline_images.items():
        if not os.path.isfile(file_path):
            raise FluxMailException(
                f"Inline image not found: {file_path}", code="attachment_not_found"
            )
        data, name = self._read_file(file_path)
        mime_type, _ = mimetypes.guess_type(file_path)
        maintype, subtype = (mime_type or "application/octet-stream").split("/", 1)
        self.message.add_attachment(
            data,
            maintype=maintype,
            subtype=subtype,
            filename=name,
            disposition="inline",
            cid=f"<{cid_name}>",
        )
        self.logger.debug("Inline image attached: cid=%s file=%s", cid_name, file_path)
```

---

### 1.5 CSS inlining

**File:** `src/fluxmail/fluxmail.py`

New parameter on `create()`: `inline_css: bool = False`.

When `True` AND `html_body=True`, runs `premailer.transform(body)` before setting the email body. If `html_body=False`, `inline_css=True` is silently ignored (inlining CSS into plain text is a no-op).

If `premailer.transform()` raises, the exception is caught and re-raised as `FluxMailException(f"CSS inlining failed: {e}", code="css_inline_failed") from e`.

New `__slots__` entry: `"inline_css"`

`_set_content_type()` updated:
```python
def _set_content_type(self):
    body = self.body
    if self.is_smtp() and self.html_body and self.inline_css:
        import premailer
        try:
            body = premailer.transform(body)
        except Exception as e:
            raise FluxMailException(
                f"CSS inlining failed: {e}", code="css_inline_failed"
            ) from e
    # ... rest of existing logic using `body` instead of `self.body`
```

---

### 1.6 `create()` signature additions

Three new keyword params appended to `create()`:

```python
def create(
    self,
    ...                                                      # existing params unchanged
    unsubscribe_url: Optional[str] = None,
    inline_images: Optional[Dict[str, str]] = None,
    inline_css: bool = False,
) -> "FluxMail":
```

These three must be assigned in the `create()` body:
```python
self.unsubscribe_url = unsubscribe_url
self.inline_images = inline_images
self.inline_css = inline_css
```

`_validate_parameters()` gains one new check (after the attachments check):
```python
if self.inline_images is not None and not isinstance(self.inline_images, dict):
    raise FluxMailException(
        "inline_images must be a dict mapping cid_name to file_path.",
        code="invalid_params",
    )
```

---

### 1.7 `create()` call chain update

Updated call order in `create()`:
```python
self._validate_parameters()   # now also validates inline_images type
self._handle_message_id()
self._handle_sender()
self._handle_recipient()
self._handle_cc()
self._handle_bcc()
self._handle_reply_to()
self._handle_unsubscribe()    # NEW
self._handle_threading()
self._handle_priority()
self._set_content_type()      # updated for inline_css
self._attach_files()
self._attach_inline_images()  # NEW
self.is_created = True
```

---

## Section 2 — BulkSender enhancements

### 2.1 `_SMTPTransport.async_connection()`

**File:** `src/fluxmail/_transport.py`

New async context manager that yields an authenticated `aiosmtplib.SMTP` instance for reuse across multiple sends.

**Parameter mapping (mirrors `send_async()`):**
- `use_ssl=True` → `aiosmtplib.SMTP(use_tls=True)` (implicit TLS, port 465)
- `use_tls=True` → `aiosmtplib.SMTP(use_tls=False)` then `await smtp.starttls(context=...)`
- `ssl_context` → passed to constructor as `tls_context` when `use_ssl`, or to `starttls()` when `use_tls`

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def async_connection(self):
    tls_mode = "implicit-TLS" if self._use_ssl else ("STARTTLS" if self._use_tls else "plain")
    self._logger.debug(
        "Opening persistent async SMTP connection to %s:%d (%s)",
        self._relay, self._port, tls_mode,
    )
    smtp = aiosmtplib.SMTP(
        hostname=self._relay,
        port=self._port,
        use_tls=self._use_ssl,
        tls_context=self._ssl_context if self._use_ssl else None,
        timeout=self._timeout,
    )
    async with smtp:
        if self._use_tls:
            await smtp.starttls(context=self._ssl_context)
            self._logger.debug("Async STARTTLS negotiated with %s", self._relay)
        if self._username and self._password:
            await smtp.login(self._username, self._password)
            self._logger.debug("Async authenticated as %s", self._username)
        yield smtp
    self._logger.debug("Persistent async SMTP connection closed: %s:%d", self._relay, self._port)
```

---

### 2.2 `BulkSender.send_batch_async()`

**File:** `src/fluxmail/bulk.py`

New async method. Opens one persistent async SMTP connection, loops through messages, sends each via `await smtp.send_message()`. Same error-isolation contract as `send_batch()` — catches `Exception` broadly, wraps non-`FluxMailException` in `FluxMailException(code="send_failed")`.

```python
async def send_batch_async(
    self,
    messages: List[Dict[str, Any]],
    *,
    on_success: Optional[Callable[[int, str], None]] = None,
    on_error: Optional[Callable[[int, FluxMailException], None]] = None,
    progress: bool = True,
    max_per_second: float = 0,
) -> Dict[str, Any]:
```

**Rate limiting:** After each successful send, if `max_per_second > 0`, `await asyncio.sleep(1 / max_per_second)`. Validated: negative `max_per_second` raises `FluxMailException(code="invalid_config")`.

**Progress bar:** Same Rich `Progress` components as `send_batch()`. Rich's `Progress` context manager is safe to use inside an async function (it only writes to stdout, no blocking I/O).

**Return shape:** Identical to `send_batch()`:
```python
{"sent": int, "failed": int, "total": int, "errors": List[Tuple[int, FluxMailException]]}
```

**Imports to add:** `import asyncio` at top of `bulk.py`.

---

## Section 3 — Django email backend

### 3.1 File layout

```
src/fluxmail/backends/__init__.py   # empty
src/fluxmail/backends/django.py     # FluxMailBackend
```

Usage:
```python
# settings.py
EMAIL_BACKEND = "fluxmail.backends.django.FluxMailBackend"
EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_HOST_USER = "me@gmail.com"
EMAIL_HOST_PASSWORD = "secret"
EMAIL_USE_TLS = True
EMAIL_TIMEOUT = 30
```

---

### 3.2 Settings mapping

| Django setting | FluxMail param |
|---|---|
| `EMAIL_HOST` | `host` |
| `EMAIL_PORT` | `port` (default `25`) |
| `EMAIL_HOST_USER` | `username` |
| `EMAIL_HOST_PASSWORD` | `password` |
| `EMAIL_USE_TLS` | `use_tls` |
| `EMAIL_USE_SSL` | `use_ssl` |
| `EMAIL_TIMEOUT` | `timeout` (default `30`) |

FluxMail-specific settings (optional, defaults shown):
- `EMAIL_FLUXMAIL_MAX_RETRIES` → `max_retries` (default `0`)
- `EMAIL_FLUXMAIL_RETRY_DELAY` → `retry_delay` (default `1.0`)

---

### 3.3 Email construction strategy

The backend does **not** go through `FluxMail.create()` for message construction. Django's `EmailMessage.message()` returns a stdlib `email.message.Message` — the backend calls this directly and passes the result to `self._mailer._transport.send(msg)`. This avoids re-implementing Django's MIME logic (attachments as `(filename, bytes, mimetype)` tuples, `EmailMultiAlternatives` HTML alternatives, etc.).

```python
def send_messages(self, email_messages):
    sent = 0
    for msg in email_messages:
        try:
            self._mailer._transport.send(msg.message())
            sent += 1
        except Exception:
            if not self.fail_silently:
                raise
    return sent
```

---

### 3.4 Connection lifecycle

`open()` — creates a `FluxMail` instance from Django settings and opens a persistent SMTP connection. Returns `True` if a new connection was opened, `False` if already open (Django's expected convention for connection reuse tracking).

`close()` — closes the persistent connection. No-op if already closed.

When used outside a `with` block, `send_messages()` opens and closes a transient connection per call.

`fail_silently` — honours Django's `BaseEmailBackend` convention: when `True`, all exceptions in `send_messages()` are swallowed and 0 is returned.

---

## New test files

| File | Covers |
|---|---|
| `tests/test_backend_django.py` | `FluxMailBackend`: settings mapping, `open()`/`close()`, `send_messages()`, `fail_silently`, HTML alt |

## Modified test files

| File | New test classes |
|---|---|
| `tests/test_fluxmail.py` | `TestFromEnv`, `TestTestConnection`, `TestUnsubscribeHeader`, `TestInlineImages`, `TestCSSInlining` |
| `tests/test_bulk.py` | `TestSendBatchAsync` |
| `tests/test_transport.py` | `TestAsyncConnection` |

## CLAUDE.md updates

- Architecture table: add `backends/__init__.py`, `backends/django.py`
- Key design decisions: from_env env vars, test_connection dict, List-Unsubscribe, CID images, CSS inlining, async bulk, Django backend pattern
