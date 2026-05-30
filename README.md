<a name="readme-top"></a>

<div align="center">
<img src="https://github.com/ihassan8/fluxmail/raw/main/docs/img/fluxmail.png" alt="FluxMail Logo" width="420">

<br/>

[![PyPI version](https://img.shields.io/pypi/v/fluxmail?color=2563eb&logo=pypi&logoColor=white)](https://pypi.org/project/fluxmail/)
[![Python versions](https://img.shields.io/pypi/pyversions/fluxmail?color=2563eb&logo=python&logoColor=white)](https://pypi.org/project/fluxmail/)
[![License: MIT](https://img.shields.io/badge/license-MIT-2563eb.svg)](https://github.com/ihassan8/fluxmail/blob/main/LICENSE.txt)
[![Downloads](https://img.shields.io/pypi/dm/fluxmail?color=2563eb)](https://pypi.org/project/fluxmail/)
[![CI](https://img.shields.io/github/actions/workflow/status/ihassan8/fluxmail/ci.yml?branch=main&label=CI&logo=github)](https://github.com/ihassan8/fluxmail/actions/workflows/ci.yml)
[![Docs](https://img.shields.io/badge/docs-online-2563eb?logo=readthedocs&logoColor=white)](https://ihassan8.github.io/fluxmail)

<br/>

<p>
<a href="https://ihassan8.github.io/fluxmail"><strong>📃 Documentation</strong></a>
&nbsp;·&nbsp;
<a href="https://github.com/ihassan8/fluxmail/issues/new">🔧 Report Bug</a>
</p>

</div>

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Quick Start](#-quick-start)
- [Configuration](#-configuration)
- [Contributing](#-contributing)

---

## 📣 Overview

A Python library for email automation supporting SMTP and Outlook protocols. Send emails
via CLI or Python API. Outlook support is Windows-only (requires `pywin32`).

---

## 📌 Quick Start

### Installation

```bash
pip install fluxmail
```

```bash
pip install --upgrade fluxmail   # upgrade
```

### CLI

```bash
export FLUXMAIL_USERNAME=me@gmail.com
export FLUXMAIL_PASSWORD=secret

fluxmail --type smtp --host smtp.gmail.com --port 587 --tls \
  --subject "Hello" \
  --recipients friend@example.com \
  --body "Hi from the CLI!"
```

### Python API

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

**Full documentation:** 👉 [ihassan8.github.io/fluxmail](https://ihassan8.github.io/fluxmail)

---

## ⚙️ Configuration

Pass credentials via environment variables so they never appear in shell history:

```bash
export FLUXMAIL_USERNAME=me@gmail.com
export FLUXMAIL_PASSWORD=secret
```

Works with any SMTP provider — Gmail, SendGrid, Amazon SES, Mailgun, Office 365, or a self-hosted relay.

See [Configuration](https://ihassan8.github.io/fluxmail/getting-started/configuration/) for provider-specific settings.

---


---

## CI Pipeline

Every push to `main` and every pull request runs automatically via [shared-workflows](https://github.com/ihassan8/shared-workflows):

| Job | What it checks |
|-----|----------------|
| **Test** | pytest on Python 3.9–3.12 x Ubuntu + Windows |
| **Lint** | `ruff check` + `ruff format --check` |
| **Type Check** | `mypy src/` |
| **Audit** | `pip-audit` — all dependencies scanned for known CVEs |
| **Coverage** | `pytest-cov` — report posted to the Actions job summary |
## 👪 Contributing

All contributions are welcome! Fork the repo, make your changes, and open a pull request.
You can also open an issue with the label `enhancement`.

Don't forget to ⭐ star the project!

🔶 [View all contributors](https://github.com/ihassan8/fluxmail/graphs/contributors)

---

📃 [Full Docs](https://ihassan8.github.io/fluxmail) &nbsp;·&nbsp; 🔧 [Report a Bug](https://github.com/ihassan8/fluxmail/issues/new)

<p align="right">(<a href="#readme-top">back to top</a>)</p>
