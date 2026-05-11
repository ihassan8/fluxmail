import smtplib
import ssl as _ssl
from typing import Optional


class _SMTPTransport:
    """Private SMTP connection manager — sync path only (async added separately)."""

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
    ) -> None:
        self._relay = relay
        self._port = port
        self._use_ssl = use_ssl
        self._use_tls = use_tls
        self._ssl_context = ssl_context
        self._timeout = timeout
        self._username = username
        self._password = password
        self._conn: Optional[smtplib.SMTP] = None

    def _make_connection(self) -> smtplib.SMTP:
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
        if self._username and self._password:
            conn.login(self._username, self._password)
        return conn

    def send(self, message) -> None:
        if self._conn is not None:
            self._conn.send_message(message)
        else:
            conn = self._make_connection()
            try:
                conn.send_message(message)
            finally:
                try:
                    conn.quit()
                except Exception:
                    pass

    def open(self) -> None:
        self._conn = self._make_connection()

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.quit()
            except Exception:
                pass
            self._conn = None
