import os
import re
import socket
from collections import namedtuple
from enum import Enum
from getpass import getuser
from typing import Type, TypeVar, Union


class AutoEmailException(Exception):
    """Custom exception class for AutoEmail errors."""


class EmailObject(Enum):
    """Supported email object types."""

    OUTLOOK = "outlook"
    """Use ``outlook`` object to create and send email."""
    SMTP = "smtp"
    """Use ``smtp`` object to create and send email."""


EmailInstance = namedtuple("EmailInstance", ["relay", "domain"])


class EmailEnv(EmailInstance, Enum):
    """Supported email environments.

    Relay and domain values can be overridden via environment variables before
    importing the module::

        AUTOEMAIL_DOMAIN1_RELAY   AUTOEMAIL_DOMAIN1_DOMAIN
        AUTOEMAIL_DOMAIN2_RELAY   AUTOEMAIL_DOMAIN2_DOMAIN
        AUTOEMAIL_DOMAIN3_RELAY   AUTOEMAIL_DOMAIN3_DOMAIN

    For fully custom servers pass an ``EmailInstance`` directly to ``AutoEmail(host=...)``.
    """

    Domain1 = EmailInstance(
        relay=os.environ.get("AUTOEMAIL_DOMAIN1_RELAY", "domain1-mail.hr.acme.com"),
        domain=os.environ.get("AUTOEMAIL_DOMAIN1_DOMAIN", "hr.acme.com"),
    )
    Domain2 = EmailInstance(
        relay=os.environ.get("AUTOEMAIL_DOMAIN2_RELAY", "domain2-mail.ops.acme.com"),
        domain=os.environ.get("AUTOEMAIL_DOMAIN2_DOMAIN", "ops.acme.com"),
    )
    Domain3 = EmailInstance(
        relay=os.environ.get("AUTOEMAIL_DOMAIN3_RELAY", "domain3-mail.server.acme.com"),
        domain=os.environ.get("AUTOEMAIL_DOMAIN3_DOMAIN", "server.acme.com"),
    )


EMAIL_REGEX = re.compile(r"[^@]+@[^@]+\.[^@]+")
HOST_MISMATCH = "Mismatch host detected. Host: {}, Domain: {}"


E = TypeVar("E", bound=Enum)


def str_to_enum(enum_cls: Type[E], item: Union[str, E]) -> E:
    """Converts a string to an Enum instance.

    Matches on member name (case-insensitive), then on member value for
    string-valued enums.

    Parameters
    ----------
    enum_cls : Type[Enum]
        Enum class.
    item : Union[str, Enum]
        Enum member or string to convert.

    Returns
    -------
    Enum
        Converted Enum member.

    Raises
    ------
    ValueError
        If the string does not match any member.
    TypeError
        If the input is not a string or Enum member.
    """
    if isinstance(item, enum_cls):
        return item
    elif isinstance(item, str):
        item_lower = item.lower()
        for member in enum_cls:
            if member.name.lower() == item_lower:
                return member
        for member in enum_cls:
            if isinstance(member.value, str) and member.value.lower() == item_lower:
                return member
        raise ValueError(
            f"Invalid value '{item}' for {enum_cls.__name__}. "
            f"Must be one of: {enum_cls._member_names_}"
        )
    else:
        raise TypeError(f"Item must be a string or enum member of: {enum_cls._member_names_}")


def get_domain() -> str:
    """Fetches the current machine's fully-qualified domain name.

    Returns
    -------
    str
        Lowercased FQDN.

    Raises
    ------
    AutoEmailException
        If the domain cannot be determined.
    """
    try:
        return socket.getfqdn().lower()
    except Exception:
        raise AutoEmailException("Error detecting computer domain.")


def detect_domain_mismatch(value: EmailEnv):
    """Validates that the current machine's domain matches the selected EmailEnv.

    Parameters
    ----------
    value : EmailEnv
        Chosen email host.

    Raises
    ------
    AutoEmailException
        If the domain does not match the host.
    """
    fqdn = get_domain()
    if not fqdn or "runner" in fqdn:
        return  # skip CI/CD environments or unresolvable hosts

    parts = fqdn.split(".", 1)
    subdomain = parts[1] if len(parts) > 1 else ""

    if not subdomain:
        return  # single-label hostname — cannot validate

    if subdomain != value.domain:
        raise AutoEmailException(HOST_MISMATCH.format(value.name, fqdn))


def detect_host() -> EmailEnv:
    """Attempt to automatically detect the current ``EmailEnv`` by inspecting
    the machine's FQDN.

    Returns
    -------
    EmailEnv
        The detected email environment.

    Raises
    ------
    AutoEmailException
        If the environment could not be determined.
    """
    domain = get_domain()
    for env in EmailEnv:
        if f".{env.domain}" in domain or domain.endswith(env.domain):
            return env
    raise AutoEmailException(f"Unable to determine environment from domain: {domain}")


def get_current_user() -> str:
    """Returns the current OS username.

    Returns
    -------
    str
        Current username.

    Raises
    ------
    AutoEmailException
        If username retrieval fails.
    """
    try:
        return getuser()
    except Exception as e:
        raise AutoEmailException(f"An error occurred while retrieving current user: {e}")


def validate_email(item: str, host, gov_email: bool = False) -> str:
    """Validates and normalizes an email address.

    Parameters
    ----------
    item : str
        Email address string.
    host : EmailEnv or EmailInstance
        Email environment.
    gov_email : bool, optional
        If ``True``, requires a ``.gov`` address matching the host domain.
        Default: ``False``.

    Returns
    -------
    str
        Normalized (lowercased, stripped) email address.

    Raises
    ------
    AutoEmailException
        On format or domain validation errors.
    """
    if not item:
        raise AutoEmailException("No email address provided.")

    email = item.strip().lower().strip(".")

    if ".@" in email or "@" not in email or "@." in email:
        raise AutoEmailException(f"Invalid email '{email}': format issue.")

    if not EMAIL_REGEX.match(email):
        raise AutoEmailException(f"Invalid email '{email}': does not match expected pattern.")

    if gov_email:
        if not email.endswith(".gov"):
            raise AutoEmailException(f"'{email}' must be a .gov email address.")
        _, domain = email.split("@", 1)
        if domain != host.domain:
            raise AutoEmailException(f"'{email}' must match domain '{host.domain}'.")

    return email
