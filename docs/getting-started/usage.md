# Python API

## Basic Send

Pass the relay hostname as a string and set `username` — it doubles as the `From` address:

```python
from autoemail import AutoEmail

email = AutoEmail(
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
from autoemail import AutoEmail

email = AutoEmail(
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
from autoemail import AutoEmail, EmailInstance

relay = EmailInstance(relay="smtp.myrelay.net", domain="mycompany.com")
email = AutoEmail(object_type="smtp", host=relay, username="me@mycompany.com")
email.create(subject="Hi", recipients=["user@mycompany.com"], body="Hello").send()
```

## Method Chaining

`create()` returns `self`, enabling a single-expression send:

```python
AutoEmail(object_type="smtp", host="smtp.gmail.com", port=587, use_tls=True,
          username="me@gmail.com", password="secret").create(
    subject="Quick Note",
    recipients=["friend@example.com"],
    body="Hi",
).send()
```

## Full Options

```python
from autoemail import AutoEmail

email = AutoEmail(object_type="smtp", host="smtp.gmail.com", port=587, use_tls=True,
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

Use `AutoEmail` as a context manager to hold one SMTP connection open across
multiple sends — useful for bulk operations:

```python
with AutoEmail(object_type="smtp", host="smtp.gmail.com", port=587, use_tls=True,
               username="me@gmail.com", password="secret") as mailer:
    for recipient in recipients:
        mailer.create(subject="Hi", recipients=[recipient], body="Hello").send()
```

## Outlook

!!! warning "Windows only"
    Outlook requires the desktop app to be installed and running on Windows.
    Using `EmailObject.OUTLOOK` on Linux or macOS raises `AutoEmailException`.

```python
from autoemail import AutoEmail, EmailInstance, EmailObject

email = AutoEmail(object_type=EmailObject.OUTLOOK, host=EmailInstance(relay=""))
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
    instance raises `AutoEmailException`. Use `display()` to open the compose
    window and let the user confirm the send.

!!! note "Sender"
    Outlook controls the sender address. Passing `sender=` raises
    `AutoEmailException`.

!!! note "Reply-To"
    SMTP only. Outlook's COM interface does not expose a Reply-To field.

!!! note "BCC"
    Works on both SMTP and Outlook.

## Error Handling

!!! tip
    Chain `.send()` directly onto `.create()` to keep script logic concise — both
    raise `AutoEmailException` on failure, so a single `try/except` covers both.

```python
from autoemail import AutoEmail, AutoEmailException

try:
    AutoEmail(object_type="smtp", host="smtp.gmail.com", port=587, use_tls=True,
              username="me@gmail.com", password="secret").create(
        subject="Test",
        recipients=["user@example.com"],
        body="Hello",
    ).send()
except AutoEmailException as e:
    print(f"Email failed: {e}")
```
