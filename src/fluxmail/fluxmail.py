import logging
import mimetypes
import os
import platform
import ssl
from email.message import EmailMessage
from email.utils import make_msgid
from typing import List, Optional, Tuple, Union

# Windows-only dependency for Outlook
if platform.system() == "Windows":
    import win32com.client as win32
else:
    win32 = None

from pylogshield import get_logger
from tenacity import Retrying, stop_after_attempt, wait_fixed

from ._transport import _SMTPTransport
from .utils import (
    FluxMailException,
    EMAIL_REGEX,
    EmailInstance,
    EmailObject,
    str_to_enum,
    validate_email,
)


_PRIORITY_MAP = {
    "high":   ("1", "High",   "High"),
    "normal": ("3", "Normal", "Normal"),
    "low":    ("5", "Low",    "Low"),
}


class FluxMail:
    """Automates email creation and sending using SMTP or Outlook."""

    __slots__ = (
        "object_type",
        "host",
        "logger",
        "log_level",
        "message",
        "is_created",
        "subject",
        "recipients",
        "body",
        "plain_body",
        "sender",
        "cc",
        "bcc",
        "reply_to",
        "input_path",
        "html_body",
        "port",
        "username",
        "password",
        "use_tls",
        "use_ssl",
        "ssl_context",
        "timeout",
        "max_retries",
        "retry_delay",
        "in_reply_to",
        "references",
        "priority",
        "_transport",
    )

    def __init__(
        self,
        object_type: Union[EmailObject, str],
        host: Union[EmailInstance, str],
        logger: Optional[logging.Logger] = None,
        log_level: str = "WARNING",
        port: int = 25,
        username: Optional[str] = None,
        password: Optional[str] = None,
        use_tls: bool = False,
        use_ssl: bool = False,
        ssl_context: Optional[ssl.SSLContext] = None,
        timeout: int = 30,
        max_retries: int = 0,
        retry_delay: float = 1.0,
    ):
        """Initializes the FluxMail class.

        Parameters
        ----------
        object_type : Union[EmailObject, str]
            Email object type: ``smtp`` or ``outlook``.
        host : Union[EmailInstance, str]
            SMTP relay host. Accepts an ``EmailInstance(relay=..., domain=...)``
            namedtuple, a bare relay hostname string (e.g. ``"smtp.gmail.com"``),
            or a ``"relay:domain"`` string (e.g. ``"smtp.gmail.com:gmail.com"``).
        logger : logging.Logger, optional
            Logger instance for logging.
        log_level : str, optional
            Logging level string (e.g. ``"DEBUG"``, ``"INFO"``, ``"WARNING"``, ``"ERROR"``).
            Default: ``"WARNING"``.
        port : int, optional
            SMTP port. Default: ``25``. Use ``587`` for STARTTLS.
        username : str, optional
            SMTP login username. When this is a valid email address it also
            serves as the default ``From`` address if ``sender`` is not provided
            in :meth:`create`.
        password : str, optional
            SMTP login password.
        use_tls : bool, optional
            Enable STARTTLS for the SMTP connection. Default: ``False``.
        use_ssl : bool, optional
            Enable implicit TLS (SSL) for the SMTP connection (port 465). Default: ``False``.
            Mutually exclusive with ``use_tls``.
        ssl_context : ssl.SSLContext, optional
            Custom SSL context for TLS/SSL connections. Default: ``None``.
        timeout : int, optional
            Connection timeout in seconds. Default: ``30``.
        max_retries : int, optional
            Number of retry attempts on send failure. ``0`` disables retries. Default: ``0``.
        retry_delay : float, optional
            Seconds to wait between retry attempts. Default: ``1.0``.

        Raises
        ------
        FluxMailException
            If ``host`` is not provided or Outlook is used on a non-Windows OS.
        TypeError
            If ``host`` is not a string or ``EmailInstance``.
        """
        if use_ssl and use_tls:
            raise FluxMailException(
                "use_ssl and use_tls are mutually exclusive — use use_ssl for port 465 "
                "implicit TLS, or use_tls for port 587 STARTTLS.",
                code="invalid_config",
            )

        self.object_type = str_to_enum(EmailObject, object_type)
        self.port = port
        self.username = username
        self.password = password
        self.use_tls = use_tls
        self.use_ssl = use_ssl
        self.ssl_context = ssl_context
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        if isinstance(host, EmailInstance):
            self.host = host
        elif isinstance(host, str):
            if ":" in host:
                relay, domain = host.split(":", 1)
                self.host = EmailInstance(relay=relay.strip(), domain=domain.strip())
            else:
                self.host = EmailInstance(relay=host.strip())
        else:
            raise TypeError(
                f"host must be an EmailInstance or a string, got {type(host).__name__}"
            )

        if logger and not isinstance(logger, logging.Logger):
            raise FluxMailException(
                "logger must be an instance of logging.Logger. "
                "Use get_logger() from pylogshield or Python's standard logging module.",
                code="invalid_config",
            )

        self.logger = logger or get_logger("fluxmail", log_level=log_level)
        self.log_level = log_level
        self.message = None
        self.is_created = False
        self.plain_body = None
        self.in_reply_to = None
        self.references = None
        self.priority = None

        self.logger.debug("Initializing FluxMail instance...")

        if self.is_smtp():
            self.message = EmailMessage()
            self._transport = _SMTPTransport(
                relay=self.host.relay,
                port=self.port,
                use_ssl=use_ssl,
                use_tls=use_tls,
                ssl_context=ssl_context,
                timeout=timeout,
                username=username,
                password=password,
            )
        elif self.is_outlook():
            self._transport = None
            if win32 is None:
                raise FluxMailException(
                    "Outlook is only supported on Windows OS.",
                    code="invalid_config",
                )
            ol_app = win32.Dispatch("outlook.application")
            self.message = ol_app.CreateItem(0)

    def is_smtp(self) -> bool:
        return self.object_type == EmailObject.SMTP

    def is_outlook(self) -> bool:
        return self.object_type == EmailObject.OUTLOOK

    def _handle_message_id(self) -> None:
        if self.is_smtp():
            self.message["Message-ID"] = make_msgid()

    def create(
        self,
        subject: str,
        recipients: List[str],
        body: str,
        sender: Optional[str] = None,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        reply_to: Optional[str] = None,
        attachments: Optional[List[str]] = None,
        html_body: bool = False,
        plain_body: Optional[str] = None,
        in_reply_to: Optional[str] = None,
        references: Optional[List[str]] = None,
        priority: Optional[str] = None,
    ) -> "FluxMail":
        """Creates an email with the specified details.

        Parameters
        ----------
        subject : str
            Email subject.
        recipients : list of str
            Recipient email addresses.
        body : str
            Email content (plain text or HTML).
        sender : str, optional
            Sender address (SMTP only). Defaults to ``username`` if ``username``
            is a valid email address, otherwise this parameter is required.
        cc : list of str, optional
            CC'd email addresses.
        bcc : list of str, optional
            BCC'd email addresses (SMTP only).
        reply_to : str, optional
            Reply-To address (SMTP only).
        attachments : list of str, optional
            Paths to files to attach.
        html_body : bool, optional
            Use HTML format. Default: ``False``.
        plain_body : str, optional
            Plain-text fallback body. When provided alongside ``html_body=True``
            the message is built as ``multipart/alternative``.
        in_reply_to : str, optional
            Message-ID of the email being replied to (SMTP only).
        references : list of str, optional
            List of Message-IDs forming the thread chain (SMTP only).
        priority : str, optional
            Message priority: ``"high"``, ``"normal"``, or ``"low"`` (SMTP only).

        Returns
        -------
        FluxMail
            Returns ``self`` to support method chaining.
        """
        # Reset so create() can be called again on the same instance.
        if self.is_smtp():
            self.message = EmailMessage()
        self.is_created = False

        self.subject = subject
        self.recipients = recipients
        self.body = body
        self.plain_body = plain_body
        self.sender = sender
        self.cc = cc
        self.bcc = bcc
        self.reply_to = reply_to
        self.input_path = attachments
        self.html_body = html_body
        self.in_reply_to = in_reply_to
        self.references = references
        self.priority = priority

        self._validate_parameters()
        self._handle_message_id()
        self._handle_sender()
        self._handle_recipient()
        self._handle_cc()
        self._handle_bcc()
        self._handle_reply_to()
        self._handle_threading()
        self._handle_priority()
        self._set_content_type()
        self._attach_files()
        self.is_created = True
        return self

    def _handle_sender(self):
        if self.is_smtp():
            if self.sender:
                self.sender = validate_email(self.sender)
            elif self.username and EMAIL_REGEX.match(self.username.strip().lower()):
                self.sender = self.username.strip().lower()
            else:
                raise FluxMailException(
                    "sender is required. Pass sender= explicitly, or set username= "
                    "to a valid email address so it can be used as the From address.",
                    code="sender_required",
                )
            self.message["From"] = self.sender

        elif self.is_outlook() and self.sender:
            msg = "Outlook does not support setting the sender address."
            self.logger.error(msg)
            raise FluxMailException(msg, code="outlook_no_sender")

    def _handle_recipient(self):
        validated = [validate_email(email) for email in self.recipients]
        if self.is_smtp():
            self.message["To"] = ", ".join(validated)
        elif self.is_outlook():
            self.message.To = ";".join(validated)

    def _handle_cc(self):
        if self.cc:
            validated = [validate_email(email) for email in self.cc]
            if self.is_smtp():
                self.message["Cc"] = ", ".join(validated)
            elif self.is_outlook():
                self.message.Cc = ";".join(validated)

    def _handle_bcc(self):
        if self.bcc:
            validated = [validate_email(email) for email in self.bcc]
            if self.is_smtp():
                self.message["Bcc"] = ", ".join(validated)
            elif self.is_outlook():
                self.message.BCC = ";".join(validated)

    def _handle_reply_to(self):
        if self.reply_to:
            validated = validate_email(self.reply_to)
            if self.is_smtp():
                self.message["Reply-To"] = validated
            # Outlook COM does not expose a Reply-To field

    def _validate_parameters(self):
        if not self.subject:
            raise FluxMailException("Subject is required.", code="invalid_params")
        if not isinstance(self.recipients, list) or not self.recipients:
            raise FluxMailException("Recipients must be a non-empty list.", code="invalid_params")
        if self.cc and not isinstance(self.cc, list):
            raise FluxMailException("CC must be a list.", code="invalid_params")
        if self.bcc and not isinstance(self.bcc, list):
            raise FluxMailException("BCC must be a list.", code="invalid_params")
        if self.input_path and not isinstance(self.input_path, list):
            raise FluxMailException("Attachments must be a list.", code="invalid_params")
        if self.priority and self.priority not in _PRIORITY_MAP:
            raise FluxMailException(
                f"priority must be one of {list(_PRIORITY_MAP.keys())}, got '{self.priority}'",
                code="invalid_priority",
            )

        if self.is_smtp():
            self.message["Subject"] = self.subject
        elif self.is_outlook():
            self.message.Subject = self.subject

    def _handle_threading(self) -> None:
        if not self.is_smtp():
            return
        if self.in_reply_to:
            self.message["In-Reply-To"] = self.in_reply_to
        if self.references:
            self.message["References"] = " ".join(self.references)

    def _handle_priority(self) -> None:
        if not self.priority or not self.is_smtp():
            return
        x_prio, importance, ms_prio = _PRIORITY_MAP[self.priority]
        self.message["X-Priority"] = x_prio
        self.message["Importance"] = importance
        self.message["X-MSMail-Priority"] = ms_prio

    def _set_content_type(self):
        if self.is_smtp():
            if self.html_body and self.plain_body:
                self.message.set_content(self.plain_body, subtype="plain")
                self.message.add_alternative(self.body, subtype="html")
            else:
                self.message.set_content(
                    self.body, subtype="html" if self.html_body else "plain"
                )
        elif self.is_outlook():
            self.message.BodyFormat = 2 if self.html_body else 1
            if self.html_body:
                self.message.HTMLBody = self.body
            else:
                self.message.Body = self.body

    def _attach_files(self):
        if self.input_path:
            for file_path in self.input_path:
                if not os.path.isfile(file_path):
                    raise FluxMailException(
                        f"Attachment not found: {file_path}",
                        code="attachment_not_found",
                    )
                self._attach_file(file_path)

    def _attach_file(self, file_path: str):
        data, name = self._read_file(file_path)
        if self.is_smtp():
            mime_type, _ = mimetypes.guess_type(file_path)
            maintype, subtype = (mime_type or "application/octet-stream").split("/", 1)
            self.message.add_attachment(data, maintype=maintype, subtype=subtype, filename=name)
        elif self.is_outlook():
            self.message.Attachments.Add(os.path.abspath(file_path))

    def _read_file(self, file: str) -> Tuple[bytes, str]:
        try:
            with open(file, "rb") as fl:
                file_data = fl.read()
            file_name = os.path.basename(file)
            return file_data, file_name
        except Exception as e:
            msg = f"Error reading file '{file}': {e}"
            self.logger.error(msg)
            raise FluxMailException(msg, code="read_error") from e

    def display(self) -> str:
        """Displays or returns an email preview.

        Returns
        -------
        str
            Email preview string.

        Raises
        ------
        FluxMailException
            If ``create()`` has not been called or display fails.
        """
        if not self.is_created:
            raise FluxMailException("Call create() before display().", code="not_created")
        try:
            if self.is_smtp():
                return f"Email Preview:\n{self.message}"
            elif self.is_outlook():
                self.message.Display()
                return "Outlook email displayed successfully."
        except FluxMailException:
            raise
        except Exception as e:
            msg = f"Display failed: {e}"
            self.logger.error(msg)
            raise FluxMailException(msg, code="display_failed") from e

    def send(self, dry_run: bool = False) -> str:
        """Sends or previews the email.

        Parameters
        ----------
        dry_run : bool, optional
            If ``True``, display the email instead of sending it. Default: ``False``.

        Returns
        -------
        str
            Success or preview message.

        Raises
        ------
        FluxMailException
            If ``create()`` has not been called, or on send failure.
        """
        if not self.is_created:
            raise FluxMailException("Call create() before send().", code="not_created")
        if dry_run:
            return self.display()
        if self.is_smtp() and not self.host.relay:
            raise FluxMailException("No SMTP relay configured.", code="no_relay")

        try:
            if self.is_smtp():
                if self.max_retries > 0:
                    for attempt in Retrying(
                        stop=stop_after_attempt(self.max_retries + 1),
                        wait=wait_fixed(self.retry_delay),
                        reraise=True,
                    ):
                        with attempt:
                            self._transport.send(self.message)
                else:
                    self._transport.send(self.message)
                return "Email sent successfully via SMTP."
            elif self.is_outlook():
                raise FluxMailException(
                    "Outlook requires user interaction to send emails and cannot "
                    "send programmatically.",
                    code="outlook_no_send",
                )
        except FluxMailException:
            raise
        except Exception as e:
            msg = f"Send failed: {e}"
            self.logger.error(msg)
            raise FluxMailException(msg, code="send_failed") from e

    def __enter__(self) -> "FluxMail":
        """Open a persistent SMTP connection for reuse across multiple sends."""
        if self._transport is not None:
            self._transport.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        if self._transport is not None:
            self._transport.close()
        return False

    def __repr__(self) -> str:
        return (
            f"FluxMail(object_type={self.object_type}, host={self.host}, "
            f"logger={self.logger}, log_level={self.log_level})"
        )
