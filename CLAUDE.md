# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AutoEmail is a Python library for email automation supporting SMTP and Outlook protocols. It provides both a Python API and a CLI. Outlook support is Windows-only (requires `pywin32`).

## Development Setup

```bash
pip install -e .
```

## Build

```bash
pip install build
python -m build    # produces wheel + sdist in dist/
```

## Run CLI

The CLI is built with **Typer**. Run `autoemail --help` for full usage with Rich-formatted output.

```bash
# Built-in relay
autoemail --type smtp --host Domain1 --subject "Test" --recipients user@hr.acme.com --body "Hello"

# Custom relay with TLS (credentials via env vars)
AUTOEMAIL_USERNAME=me@gmail.com AUTOEMAIL_PASSWORD=secret \
  autoemail --type smtp --host smtp.gmail.com:gmail.com --port 587 --tls \
  --subject "Test" --recipients someone@example.com --body "Hello"

# All optional flags
autoemail ... --sender me@example.com --cc a@x.com --bcc b@x.com \
  --reply-to r@x.com --attachments file.pdf --html --dry-run

autoemail --version
```

Credentials can also be passed inline via `--username` / `--password`, but env vars (`AUTOEMAIL_USERNAME`, `AUTOEMAIL_PASSWORD`) are preferred to avoid secrets appearing in shell history.

## Documentation

Docs tooling (separate from library dependencies):

```bash
pip install mkdocs-material mkdocstrings-python mkdocs-autorefs
```

```bash
mkdocs serve    # preview at http://localhost:8000
mkdocs build    # build static site to public/
```

Config is in `mkdocs.yml` (project root).

## Architecture

**Source layout** (`src/autoemail/`):

| File | Role |
|------|------|
| `autoemail.py` | `AutoEmail` class — core email creation/sending logic |
| `utils.py` | `EmailEnv`, `EmailObject`, `EmailInstance` enums/types; validation helpers; `AutoEmailException` |
| `autoemail_cli.py` | Typer-based CLI; calls `AutoEmail` |
| `__init__.py` | Public exports: `AutoEmail`, `AutoEmailException`, `EmailEnv`, `EmailInstance`, `EmailObject`, `__version__` |
| `__main__.py` | `python -m autoemail` entry point |

**Key design decisions:**

- `AutoEmail` uses `__slots__` for memory efficiency.
- `host` accepts `EmailEnv` (built-in named environments), `EmailInstance(relay=..., domain=...)` (custom server — no source changes needed), or a string name (`"Domain1"`).
- `EmailEnv` is a hybrid class: it inherits from both `EmailInstance` (a `namedtuple`) and `Enum`. This means each member *is* an `EmailInstance` and can be used wherever one is expected.
- `EmailEnv` relay/domain values default to `acme.com` placeholders but can be overridden via env vars (`AUTOEMAIL_DOMAIN1_RELAY`, `AUTOEMAIL_DOMAIN1_DOMAIN`, etc.) before import.
- `detect_domain_mismatches=False` by default — opt in when you need to enforce host/machine domain matching. CI/CD environments (FQDN containing `"runner"`) are automatically skipped.
- SMTP sends via `smtplib.SMTP`. Supports port, STARTTLS (`use_tls=True`), and login credentials for external servers (Gmail, SendGrid, etc.).
- Outlook sends via `win32com.client` (Windows only). Cannot send programmatically — requires user confirmation.
- Logging uses `pylogshield`. `get_logger()` is imported from it and returns a standard `logging.Logger`-compatible instance. Pass a custom `logging.Logger` or set `log_level` (a string: `"DEBUG"`, `"INFO"`, `"WARNING"`, `"ERROR"`) in the constructor.
- `create()` returns `self` — method chaining is supported: `AutoEmail(...).create(...).send()`.
- `display()` returns an email preview string (SMTP) or opens Outlook's display window. `send(dry_run=True)` delegates to `display()` internally.

**Typical API flow:**

```python
from autoemail import AutoEmail, EmailEnv, EmailObject, EmailInstance

# Built-in relay
email = AutoEmail(object_type=EmailObject.SMTP, host=EmailEnv.Domain1)
email.create(subject="Hi", recipients=["user@hr.acme.com"], body="Hello").send()

# Custom relay (any org, any SMTP server)
custom = EmailInstance(relay="smtp.gmail.com", domain="gmail.com")
email = AutoEmail(object_type="smtp", host=custom, port=587, use_tls=True,
                  username="me@gmail.com", password="secret")
email.create(subject="Hi", recipients=["friend@example.com"], body="Hello",
             bcc=["archive@example.com"], reply_to="noreply@example.com").send()

# Catch errors
from autoemail import AutoEmailException
try:
    email.send()
except AutoEmailException as e:
    print(e)
```

## Email Validation Behavior

`validate_email()` in `utils.py` has a `gov_email` mode that is non-obvious:
- The **sender** is always validated as a `.gov` address matching `host.domain` (SMTP only).
- **Recipients, CC** are validated as `.gov` only when the host is not `EmailEnv.Domain1`; Domain1 recipients can be any valid email.
- **BCC** and `reply_to` always skip `.gov` enforcement regardless of host.

This means an SMTP email to a custom relay or Domain2/Domain3 requires all To/CC addresses to be `.gov` addresses on the host's domain.

## Python Compatibility

All type annotations must use `typing` module forms (`List`, `Optional`, `Union`, `Tuple`) — not the Python 3.10+ shorthand (`|`, `list[...]`, `X | None`). The project supports Python 3.8+.

## Adding Dependencies

Only update `requirements.txt` when adding dependencies. Both `pyproject.toml` (via `dynamic = ["dependencies"]`) and `setup.py` read from it automatically — no other file needs changing.

## CLI Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | Invalid `--type` or `--host` argument |
| `2` | `AutoEmailException` raised during send |
| `99` | Unexpected/unhandled exception |

## Planned Features

An approved design spec for five additive features is planned at `docs/superpowers/specs/2026-03-16-feature-expansion-design.md` (file not yet created):
1. **`EmailTemplate`** (`template.py`) — Jinja2-based body templating
2. **`send_async()`** — async SMTP via `aiosmtplib`
3. **Retry logic** — `max_retries`/`retry_delay` via `tenacity`
4. **`mock_smtp()`** (`testing.py`) — test-only context manager; not exported from `__init__.py`
5. **`BulkSender`** (`bulk.py`) — per-recipient send loop with progress bar

New `__slots__` entries are required in `AutoEmail` when adding instance attributes.

## Versioning

Version is managed by `setuptools_scm` from git tags and written to `src/autoemail/_version.py` at build time. Do not manually edit `_version.py`.

## Notes

- No test suite exists in this repository.
- `EmailEnv` docstrings use the internal org domain names (`acme.com`) as placeholders — update them and the env var defaults when deploying to a real organization.
- MIME type for SMTP attachments is auto-detected via `mimetypes.guess_type` (stdlib); no extra dependency needed.
