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

# Email tests cover inherited delivery behavior. These tests cover the
# Delta Chat schema, plain-text envelope, and chat headers.

import logging
import os
from unittest import mock

from apprise import Apprise, AppriseAsset, NotifyBase, PersistentStoreMode
from apprise.exception import AppriseImproperlyConfigured
from apprise.plugins.deltachat import NotifyDeltaChat

logging.disable(logging.CRITICAL)

# PGP fixture directory (shared with test_plugin_email.py / test_utils_pgp.py)
PGP_VAR_DIR = os.path.join(os.path.dirname(__file__), "var", "pgp")
VALID_PRV_KEY = os.path.join(PGP_VAR_DIR, "valid-prv.asc")
VALID_PUB_KEY = os.path.join(PGP_VAR_DIR, "valid-pub.asc")

# Our Testing URLs
apprise_url_tests = (
    (
        "deltachat://",
        {
            "instance": AppriseImproperlyConfigured,
        },
    ),
    # A minimal, valid URL: login doubles as our sender identity
    (
        "deltachat://user:pass@smtp.example.com/friend@example.org",
        {
            "instance": NotifyDeltaChat,
            "privacy_url": (
                "deltachat://user:****@smtp.example.com/friend%40example.org"
            ),
        },
    ),
    # The secure schema variant round-trips as itself
    (
        "deltachats://user:pass@smtp.example.com/friend@example.org",
        {
            "instance": NotifyDeltaChat,
            "privacy_url": (
                "deltachats://user:****@smtp.example.com/friend%40example.org"
            ),
        },
    ),
    # Multiple targets
    (
        "deltachat://user:pass@smtp.example.com/"
        "friend1@example.org/friend2@example.org",
        {
            "instance": NotifyDeltaChat,
        },
    ),
    # ?to= adds an additional target
    (
        "deltachat://user:pass@smtp.example.com/friend1@example.org"
        "?to=friend2@example.org",
        {
            "instance": NotifyDeltaChat,
        },
    ),
    # Explicit insecure mode (no transport security at all)
    (
        "deltachat://user:pass@smtp.example.com/friend@example.org"
        "?mode=insecure",
        {
            "instance": NotifyDeltaChat,
        },
    ),
    # An invalid secure mode
    (
        "deltachat://user:pass@smtp.example.com/friend@example.org"
        "?mode=invalid",
        {
            "instance": AppriseImproperlyConfigured,
        },
    ),
    # An invalid PGP mode
    (
        "deltachat://user:pass@smtp.example.com/friend@example.org"
        "?pgp=invalid",
        {
            "instance": AppriseImproperlyConfigured,
        },
    ),
    # Encryption fails without a recipient key.
    (
        "deltachat://user:pass@smtp.example.com/friend@example.org"
        "?pgp=encrypt",
        {
            "instance": NotifyDeltaChat,
            "response": False,
        },
    ),
    # A custom display name
    (
        "deltachat://user:pass@smtp.example.com/friend@example.org"
        "?name=My%20Bot",
        {
            "instance": NotifyDeltaChat,
        },
    ),
    # The explicit secure schema, with a custom port
    (
        "deltachats://user:pass@smtp.example.com:2525/friend@example.org",
        {
            "instance": NotifyDeltaChat,
        },
    ),
)


@mock.patch("smtplib.SMTP")
@mock.patch("smtplib.SMTP_SSL")
def test_plugin_deltachat_urls(mock_smtp, mock_smtpssl):
    """NotifyDeltaChat() Apprise URLs."""

    mock_socket = mock.Mock()
    mock_socket.starttls.return_value = True
    mock_socket.login.return_value = True
    # An empty refusal map means SMTP accepted every recipient.
    mock_socket.sendmail.return_value = {}
    mock_smtp.return_value = mock_socket
    mock_smtpssl.return_value = mock_socket

    for url, meta in apprise_url_tests:
        instance = meta.get("instance", None)
        response = meta.get("response", True)
        privacy_url = meta.get("privacy_url")

        try:
            obj = Apprise.instantiate(url, suppress_exceptions=False)

        except Exception as e:
            if instance is None or not isinstance(e, instance):
                raise
            continue

        assert isinstance(obj, instance)
        assert isinstance(obj, NotifyBase)

        # Confirm a lossless round trip through our own generated URL
        assert isinstance(obj.url(), str)
        assert isinstance(obj.url_id(), str)
        assert isinstance(len(obj), int)
        assert isinstance(obj.url(privacy=True), str)

        # Invalid input remains safe through the parse override.
        assert instance.parse_url(None) is None
        assert instance.parse_url(object) is None
        assert instance.parse_url(42) is None

        if privacy_url and not obj.url(privacy=True).startswith(privacy_url):
            raise AssertionError(
                f"URL: {url} Privacy URL:"
                f" '{obj.url(privacy=True)[: len(privacy_url)]}' !="
                f" expected '{privacy_url}'"
            )

        obj_cmp = Apprise.instantiate(obj.url())
        assert isinstance(obj_cmp, NotifyBase)
        assert len(obj) == len(obj_cmp)
        assert obj.url_identifier == obj_cmp.url_identifier

        assert obj.notify(title="test", body="body test message") == response


def test_plugin_deltachat_schema_identity():
    """NotifyDeltaChat() class-level schema/format identity."""

    assert NotifyDeltaChat.protocol == "deltachat"
    assert NotifyDeltaChat.secure_protocol == "deltachats"
    assert NotifyDeltaChat.service_name == "Delta Chat"

    # Plain-text only; no separate title field, so the framework merges
    # any title into the body for us
    assert NotifyDeltaChat.notify_format == "text"
    assert NotifyDeltaChat.title_maxlen == 0

    # PGPy remains the one optional dependency, inherited from Email
    assert NotifyDeltaChat.runtime_deps() == ("pgpy",)


def _deltachat_instance(pgp="no"):
    """Build an instance for subject tests without sending."""

    return NotifyDeltaChat(
        host="smtp.example.com",
        user="bot",
        password="secret",
        targets=["friend@example.org"],
        pgp_mode=pgp,
    )


def test_plugin_deltachat_chat_subject():
    """Plain subjects contain a shortened body excerpt."""

    obj = _deltachat_instance(pgp="no")

    # A short body is used verbatim
    assert obj._chat_subject("hello there") == "Chat: hello there"

    # Collapse internal whitespace, including a merged title.
    assert (
        obj._chat_subject("My Title\nhello   world")
        == "Chat: My Title hello world"
    )

    # An empty body still produces a valid, generic subject
    assert obj._chat_subject("") == "Chat:"

    # Truncate long bodies and append an ellipsis.
    long_body = "x" * 80
    subject = obj._chat_subject(long_body)
    assert subject == f"Chat: {'x' * 50}..."


def test_plugin_deltachat_pgp_subject_privacy():
    """PGP modes keep body text out of the unencrypted subject."""

    secret = "CONFIDENTIAL body content must remain private"

    expected = {
        "sign": "Chat:",
        "encrypt": "Chat: Encrypted message",
    }
    for pgp_mode, subject in expected.items():
        obj = _deltachat_instance(pgp=pgp_mode)

        assert obj._chat_subject(secret) == subject
        assert secret not in obj._chat_subject(secret)

        # Still a valid, generic subject for an empty body
        assert obj._chat_subject("") == subject


def test_plugin_deltachat_protocol_headers():
    """NotifyDeltaChat._protocol_headers() emits Chat-Version only."""

    obj = NotifyDeltaChat(
        host="smtp.example.com",
        user="bot",
        password="secret",
        targets=["friend@example.org"],
    )
    assert obj._protocol_headers("any body") == {"Chat-Version": "1.0"}


@mock.patch("smtplib.SMTP")
@mock.patch("smtplib.SMTP_SSL")
def test_plugin_deltachat_send_envelope(mock_smtp, mock_smtpssl):
    """NotifyDeltaChat() send() builds a spec-compliant envelope."""

    mock_socket = mock.Mock()
    mock_socket.starttls.return_value = True
    mock_socket.login.return_value = True
    # An empty refusal map means SMTP accepted every recipient.
    mock_socket.sendmail.return_value = {}
    mock_smtp.return_value = mock_socket
    mock_smtpssl.return_value = mock_socket

    obj = Apprise.instantiate(
        "deltachat://user:pass@smtp.example.com/friend@example.org",
        suppress_exceptions=False,
    )

    assert obj.notify(title="My Title", body="hello world") is True

    raw = mock_socket.sendmail.call_args[0][2]

    # Chat-Version is a hard protocol requirement on every message
    assert "Chat-Version: 1.0" in raw

    # The subject uses the title already merged into the body.
    assert "Subject: Chat: My Title hello world" in raw

    # The body itself is always sent as plain text
    assert 'Content-Type: text/plain; charset="utf-8"' in raw


@mock.patch("smtplib.SMTP")
@mock.patch("smtplib.SMTP_SSL")
def test_plugin_deltachat_send_forces_text_format(mock_smtp, mock_smtpssl):
    """NotifyDeltaChat() send() ignores an explicit HTML body_format."""

    mock_socket = mock.Mock()
    mock_socket.starttls.return_value = True
    mock_socket.login.return_value = True
    # An empty refusal map means SMTP accepted every recipient.
    mock_socket.sendmail.return_value = {}
    mock_smtp.return_value = mock_socket
    mock_smtpssl.return_value = mock_socket

    obj = Apprise.instantiate(
        "deltachat://user:pass@smtp.example.com/friend@example.org"
        "?format=html",
        suppress_exceptions=False,
    )

    assert obj.notify(title="T", body="<b>hi</b>") is True

    raw = mock_socket.sendmail.call_args[0][2]
    assert 'Content-Type: text/plain; charset="utf-8"' in raw
    assert "text/html" not in raw


@mock.patch("smtplib.SMTP")
@mock.patch("smtplib.SMTP_SSL")
def test_plugin_deltachat_autocrypt_and_pgp_inherited(
    mock_smtp, mock_smtpssl, tmpdir
):
    """Delta Chat inherits Email signing and Autocrypt handling."""

    mock_socket = mock.Mock()
    mock_socket.starttls.return_value = True
    mock_socket.login.return_value = True
    # An empty refusal map means SMTP accepted every recipient.
    mock_socket.sendmail.return_value = {}
    mock_smtp.return_value = mock_socket
    mock_smtpssl.return_value = mock_socket

    asset = AppriseAsset(
        storage_mode=PersistentStoreMode.FLUSH,
        storage_path=str(tmpdir),
    )

    obj = Apprise.instantiate(
        "deltachat://user:pass@smtp.example.com/friend@example.org?pgp=sign",
        asset=asset,
        suppress_exceptions=False,
    )

    # Generate an Autocrypt-compatible key in this instance's store.
    assert obj.pgp.keygen() is True

    assert obj.notify(title="T", body="secret chat message") is True

    raw = mock_socket.sendmail.call_args[0][2]
    assert "Chat-Version: 1.0" in raw
    assert "multipart/signed" in raw
    assert raw.count("Autocrypt:") == 1

    # PGP is in play, so the outer Subject must be generic
    assert "Subject: Chat:" in raw
    assert "Subject: Chat: T secret chat message" not in raw


@mock.patch("smtplib.SMTP")
@mock.patch("smtplib.SMTP_SSL")
def test_plugin_deltachat_encrypt_subject_privacy(
    mock_smtp, mock_smtpssl, tmpdir
):
    """Encrypted sends keep body text out of the outer subject."""

    mock_socket = mock.Mock()
    mock_socket.starttls.return_value = True
    mock_socket.login.return_value = True
    # An empty refusal map means SMTP accepted every recipient.
    mock_socket.sendmail.return_value = {}
    mock_smtp.return_value = mock_socket
    mock_smtpssl.return_value = mock_socket

    asset = AppriseAsset(
        storage_mode=PersistentStoreMode.FLUSH,
        storage_path=str(tmpdir),
    )
    obj = Apprise.instantiate(
        "deltachat://user:pass@smtp.example.com/friend@example.org"
        f"?pgp=encrypt&pgppub={VALID_PUB_KEY}",
        asset=asset,
        suppress_exceptions=False,
    )

    secret = "CONFIDENTIAL body content must remain private"
    assert obj.notify(title="T", body=secret) is True

    raw = mock_socket.sendmail.call_args[0][2]

    # Use Delta Chat's recommended placeholder without exposing the body.
    assert "Subject: Chat: Encrypted message" in raw

    # Protected body text must not appear in the outer envelope.
    assert secret not in raw
    assert "CONFIDENTIAL body content" not in raw
