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

# Disable logging for a cleaner testing output
import logging
from unittest import mock

from helpers import AppriseURLTester
import pytest
import requests

from apprise.plugins.threema import (
    NACL_SUPPORT,
    THREEMA_E2E_URL,
    THREEMA_PUBKEY_URL,
    NotifyThreema,
    ThreemaMode,
    ThreemaRecipientTypes,
)

logging.disable(logging.CRITICAL)

# A valid 64-character hex private key (all-zeros for testing)
VALID_PRIVKEY_HEX = "a" * 64
VALID_PRIVKEY = f"private:{VALID_PRIVKEY_HEX}"

# A valid 64-character hex public key (all-ones for testing)
VALID_PUBKEY_HEX = "b" * 64

# A valid 8-character Gateway ID
GW_ID = "*THEGWID"
SECRET = "mysecret"

# A valid 8-character Threema recipient ID
RECIPIENT_ID = "ABCD1234"

# Our Testing URLs
apprise_url_tests = (
    (
        "threema://",
        {
            # No user/secret specified
            "instance": TypeError,
        },
    ),
    (
        "threema://@:",
        {
            # Invalid url
            "instance": TypeError,
        },
    ),
    (
        "threema://user@secret",
        {
            # gateway id must be 8 characters in len
            "instance": TypeError,
        },
    ),
    (
        "threema://*THEGWID@secret/{targets}/".format(
            targets="/".join(["2222"])
        ),
        {
            # Invalid target phone number
            "instance": NotifyThreema,
            "notify_response": False,
            "privacy_url": "threema://%2ATHEGWID@****/2222",
        },
    ),
    (
        "threema://*THEGWID@secret/{targets}/".format(
            targets="/".join(["16134442222"])
        ),
        {
            # Valid
            "instance": NotifyThreema,
            "privacy_url": "threema://%2ATHEGWID@****/16134442222",
        },
    ),
    (
        "threema://*THEGWID@secret/{targets}/".format(
            targets="/".join(["16134442222", "16134443333"])
        ),
        {
            # Valid multiple targets
            "instance": NotifyThreema,
            "privacy_url": "threema://%2ATHEGWID@****/16134442222/16134443333",
        },
    ),
    (
        "threema:///?secret=secret&from=*THEGWID&to={targets}".format(
            targets=",".join(["16134448888", "user1@gmail.com", "abcd1234"])
        ),
        {
            # Valid
            "instance": NotifyThreema,
        },
    ),
    (
        "threema:///?secret=secret&gwid=*THEGWID&to={targets}".format(
            targets=",".join(["16134448888", "user2@gmail.com", "abcd1234"])
        ),
        {
            # Valid
            "instance": NotifyThreema,
        },
    ),
    (
        "threema://*THEGWID@secret",
        {
            "instance": NotifyThreema,
            # No targets specified
            "notify_response": False,
        },
    ),
    (
        "threema://*THEGWID@secret/16134443333",
        {
            "instance": NotifyThreema,
            # throw a bizarre code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "threema://*THEGWID@secret/16134443333",
        {
            "instance": NotifyThreema,
            # Throws a series of errors
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_threema():
    """NotifyThreema() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.post")
def test_plugin_threema_edge_cases(mock_post):
    """NotifyThreema() Edge Cases."""

    # Prepare our response
    response = requests.Request()
    response.status_code = requests.codes.ok

    # Prepare Mock
    mock_post.return_value = response

    # Initialize some generic (but valid) tokens
    gwid = "*THEGWID"
    secret = "mysecret"
    targets = "+1 (555) 123-9876"

    # No email specified
    with pytest.raises(TypeError):
        NotifyThreema(user=gwid, secret=None, targets=targets)

    results = NotifyThreema.parse_url(
        f"threema://?gwid={gwid}&secret={secret}&to={targets}"
    )

    assert isinstance(results, dict)
    assert results["user"] == gwid
    assert results["secret"] == secret
    assert results["password"] is None
    assert results["port"] is None
    assert results["host"] == ""
    assert results["fullpath"] == "/"
    assert results["path"] == "/"
    assert results["query"] is None
    assert results["schema"] == "threema"
    assert results["url"] == "threema:///"
    assert isinstance(results["targets"], list)
    assert len(results["targets"]) == 1
    assert results["targets"][0] == targets

    instance = NotifyThreema(**results)
    assert len(instance.targets) == 1
    assert instance.targets[0] == ("phone", "15551239876")
    assert isinstance(instance, NotifyThreema)

    response = instance.send(title="title", body="body 😊")
    assert response is True
    assert mock_post.call_count == 1

    details = mock_post.call_args_list[0]
    assert details[0][0] == "https://msgapi.threema.ch/send_simple"
    assert details[1]["headers"]["User-Agent"] == "Apprise"
    assert details[1]["headers"]["Accept"] == "*/*"
    assert (
        details[1]["headers"]["Content-Type"]
        == "application/x-www-form-urlencoded; charset=utf-8"
    )
    assert details[1]["params"]["secret"] == secret
    assert details[1]["params"]["from"] == gwid
    assert details[1]["params"]["phone"] == "15551239876"
    assert details[1]["params"]["text"] == "body 😊".encode()


def test_plugin_threema_modes():
    """NotifyThreema() mode detection and validation."""

    # Default mode is basic
    obj = NotifyThreema(user=GW_ID, secret=SECRET, targets=[RECIPIENT_ID])
    assert obj.mode == ThreemaMode.BASIC

    # Explicit basic mode
    obj = NotifyThreema(
        user=GW_ID, secret=SECRET, targets=[RECIPIENT_ID], mode="basic"
    )
    assert obj.mode == ThreemaMode.BASIC

    # Invalid mode raises
    with pytest.raises(TypeError):
        NotifyThreema(
            user=GW_ID, secret=SECRET, targets=[RECIPIENT_ID], mode="bad"
        )


def test_plugin_threema_parse_privkey():
    """NotifyThreema._parse_privkey() handles all input forms."""

    # Valid raw hex
    assert NotifyThreema._parse_privkey(VALID_PRIVKEY_HEX) == VALID_PRIVKEY_HEX

    # Valid with 'private:' prefix
    assert (
        NotifyThreema._parse_privkey(f"private:{VALID_PRIVKEY_HEX}")
        == VALID_PRIVKEY_HEX
    )

    # Upper-case hex is normalised to lower-case
    upper = VALID_PRIVKEY_HEX.upper()
    assert NotifyThreema._parse_privkey(upper) == VALID_PRIVKEY_HEX

    # Wrong length
    assert NotifyThreema._parse_privkey("aa" * 31) is None
    assert NotifyThreema._parse_privkey("aa" * 33) is None

    # Non-hex characters
    assert NotifyThreema._parse_privkey("g" * 64) is None

    # Not a string
    assert NotifyThreema._parse_privkey(None) is None
    assert NotifyThreema._parse_privkey(123) is None


@pytest.mark.skipif(not NACL_SUPPORT, reason="PyNaCl not installed")
def test_plugin_threema_e2e_init():
    """NotifyThreema() E2E mode initialisation."""

    # Auto-detect E2E when privkey supplied
    obj = NotifyThreema(
        user=GW_ID,
        secret=SECRET,
        targets=[RECIPIENT_ID],
        privkey=VALID_PRIVKEY,
    )
    assert obj.mode == ThreemaMode.E2E
    assert obj._privkey == VALID_PRIVKEY_HEX

    # Explicit e2e mode
    obj = NotifyThreema(
        user=GW_ID,
        secret=SECRET,
        targets=[RECIPIENT_ID],
        mode="e2e",
        privkey=VALID_PRIVKEY,
    )
    assert obj.mode == ThreemaMode.E2E

    # E2E mode without a private key raises
    with pytest.raises(TypeError):
        NotifyThreema(
            user=GW_ID,
            secret=SECRET,
            targets=[RECIPIENT_ID],
            mode="e2e",
        )

    # E2E mode with an invalid private key raises
    with pytest.raises(TypeError):
        NotifyThreema(
            user=GW_ID,
            secret=SECRET,
            targets=[RECIPIENT_ID],
            privkey="not-a-valid-key",
        )


@pytest.mark.skipif(not NACL_SUPPORT, reason="PyNaCl not installed")
def test_plugin_threema_e2e_url():
    """NotifyThreema() URL round-trip for E2E mode."""

    obj = NotifyThreema(
        user=GW_ID,
        secret=SECRET,
        targets=[RECIPIENT_ID],
        privkey=VALID_PRIVKEY,
    )

    # url() encodes mode and privkey
    url = obj.url()
    assert "mode=e2e" in url
    assert VALID_PRIVKEY_HEX in url

    # Privacy URL masks the private key
    priv_url = obj.url(privacy=True)
    assert VALID_PRIVKEY_HEX not in priv_url
    assert "key" in priv_url

    # parse_url round-trip
    results = NotifyThreema.parse_url(url)
    assert results is not None
    assert results["mode"] == "e2e"
    assert VALID_PRIVKEY_HEX in results["privkey"]

    obj2 = NotifyThreema(**results)
    assert obj2.mode == ThreemaMode.E2E
    assert obj2._privkey == VALID_PRIVKEY_HEX


@pytest.mark.skipif(not NACL_SUPPORT, reason="PyNaCl not installed")
@mock.patch("requests.get")
@mock.patch("requests.post")
def test_plugin_threema_e2e_send(mock_post, mock_get):
    """NotifyThreema() E2E send — success path."""

    # Public-key lookup response
    pubkey_resp = mock.MagicMock()
    pubkey_resp.status_code = requests.codes.ok
    pubkey_resp.text = VALID_PUBKEY_HEX
    mock_get.return_value = pubkey_resp

    # Send response
    send_resp = mock.MagicMock()
    send_resp.status_code = requests.codes.ok
    mock_post.return_value = send_resp

    obj = NotifyThreema(
        user=GW_ID,
        secret=SECRET,
        targets=[RECIPIENT_ID],
        privkey=VALID_PRIVKEY,
    )

    assert obj.send(body="Hello E2E") is True

    # One GET (pubkey lookup) + one POST (send_e2e)
    assert mock_get.call_count == 1
    assert mock_post.call_count == 1

    get_url = mock_get.call_args[0][0]
    assert RECIPIENT_ID in get_url
    assert "pubkeys" in get_url

    post_url = mock_post.call_args[0][0]
    assert post_url == THREEMA_E2E_URL

    payload = mock_post.call_args[1]["params"]
    assert payload["from"] == GW_ID
    assert payload["to"] == RECIPIENT_ID
    assert payload["secret"] == SECRET
    # nonce: 48 hex chars (24 bytes)
    assert len(payload["nonce"]) == 48
    # box: non-empty hex
    assert len(payload["box"]) > 0
    assert all(c in "0123456789abcdef" for c in payload["box"])


@pytest.mark.skipif(not NACL_SUPPORT, reason="PyNaCl not installed")
@mock.patch("requests.get")
@mock.patch("requests.post")
def test_plugin_threema_e2e_pubkey_cached(mock_post, mock_get):
    """NotifyThreema() E2E public key is fetched once and cached."""

    pubkey_resp = mock.MagicMock()
    pubkey_resp.status_code = requests.codes.ok
    pubkey_resp.text = VALID_PUBKEY_HEX
    mock_get.return_value = pubkey_resp

    send_resp = mock.MagicMock()
    send_resp.status_code = requests.codes.ok
    mock_post.return_value = send_resp

    obj = NotifyThreema(
        user=GW_ID,
        secret=SECRET,
        targets=[RECIPIENT_ID, "XXXXXXXX"],
        privkey=VALID_PRIVKEY,
    )

    # Pre-populate the persistent store for RECIPIENT_ID so its pubkey
    # lookup is skipped — only XXXXXXXX needs a live GET.
    obj.store.set(
        f"pubkey_{RECIPIENT_ID}",
        bytes.fromhex(VALID_PUBKEY_HEX),
    )

    assert obj.send(body="Cached") is True
    # Only one GET (for XXXXXXXX); RECIPIENT_ID served from cache
    assert mock_get.call_count == 1
    assert mock_post.call_count == 2


@pytest.mark.skipif(not NACL_SUPPORT, reason="PyNaCl not installed")
@mock.patch("requests.get")
def test_plugin_threema_e2e_encrypt_failure(mock_get):
    """NotifyThreema() E2E handles exceptions from _encrypt_message."""

    pubkey_resp = mock.MagicMock()
    pubkey_resp.status_code = requests.codes.ok
    pubkey_resp.text = VALID_PUBKEY_HEX
    mock_get.return_value = pubkey_resp

    obj = NotifyThreema(
        user=GW_ID,
        secret=SECRET,
        targets=[RECIPIENT_ID],
        privkey=VALID_PRIVKEY,
    )

    with mock.patch.object(
        obj, "_encrypt_message", side_effect=Exception("boom")
    ):
        assert obj.send(body="test") is False


@pytest.mark.skipif(not NACL_SUPPORT, reason="PyNaCl not installed")
@mock.patch("requests.get")
def test_plugin_threema_e2e_pubkey_fetch_error(mock_get):
    """NotifyThreema() E2E aborts gracefully when pubkey fetch fails."""

    obj = NotifyThreema(
        user=GW_ID,
        secret=SECRET,
        targets=[RECIPIENT_ID],
        privkey=VALID_PRIVKEY,
    )

    # HTTP error from pubkey endpoint
    err_resp = mock.MagicMock()
    err_resp.status_code = requests.codes.not_found
    mock_get.return_value = err_resp
    assert obj.send(body="test") is False

    # Connection error from pubkey endpoint
    mock_get.side_effect = requests.RequestException("conn error")
    assert obj.send(body="test") is False

    # Invalid pubkey length
    mock_get.side_effect = None
    bad_len_resp = mock.MagicMock()
    bad_len_resp.status_code = requests.codes.ok
    bad_len_resp.text = "abcd"  # too short
    mock_get.return_value = bad_len_resp
    assert obj.send(body="test") is False

    # Non-hex pubkey
    bad_hex_resp = mock.MagicMock()
    bad_hex_resp.status_code = requests.codes.ok
    bad_hex_resp.text = "z" * 64  # valid length, non-hex
    mock_get.return_value = bad_hex_resp
    assert obj.send(body="test") is False


@pytest.mark.skipif(not NACL_SUPPORT, reason="PyNaCl not installed")
@mock.patch("requests.get")
@mock.patch("requests.post")
def test_plugin_threema_e2e_send_http_error(mock_post, mock_get):
    """NotifyThreema() E2E handles HTTP errors from /send_e2e."""

    pubkey_resp = mock.MagicMock()
    pubkey_resp.status_code = requests.codes.ok
    pubkey_resp.text = VALID_PUBKEY_HEX
    mock_get.return_value = pubkey_resp

    obj = NotifyThreema(
        user=GW_ID,
        secret=SECRET,
        targets=[RECIPIENT_ID],
        privkey=VALID_PRIVKEY,
    )

    # HTTP 500
    err_resp = mock.MagicMock()
    err_resp.status_code = requests.codes.internal_server_error
    err_resp.content = b""
    mock_post.return_value = err_resp
    assert obj.send(body="test") is False

    # HTTP 999 — pubkey already in store; no new GET needed
    err_resp.status_code = 999
    assert obj.send(body="test") is False

    # RequestException from /send_e2e — pubkey already in store
    mock_post.side_effect = requests.RequestException("conn")
    assert obj.send(body="test") is False


@pytest.mark.skipif(not NACL_SUPPORT, reason="PyNaCl not installed")
@mock.patch("requests.get")
@mock.patch("requests.post")
def test_plugin_threema_e2e_partial_failure(mock_post, mock_get):
    """NotifyThreema() E2E returns False when any target fails."""

    pubkey_resp = mock.MagicMock()
    pubkey_resp.status_code = requests.codes.ok
    pubkey_resp.text = VALID_PUBKEY_HEX
    mock_get.return_value = pubkey_resp

    ok_resp = mock.MagicMock()
    ok_resp.status_code = requests.codes.ok
    err_resp = mock.MagicMock()
    err_resp.status_code = requests.codes.internal_server_error
    err_resp.content = b""

    # First target succeeds, second fails
    mock_post.side_effect = [ok_resp, err_resp]

    obj = NotifyThreema(
        user=GW_ID,
        secret=SECRET,
        targets=[RECIPIENT_ID, "XXXXXXXX"],
        privkey=VALID_PRIVKEY,
    )

    assert obj.send(body="test") is False
    assert mock_post.call_count == 2


@pytest.mark.skipif(not NACL_SUPPORT, reason="PyNaCl not installed")
@mock.patch("requests.get")
def test_plugin_threema_e2e_skip_non_id_targets(mock_get):
    """NotifyThreema() E2E skips phone/email targets with a warning."""

    obj = NotifyThreema(
        user=GW_ID,
        secret=SECRET,
        targets=["16134442222"],  # phone number
        privkey=VALID_PRIVKEY,
    )
    # All targets are phones — nothing to send
    assert obj.send(body="test") is False
    # No pubkey lookups attempted
    assert mock_get.call_count == 0


@pytest.mark.skipif(not NACL_SUPPORT, reason="PyNaCl not installed")
@mock.patch("requests.get")
@mock.patch("requests.post")
def test_plugin_threema_e2e_mixed_targets(mock_post, mock_get):
    """NotifyThreema() E2E sends to ID targets and skips phone/email."""

    pubkey_resp = mock.MagicMock()
    pubkey_resp.status_code = requests.codes.ok
    pubkey_resp.text = VALID_PUBKEY_HEX
    mock_get.return_value = pubkey_resp

    send_resp = mock.MagicMock()
    send_resp.status_code = requests.codes.ok
    mock_post.return_value = send_resp

    obj = NotifyThreema(
        user=GW_ID,
        secret=SECRET,
        targets=["16134442222", RECIPIENT_ID],  # phone + ID
        privkey=VALID_PRIVKEY,
    )

    assert obj.send(body="test") is True
    # Only the Threema ID target should be sent
    assert mock_post.call_count == 1


@pytest.mark.skipif(not NACL_SUPPORT, reason="PyNaCl not installed")
def test_plugin_threema_e2e_no_targets():
    """NotifyThreema() E2E returns False when there are no ID targets."""

    obj = NotifyThreema(
        user=GW_ID,
        secret=SECRET,
        targets=[],  # no targets at all
        privkey=VALID_PRIVKEY,
    )
    assert obj.send(body="test") is False


@pytest.mark.skipif(NACL_SUPPORT, reason="PyNaCl IS installed")
def test_plugin_threema_e2e_no_nacl():
    """NotifyThreema() loads but send() returns False without PyNaCl."""

    # Plugin should load without error even when PyNaCl is missing
    obj = NotifyThreema(
        user=GW_ID,
        secret=SECRET,
        targets=[RECIPIENT_ID],
        privkey=VALID_PRIVKEY,
    )
    assert obj.mode == ThreemaMode.E2E

    # send() must fail gracefully with a warning, not raise
    assert obj.send(body="test") is False


@pytest.mark.skipif(not NACL_SUPPORT, reason="PyNaCl not installed")
def test_plugin_threema_e2e_encrypt_message():
    """NotifyThreema._encrypt_message() returns valid nonce+ciphertext."""
    from nacl.public import PrivateKey

    obj = NotifyThreema(
        user=GW_ID,
        secret=SECRET,
        targets=[RECIPIENT_ID],
        privkey=VALID_PRIVKEY,
    )

    recipient_key = PrivateKey.generate()
    pubkey_bytes = bytes(recipient_key.public_key)

    sender_key = PrivateKey(bytes.fromhex(VALID_PRIVKEY_HEX))

    nonce, ciphertext = obj._encrypt_message("hello", sender_key, pubkey_bytes)

    assert len(nonce) == 24
    assert len(ciphertext) > 0

    # Verify ciphertext can be decrypted by the recipient
    from nacl.public import Box

    box = Box(recipient_key, sender_key.public_key)
    plaintext = box.decrypt(ciphertext, nonce)
    # First byte is the type byte (0x01)
    assert plaintext[0:1] == b"\x01"
    # Remaining bytes (before padding) contain the message
    assert b"hello" in plaintext


@pytest.mark.skipif(not NACL_SUPPORT, reason="PyNaCl not installed")
def test_plugin_threema_url_identifier():
    """NotifyThreema.url_identifier uniquely identifies the plugin instance."""

    obj = NotifyThreema(
        user=GW_ID,
        secret=SECRET,
        targets=[RECIPIENT_ID],
    )
    ident = obj.url_identifier
    assert ident == ("threema", GW_ID, SECRET)

    obj_e2e = NotifyThreema(
        user=GW_ID,
        secret=SECRET,
        targets=[RECIPIENT_ID],
        privkey=VALID_PRIVKEY,
    )
    # url_identifier is the same regardless of mode
    assert obj_e2e.url_identifier == ident


def test_plugin_threema_parse_url_e2e():
    """NotifyThreema.parse_url() round-trips E2E parameters."""

    url = (
        f"threema://{GW_ID}@{SECRET}/{RECIPIENT_ID}"
        f"?mode=e2e&privkey=private:{VALID_PRIVKEY_HEX}"
    )
    results = NotifyThreema.parse_url(url)
    assert results is not None
    assert results["mode"] == "e2e"
    assert VALID_PRIVKEY_HEX in results["privkey"]
    assert RECIPIENT_ID in results["targets"]


def test_plugin_threema_parse_url_no_privkey():
    """NotifyThreema.parse_url() without privkey returns no privkey key."""

    url = f"threema://{GW_ID}@{SECRET}/{RECIPIENT_ID}"
    results = NotifyThreema.parse_url(url)
    assert results is not None
    assert "privkey" not in results or not results.get("privkey")


def test_plugin_threema_len():
    """NotifyThreema.__len__() returns at least 1."""

    obj = NotifyThreema(user=GW_ID, secret=SECRET, targets=[])
    assert len(obj) == 1

    obj2 = NotifyThreema(
        user=GW_ID, secret=SECRET, targets=["16134442222", "16134443333"]
    )
    assert len(obj2) == 2


@pytest.mark.skipif(not NACL_SUPPORT, reason="PyNaCl not installed")
def test_plugin_threema_pubkey_url_format():
    """THREEMA_PUBKEY_URL contains the expected base URL."""
    url = THREEMA_PUBKEY_URL.format(RECIPIENT_ID)
    assert "msgapi.threema.ch" in url
    assert "pubkeys" in url
    assert RECIPIENT_ID in url


@pytest.mark.skipif(not NACL_SUPPORT, reason="PyNaCl not installed")
def test_plugin_threema_e2e_url_constant():
    """THREEMA_E2E_URL points at the correct endpoint."""
    assert "msgapi.threema.ch" in THREEMA_E2E_URL
    assert "send_e2e" in THREEMA_E2E_URL


def test_plugin_threema_recipient_types():
    """ThreemaRecipientTypes constants have expected values."""
    assert ThreemaRecipientTypes.THREEMA_ID == "to"
    assert ThreemaRecipientTypes.PHONE == "phone"
    assert ThreemaRecipientTypes.EMAIL == "email"
