import pytest

from fluxmail import EmailInstance, EmailObject
from fluxmail.fluxmail import FluxMail


@pytest.fixture
def smtp_email():
    """FluxMail instance with a test relay and sender username."""
    return FluxMail(
        object_type=EmailObject.SMTP,
        host=EmailInstance(relay="smtp.example.com"),
        username="sender@example.com",
    )
