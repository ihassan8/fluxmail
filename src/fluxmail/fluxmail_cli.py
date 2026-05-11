from typing import List, Optional

import typer
from typing_extensions import Annotated

from . import __version__
from .fluxmail import FluxMail, FluxMailException, EmailObject
from .utils import str_to_enum

app = typer.Typer(
    name="fluxmail",
    help="Send emails via SMTP or Outlook.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


def _version_callback(value: bool):
    if value:
        typer.echo(f"fluxmail {__version__}")
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
            envvar="FLUXMAIL_USERNAME",
        ),
    ] = None,
    password: Annotated[
        Optional[str],
        typer.Option(
            help="SMTP password. Reads from [bold]FLUXMAIL_PASSWORD[/bold] env var if not set.",
            envvar="FLUXMAIL_PASSWORD",
            hide_input=True,
        ),
    ] = None,
    tls: Annotated[bool, typer.Option("--tls/--no-tls", help="Enable STARTTLS.")] = False,
    ssl: Annotated[
        bool,
        typer.Option("--ssl/--no-ssl",
                     help="Use implicit TLS (port 465). Mutually exclusive with --tls."),
    ] = False,
    timeout: Annotated[
        int,
        typer.Option(help="SMTP connection timeout in seconds."),
    ] = 30,
    max_retries: Annotated[
        int,
        typer.Option("--max-retries", help="Number of send retries on failure."),
    ] = 0,
    retry_delay: Annotated[
        float,
        typer.Option("--retry-delay", help="Seconds to wait between retries."),
    ] = 1.0,
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
      FLUXMAIL_USERNAME=me@gmail.com FLUXMAIL_PASSWORD=secret \\
        fluxmail --type smtp --host smtp.gmail.com --port 587 --tls \\
        --subject "Hi" --recipients friend@example.com --body "Hello"

      [dim]# Explicit relay:domain pair[/dim]
      fluxmail --type smtp --host smtp.myrelay.com:mycompany.com \\
        --subject "Hi" --recipients user@mycompany.com --body "Hello" \\
        --sender noreply@mycompany.com

      [dim]# Dry run (preview without sending)[/dim]
      fluxmail ... --dry-run
    """
    if body and body_file:
        typer.echo("[ERROR] --body and --body-file are mutually exclusive.", err=True)
        raise typer.Exit(1)

    if tls and ssl:
        typer.echo("[ERROR] --tls and --ssl are mutually exclusive.", err=True)
        raise typer.Exit(2)

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

    try:
        email = FluxMail(
            object_type=email_obj,
            host=host,
            port=port,
            username=username,
            password=password,
            use_tls=tls,
            use_ssl=ssl,
            timeout=timeout,
            max_retries=max_retries,
            retry_delay=retry_delay,
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
    except FluxMailException as e:
        typer.echo(f"[FluxMail ERROR] {e}", err=True)
        raise typer.Exit(2)
    except Exception as e:
        typer.echo(f"[UNEXPECTED ERROR] {e}", err=True)
        raise typer.Exit(99)


def main():
    app()


if __name__ == "__main__":
    main()
