from ._version import __version__
from .autoemail import AutoEmail
from .utils import AutoEmailException, EmailEnv, EmailInstance, EmailObject

__all__ = [
    "AutoEmail",
    "AutoEmailException",
    "EmailEnv",
    "EmailInstance",
    "EmailObject",
    "__version__",
]
