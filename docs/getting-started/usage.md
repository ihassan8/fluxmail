# Python API

## Basic Send

```python
from autoemail import AutoEmail, EmailEnv, EmailObject

email = AutoEmail(object_type=EmailObject.SMTP, host=EmailEnv.Domain1)
email.create(
    subject="Project Update",
    recipients=["user@hr.acme.com"],
    body="Please find the latest update below.",
).send()
```

## Method Chaining

`create()` returns `self`, enabling a single-expression send:

```python
from autoemail import AutoEmail, EmailEnv, EmailObject

AutoEmail(object_type=EmailObject.SMTP, host=EmailEnv.Domain1).create(
    subject="Quick Note",
    recipients=["user@hr.acme.com"],
    body="Hi",
).send()
```

## Full Options

```python
from autoemail import AutoEmail, EmailEnv, EmailObject

email = AutoEmail(object_type=EmailObject.SMTP, host=EmailEnv.Domain1)
email.create(
    subject="Monthly Report",
    recipients=["alice@hr.acme.com", "bob@hr.acme.com"],
    body="<h1>Report</h1><p>See attached.</p>",
    sender="reports@hr.acme.com",
    cc=["manager@hr.acme.com"],
    bcc=["archive@hr.acme.com"],
    attachments=["/path/to/report.pdf"],
    html_body=True,
)
email.send()
```

## Custom Relay

Use any external SMTP server without modifying the library:

```python
from autoemail import AutoEmail, EmailInstance

custom = EmailInstance(relay="smtp.gmail.com", domain="gmail.com")
email = AutoEmail(
    object_type="smtp",
    host=custom,
    port=587,
    use_tls=True,
    username="me@gmail.com",
    password="secret",  # (1)!
)
email.create(
    subject="Hello",
    recipients=["friend@example.com"],
    body="Test message",
).send()
```

1. Load credentials from an environment variable or secrets manager — never hardcode them in source.

## Dry-Run Preview

Preview the full email without sending — useful for verifying recipients and content:

```python
from autoemail import AutoEmail, EmailEnv

email = AutoEmail(object_type="smtp", host=EmailEnv.Domain1)
email.create(
    subject="Test",
    recipients=["user@hr.acme.com"],
    body="Hello",
)

print(email.send(dry_run=True))  # same as email.display()
```

## Outlook

!!! warning "Windows only"
    Outlook requires the desktop app to be installed and running on Windows.
    Using `EmailObject.OUTLOOK` on Linux or macOS raises `AutoEmailException`.

```python
from autoemail import AutoEmail, EmailEnv, EmailObject

email = AutoEmail(object_type=EmailObject.OUTLOOK, host=EmailEnv.Domain1)
email.create(
    subject="Project Update",
    recipients=["user@hr.acme.com"],
    body="Please find the update below.",
    cc=["manager@hr.acme.com"],
    attachments=["/path/to/report.pdf"],
)
# Opens the Outlook compose window — user must click Send manually
email.display()
```

!!! note "Sending"
    Outlook cannot send programmatically. Calling `send()` on an Outlook
    instance raises `AutoEmailException`. Use `display()` to open the compose
    window and let the user confirm the send.

!!! note "Sender"
    Outlook controls the sender address. Passing `sender=` raises
    `AutoEmailException`.

!!! note "Reply-To"
    SMTP only. Outlook's COM interface does not expose a Reply-To field.

!!! note "BCC"
    Works on both SMTP and Outlook.

## Multipart Email (HTML + Plain Text Fallback)

When `html_body=True` and `plain_body` is provided, the message is sent as
`multipart/alternative` so clients that cannot render HTML show the plain-text version:

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

Link replies to existing threads using standard email headers:

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

Use `AutoEmail` as a context manager to hold one SMTP connection open across
multiple sends — useful for bulk operations:

```python
with AutoEmail(object_type="smtp", host=EmailEnv.Domain1) as mailer:
    for recipient in recipients:
        mailer.create(subject="Hi", recipients=[recipient], body="Hello").send()
```

## Error Handling

!!! tip
    Chain `.send()` directly onto `.create()` to keep script logic concise — both
    raise `AutoEmailException` on failure, so a single `try/except` covers both.

```python
from autoemail import AutoEmail, EmailEnv, AutoEmailException

try:
    AutoEmail(object_type="smtp", host=EmailEnv.Domain1).create(
        subject="Test",
        recipients=["user@hr.acme.com"],
        body="Hello",
    ).send()
except AutoEmailException as e:
    print(f"Email failed: {e}")
```
