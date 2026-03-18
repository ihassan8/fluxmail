from typing import List, Optional

import typer
from typing_extensions import Annotated

from . import __version__
from .autoemail import AutoEmail, AutoEmailException, EmailObject
from .utils import EmailInstance, str_to_enum

app = typer.Typer(
    name="autoemail",
    help="Send emails via SMTP or Outlook.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


def _resolve_host(host_str: str) -> EmailInstance:
    """Parse a host string into an ``EmailInstance``.

    Accepts either a bare relay hostname or a ``relay:domain`` pair.

    Parameters
    ----------
    host_str : str
        Relay hostname (e.g. ``"smtp.gmail.com"``) or
        ``"relay:domain"`` pair (e.g. ``"smtp.gmail.com:gmail.com"``).

    Returns
    -------
    EmailInstance
        Parsed host object.
    """
    if ":" in host_str:
        relay, domain = host_str.split(":", 1)
        return EmailInstance(relay=relay.strip(), domain=domain.strip())
    return EmailInstance(relay=host_str.strip())


def _version_callback(value: bool):
    if value:
        typer.echo(f"autoemail {__version__}")
        raise typer.Exit()


@app.command()
def send(
    # ── Required ────────────────────────────────────────────────────────────
    email_type: Annotated[
        str,
        typer.Option("--type", help="Email protocol: [bold]smtp[/bold] or [bold]outlook[/bold]"),
    ],
    host: Annotated[
        str,
        typer.Option(
            help=(
                "SMTP relay hostname (e.g. [bold]smtp.gmail.com[/bold]) or a "
                "[bold]relay:domain[/bold] pair (e.g. [bold]smtp.gmail.com:gmail.com[/bold])."
            )
        ),
    ],
    subject: Annotated[str, typer.Option(help="Email subject.")],
    recipients: Annotated[List[str], typer.Option("--recipients", help="Recipient email addresses.")],
    # ── Body (one of --body or --body-file is required) ──────────────────────
    body: Annotated[
        Optional[str],
        typer.Option(help="Email body — plain text or HTML string."),
    ] = None,
    body_file: Annotated[
        Optional[str],
        typer.Option(
            "--body-file",
            help="Path to a file whose content becomes the email body. "
                 "Mutually exclusive with --body.",
        ),
    ] = None,
    # ── Content (optional) ──────────────────────────────────────────────────
    sender: Annotated[
        Optional[str],
        typer.Option(
            help=(
                "Sender address (SMTP only). Defaults to [bold]--username[/bold] "
                "when it is a valid email address."
            )
        ),
    ] = None,
    cc: Annotated[Optional[List[str]], typer.Option(help="CC email addresses.")] = None,
    bcc: Annotated[Optional[List[str]], typer.Option(help="BCC email addresses.")] = None,
    reply_to: Annotated[
        Optional[str], typer.Option("--reply-to", help="Reply-To address (SMTP only).")
    ] = None,
    attachments: Annotated[
        Optional[List[str]], typer.Option(help="Paths to files to attach.")
    ] = None,
    html: Annotated[bool, typer.Option("--html/--no-html", help="Treat body as HTML.")] = False,
    dry_run: Annotated[
        bool, typer.Option("--dry-run/--no-dry-run", help="Preview the email without sending.")
    ] = False,
    # ── SMTP connection ──────────────────────────────────────────────────────
    port: Annotated[int, typer.Option(help="SMTP port. Use 587 for STARTTLS.")] = 25,
    username: Annotated[
        Optional[str],
        typer.Option(
            help=(
                "SMTP username. When this is a valid email address it also serves "
                "as the default sender if [bold]--sender[/bold] is not set."
            ),
            envvar="AUTOEMAIL_USERNAME",
        ),
    ] = None,
    password: Annotated[
        Optional[str],
        typer.Option(
            help="SMTP password. Reads from [bold]AUTOEMAIL_PASSWORD[/bold] env var if not set.",
            envvar="AUTOEMAIL_PASSWORD",
            hide_input=True,
        ),
    ] = None,
    tls: Annotated[bool, typer.Option("--tls/--no-tls", help="Enable STARTTLS.")] = False,
    # ── Meta ────────────────────────────────────────────────────────────────
    version: Annotated[
        bool,
        typer.Option(
            "--version", callback=_version_callback, is_eager=True,
            help="Show version and exit."
        ),
    ] = False,
):
    """Send an email via SMTP or Outlook.

    [bold]Examples:[/bold]

      [dim]# Gmail with TLS (credentials from env vars)[/dim]
      AUTOEMAIL_USERNAME=me@gmail.com AUTOEMAIL_PASSWORD=secret \\
        autoemail --type smtp --host smtp.gmail.com --port 587 --tls \\
        --subject "Hi" --recipients friend@example.com --body "Hello"

      [dim]# Explicit relay:domain pair[/dim]
      autoemail --type smtp --host smtp.myrelay.com:mycompany.com \\
        --subject "Hi" --recipients user@mycompany.com --body "Hello" \\
        --sender noreply@mycompany.com

      [dim]# Dry run (preview without sending)[/dim]
      autoemail ... --dry-run
    """
    if body and body_file:
        typer.echo("[ERROR] --body and --body-file are mutually exclusive.", err=True)
        raise typer.Exit(1)

    if body_file:
        try:
            with open(body_file, "r", encoding="utf-8") as fh:
                body = fh.read()
        except OSError as exc:
            typer.echo(f"[ERROR] Cannot read --body-file: {exc}", err=True)
            raise typer.Exit(1)

    if not body:
        typer.echo("[ERROR] Either --body or --body-file is required.", err=True)
        raise typer.Exit(1)

    try:
        email_obj = str_to_enum(EmailObject, email_type)
    except ValueError as e:
        typer.echo(f"[ERROR] Invalid --type: {e}", err=True)
        raise typer.Exit(1)

    email_host = _resolve_host(host)

    try:
        email = AutoEmail(
            object_type=email_obj,
            host=email_host,
            port=port,
            username=username,
            password=password,
            use_tls=tls,
        )
        email.create(
            subject=subject,
            recipients=recipients,
            body=body,
            sender=sender,
            cc=cc,
            bcc=bcc,
            reply_to=reply_to,
            attachments=attachments,
            html_body=html,
        )
        result = email.send(dry_run=dry_run)
        typer.echo(result)
    except AutoEmailException as e:
        typer.echo(f"[AutoEmail ERROR] {e}", err=True)
        raise typer.Exit(2)
    except Exception as e:
        typer.echo(f"[UNEXPECTED ERROR] {e}", err=True)
        raise typer.Exit(99)


def main():
    app()


if __name__ == "__main__":
    main()
