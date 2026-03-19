import codecs
import os

from setuptools import setup

package = "src/fluxmail"
VERSION_FILE = os.path.join(package, "_version.py")
REQUIREMENTS_FILE = os.path.join("requirements.txt")
MODE = "scm"  # Use can select the option 'manual' to read from version.py or 'scm' to autmatically read from .git metedata version


def read(rel_path):
    here = os.path.abspath(os.path.dirname(__file__))
    with codecs.open(os.path.join(here, rel_path), "r", encoding="utf-8") as f:
        return f.read()


def get_version(rel_path):
    for line in read(rel_path).splitlines():
        if "version" in line:
            delim = '"' if '"' in line else "'"
            return line.split(delim)[1]
    else:
        raise RuntimeError("Unable to find version string.")


def get_package_requirements(rel_path):
    return read(rel_path).splitlines()


def auto_version_toggle(mode):
    if mode == "scm":
        return {"use_scm_version": True, "setup_requires": ["setuptools_scm"]}
    elif mode == "manual":
        return {"version": get_version(VERSION_FILE)}

    raise RuntimeError("Please select version mode 'scm', or 'manual'")


setup_args = {
    "install_requires": get_package_requirements(REQUIREMENTS_FILE),
}

version_args = auto_version_toggle(MODE)
setup(**setup_args, **version_args)
