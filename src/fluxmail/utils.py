import re
from collections import namedtuple
from enum import Enum
from typing import Optional, Type, TypeVar, Union


class FluxMailException(Exception):
    """Custom exception class for FluxMail errors."""

    def __init__(self, message: str, code: Optional[str] = None) -> None:
        super().__init__(message)
        self.code = code


class EmailObject(Enum):
    """Supported email object types."""

    OUTLOOK = "outlook"
    """Use ``outlook`` object to create and send email."""
    SMTP = "smtp"
    """Use ``smtp`` object to create and send email."""


EmailInstance = namedtuple("EmailInstance", ["relay", "domain"], defaults=[""])
"""Named tuple representing an SMTP relay host.

Parameters
----------
relay : str
    SMTP relay hostname (e.g. ``"smtp.gmail.com"``).
domain : str, optional
    Sender domain used for display or routing (e.g. ``"gmail.com"``).
    Defaults to ``""``.
"""


EMAIL_REGEX = re.compile(r"[^@]+@[^@]+\.[^@]+")

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
        raise TypeError(
            f"Item must be a string or enum member of: {enum_cls._member_names_}"
        )


def validate_email(item: str) -> str:
    """Validates and normalizes an email address.

    Parameters
    ----------
    item : str
        Email address string.

    Returns
    -------
    str
        Normalized (lowercased, stripped) email address.

    Raises
    ------
    FluxMailException
        On format validation errors.
    """
    if not item:
        raise FluxMailException("No email address provided.", code="no_email")

    email = item.strip().lower().rstrip(".")

    if email.startswith(".") or ".@" in email or "@" not in email or "@." in email:
        raise FluxMailException(
            f"Invalid email '{email}': format issue.", code="invalid_email"
        )

    if not EMAIL_REGEX.match(email):
        raise FluxMailException(
            f"Invalid email '{email}': does not match expected pattern.",
            code="invalid_email",
        )

    return email
