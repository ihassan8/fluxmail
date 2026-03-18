import pytest
from unittest.mock import patch

from autoemail import EmailEnv, EmailInstance, EmailObject
from autoemail.autoemail import AutoEmail


@pytest.fixture
def gov_host():
    """A custom EmailInstance whose domain ends in .gov — needed for gov_email validation tests."""
    return EmailInstance(relay="smtp.test.gov", domain="hr.test.gov")


@pytest.fixture
def smtp_email():
    return AutoEmail(object_type=EmailObject.SMTP, host=EmailEnv.Domain1)


@pytest.fixture(autouse=True)
def mock_current_user():
    """Prevent all tests from calling getpass.getuser() — returns a stable value instead.

    Without this, the auto-sender path fails in CI where the OS username is unpredictable.
    The auto-sender becomes 'testuser@<host.domain>' and bypasses gov_email validation
    because it is set directly (not through validate_email).
    """
    with patch("autoemail.autoemail.get_current_user", return_value="testuser"):
        yield
