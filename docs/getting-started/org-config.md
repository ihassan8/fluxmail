# Org Configuration

Configure AutoEmail for your organization's email infrastructure before first use.

## Built-in Environments

AutoEmail ships with three named environments that map to SMTP relay servers and domains:

| Environment | Default Relay | Default Domain |
|-------------|---------------|----------------|
| `Domain1` | `domain1-mail.hr.acme.com` | `hr.acme.com` |
| `Domain2` | `domain2-mail.ops.acme.com` | `ops.acme.com` |
| `Domain3` | `domain3-mail.server.acme.com` | `server.acme.com` |

These defaults are placeholders. Your org's actual relay hostnames and domains
are configured via environment variables (see below).

## Overriding Relay and Domain

!!! danger "Import-time evaluation"
    Environment variables are read **once** when `autoemail` is first imported.
    Set them in your shell profile, `.env` file, or deployment config **before**
    the module is imported — changes made after import have no effect.

```bash
export AUTOEMAIL_DOMAIN1_RELAY=mail.hr.yourorg.com
export AUTOEMAIL_DOMAIN1_DOMAIN=hr.yourorg.com

export AUTOEMAIL_DOMAIN2_RELAY=mail.ops.yourorg.com
export AUTOEMAIL_DOMAIN2_DOMAIN=ops.yourorg.com

export AUTOEMAIL_DOMAIN3_RELAY=mail.server.yourorg.com
export AUTOEMAIL_DOMAIN3_DOMAIN=server.yourorg.com
```

For the CLI, set these in your shell profile (`~/.bashrc`, `~/.zshrc`) or in a
wrapper script that calls `autoemail`.

## Auto Domain Detection

Pass `host=None` in the Python API to let AutoEmail automatically detect the
correct environment from the machine's fully-qualified domain name (FQDN):

```python
# Selects the EmailEnv whose domain matches this machine's FQDN
from autoemail import AutoEmail

email = AutoEmail(object_type="smtp", host=None)
```

AutoEmail calls `socket.getfqdn()` and matches the result against each configured
`EmailEnv` domain. The first match wins. If no environment matches,
`AutoEmailException` is raised with a descriptive message.

!!! note
    The `"runner"` CI bypass applies only to domain-mismatch validation
    (`detect_domain_mismatches=True`), not to `host=None` auto-detection.
    If you use `host=None` in a CI environment, AutoEmail will still attempt
    to match the machine FQDN against configured domains and raise
    `AutoEmailException` if none match.

The `--host` flag is required in the CLI and does not support auto-detection.

## Address Validation

!!! info "Address validation rules"

    These rules are enforced automatically and cannot be disabled:

    | Field | Rule |
    |-------|------|
    | **Sender** (SMTP only) | Must be a `.gov` address matching `host.domain` |
    | **Recipients / CC** | `.gov` on `host.domain` required — except `Domain1`, which accepts any valid email |
    | **BCC** | No domain restriction (works on both SMTP and Outlook) |
    | **Reply-To** | No domain restriction (SMTP only — Outlook has no Reply-To field) |

!!! tip
    Use `Domain1` for most internal sends. Use `Domain2` or `Domain3` only when
    sending to addresses within those specific sub-domains, and ensure all
    recipients, CC, and sender addresses are `.gov` addresses on that domain.

## Credential Handling

For SMTP servers that require login (e.g., external relay with `--port 587 --tls`),
prefer environment variables over inline flags to keep secrets out of shell history
and process listings:

```bash
export AUTOEMAIL_USERNAME=me@yourorg.com
export AUTOEMAIL_PASSWORD=secret
```

The CLI reads `AUTOEMAIL_USERNAME` and `AUTOEMAIL_PASSWORD` automatically. The
`--username` and `--password` flags also work but will appear in `ps` output and
shell history — avoid for production or shared systems.
