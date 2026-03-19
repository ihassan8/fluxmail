---
hide:
  - toc
---

<div class="hero" markdown>
<img src="img/autoemail_192x192.png" alt="FluxMail">

# FluxMail

**Send emails from the terminal or Python — SMTP and Outlook in one library.**

[Get Started](installation.md){ .md-button .md-button--primary }
[Python API](getting-started/usage.md){ .md-button }

</div>

---

<div align="center" markdown>

[![PyPI](https://img.shields.io/pypi/v/fluxmail?color=2563eb&logo=pypi&logoColor=white)](https://pypi.org/project/fluxmail/)
[![Python](https://img.shields.io/pypi/pyversions/fluxmail?color=2563eb&logo=python&logoColor=white)](https://pypi.org/project/fluxmail/)
[![License](https://img.shields.io/badge/license-MIT-2563eb.svg)](https://github.com/vertex-ai-automations/autoemail/blob/main/LICENSE.txt)
[![Downloads](https://img.shields.io/pypi/dm/fluxmail?color=2563eb)](https://pypi.org/project/fluxmail/)
[![CI](https://img.shields.io/github/actions/workflow/status/vertex-ai-automations/autoemail/release.yml?branch=main&label=CI&logo=github)](https://github.com/vertex-ai-automations/autoemail/actions)

</div>

---

<div class="feature-grid" markdown>

<div class="feature-item" markdown>
**:material-email-fast: SMTP**

Send via any SMTP server — Gmail, SendGrid, SES, Mailgun, or your own relay — with STARTTLS and credential auth.
</div>

<div class="feature-item" markdown>
**:material-microsoft-outlook: Outlook**

Compose and preview Outlook emails via COM automation. Windows only — no extra configuration required.
</div>

<div class="feature-item" markdown>
**:material-console: CLI**

One-line sends from the terminal. All options as flags; credentials safely via environment variables.
</div>

<div class="feature-item" markdown>
**:material-language-python: Python API**

Chainable API: `FluxMail(...).create(...).send()`. Plugs into any Python script or automation pipeline.
</div>

</div>

---

## Quickstart

=== "Python"

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

=== "CLI"

    ```bash
    pip install fluxmail

    FLUXMAIL_USERNAME=me@gmail.com FLUXMAIL_PASSWORD=secret \
      fluxmail --type smtp --host smtp.gmail.com --port 587 --tls \
        --subject "Hello" \
        --recipients friend@example.com \
        --body "Hi there!"
    ```

---

## What's included

<div class="grid cards" markdown>

- :material-lock-check: **Secure credential handling** — load SMTP credentials from env vars; passwords never appear in shell history

- :material-attachment: **File attachments** — attach any file; MIME type is detected automatically

- :material-code-tags: **HTML or plain text** — switch body format with a single flag or parameter

- :material-eye-outline: **Dry-run preview** — inspect the full email before it leaves your machine

- :material-server-network: **Any SMTP relay** — pass a hostname string or `EmailInstance`; works with Gmail, SendGrid, SES, and self-hosted servers

- :material-python: **Python 3.8+ compatible** — runs on any modern Python; no breaking syntax used

</div>
