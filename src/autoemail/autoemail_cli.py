from typing import List, Optional

import typer
from typing_extensions import Annotated

from . import __version__
from .autoemail import AutoEmail, AutoEmailException, EmailObject
from .utils import EmailEnv, EmailInstance, str_to_enum

app = typer.Typer(
    name="autoemail",
    help="Send emails via SMTP or Outlook.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


def _resolve_host(host_str: str) -> "EmailEnv | EmailInstance":
    """Try built-in EmailEnv first; fall back to custom relay:domain syntax.

    Parameters
    ----------
    host_str : str
        Host string — either an ``EmailEnv`` member name (e.g. ``"Domain1"``)
        or a custom relay in ``relay:domain`` format (e.g. ``"smtp.gmail.com:gmail.com"``).

    Returns
    -------
    EmailEnv or EmailInstance
        Resolved host object.

    Raises
    ------
    typer.BadParameter
        If the string does not match a known ``EmailEnv`` and is not in ``relay:domain`` format.
    """
    try:
        return str_to_enum(EmailEnv, host_str)
    except ValueError:
        pass
    if ":" in host_str:
        relay, domain = host_str.split(":", 1)
        return EmailInstance(relay=relay.strip(), domain=domain.strip())
    raise typer.BadParameter(
        f"Unknown host '{host_str}'. Use Domain1/Domain2/Domain3 "
        f"or a custom relay as 'relay:domain' (e.g. [bold]smtp.gmail.com:gmail.com[/bold])."
    )


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
                "Host environment ([bold]Domain1[/bold], [bold]Domain2[/bold], [bold]Domain3[/bold]) "
                "or a custom relay as [bold]relay:domain[/bold] (e.g. smtp.gmail.com:gmail.com)."
            )
        ),
    ],
    subject: Annotated[str, typer.Option(help="Email subject.")],
    recipients: Annotated[List[str], typer.Option("--recipients", help="Recipient email addresses.")],
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
        typer.Option(help="Sender address (SMTP only). Defaults to <current_user>@<host.domain>."),
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
        typer.Option(help="SMTP username.", envvar="AUTOEMAIL_USERNAME"),
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

      [dim]# Built-in relay[/dim]
      autoemail --type smtp --host Domain1 --subject "Hi" --recipients user@hr.acme.com --body "Hello"

      [dim]# Custom relay with TLS auth (credentials from env vars)[/dim]
      AUTOEMAIL_USERNAME=me@gmail.com AUTOEMAIL_PASSWORD=secret \\
        autoemail --type smtp --host smtp.gmail.com:gmail.com --port 587 --tls \\
        --subject "Hi" --recipients friend@example.com --body "Hello"

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

    try:
        email_host = _resolve_host(host)
    except typer.BadParameter as e:
        typer.echo(f"[ERROR] Invalid --host: {e}", err=True)
        raise typer.Exit(1)

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
