# Configuration

## Credentials via Environment Variables

The recommended way to pass SMTP credentials is through environment variables so
they never appear in shell history or source code:

```bash
export FLUXMAIL_USERNAME=me@gmail.com
export FLUXMAIL_PASSWORD=secret
```

These are read automatically by the CLI (`--username` and `--password` flags).
In Python, read them explicitly:

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
```

## `from_env()` factory

For fully environment-driven configuration, `FluxMail.from_env()` reads the
complete set of connection settings from `FLUXMAIL_*` environment variables.
Ideal for containers, Heroku, Lambda, and any twelve-factor app:

```bash
# .env or deployment secrets
FLUXMAIL_HOST=smtp.gmail.com
FLUXMAIL_PORT=587
FLUXMAIL_TLS=true
FLUXMAIL_USERNAME=me@gmail.com
FLUXMAIL_PASSWORD=secret
FLUXMAIL_TIMEOUT=15
FLUXMAIL_MAX_RETRIES=3
FLUXMAIL_RETRY_DELAY=2.0
```

```python
from fluxmail import FluxMail

# One line — no hardcoded connection params
mailer = FluxMail.from_env()
mailer.create(subject="Hi", recipients=["user@example.com"], body="Hello").send()
```

All env vars have sensible defaults. `FLUXMAIL_HOST` is the only required variable
when `FLUXMAIL_TYPE=smtp` (the default). `FLUXMAIL_TLS` and `FLUXMAIL_SSL` accept
`true`, `1`, or `yes` (case-insensitive).

## Host Formats

`host` accepts three forms:

| Form | Example | When to use |
|------|---------|-------------|
| Bare relay string | `"smtp.gmail.com"` | Most common — relay hostname only |
| `relay:domain` string | `"smtp.gmail.com:gmail.com"` | CLI shorthand when you want both relay and domain stored |
| `EmailInstance` namedtuple | `EmailInstance(relay="smtp.myrelay.net", domain="mycompany.com")` | Reusable host config in Python code |

```python
from fluxmail import FluxMail, EmailInstance

# Bare string — domain defaults to ""
FluxMail(object_type="smtp", host="smtp.gmail.com", ...)

# relay:domain string
FluxMail(object_type="smtp", host="smtp.gmail.com:gmail.com", ...)

# EmailInstance (domain is optional)
FluxMail(object_type="smtp", host=EmailInstance(relay="smtp.myrelay.net"), ...)
```

## Sender Resolution

`sender` in `create()` is determined in this order:

1. **Explicit `sender=`** — always wins.
2. **`username`** — used as the `From` address when it is a valid email address
   (e.g. `me@gmail.com`). Useful for Gmail, SES, Brevo, and others where your login is an email.
3. **Error** — if neither applies (e.g. SendGrid's `apikey` username or SMTP2Go's username token),
   `FluxMailException` is raised. Pass `sender=` explicitly in that case.

## TLS Modes

FluxMail supports two TLS modes for encrypted SMTP connections:

| Mode | Parameter | Port | How it works |
|------|-----------|------|--------------|
| **STARTTLS** | `use_tls=True` | 587 | Starts as plain text, upgrades to TLS via STARTTLS command |
| **Implicit TLS** | `use_ssl=True` | 465 | TLS from the first byte — uses `smtplib.SMTP_SSL` |

The two modes are mutually exclusive. Passing both raises `FluxMailException(code="invalid_config")`.

```python
# STARTTLS — most providers, port 587
FluxMail(object_type="smtp", host="smtp.gmail.com", port=587, use_tls=True, ...)

# Implicit TLS — port 465
FluxMail(object_type="smtp", host="smtp.example.com", port=465, use_ssl=True, ...)
```

### Custom SSL context

For self-signed certificates or custom CA bundles, pass an `ssl.SSLContext`:

```python
import ssl
from fluxmail import FluxMail

ctx = ssl.create_default_context()
ctx.load_verify_locations("/path/to/ca-bundle.crt")

FluxMail(
    object_type="smtp",
    host="mail.internal.corp",
    port=465,
    use_ssl=True,
    ssl_context=ctx,
    ...
)
```

To disable certificate verification entirely (development only — never in production):

```python
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
```

## Connection Settings

### Timeout

The default SMTP connection timeout is **30 seconds**. Adjust it with the `timeout` parameter:

```python
FluxMail(
    object_type="smtp",
    host="smtp.gmail.com",
    port=587,
    use_tls=True,
    timeout=10,   # fail fast — useful in latency-sensitive pipelines
    username=os.environ["FLUXMAIL_USERNAME"],
    password=os.environ["FLUXMAIL_PASSWORD"],
)
```

### Retry on failure

Transient SMTP errors (network blips, rate limits, temporary server failures) can be retried automatically:

```python
FluxMail(
    object_type="smtp",
    host="smtp.gmail.com",
    port=587,
    use_tls=True,
    max_retries=3,     # up to 3 retries after the first attempt
    retry_delay=2.0,   # 2-second pause between attempts
    username=os.environ["FLUXMAIL_USERNAME"],
    password=os.environ["FLUXMAIL_PASSWORD"],
)
```

After exhausting all retries, `FluxMailException(code="send_failed")` is raised with the last error message. Retry is applied to `send()` only — `send_async()` does not retry.

!!! tip "Retry + context manager"
    Combining `max_retries` with the context manager (`with FluxMail(...) as mailer:`) is the recommended pattern for production bulk sends: one persistent connection with automatic retry on each message.

## SMTP Providers

| Provider | Host | Port | Username | `sender=` required? | Free plan |
|----------|------|------|----------|----------------------|-----------|
| [Gmail](https://support.google.com/mail/answer/7126229) | `smtp.gmail.com` | 587 | your Gmail address | No — username is used | 500 emails/day |
| [SendGrid](https://docs.sendgrid.com/for-developers/sending-email/getting-started-smtp) | `smtp.sendgrid.net` | 587 | `apikey` | **Yes** | 100 emails/day (60 days) |
| [Brevo](https://help.brevo.com/hc/en-us/articles/209462765) | `smtp-relay.brevo.com` | 587 | your Brevo login email | No — username is used | 300 emails/day |
| [Mailjet](https://dev.mailjet.com/email/guides/send-with-smtp/) | `in-v3.mailjet.com` | 587 | API key | **Yes** | 200 emails/day |
| [MailerSend](https://www.mailersend.com/features/smtp-relay) | `smtp.mailersend.net` | 587 | `MS_USERNAME` token | **Yes** | 500 emails/month |
| [Mailtrap](https://help.mailtrap.io/article/79-sending-domain-setup) | `live.smtp.mailtrap.io` | 587 | API token | **Yes** | 1,000 emails/month |
| [SMTP2Go](https://support.smtp2go.com/hc/en-gb/articles/223087728) | `mail.smtp2go.com` | 587 | your SMTP2Go username | **Yes** | 1,000 emails/month |
| [SendPulse](https://sendpulse.com/integrations/smtp) | `smtp-pulse.com` | 587 | your SendPulse login | No — username is used | 12,000 emails/month |
| [Maileroo](https://maileroo.com/smtp-relay/) | `smtp.maileroo.com` | 587 | your Maileroo username | **Yes** | 3,000 emails/month |
| [Postmark](https://postmarkapp.com/developer/user-guide/send-email-with-smtp) | `smtp.postmarkapp.com` | 587 | server API token | **Yes** | 100 emails/month |
| [Elastic Email](https://elasticemail.com/developers/api-documentation/smtp-api) | `smtp.elasticemail.com` | 2525 | your account email | No — username is used | Free tier available |
| [Amazon SES](https://docs.aws.amazon.com/ses/latest/dg/send-email-smtp.html) | `email-smtp.<region>.amazonaws.com` | 587 | SMTP credentials (IAM) | **Yes** | Pay-per-use |
| [Mailgun](https://documentation.mailgun.com/docs/mailgun/user-manual/smtp/) | `smtp.mailgun.org` | 587 | `postmaster@<domain>` | No — username is used | Pay-per-use |
| Office 365 | `smtp.office365.com` | 587 | your O365 address | No — username is used | Microsoft 365 plan |
| Self-hosted | your relay hostname | 25 or 587 | varies | varies | — |

!!! tip "When is `sender=` required?"
    Providers that use an **API key or token** as the SMTP username (SendGrid, Mailjet,
    MailerSend, Mailtrap, SMTP2Go, Maileroo, Postmark, Amazon SES) require an explicit
    `sender=` argument because the username is not a valid email address. Providers where
    your login **is** an email address (Gmail, Brevo, SendPulse, Elastic Email, Mailgun,
    Office 365) automatically use it as the `From` address.

### Provider examples

=== "Gmail"

    ```python
    FluxMail(
        object_type="smtp",
        host="smtp.gmail.com",
        port=587,
        use_tls=True,
        username="me@gmail.com",       # also used as From
        password="app-password",
    )
    ```

    !!! note
        Gmail requires an [App Password](https://support.google.com/accounts/answer/185833)
        when 2-Step Verification is enabled. Your regular Gmail password will not work.

=== "SendGrid"

    ```python
    FluxMail(
        object_type="smtp",
        host="smtp.sendgrid.net",
        port=587,
        use_tls=True,
        username="apikey",             # literal string "apikey"
        password="SG.xxxx",            # your SendGrid API key
        sender="noreply@myapp.com",    # required — "apikey" is not an email
    )
    ```

=== "Brevo"

    ```python
    FluxMail(
        object_type="smtp",
        host="smtp-relay.brevo.com",
        port=587,
        use_tls=True,
        username="me@myapp.com",       # your Brevo login email
        password="brevo-smtp-key",     # SMTP key from Brevo dashboard
    )
    ```

=== "Mailjet"

    ```python
    FluxMail(
        object_type="smtp",
        host="in-v3.mailjet.com",
        port=587,
        use_tls=True,
        username="mailjet-api-key",
        password="mailjet-secret-key",
        sender="noreply@myapp.com",    # required — API key is not an email
    )
    ```

=== "MailerSend"

    ```python
    FluxMail(
        object_type="smtp",
        host="smtp.mailersend.net",
        port=587,
        use_tls=True,
        username="MS_xxxxxxxx",        # MailerSend SMTP username token
        password="mailersend-token",
        sender="noreply@myapp.com",    # required
    )
    ```

=== "Mailtrap"

    ```python
    FluxMail(
        object_type="smtp",
        host="live.smtp.mailtrap.io",
        port=587,
        use_tls=True,
        username="api",                # literal string "api"
        password="mailtrap-token",
        sender="noreply@myapp.com",    # required
    )
    ```

=== "SMTP2Go"

    ```python
    FluxMail(
        object_type="smtp",
        host="mail.smtp2go.com",
        port=587,
        use_tls=True,
        username="smtp2go-username",
        password="smtp2go-password",
        sender="noreply@myapp.com",    # required
    )
    ```

=== "SendPulse"

    ```python
    FluxMail(
        object_type="smtp",
        host="smtp-pulse.com",
        port=587,
        use_tls=True,
        username="me@myapp.com",       # your SendPulse login email
        password="sendpulse-password",
    )
    ```

=== "Postmark"

    ```python
    FluxMail(
        object_type="smtp",
        host="smtp.postmarkapp.com",
        port=587,
        use_tls=True,
        username="postmark-server-token",
        password="postmark-server-token",  # same value for both
        sender="noreply@myapp.com",        # required
    )
    ```

=== "Elastic Email"

    ```python
    FluxMail(
        object_type="smtp",
        host="smtp.elasticemail.com",
        port=2525,
        use_tls=True,
        username="me@myapp.com",       # your Elastic Email account email
        password="elastic-api-key",
    )
    ```

=== "Amazon SES"

    ```python
    FluxMail(
        object_type="smtp",
        host="email-smtp.us-east-1.amazonaws.com",  # replace with your region
        port=587,
        use_tls=True,
        username="AKIAIOSFODNN7EXAMPLE",   # SES SMTP credentials (not IAM key)
        password="ses-smtp-password",
        sender="noreply@myapp.com",        # required — must be a verified address
    )
    ```

=== "Mailgun"

    ```python
    FluxMail(
        object_type="smtp",
        host="smtp.mailgun.org",
        port=587,
        use_tls=True,
        username="postmaster@mg.myapp.com",  # also used as From
        password="mailgun-smtp-password",
    )
    ```
