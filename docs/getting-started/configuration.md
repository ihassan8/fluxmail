# Configuration

## Credentials via Environment Variables

The recommended way to pass SMTP credentials is through environment variables so
they never appear in shell history or source code:

```bash
export AUTOEMAIL_USERNAME=me@gmail.com
export AUTOEMAIL_PASSWORD=secret
```

These are read automatically by the CLI (`--username` and `--password` flags).
In Python, read them explicitly:

```python
import os
from autoemail import AutoEmail

email = AutoEmail(
    object_type="smtp",
    host="smtp.gmail.com",
    port=587,
    use_tls=True,
    username=os.environ["AUTOEMAIL_USERNAME"],
    password=os.environ["AUTOEMAIL_PASSWORD"],
)
```

## Host Formats

`host` accepts three forms:

| Form | Example | When to use |
|------|---------|-------------|
| Bare relay string | `"smtp.gmail.com"` | Most common — relay hostname only |
| `relay:domain` string | `"smtp.gmail.com:gmail.com"` | CLI shorthand when you want both relay and domain stored |
| `EmailInstance` namedtuple | `EmailInstance(relay="smtp.myrelay.net", domain="mycompany.com")` | Reusable host config in Python code |

```python
from autoemail import AutoEmail, EmailInstance

# Bare string — domain defaults to ""
AutoEmail(object_type="smtp", host="smtp.gmail.com", ...)

# relay:domain string
AutoEmail(object_type="smtp", host="smtp.gmail.com:gmail.com", ...)

# EmailInstance (domain is optional)
AutoEmail(object_type="smtp", host=EmailInstance(relay="smtp.myrelay.net"), ...)
```

## Sender Resolution

`sender` in `create()` is determined in this order:

1. **Explicit `sender=`** — always wins.
2. **`username`** — used as the `From` address when it is a valid email address
   (e.g. `me@gmail.com`). Useful for Gmail, SES, Mailgun.
3. **Error** — if neither applies (e.g. SendGrid's `apikey` username),
   `AutoEmailException` is raised. Pass `sender=` explicitly in that case.

## Common SMTP Providers

| Provider | Host | Port | TLS |
|----------|------|------|-----|
| Gmail | `smtp.gmail.com` | 587 | Yes |
| SendGrid | `smtp.sendgrid.net` | 587 | Yes |
| Amazon SES | `email-smtp.<region>.amazonaws.com` | 587 | Yes |
| Mailgun | `smtp.mailgun.org` | 587 | Yes |
| Office 365 | `smtp.office365.com` | 587 | Yes |
| Self-hosted | your relay hostname | 25 or 587 | Optional |
