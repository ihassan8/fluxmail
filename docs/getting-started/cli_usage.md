# CLI Usage

Send emails directly from the terminal with the `autoemail` command.
Run `autoemail --help` for full usage with formatted output.

## Flags

| Flag | Required | Default | Description |
|------|----------|---------|-------------|
| `--type` | Yes | — | Email protocol: `smtp` or `outlook` |
| `--host` | Yes | — | SMTP relay hostname (e.g. `smtp.gmail.com`) or `relay:domain` pair (e.g. `smtp.gmail.com:gmail.com`) |
| `--subject` | Yes | — | Email subject line |
| `--recipients` | Yes | — | Recipient address. Repeat flag for multiple. |
| `--body` | No* | — | Email body — plain text or HTML string |
| `--body-file` | No* | — | Path to a file to use as the email body. Mutually exclusive with `--body`. |
| `--sender` | No | username (if valid email) | Sender address (SMTP only) |
| `--cc` | No | — | CC address. Repeat flag for multiple. |
| `--bcc` | No | — | BCC address. Repeat flag for multiple. |
| `--reply-to` | No | — | Reply-To address (SMTP only) |
| `--attachments` | No | — | File path to attach. Repeat flag for multiple. |
| `--html` / `--no-html` | No | `--no-html` | Treat body as HTML |
| `--dry-run` | No | off | Preview the email without sending |
| `--port` | No | `25` | SMTP port. Use `587` for STARTTLS. |
| `--username` | No | `$AUTOEMAIL_USERNAME` | SMTP login username. When this is a valid email it also sets the default sender. |
| `--password` | No | `$AUTOEMAIL_PASSWORD` | SMTP login password (hidden in prompts) |
| `--tls` / `--no-tls` | No | `--no-tls` | Enable STARTTLS |
| `--version` | No | — | Print version and exit |

*Exactly one of `--body` or `--body-file` is required.

## Examples

=== "Gmail with TLS"

    ```bash
    export AUTOEMAIL_USERNAME=me@gmail.com
    export AUTOEMAIL_PASSWORD=secret

    autoemail --type smtp --host smtp.gmail.com --port 587 --tls \
      --subject "Hello" \
      --recipients friend@example.com \
      --body "Hi from the CLI!"
    ```

=== "SendGrid (API key auth)"

    ```bash
    export AUTOEMAIL_USERNAME=apikey
    export AUTOEMAIL_PASSWORD=SG.xxxx

    autoemail --type smtp --host smtp.sendgrid.net --port 587 --tls \
      --subject "Notification" \
      --recipients user@example.com \
      --sender noreply@myapp.com \
      --body "Your order has shipped."
    ```

=== "Multiple recipients + CC"

    ```bash
    autoemail --type smtp --host smtp.gmail.com --port 587 --tls \
      --subject "Q1 Summary" \
      --recipients alice@example.com \
      --recipients bob@example.com \
      --cc manager@example.com \
      --body "Q1 summary is attached." \
      --attachments /path/to/q1-summary.pdf \
      --username me@gmail.com
    ```

=== "Body from file"

    ```bash
    autoemail --type smtp --host smtp.gmail.com --port 587 --tls \
      --subject "Report" \
      --recipients user@example.com \
      --body-file /path/to/report-body.html \
      --html \
      --username me@gmail.com
    ```

=== "Dry-run preview"

    ```bash
    autoemail --type smtp --host smtp.gmail.com --port 587 --tls \
      --subject "Test" \
      --recipients user@example.com \
      --body "Hello" \
      --username me@gmail.com \
      --dry-run
    ```

!!! warning "Credentials in shell history"
    Prefer `AUTOEMAIL_USERNAME` / `AUTOEMAIL_PASSWORD` environment variables over
    the `--username` / `--password` flags. Inline flags appear in shell history
    and `ps` output, making them unsuitable for shared or production systems.
