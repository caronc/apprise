# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2026, Chris Caron <lead2gold@gmail.com>
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

"""Verify that logging masks credentials in file-like URL inputs.

See CWE-312 for the related cleartext-storage weakness.
"""

import logging
import os
from unittest import mock
from urllib.parse import urlparse

import pytest
import requests

from apprise import (
    LOGGER_NAME,
    AppriseAsset,
    AppriseAttachment,
    AppriseConfig,
    utils,
)
from apprise.attachment import AttachBase
from apprise.common import ContentLocation
from apprise.utils.pgp import ApprisePGPController

# A password that must never turn up in a log line
SECRET = "pass123"

# URLs shaped like supported key and attachment inputs.
SECRET_KEY_URL = f"https://user:{SECRET}@example.com/private_key.pem"
SECRET_ATTACH_URL = f"https://user:{SECRET}@example.com/image.png"


@pytest.fixture
def logs(caplog):
    """Capture Apprise logs, undoing logging disabled by other test modules."""

    disabled = logging.root.manager.disable
    logging.disable(logging.NOTSET)
    caplog.set_level(1, logger=LOGGER_NAME)
    yield caplog
    logging.disable(disabled)


@pytest.fixture
def unreachable():
    """Makes any attempt to fetch a remote file fail."""

    with mock.patch(
        "requests.get", side_effect=requests.RequestException("nope")
    ):
        yield


def test_pem_private_keyfile_credentials(logs, unreachable, tmpdir):
    """A PEM private key url does not put its password in the log."""

    pem = utils.pem.ApprisePEMController(path=str(tmpdir))
    assert pem.load_private_key(SECRET_KEY_URL) is False

    # The failure is reported without the password.
    assert "Could not access PEM Private Key" in logs.text
    assert SECRET not in logs.text

    # Parse logged URLs before checking which host was retained.
    urls_in_logs = [token for token in logs.text.split() if "://" in token]
    assert any(
        urlparse(token).hostname == "example.com" for token in urls_in_logs
    )

    # The masked form is what was written.
    assert "user:p...3@example.com" in logs.text


def test_pem_public_keyfile_credentials(logs, unreachable, tmpdir):
    """A PEM public key url does not put its password in the log."""

    pem = utils.pem.ApprisePEMController(path=str(tmpdir))
    assert pem.load_public_key(SECRET_KEY_URL) is False

    assert "Could not access PEM Public Key" in logs.text
    assert SECRET not in logs.text


def test_attachment_url_credentials(logs, unreachable):
    """Adding a remote attachment does not log its password."""

    attach = AppriseAttachment()
    assert attach.add(SECRET_ATTACH_URL) is True

    assert "Loading attachment" in logs.text
    assert SECRET not in logs.text


def test_attachment_disabled_credentials(logs):
    """Refusing an attachment does not log its password either."""

    attach = AppriseAttachment(location=ContentLocation.INACCESSIBLE)
    assert attach.add(SECRET_ATTACH_URL) is False

    assert "Attachments are disabled" in logs.text
    assert SECRET not in logs.text


def test_attachment_parse_failure_credentials(logs):
    """Mask credentials when an attachment URL cannot be parsed."""

    url = f"https://user:{SECRET}@example.com:bad/image.png"
    assert AppriseAttachment().add(url) is False

    assert "Unparseable URL" in logs.text
    assert SECRET not in logs.text


def test_attachment_load_failure_credentials(logs):
    """Mask credentials when attachment construction raises an exception."""

    class BadAttach(AttachBase):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            raise TypeError()

    manager = AppriseAttachment.instantiate.__globals__["A_MGR"]
    manager["securebad"] = BadAttach
    try:
        url = f"securebad://user:{SECRET}@localhost/file"
        assert AppriseAttachment.instantiate(url) is None
    finally:
        del manager["securebad"]

    assert "Could not load URL" in logs.text
    assert SECRET not in logs.text


def test_secure_logging_disabled(logs, unreachable, tmpdir):
    """Disabling secure logging exposes the full value for debugging."""

    asset = AppriseAsset(secure_logging=False)
    pem = utils.pem.ApprisePEMController(path=str(tmpdir), asset=asset)
    assert pem.load_private_key(SECRET_KEY_URL) is False

    # With masking off, the full URL and password appear.
    assert SECRET in logs.text
    assert SECRET_KEY_URL in logs.text


def test_pem_keyfile_read_errors(logs, tmpdir):
    """Keep a failed local key path readable so users can identify it."""

    keyfile = os.path.join(str(tmpdir), "private_key.pem")
    with open(keyfile, "w") as f:
        f.write("not a real key")

    pem = utils.pem.ApprisePEMController(path=str(tmpdir))

    # Simulate a file disappearing before it is opened.
    with mock.patch("builtins.open", side_effect=FileNotFoundError):
        assert pem.load_private_key(keyfile) is False

    assert "PEM Private Key file not found" in logs.text
    assert keyfile in logs.text

    # Simulate a file that cannot be read.
    logs.clear()
    with mock.patch("builtins.open", side_effect=OSError):
        assert pem.load_private_key(keyfile) is False

    assert "Error accessing PEM Private Key file" in logs.text
    assert keyfile in logs.text

    # Public keys handle the same failures.
    logs.clear()
    with mock.patch("builtins.open", side_effect=FileNotFoundError):
        assert pem.load_public_key(keyfile) is False

    assert "PEM Public Key file not found" in logs.text
    assert keyfile in logs.text

    logs.clear()
    with mock.patch("builtins.open", side_effect=OSError):
        assert pem.load_public_key(keyfile) is False

    assert "Error accessing PEM Public Key file" in logs.text
    assert keyfile in logs.text


@pytest.mark.parametrize("method", ("private_key", "public_key"))
def test_pgp_key_credentials(logs, tmpdir, method):
    """Mask credentials in PGP key read failures."""

    pgp = ApprisePGPController(path=str(tmpdir))
    keyfile_method = f"{method}file"
    error = OSError("disk error")
    with (
        mock.patch.object(pgp, keyfile_method, return_value=SECRET_KEY_URL),
        mock.patch("builtins.open", side_effect=error),
    ):
        assert getattr(pgp, method)() is None

    assert "disk error" in logs.text
    assert SECRET not in logs.text


def test_config_parse_failure_credentials(logs):
    """Mask credentials when a configuration URL cannot be parsed."""

    url = f"https://user:{SECRET}@example.com:bad/config.yml"
    assert AppriseConfig().add(url) is False

    assert "Unparseable URL" in logs.text
    assert SECRET not in logs.text
