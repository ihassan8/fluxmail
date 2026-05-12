try:
    from .django import FluxMailBackend

    __all__ = ["FluxMailBackend"]
except ImportError:
    # Django is an optional dependency — install with: pip install fluxmail[django]
    __all__ = []
