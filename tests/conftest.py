import pytest

from autoemail import EmailInstance, EmailObject
from autoemail.autoemail import AutoEmail


@pytest.fixture
def smtp_email():
    """AutoEmail instance with a test relay and sender username."""
    return AutoEmail(
        object_type=EmailObject.SMTP,
        host=EmailInstance(relay="smtp.example.com"),
        username="sender@example.com",
    )
