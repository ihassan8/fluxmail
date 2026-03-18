# CLI Usage

Send emails directly from the terminal with the `autoemail` command.
Run `autoemail --help` for full usage with formatted output.

## Flags

| Flag | Required | Default | Description |
|------|----------|---------|-------------|
| `--type` | Yes | — | Email protocol: `smtp` or `outlook` |
| `--host` | Yes | — | Environment (`Domain1`, `Domain2`, `Domain3`) or custom relay as `relay:domain` (e.g. `smtp.gmail.com:gmail.com`) |
| `--subject` | Yes | — | Email subject line |
| `--recipients` | Yes | — | Recipient address. Repeat flag for multiple. |
| `--body` | No* | — | Email body — plain text or HTML string |
| `--body-file` | No* | — | Path to a file to use as the email body. Mutually exclusive with `--body`. |
| `--sender` | No | `<user>@<host.domain>` | Sender address (SMTP only) |
| `--cc` | No | — | CC address. Repeat flag for multiple. |
| `--bcc` | No | — | BCC address. Repeat flag for multiple. |
| `--reply-to` | No | — | Reply-To address (SMTP only) |
| `--attachments` | No | — | File path to attach. Repeat flag for multiple. |
| `--html` / `--no-html` | No | `--no-html` | Treat body as HTML |
| `--dry-run` | No | off | Preview the email without sending |
| `--port` | No | `25` | SMTP port. Use `587` for STARTTLS. |
| `--username` | No | `$AUTOEMAIL_USERNAME` | SMTP login username |
| `--password` | No | `$AUTOEMAIL_PASSWORD` | SMTP login password (hidden in prompts) |
| `--tls` / `--no-tls` | No | `--no-tls` | Enable STARTTLS |
| `--version` | No | — | Print version and exit |

*Exactly one of `--body` or `--body-file` is required.

## Examples

=== "Basic send"

    ```bash
    autoemail --type smtp --host Domain1 \
      --subject "Weekly Report" \
      --recipients user@hr.acme.com \
      --body "Please find this week's report below."
    ```

=== "Multiple recipients"

    ```bash
    autoemail --type smtp --host Domain1 \
      --subject "Q1 Summary" \
      --recipients alice@hr.acme.com \
      --recipients bob@hr.acme.com \
      --cc manager@hr.acme.com \
      --body "Q1 summary is attached." \
      --attachments /path/to/q1-summary.pdf
    ```

=== "External relay + TLS"

    ```bash
    export AUTOEMAIL_USERNAME=me@example.com
    export AUTOEMAIL_PASSWORD=secret

    autoemail --type smtp \
      --host smtp.gmail.com:gmail.com \
      --port 587 --tls \
      --subject "Test" \
      --recipients friend@example.com \
      --body "Hello from the CLI"
    ```

=== "Body from file"

    ```bash
    autoemail --type smtp --host Domain1 \
      --subject "Report" \
      --recipients user@hr.acme.com \
      --body-file /path/to/report-body.html \
      --html
    ```

=== "Dry-run preview"

    ```bash
    autoemail --type smtp --host Domain1 \
      --subject "Test" \
      --recipients user@hr.acme.com \
      --body "Hello" \
      --dry-run
    ```

!!! warning "Credentials in shell history"
    Prefer `AUTOEMAIL_USERNAME` / `AUTOEMAIL_PASSWORD` environment variables over
    the `--username` / `--password` flags. Inline flags appear in shell history
    and `ps` output, making them unsuitable for shared or production systems.
