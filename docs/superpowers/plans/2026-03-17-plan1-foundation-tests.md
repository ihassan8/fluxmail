# Plan 1: Foundation — Test Infrastructure & Core Enhancements

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish a full pytest suite for the existing codebase and add eight additive improvements to `AutoEmail` and the CLI without breaking any current behaviour.

**Architecture:** All new behaviour is additive — new optional parameters on `create()` / `__init__()` with `None` defaults and corresponding new private methods. The `create()` method is made reusable by resetting `self.message` at its start, enabling connection-reuse via a new `__enter__`/`__exit__` pair. The CLI's `--body` flag is relaxed to optional; mutual exclusion with `--body-file` is enforced at runtime.

**Tech Stack:** `pytest`, `typer[testing]`, `unittest.mock` (stdlib) — no new runtime dependencies for Plan 1.

---

## File Map

| Action | Path | Responsibility |
|--------|------|---------------|
| Create | `requirements-dev.txt` | Dev/test dependencies |
| Create | `tests/__init__.py` | Make tests a package |
| Create | `tests/conftest.py` | Shared fixtures (`gov_host`, `smtp_email`, `mock_current_user`) |
| Create | `tests/test_utils.py` | Unit tests for `utils.py` |
| Create | `tests/test_autoemail.py` | Unit tests for `AutoEmail` core |
| Create | `tests/test_cli.py` | Unit tests for the Typer CLI |
| Create | `src/autoemail/testing.py` | `mock_smtp()` context manager (not exported from `__init__.py`) |
| Modify | `src/autoemail/autoemail.py` | `__slots__`, `create()` reset, multipart, threading, priority, context manager |
| Modify | `src/autoemail/autoemail_cli.py` | Make `--body` optional, add `--body-file` |
| Modify | `pyproject.toml` | Add `[tool.pytest.ini_options]` section |

### New `__slots__` entries (must be added to `AutoEmail.__slots__`)

`"plain_body"`, `"in_reply_to"`, `"references"`, `"priority"`, `"_smtp_conn"`

All five must be initialised to `None` in `__init__`.

---

## Task 1: Dev Tooling

**Files:**
- Create: `requirements-dev.txt`
- Modify: `pyproject.toml`

- [ ] **Step 1: Create `requirements-dev.txt`**

```
pytest>=7.4
```

- [ ] **Step 2: Add pytest config to `pyproject.toml`**

Append to the end of `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 3: Install dev deps and verify pytest runs**

```bash
pip install -r requirements-dev.txt
pytest --collect-only
```
Expected: `no tests ran` (no test files yet) — not an error.

- [ ] **Step 4: Commit**

```bash
git add requirements-dev.txt pyproject.toml
git commit -m "chore: add pytest dev tooling"
```

---

## Task 2: `mock_smtp()` Test Utility

**Files:**
- Create: `src/autoemail/testing.py`

- [ ] **Step 1: Create `src/autoemail/testing.py`**

```python
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
    >>> from autoemail import AutoEmail, EmailEnv, EmailObject
    >>> with mock_smtp() as smtp:
    ...     AutoEmail(object_type=EmailObject.SMTP, host=EmailEnv.Domain1).create(
    ...         subject="Hi", recipients=["a@b.com"], body="Hello"
    ...     ).send()
    ...     smtp.send_message.assert_called_once()
    """
    mock_instance = MagicMock()
    mock_cls = MagicMock()
    mock_cls.return_value.__enter__ = MagicMock(return_value=mock_instance)
    mock_cls.return_value.__exit__ = MagicMock(return_value=False)

    with patch("autoemail.autoemail.smtplib.SMTP", mock_cls):
        yield mock_instance
```

- [ ] **Step 2: Verify import works**

```bash
python -c "from autoemail.testing import mock_smtp; print('ok')"
```
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add src/autoemail/testing.py
git commit -m "feat: add mock_smtp() test utility"
```

---

## Task 3: Test Infrastructure (conftest + empty test files)

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create `tests/__init__.py`** (empty)

- [ ] **Step 2: Create `tests/conftest.py`**

```python
import pytest
from unittest.mock import patch

from autoemail import EmailEnv, EmailInstance, EmailObject
from autoemail.autoemail import AutoEmail


@pytest.fixture
def gov_host():
    """A custom EmailInstance whose domain ends in .gov — needed for gov_email validation tests."""
    return EmailInstance(relay="smtp.test.gov", domain="hr.test.gov")


@pytest.fixture
def smtp_email():
    return AutoEmail(object_type=EmailObject.SMTP, host=EmailEnv.Domain1)


@pytest.fixture(autouse=True)
def mock_current_user():
    """Prevent all tests from calling getpass.getuser() — returns a stable value instead.

    Without this, the auto-sender path fails in CI where the OS username is unpredictable.
    The auto-sender becomes 'testuser@<host.domain>' and bypasses gov_email validation
    because it is set directly (not through validate_email).
    """
    with patch("autoemail.autoemail.get_current_user", return_value="testuser"):
        yield
```

- [ ] **Step 3: Verify fixtures are discovered**

```bash
pytest --fixtures -q 2>&1 | grep -E "gov_host|smtp_email|mock_current_user"
```
Expected: all three fixture names appear.

- [ ] **Step 4: Commit**

```bash
git add tests/
git commit -m "chore: add test package and shared fixtures"
```

---

## Task 4: Unit Tests for `utils.py`

**Files:**
- Create: `tests/test_utils.py`

- [ ] **Step 1: Write `tests/test_utils.py`**

```python
import pytest

from autoemail import AutoEmailException, EmailEnv, EmailInstance, EmailObject
from autoemail.utils import (
    detect_domain_mismatch,
    str_to_enum,
    validate_email,
)


# ── str_to_enum ──────────────────────────────────────────────────────────────

class TestStrToEnum:
    def test_by_name_lowercase(self):
        assert str_to_enum(EmailObject, "smtp") == EmailObject.SMTP

    def test_by_name_uppercase(self):
        assert str_to_enum(EmailObject, "SMTP") == EmailObject.SMTP

    def test_by_name_mixed_case(self):
        assert str_to_enum(EmailObject, "Smtp") == EmailObject.SMTP

    def test_passthrough_enum_member(self):
        assert str_to_enum(EmailObject, EmailObject.SMTP) == EmailObject.SMTP

    def test_invalid_string_raises_value_error(self):
        with pytest.raises(ValueError, match="Invalid value"):
            str_to_enum(EmailObject, "fax")

    def test_non_string_non_enum_raises_type_error(self):
        with pytest.raises(TypeError):
            str_to_enum(EmailObject, 123)

    def test_emailenv_by_name(self):
        assert str_to_enum(EmailEnv, "Domain1") == EmailEnv.Domain1

    def test_emailenv_case_insensitive(self):
        assert str_to_enum(EmailEnv, "domain1") == EmailEnv.Domain1


# ── validate_email ───────────────────────────────────────────────────────────

class TestValidateEmail:
    HOST = EmailInstance(relay="r", domain="example.com")
    GOV  = EmailInstance(relay="r", domain="hr.test.gov")

    def test_valid_email_returned(self):
        assert validate_email("user@example.com", self.HOST) == "user@example.com"

    def test_strips_and_lowercases(self):
        assert validate_email("  User@Example.COM  ", self.HOST) == "user@example.com"

    def test_strips_trailing_dot(self):
        assert validate_email("user@example.com.", self.HOST) == "user@example.com"

    def test_missing_at_raises(self):
        with pytest.raises(AutoEmailException):
            validate_email("notanemail", self.HOST)

    def test_dot_before_at_raises(self):
        with pytest.raises(AutoEmailException):
            validate_email(".@example.com", self.HOST)

    def test_at_before_dot_raises(self):
        with pytest.raises(AutoEmailException):
            validate_email("user@.example.com", self.HOST)

    def test_empty_string_raises(self):
        with pytest.raises(AutoEmailException):
            validate_email("", self.HOST)

    def test_gov_email_valid(self):
        assert validate_email("user@hr.test.gov", self.GOV, gov_email=True) == "user@hr.test.gov"

    def test_gov_email_wrong_tld_raises(self):
        with pytest.raises(AutoEmailException, match=r"\.gov"):
            validate_email("user@hr.test.com", self.GOV, gov_email=True)

    def test_gov_email_wrong_domain_raises(self):
        with pytest.raises(AutoEmailException, match="must match domain"):
            validate_email("user@other.test.gov", self.GOV, gov_email=True)

    def test_bcc_skips_gov_check(self):
        # gov_email=False (BCC/reply-to path) must accept non-.gov address even on gov host
        assert validate_email("user@gmail.com", self.GOV, gov_email=False) == "user@gmail.com"


# ── detect_domain_mismatch ───────────────────────────────────────────────────

class TestDetectDomainMismatch:
    def test_matching_domain_does_not_raise(self, monkeypatch):
        monkeypatch.setattr("autoemail.utils.get_domain", lambda: "machine.hr.acme.com")
        detect_domain_mismatch(EmailEnv.Domain1)  # should not raise

    def test_mismatched_domain_raises(self, monkeypatch):
        monkeypatch.setattr("autoemail.utils.get_domain", lambda: "machine.ops.acme.com")
        with pytest.raises(AutoEmailException, match="Mismatch"):
            detect_domain_mismatch(EmailEnv.Domain1)

    def test_ci_runner_skipped(self, monkeypatch):
        monkeypatch.setattr("autoemail.utils.get_domain", lambda: "runner.github.com")
        detect_domain_mismatch(EmailEnv.Domain1)  # should not raise

    def test_single_label_hostname_skipped(self, monkeypatch):
        monkeypatch.setattr("autoemail.utils.get_domain", lambda: "localhost")
        detect_domain_mismatch(EmailEnv.Domain1)  # should not raise
```

- [ ] **Step 2: Run and verify all pass**

```bash
pytest tests/test_utils.py -v
```
Expected: all green.

- [ ] **Step 3: Commit**

```bash
git add tests/test_utils.py
git commit -m "test: unit tests for utils.py"
```

---

## Task 5: Unit Tests for `AutoEmail` Core

**Files:**
- Create: `tests/test_autoemail.py`

- [ ] **Step 1: Write `tests/test_autoemail.py`**

```python
import pytest
from autoemail import AutoEmail, AutoEmailException, EmailEnv, EmailInstance, EmailObject
from autoemail.testing import mock_smtp


GOV_HOST = EmailInstance(relay="smtp.test.gov", domain="hr.test.gov")


# ── __init__ ─────────────────────────────────────────────────────────────────

class TestInit:
    def test_smtp_object_type(self):
        e = AutoEmail(object_type=EmailObject.SMTP, host=EmailEnv.Domain1)
        assert e.is_smtp()
        assert not e.is_outlook()

    def test_string_type_accepted(self):
        e = AutoEmail(object_type="smtp", host=EmailEnv.Domain1)
        assert e.is_smtp()

    def test_custom_emailinstance_host(self):
        e = AutoEmail(object_type="smtp", host=GOV_HOST)
        assert e.host == GOV_HOST

    def test_invalid_type_raises(self):
        with pytest.raises(ValueError):
            AutoEmail(object_type="fax", host=EmailEnv.Domain1)

    def test_invalid_logger_raises(self):
        with pytest.raises(AutoEmailException):
            AutoEmail(object_type="smtp", host=EmailEnv.Domain1, logger="not-a-logger")

    def test_default_port(self):
        e = AutoEmail(object_type="smtp", host=EmailEnv.Domain1)
        assert e.port == 25

    def test_custom_port(self):
        e = AutoEmail(object_type="smtp", host=EmailEnv.Domain1, port=587)
        assert e.port == 587


# ── create() ─────────────────────────────────────────────────────────────────

class TestCreate:
    def test_returns_self(self, smtp_email):
        result = smtp_email.create(subject="Hi", recipients=["a@b.com"], body="Hello")
        assert result is smtp_email

    def test_is_created_true_after_call(self, smtp_email):
        smtp_email.create(subject="Hi", recipients=["a@b.com"], body="Hello")
        assert smtp_email.is_created

    def test_empty_subject_raises(self, smtp_email):
        with pytest.raises(AutoEmailException):
            smtp_email.create(subject="", recipients=["a@b.com"], body="Hello")

    def test_empty_recipients_raises(self, smtp_email):
        with pytest.raises(AutoEmailException):
            smtp_email.create(subject="Hi", recipients=[], body="Hello")

    def test_string_recipients_raises(self, smtp_email):
        with pytest.raises(AutoEmailException):
            smtp_email.create(subject="Hi", recipients="a@b.com", body="Hello")

    def test_string_cc_raises(self, smtp_email):
        with pytest.raises(AutoEmailException):
            smtp_email.create(subject="Hi", recipients=["a@b.com"], body="Hi", cc="a@b.com")

    def test_string_bcc_raises(self, smtp_email):
        with pytest.raises(AutoEmailException):
            smtp_email.create(subject="Hi", recipients=["a@b.com"], body="Hi", bcc="a@b.com")

    def test_subject_set_on_message(self, smtp_email):
        smtp_email.create(subject="Test Subject", recipients=["a@b.com"], body="Hi")
        assert smtp_email.message["Subject"] == "Test Subject"

    def test_recipients_set_on_message(self, smtp_email):
        smtp_email.create(subject="Hi", recipients=["alice@b.com", "bob@b.com"], body="Hi")
        assert "alice@b.com" in smtp_email.message["To"]
        assert "bob@b.com" in smtp_email.message["To"]

    def test_cc_set_on_message(self, smtp_email):
        smtp_email.create(subject="Hi", recipients=["a@b.com"], body="Hi", cc=["cc@b.com"])
        assert "cc@b.com" in smtp_email.message["Cc"]

    def test_bcc_set_on_message(self, smtp_email):
        smtp_email.create(subject="Hi", recipients=["a@b.com"], body="Hi", bcc=["bcc@b.com"])
        assert "bcc@b.com" in smtp_email.message["Bcc"]

    def test_reply_to_set_on_message(self, smtp_email):
        smtp_email.create(
            subject="Hi", recipients=["a@b.com"], body="Hi", reply_to="r@b.com"
        )
        assert "r@b.com" in smtp_email.message["Reply-To"]

    def test_sender_validated_when_explicit(self, gov_host):
        e = AutoEmail(object_type="smtp", host=gov_host)
        e.create(subject="Hi", recipients=["user@hr.test.gov"], body="Hi",
                 sender="sender@hr.test.gov")
        assert e.message["From"] == "sender@hr.test.gov"

    def test_explicit_sender_wrong_domain_raises(self, gov_host):
        e = AutoEmail(object_type="smtp", host=gov_host)
        with pytest.raises(AutoEmailException):
            e.create(subject="Hi", recipients=["user@hr.test.gov"], body="Hi",
                     sender="sender@other.gov")


# ── send() ───────────────────────────────────────────────────────────────────

class TestSend:
    def test_send_before_create_raises(self, smtp_email):
        with pytest.raises(AutoEmailException, match=r"create\(\)"):
            smtp_email.send()

    def test_dry_run_returns_preview_string(self, smtp_email):
        smtp_email.create(subject="Hi", recipients=["a@b.com"], body="Hello")
        result = smtp_email.send(dry_run=True)
        assert "Email Preview" in result

    def test_send_calls_send_message(self, smtp_email):
        with mock_smtp() as smtp:
            smtp_email.create(subject="Hi", recipients=["a@b.com"], body="Hello")
            result = smtp_email.send()
        assert "sent successfully" in result
        smtp.send_message.assert_called_once()

    def test_send_with_tls_calls_starttls(self):
        with mock_smtp() as smtp:
            e = AutoEmail(object_type="smtp", host=EmailEnv.Domain1, use_tls=True)
            e.create(subject="Hi", recipients=["a@b.com"], body="Hello")
            e.send()
        smtp.starttls.assert_called_once()

    def test_send_without_tls_does_not_starttls(self):
        with mock_smtp() as smtp:
            e = AutoEmail(object_type="smtp", host=EmailEnv.Domain1, use_tls=False)
            e.create(subject="Hi", recipients=["a@b.com"], body="Hello")
            e.send()
        smtp.starttls.assert_not_called()

    def test_send_with_credentials_calls_login(self):
        with mock_smtp() as smtp:
            e = AutoEmail(object_type="smtp", host=EmailEnv.Domain1,
                          username="u", password="p")
            e.create(subject="Hi", recipients=["a@b.com"], body="Hello")
            e.send()
        smtp.login.assert_called_once_with("u", "p")

    def test_send_without_credentials_skips_login(self):
        with mock_smtp() as smtp:
            e = AutoEmail(object_type="smtp", host=EmailEnv.Domain1)
            e.create(subject="Hi", recipients=["a@b.com"], body="Hello")
            e.send()
        smtp.login.assert_not_called()

    def test_smtp_exception_raises_autoemail_exception(self, smtp_email):
        with mock_smtp() as smtp:
            smtp.send_message.side_effect = ConnectionRefusedError("refused")
            smtp_email.create(subject="Hi", recipients=["a@b.com"], body="Hello")
            with pytest.raises(AutoEmailException, match="Send failed"):
                smtp_email.send()


# ── display() ────────────────────────────────────────────────────────────────

class TestDisplay:
    def test_display_before_create_raises(self, smtp_email):
        with pytest.raises(AutoEmailException, match="create()"):
            smtp_email.display()

    def test_display_returns_string(self, smtp_email):
        smtp_email.create(subject="Hi", recipients=["a@b.com"], body="Hello")
        result = smtp_email.display()
        assert isinstance(result, str)
        assert "Email Preview" in result
```

- [ ] **Step 2: Run and verify all pass**

```bash
pytest tests/test_autoemail.py -v
```
Expected: all green.

- [ ] **Step 3: Commit**

```bash
git add tests/test_autoemail.py
git commit -m "test: unit tests for AutoEmail core"
```

---

## Task 6: CLI Unit Tests

**Files:**
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write `tests/test_cli.py`**

```python
import pytest
from typer.testing import CliRunner
from autoemail.autoemail_cli import app
from autoemail.testing import mock_smtp

runner = CliRunner()

BASE = [
    "--type", "smtp",
    "--host", "Domain1",
    "--subject", "Test",
    "--recipients", "user@example.com",
    "--body", "Hello",
]


def test_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "autoemail" in result.output


def test_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "--type" in result.output


def test_basic_send():
    with mock_smtp():
        result = runner.invoke(app, BASE)
    assert result.exit_code == 0
    assert "sent successfully" in result.output


def test_dry_run():
    result = runner.invoke(app, BASE + ["--dry-run"])
    assert result.exit_code == 0
    assert "Email Preview" in result.output


def test_invalid_type_exits_1():
    args = ["--type", "fax", "--host", "Domain1",
            "--subject", "T", "--recipients", "a@b.com", "--body", "Hi"]
    result = runner.invoke(app, args)
    assert result.exit_code == 1


def test_invalid_host_exits_1():
    # A host string with no colon and no matching EmailEnv name → BadParameter → exit 1.
    # Do NOT use "relay:domain" format here — that is a valid custom EmailInstance.
    args = ["--type", "smtp", "--host", "NotAValidHost",
            "--subject", "T", "--recipients", "a@b.com", "--body", "Hi"]
    result = runner.invoke(app, args)
    assert result.exit_code == 1


def test_custom_host_relay_colon_syntax():
    with mock_smtp():
        args = [
            "--type", "smtp",
            "--host", "smtp.example.com:example.com",
            "--subject", "T",
            "--recipients", "a@b.com",
            "--body", "Hi",
        ]
        result = runner.invoke(app, args)
    assert result.exit_code == 0


def test_multiple_recipients():
    with mock_smtp():
        result = runner.invoke(app, [
            "--type", "smtp", "--host", "Domain1",
            "--subject", "T",
            "--recipients", "a@b.com",
            "--recipients", "c@d.com",
            "--body", "Hi",
        ])
    assert result.exit_code == 0


def test_html_flag():
    with mock_smtp():
        result = runner.invoke(app, BASE + ["--html"])
    assert result.exit_code == 0
```

- [ ] **Step 2: Run and verify all pass**

```bash
pytest tests/test_cli.py -v
```
Expected: all green.

- [ ] **Step 3: Commit**

```bash
git add tests/test_cli.py
git commit -m "test: unit tests for CLI"
```

---

## Task 7: Multipart Email (plain + HTML alternative)

**Files:**
- Modify: `src/autoemail/autoemail.py`
- Modify: `tests/test_autoemail.py`

**Background:** RFC 2046 recommends sending `multipart/alternative` with a plain-text fallback when the body is HTML. Currently `_set_content_type()` sets one or the other. This task adds an optional `plain_body` parameter: when both `html_body=True` and `plain_body` is provided, the message is built as `multipart/alternative`.

- [ ] **Step 1: Write the failing tests first**

Add to `tests/test_autoemail.py`:

```python
class TestMultipart:
    def test_html_with_plain_body_creates_multipart(self, smtp_email):
        smtp_email.create(
            subject="Hi", recipients=["a@b.com"],
            body="<h1>Hello</h1>",
            html_body=True,
            plain_body="Hello",
        )
        # multipart/alternative has a list payload
        assert isinstance(smtp_email.message.get_payload(), list)

    def test_html_without_plain_body_is_not_multipart(self, smtp_email):
        smtp_email.create(
            subject="Hi", recipients=["a@b.com"],
            body="<h1>Hello</h1>",
            html_body=True,
        )
        assert isinstance(smtp_email.message.get_payload(), str)

    def test_plain_body_ignored_when_html_body_false(self, smtp_email):
        smtp_email.create(
            subject="Hi", recipients=["a@b.com"],
            body="Hello",
            html_body=False,
            plain_body="ignored",
        )
        assert isinstance(smtp_email.message.get_payload(), str)
```

- [ ] **Step 2: Run to confirm they fail**

```bash
pytest tests/test_autoemail.py::TestMultipart -v
```
Expected: FAIL (TypeError — `plain_body` is an unexpected keyword argument).

- [ ] **Step 3: Add `"plain_body"` to `AutoEmail.__slots__`**

In `src/autoemail/autoemail.py`, inside `__slots__`:

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
    "plain_body",       # NEW — plain-text fallback for multipart/alternative
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
    "in_reply_to",      # NEW — threading (added in Task 8)
    "references",       # NEW — threading (added in Task 8)
    "priority",         # NEW — priority headers (added in Task 9)
    "_smtp_conn",       # NEW — connection reuse (added in Task 10)
)
```

> **Add all five new slots at once** to avoid revisiting this section for Tasks 8–10.

- [ ] **Step 4: Initialize all new slots in `__init__`**

At the end of `__init__`, after `self.is_created = False`:

```python
self.plain_body = None
self.in_reply_to = None
self.references = None
self.priority = None
self._smtp_conn = None
```

- [ ] **Step 5: Add `plain_body` parameter to `create()`**

```python
def create(
    self,
    subject: str,
    recipients: List[str],
    body: str,
    sender: Optional[str] = None,
    cc: Optional[List[str]] = None,
    bcc: Optional[List[str]] = None,
    reply_to: Optional[str] = None,
    attachments: Optional[List[str]] = None,
    html_body: bool = False,
    plain_body: Optional[str] = None,   # NEW
) -> "AutoEmail":
```

And assign it with the others:

```python
self.plain_body = plain_body
```

- [ ] **Step 6: Reset `self.message` at the top of `create()` for reusability**

Replace the opening lines of `create()` body (before `self.subject = subject`) with:

```python
# Reset the message object so create() can be called again on the same instance.
if self.is_smtp():
    self.message = EmailMessage()
self.is_created = False
```

- [ ] **Step 7: Update `_set_content_type()` to build multipart when appropriate**

```python
def _set_content_type(self):
    if self.is_smtp():
        if self.html_body and self.plain_body:
            self.message.set_content(self.plain_body, subtype="plain")
            self.message.add_alternative(self.body, subtype="html")
        else:
            self.message.set_content(
                self.body, subtype="html" if self.html_body else "plain"
            )
    elif self.is_outlook():
        self.message.BodyFormat = 2 if self.html_body else 1
        if self.html_body:
            self.message.HTMLBody = self.body
        else:
            self.message.Body = self.body
```

- [ ] **Step 8: Run tests to confirm they pass**

```bash
pytest tests/test_autoemail.py -v
```
Expected: all green including `TestMultipart`.

- [ ] **Step 9: Commit**

```bash
git add src/autoemail/autoemail.py tests/test_autoemail.py
git commit -m "feat: add plain_body param for multipart/alternative emails"
```

---

## Task 8: Threading Headers (In-Reply-To, References)

**Files:**
- Modify: `src/autoemail/autoemail.py`
- Modify: `tests/test_autoemail.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_autoemail.py`:

```python
class TestThreadingHeaders:
    def test_in_reply_to_set(self, smtp_email):
        smtp_email.create(
            subject="Re: Hi", recipients=["a@b.com"], body="Reply",
            in_reply_to="<abc123@example.com>",
        )
        assert smtp_email.message["In-Reply-To"] == "<abc123@example.com>"

    def test_references_set(self, smtp_email):
        smtp_email.create(
            subject="Re: Hi", recipients=["a@b.com"], body="Reply",
            references=["<msg1@example.com>", "<msg2@example.com>"],
        )
        assert "<msg1@example.com>" in smtp_email.message["References"]
        assert "<msg2@example.com>" in smtp_email.message["References"]

    def test_no_threading_headers_by_default(self, smtp_email):
        smtp_email.create(subject="Hi", recipients=["a@b.com"], body="Hi")
        assert smtp_email.message["In-Reply-To"] is None
        assert smtp_email.message["References"] is None
```

- [ ] **Step 2: Run to confirm they fail**

```bash
pytest tests/test_autoemail.py::TestThreadingHeaders -v
```
Expected: FAIL.

- [ ] **Step 3: Add parameters to `create()`**

```python
def create(
    self,
    ...
    plain_body: Optional[str] = None,
    in_reply_to: Optional[str] = None,        # NEW
    references: Optional[List[str]] = None,   # NEW
) -> "AutoEmail":
```

Assign them:

```python
self.in_reply_to = in_reply_to
self.references = references
```

- [ ] **Step 4: Add `_handle_threading()` method and call it from `create()`**

```python
def _handle_threading(self) -> None:
    if not self.is_smtp():
        return
    if self.in_reply_to:
        self.message["In-Reply-To"] = self.in_reply_to
    if self.references:
        self.message["References"] = " ".join(self.references)
```

Call `self._handle_threading()` inside `create()` after `self._handle_reply_to()`.

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_autoemail.py -v
```
Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add src/autoemail/autoemail.py tests/test_autoemail.py
git commit -m "feat: add in_reply_to and references threading headers"
```

---

## Task 9: Priority / Importance Headers

**Files:**
- Modify: `src/autoemail/autoemail.py`
- Modify: `tests/test_autoemail.py`

- [ ] **Step 1: Write failing tests**

```python
class TestPriorityHeaders:
    def test_high_priority_sets_headers(self, smtp_email):
        smtp_email.create(
            subject="URGENT", recipients=["a@b.com"], body="Hi", priority="high"
        )
        assert smtp_email.message["X-Priority"] == "1"
        assert smtp_email.message["Importance"] == "High"
        assert smtp_email.message["X-MSMail-Priority"] == "High"

    def test_low_priority(self, smtp_email):
        smtp_email.create(
            subject="FYI", recipients=["a@b.com"], body="Hi", priority="low"
        )
        assert smtp_email.message["X-Priority"] == "5"

    def test_invalid_priority_raises(self, smtp_email):
        with pytest.raises(AutoEmailException, match="priority"):
            smtp_email.create(
                subject="Hi", recipients=["a@b.com"], body="Hi", priority="urgent"
            )

    def test_no_priority_headers_by_default(self, smtp_email):
        smtp_email.create(subject="Hi", recipients=["a@b.com"], body="Hi")
        assert smtp_email.message["X-Priority"] is None
```

- [ ] **Step 2: Run to confirm they fail**

```bash
pytest tests/test_autoemail.py::TestPriorityHeaders -v
```

- [ ] **Step 3: Add module-level constant and `_handle_priority()` to `autoemail.py`**

Add near the top of `autoemail.py` (after imports):

```python
_PRIORITY_MAP = {
    "high":   ("1", "High",   "High"),
    "normal": ("3", "Normal", "Normal"),
    "low":    ("5", "Low",    "Low"),
}
```

Add method to `AutoEmail`:

```python
def _handle_priority(self) -> None:
    if not self.priority or not self.is_smtp():
        return
    x_prio, importance, ms_prio = _PRIORITY_MAP[self.priority]
    self.message["X-Priority"] = x_prio
    self.message["Importance"] = importance
    self.message["X-MSMail-Priority"] = ms_prio
```

- [ ] **Step 4: Add `priority` parameter to `create()` and validate it**

```python
def create(
    self,
    ...
    references: Optional[List[str]] = None,
    priority: Optional[str] = None,   # NEW — "high", "normal", or "low"
) -> "AutoEmail":
```

Assign: `self.priority = priority`

In `_validate_parameters()`, add:

```python
if self.priority and self.priority not in _PRIORITY_MAP:
    raise AutoEmailException(
        f"priority must be one of {list(_PRIORITY_MAP.keys())}, got '{self.priority}'"
    )
```

Call `self._handle_priority()` inside `create()` after `self._handle_threading()`.

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_autoemail.py -v
```
Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add src/autoemail/autoemail.py tests/test_autoemail.py
git commit -m "feat: add priority/importance headers (high, normal, low)"
```

---

## Task 10: Connection Reuse via Context Manager

**Files:**
- Modify: `src/autoemail/autoemail.py`
- Modify: `tests/test_autoemail.py`

**Background:** Every `send()` currently opens and closes a fresh SMTP connection. `__enter__`/`__exit__` lets callers hold one connection open across multiple `create()` + `send()` pairs.

- [ ] **Step 1: Write failing tests**

```python
class TestContextManager:
    def test_context_manager_reuses_connection(self):
        from unittest.mock import patch, MagicMock
        mock_conn = MagicMock()
        mock_cls = MagicMock(return_value=mock_conn)

        with patch("autoemail.autoemail.smtplib.SMTP", mock_cls):
            with AutoEmail(object_type="smtp", host=EmailEnv.Domain1) as mailer:
                mailer.create(subject="A", recipients=["a@b.com"], body="1").send()
                mailer.create(subject="B", recipients=["a@b.com"], body="2").send()

        # SMTP() constructor called only once, not twice
        mock_cls.assert_called_once()
        assert mock_conn.send_message.call_count == 2

    def test_context_manager_calls_quit_on_exit(self):
        from unittest.mock import patch, MagicMock
        mock_conn = MagicMock()
        mock_cls = MagicMock(return_value=mock_conn)

        with patch("autoemail.autoemail.smtplib.SMTP", mock_cls):
            with AutoEmail(object_type="smtp", host=EmailEnv.Domain1) as mailer:
                mailer.create(subject="A", recipients=["a@b.com"], body="1").send()

        mock_conn.quit.assert_called_once()

    def test_send_outside_context_still_works(self):
        with mock_smtp() as smtp:
            e = AutoEmail(object_type="smtp", host=EmailEnv.Domain1)
            e.create(subject="Hi", recipients=["a@b.com"], body="Hello").send()
        smtp.send_message.assert_called_once()
```

- [ ] **Step 2: Run to confirm they fail**

```bash
pytest tests/test_autoemail.py::TestContextManager -v
```

- [ ] **Step 3: Implement `__enter__` and `__exit__`**

Add to `AutoEmail` (after `__repr__`):

```python
def __enter__(self) -> "AutoEmail":
    """Open a persistent SMTP connection for reuse across multiple sends."""
    if self.is_smtp():
        self._smtp_conn = smtplib.SMTP(self.host.relay, self.port)
        if self.use_tls:
            self._smtp_conn.starttls()
        if self.username and self.password:
            self._smtp_conn.login(self.username, self.password)
    return self

def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
    if self._smtp_conn is not None:
        try:
            self._smtp_conn.quit()
        except Exception:
            pass
        self._smtp_conn = None
    return False
```

- [ ] **Step 4: Update `send()` to use `_smtp_conn` when available**

Replace the `if self.is_smtp() and self.host.relay:` block in `send()`:

```python
if self.is_smtp() and self.host.relay:
    if self._smtp_conn is not None:
        # Reuse existing connection opened by __enter__
        self._smtp_conn.send_message(self.message)
    else:
        with smtplib.SMTP(self.host.relay, self.port) as smtp:
            if self.use_tls:
                smtp.starttls()
            if self.username and self.password:
                smtp.login(self.username, self.password)
            smtp.send_message(self.message)
    return "Email sent successfully via SMTP."
```

- [ ] **Step 5: Run all tests**

```bash
pytest tests/ -v
```
Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add src/autoemail/autoemail.py tests/test_autoemail.py
git commit -m "feat: add context manager for SMTP connection reuse"
```

---

## Task 11: `--body-file` CLI Flag

**Files:**
- Modify: `src/autoemail/autoemail_cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_cli.py`:

```python
import tempfile, os

def test_body_file_sends_file_content(tmp_path):
    body_file = tmp_path / "body.txt"
    body_file.write_text("Hello from file")
    with mock_smtp() as smtp:
        result = runner.invoke(app, [
            "--type", "smtp", "--host", "Domain1",
            "--subject", "T", "--recipients", "a@b.com",
            "--body-file", str(body_file),
        ])
    assert result.exit_code == 0
    sent = smtp.send_message.call_args[0][0]
    assert "Hello from file" in sent.get_payload()


def test_body_and_body_file_mutual_exclusion():
    result = runner.invoke(app, [
        "--type", "smtp", "--host", "Domain1",
        "--subject", "T", "--recipients", "a@b.com",
        "--body", "Hi",
        "--body-file", "somefile.txt",
    ])
    assert result.exit_code == 1


def test_neither_body_nor_body_file_exits_1():
    result = runner.invoke(app, [
        "--type", "smtp", "--host", "Domain1",
        "--subject", "T", "--recipients", "a@b.com",
    ])
    assert result.exit_code == 1


def test_body_file_not_found_exits_1(tmp_path):
    result = runner.invoke(app, [
        "--type", "smtp", "--host", "Domain1",
        "--subject", "T", "--recipients", "a@b.com",
        "--body-file", str(tmp_path / "missing.txt"),
    ])
    assert result.exit_code == 1
```

- [ ] **Step 2: Run to confirm they fail**

```bash
pytest tests/test_cli.py::test_body_file_sends_file_content -v
```
Expected: FAIL (unrecognised option `--body-file`).

- [ ] **Step 3: Update `send()` command in `autoemail_cli.py`**

Change `body` from required to optional (default `None`):

```python
body: Annotated[
    Optional[str],
    typer.Option(help="Email body — plain text or HTML string."),
] = None,
```

Add `body_file` parameter after `body`:

```python
body_file: Annotated[
    Optional[str],
    typer.Option(
        "--body-file",
        help="Path to a file whose content becomes the email body. "
             "Mutually exclusive with --body.",
    ),
] = None,
```

- [ ] **Step 4: Add validation logic in the command body (before `AutoEmail` is constructed)**

```python
if body and body_file:
    typer.echo("[ERROR] --body and --body-file are mutually exclusive.", err=True)
    raise typer.Exit(1)

if body_file:
    try:
        with open(body_file, "r", encoding="utf-8") as fh:
            body = fh.read()
    except OSError as exc:
        typer.echo(f"[ERROR] Cannot read --body-file: {exc}", err=True)
        raise typer.Exit(1)

if not body:
    typer.echo("[ERROR] Either --body or --body-file is required.", err=True)
    raise typer.Exit(1)
```

- [ ] **Step 5: Run all tests**

```bash
pytest tests/ -v
```
Expected: all green.

- [ ] **Step 6: Update `docs/getting-started/cli_usage.md`**

Add `--body-file` row to the Flags table:

```markdown
| `--body-file` | No | — | Path to a file to use as the email body. Mutually exclusive with `--body`. |
```

Add an example tab `=== "Body from file"`:

```bash
autoemail --type smtp --host Domain1 \
  --subject "Report" \
  --recipients user@hr.acme.com \
  --body-file /path/to/report-body.html \
  --html
```

- [ ] **Step 7: Commit**

```bash
git add src/autoemail/autoemail_cli.py tests/test_cli.py docs/getting-started/cli_usage.md
git commit -m "feat: add --body-file CLI flag; make --body optional"
```

---

## Task 12: Final Test Run & Documentation

- [ ] **Step 1: Run the full suite**

```bash
pytest tests/ -v --tb=short
```
Expected: all green, zero failures.

- [ ] **Step 2: Check coverage (optional)**

```bash
pip install pytest-cov
pytest tests/ --cov=src/autoemail --cov-report=term-missing
```

- [ ] **Step 3: Update `docs/getting-started/usage.md`**

Add a section after "Connection reuse":

```markdown
## Multipart Email (HTML + Plain Text Fallback)

```python
email.create(
    subject="Report",
    recipients=["user@hr.acme.com"],
    body="<h1>Report</h1>",
    html_body=True,
    plain_body="Report — see the HTML version for formatting.",
)
```

## Threading

```python
email.create(
    subject="Re: Question",
    recipients=["user@hr.acme.com"],
    body="Following up.",
    in_reply_to="<original-message-id@example.com>",
    references=["<original-message-id@example.com>"],
)
```

## Priority

```python
email.create(
    subject="URGENT",
    recipients=["user@hr.acme.com"],
    body="Please respond ASAP.",
    priority="high",   # "high", "normal", or "low"
)
```

## Connection Reuse

```python
with AutoEmail(object_type="smtp", host=EmailEnv.Domain1) as mailer:
    for recipient in recipients:
        mailer.create(subject="Hi", recipients=[recipient], body="Hello").send()
```
```

- [ ] **Step 4: Final commit**

```bash
git add docs/
git commit -m "docs: document new Plan 1 features in usage guide"
```
