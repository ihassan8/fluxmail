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
# Gmail with TLS (credentials via env vars)
AUTOEMAIL_USERNAME=me@gmail.com AUTOEMAIL_PASSWORD=secret \
  autoemail --type smtp --host smtp.gmail.com --port 587 --tls \
  --subject "Test" --recipients someone@example.com --body "Hello"

# relay:domain pair
autoemail --type smtp --host smtp.myrelay.com:mycompany.com \
  --subject "Test" --recipients user@mycompany.com --body "Hello" \
  --sender noreply@mycompany.com

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
| `utils.py` | `EmailObject`, `EmailInstance`, `AutoEmailException`, `validate_email`, `str_to_enum` |
| `autoemail_cli.py` | Typer-based CLI; calls `AutoEmail` |
| `__init__.py` | Public exports: `AutoEmail`, `AutoEmailException`, `EmailInstance`, `EmailObject`, `__version__` |
| `__main__.py` | `python -m autoemail` entry point |
| `testing.py` | `mock_smtp()` context manager for tests (not exported from `__init__.py`) |

**Key design decisions:**

- `AutoEmail` uses `__slots__` for memory efficiency.
- `host` accepts `EmailInstance(relay=..., domain=...)` (domain is optional, defaults to `""`), a bare relay string `"smtp.gmail.com"`, or a `"relay:domain"` string `"smtp.gmail.com:gmail.com"`.
- `EmailInstance` is a `namedtuple` with `relay` required and `domain` optional (default `""`).
- **Sender resolution**: if `sender=` is not provided, `username` is used when it is a valid email address (works for Gmail, SES, Mailgun). For API-key-style auth (e.g. SendGrid's `"apikey"` username), `sender=` must be passed explicitly.
- `validate_email()` performs format-only validation — no domain or TLD restrictions.
- SMTP sends via `smtplib.SMTP`. Supports port, STARTTLS (`use_tls=True`), and login credentials.
- Outlook sends via `win32com.client` (Windows only). Cannot send programmatically — requires user confirmation.
- Logging uses `pylogshield`. `get_logger()` is imported from it and returns a standard `logging.Logger`-compatible instance. Pass a custom `logging.Logger` or set `log_level` (a string: `"DEBUG"`, `"INFO"`, `"WARNING"`, `"ERROR"`) in the constructor.
- `create()` returns `self` — method chaining is supported: `AutoEmail(...).create(...).send()`.
- `create()` resets `self.message` on each call — the same `AutoEmail` instance can be reused.
- `display()` returns an email preview string (SMTP) or opens Outlook's display window. `send(dry_run=True)` delegates to `display()` internally.
- `__enter__`/`__exit__` open a persistent SMTP connection for reuse across multiple sends.

**Typical API flow:**

```python
from autoemail import AutoEmail, EmailInstance

# Bare relay string (simplest)
email = AutoEmail(object_type="smtp", host="smtp.gmail.com",
                  port=587, use_tls=True,
                  username="me@gmail.com", password="secret")
email.create(subject="Hi", recipients=["friend@example.com"], body="Hello").send()

# EmailInstance with explicit sender (e.g. SendGrid)
email = AutoEmail(object_type="smtp",
                  host=EmailInstance(relay="smtp.sendgrid.net"),
                  port=587, use_tls=True,
                  username="apikey", password="SG.xxx")
email.create(subject="Hi", recipients=["user@example.com"], body="Hello",
             sender="noreply@myapp.com").send()

# Catch errors
from autoemail import AutoEmailException
try:
    email.send()
except AutoEmailException as e:
    print(e)
```

## Python Compatibility

All type annotations must use `typing` module forms (`List`, `Optional`, `Union`, `Tuple`) — not the Python 3.10+ shorthand (`|`, `list[...]`, `X | None`). The project supports Python 3.8+.

## Adding Dependencies

Only update `requirements.txt` when adding dependencies. Both `pyproject.toml` (via `dynamic = ["dependencies"]`) and `setup.py` read from it automatically — no other file needs changing.

## CLI Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | Invalid `--type`, missing body, or `--body`/`--body-file` conflict |
| `2` | `AutoEmailException` raised during send (e.g. missing sender, SMTP error) |
| `99` | Unexpected/unhandled exception |

## Planned Features

Plans for future modules in `docs/superpowers/plans/`:
1. **`EmailTemplate`** (`template.py`) — Jinja2-based body templating
2. **`send_async()`** — async SMTP via `aiosmtplib`
3. **Retry logic** — `max_retries`/`retry_delay` via `tenacity`
4. **`BulkSender`** (`bulk.py`) — per-recipient send loop with progress bar

New `__slots__` entries are required in `AutoEmail` when adding instance attributes.

## Versioning

Version is managed by `setuptools_scm` from git tags and written to `src/autoemail/_version.py` at build time. Do not manually edit `_version.py`.

## Notes

- MIME type for SMTP attachments is auto-detected via `mimetypes.guess_type` (stdlib); no extra dependency needed.
- Tests live in `tests/`. Run with `pytest`. `conftest.py` provides the `smtp_email` fixture (host + username pre-configured).
