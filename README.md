<a name="readme-top"></a>

<div align="center">
<img src="https://github.com/vertex-ai-automations/autoemail/raw/main/docs/img/autoemail.png" alt="AutoEmail Logo" width="420">

<br/>

[![PyPI version](https://img.shields.io/pypi/v/autoemail?color=2563eb&logo=pypi&logoColor=white)](https://pypi.org/project/autoemail/)
[![Python versions](https://img.shields.io/pypi/pyversions/autoemail?color=2563eb&logo=python&logoColor=white)](https://pypi.org/project/autoemail/)
[![License: MIT](https://img.shields.io/badge/license-MIT-2563eb.svg)](https://github.com/vertex-ai-automations/autoemail/blob/main/LICENSE.txt)
[![Downloads](https://img.shields.io/pypi/dm/autoemail?color=2563eb)](https://pypi.org/project/autoemail/)
[![CI](https://img.shields.io/github/actions/workflow/status/vertex-ai-automations/autoemail/release.yml?branch=main&label=CI&logo=github)](https://github.com/vertex-ai-automations/autoemail/actions)
[![Docs](https://img.shields.io/badge/docs-online-2563eb?logo=readthedocs&logoColor=white)](https://vertex-ai-automations.github.io/autoemail)

<br/>

<p>
<a href="https://vertex-ai-automations.github.io/autoemail"><strong>📃 Documentation</strong></a>
&nbsp;·&nbsp;
<a href="https://github.com/vertex-ai-automations/autoemail/issues/new">🔧 Report Bug</a>
&nbsp;·&nbsp;
<a href="https://www.vertexaiautomations.com">⛪ Vertex AI Automations</a>
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
pip install autoemail
```

```bash
pip install --upgrade autoemail   # upgrade
```

### CLI

```bash
autoemail --type smtp --host Domain1 \
  --subject "Weekly Report" \
  --recipients user@hr.acme.com \
  --body "Please find this week's report below."
```

### Python API

```python
from autoemail import AutoEmail, EmailEnv, EmailObject

AutoEmail(object_type=EmailObject.SMTP, host=EmailEnv.Domain1).create(
    subject="Weekly Report",
    recipients=["user@hr.acme.com"],
    body="Please find this week's report below.",
).send()
```

**Full documentation:** 👉 [vertex-ai-automations.github.io/autoemail](https://vertex-ai-automations.github.io/autoemail)

---

## ⚙️ Configuration

Override built-in relay environments with env vars (set before import):

```bash
export AUTOEMAIL_DOMAIN1_RELAY=mail.hr.yourorg.com
export AUTOEMAIL_DOMAIN1_DOMAIN=hr.yourorg.com
```

Store credentials safely:

```bash
export AUTOEMAIL_USERNAME=me@yourorg.com
export AUTOEMAIL_PASSWORD=secret
```

See [Org Configuration](https://vertex-ai-automations.github.io/autoemail/getting-started/org-config/) for full details.

---

## 👪 Contributing

All contributions are welcome! Fork the repo, make your changes, and open a pull request.
You can also open an issue with the label `enhancement`.

Don't forget to ⭐ star the project!

🔶 [View all contributors](https://github.com/vertex-ai-automations/autoemail/graphs/contributors)

---

📃 [Full Docs](https://vertex-ai-automations.github.io/autoemail) &nbsp;·&nbsp; 🔧 [Report a Bug](https://github.com/vertex-ai-automations/autoemail/issues/new) &nbsp;·&nbsp; ⛪ [Vertex AI Automations](https://www.vertexaiautomations.com)

<p align="right">(<a href="#readme-top">back to top</a>)</p>
