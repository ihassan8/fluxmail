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

## Connection Reuse

Use `FluxMail` as a context manager to hold one SMTP connection open across
multiple sends — useful for bulk operations:

```python
with FluxMail(object_type="smtp", host="smtp.gmail.com", port=587, use_tls=True,
               username="me@gmail.com", password="secret") as mailer:
    for recipient in recipients:
        mailer.create(subject="Hi", recipients=[recipient], body="Hello").send()
```

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
