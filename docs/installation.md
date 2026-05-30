# Installation

Requires **Python 3.8 or later**.

## Install

=== "pip (recommended)"

    ```bash
    pip install fluxmail
    ```

=== "From source"

    ```bash
    git clone https://github.com/ihassan8/fluxmail.git
    cd fluxmail
    pip install -e .
    ```

## Upgrade

```bash
pip install --upgrade fluxmail
```

## Outlook Support

!!! tip "Outlook on Windows"
    The `pywin32` dependency is installed automatically when running
    `pip install fluxmail` on **Windows**. On Linux and macOS, `pywin32` is
    skipped and only SMTP is available. Outlook itself must be installed and
    open for COM automation to work.

## Verify

Confirm the installation succeeded:

```bash
fluxmail --version
# fluxmail 1.x.y
```
