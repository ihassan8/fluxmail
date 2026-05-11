from typing import Any

from jinja2 import BaseLoader, Environment, select_autoescape


class EmailTemplate:
    """Jinja2-based email body renderer."""

    def __init__(self, template: str, autoescape: bool = False) -> None:
        env = Environment(
            loader=BaseLoader(),
            autoescape=select_autoescape(["html", "xml"]) if autoescape else False,
        )
        self._template = env.from_string(template)

    def render(self, **context: Any) -> str:
        """Render the template with the given context variables."""
        return self._template.render(**context)

    @classmethod
    def from_file(cls, path: str, autoescape: bool = False) -> "EmailTemplate":
        """Load a template from a file (UTF-8 encoding)."""
        with open(path, "r", encoding="utf-8") as f:
            return cls(f.read(), autoescape=autoescape)
