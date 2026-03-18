from ._version import __version__
from .autoemail import AutoEmail
from .utils import AutoEmailException, EmailInstance, EmailObject

__all__ = [
    "AutoEmail",
    "AutoEmailException",
    "EmailInstance",
    "EmailObject",
    "__version__",
]
