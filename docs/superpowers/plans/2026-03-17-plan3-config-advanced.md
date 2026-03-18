# Plan 3: Configuration System, OAuth2 & Advanced Email Features

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a TOML config file for CLI defaults, make `EmailEnv` environments loadable from config (not just env vars), support OAuth2 SMTP authentication, and support inline CID image attachments for HTML emails.

**Architecture:** Config is loaded once at CLI startup and merged with flag values (flags win). A new `config.py` module handles TOML parsing. `EmailEnv` loading remains backward-compatible — env vars still take priority. OAuth2 is a new `oauth2_token` constructor param that replaces the `smtp.login()` call. Inline images extend the `create()` parameter list and hook into the existing `_attach_files()` pipeline.

**Tech Stack:** `tomllib` (stdlib ≥ 3.11) / `tomli` (backport for 3.8–3.10), `stdlib base64` (OAuth2, no new dep)

**Prerequisite:** Plans 1 and 2 must be complete.

---

## File Map

| Action | Path | Responsibility |
|--------|------|---------------|
| Modify | `requirements.txt` | Add `tomli` (Python 3.8–3.10 backport) |
| Create | `src/autoemail/config.py` | TOML config loader |
| Modify | `src/autoemail/utils.py` | Dynamic `EmailEnv` loading from config |
| Modify | `src/autoemail/autoemail.py` | `oauth2_token` slot, OAuth2 auth in `send()`, `inline_images` slot + `_attach_inline_images()` |
| Modify | `src/autoemail/autoemail_cli.py` | Load config file at startup, merge with flags |
| Modify | `src/autoemail/__init__.py` | Export `load_config` |
| Create | `tests/test_config.py` | Tests for TOML config loading |
| Modify | `tests/test_autoemail.py` | Tests for OAuth2 and inline images |
| Modify | `tests/test_cli.py` | Tests for CLI config file integration |

### New `__slots__` entries on `AutoEmail`

`"oauth2_token"`, `"inline_images"` — both initialised to `None` in `__init__`.

---

## Task 1: TOML Dependency

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add `tomli` for Python < 3.11**

```
tomli>=2.0; python_version < "3.11"
```

- [ ] **Step 2: Install and verify**

```bash
pip install -r requirements.txt
python -c "
import sys
if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib
print('tomllib ok')
"
```
Expected: `tomllib ok`

- [ ] **Step 3: Commit**

```bash
git add requirements.txt
git commit -m "chore: add tomli backport for Python < 3.11"
```

---

## Task 2: TOML Config Loader

**Files:**
- Create: `src/autoemail/config.py`
- Create: `tests/test_config.py`

The config file location (searched in order):
1. Path in `AUTOEMAIL_CONFIG` env var
2. `.autoemail.toml` in the current working directory
3. `~/.autoemail.toml` (user home directory)

If none exist, an empty dict is returned — config is always optional.

**Supported config keys** (all optional, all overridable by CLI flags):

```toml
[defaults]
type    = "smtp"
host    = "Domain1"
port    = 25
tls     = false
username = ""
password = ""

[environments.myenv]
relay  = "smtp.myorg.com"
domain = "myorg.com"
```

- [ ] **Step 1: Write failing tests**

```python
# tests/test_config.py
import pytest
from autoemail.config import load_config, find_config_file


class TestFindConfigFile:
    def test_returns_none_when_no_config(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("AUTOEMAIL_CONFIG", raising=False)
        # Set both HOME (Unix) and USERPROFILE (Windows) so expanduser("~") resolves
        # to tmp_path on all platforms, preventing the user's real config from being found.
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))
        assert find_config_file() is None

    def test_env_var_takes_priority(self, tmp_path, monkeypatch):
        cfg = tmp_path / "custom.toml"
        cfg.write_text('[defaults]\ntype = "smtp"\n')
        monkeypatch.setenv("AUTOEMAIL_CONFIG", str(cfg))
        assert find_config_file() == str(cfg)

    def test_cwd_config_found(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("AUTOEMAIL_CONFIG", raising=False)
        cfg = tmp_path / ".autoemail.toml"
        cfg.write_text('[defaults]\n')
        assert find_config_file() == str(cfg)


class TestLoadConfig:
    def test_empty_when_no_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("AUTOEMAIL_CONFIG", raising=False)
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))
        assert load_config() == {}

    def test_loads_defaults_section(self, tmp_path, monkeypatch):
        cfg = tmp_path / ".autoemail.toml"
        cfg.write_text('[defaults]\ntype = "smtp"\nhost = "Domain1"\n')
        monkeypatch.setenv("AUTOEMAIL_CONFIG", str(cfg))
        result = load_config()
        assert result["defaults"]["type"] == "smtp"
        assert result["defaults"]["host"] == "Domain1"

    def test_loads_environments(self, tmp_path, monkeypatch):
        cfg = tmp_path / ".autoemail.toml"
        cfg.write_text(
            '[environments.myenv]\nrelay = "smtp.myorg.com"\ndomain = "myorg.com"\n'
        )
        monkeypatch.setenv("AUTOEMAIL_CONFIG", str(cfg))
        result = load_config()
        assert result["environments"]["myenv"]["relay"] == "smtp.myorg.com"

    def test_invalid_toml_raises(self, tmp_path, monkeypatch):
        from autoemail.utils import AutoEmailException
        cfg = tmp_path / ".autoemail.toml"
        cfg.write_text("not valid [[toml")
        monkeypatch.setenv("AUTOEMAIL_CONFIG", str(cfg))
        with pytest.raises(AutoEmailException, match="Invalid config"):
            load_config()
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/test_config.py -v
```

- [ ] **Step 3: Implement `src/autoemail/config.py`**

```python
"""TOML config file loading for AutoEmail CLI defaults."""
import os
import sys
from typing import Any, Dict, Optional

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore[no-redef]

from .utils import AutoEmailException

_CONFIG_FILENAMES = (".autoemail.toml",)


def find_config_file() -> Optional[str]:
    """Return the path of the first config file found, or None.

    Search order:
    1. ``AUTOEMAIL_CONFIG`` environment variable
    2. ``.autoemail.toml`` in the current working directory
    3. ``~/.autoemail.toml`` in the user home directory
    """
    env_path = os.environ.get("AUTOEMAIL_CONFIG")
    if env_path and os.path.isfile(env_path):
        return env_path

    for name in _CONFIG_FILENAMES:
        cwd_path = os.path.join(os.getcwd(), name)
        if os.path.isfile(cwd_path):
            return cwd_path

        home_path = os.path.join(os.path.expanduser("~"), name)
        if os.path.isfile(home_path):
            return home_path

    return None


def load_config() -> Dict[str, Any]:
    """Load and return the TOML config as a nested dict.

    Returns an empty dict if no config file is found.

    Raises
    ------
    AutoEmailException
        If a config file is found but contains invalid TOML.
    """
    path = find_config_file()
    if path is None:
        return {}

    try:
        with open(path, "rb") as fh:
            return tomllib.load(fh)
    except tomllib.TOMLDecodeError as exc:
        raise AutoEmailException(f"Invalid config file at '{path}': {exc}")
    except OSError as exc:
        raise AutoEmailException(f"Cannot read config file '{path}': {exc}")
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_config.py -v
```
Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add src/autoemail/config.py tests/test_config.py
git commit -m "feat: add TOML config file loader"
```

---

## Task 3: Dynamic `EmailEnv` from Config

**Files:**
- Modify: `src/autoemail/utils.py`
- Modify: `tests/test_config.py`

**Background:** Currently `EmailEnv` is fixed at three members resolved at import time from env vars. This task adds a function to register custom environments from a config dict at runtime — without touching the enum.

The simplest approach: `resolve_host_from_config(name, config)` looks up `config["environments"][name]` and returns an `EmailInstance`. The CLI can call this before constructing `AutoEmail` when the host string doesn't match a known `EmailEnv` member and a config file is present.

- [ ] **Step 1: Write failing tests**

Add to `tests/test_config.py`:

```python
from autoemail.utils import resolve_host_from_config
from autoemail import EmailInstance


class TestResolveHostFromConfig:
    CONFIG = {
        "environments": {
            "myenv": {"relay": "smtp.myorg.com", "domain": "myorg.com"}
        }
    }

    def test_resolves_named_environment(self):
        host = resolve_host_from_config("myenv", self.CONFIG)
        assert isinstance(host, EmailInstance)
        assert host.relay == "smtp.myorg.com"
        assert host.domain == "myorg.com"

    def test_missing_name_returns_none(self):
        assert resolve_host_from_config("unknown", self.CONFIG) is None

    def test_empty_config_returns_none(self):
        assert resolve_host_from_config("myenv", {}) is None

    def test_missing_relay_raises(self):
        from autoemail.utils import AutoEmailException
        bad_config = {"environments": {"e": {"domain": "x.com"}}}
        with pytest.raises(AutoEmailException, match="relay"):
            resolve_host_from_config("e", bad_config)
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/test_config.py::TestResolveHostFromConfig -v
```

- [ ] **Step 3: Implement `resolve_host_from_config` in `utils.py`**

```python
from typing import Any, Dict, Optional  # add to existing imports

def resolve_host_from_config(
    name: str, config: Dict[str, Any]
) -> Optional["EmailInstance"]:
    """Look up a named environment in the config dict.

    Parameters
    ----------
    name : str
        Key under ``config["environments"]``.
    config : dict
        Parsed TOML config (from ``load_config()``).

    Returns
    -------
    EmailInstance or None
        The resolved instance, or ``None`` if the name is not found.

    Raises
    ------
    AutoEmailException
        If the environment entry is missing the required ``relay`` or ``domain`` keys.
    """
    envs = config.get("environments", {})
    entry = envs.get(name)
    if entry is None:
        return None

    relay = entry.get("relay")
    domain = entry.get("domain")

    if not relay:
        raise AutoEmailException(
            f"Config environment '{name}' is missing required key 'relay'."
        )
    if not domain:
        raise AutoEmailException(
            f"Config environment '{name}' is missing required key 'domain'."
        )

    return EmailInstance(relay=relay, domain=domain)
```

- [ ] **Step 4: Update the CLI `_resolve_host()` to check config environments**

In `autoemail_cli.py`, update `_resolve_host()`:

```python
def _resolve_host(host_str: str, config: Optional[dict] = None) -> "Union[EmailEnv, EmailInstance]":
    """Resolve host: built-in EmailEnv → config environments → relay:domain syntax."""
    from .config import load_config
    from .utils import resolve_host_from_config

    if config is None:
        config = {}

    # 1. Known built-in environment
    try:
        return str_to_enum(EmailEnv, host_str)
    except ValueError:
        pass

    # 2. Named environment in config file
    host_from_cfg = resolve_host_from_config(host_str, config)
    if host_from_cfg is not None:
        return host_from_cfg

    # 3. Inline relay:domain
    if ":" in host_str:
        relay, domain = host_str.split(":", 1)
        return EmailInstance(relay=relay.strip(), domain=domain.strip())

    raise typer.BadParameter(
        f"Unknown host '{host_str}'. Use Domain1/Domain2/Domain3, a name from "
        f"your config file, or a custom relay as 'relay:domain'."
    )
```

And pass `config` when calling `_resolve_host()` inside the `send()` command:

```python
cfg = load_config()
# apply config defaults (CLI flags win over config)
if email_type is None:
    email_type = cfg.get("defaults", {}).get("type")
if host is None:
    host = cfg.get("defaults", {}).get("host")
...
email_host = _resolve_host(host, config=cfg)
```

> Note: since `email_type` and `host` are required flags in the CLI, the `None` fallback from config only helps when a wrapper script passes them. No existing tests break.

- [ ] **Step 5: Run all tests**

```bash
pytest tests/ -v
```
Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add src/autoemail/utils.py src/autoemail/autoemail_cli.py tests/test_config.py
git commit -m "feat: resolve named environments from TOML config file"
```

---

## Task 4: OAuth2 Authentication

**Files:**
- Modify: `src/autoemail/autoemail.py`
- Modify: `tests/test_autoemail.py`

**Background:** Modern email providers (Gmail, Microsoft 365) deprecate basic `username`/`password` auth. OAuth2 uses a bearer token via the XOAUTH2 SASL mechanism. No new library needed — `base64` is stdlib.

The token is passed as `oauth2_token` to the constructor. When both `oauth2_token` and `username` are set, OAuth2 takes priority over `smtp.login()`.

- [ ] **Step 1: Write failing tests**

```python
class TestOAuth2:
    def test_oauth2_used_instead_of_login(self):
        from unittest.mock import patch, MagicMock, call
        import base64

        mock_smtp = MagicMock()
        mock_cls = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_smtp)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_smtp.docmd.return_value = (235, b"OK")

        with patch("autoemail.autoemail.smtplib.SMTP", mock_cls):
            e = AutoEmail(
                object_type="smtp",
                host=EmailEnv.Domain1,
                username="user@example.com",
                oauth2_token="mytoken",
            )
            e.create(subject="Hi", recipients=["a@b.com"], body="Hello").send()

        mock_smtp.login.assert_not_called()
        mock_smtp.docmd.assert_called_once()
        call_args = mock_smtp.docmd.call_args[0]
        assert call_args[0] == "AUTH"
        assert "XOAUTH2" in call_args[1]

    def test_oauth2_token_without_username_raises(self):
        with pytest.raises(AutoEmailException, match="username"):
            AutoEmail(
                object_type="smtp",
                host=EmailEnv.Domain1,
                oauth2_token="mytoken",
                # no username
            ).create(subject="Hi", recipients=["a@b.com"], body="Hello").send()

    def test_oauth2_failed_auth_raises(self):
        from unittest.mock import patch, MagicMock
        mock_smtp = MagicMock()
        mock_cls = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_smtp)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_smtp.docmd.return_value = (535, b"Authentication failed")

        with patch("autoemail.autoemail.smtplib.SMTP", mock_cls):
            e = AutoEmail(
                object_type="smtp",
                host=EmailEnv.Domain1,
                username="user@example.com",
                oauth2_token="badtoken",
            )
            e.create(subject="Hi", recipients=["a@b.com"], body="Hello")
            with pytest.raises(AutoEmailException, match="OAuth2"):
                e.send()
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/test_autoemail.py::TestOAuth2 -v
```

- [ ] **Step 3: Add `oauth2_token` to `__slots__` and `__init__`**

In `__slots__`: add `"oauth2_token"`

In `__init__` signature:
```python
oauth2_token: Optional[str] = None,
```

In `__init__` body:
```python
self.oauth2_token = oauth2_token
```

- [ ] **Step 4: Add `import base64` to `autoemail.py` and implement `_auth_smtp()`**

```python
import base64  # add to imports
```

```python
def _auth_smtp(self, smtp) -> None:
    """Authenticate smtp using OAuth2 token or basic credentials."""
    if self.oauth2_token:
        if not self.username:
            raise AutoEmailException(
                "oauth2_token requires username to be set."
            )
        auth_str = f"user={self.username}\x01auth=Bearer {self.oauth2_token}\x01\x01"
        encoded = base64.b64encode(auth_str.encode()).decode()
        code, _ = smtp.docmd("AUTH", f"XOAUTH2 {encoded}")
        if code != 235:
            raise AutoEmailException(
                f"OAuth2 authentication failed (server returned code {code})."
            )
    elif self.username and self.password:
        smtp.login(self.username, self.password)
```

- [ ] **Step 5: Replace inline auth logic in `send()` and `__enter__()` with `_auth_smtp()`**

In `send()`, replace:
```python
if self.username and self.password:
    smtp.login(self.username, self.password)
```
with:
```python
self._auth_smtp(smtp)
```

In `__enter__()`, replace:
```python
if self.username and self.password:
    self._smtp_conn.login(self.username, self.password)
```
with:
```python
self._auth_smtp(self._smtp_conn)
```

Also apply `_auth_smtp` in `send_async()` — replace the `await smtp.login(...)` line:
```python
if self.username and self.password:
    await smtp.login(self.username, self.password)
```
> Note: `aiosmtplib` does not support arbitrary `AUTH` commands the same way. Document that OAuth2 is SMTP-only (not async) for now — raise `AutoEmailException` if `oauth2_token` is set and `send_async()` is called.

```python
async def send_async(self) -> str:
    if self.oauth2_token:
        raise AutoEmailException(
            "OAuth2 is not supported with send_async(). Use send() instead."
        )
    ...
```

- [ ] **Step 6: Run all tests**

```bash
pytest tests/ -v
```
Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add src/autoemail/autoemail.py tests/test_autoemail.py
git commit -m "feat: add OAuth2 (XOAUTH2) SMTP authentication"
```

---

## Task 5: Inline CID Image Attachments

**Files:**
- Modify: `src/autoemail/autoemail.py`
- Modify: `tests/test_autoemail.py`

**Background:** When `html_body=True`, images can be embedded inline in the HTML body using `<img src="cid:logo">` and attaching the file with a matching `Content-ID`. This requires the message to be `multipart/related` wrapping `multipart/alternative`. Only meaningful for SMTP with `html_body=True`.

New `create()` parameter: `inline_images: Optional[Dict[str, str]] = None`
where keys are CID names (e.g. `"logo"`) and values are file paths.

- [ ] **Step 1: Write failing tests**

```python
class TestInlineImages:
    def test_inline_image_attaches_related_part(self, smtp_email, tmp_path):
        img = tmp_path / "logo.png"
        img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 8)  # minimal PNG header

        smtp_email.create(
            subject="Hi", recipients=["a@b.com"],
            body='<img src="cid:logo"><p>Hello</p>',
            html_body=True,
            inline_images={"logo": str(img)},
        )
        # Top-level content type should be multipart/related
        assert smtp_email.message.get_content_type() == "multipart/related"

    def test_inline_image_requires_html_body(self, smtp_email, tmp_path):
        img = tmp_path / "img.png"
        img.write_bytes(b"\x89PNG" + b"\x00" * 8)
        with pytest.raises(AutoEmailException, match="html_body"):
            smtp_email.create(
                subject="Hi", recipients=["a@b.com"],
                body="plain text",
                html_body=False,
                inline_images={"img": str(img)},
            )

    def test_inline_image_not_found_raises(self, smtp_email):
        with pytest.raises(AutoEmailException, match="not found"):
            smtp_email.create(
                subject="Hi", recipients=["a@b.com"],
                body="<img src='cid:x'>",
                html_body=True,
                inline_images={"x": "/nonexistent/image.png"},
            )
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/test_autoemail.py::TestInlineImages -v
```

- [ ] **Step 3: Add `inline_images` to `__slots__` and `__init__`**

In `__slots__`: add `"inline_images"`
In `__init__` body: `self.inline_images = None`

- [ ] **Step 4: Add `inline_images` parameter to `create()` and validate**

```python
inline_images: Optional[dict] = None,   # Dict[str, str] — cid_name: file_path
```

Assign: `self.inline_images = inline_images`

In `_validate_parameters()`:
```python
if self.inline_images and not self.html_body:
    raise AutoEmailException(
        "inline_images requires html_body=True."
    )
```

- [ ] **Step 5: Implement `_attach_inline_images()` and call it from `create()`**

```python
def _attach_inline_images(self) -> None:
    """Attach inline CID images to the HTML part of the message."""
    if not self.inline_images or not self.is_smtp():
        return

    # Find the HTML part — it is either self.message (simple HTML)
    # or the last payload in multipart/alternative
    payload = self.message.get_payload()
    if isinstance(payload, list):
        html_part = payload[-1]
    else:
        html_part = self.message

    for cid_name, file_path in self.inline_images.items():
        if not os.path.isfile(file_path):
            raise AutoEmailException(
                f"Inline image not found: '{file_path}' (cid: '{cid_name}')"
            )
        mime_type, _ = mimetypes.guess_type(file_path)
        maintype, subtype = (mime_type or "image/png").split("/", 1)
        with open(file_path, "rb") as fh:
            data = fh.read()
        html_part.add_related(
            data,
            maintype=maintype,
            subtype=subtype,
            cid=f"<{cid_name}>",
        )
```

Call `self._attach_inline_images()` inside `create()` after `self._attach_files()`.

- [ ] **Step 6: Run all tests**

```bash
pytest tests/ -v
```
Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add src/autoemail/autoemail.py tests/test_autoemail.py
git commit -m "feat: add inline_images for CID image embedding in HTML emails"
```

---

## Task 6: Final Run, Docs & Config Documentation

- [ ] **Step 1: Run full test suite**

```bash
pytest tests/ -v --tb=short
```
Expected: all green, zero failures.

- [ ] **Step 2: Create a sample config file at `docs/autoemail.toml.example`**

```toml
# AutoEmail configuration file
# Copy to ~/.autoemail.toml or .autoemail.toml in your project root.
# CLI flags always override these values.

[defaults]
type = "smtp"
host = "Domain1"
port  = 25
tls   = false

# Uncomment and fill in for authenticated relays:
# username = "me@yourorg.com"
# password = ""   # prefer AUTOEMAIL_PASSWORD env var instead

[environments]

# Custom relay not covered by Domain1/2/3:
# [environments.gmail]
# relay  = "smtp.gmail.com"
# domain = "gmail.com"

# [environments.sendgrid]
# relay  = "smtp.sendgrid.net"
# domain = "sendgrid.net"
```

- [ ] **Step 3: Update `docs/getting-started/org-config.md`** — add section after "Overriding Relay and Domain":

```markdown
## Config File

Place a `.autoemail.toml` file in your project root or `~/.autoemail.toml` for
user-level defaults. CLI flags always win over config values.

```toml
[defaults]
type = "smtp"
host = "Domain1"

[environments.mailing]
relay  = "smtp.myorg.com"
domain = "myorg.com"
```

Use the named environment in the CLI:

```bash
autoemail --type smtp --host mailing --subject "Test" \
  --recipients user@myorg.com --body "Hello"
```

A sample config file is at `docs/autoemail.toml.example`.
```

- [ ] **Step 4: Update `docs/getting-started/usage.md`** — add sections:

```markdown
## OAuth2 Authentication

```python
email = AutoEmail(
    object_type="smtp",
    host=EmailInstance(relay="smtp.gmail.com", domain="gmail.com"),
    port=587,
    use_tls=True,
    username="me@gmail.com",
    oauth2_token="ya29.your_access_token",
)
email.create(subject="Hello", recipients=["friend@example.com"], body="Hi").send()
```

## Inline Images in HTML Emails

Reference images in the HTML body using `cid:<name>`, then provide file paths:

```python
email.create(
    subject="Report",
    recipients=["user@hr.acme.com"],
    body='<h1>Report</h1><img src="cid:chart">',
    html_body=True,
    inline_images={"chart": "/path/to/chart.png"},
)
```
```

- [ ] **Step 5: Commit everything**

```bash
git add docs/ src/autoemail/__init__.py
git commit -m "docs: document Plan 3 config, OAuth2, and inline images"
```
