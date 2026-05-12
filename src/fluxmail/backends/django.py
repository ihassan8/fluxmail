from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

from ..fluxmail import FluxMail


class FluxMailBackend(BaseEmailBackend):
    """Django email backend using FluxMail for SMTP delivery.

    Configure in Django settings::

        EMAIL_BACKEND = "fluxmail.backends.django.FluxMailBackend"
        EMAIL_HOST = "smtp.gmail.com"
        EMAIL_PORT = 587
        EMAIL_HOST_USER = "me@gmail.com"
        EMAIL_HOST_PASSWORD = "secret"
        EMAIL_USE_TLS = True

    Optional FluxMail-specific settings::

        EMAIL_FLUXMAIL_MAX_RETRIES = 3
        EMAIL_FLUXMAIL_RETRY_DELAY = 1.0
    """

    def __init__(self, fail_silently: bool = False, **kwargs) -> None:
        super().__init__(fail_silently=fail_silently, **kwargs)
        self._mailer = self._create_mailer()
        self._connection_open = False

    def _create_mailer(self) -> FluxMail:
        return FluxMail(
            object_type="smtp",
            host=getattr(settings, "EMAIL_HOST", "localhost"),
            port=int(getattr(settings, "EMAIL_PORT", 25)),
            username=getattr(settings, "EMAIL_HOST_USER", None) or None,
            password=getattr(settings, "EMAIL_HOST_PASSWORD", None) or None,
            use_tls=getattr(settings, "EMAIL_USE_TLS", False),
            use_ssl=getattr(settings, "EMAIL_USE_SSL", False),
            timeout=int(getattr(settings, "EMAIL_TIMEOUT", 30)),
            max_retries=int(getattr(settings, "EMAIL_FLUXMAIL_MAX_RETRIES", 0)),
            retry_delay=float(getattr(settings, "EMAIL_FLUXMAIL_RETRY_DELAY", 1.0)),
        )

    def open(self) -> bool:
        """Open a persistent SMTP connection.

        Returns ``True`` if a new connection was opened, ``False`` if already open.
        """
        if self._connection_open:
            return False
        self._mailer.__enter__()
        self._connection_open = True
        return True

    def close(self) -> None:
        """Close the persistent SMTP connection."""
        if not self._connection_open:
            return
        self._mailer.__exit__(None, None, None)
        self._connection_open = False

    def send_messages(self, email_messages) -> int:
        """Send Django EmailMessage objects via FluxMail transport.

        Uses Django's ``EmailMessage.message()`` to build the stdlib MIME message
        and passes it directly to ``_transport.send()``, preserving Django's full
        MIME logic (attachments, multipart, etc.).

        Returns the number of messages successfully sent.
        """
        sent = 0
        for msg in email_messages:
            try:
                self._mailer._transport.send(msg.message())
                sent += 1
            except Exception:
                if not self.fail_silently:
                    raise
        return sent
