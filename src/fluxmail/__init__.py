from ._version import __version__
from .fluxmail import FluxMail
from .template import EmailTemplate
from .utils import FluxMailException, EmailInstance, EmailObject

__all__ = [
    "FluxMail",
    "FluxMailException",
    "EmailInstance",
    "EmailObject",
    "EmailTemplate",
    "__version__",
]
