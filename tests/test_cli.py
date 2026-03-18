import pytest
from typer.testing import CliRunner
from autoemail.autoemail_cli import app
from autoemail.testing import mock_smtp

runner = CliRunner()

BASE = [
    "--type", "smtp",
    "--host", "Domain1",
    "--subject", "Test",
    "--recipients", "user@example.com",
    "--body", "Hello",
]


def test_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "autoemail" in result.output


def test_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "--type" in result.output


def test_basic_send():
    with mock_smtp():
        result = runner.invoke(app, BASE)
    assert result.exit_code == 0
    assert "sent successfully" in result.output


def test_dry_run():
    result = runner.invoke(app, BASE + ["--dry-run"])
    assert result.exit_code == 0
    assert "Email Preview" in result.output


def test_invalid_type_exits_1():
    args = ["--type", "fax", "--host", "Domain1",
            "--subject", "T", "--recipients", "a@b.com", "--body", "Hi"]
    result = runner.invoke(app, args)
    assert result.exit_code == 1


def test_invalid_host_exits_1():
    # A host string with no colon and no matching EmailEnv name → BadParameter → exit 1.
    # Do NOT use "relay:domain" format here — that is a valid custom EmailInstance.
    args = ["--type", "smtp", "--host", "NotAValidHost",
            "--subject", "T", "--recipients", "a@b.com", "--body", "Hi"]
    result = runner.invoke(app, args)
    assert result.exit_code == 1


def test_custom_host_relay_colon_syntax():
    with mock_smtp():
        args = [
            "--type", "smtp",
            "--host", "smtp.example.gov:example.gov",
            "--subject", "T",
            "--recipients", "a@example.gov",
            "--body", "Hi",
        ]
        result = runner.invoke(app, args)
    assert result.exit_code == 0


def test_multiple_recipients():
    with mock_smtp():
        result = runner.invoke(app, [
            "--type", "smtp", "--host", "Domain1",
            "--subject", "T",
            "--recipients", "a@b.com",
            "--recipients", "c@d.com",
            "--body", "Hi",
        ])
    assert result.exit_code == 0


def test_html_flag():
    with mock_smtp():
        result = runner.invoke(app, BASE + ["--html"])
    assert result.exit_code == 0


def test_body_file_sends_file_content(tmp_path):
    body_file = tmp_path / "body.txt"
    body_file.write_text("Hello from file")
    with mock_smtp() as smtp:
        result = runner.invoke(app, [
            "--type", "smtp", "--host", "Domain1",
            "--subject", "T", "--recipients", "a@b.com",
            "--body-file", str(body_file),
        ])
    assert result.exit_code == 0
    sent = smtp.send_message.call_args[0][0]
    assert "Hello from file" in sent.get_payload()


def test_body_and_body_file_mutual_exclusion():
    result = runner.invoke(app, [
        "--type", "smtp", "--host", "Domain1",
        "--subject", "T", "--recipients", "a@b.com",
        "--body", "Hi",
        "--body-file", "somefile.txt",
    ])
    assert result.exit_code == 1


def test_neither_body_nor_body_file_exits_1():
    result = runner.invoke(app, [
        "--type", "smtp", "--host", "Domain1",
        "--subject", "T", "--recipients", "a@b.com",
    ])
    assert result.exit_code == 1


def test_body_file_not_found_exits_1(tmp_path):
    result = runner.invoke(app, [
        "--type", "smtp", "--host", "Domain1",
        "--subject", "T", "--recipients", "a@b.com",
        "--body-file", str(tmp_path / "missing.txt"),
    ])
    assert result.exit_code == 1
