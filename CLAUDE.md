# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

FluxMail is a Python library for email automation supporting SMTP and Outlook protocols. It provides both a Python API and a CLI. Outlook support is Windows-only (requires `pywin32`).

## Development Setup

```bash
pip install -e .
pip install -r requirements-dev.txt   # test dependencies (pytest)
```

## Build

```bash
pip install build
python -m build    # produces wheel + sdist in dist/
```

## Testing

```bash
pytest                                              # run all tests
pytest tests/test_fluxmail.py                       # single file
pytest tests/test_fluxmail.py::TestSend             # single class
pytest tests/test_fluxmail.py::TestSend::test_send_calls_send_message  # single test
pytest -k "tls"                                     # keyword filter
```

`conftest.py` provides the `smtp_email` fixture (host + username pre-configured).

Use `mock_smtp()` from `fluxmail.testing` to patch `smtplib.SMTP` without real network connections:

```python
from fluxmail.testing import mock_smtp

with mock_smtp() as smtp:
    mailer.create(...).send()
    smtp.send_message.assert_called_once()
```

## Run CLI

The CLI is built with **Typer**. Run `fluxmail --help` for full usage with Rich-formatted output.

```bash
# Gmail with TLS (credentials via env vars)
FLUXMAIL_USERNAME=me@gmail.com FLUXMAIL_PASSWORD=secret \
  fluxmail --type smtp --host smtp.gmail.com --port 587 --tls \
  --subject "Test" --recipients someone@example.com --body "Hello"

# Body from file (mutually exclusive with --body)
fluxmail --type smtp --host smtp.gmail.com --port 587 --tls \
  --subject "Test" --recipients someone@example.com --body-file message.html --html

# relay:domain pair
fluxmail --type smtp --host smtp.myrelay.com:mycompany.com \
  --subject "Test" --recipients user@mycompany.com --body "Hello" \
  --sender noreply@mycompany.com

# All optional flags
fluxmail ... --sender me@example.com --cc a@x.com --bcc b@x.com \
  --reply-to r@x.com --attachments file.pdf --html --dry-run

fluxmail --version
```

Credentials can also be passed inline via `--username` / `--password`, but env vars (`FLUXMAIL_USERNAME`, `FLUXMAIL_PASSWORD`) are preferred to avoid secrets appearing in shell history.

## Documentation

Docs tooling (separate from library dependencies):

```bash
pip install -r docs/requirements.txt   # zensical + mkdocstrings[python]
```

```bash
zensical serve    # preview at http://localhost:8000
zensical build    # build static site to public/
```

Config is in `zensical.toml` (project root). Also install the library itself (`pip install -e .`) so mkdocstrings can import the package for API docs.

## Architecture

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

**Key design decisions:**

- `FluxMail` uses `__slots__` for memory efficiency.
- `host` accepts `EmailInstance(relay=..., domain=...)` (domain is optional, defaults to `""`), a bare relay string `"smtp.gmail.com"`, or a `"relay:domain"` string `"smtp.gmail.com:gmail.com"`.
- `EmailInstance` is a `namedtuple` with `relay` required and `domain` optional (default `""`).
- **Sender resolution**: if `sender=` is not provided, `username` is used when it is a valid email address (works for Gmail, SES, Mailgun). For API-key-style auth (e.g. SendGrid's `"apikey"` username), `sender=` must be passed explicitly.
- `validate_email()` performs format-only validation — no domain or TLD restrictions.
- SMTP sends via `smtplib.SMTP`. Supports port, STARTTLS (`use_tls=True`), and login credentials.
- Outlook sends via `win32com.client` (Windows only). Cannot send programmatically — requires user confirmation.
- Logging uses `pylogshield`. `get_logger()` is imported from it and returns a standard `logging.Logger`-compatible instance. Pass a custom `logging.Logger` or set `log_level` (a string: `"DEBUG"`, `"INFO"`, `"WARNING"`, `"ERROR"`) in the constructor.
- `create()` returns `self` — method chaining is supported: `FluxMail(...).create(...).send()`.
- `create()` resets `self.message` on each call — the same `FluxMail` instance can be reused.
- `display()` returns an email preview string (SMTP) or opens Outlook's display window. `send(dry_run=True)` delegates to `display()` internally.
- `__enter__`/`__exit__` open a persistent SMTP connection for reuse across multiple sends.
- **Multipart/alternative**: pass `html_body=True` + `plain_body="..."` to `create()` to build a `multipart/alternative` message; omitting `plain_body` sends HTML-only.
- **Priority headers**: `priority="high"|"normal"|"low"` sets `X-Priority`, `Importance`, and `X-MSMail-Priority` headers (SMTP only).
- **Thread headers**: `in_reply_to` and `references` set `In-Reply-To` / `References` MIME headers for reply threading (SMTP only).
- `use_ssl=True` uses `smtplib.SMTP_SSL` (port 465 implicit TLS). Mutually exclusive with `use_tls=True`.
- `timeout` (default `30`) is passed to every SMTP connection.
- `ssl_context` accepts a custom `ssl.SSLContext` for cert customisation.
- `max_retries` / `retry_delay` configure automatic retry via tenacity. Not applied to `send_async()`.
- `send_async()` uses `aiosmtplib` and accepts the same TLS/timeout params as `send()`.
- `EmailTemplate(template_str)` renders Jinja2 templates; use the result as `body=` in `create()`.
- `BulkSender(mailer).send_batch(messages)` sends a list-of-dicts batch over one connection.

**Typical API flow:**

```python
from fluxmail import FluxMail, EmailInstance

# Bare relay string (simplest)
email = FluxMail(object_type="smtp", host="smtp.gmail.com",
                  port=587, use_tls=True,
                  username="me@gmail.com", password="secret")
email.create(subject="Hi", recipients=["friend@example.com"], body="Hello").send()

# EmailInstance with explicit sender (e.g. SendGrid)
email = FluxMail(object_type="smtp",
                  host=EmailInstance(relay="smtp.sendgrid.net"),
                  port=587, use_tls=True,
                  username="apikey", password="SG.xxx")
email.create(subject="Hi", recipients=["user@example.com"], body="Hello",
             sender="noreply@myapp.com").send()

# Catch errors
from fluxmail import FluxMailException
try:
    email.send()
except FluxMailException as e:
    print(e)
```

## Python Compatibility

All type annotations must use `typing` module forms (`List`, `Optional`, `Union`, `Tuple`) — not the Python 3.10+ shorthand (`|`, `list[...]`, `X | None`). The project supports Python 3.8+.

## Adding Dependencies

Only update `requirements.txt` when adding library dependencies. `pyproject.toml` reads from it automatically via `dynamic = ["dependencies"]` — no other file needs changing. Add test-only dependencies to `requirements-dev.txt`.

## CLI Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | Invalid `--type`, missing body, or `--body`/`--body-file` conflict |
| `2` | `FluxMailException` raised during send (e.g. missing sender, SMTP error) |
| `99` | Unexpected/unhandled exception |

## Versioning

Version is managed by `setuptools_scm` from git tags and written to `src/fluxmail/_version.py` at build time. Do not manually edit `_version.py`.

## Notes

- MIME type for SMTP attachments is auto-detected via `mimetypes.guess_type` (stdlib); no extra dependency needed.
