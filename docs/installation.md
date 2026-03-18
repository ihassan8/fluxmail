# Installation

Requires **Python 3.8 or later**.

## Install

=== "pip (recommended)"

    ```bash
    pip install autoemail
    ```

=== "From source"

    ```bash
    git clone https://github.com/vertex-ai-automations/autoemail.git
    cd autoemail
    pip install -e .
    ```

## Upgrade

```bash
pip install --upgrade autoemail
```

## Outlook Support

!!! tip "Outlook on Windows"
    The `pywin32` dependency is installed automatically when running
    `pip install autoemail` on **Windows**. On Linux and macOS, `pywin32` is
    skipped and only SMTP is available. Outlook itself must be installed and
    open for COM automation to work.

## Verify

Confirm the installation succeeded:

```bash
autoemail --version
# autoemail 1.x.y
```
