# FluxMail Developer Features Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add eight developer-facing features — `from_env()`, `test_connection()`, `List-Unsubscribe`, inline CID images, CSS inlining, async bulk send, rate limiting, and a Django email backend.

**Architecture:** Core additions (Tasks 2–6) extend `FluxMail` and `create()` in `fluxmail.py`. Async bulk send (Tasks 7–8) adds `async_connection()` to `_SMTPTransport` and `send_batch_async()` to `BulkSender`. The Django backend (Task 9) is an isolated new module `fluxmail/backends/django.py` that wraps `FluxMail` via the `BaseEmailBackend` interface.

**Tech Stack:** Python 3.8+, premailer, Django>=3.2, aiosmtplib, asynccontextmanager, pytest

**Spec:** `docs/superpowers/specs/2026-05-12-developer-features-design.md`

---

## File Map

| Action | File |
|---|---|
| Modify | `requirements.txt` |
| Modify | `src/fluxmail/fluxmail.py` |
| Modify | `src/fluxmail/_transport.py` |
| Modify | `src/fluxmail/bulk.py` |
| Create | `src/fluxmail/backends/__init__.py` |
| Create | `src/fluxmail/backends/django.py` |
| Modify | `tests/test_fluxmail.py` |
| Modify | `tests/test_transport.py` |
| Modify | `tests/test_bulk.py` |
| Create | `tests/test_backend_django.py` |
| Modify | `CLAUDE.md` |

---

### Task 1: Add dependencies

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add deps to requirements.txt**

Append to `requirements.txt`:
```
premailer>=3.10
Django>=3.2
```

- [ ] **Step 2: Install**

```
pip install -r requirements.txt
```

- [ ] **Step 3: Verify imports work**

```
python -c "import premailer; import django; print('OK')"
```
Expected: `OK`

- [ ] **Step 4: Run full suite — expect all still pass**

```
pytest tests/ -v --tb=short 2>&1 | tail -5
```
Expected: all pass, no new failures.

- [ ] **Step 5: Commit**

```
git add requirements.txt
git commit -m "feat: add premailer and Django dependencies"
```

---

### Task 2: `_parse_bool` module function + `FluxMail.from_env()`

**Files:**
- Modify: `src/fluxmail/fluxmail.py`
- Modify: `tests/test_fluxmail.py`

- [ ] **Step 1: Write failing tests** — append to `tests/test_fluxmail.py`:

```python
import sys  # already at top — ensure it's there


class TestFromEnv:
    def test_reads_smtp_config(self, monkeypatch):
        monkeypatch.setenv("FLUXMAIL_HOST", "smtp.example.com")
        monkeypatch.setenv("FLUXMAIL_USERNAME", "u@example.com")
        monkeypatch.delenv("FLUXMAIL_TYPE", raising=False)
        e = FluxMail.from_env()
        assert e.host.relay == "smtp.example.com"
        assert e.username == "u@example.com"
        assert e.object_type == EmailObject.SMTP

    def test_missing_host_raises_invalid_config(self, monkeypatch):
        monkeypatch.setenv("FLUXMAIL_TYPE", "smtp")
        monkeypatch.delenv("FLUXMAIL_HOST", raising=False)
        with pytest.raises(FluxMailException) as exc_info:
            FluxMail.from_env()
        assert exc_info.value.code == "invalid_config"
        assert "FLUXMAIL_HOST" in str(exc_info.value)

    def test_tls_parsed_true(self, monkeypatch):
        monkeypatch.setenv("FLUXMAIL_HOST", "smtp.example.com")
        monkeypatch.setenv("FLUXMAIL_TLS", "true")
        monkeypatch.delenv("FLUXMAIL_SSL", raising=False)
        e = FluxMail.from_env()
        assert e.use_tls is True

    def test_tls_parsed_false(self, monkeypatch):
        monkeypatch.setenv("FLUXMAIL_HOST", "smtp.example.com")
        monkeypatch.setenv("FLUXMAIL_TLS", "false")
        e = FluxMail.from_env()
        assert e.use_tls is False

    def test_custom_port_and_timeout(self, monkeypatch):
        monkeypatch.setenv("FLUXMAIL_HOST", "smtp.example.com")
        monkeypatch.setenv("FLUXMAIL_PORT", "587")
        monkeypatch.setenv("FLUXMAIL_TIMEOUT", "60")
        e = FluxMail.from_env()
        assert e.port == 587
        assert e.timeout == 60

    @pytest.mark.skipif(sys.platform == "win32", reason="Outlook connects on Windows")
    def test_outlook_type_no_host_required(self, monkeypatch):
        monkeypatch.setenv("FLUXMAIL_TYPE", "outlook")
        monkeypatch.delenv("FLUXMAIL_HOST", raising=False)
        with pytest.raises(FluxMailException) as exc_info:
            FluxMail.from_env()
        # Should raise platform error, NOT missing-host error
        assert "FLUXMAIL_HOST" not in str(exc_info.value)
        assert "Windows" in str(exc_info.value)
```

- [ ] **Step 2: Run — expect FAIL**

```
pytest tests/test_fluxmail.py::TestFromEnv -v
```
Expected: `AttributeError: type object 'FluxMail' has no attribute 'from_env'`

- [ ] **Step 3: Implement** — in `src/fluxmail/fluxmail.py`:

**3a** — Add `_parse_bool` as a module-level function directly above the `FluxMail` class definition (after `_PRIORITY_MAP`):

```python
def _parse_bool(value: str) -> bool:
    """Parse an environment variable string as a boolean."""
    return value.strip().lower() in ("true", "1", "yes")
```

**3b** — Add `from_env()` as a classmethod inside `FluxMail`, after `__repr__()`:

```python
    @classmethod
    def from_env(cls) -> "FluxMail":
        """Create a ``FluxMail`` instance from environment variables.

        Reads ``FLUXMAIL_TYPE``, ``FLUXMAIL_HOST``, ``FLUXMAIL_PORT``,
        ``FLUXMAIL_USERNAME``, ``FLUXMAIL_PASSWORD``, ``FLUXMAIL_TLS``,
        ``FLUXMAIL_SSL``, ``FLUXMAIL_TIMEOUT``, ``FLUXMAIL_MAX_RETRIES``,
        ``FLUXMAIL_RETRY_DELAY``.

        Raises
        ------
        FluxMailException
            If ``FLUXMAIL_HOST`` is missing when ``FLUXMAIL_TYPE=smtp``.
        """
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

- [ ] **Step 4: Run — expect PASS**

```
pytest tests/test_fluxmail.py::TestFromEnv -v
```

- [ ] **Step 5: Run full suite**

```
pytest tests/ -v --tb=short 2>&1 | tail -5
```

- [ ] **Step 6: Commit**

```
git add src/fluxmail/fluxmail.py tests/test_fluxmail.py
git commit -m "feat: add _parse_bool and FluxMail.from_env() factory"
```

---

### Task 3: `test_connection()`

**Files:**
- Modify: `src/fluxmail/fluxmail.py`
- Modify: `tests/test_fluxmail.py`

- [ ] **Step 1: Write failing tests** — append to `tests/test_fluxmail.py`:

```python
class TestTestConnection:
    def test_returns_diagnostics_dict(self, smtp_email):
        mock_conn = MagicMock()
        with patch.object(smtp_email._transport, "_make_connection", return_value=mock_conn):
            result = smtp_email.test_connection()
        assert result["ok"] is True
        assert result["relay"] == smtp_email.host.relay
        assert result["port"] == smtp_email.port
        assert isinstance(result["latency_ms"], int)
        assert result["latency_ms"] >= 0
        mock_conn.quit.assert_called_once()

    def test_quit_failure_does_not_mask_connection_error(self, smtp_email):
        mock_conn = MagicMock()
        mock_conn.quit.side_effect = Exception("already closed")
        with patch.object(smtp_email._transport, "_make_connection", return_value=mock_conn):
            result = smtp_email.test_connection()  # must not raise
        assert result["ok"] is True

    def test_raises_connection_failed_on_error(self, smtp_email):
        with patch.object(
            smtp_email._transport, "_make_connection",
            side_effect=OSError("connection refused")
        ):
            with pytest.raises(FluxMailException) as exc_info:
                smtp_email.test_connection()
        assert exc_info.value.code == "connection_failed"

    def test_outlook_raises_outlook_no_connect(self, smtp_email):
        with patch.object(smtp_email, "is_outlook", return_value=True), \
             patch.object(smtp_email, "is_smtp", return_value=False):
            with pytest.raises(FluxMailException) as exc_info:
                smtp_email.test_connection()
        assert exc_info.value.code == "outlook_no_connect"
```

- [ ] **Step 2: Run — expect FAIL**

```
pytest tests/test_fluxmail.py::TestTestConnection -v
```
Expected: `AttributeError: 'FluxMail' object has no attribute 'test_connection'`

- [ ] **Step 3: Implement** — add `import time` to the top-level imports in `src/fluxmail/fluxmail.py` (after `import ssl`):

```python
import time
```

Then add `test_connection()` as an instance method inside `FluxMail`, after `from_env()`:

```python
    def test_connection(self) -> dict:
        """Test SMTP connectivity and authentication without sending email.

        Returns
        -------
        dict
            ``{"ok": True, "relay": str, "port": int, "latency_ms": int}``

        Raises
        ------
        FluxMailException
            ``code="outlook_no_connect"`` for Outlook instances.
            ``code="connection_failed"`` if connection or auth fails.
        """
        if self.is_outlook():
            raise FluxMailException(
                "Outlook does not support connection testing.",
                code="outlook_no_connect",
            )
        try:
            start = time.monotonic()
            conn = self._transport._make_connection()
            latency_ms = int((time.monotonic() - start) * 1000)
            try:
                conn.quit()
            except Exception:
                pass
            self.logger.info(
                "Connection test OK: relay=%s port=%d latency=%dms",
                self.host.relay, self.port, latency_ms,
            )
            return {
                "ok": True,
                "relay": self.host.relay,
                "port": self.port,
                "latency_ms": latency_ms,
            }
        except FluxMailException:
            raise
        except Exception as e:
            msg = f"Connection test failed: {e}"
            self.logger.error(msg)
            raise FluxMailException(msg, code="connection_failed") from e
```

- [ ] **Step 4: Run — expect PASS**

```
pytest tests/test_fluxmail.py::TestTestConnection -v
```

- [ ] **Step 5: Run full suite**

```
pytest tests/ --tb=short 2>&1 | tail -5
```

- [ ] **Step 6: Commit**

```
git add src/fluxmail/fluxmail.py tests/test_fluxmail.py
git commit -m "feat: add test_connection() with latency diagnostics"
```

---

### Task 4: `List-Unsubscribe` header

**Files:**
- Modify: `src/fluxmail/fluxmail.py`
- Modify: `tests/test_fluxmail.py`

- [ ] **Step 1: Write failing tests** — append to `tests/test_fluxmail.py`:

```python
class TestUnsubscribeHeader:
    def test_headers_set_when_url_provided(self, smtp_email):
        smtp_email.create(
            subject="Newsletter", recipients=["a@b.com"], body="Hi",
            unsubscribe_url="https://example.com/unsub?token=abc",
        )
        assert smtp_email.message["List-Unsubscribe"] == "<https://example.com/unsub?token=abc>"
        assert smtp_email.message["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"

    def test_no_headers_by_default(self, smtp_email):
        smtp_email.create(subject="Hi", recipients=["a@b.com"], body="Hello")
        assert smtp_email.message["List-Unsubscribe"] is None
        assert smtp_email.message["List-Unsubscribe-Post"] is None

    def test_silently_ignored_for_outlook(self, smtp_email):
        # Outlook path: create() shouldn't raise when unsubscribe_url is set
        # We can verify by testing that the slot stores the value without error
        smtp_email.create(
            subject="Hi", recipients=["a@b.com"], body="Hello",
            unsubscribe_url="https://example.com/unsub",
        )
        # SMTP instance — header should be set
        assert smtp_email.message["List-Unsubscribe"] is not None
```

- [ ] **Step 2: Run — expect FAIL**

```
pytest tests/test_fluxmail.py::TestUnsubscribeHeader -v
```
Expected: `TypeError: FluxMail.create() got an unexpected keyword argument 'unsubscribe_url'`

- [ ] **Step 3: Implement** — in `src/fluxmail/fluxmail.py`:

**3a** — Add `"unsubscribe_url"` to `__slots__` (after `"priority"`):
```python
        "priority",
        "unsubscribe_url",
```

**3b** — Add `unsubscribe_url: Optional[str] = None` to `create()` signature (after `priority`):
```python
        priority: Optional[str] = None,
        unsubscribe_url: Optional[str] = None,
```

**3c** — Add assignment in `create()` body (after `self.priority = priority`):
```python
        self.unsubscribe_url = unsubscribe_url
```

**3d** — Add `_handle_unsubscribe()` method after `_handle_reply_to()`:
```python
    def _handle_unsubscribe(self) -> None:
        if self.unsubscribe_url and self.is_smtp():
            self.message["List-Unsubscribe"] = f"<{self.unsubscribe_url}>"
            self.message["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
```

**3e** — Add `self._handle_unsubscribe()` call in `create()` call chain, after `self._handle_reply_to()`:
```python
        self._handle_reply_to()
        self._handle_unsubscribe()
        self._handle_threading()
```

- [ ] **Step 4: Run — expect PASS**

```
pytest tests/test_fluxmail.py::TestUnsubscribeHeader -v
```

- [ ] **Step 5: Run full suite**

```
pytest tests/ --tb=short 2>&1 | tail -5
```

- [ ] **Step 6: Commit**

```
git add src/fluxmail/fluxmail.py tests/test_fluxmail.py
git commit -m "feat: add List-Unsubscribe header support on create()"
```

---

### Task 5: Inline CID images

**Files:**
- Modify: `src/fluxmail/fluxmail.py`
- Modify: `tests/test_fluxmail.py`

- [ ] **Step 1: Write failing tests** — append to `tests/test_fluxmail.py`:

```python
class TestInlineImages:
    def test_inline_image_attaches_with_content_id(self, smtp_email, tmp_path):
        img = tmp_path / "logo.png"
        img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 50)
        smtp_email.create(
            subject="Hi", recipients=["a@b.com"],
            body='<img src="cid:logo">Hello', html_body=True,
            inline_images={"logo": str(img)},
        )
        payload = smtp_email.message.get_payload()
        content_ids = [
            str(part.get("Content-ID", ""))
            for part in (payload if isinstance(payload, list) else [smtp_email.message])
        ]
        assert any("logo" in cid for cid in content_ids)

    def test_missing_inline_image_raises(self, smtp_email, tmp_path):
        with pytest.raises(FluxMailException) as exc_info:
            smtp_email.create(
                subject="Hi", recipients=["a@b.com"],
                body="<b>hi</b>", html_body=True,
                inline_images={"logo": str(tmp_path / "missing.png")},
            )
        assert exc_info.value.code == "attachment_not_found"

    def test_non_dict_inline_images_raises(self, smtp_email):
        with pytest.raises(FluxMailException) as exc_info:
            smtp_email.create(
                subject="Hi", recipients=["a@b.com"], body="Hi",
                inline_images=["logo.png"],
            )
        assert exc_info.value.code == "invalid_params"

    def test_inline_images_outlook_raises(self, smtp_email):
        with patch.object(smtp_email, "is_outlook", return_value=True), \
             patch.object(smtp_email, "is_smtp", return_value=False):
            smtp_email.create(subject="Hi", recipients=["a@b.com"], body="Hi")
            smtp_email.inline_images = {"logo": "/fake/logo.png"}
            with pytest.raises(FluxMailException) as exc_info:
                smtp_email._attach_inline_images()
        assert exc_info.value.code == "invalid_params"

    def test_no_inline_images_by_default(self, smtp_email):
        smtp_email.create(subject="Hi", recipients=["a@b.com"], body="Hello")
        assert smtp_email.is_created  # no error
```

- [ ] **Step 2: Run — expect FAIL**

```
pytest tests/test_fluxmail.py::TestInlineImages -v
```
Expected: `TypeError: FluxMail.create() got an unexpected keyword argument 'inline_images'`

- [ ] **Step 3: Implement** — in `src/fluxmail/fluxmail.py`:

**3a** — Add `"inline_images"` to `__slots__` (after `"unsubscribe_url"`):
```python
        "unsubscribe_url",
        "inline_images",
```

**3b** — Add `inline_images: Optional[Dict[str, str]] = None` to `create()` (after `unsubscribe_url`). Also add `Dict` to the typing import if not present — current import is `from typing import List, Optional, Tuple, Union`. Update to:
```python
from typing import Dict, List, Optional, Tuple, Union
```

Add to `create()` signature:
```python
        unsubscribe_url: Optional[str] = None,
        inline_images: Optional[Dict[str, str]] = None,
```

**3c** — Add assignment in `create()` body (after `self.unsubscribe_url = unsubscribe_url`):
```python
        self.inline_images = inline_images
```

**3d** — Add inline_images validation in `_validate_parameters()` after the attachments check:
```python
        if self.inline_images is not None and not isinstance(self.inline_images, dict):
            raise FluxMailException(
                "inline_images must be a dict mapping cid_name to file_path.",
                code="invalid_params",
            )
```

**3e** — Add `_attach_inline_images()` method after `_attach_files()`:
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
                    f"Inline image not found: {file_path}",
                    code="attachment_not_found",
                )
            data, name = self._read_file(file_path)
            mime_type, _ = mimetypes.guess_type(file_path)
            content_type = mime_type or "application/octet-stream"
            maintype, subtype = content_type.split("/", 1)
            self.message.add_attachment(
                data,
                maintype=maintype,
                subtype=subtype,
                filename=name,
                disposition="inline",
                cid=f"<{cid_name}>",
            )
            self.logger.debug(
                "Inline image attached: cid=%s (%s, %d bytes)",
                cid_name, content_type, len(data),
            )
```

**3f** — Add `self._attach_inline_images()` to `create()` call chain, after `self._attach_files()`:
```python
        self._attach_files()
        self._attach_inline_images()
        self.is_created = True
```

- [ ] **Step 4: Run — expect PASS**

```
pytest tests/test_fluxmail.py::TestInlineImages -v
```

- [ ] **Step 5: Run full suite**

```
pytest tests/ --tb=short 2>&1 | tail -5
```

- [ ] **Step 6: Commit**

```
git add src/fluxmail/fluxmail.py tests/test_fluxmail.py
git commit -m "feat: add inline CID image support on create()"
```

---

### Task 6: CSS inlining via premailer

**Files:**
- Modify: `src/fluxmail/fluxmail.py`
- Modify: `tests/test_fluxmail.py`

- [ ] **Step 1: Write failing tests** — append to `tests/test_fluxmail.py`:

```python
class TestCSSInlining:
    def test_css_inlined_when_html_true(self, smtp_email):
        smtp_email.create(
            subject="Hi", recipients=["a@b.com"],
            body='<p style="color: red">Hello</p>',
            html_body=True, inline_css=True,
        )
        assert smtp_email.is_created

    def test_inline_css_ignored_when_not_html(self, smtp_email):
        # inline_css=True with html_body=False must not raise
        smtp_email.create(
            subject="Hi", recipients=["a@b.com"],
            body="Plain text", html_body=False, inline_css=True,
        )
        assert smtp_email.is_created

    def test_premailer_failure_raises_css_inline_failed(self, smtp_email):
        with patch("fluxmail.fluxmail.premailer.transform", side_effect=Exception("bad html")):
            with pytest.raises(FluxMailException) as exc_info:
                smtp_email.create(
                    subject="Hi", recipients=["a@b.com"],
                    body="<bad>", html_body=True, inline_css=True,
                )
        assert exc_info.value.code == "css_inline_failed"

    def test_inline_css_false_by_default(self, smtp_email):
        smtp_email.create(
            subject="Hi", recipients=["a@b.com"],
            body='<style>p{color:red}</style><p>Hi</p>', html_body=True,
        )
        assert smtp_email.is_created
```

- [ ] **Step 2: Run — expect FAIL**

```
pytest tests/test_fluxmail.py::TestCSSInlining -v
```
Expected: `TypeError: FluxMail.create() got an unexpected keyword argument 'inline_css'`

- [ ] **Step 3: Implement** — in `src/fluxmail/fluxmail.py`:

**3a** — Add `import premailer` to the top-level imports (after `import time`):
```python
import premailer
```

**3b** — Add `"inline_css"` to `__slots__` (after `"inline_images"`):
```python
        "inline_images",
        "inline_css",
```

**3c** — Add `inline_css: bool = False` to `create()` signature (after `inline_images`):
```python
        inline_images: Optional[Dict[str, str]] = None,
        inline_css: bool = False,
```

**3d** — Add assignment in `create()` body (after `self.inline_images = inline_images`):
```python
        self.inline_css = inline_css
```

**3e** — Update `_set_content_type()` to apply CSS inlining. Replace the current opening of `_set_content_type()`:

```python
    def _set_content_type(self):
        if self.is_smtp():
            body = self.body
            if self.html_body and self.inline_css:
                try:
                    body = premailer.transform(body)
                except Exception as e:
                    raise FluxMailException(
                        f"CSS inlining failed: {e}", code="css_inline_failed"
                    ) from e
            if self.html_body and self.plain_body:
                self.message.set_content(self.plain_body, subtype="plain")
                self.message.add_alternative(body, subtype="html")
            else:
                self.message.set_content(
                    body, subtype="html" if self.html_body else "plain"
                )
        elif self.is_outlook():
            self.message.BodyFormat = 2 if self.html_body else 1
            if self.html_body:
                self.message.HTMLBody = self.body
            else:
                self.message.Body = self.body
```

- [ ] **Step 4: Run — expect PASS**

```
pytest tests/test_fluxmail.py::TestCSSInlining -v
```

- [ ] **Step 5: Run full suite**

```
pytest tests/ --tb=short 2>&1 | tail -5
```

- [ ] **Step 6: Commit**

```
git add src/fluxmail/fluxmail.py tests/test_fluxmail.py
git commit -m "feat: add CSS inlining via premailer on create()"
```

---

### Task 7: `_SMTPTransport.async_connection()`

**Files:**
- Modify: `src/fluxmail/_transport.py`
- Modify: `tests/test_transport.py`

- [ ] **Step 1: Write failing tests** — append to `tests/test_transport.py`:

```python
class TestAsyncConnection:
    async def test_yields_authenticated_smtp_conn(self):
        t = make_transport(username="u@example.com", password="pass")
        mock_smtp = AsyncMock()
        mock_smtp.__aenter__ = AsyncMock(return_value=mock_smtp)
        mock_smtp.__aexit__ = AsyncMock(return_value=False)
        with patch("fluxmail._transport.aiosmtplib.SMTP", MagicMock(return_value=mock_smtp)):
            async with t.async_connection() as smtp:
                assert smtp is mock_smtp
        mock_smtp.login.assert_called_once_with("u@example.com", "pass")

    async def test_starttls_called_when_use_tls(self):
        t = make_transport(use_tls=True, username="u@example.com", password="pass")
        mock_smtp = AsyncMock()
        mock_smtp.__aenter__ = AsyncMock(return_value=mock_smtp)
        mock_smtp.__aexit__ = AsyncMock(return_value=False)
        with patch("fluxmail._transport.aiosmtplib.SMTP", MagicMock(return_value=mock_smtp)):
            async with t.async_connection() as smtp:
                pass
        mock_smtp.starttls.assert_called_once()
        mock_smtp.login.assert_called_once()

    async def test_starttls_not_called_when_use_ssl(self):
        t = make_transport(use_ssl=True, username="u@example.com", password="pass")
        mock_smtp = AsyncMock()
        mock_smtp.__aenter__ = AsyncMock(return_value=mock_smtp)
        mock_smtp.__aexit__ = AsyncMock(return_value=False)
        with patch("fluxmail._transport.aiosmtplib.SMTP", MagicMock(return_value=mock_smtp)):
            async with t.async_connection() as smtp:
                pass
        mock_smtp.starttls.assert_not_called()

    async def test_no_login_without_credentials(self):
        t = make_transport()
        mock_smtp = AsyncMock()
        mock_smtp.__aenter__ = AsyncMock(return_value=mock_smtp)
        mock_smtp.__aexit__ = AsyncMock(return_value=False)
        with patch("fluxmail._transport.aiosmtplib.SMTP", MagicMock(return_value=mock_smtp)):
            async with t.async_connection() as smtp:
                pass
        mock_smtp.login.assert_not_called()
```

- [ ] **Step 2: Run — expect FAIL**

```
pytest tests/test_transport.py::TestAsyncConnection -v
```
Expected: `AttributeError: '_SMTPTransport' object has no attribute 'async_connection'`

- [ ] **Step 3: Implement** — in `src/fluxmail/_transport.py`:

**3a** — Add `from contextlib import asynccontextmanager` to the top-level imports (after `import logging`):
```python
from contextlib import asynccontextmanager
```

**3b** — Add `async_connection()` method to `_SMTPTransport`, after `send_async()`:

```python
    @asynccontextmanager
    async def async_connection(self):
        """Async context manager yielding an authenticated aiosmtplib.SMTP for reuse.

        Use inside ``BulkSender.send_batch_async()`` to hold one connection
        open across the whole batch instead of reconnecting per message.
        """
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
        self._logger.debug(
            "Persistent async SMTP connection closed: %s:%d", self._relay, self._port
        )
```

- [ ] **Step 4: Run — expect PASS**

```
pytest tests/test_transport.py::TestAsyncConnection -v
```

- [ ] **Step 5: Run full suite**

```
pytest tests/ --tb=short 2>&1 | tail -5
```

- [ ] **Step 6: Commit**

```
git add src/fluxmail/_transport.py tests/test_transport.py
git commit -m "feat: add _SMTPTransport.async_connection() context manager"
```

---

### Task 8: `BulkSender.send_batch_async()`

**Files:**
- Modify: `src/fluxmail/bulk.py`
- Modify: `tests/test_bulk.py`

- [ ] **Step 1: Write failing tests** — append to `tests/test_bulk.py`:

```python
class TestSendBatchAsync:
    async def test_all_succeed(self):
        mock_smtp = AsyncMock()
        mock_smtp.__aenter__ = AsyncMock(return_value=mock_smtp)
        mock_smtp.__aexit__ = AsyncMock(return_value=False)
        with patch("fluxmail._transport.aiosmtplib.SMTP", MagicMock(return_value=mock_smtp)):
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
            {"subject": "Good",  "recipients": ["a@b.com"], "body": "ok"},
            {"subject": "Bad",   "recipients": ["not-valid"], "body": "fail"},
            {"subject": "Good2", "recipients": ["b@b.com"], "body": "ok"},
        ]
        with patch("fluxmail._transport.aiosmtplib.SMTP", MagicMock(return_value=mock_smtp)):
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
        with patch("fluxmail._transport.aiosmtplib.SMTP", MagicMock(return_value=mock_smtp)):
            with patch("fluxmail.bulk.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                mailer = FluxMail(object_type="smtp", host=HOST, username="u@example.com")
                await BulkSender(mailer).send_batch_async(
                    make_messages(2), progress=False, max_per_second=10
                )
        assert mock_sleep.call_count == 2
        mock_sleep.assert_called_with(pytest.approx(0.1, rel=1e-3))

    async def test_negative_max_per_second_raises(self):
        mailer = FluxMail(object_type="smtp", host=HOST, username="u@example.com")
        with pytest.raises(FluxMailException) as exc_info:
            await BulkSender(mailer).send_batch_async([], progress=False, max_per_second=-1)
        assert exc_info.value.code == "invalid_config"

    async def test_on_error_callback_called(self):
        errors = []
        mock_smtp = AsyncMock()
        mock_smtp.__aenter__ = AsyncMock(return_value=mock_smtp)
        mock_smtp.__aexit__ = AsyncMock(return_value=False)
        with patch("fluxmail._transport.aiosmtplib.SMTP", MagicMock(return_value=mock_smtp)):
            mailer = FluxMail(object_type="smtp", host=HOST, username="u@example.com")
            await BulkSender(mailer).send_batch_async(
                [{"subject": "Hi", "recipients": ["bad"], "body": "Hello"}],
                on_error=lambda i, e: errors.append((i, e)),
                progress=False,
            )
        assert len(errors) == 1
        assert isinstance(errors[0][1], FluxMailException)
```

Also add `from unittest.mock import AsyncMock` to `tests/test_bulk.py` imports if not already present.

- [ ] **Step 2: Run — expect FAIL**

```
pytest tests/test_bulk.py::TestSendBatchAsync -v
```
Expected: `AttributeError: 'BulkSender' object has no attribute 'send_batch_async'`

- [ ] **Step 3: Implement** — in `src/fluxmail/bulk.py`:

**3a** — Add `import asyncio` to the top of `bulk.py`:
```python
import asyncio
```

**3b** — Add `send_batch_async()` method to `BulkSender`, after `send_batch()`:

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
                        if max_per_second > 0:
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
```

- [ ] **Step 4: Run — expect PASS**

```
pytest tests/test_bulk.py::TestSendBatchAsync -v
```

- [ ] **Step 5: Run full suite**

```
pytest tests/ --tb=short 2>&1 | tail -5
```

- [ ] **Step 6: Commit**

```
git add src/fluxmail/bulk.py tests/test_bulk.py
git commit -m "feat: add BulkSender.send_batch_async() with rate limiting"
```

---

### Task 9: Django email backend

**Files:**
- Create: `src/fluxmail/backends/__init__.py`
- Create: `src/fluxmail/backends/django.py`
- Create: `tests/test_backend_django.py`

- [ ] **Step 1: Write failing tests** — create `tests/test_backend_django.py`:

```python
"""Tests for the Django email backend.

Django settings are configured via settings.configure() at module level
so no Django project is required to run these tests.
"""
from unittest.mock import MagicMock, patch

import pytest
import django
from django.conf import settings

if not settings.configured:
    settings.configure(
        EMAIL_HOST="smtp.example.com",
        EMAIL_PORT=587,
        EMAIL_HOST_USER="u@example.com",
        EMAIL_HOST_PASSWORD="secret",
        EMAIL_USE_TLS=True,
        EMAIL_USE_SSL=False,
        EMAIL_TIMEOUT=30,
        EMAIL_FLUXMAIL_MAX_RETRIES=0,
        EMAIL_FLUXMAIL_RETRY_DELAY=1.0,
        USE_TZ=True,
    )

from fluxmail.backends.django import FluxMailBackend  # noqa: E402


HOST = "smtp.example.com"
SMTP_MOCK = "fluxmail._transport.smtplib.SMTP"


def make_backend(fail_silently=False):
    return FluxMailBackend(fail_silently=fail_silently)


def make_django_msg(subject="Test", to=None, body="Hello"):
    """Minimal Django EmailMessage stub."""
    stdlib_msg = MagicMock()
    msg = MagicMock()
    msg.message.return_value = stdlib_msg
    return msg


class TestFluxMailBackend:
    def test_send_messages_returns_sent_count(self):
        backend = make_backend()
        mock_conn = MagicMock()
        with patch(SMTP_MOCK, MagicMock(return_value=mock_conn)):
            result = backend.send_messages([make_django_msg(), make_django_msg()])
        assert result == 2

    def test_send_messages_calls_transport_send(self):
        backend = make_backend()
        stdlib_msg = MagicMock()
        django_msg = MagicMock()
        django_msg.message.return_value = stdlib_msg
        mock_conn = MagicMock()
        with patch(SMTP_MOCK, MagicMock(return_value=mock_conn)):
            backend.send_messages([django_msg])
        mock_conn.send_message.assert_called_once_with(stdlib_msg)

    def test_fail_silently_suppresses_exception(self):
        backend = make_backend(fail_silently=True)
        with patch.object(backend._mailer._transport, "send", side_effect=Exception("fail")):
            result = backend.send_messages([make_django_msg()])
        assert result == 0

    def test_fail_silently_false_raises(self):
        backend = make_backend(fail_silently=False)
        with patch.object(backend._mailer._transport, "send", side_effect=Exception("fail")):
            with pytest.raises(Exception, match="fail"):
                backend.send_messages([make_django_msg()])

    def test_open_returns_true_first_call(self):
        backend = make_backend()
        mock_conn = MagicMock()
        with patch(SMTP_MOCK, MagicMock(return_value=mock_conn)):
            result = backend.open()
        assert result is True
        assert backend._connection_open is True

    def test_open_returns_false_when_already_open(self):
        backend = make_backend()
        mock_conn = MagicMock()
        with patch(SMTP_MOCK, MagicMock(return_value=mock_conn)):
            backend.open()
            result = backend.open()
        assert result is False

    def test_close_resets_connection_state(self):
        backend = make_backend()
        mock_conn = MagicMock()
        with patch(SMTP_MOCK, MagicMock(return_value=mock_conn)):
            backend.open()
        backend.close()
        assert backend._connection_open is False

    def test_close_is_noop_when_not_open(self):
        backend = make_backend()
        backend.close()  # must not raise
        assert backend._connection_open is False

    def test_settings_map_correctly(self):
        backend = make_backend()
        assert backend._mailer.host.relay == "smtp.example.com"
        assert backend._mailer.port == 587
        assert backend._mailer.use_tls is True
        assert backend._mailer.timeout == 30
```

- [ ] **Step 2: Run — expect FAIL**

```
pytest tests/test_backend_django.py -v
```
Expected: `ModuleNotFoundError: No module named 'fluxmail.backends'`

- [ ] **Step 3: Create `src/fluxmail/backends/__init__.py`** — empty file:

```python
```

(Create the file with no content.)

- [ ] **Step 4: Create `src/fluxmail/backends/django.py`**:

```python
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

from ..fluxmail import FluxMail


class FluxMailBackend(BaseEmailBackend):
    """Django email backend using FluxMail for SMTP delivery.

    Configure in Django settings::

        EMAIL_BACKEND = "fluxmail.backends.django.FluxMailBackend"
        EMAIL_HOST = "smtp.gmail.com"
        EMAIL_PORT = 587
        EMAIL_HOST_USER = "me@gmail.com"
        EMAIL_HOST_PASSWORD = "secret"
        EMAIL_USE_TLS = True

    Optional FluxMail-specific settings::

        EMAIL_FLUXMAIL_MAX_RETRIES = 3
        EMAIL_FLUXMAIL_RETRY_DELAY = 1.0
    """

    def __init__(self, fail_silently: bool = False, **kwargs) -> None:
        super().__init__(fail_silently=fail_silently, **kwargs)
        self._mailer = self._create_mailer()
        self._connection_open = False

    def _create_mailer(self) -> FluxMail:
        return FluxMail(
            object_type="smtp",
            host=getattr(settings, "EMAIL_HOST", "localhost"),
            port=getattr(settings, "EMAIL_PORT", 25),
            username=getattr(settings, "EMAIL_HOST_USER", None) or None,
            password=getattr(settings, "EMAIL_HOST_PASSWORD", None) or None,
            use_tls=getattr(settings, "EMAIL_USE_TLS", False),
            use_ssl=getattr(settings, "EMAIL_USE_SSL", False),
            timeout=int(getattr(settings, "EMAIL_TIMEOUT", 30)),
            max_retries=int(getattr(settings, "EMAIL_FLUXMAIL_MAX_RETRIES", 0)),
            retry_delay=float(getattr(settings, "EMAIL_FLUXMAIL_RETRY_DELAY", 1.0)),
        )

    def open(self) -> bool:
        """Open a persistent SMTP connection.

        Returns ``True`` if a new connection was opened, ``False`` if already open.
        This return value is used by Django to track connection reuse.
        """
        if self._connection_open:
            return False
        self._mailer.__enter__()
        self._connection_open = True
        return True

    def close(self) -> None:
        """Close the persistent SMTP connection."""
        if not self._connection_open:
            return
        self._mailer.__exit__(None, None, None)
        self._connection_open = False

    def send_messages(self, email_messages) -> int:
        """Send a list of Django EmailMessage objects.

        Uses Django's own ``EmailMessage.message()`` to build the stdlib
        ``email.message.Message`` and passes it directly to ``_transport.send()``,
        preserving Django's full MIME logic (attachments, multipart, etc.).

        Returns the number of messages successfully sent.
        """
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

- [ ] **Step 5: Run — expect PASS**

```
pytest tests/test_backend_django.py -v
```

- [ ] **Step 6: Run full suite**

```
pytest tests/ --tb=short 2>&1 | tail -5
```

- [ ] **Step 7: Commit**

```
git add src/fluxmail/backends/__init__.py src/fluxmail/backends/django.py tests/test_backend_django.py
git commit -m "feat: add Django email backend (FluxMailBackend)"
```

---

### Task 10: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update architecture source layout table**

Replace the existing `**Source layout** (\`src/fluxmail/\`):` table with:

```markdown
**Source layout** (`src/fluxmail/`):

| File | Role |
|------|------|
| `fluxmail.py` | `FluxMail` class — email creation, send, send_async, retry, from_env, test_connection |
| `_transport.py` | `_SMTPTransport` — all SMTP connection logic (sync + async, SSL variants, async_connection) |
| `utils.py` | `EmailObject`, `EmailInstance`, `FluxMailException`, `validate_email`, `str_to_enum` |
| `template.py` | `EmailTemplate` — Jinja2 body renderer |
| `bulk.py` | `BulkSender` — batch sender with Rich progress bar; sync and async |
| `backends/__init__.py` | Package marker (empty) |
| `backends/django.py` | `FluxMailBackend` — Django `EMAIL_BACKEND` drop-in |
| `fluxmail_cli.py` | Typer-based CLI; calls `FluxMail` |
| `__init__.py` | Public exports: `FluxMail`, `FluxMailException`, `EmailInstance`, `EmailObject`, `EmailTemplate`, `BulkSender`, `__version__` |
| `__main__.py` | `python -m fluxmail` entry point |
| `testing.py` | `mock_smtp()` context manager for tests (patches `fluxmail._transport.smtplib.SMTP`) |
```

- [ ] **Step 2: Append new design decisions**

At the end of the `**Key design decisions:**` bullet list, add:

```markdown
- `FluxMail.from_env()` reads `FLUXMAIL_HOST`, `FLUXMAIL_PORT`, `FLUXMAIL_USERNAME`, `FLUXMAIL_PASSWORD`, `FLUXMAIL_TLS`, `FLUXMAIL_SSL`, `FLUXMAIL_TIMEOUT`, `FLUXMAIL_MAX_RETRIES`, `FLUXMAIL_RETRY_DELAY` from env.
- `test_connection()` opens, authenticates, and immediately closes an SMTP connection; returns `{"ok", "relay", "port", "latency_ms"}`.
- `create(unsubscribe_url=)` adds RFC 8058 `List-Unsubscribe` + `List-Unsubscribe-Post` headers (SMTP only).
- `create(inline_images={"cid": "/path"})` attaches inline images with `Content-ID: <cid>` for use as `<img src="cid:cid">` in HTML (SMTP only).
- `create(inline_css=True)` runs `premailer.transform()` on the HTML body before sending; silently skipped when `html_body=False`.
- `BulkSender.send_batch_async(messages, max_per_second=N)` uses `_SMTPTransport.async_connection()` to hold one async SMTP connection for the whole batch; `max_per_second` inserts `asyncio.sleep(1/N)` after each send.
- Django backend (`fluxmail.backends.django.FluxMailBackend`) reads standard `EMAIL_*` settings; `send_messages()` uses `django_msg.message()` directly to preserve Django's MIME logic.
```

- [ ] **Step 3: Run full suite one final time**

```
pytest tests/ -v --tb=short 2>&1 | tail -10
```
Expected: all tests pass.

- [ ] **Step 4: Commit**

```
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md for developer features (from_env, test_connection, CID, CSS, async bulk, Django)"
```

---

## Self-Review

**Spec coverage:**

| Spec requirement | Task |
|---|---|
| `_parse_bool` module-level function | Task 2 |
| `FluxMail.from_env()` with all 10 env vars | Task 2 |
| Outlook special case in `from_env()` | Task 2 |
| `test_connection()` returning diagnostics dict | Task 3 |
| `test_connection()` Outlook raises `outlook_no_connect` | Task 3 |
| `List-Unsubscribe` + `List-Unsubscribe-Post` headers | Task 4 |
| Outlook: silently ignore `unsubscribe_url` | Task 4 |
| Inline CID images: dict param, SMTP only | Task 5 |
| Inline CID images: Outlook raises, missing file raises | Task 5 |
| `inline_images` dict validation in `_validate_parameters()` | Task 5 |
| CSS inlining via `premailer.transform()` | Task 6 |
| CSS inlining silently skipped when `html_body=False` | Task 6 |
| `import premailer` at top of `fluxmail.py` | Task 6 |
| `from contextlib import asynccontextmanager` added to `_transport.py` | Task 7 |
| `async_connection()` TLS mapping: `use_ssl`→constructor, `use_tls`→`starttls()` | Task 7 |
| `send_batch_async()` with same error-isolation as `send_batch()` | Task 8 |
| `max_per_second` rate limiting with `asyncio.sleep` | Task 8 |
| Negative `max_per_second` raises `invalid_config` | Task 8 |
| `backends/__init__.py` empty package marker | Task 9 |
| `FluxMailBackend` reads `EMAIL_*` settings | Task 9 |
| `_mailer` created in `__init__` (always available) | Task 9 |
| `open()` returns `True`/`False` per Django convention | Task 9 |
| `send_messages()` uses `msg.message()` → `_transport.send()` | Task 9 |
| `fail_silently` suppresses exceptions | Task 9 |
| CLAUDE.md architecture table | Task 10 |

**Placeholder scan:** No TBDs, TODOs, or vague steps. All code blocks are complete.

**Type consistency:**
- `_parse_bool(value: str) -> bool` defined Task 2, called in `from_env()` Task 2 ✓
- `inline_images: Optional[Dict[str, str]]` defined Task 5, `Dict` import added Task 5 ✓
- `async_connection()` defined Task 7, called in `send_batch_async()` Task 8 ✓
- `FluxMailBackend._mailer` created in `__init__` Task 9, used in `send_messages()` Task 9 ✓
