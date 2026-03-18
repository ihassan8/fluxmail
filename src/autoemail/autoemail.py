import logging
import mimetypes
import os
import platform
import smtplib
from email.message import EmailMessage
from typing import List, Optional, Tuple, Union

# Windows-only dependency for Outlook
if platform.system() == "Windows":
    import win32com.client as win32
else:
    win32 = None

from pylogshield import get_logger

from .utils import (
    AutoEmailException,
    EmailEnv,
    EmailInstance,
    EmailObject,
    detect_host,
    detect_domain_mismatch,
    get_current_user,
    str_to_enum,
    validate_email,
)


class AutoEmail:
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
    )

    def __init__(
        self,
        object_type: Union[EmailObject, str],
        host: Union[EmailEnv, EmailInstance, str, None] = None,
        logger: Optional[logging.Logger] = None,
        log_level: str = "WARNING",
        detect_domain_mismatches: bool = False,
        port: int = 25,
        username: Optional[str] = None,
        password: Optional[str] = None,
        use_tls: bool = False,
    ):
        """Initializes the AutoEmail class.

        Parameters
        ----------
        object_type : Union[EmailObject, str]
            Email object type: ``smtp`` or ``outlook``.
        host : Union[EmailEnv, EmailInstance, str, None], optional
            SMTP relay host. Accepts an ``EmailEnv`` member, an
            ``EmailInstance(relay=..., domain=...)`` for custom servers, a string name
            (e.g. ``"Domain1"``), or ``None`` to auto-detect.
        logger : logging.Logger, optional
            Logger instance for logging.
        log_level : str, optional
            Logging level string (e.g. ``"DEBUG"``, ``"INFO"``, ``"WARNING"``, ``"ERROR"``).
            Default: ``"WARNING"``.
        detect_domain_mismatches : bool, optional
            Raise an error if the machine's domain does not match the selected host.
            Default: ``False``.
        port : int, optional
            SMTP port. Default: ``25``. Use ``587`` for STARTTLS.
        username : str, optional
            SMTP login username.
        password : str, optional
            SMTP login password.
        use_tls : bool, optional
            Enable STARTTLS for the SMTP connection. Default: ``False``.

        Raises
        ------
        AutoEmailException
            If ``host`` is ``None`` and cannot be auto-detected.
        AutoEmailException
            If Outlook is used on a non-Windows OS.
        """
        self.object_type = str_to_enum(EmailObject, object_type)
        self.port = port
        self.username = username
        self.password = password
        self.use_tls = use_tls

        if host is None:
            self.host = detect_host()
        elif isinstance(host, EmailEnv):
            self.host = host
        elif isinstance(host, EmailInstance):
            self.host = host
        elif isinstance(host, str):
            self.host = str_to_enum(EmailEnv, host)
        else:
            raise TypeError(
                f"host must be EmailEnv, EmailInstance, or str, got {type(host).__name__}"
            )

        if detect_domain_mismatches and isinstance(self.host, EmailEnv):
            detect_domain_mismatch(self.host)

        if logger and not isinstance(logger, logging.Logger):
            raise AutoEmailException(
                "logger must be an instance of logging.Logger. "
                "Use get_logger() from pylogshield or Python's standard logging module."
            )

        self.logger = logger or get_logger("autoemail", log_level=log_level)
        self.log_level = log_level
        self.message = None
        self.is_created = False

        self.logger.debug("Initializing AutoEmail instance...")

        if self.is_smtp():
            self.message = EmailMessage()
        elif self.is_outlook():
            if win32 is None:
                raise AutoEmailException("Outlook is only supported on Windows OS.")
            ol_app = win32.Dispatch("outlook.application")
            self.message = ol_app.CreateItem(0)

    def is_smtp(self) -> bool:
        return self.object_type == EmailObject.SMTP

    def is_outlook(self) -> bool:
        return self.object_type == EmailObject.OUTLOOK

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
    ) -> "AutoEmail":
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
            Sender address. Defaults to ``<current_user>@<host.domain>``.
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

        Returns
        -------
        AutoEmail
            Returns ``self`` to support method chaining.
        """
        self.subject = subject
        self.recipients = recipients
        self.body = body
        self.sender = sender
        self.cc = cc
        self.bcc = bcc
        self.reply_to = reply_to
        self.input_path = attachments
        self.html_body = html_body

        self._validate_parameters()
        self._handle_sender()
        self._handle_recipient()
        self._handle_cc()
        self._handle_bcc()
        self._handle_reply_to()
        self._set_content_type()
        self._attach_files()
        self.is_created = True
        return self

    def _handle_sender(self):
        if self.is_smtp():
            if self.sender:
                self.sender = validate_email(self.sender, self.host, gov_email=True)
            else:
                try:
                    self.sender = f"{get_current_user()}@{self.host.domain}"
                except Exception as e:
                    msg = f"Failed to get current user. Please use the sender parameter. Error: {e}"
                    self.logger.error(msg)
                    raise AutoEmailException(msg)

            self.message["From"] = self.sender

        elif self.is_outlook() and self.sender:
            msg = "Outlook does not support setting the sender address."
            self.logger.error(msg)
            raise AutoEmailException(msg)

    def _handle_recipient(self):
        validated = [
            validate_email(email, self.host, gov_email=(self.host != EmailEnv.Domain1))
            for email in self.recipients
        ]
        if self.is_smtp():
            self.message["To"] = ", ".join(validated)
        elif self.is_outlook():
            self.message.To = ";".join(validated)

    def _handle_cc(self):
        if self.cc:
            validated = [
                validate_email(email, self.host, gov_email=(self.host != EmailEnv.Domain1))
                for email in self.cc
            ]
            if self.is_smtp():
                self.message["Cc"] = ", ".join(validated)
            elif self.is_outlook():
                self.message.Cc = ";".join(validated)

    def _handle_bcc(self):
        if self.bcc:
            validated = [
                validate_email(email, self.host, gov_email=False)
                for email in self.bcc
            ]
            if self.is_smtp():
                self.message["Bcc"] = ", ".join(validated)
            elif self.is_outlook():
                self.message.BCC = ";".join(validated)

    def _handle_reply_to(self):
        if self.reply_to:
            validated = validate_email(self.reply_to, self.host, gov_email=False)
            if self.is_smtp():
                self.message["Reply-To"] = validated
            # Outlook COM does not expose a Reply-To field

    def _validate_parameters(self):
        if not self.subject:
            raise AutoEmailException("Subject is required.")
        if not isinstance(self.recipients, list) or not self.recipients:
            raise AutoEmailException("Recipients must be a non-empty list.")
        if self.cc and not isinstance(self.cc, list):
            raise AutoEmailException("CC must be a list.")
        if self.bcc and not isinstance(self.bcc, list):
            raise AutoEmailException("BCC must be a list.")
        if self.input_path and not isinstance(self.input_path, list):
            raise AutoEmailException("Attachments must be a list.")

        if self.is_smtp():
            self.message["Subject"] = self.subject
        elif self.is_outlook():
            self.message.Subject = self.subject

    def _set_content_type(self):
        if self.is_smtp():
            self.message.set_content(self.body, subtype="html" if self.html_body else "plain")
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
                    raise AutoEmailException(f"Attachment not found: {file_path}")
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
            raise AutoEmailException(msg)

    def display(self) -> str:
        """Displays or returns an email preview.

        Returns
        -------
        str
            Email preview string.

        Raises
        ------
        AutoEmailException
            If ``create()`` has not been called or display fails.
        """
        if not self.is_created:
            raise AutoEmailException("Call create() before display().")
        try:
            if self.is_smtp():
                return f"Email Preview:\n{self.message}"
            elif self.is_outlook():
                self.message.Display()
                return "Outlook email displayed successfully."
        except AutoEmailException:
            raise
        except Exception as e:
            msg = f"Display failed: {e}"
            self.logger.error(msg)
            raise AutoEmailException(msg)

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
        AutoEmailException
            If ``create()`` has not been called, or on send failure.
        """
        if not self.is_created:
            raise AutoEmailException("Call create() before send().")
        if dry_run:
            return self.display()

        try:
            if self.is_smtp() and self.host.relay:
                with smtplib.SMTP(self.host.relay, self.port) as smtp:
                    if self.use_tls:
                        smtp.starttls()
                    if self.username and self.password:
                        smtp.login(self.username, self.password)
                    smtp.send_message(self.message)
                return "Email sent successfully via SMTP."
            elif self.is_outlook():
                raise AutoEmailException(
                    "Outlook requires user interaction to send emails and cannot send programmatically."
                )
        except AutoEmailException:
            raise
        except Exception as e:
            msg = f"Send failed: {e}"
            self.logger.error(msg)
            raise AutoEmailException(msg)

    def __repr__(self) -> str:
        return (
            f"AutoEmail(object_type={self.object_type}, host={self.host}, "
            f"logger={self.logger}, log_level={self.log_level})"
        )
