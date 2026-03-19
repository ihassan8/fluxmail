from ._version import __version__
from .fluxmail import FluxMail
from .utils import FluxMailException, EmailInstance, EmailObject

__all__ = [
    "FluxMail",
    "FluxMailException",
    "EmailInstance",
    "EmailObject",
    "__version__",
]
