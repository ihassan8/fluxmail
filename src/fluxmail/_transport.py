import logging
import smtplib
import ssl as _ssl
from typing import Optional

import aiosmtplib


class _SMTPTransport:
    """Private SMTP connection manager — sync and async SMTP connection logic."""

    def __init__(
        self,
        relay: str,
        port: int,
        *,
        use_ssl: bool,
        use_tls: bool,
        ssl_context: Optional[_ssl.SSLContext],
        timeout: int,
        username: Optional[str],
        password: Optional[str],
        logger: logging.Logger,
    ) -> None:
        self._relay = relay
        self._port = port
        self._use_ssl = use_ssl
        self._use_tls = use_tls
        self._ssl_context = ssl_context
        self._timeout = timeout
        self._username = username
        self._password = password
        self._logger = logger
        self._conn: Optional[smtplib.SMTP] = None

    def _make_connection(self) -> smtplib.SMTP:
        tls_mode = "implicit-TLS" if self._use_ssl else ("STARTTLS" if self._use_tls else "plain")
        self._logger.debug(
            "Connecting to %s:%d (%s, timeout=%ds)",
            self._relay, self._port, tls_mode, self._timeout,
        )
        if self._use_ssl:
            conn: smtplib.SMTP = smtplib.SMTP_SSL(
                self._relay, self._port,
                context=self._ssl_context,
                timeout=self._timeout,
            )
        else:
            conn = smtplib.SMTP(self._relay, self._port, timeout=self._timeout)
            if self._use_tls:
                conn.starttls(context=self._ssl_context)
                self._logger.debug("STARTTLS negotiated with %s", self._relay)
        if self._username and self._password:
            conn.login(self._username, self._password)
            self._logger.debug("Authenticated as %s", self._username)
        return conn

    def send(self, message) -> None:
        if self._conn is not None:
            self._logger.debug("Sending via persistent connection to %s:%d", self._relay, self._port)
            self._conn.send_message(message)
        else:
            self._logger.debug("Sending via transient connection to %s:%d", self._relay, self._port)
            conn = self._make_connection()
            try:
                conn.send_message(message)
            finally:
                try:
                    conn.quit()
                except Exception:
                    pass

    def open(self) -> None:
        self._logger.debug("Opening persistent SMTP connection to %s:%d", self._relay, self._port)
        self._conn = self._make_connection()

    def close(self) -> None:
        if self._conn is not None:
            self._logger.debug("Closing persistent SMTP connection to %s:%d", self._relay, self._port)
            try:
                self._conn.quit()
            except Exception:
                pass
            self._conn = None

    async def send_async(self, message) -> None:
        tls_mode = "implicit-TLS" if self._use_ssl else ("STARTTLS" if self._use_tls else "plain")
        self._logger.debug(
            "Sending async to %s:%d (%s)",
            self._relay, self._port, tls_mode,
        )
        await aiosmtplib.send(
            message,
            hostname=self._relay,
            port=self._port,
            use_tls=self._use_ssl,
            start_tls=True if self._use_tls else None,
            username=self._username if (self._username and self._password) else None,
            password=self._password if (self._username and self._password) else None,
            timeout=self._timeout,
            tls_context=self._ssl_context,
        )
