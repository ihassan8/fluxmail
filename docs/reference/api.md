# API Reference

## `FluxMail`

::: fluxmail.fluxmail.FluxMail

---

### Constructor

```python
FluxMail(
    object_type,
    host,
    port=25,
    use_tls=False,
    username=None,
    password=None,
    sender=None,
    log_level="WARNING",
    logger=None,
)
```

**Parameters**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `object_type` | `str \| EmailObject` | — | `"smtp"` or `"outlook"` (or `EmailObject.SMTP` / `EmailObject.OUTLOOK`) |
| `host` | `str \| EmailInstance` | — | Relay hostname string, `"relay:domain"` shorthand, or `EmailInstance` |
| `port` | `int` | `25` | SMTP port. Use `587` for STARTTLS. |
| `use_tls` | `bool` | `False` | Enable STARTTLS negotiation |
| `username` | `str \| None` | `None` | SMTP login username. When a valid email, doubles as the `From` address. |
| `password` | `str \| None` | `None` | SMTP login password |
| `sender` | `str \| None` | `None` | Explicit `From` address. Overrides `username`. |
| `log_level` | `str` | `"WARNING"` | Logging level: `"DEBUG"`, `"INFO"`, `"WARNING"`, `"ERROR"` |
| `logger` | `logging.Logger \| None` | `None` | Supply a custom logger instance |

=== "Gmail (username as sender)"

    ```python
    from fluxmail import FluxMail

    email = FluxMail(
        object_type="smtp",
        host="smtp.gmail.com",
        port=587,
        use_tls=True,
        username="me@gmail.com",
        password="secret",
    )
    ```

=== "SendGrid (explicit sender)"

    ```python
    from fluxmail import FluxMail

    email = FluxMail(
        object_type="smtp",
        host="smtp.sendgrid.net",
        port=587,
        use_tls=True,
        username="apikey",
        password="SG.xxxx",
        sender="noreply@myapp.com",
    )
    ```

=== "Amazon SES"

    ```python
    from fluxmail import FluxMail

    email = FluxMail(
        object_type="smtp",
        host="email-smtp.us-east-1.amazonaws.com",
        port=587,
        use_tls=True,
        username="AKIAIOSFODNN7EXAMPLE",
        password="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        sender="noreply@myapp.com",
    )
    ```

=== "Office 365"

    ```python
    from fluxmail import FluxMail

    email = FluxMail(
        object_type="smtp",
        host="smtp.office365.com",
        port=587,
        use_tls=True,
        username="me@mycompany.com",
        password="secret",
    )
    ```

=== "Self-hosted relay"

    ```python
    from fluxmail import FluxMail, EmailInstance

    email = FluxMail(
        object_type="smtp",
        host=EmailInstance(relay="mail.mycompany.com", domain="mycompany.com"),
        port=25,
        username="noreply@mycompany.com",
    )
    ```

=== "Outlook (Windows)"

    ```python
    from fluxmail import FluxMail, EmailInstance, EmailObject

    email = FluxMail(
        object_type=EmailObject.OUTLOOK,
        host=EmailInstance(relay=""),
    )
    ```

---

### `create()`

Build the email message. Returns `self` for method chaining.

```python
create(
    subject,
    recipients,
    body,
    sender=None,
    cc=None,
    bcc=None,
    attachments=None,
    html_body=False,
    plain_body=None,
    reply_to=None,
    in_reply_to=None,
    references=None,
    priority=None,
)
```

**Parameters**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `subject` | `str` | — | Email subject line |
| `recipients` | `List[str]` | — | One or more `To` addresses |
| `body` | `str` | — | Email body — plain text or HTML string |
| `sender` | `str \| None` | `None` | Override the `From` address set on the constructor |
| `cc` | `List[str] \| None` | `None` | CC addresses |
| `bcc` | `List[str] \| None` | `None` | BCC addresses |
| `attachments` | `List[str] \| None` | `None` | File paths to attach (MIME type auto-detected) |
| `html_body` | `bool` | `False` | Treat `body` as HTML |
| `plain_body` | `str \| None` | `None` | Plain-text fallback when `html_body=True` (sends `multipart/alternative`) |
| `reply_to` | `str \| None` | `None` | `Reply-To` header (SMTP only) |
| `in_reply_to` | `str \| None` | `None` | `In-Reply-To` header for threading |
| `references` | `List[str] \| None` | `None` | `References` header for threading |
| `priority` | `str \| None` | `None` | `"high"`, `"normal"`, or `"low"` |

=== "Plain text"

    ```python
    email.create(
        subject="Hello",
        recipients=["friend@example.com"],
        body="Hi there!",
    )
    ```

=== "HTML body"

    ```python
    email.create(
        subject="Newsletter",
        recipients=["user@example.com"],
        body="<h1>Hello</h1><p>Welcome to the newsletter.</p>",
        html_body=True,
    )
    ```

=== "HTML + plain-text fallback"

    ```python
    email.create(
        subject="Report",
        recipients=["user@example.com"],
        body="<h1>Monthly Report</h1><p>See figures below.</p>",
        html_body=True,
        plain_body="Monthly Report — open in an HTML-capable client for formatting.",
    )
    ```

=== "Attachments + CC/BCC"

    ```python
    email.create(
        subject="Q1 Summary",
        recipients=["alice@example.com", "bob@example.com"],
        body="Q1 summary is attached.",
        cc=["manager@example.com"],
        bcc=["archive@example.com"],
        attachments=["/path/to/q1-summary.pdf", "/path/to/charts.xlsx"],
    )
    ```

=== "Threading"

    ```python
    email.create(
        subject="Re: Original Subject",
        recipients=["user@example.com"],
        body="Following up on your question.",
        in_reply_to="<original-message-id@example.com>",
        references=["<original-message-id@example.com>"],
    )
    ```

=== "Priority"

    ```python
    email.create(
        subject="URGENT: Action required",
        recipients=["user@example.com"],
        body="Please respond by end of day.",
        priority="high",   # "high", "normal", or "low"
    )
    ```

=== "Reply-To"

    ```python
    email.create(
        subject="Do not reply to this address",
        recipients=["user@example.com"],
        body="Reply to the address below.",
        reply_to="support@myapp.com",
    )
    ```

---

### `send()`

Send the email. Returns `self`.

```python
send(dry_run=False)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `dry_run` | `bool` | `False` | If `True`, returns a preview string without sending (delegates to `display()`) |

=== "Normal send"

    ```python
    email.create(subject="Hi", recipients=["user@example.com"], body="Hello").send()
    ```

=== "Chained"

    ```python
    from fluxmail import FluxMail

    FluxMail(
        object_type="smtp",
        host="smtp.gmail.com",
        port=587,
        use_tls=True,
        username="me@gmail.com",
        password="secret",
    ).create(
        subject="Hello",
        recipients=["friend@example.com"],
        body="Hi there!",
    ).send()
    ```

=== "Dry-run"

    ```python
    preview = email.send(dry_run=True)
    print(preview)
    ```

---

### `display()`

Return an email preview string (SMTP), or open the Outlook compose window (Outlook).

```python
display()
```

=== "SMTP preview"

    ```python
    email.create(subject="Hi", recipients=["user@example.com"], body="Hello")
    print(email.display())
    ```

=== "Outlook compose window"

    ```python
    # Opens Outlook's compose window — user must click Send manually.
    email.create(
        subject="Project Update",
        recipients=["user@example.com"],
        body="Please find the update below.",
    )
    email.display()
    ```

---

### `is_smtp()` / `is_outlook()`

Convenience predicates for the configured protocol.

```python
email = FluxMail(object_type="smtp", host="smtp.gmail.com", ...)
email.is_smtp()    # True
email.is_outlook() # False
```

---

### Context manager — connection reuse

Use `FluxMail` as a context manager to hold one SMTP connection open across multiple sends.
Useful for bulk sends where opening a new connection per message would be slow.

=== "Bulk send"

    ```python
    from fluxmail import FluxMail

    recipients = ["a@example.com", "b@example.com", "c@example.com"]

    with FluxMail(
        object_type="smtp",
        host="smtp.gmail.com",
        port=587,
        use_tls=True,
        username="me@gmail.com",
        password="secret",
    ) as mailer:
        for recipient in recipients:
            mailer.create(
                subject="Hello",
                recipients=[recipient],
                body="Hi there!",
            ).send()
    ```

=== "With error handling"

    ```python
    from fluxmail import FluxMail, FluxMailException

    with FluxMail(object_type="smtp", host="smtp.gmail.com", port=587,
                   use_tls=True, username="me@gmail.com", password="secret") as mailer:
        for recipient in recipients:
            try:
                mailer.create(subject="Hi", recipients=[recipient], body="Hello").send()
            except FluxMailException as e:
                print(f"Failed to send to {recipient}: {e}")
    ```

---

## `EmailInstance`

A `namedtuple` representing an SMTP relay configuration.

```python
EmailInstance(relay, domain="")
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `relay` | `str` | — | Hostname of the SMTP relay (e.g. `smtp.gmail.com`) |
| `domain` | `str` | `""` | Email domain for the relay (e.g. `gmail.com`). Optional. |

=== "Relay only"

    ```python
    from fluxmail import EmailInstance

    host = EmailInstance(relay="smtp.gmail.com")
    ```

=== "Relay + domain"

    ```python
    from fluxmail import EmailInstance

    host = EmailInstance(relay="smtp.myrelay.net", domain="mycompany.com")
    ```

=== "In constructor"

    ```python
    from fluxmail import FluxMail, EmailInstance

    email = FluxMail(
        object_type="smtp",
        host=EmailInstance(relay="smtp.myrelay.net", domain="mycompany.com"),
        port=587,
        use_tls=True,
        username="me@mycompany.com",
    )
    ```

::: fluxmail.utils.EmailInstance

---

## Host formats

`host` on the `FluxMail` constructor accepts three forms:

=== "Bare string"

    ```python
    # relay hostname only — domain defaults to ""
    FluxMail(object_type="smtp", host="smtp.gmail.com", ...)
    ```

=== "relay:domain string"

    ```python
    # CLI-friendly shorthand
    FluxMail(object_type="smtp", host="smtp.gmail.com:gmail.com", ...)
    ```

=== "EmailInstance"

    ```python
    from fluxmail import EmailInstance

    FluxMail(object_type="smtp", host=EmailInstance(relay="smtp.myrelay.net", domain="mycompany.com"), ...)
    ```

---

## `EmailObject`

::: fluxmail.utils.EmailObject

```python
from fluxmail import EmailObject

FluxMail(object_type=EmailObject.SMTP, ...)
FluxMail(object_type=EmailObject.OUTLOOK, ...)

# String aliases also work:
FluxMail(object_type="smtp", ...)
FluxMail(object_type="outlook", ...)
```

---

## `FluxMailException`

::: fluxmail.utils.FluxMailException

All errors raised by FluxMail are `FluxMailException` instances. A single `try/except` covers
both `create()` and `send()`:

=== "Basic error handling"

    ```python
    from fluxmail import FluxMail, FluxMailException

    try:
        FluxMail(
            object_type="smtp",
            host="smtp.gmail.com",
            port=587,
            use_tls=True,
            username="me@gmail.com",
            password="secret",
        ).create(
            subject="Test",
            recipients=["user@example.com"],
            body="Hello",
        ).send()
    except FluxMailException as e:
        print(f"Email failed: {e}")
    ```

=== "Missing sender"

    ```python
    # SendGrid uses "apikey" as username — not a valid email address.
    # Pass sender= explicitly or FluxMailException is raised.
    from fluxmail import FluxMail, FluxMailException

    try:
        FluxMail(
            object_type="smtp",
            host="smtp.sendgrid.net",
            port=587,
            use_tls=True,
            username="apikey",
            password="SG.xxxx",
            # sender= required here
        ).create(subject="Hi", recipients=["user@example.com"], body="Hello").send()
    except FluxMailException as e:
        print(e)  # "sender is required. Pass sender= explicitly..."
    ```

=== "Invalid recipient"

    ```python
    from fluxmail import FluxMail, FluxMailException

    try:
        email.create(subject="Hi", recipients=["not-an-email"], body="Hello")
    except FluxMailException as e:
        print(f"Validation error: {e}")
    ```

=== "Outlook on non-Windows"

    ```python
    from fluxmail import FluxMail, EmailInstance, EmailObject, FluxMailException

    try:
        FluxMail(
            object_type=EmailObject.OUTLOOK,
            host=EmailInstance(relay=""),
        ).create(subject="Hi", recipients=["user@example.com"], body="Hello").send()
    except FluxMailException as e:
        print(e)  # "Outlook is not supported on this platform."
    ```

---

## Full examples

=== "Gmail"

    ```python
    import os
    from fluxmail import FluxMail

    FluxMail(
        object_type="smtp",
        host="smtp.gmail.com",
        port=587,
        use_tls=True,
        username=os.environ["FLUXMAIL_USERNAME"],
        password=os.environ["FLUXMAIL_PASSWORD"],
    ).create(
        subject="Hello from FluxMail",
        recipients=["friend@example.com"],
        body="Hi there!",
    ).send()
    ```

=== "SendGrid"

    ```python
    import os
    from fluxmail import FluxMail

    FluxMail(
        object_type="smtp",
        host="smtp.sendgrid.net",
        port=587,
        use_tls=True,
        username="apikey",
        password=os.environ["SENDGRID_API_KEY"],
        sender="noreply@myapp.com",
    ).create(
        subject="Your order has shipped",
        recipients=["customer@example.com"],
        body="<h1>Order Shipped</h1><p>Your order is on its way.</p>",
        html_body=True,
        plain_body="Your order is on its way.",
    ).send()
    ```

=== "Bulk send"

    ```python
    import os
    from fluxmail import FluxMail

    subscribers = ["alice@example.com", "bob@example.com", "carol@example.com"]

    with FluxMail(
        object_type="smtp",
        host="smtp.gmail.com",
        port=587,
        use_tls=True,
        username=os.environ["FLUXMAIL_USERNAME"],
        password=os.environ["FLUXMAIL_PASSWORD"],
    ) as mailer:
        for email_addr in subscribers:
            mailer.create(
                subject="Monthly Newsletter",
                recipients=[email_addr],
                body="<h1>Newsletter</h1>",
                html_body=True,
            ).send()
    ```

=== "Full options"

    ```python
    import os
    from fluxmail import FluxMail

    email = FluxMail(
        object_type="smtp",
        host="smtp.gmail.com",
        port=587,
        use_tls=True,
        username=os.environ["FLUXMAIL_USERNAME"],
        password=os.environ["FLUXMAIL_PASSWORD"],
    )
    email.create(
        subject="Monthly Report",
        recipients=["alice@example.com", "bob@example.com"],
        body="<h1>Report</h1><p>See attached.</p>",
        html_body=True,
        plain_body="Monthly report — see attached.",
        sender="reports@myapp.com",
        cc=["manager@example.com"],
        bcc=["archive@example.com"],
        attachments=["/path/to/report.pdf"],
        reply_to="noreply@myapp.com",
        priority="high",
    )
    email.send()
    ```
