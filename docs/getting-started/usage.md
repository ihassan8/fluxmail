# Python API

## Basic Send

Pass the relay hostname as a string and set `username` — it doubles as the `From` address:

```python
from fluxmail import FluxMail

email = FluxMail(
    object_type="smtp",
    host="smtp.gmail.com",
    port=587,
    use_tls=True,
    username="me@gmail.com",
    password="secret",  # (1)!
)
email.create(
    subject="Hello",
    recipients=["friend@example.com"],
    body="Hi there!",
).send()
```

1. Load credentials from an environment variable or secrets manager — never hardcode them in source.

## Explicit Sender

When your SMTP auth username is not the address you want in `From` (e.g. SendGrid API keys),
pass `sender=` explicitly:

```python
from fluxmail import FluxMail

email = FluxMail(
    object_type="smtp",
    host="smtp.sendgrid.net",
    port=587,
    use_tls=True,
    username="apikey",
    password="SG.xxxx",
)
email.create(
    subject="Hello",
    recipients=["user@example.com"],
    body="Hi!",
    sender="noreply@myapp.com",
).send()
```

## `EmailInstance` for Named Hosts

For reusable relay configurations, use `EmailInstance`:

```python
from fluxmail import FluxMail, EmailInstance

relay = EmailInstance(relay="smtp.myrelay.net", domain="mycompany.com")
email = FluxMail(object_type="smtp", host=relay, username="me@mycompany.com")
email.create(subject="Hi", recipients=["user@mycompany.com"], body="Hello").send()
```

## Method Chaining

`create()` returns `self`, enabling a single-expression send:

```python
FluxMail(object_type="smtp", host="smtp.gmail.com", port=587, use_tls=True,
          username="me@gmail.com", password="secret").create(
    subject="Quick Note",
    recipients=["friend@example.com"],
    body="Hi",
).send()
```

## Full Options

```python
from fluxmail import FluxMail

email = FluxMail(object_type="smtp", host="smtp.gmail.com", port=587, use_tls=True,
                  username="me@gmail.com", password="secret")
email.create(
    subject="Monthly Report",
    recipients=["alice@example.com", "bob@example.com"],
    body="<h1>Report</h1><p>See attached.</p>",
    sender="reports@myapp.com",
    cc=["manager@example.com"],
    bcc=["archive@example.com"],
    attachments=["/path/to/report.pdf"],
    html_body=True,
)
email.send()
```

## Dry-Run Preview

Preview the full email without sending:

```python
print(email.send(dry_run=True))  # same as email.display()
```

## Multipart Email (HTML + Plain Text Fallback)

When `html_body=True` and `plain_body` is provided, the message is sent as
`multipart/alternative` so clients that cannot render HTML show the plain-text version:

```python
email.create(
    subject="Report",
    recipients=["user@example.com"],
    body="<h1>Report</h1>",
    html_body=True,
    plain_body="Report — see the HTML version for formatting.",
)
```

## Threading

Link replies to existing threads using standard email headers:

```python
email.create(
    subject="Re: Question",
    recipients=["user@example.com"],
    body="Following up.",
    in_reply_to="<original-message-id@example.com>",
    references=["<original-message-id@example.com>"],
)
```

## Priority

```python
email.create(
    subject="URGENT",
    recipients=["user@example.com"],
    body="Please respond ASAP.",
    priority="high",   # "high", "normal", or "low"
)
```

## List-Unsubscribe header

Gmail and Yahoo require a `List-Unsubscribe` header for bulk senders (policy
effective February 2024). Pass `unsubscribe_url=` on `create()` — FluxMail adds
both the `List-Unsubscribe` and `List-Unsubscribe-Post` headers required for
RFC 8058 one-click unsubscribe. The URL must use `https://`:

```python
email.create(
    subject="Monthly Newsletter",
    recipients=["subscriber@example.com"],
    body="...",
    unsubscribe_url="https://myapp.com/unsubscribe?token=abc123",
)
```

This generates:
```
List-Unsubscribe: <https://myapp.com/unsubscribe?token=abc123>
List-Unsubscribe-Post: List-Unsubscribe=One-Click
```

## Inline images (CID attachments)

Embed images directly in HTML email bodies using Content-ID references.
`inline_images` maps a CID name to a file path; the body references them
as `cid:<name>`. Requires `html_body=True`.

```python
email.create(
    subject="Welcome to Acme",
    recipients=["user@example.com"],
    body="""
        <h1><img src="cid:logo" alt="Acme"> Welcome!</h1>
        <p>Thanks for joining us.</p>
    """,
    html_body=True,
    inline_images={
        "logo": "/path/to/acme-logo.png",
    },
)
```

The images are attached with `Content-Disposition: inline` inside a
`multipart/related` structure (RFC 2387), which major clients render
inline rather than as attachments.

## CSS inlining

Most email clients (Outlook desktop, older Gmail) strip `<style>` tags.
Pass `inline_css=True` to automatically inline all CSS rules into element
`style` attributes before sending, via [premailer](https://github.com/peterbe/premailer):

```python
email.create(
    subject="Styled newsletter",
    recipients=["user@example.com"],
    body="""
        <style>h1 { color: #2563eb; } p { font-size: 14px; }</style>
        <h1>Hello</h1>
        <p>This email renders correctly everywhere.</p>
    """,
    html_body=True,
    inline_css=True,
)
```

`inline_css=True` is silently ignored when `html_body=False` (no-op on plain text).

## Connection Reuse

Use `FluxMail` as a context manager to hold one SMTP connection open across
multiple sends — useful for bulk operations:

```python
with FluxMail(object_type="smtp", host="smtp.gmail.com", port=587, use_tls=True,
               username="me@gmail.com", password="secret") as mailer:
    for recipient in recipients:
        mailer.create(subject="Hi", recipients=[recipient], body="Hello").send()
```

## Factory from environment variables

`from_env()` reads all connection settings from `FLUXMAIL_*` environment variables,
removing boilerplate from every deployment context (Docker, CI/CD, serverless, Heroku):

```python
import os
from fluxmail import FluxMail

# Set once in your environment / .env file / secret manager:
# FLUXMAIL_HOST=smtp.gmail.com
# FLUXMAIL_PORT=587
# FLUXMAIL_TLS=true
# FLUXMAIL_USERNAME=me@gmail.com
# FLUXMAIL_PASSWORD=secret

mailer = FluxMail.from_env()
mailer.create(subject="Hello", recipients=["user@example.com"], body="Hi!").send()
```

| Env var | Default | Notes |
|---|---|---|
| `FLUXMAIL_TYPE` | `smtp` | `smtp` or `outlook` |
| `FLUXMAIL_HOST` | — | Required when type is `smtp` |
| `FLUXMAIL_PORT` | `25` | |
| `FLUXMAIL_USERNAME` | — | Same var read by the CLI |
| `FLUXMAIL_PASSWORD` | — | Same var read by the CLI |
| `FLUXMAIL_TLS` | `false` | `true`/`1`/`yes` → `True` |
| `FLUXMAIL_SSL` | `false` | Implicit TLS (port 465) |
| `FLUXMAIL_TIMEOUT` | `30` | Seconds |
| `FLUXMAIL_MAX_RETRIES` | `0` | |
| `FLUXMAIL_RETRY_DELAY` | `1.0` | Seconds |

## Implicit TLS (port 465)

Some providers use implicit TLS on port 465 instead of STARTTLS on port 587.
Use `use_ssl=True` instead of `use_tls=True`:

```python
FluxMail(
    object_type="smtp",
    host="smtp.example.com",
    port=465,
    use_ssl=True,   # implicit TLS — cannot be combined with use_tls=True
    username="me@example.com",
    password="secret",
)
```

## Connection Timeout and Retry

Control the SMTP connection timeout (default `30` seconds) and automatic retry
for transient failures:

```python
FluxMail(
    object_type="smtp",
    host="smtp.gmail.com",
    port=587,
    use_tls=True,
    timeout=15,        # fail after 15 s if server is unresponsive
    max_retries=3,     # retry up to 3 times after the first attempt
    retry_delay=2.0,   # wait 2 seconds between retries
    username=os.environ["FLUXMAIL_USERNAME"],
    password=os.environ["FLUXMAIL_PASSWORD"],
)
```

After all retries are exhausted, `FluxMailException` is raised with the original
error preserved via exception chaining.

## Connection health check

`test_connection()` opens an SMTP connection, authenticates, and returns a
diagnostics dict — without sending any email. Use it in application startup,
health endpoints, or to diagnose credential issues before going to production:

```python
try:
    result = mailer.test_connection()
    print(result)
    # {"ok": True, "relay": "smtp.gmail.com", "port": 587, "latency_ms": 43}
except FluxMailException as e:
    print(f"SMTP unreachable: {e}")  # e.code == "connection_failed"
```

## Async Send

`send_async()` is the async equivalent of `send()`. Use it inside `async` functions
with any async framework (asyncio, FastAPI, Django async views, etc.):

```python
import asyncio
import os
from fluxmail import FluxMail

async def main():
    email = FluxMail(
        object_type="smtp",
        host="smtp.gmail.com",
        port=587,
        use_tls=True,
        username=os.environ["FLUXMAIL_USERNAME"],
        password=os.environ["FLUXMAIL_PASSWORD"],
    )
    email.create(
        subject="Async notification",
        recipients=["user@example.com"],
        body="Sent with send_async().",
    )
    result = await email.send_async()
    print(result)  # "Email sent successfully via SMTP."

asyncio.run(main())
```

`send_async()` accepts `dry_run=True` for previews. Retry (`max_retries`) is
**not** applied to async sends — handle retries in the caller if needed.

## Email Templates

`EmailTemplate` renders [Jinja2](https://jinja.palletsprojects.com/) templates so
you can separate email content from code:

```python
from fluxmail import FluxMail, EmailTemplate

tmpl = EmailTemplate(
    "Hello {{ name }},\n\nYour order #{{ order_id }} has shipped."
)

body = tmpl.render(name="Alice", order_id=12345)

FluxMail(
    object_type="smtp",
    host="smtp.gmail.com",
    port=587,
    use_tls=True,
    username=os.environ["FLUXMAIL_USERNAME"],
    password=os.environ["FLUXMAIL_PASSWORD"],
).create(
    subject="Your order has shipped",
    recipients=["alice@example.com"],
    body=body,
).send()
```

### Load a template from a file

```python
# templates/welcome.html
# <h1>Welcome, {{ first_name }}!</h1>
# <p>Thanks for joining {{ company }}.</p>

tmpl = EmailTemplate.from_file("templates/welcome.html", autoescape=True)
body = tmpl.render(first_name="Bob", company="Acme Corp")
```

`autoescape=True` HTML-escapes all variables — use this for HTML emails to prevent
injection. The default is `False` (safe for plain-text templates).

### Inline template for HTML email

```python
html_tmpl = EmailTemplate(
    """
    <h2>Monthly Report — {{ month }}</h2>
    <p>Total sent: <strong>{{ count }}</strong></p>
    """,
    autoescape=True,
)

email.create(
    subject=f"Report for {month}",
    recipients=["manager@example.com"],
    body=html_tmpl.render(month="May 2026", count=4821),
    html_body=True,
)
```

## Bulk Sending

`BulkSender` opens one SMTP connection and sends a batch of messages over it,
which is significantly faster than reconnecting for each email:

```python
import os
from fluxmail import FluxMail, BulkSender

mailer = FluxMail(
    object_type="smtp",
    host="smtp.gmail.com",
    port=587,
    use_tls=True,
    username=os.environ["FLUXMAIL_USERNAME"],
    password=os.environ["FLUXMAIL_PASSWORD"],
)

messages = [
    {"subject": f"Hi {name}", "recipients": [email], "body": f"Hello {name}!"}
    for name, email in [("Alice", "alice@example.com"), ("Bob", "bob@example.com")]
]

result = BulkSender(mailer).send_batch(messages)
print(result)
# {"sent": 2, "failed": 0, "total": 2, "errors": []}
```

A Rich progress bar is shown by default. Pass `progress=False` to suppress it.

### Callbacks and error handling

```python
def on_success(index: int, result: str) -> None:
    print(f"[{index}] sent: {result}")

def on_error(index: int, exc: FluxMailException) -> None:
    print(f"[{index}] FAILED ({exc.code}): {exc}")

result = BulkSender(mailer).send_batch(
    messages,
    on_success=on_success,
    on_error=on_error,
    progress=False,
)

# Inspect failures after the batch
for idx, exc in result["errors"]:
    print(f"Message {idx} failed: {exc}")
```

### BulkSender + templates

Combine `EmailTemplate` with `BulkSender` for personalised batch emails:

```python
from fluxmail import FluxMail, BulkSender, EmailTemplate

tmpl = EmailTemplate("Hi {{ name }}, your balance is {{ balance }}.")

subscribers = [
    {"name": "Alice", "email": "alice@example.com", "balance": "$120.00"},
    {"name": "Bob",   "email": "bob@example.com",   "balance": "$45.00"},
]

messages = [
    {
        "subject": "Your account balance",
        "recipients": [sub["email"]],
        "body": tmpl.render(name=sub["name"], balance=sub["balance"]),
    }
    for sub in subscribers
]

BulkSender(mailer).send_batch(messages)
```

### Async bulk sending

`send_batch_async()` is the async equivalent — it holds one persistent async SMTP
connection for the entire batch. Add `max_per_second` to respect ESP rate limits:

```python
import asyncio
import os
from fluxmail import FluxMail, BulkSender

mailer = FluxMail(
    object_type="smtp",
    host="smtp.sendgrid.net",
    port=587,
    use_tls=True,
    username="apikey",
    password=os.environ["SENDGRID_API_KEY"],
    sender="noreply@myapp.com",
)

messages = [
    {"subject": f"Hi {name}", "recipients": [email], "body": f"Hello {name}!"}
    for name, email in subscribers
]

async def send():
    result = await BulkSender(mailer).send_batch_async(
        messages,
        max_per_second=14,  # SES limit; 0 = no throttle (default)
        progress=False,
    )
    print(f"{result['sent']} sent, {result['failed']} failed")

asyncio.run(send())
```

## Django integration

Use FluxMail as a drop-in replacement for Django's email backend by setting
`EMAIL_BACKEND` in your Django settings:

```python
# settings.py
EMAIL_BACKEND = "fluxmail.backends.django.FluxMailBackend"
EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_HOST_USER = "me@gmail.com"
EMAIL_HOST_PASSWORD = "secret"
EMAIL_USE_TLS = True
EMAIL_TIMEOUT = 30

# Optional FluxMail-specific settings
EMAIL_FLUXMAIL_MAX_RETRIES = 3
EMAIL_FLUXMAIL_RETRY_DELAY = 1.0
```

With this in place, all of Django's standard email functions work through FluxMail:

```python
from django.core.mail import send_mail, send_mass_mail, EmailMultiAlternatives

# Plain send_mail
send_mail("Subject", "Body", "from@example.com", ["to@example.com"])

# HTML email via EmailMultiAlternatives
msg = EmailMultiAlternatives(
    subject="Newsletter",
    body="Plain text version",
    from_email="news@example.com",
    to=["user@example.com"],
)
msg.attach_alternative("<h1>HTML version</h1>", "text/html")
msg.send()
```

The backend reads Django's standard `EMAIL_*` settings and delegates message
construction to Django's own MIME builder, so attachments, multipart, and all
Django email features work unchanged.

!!! note "Thread safety"
    The backend uses a single `FluxMail` instance per backend object. Do not
    share a single backend instance across concurrent threads without external
    synchronisation.

## Outlook

!!! warning "Windows only"
    Outlook requires the desktop app to be installed and running on Windows.
    Using `EmailObject.OUTLOOK` on Linux or macOS raises `FluxMailException`.

```python
from fluxmail import FluxMail, EmailInstance, EmailObject

email = FluxMail(object_type=EmailObject.OUTLOOK, host=EmailInstance(relay=""))
email.create(
    subject="Project Update",
    recipients=["user@example.com"],
    body="Please find the update below.",
    cc=["manager@example.com"],
    attachments=["/path/to/report.pdf"],
)
# Opens the Outlook compose window — user must click Send manually
email.display()
```

!!! note "Sending"
    Outlook cannot send programmatically. Calling `send()` on an Outlook
    instance raises `FluxMailException`. Use `display()` to open the compose
    window and let the user confirm the send.

!!! note "Sender"
    Outlook controls the sender address. Passing `sender=` raises
    `FluxMailException`.

!!! note "Reply-To"
    SMTP only. Outlook's COM interface does not expose a Reply-To field.

!!! note "BCC"
    Works on both SMTP and Outlook.

## Error Handling

!!! tip
    Chain `.send()` directly onto `.create()` to keep script logic concise — both
    raise `FluxMailException` on failure, so a single `try/except` covers both.

```python
from fluxmail import FluxMail, FluxMailException

try:
    FluxMail(object_type="smtp", host="smtp.gmail.com", port=587, use_tls=True,
              username="me@gmail.com", password="secret").create(
        subject="Test",
        recipients=["user@example.com"],
        body="Hello",
    ).send()
except FluxMailException as e:
    print(f"Email failed: {e}")
```
