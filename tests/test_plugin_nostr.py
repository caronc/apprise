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


from base64 import b64decode, b64encode
import hashlib
import hmac
from json import dumps, loads
import logging
import os
import re
import socket
import time
from types import SimpleNamespace
from unittest import mock

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise, AppriseAttachment, NotifyType
from apprise.exception import AppriseImproperlyConfigured
from apprise.plugins.nostr import NotifyNostr, crypto
from apprise.plugins.nostr.base import NOSTR_DEFAULT_BLOSSOM, NostrMode
from apprise.plugins.nostr.crypto import NostrKey, bech32_encode
from apprise.plugins.nostr.relay import (
    WS_ACCEPT_GUID,
    NostrRelay,
    RelayTransport,
)
from apprise.utils.socket import AppriseSocketError

logging.disable(logging.CRITICAL)

# Attachment Directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), "var")

# Fixed keys so every run builds the same URLs
SENDER = NostrKey(int("11" * 32, 16))
RECIPIENT = NostrKey(int("22" * 32, 16))
OTHER = NostrKey(int("33" * 32, 16))

NSEC = bech32_encode("nsec", SENDER.secret.to_bytes(32, "big"))
NPUB = bech32_encode("npub", bytes.fromhex(RECIPIENT.public_key))
NPUB_OTHER = bech32_encode("npub", bytes.fromhex(OTHER.public_key))

# What a mocked Blossom server and Nostr address lookup answer with
BLOB_URL = "https://cdn.example.com/abc.png"
OK_REPLY = dumps(
    {"url": BLOB_URL, "names": {"alice": RECIPIENT.public_key}}
).encode()

apprise_url_tests = (
    (
        "nostr://",
        {
            # No secret key
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "nostr://invalid",
        {
            # Not a usable secret key
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "nostr://{}".format("0" * 64),
        {
            # Zero is not a valid secret key
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "nostr://{}".format(NSEC),
        {
            # A public note
            "instance": NotifyNostr,
            "requests_response_text": OK_REPLY,
            # The reply does not describe the uploaded file
            "attach_response": False,
            "privacy_url": "nostr://{}...{}/".format(NSEC[0], NSEC[-1]),
        },
    ),
    (
        "nostr://?key={}".format("11" * 32),
        {
            # Secret key given as hex in ?key=
            "instance": NotifyNostr,
            "requests_response_text": OK_REPLY,
            "attach_response": False,
        },
    ),
    (
        "nostr://{}?mode=invalid".format(NSEC),
        {
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "nostr://{}?relay=relay!".format(NSEC),
        {
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "nostr://{}?relay=relay.example.com:99999".format(NSEC),
        {
            # A port that can not exist
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "nostr://{}?relay={}.example.com".format(NSEC, "a" * 64),
        {
            # A hostname label longer than 63 characters
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "nostr://{}?relay=relay.example.com:0".format(NSEC),
        {
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "nostr://{}/junk".format(NSEC),
        {
            # Only invalid recipients, so nothing is sent
            "instance": NotifyNostr,
            "notify_response": False,
        },
    ),
    (
        "nostr://{}?blossom=cdn.example.com&relay=relay.example.com".format(
            NSEC
        ),
        {
            "instance": NotifyNostr,
            "requests_response_text": OK_REPLY,
            "attach_response": False,
        },
    ),
    (
        "nostr://{}?blossom=https://cdn.example.com".format(NSEC),
        {
            # The note is fine but the upload fails
            "instance": NotifyNostr,
            "requests_response_code": requests.codes.internal_server_error,
            "notify_response": True,
            "attach_response": False,
        },
    ),
)


@pytest.fixture
def relays():
    """Replace relay connections with an in-memory stand-in."""
    state = SimpleNamespace(
        # (relay url, event) for every publish attempt
        published=[],
        # (relay url, filters) for every lookup
        queries=[],
        # Relays that can not be reached, or that refuse everything
        down=set(),
        refuse=set(),
        # Recipients whose messages are always refused
        refuse_pubkeys=set(),
        # Stored events returned by lookups, by kind
        events={},
        # Relays only allowed to reach public addresses
        public_only=set(),
    )

    class Relay:
        def __init__(self, url, key, public_only=False, **kwargs):
            self.url = url
            if public_only:
                state.public_only.add(url)

        def __enter__(self):
            if self.url in state.down:
                raise AppriseSocketError("down")
            return self

        def __exit__(self, *args):
            return None

        def publish(self, event):
            state.published.append((self.url, event))
            p_tags = {t[1] for t in event["tags"] if t[0] == "p"}
            if self.url in state.refuse or p_tags & state.refuse_pubkeys:
                return (False, "blocked: no")
            return (True, "")

        def query(self, filters):
            state.queries.append((self.url, filters))
            return list(state.events.get(filters["kinds"][0], []))

    with mock.patch("apprise.plugins.nostr.base.NostrRelay", Relay):
        yield state


def _ok_response(content=OK_REPLY, code=requests.codes.ok):
    """Return a mocked requests response."""
    response = mock.Mock()
    response.status_code = code
    response.content = content
    response.iter_content.return_value = [content]
    response.headers = {}
    return response


def _blossom_reply(url, data=None, **kwargs):
    """Answer a Blossom upload with a description of the stored file."""
    return _ok_response(
        dumps(
            {
                "url": BLOB_URL,
                "sha256": hashlib.sha256(data).hexdigest(),
                "size": len(data),
            }
        ).encode(),
        code=requests.codes.created,
    )


# JSON nested far deeper than Python can decode
NESTED = b"[" * 100000 + b"]" * 100000


def _inbox(*keys, url="wss://one.example.com"):
    """Return NIP-17 relay lists (kind 10050) for each key."""
    return [key.sign(10050, "", [["relay", url]]) for key in keys]


def _nip44_decrypt(payload, conversation_key):
    """Decrypt a NIP-44 payload so tests can read what was sent."""
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms

    raw = b64decode(payload)
    nonce, ciphertext, mac = raw[1:33], raw[33:-32], raw[-32:]
    keys = b""
    block = b""
    for counter in range(1, 4):
        block = hmac.new(
            conversation_key,
            block + nonce + bytes([counter]),
            hashlib.sha256,
        ).digest()
        keys += block

    expected = hmac.new(keys[44:76], nonce + ciphertext, hashlib.sha256)
    assert expected.digest() == mac
    padded = (
        Cipher(algorithms.ChaCha20(keys[:32], bytes(4) + keys[32:44]), None)
        .decryptor()
        .update(ciphertext)
    )
    size = int.from_bytes(padded[:2], "big")
    return padded[2 : 2 + size].decode("utf-8")


def _unwrap(wrap, key=RECIPIENT):
    """Return the message hidden inside a NIP-17 gift wrap."""
    seal = loads(
        _nip44_decrypt(wrap["content"], key.conversation_key(wrap["pubkey"]))
    )
    assert seal["kind"] == 13
    assert crypto.verify_event(seal)
    message = loads(
        _nip44_decrypt(seal["content"], key.conversation_key(seal["pubkey"]))
    )
    assert message["pubkey"] == seal["pubkey"] == SENDER.public_key
    return message


def test_plugin_nostr_urls(relays):
    """NotifyNostr() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


def test_plugin_nostr_init():
    """NotifyNostr() loads keys, recipients, relays and options."""
    obj = NotifyNostr(
        secret_key="11" * 32,
        targets=[NPUB, RECIPIENT.public_key.upper(), "Alice@Example.com", "x"],
        relay="relay.example.com, ws://10.0.0.1:7777/path",
        blossom="https://cdn.example.com/",
        mode="NIP04",
    )
    assert obj.key.public_key == SENDER.public_key
    assert obj.targets == [
        RECIPIENT.public_key,
        RECIPIENT.public_key,
        "alice@example.com",
    ]
    assert obj.invalid_targets == ["x"]
    assert obj.relays == [
        "wss://relay.example.com",
        "ws://10.0.0.1:7777/path",
    ]
    assert obj.blossom == "https://cdn.example.com"
    assert obj.mode == NostrMode.NIP04
    assert len(obj) == 3

    # Everything survives a round trip through the URL
    obj2 = Apprise.instantiate(obj.url())
    assert isinstance(obj2, NotifyNostr)
    assert obj2.url_identifier == obj.url_identifier
    assert obj2.targets == obj.targets
    assert obj2.invalid_targets == obj.invalid_targets
    assert obj2.relays == obj.relays
    assert obj2.blossom == obj.blossom
    assert obj2.mode == obj.mode

    # Defaults, and recipients given with ?to=
    obj = Apprise.instantiate(
        "nostr://{}?to={},bob@example.com".format(NSEC, NPUB)
    )
    assert sorted(obj.targets) == sorted(
        [RECIPIENT.public_key, "bob@example.com"]
    )
    assert obj.mode == NostrMode.NIP17
    assert obj.blossom is None
    assert "relay=" not in obj.url()
    assert "mode=" not in obj.url()
    assert NPUB in obj.url()

    # A public note still counts as one notification
    assert len(NotifyNostr(secret_key=NSEC)) == 1

    # The public key is the identity, whatever form the key came in
    assert (
        NotifyNostr(secret_key=NSEC).url_identifier
        == NotifyNostr(secret_key="11" * 32).url_identifier
        == ("nostr", SENDER.public_key)
    )

    # An npub is not a secret key
    with pytest.raises(AppriseImproperlyConfigured):
        NotifyNostr(secret_key=NPUB)


def test_plugin_nostr_note(relays):
    """NotifyNostr() posts a signed public note to every relay."""
    obj = NotifyNostr(
        secret_key=NSEC, relay="wss://one.example.com,wss://two.example.com"
    )
    assert obj.notify("Hello & <world>", title="Title") is True

    # The same note reached both relays
    assert [url for url, _ in relays.published] == [
        "wss://one.example.com",
        "wss://two.example.com",
    ]
    event = relays.published[0][1]
    assert relays.published[1][1] is event
    assert event["kind"] == 1
    assert event["pubkey"] == SENDER.public_key
    assert event["content"] == "Title\r\nHello & <world>"
    assert event["tags"] == []
    assert crypto.verify_event(event)

    # One relay accepting it is enough
    relays.published.clear()
    relays.refuse.add("wss://one.example.com")
    assert obj.notify("Hello") is True

    relays.down.add("wss://two.example.com")
    assert obj.notify("Hello") is False


@mock.patch("requests.put")
def test_plugin_nostr_note_attachments(mock_put, relays):
    """NotifyNostr() uploads attachments and links them in a note."""
    mock_put.side_effect = _blossom_reply
    path = os.path.join(TEST_VAR_DIR, "apprise-test.png")
    with open(path, "rb") as f:
        data = f.read()

    obj = NotifyNostr(
        secret_key=NSEC,
        relay="wss://one.example.com",
        blossom="cdn.example.com",
    )
    assert obj.notify("Look", attach=AppriseAttachment(path)) is True

    # The upload went to the Blossom server with a signed permission
    assert mock_put.call_count == 1
    url = mock_put.call_args[0][0]
    assert url == "https://cdn.example.com/upload"
    kwargs = mock_put.call_args[1]
    assert kwargs["data"] == data
    digest = hashlib.sha256(data).hexdigest()
    assert kwargs["headers"]["X-SHA-256"] == digest
    assert kwargs["headers"]["Content-Type"] == "image/png"
    token = kwargs["headers"]["Authorization"].split(" ", 1)[1]
    assert "=" not in token
    auth = loads(b64decode(token + "=" * (-len(token) % 4), altchars=b"-_"))
    assert auth["kind"] == 24242
    assert ["t", "upload"] in auth["tags"]
    assert ["x", digest] in auth["tags"]
    assert crypto.verify_event(auth)

    # The note links the file and describes it
    event = relays.published[0][1]
    assert event["content"] == "Look\n{}".format(BLOB_URL)
    assert event["tags"] == [
        [
            "imeta",
            "url {}".format(BLOB_URL),
            "m image/png",
            "x {}".format(digest),
            "size {}".format(len(data)),
        ]
    ]

    # An attachment with no body is fine too
    relays.published.clear()
    assert obj.notify("", attach=AppriseAttachment(path)) is True
    assert relays.published[0][1]["content"] == BLOB_URL


@mock.patch("requests.put")
def test_plugin_nostr_attach_errors(mock_put, relays):
    """NotifyNostr() fails cleanly when an attachment can not be sent."""
    path = os.path.join(TEST_VAR_DIR, "apprise-test.png")
    obj = NotifyNostr(secret_key=NSEC, blossom="cdn.example.com")

    # An inaccessible file is never uploaded
    with mock.patch("os.path.isfile", return_value=False):
        assert obj.notify("x", attach=AppriseAttachment(path)) is False
    assert mock_put.call_count == 0

    # Neither is one that can not be read
    attach = AppriseAttachment(path)
    with mock.patch("builtins.open", side_effect=OSError):
        assert obj.notify("x", attach=attach) is False
    assert mock_put.call_count == 0

    # The Blossom server can not be reached
    mock_put.side_effect = requests.RequestException("no")
    assert obj.notify("x", attach=AppriseAttachment(path)) is False
    mock_put.side_effect = None

    # The Blossom server refuses it
    mock_put.return_value = _ok_response(code=401)
    mock_put.return_value.headers = {"X-Reason": "denied"}
    assert obj.notify("x", attach=AppriseAttachment(path)) is False

    # The answer has no usable link, or does not describe our file
    with open(path, "rb") as f:
        data = f.read()

    good = {
        "url": BLOB_URL,
        "sha256": hashlib.sha256(data).hexdigest(),
        "size": len(data),
    }
    for content in (
        b"not json",
        NESTED,
        b"[]",
        b"x" * 1048577,
        dumps(dict(good, url="ftp://x")).encode(),
        dumps(dict(good, url="http://cdn.example.com/abc.png")).encode(),
        dumps(dict(good, url="https://x/" + "a" * 2048)).encode(),
        dumps(dict(good, sha256="0" * 64)).encode(),
        dumps(dict(good, size=1)).encode(),
    ):
        mock_put.return_value = _ok_response(content=content)
        assert obj.notify("x", attach=AppriseAttachment(path)) is False

    # Nothing was ever published
    assert relays.published == []


@mock.patch("requests.put")
def test_plugin_nostr_blossom_lookup(mock_put, relays):
    """NotifyNostr() finds our own Blossom server list, or uses a default."""
    mock_put.side_effect = _blossom_reply
    path = os.path.join(TEST_VAR_DIR, "apprise-test.png")

    # Our own (kind 10063) list names the server to use
    relays.events[10063] = [
        SENDER.sign(
            10063,
            "",
            [
                ["server", "http://insecure.example.com"],
                ["server", "https://mine.example.com/"],
            ],
        )
    ]
    obj = NotifyNostr(secret_key=NSEC, relay="wss://one.example.com")
    assert obj.notify("x", attach=AppriseAttachment(path)) is True
    assert mock_put.call_args[0][0] == "https://mine.example.com/upload"
    assert relays.queries[0][1] == {
        "kinds": [10063],
        "authors": [SENDER.public_key],
        "limit": 1,
    }

    # The answer is cached
    assert obj.notify("x", attach=AppriseAttachment(path)) is True
    assert len(relays.queries) == 1

    # Without a list, the default server is used
    relays.events.clear()
    obj = NotifyNostr(secret_key=NSEC, relay="wss://one.example.com")
    assert obj.notify("x", attach=AppriseAttachment(path)) is True
    assert mock_put.call_args[0][0] == NOSTR_DEFAULT_BLOSSOM + "/upload"

    # When no relay can be asked, the default is used but not remembered
    relays.down.add("wss://one.example.com")
    obj = NotifyNostr(secret_key=NSEC, relay="wss://one.example.com")
    assert obj.notify("x", attach=AppriseAttachment(path)) is False
    assert mock_put.call_args[0][0] == NOSTR_DEFAULT_BLOSSOM + "/upload"
    assert obj.store.get("blossom") is None

    # A plain http:// server of our own may hand back http:// links
    relays.down.clear()
    mock_put.side_effect = None
    with open(path, "rb") as f:
        data = f.read()

    mock_put.return_value = _ok_response(
        dumps(
            {
                "url": "http://10.0.0.1/abc.png",
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        ).encode()
    )
    obj = NotifyNostr(
        secret_key=NSEC,
        relay="wss://one.example.com",
        blossom="http://10.0.0.1",
    )
    assert obj.notify("x", attach=AppriseAttachment(path)) is True


def test_plugin_nostr_lookup(relays):
    """NotifyNostr() only trusts the newest correctly signed list."""
    obj = NotifyNostr(
        secret_key=NSEC,
        relay="wss://down.example.com,wss://one.example.com",
    )
    relays.down.add("wss://down.example.com")

    older = RECIPIENT.sign(
        10050, "", [["relay", "wss://old.example.com"]], 100
    )
    newer = RECIPIENT.sign(
        10050,
        "",
        [
            ["relay", "wss://new.example.com"],
            ["relay", "wss://new.example.com"],
            ["relay", "ws://insecure.example.com"],
            ["relay", "wss://:7777"],
            ["relay", "wss://bad-port.example.com:99999"],
            ["relay", "wss://{}.example.com".format("a" * 256)],
            ["relay", "wss://example.com/{}".format("a" * 2048)],
            ["relay", "wss://two.example.com"],
            ["relay", "wss://three.example.com"],
            ["relay", "wss://four.example.com"],
            ["relay"],
            ["other", "wss://x.example.com"],
        ],
        200,
    )
    oldest = RECIPIENT.sign(10050, "", [["relay", "wss://x.example.com"]], 50)
    forged = dict(newer, created_at=300)
    stranger = OTHER.sign(10050, "", [["relay", "wss://x.example.com"]], 400)
    wrong_kind = RECIPIENT.sign(1, "", [["relay", "wss://x.example.com"]], 500)
    malformed = dict(newer, tags=1, created_at=[])
    relays.events[10050] = [
        older,
        newer,
        oldest,
        forged,
        stranger,
        wrong_kind,
        malformed,
    ]

    # Duplicates and broken entries are dropped, and only 3 are used
    expected = [
        "wss://new.example.com",
        "wss://two.example.com",
        "wss://three.example.com",
    ]
    assert obj._inbox_relays(RECIPIENT.public_key) == expected

    # The answer is cached, so the relays are not asked again
    queries = len(relays.queries)
    assert obj._inbox_relays(RECIPIENT.public_key) == expected
    assert len(relays.queries) == queries

    # A recipient without a list has no relays
    relays.events.clear()
    assert obj._inbox_relays(OTHER.public_key) == []

    # When no relay can be asked, the lookup failed and is not cached
    relays.down.add("wss://one.example.com")
    assert obj._inbox_relays(SENDER.public_key) is None
    assert obj.store.get("inbox_{}".format(SENDER.public_key)) is None


@mock.patch("requests.get")
def test_plugin_nostr_nip05(mock_get, relays):
    """NotifyNostr() looks up Nostr addresses and caches them."""
    obj = NotifyNostr(secret_key=NSEC, targets="alice@example.com")
    mock_get.return_value = _ok_response()

    assert obj._resolve("alice@example.com") == RECIPIENT.public_key
    assert mock_get.call_args[0][0] == (
        "https://example.com/.well-known/nostr.json"
    )
    assert mock_get.call_args[1]["params"] == {"name": "alice"}
    assert mock_get.call_args[1]["allow_redirects"] is False
    assert mock_get.call_args[1]["stream"] is True

    # The answer is cached
    assert obj._resolve("alice@example.com") == RECIPIENT.public_key
    assert mock_get.call_count == 1

    # Public keys need no lookup
    assert obj._resolve(OTHER.public_key) == OTHER.public_key
    assert mock_get.call_count == 1

    # Names that are missing, malformed or refused are not found
    for response in (
        _ok_response(content=b'{"names": {"bob": "zz"}}'),
        _ok_response(content=dumps({"names": {"bob": "f" * 64}}).encode()),
        _ok_response(content=b'{"names": []}'),
        _ok_response(content=b"[]"),
        _ok_response(content=b"garbage"),
        _ok_response(content=NESTED),
        _ok_response(content=b"x" * 1048577),
        _ok_response(code=404),
    ):
        mock_get.return_value = response
        assert obj._resolve("bob@example.com") is None

    mock_get.side_effect = requests.RequestException("no")
    assert obj._resolve("bob@example.com") is None


def test_plugin_nostr_nip17(relays):
    """NotifyNostr() sends sealed, gift wrapped private messages."""
    pytest.importorskip("cryptography")
    obj = NotifyNostr(
        secret_key=NSEC, targets=NPUB, relay="wss://one.example.com"
    )

    # A recipient without a list of relays can not be sent to
    assert obj.notify("Hello") is False
    assert relays.published == []

    # Nor can one whose list could not be looked up
    relays.down.add("wss://one.example.com")
    obj = NotifyNostr(
        secret_key=NSEC, targets=NPUB, relay="wss://one.example.com"
    )
    assert obj.notify("Hello") is False
    assert relays.published == []
    relays.down.clear()

    relays.events[10050] = _inbox(RECIPIENT, url="wss://inbox.example.com")
    obj = NotifyNostr(
        secret_key=NSEC, targets=NPUB, relay="wss://one.example.com"
    )
    assert obj.notify("Hello & <world> é", title="Title") is True

    # The message went only to the recipient's own inbox relay, and only
    # to a public address
    assert len(relays.published) == 1
    url, wrap = relays.published[0]
    assert url == "wss://inbox.example.com"
    assert relays.public_only == {"wss://inbox.example.com"}
    assert wrap["kind"] == 1059
    assert wrap["tags"] == [["p", RECIPIENT.public_key]]
    assert wrap["pubkey"] != SENDER.public_key
    assert crypto.verify_event(wrap)

    message = _unwrap(wrap)
    assert message["kind"] == 14
    assert message["content"] == "Title\r\nHello & <world> é"
    assert message["tags"] == [["p", RECIPIENT.public_key]]
    assert "sig" not in message

    # When we list relays of our own, we keep a copy there too
    relays.published.clear()
    relays.events[10050] += _inbox(SENDER, url="wss://mine.example.com")
    obj = NotifyNostr(
        secret_key=NSEC, targets=NPUB, relay="wss://one.example.com"
    )
    assert obj.notify("Hello") is True
    assert [url for url, _ in relays.published] == [
        "wss://inbox.example.com",
        "wss://mine.example.com",
    ]
    copy = relays.published[1][1]
    assert copy["tags"] == [["p", SENDER.public_key]]
    assert _unwrap(copy, SENDER)["content"] == "Hello"
    assert _unwrap(copy, SENDER)["tags"] == [["p", RECIPIENT.public_key]]

    # Our own list is trusted, so it may name private relays
    assert relays.public_only == {"wss://inbox.example.com"}

    # Losing our own copy does not fail the message
    relays.refuse.add("wss://mine.example.com")
    assert obj.notify("Hello") is True

    # A message to ourselves is sent once, and our own relays may be
    # private ones
    relays.published.clear()
    relays.public_only.clear()
    relays.refuse.clear()
    obj = NotifyNostr(
        secret_key=NSEC,
        targets=bech32_encode("npub", bytes.fromhex(SENDER.public_key)),
        relay="wss://one.example.com",
    )
    assert obj.notify("Hello") is True
    assert [url for url, _ in relays.published] == ["wss://mine.example.com"]
    assert relays.public_only == set()


@mock.patch("requests.put")
def test_plugin_nostr_nip17_attachments(mock_put, relays):
    """NotifyNostr() encrypts files for NIP-17 file messages."""
    pytest.importorskip("cryptography")
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    mock_put.side_effect = _blossom_reply
    relays.events[10050] = _inbox(RECIPIENT, OTHER)
    path = os.path.join(TEST_VAR_DIR, "apprise-test.png")
    with open(path, "rb") as f:
        data = f.read()

    obj = NotifyNostr(
        secret_key=NSEC,
        targets=[NPUB, NPUB_OTHER],
        relay="wss://one.example.com",
        blossom="https://cdn.example.com",
    )
    assert obj.notify("", attach=AppriseAttachment(path)) is True

    # The encrypted file was uploaded once and shared by both recipients
    assert mock_put.call_count == 1
    uploaded = mock_put.call_args[1]["data"]
    assert uploaded != data
    assert mock_put.call_args[1]["headers"]["Content-Type"] == (
        "application/octet-stream"
    )

    # No body means a file message only
    assert len(relays.published) == 2
    message = _unwrap(relays.published[0][1])
    assert message["kind"] == 15
    assert message["content"] == BLOB_URL
    tags = {t[0]: t[1] for t in message["tags"]}
    assert tags["p"] == RECIPIENT.public_key
    assert tags["file-type"] == "image/png"
    assert tags["encryption-algorithm"] == "aes-gcm"
    assert tags["x"] == hashlib.sha256(uploaded).hexdigest()
    assert tags["ox"] == hashlib.sha256(data).hexdigest()
    assert tags["size"] == str(len(uploaded))
    assert len(bytes.fromhex(tags["decryption-nonce"])) == 16
    assert (
        AESGCM(bytes.fromhex(tags["decryption-key"])).decrypt(
            bytes.fromhex(tags["decryption-nonce"]), uploaded, None
        )
        == data
    )

    # The second recipient got their own copy
    assert _unwrap(relays.published[1][1], OTHER)["content"] == BLOB_URL

    # Upload problems stop the message
    with mock.patch("os.path.isfile", return_value=False):
        assert obj.notify("x", attach=AppriseAttachment(path)) is False

    mock_put.side_effect = None
    mock_put.return_value = _ok_response(code=500)
    assert obj.notify("x", attach=AppriseAttachment(path)) is False


@mock.patch("requests.put")
def test_plugin_nostr_nip04(mock_put, relays):
    """NotifyNostr() sends older NIP-04 encrypted messages."""
    pytest.importorskip("cryptography")
    from cryptography.hazmat.primitives import padding
    from cryptography.hazmat.primitives.ciphers import (
        Cipher,
        algorithms,
        modes,
    )

    mock_put.side_effect = _blossom_reply
    path = os.path.join(TEST_VAR_DIR, "apprise-test.png")
    obj = Apprise.instantiate(
        "nostr://{}/{}?mode=nip04&relay=wss://one.example.com"
        "&blossom=cdn.example.com".format(NSEC, NPUB)
    )
    assert obj.notify("Hello", attach=AppriseAttachment(path)) is True

    # Published to our own relays and tagged for the recipient
    url, event = relays.published[0]
    assert url == "wss://one.example.com"
    assert event["kind"] == 4
    assert event["tags"] == [["p", RECIPIENT.public_key]]
    assert crypto.verify_event(event)

    # The recipient can read the text and the file link
    ciphertext, iv = event["content"].split("?iv=")
    decryptor = Cipher(
        algorithms.AES(RECIPIENT.shared_x(SENDER.public_key)),
        modes.CBC(b64decode(iv)),
    ).decryptor()
    unpadder = padding.PKCS7(128).unpadder()
    text = (
        unpadder.update(
            decryptor.update(b64decode(ciphertext)) + decryptor.finalize()
        )
        + unpadder.finalize()
    )
    assert text.decode() == "Hello\n{}".format(BLOB_URL)

    # Upload problems stop the message
    mock_put.side_effect = None
    mock_put.return_value = _ok_response(code=500)
    assert obj.notify("x", attach=AppriseAttachment(path)) is False


@mock.patch("requests.get")
def test_plugin_nostr_dm_errors(mock_get, relays):
    """NotifyNostr() reports recipients that could not be reached."""
    pytest.importorskip("cryptography")

    # A Nostr address that can not be found
    mock_get.return_value = _ok_response(code=404)
    relays.events[10050] = _inbox(RECIPIENT)
    obj = NotifyNostr(
        secret_key=NSEC,
        targets=["nobody@example.com", NPUB],
        relay="wss://one.example.com",
    )
    assert obj.notify("Hello") is False

    # The other recipient still got it
    assert len(relays.published) == 1
    assert _unwrap(relays.published[0][1])["content"] == "Hello"

    # Direct messages need the cryptography package
    with mock.patch(
        "apprise.plugins.nostr.base.NOSTR_CRYPTOGRAPHY_SUPPORT", False
    ):
        assert obj.notify("Hello") is False


def test_plugin_nostr_retry(relays):
    """NotifyNostr() retries only the recipient that failed."""
    pytest.importorskip("cryptography")
    relays.refuse_pubkeys.add(OTHER.public_key)
    relays.events[10050] = _inbox(RECIPIENT, OTHER)

    apobj = Apprise()
    assert apobj.add(
        "nostr://{}/{}/{}?relay=wss://one.example.com&retry=2&wait=0".format(
            NSEC, NPUB, NPUB_OTHER
        )
    )
    assert not apobj.notify("Hello", notify_type=NotifyType.INFO)

    # The healthy recipient was contacted once; the broken one 3 times
    sent = [event["tags"][0][1] for _, event in relays.published]
    assert sent.count(RECIPIENT.public_key) == 1
    assert sent.count(OTHER.public_key) == 3

    # Each retry resent the very same event, so relays can spot it
    retried = [
        e for _, e in relays.published if e["tags"][0][1] == OTHER.public_key
    ]
    assert len({e["id"] for e in retried}) == 1


def test_plugin_nostr_note_retry(relays):
    """NotifyNostr() resends the same public note on a retry."""
    relays.refuse.add("wss://one.example.com")
    apobj = Apprise()
    assert apobj.add(
        "nostr://{}?relay=wss://one.example.com&retry=1&wait=0".format(NSEC)
    )
    assert not apobj.notify("Hello")
    assert len(relays.published) == 2
    assert relays.published[0][1]["id"] == relays.published[1][1]["id"]


@mock.patch("requests.put")
def test_plugin_nostr_upload_retry(mock_put, relays):
    """NotifyNostr() reuses uploads when a message is retried."""
    pytest.importorskip("cryptography")
    mock_put.side_effect = _blossom_reply
    relays.refuse.add("wss://one.example.com")
    relays.events[10050] = _inbox(RECIPIENT)
    path = os.path.join(TEST_VAR_DIR, "apprise-test.png")

    for mode in ("nip04", "nip17"):
        mock_put.reset_mock()
        apobj = Apprise()
        assert apobj.add(
            "nostr://{}/{}?relay=wss://one.example.com&blossom=cdn.example.com"
            "&mode={}&retry=1&wait=0".format(NSEC, NPUB, mode)
        )
        assert not apobj.notify("x", attach=AppriseAttachment(path))
        assert mock_put.call_count == 1


def test_plugin_nostr_crypto():
    """Nostr signing and key helpers match their specifications."""
    # A BIP-340 test vector (index 0)
    key = NostrKey(3)
    assert key.public_key == (
        "f9308a019258c31049344f85f89d5229b531c845836f99b08601f113bce036f9"
    )

    # A secret key whose public point has an odd y is still usable
    odd = NostrKey(int("22" * 32, 16))
    assert crypto.verify_event(odd.sign(1, "x"))

    # A random key is made when none is given
    assert NostrKey().public_key != NostrKey().public_key

    # The NIP-19 example key
    hexkey = "3bf0c63fcb93463407af97a5e5ee64fa883d107ef9e558472c4eb9aaaefa459d"
    npub = "npub180cvv07tjdrrgpa0j7j7tmnyl2yr6yr7l8j4s3evf6u64th6gkwsyjh6w6"
    assert bech32_encode("npub", bytes.fromhex(hexkey)) == npub
    assert crypto.decode_key(npub, "npub") == hexkey
    assert crypto.decode_key(npub.upper(), "npub") == hexkey
    assert crypto.decode_key(hexkey.upper(), "nsec") == hexkey

    # Data that fits 5-bit groups exactly needs no padding
    assert crypto.bech32_decode(bech32_encode("x", bytes(5))) == (
        "x",
        bytes(5),
    )

    # Things that are not keys
    assert crypto.decode_key(None, "npub") is None
    assert crypto.decode_key(npub, "nsec") is None
    assert crypto.decode_key(npub[:-1] + "q", "npub") is None
    assert crypto.decode_key("npub1b", "npub") is None
    assert crypto.decode_key("npub1" + "b" * 10 + "!", "npub") is None
    assert crypto.decode_key("1qqqqqqqq", "npub") is None
    assert crypto.decode_key(bech32_encode("npub", b"\x01"), "npub") is None

    # Leftover bits are not allowed when decoding
    assert crypto._convert_bits(bytes([31, 31]), 5, 8, False) is None
    assert crypto._convert_bits(bytes([1]), 5, 8, False) is None
    assert (
        crypto.bech32_decode(
            "a1"
            + "".join(
                crypto.BECH32_CHARSET[v]
                for v in [1]
                + [
                    (
                        crypto._bech32_polymod(
                            crypto._bech32_hrp_expand("a") + [1] + [0] * 6
                        )
                        ^ 1
                    )
                    >> 5 * (5 - i)
                    & 31
                    for i in range(6)
                ]
            )
        )
        is None
    )

    # Points that are not on the curve
    assert crypto._lift_x(crypto.SECP256K1_P) is None
    assert crypto._lift_x(5) is None
    assert crypto.is_public_key("f" * 64) is False
    g = crypto.SECP256K1_G
    assert crypto._point_add(g, None) == g
    assert crypto._point_add(g, (g[0], crypto.SECP256K1_P - g[1])) is None


def test_plugin_nostr_verify():
    """Only well formed, correctly signed events are trusted."""
    event = SENDER.sign(1, "hello", [["t", "x"]])
    assert crypto.verify_event(event) is True

    # Anything changed or missing breaks it
    assert crypto.verify_event(dict(event, content="bye")) is False
    assert crypto.verify_event(dict(event, sig="00")) is False
    assert crypto.verify_event(dict(event, pubkey="f" * 64)) is False
    assert crypto.verify_event(dict(event, sig="zz")) is False
    assert crypto.verify_event({"pubkey": event["pubkey"]}) is False
    assert crypto.verify_event(None) is False

    # Fields of the wrong type are refused before anything else
    nested = []
    for _ in range(100000):
        nested = [nested]

    for changes in (
        {"tags": 1},
        {"tags": [1]},
        {"tags": [["t", 1]]},
        {"tags": nested},
        {"created_at": []},
        {"created_at": True},
        {"kind": "1"},
        {"content": None},
        {"id": event["id"].upper() + "0"},
        {"pubkey": 1},
        {"sig": event["sig"].upper()},
    ):
        assert crypto.verify_event(dict(event, **changes)) is False

    # A signature from someone else
    other = OTHER.sign(1, "hello", [["t", "x"]], event["created_at"])
    assert (
        crypto.verify_event(
            dict(other, pubkey=event["pubkey"], id=event["id"])
        )
        is False
    )

    # Signature halves outside of their allowed range
    r_big = "f" * 64 + event["sig"][64:]
    s_big = event["sig"][:64] + "f" * 64
    assert crypto.verify_event(dict(event, sig=r_big)) is False
    assert crypto.verify_event(dict(event, sig=s_big)) is False


def test_plugin_nostr_nip44():
    """NIP-44 encryption matches the official test vectors."""
    pytest.importorskip("cryptography")

    # From https://github.com/paulmillr/nip44 (nip44.vectors.json)
    sec1 = NostrKey(int("0" * 63 + "1", 16))
    sec2 = NostrKey(int("0" * 63 + "2", 16))
    conversation_key = sec1.conversation_key(sec2.public_key)
    assert conversation_key.hex() == (
        "c41c775356fd92eadc63ff5a0dc1da211b268cbea22316767095b2871ea1412d"
    )
    assert crypto.nip44_encrypt(
        "a", conversation_key, bytes.fromhex("0" * 63 + "1")
    ) == (
        "AgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABee0G5VSK0/9YypIObAtDKfYE"
        "AjD35uVkHyB0F4DwrcNaCXlCWZKaArsGrY6M9wnuTMxWfp1RTN9Xga8no+kF5Vsb"
    )

    # The two keys always agree on the conversation key
    assert sec2.conversation_key(sec1.public_key) == conversation_key

    # Padding sizes
    assert crypto._nip44_padded_len(1) == 32
    assert crypto._nip44_padded_len(33) == 64
    assert crypto._nip44_padded_len(257) == 320
    assert crypto._nip44_padded_len(65536) == 65536

    # Very long messages use the longer length prefix
    payload = crypto.nip44_encrypt("x" * 70000, conversation_key)
    assert _nip44_decrypt(payload, conversation_key) == ""
    raw = b64decode(payload)
    assert raw[33:39] != b""


def _frame(payload, opcode=0x1, fin=True):
    """Build an unmasked frame as a relay would send it."""
    if isinstance(payload, (list, dict)):
        payload = dumps(payload)
    if isinstance(payload, str):
        payload = payload.encode()

    header = bytearray([(0x80 if fin else 0) | opcode])
    if len(payload) < 126:
        header.append(len(payload))
    elif len(payload) < 65536:
        header.append(126)
        header += len(payload).to_bytes(2, "big")
    else:
        header.append(127)
        header += len(payload).to_bytes(8, "big")
    return bytes(header) + payload


class FakeTransport:
    """Plays the relay side of a websocket connection."""

    def __init__(self, responder=None, greeting=b"", status=None, chunk=65536):
        # Called with each message we send; returns frames to answer with
        self.responder = responder or (lambda message: [])

        # Frames sent right after the handshake, and a replacement status
        self.greeting = greeting
        self.status = status

        # How many bytes each read hands back
        self.chunk = chunk

        # What the relay will hand back, and what it received
        self.inbox = bytearray()
        self.frames = []
        self.messages = []
        self.request = b""
        self.closed = False

        # Where we connect to, and how often we did
        self.host = "relay.example.com"
        self.connects = 0

        # Addresses that refuse our connection, after a delay, and every
        # (address, timeout) we tried
        self.refuse_hosts = set()
        self.refuse_delay = 0
        self.tried = []

    def connect(self, timeout=None):
        self.connects += 1
        self.tried.append((self.host, timeout))
        if self.host in self.refuse_hosts:
            time.sleep(self.refuse_delay)
            raise AppriseSocketError("refused")

    def close(self):
        self.closed = True

    def write(self, data, timeout=None):
        if data.startswith(b"GET "):
            # Answer the websocket upgrade
            self.request = data
            key = re.search(rb"Sec-WebSocket-Key: (\S+)", data).group(1)
            accept = b64encode(
                hashlib.sha1(key + WS_ACCEPT_GUID.encode()).digest()
            )
            self.inbox += self.status or (
                b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket"
                b"\r\nSec-WebSocket-Accept: " + accept + b"\r\n\r\n"
            )
            self.inbox += self.greeting
            return len(data)

        # Every frame we send must be masked
        assert data[1] & 0x80
        length = data[1] & 0x7F
        offset = {126: 4, 127: 10}.get(length, 2)
        if offset > 2:
            length = int.from_bytes(data[2:offset], "big")
        mask = data[offset : offset + 4]
        payload = bytes(
            b ^ mask[i % 4]
            for i, b in enumerate(data[offset + 4 : offset + 4 + length])
        )
        assert len(payload) == length
        self.frames.append((data[0] & 0x0F, payload))
        if data[0] & 0x0F == 0x1:
            message = loads(payload)
            self.messages.append(message)
            for reply in self.responder(message):
                self.inbox += (
                    reply if isinstance(reply, bytes) else _frame(reply)
                )
        return len(data)

    def read(self, max_bytes=65536, blocking=True, timeout=None):
        size = min(max_bytes, self.chunk)
        data = bytes(self.inbox[:size])
        del self.inbox[:size]
        return data


def _relay(
    transport, url="wss://relay.example.com", timeout=1.0, public_only=False
):
    """Return a NostrRelay that talks to ``transport``."""
    with mock.patch(
        "apprise.plugins.nostr.relay.RelayTransport", return_value=transport
    ):
        return NostrRelay(
            url,
            SENDER,
            timeout=(timeout, timeout),
            public_only=public_only,
        )


def test_plugin_nostr_relay_publish():
    """NostrRelay publishes, logging in when the relay asks for it."""

    def responder(message):
        if message[0] == "EVENT":
            if not authenticated:
                return [
                    ["OK", "other", True, ""],
                    ["OK", message[1]["id"], False, "auth-required: hi"],
                ]
            return [["OK", message[1]["id"], True]]

        if message[0] == "AUTH":
            authenticated.append(message[1])
            return [["OK", message[1]["id"], True, ""]]
        return []

    authenticated = []
    greeting = b"".join(
        (
            _frame(["AUTH", "challenge-1"]),
            _frame(b"ping!", opcode=0x9),
            _frame(b"pong", opcode=0xA),
            _frame("not json"),
            _frame({"not": "a list"}),
            _frame([]),
            _frame(["NOTICE", "x" * 70000]),
            _frame(NESTED),
            _frame('["NOTICE",', fin=False),
            _frame('"split"]', opcode=0x0),
        )
    )
    transport = FakeTransport(responder, greeting=greeting, chunk=7)
    event = SENDER.sign(1, "y" * 300)
    with _relay(transport, url="wss://relay.example.com:8443/n?x=1") as relay:
        assert relay.publish(event) == (True, "")

    # The handshake named the right host and path
    assert transport.request.startswith(b"GET /n?x=1 HTTP/1.1\r\n")
    assert b"Host: relay.example.com:8443\r\n" in transport.request

    # We answered the ping, logged in, then resent the event
    assert (0xA, b"ping!") in transport.frames
    assert [m[0] for m in transport.messages] == ["EVENT", "AUTH", "EVENT"]
    auth = authenticated[0]
    assert auth["kind"] == 22242
    assert ["challenge", "challenge-1"] in auth["tags"]
    assert ["relay", "wss://relay.example.com:8443/n?x=1"] in auth["tags"]

    # We said goodbye
    assert transport.frames[-1] == (0x8, b"\x03\xe8")
    assert transport.closed

    # Large events use the longest length field
    transport = FakeTransport(lambda m: [["OK", m[1]["id"], True, ""]])
    with _relay(transport, url="ws://relay.example.com") as relay:
        assert relay.port == 80
        assert relay.publish(SENDER.sign(1, "z" * 70000))[0] is True
    assert b"Host: relay.example.com\r\n" in transport.request


def test_plugin_nostr_relay_auth_refused():
    """NostrRelay gives up when logging in does not help."""
    # The relay refuses our login
    transport = FakeTransport(
        lambda m: [["OK", m[1]["id"], False, "auth-required: no"]],
        greeting=_frame(["AUTH", "c"]),
    )
    with _relay(transport) as relay:
        assert relay.publish(SENDER.sign(1, "x")) == (
            False,
            "auth-required: no",
        )
        # We only ever try to log in once
        assert relay.publish(SENDER.sign(1, "x"))[0] is False
    assert [m[0] for m in transport.messages] == ["EVENT", "AUTH", "EVENT"]

    # No challenge was sent, so we can not log in at all
    transport = FakeTransport(
        lambda m: [["OK", m[1]["id"], False, "auth-required: no"]]
    )
    with _relay(transport) as relay:
        assert relay.publish(SENDER.sign(1, "x"))[0] is False
    assert [m[0] for m in transport.messages] == ["EVENT"]


def test_plugin_nostr_relay_query():
    """NostrRelay collects stored events until the relay is done."""
    stored = RECIPIENT.sign(10050, "")

    def responder(message):
        if message[0] == "REQ":
            if len(requests_seen) == 0:
                requests_seen.append(message)
                return [["CLOSED", message[1], "auth-required: log in"]]

            requests_seen.append(message)
            return [
                ["EVENT", "someone-else", stored],
                ["NOTICE"],
                ["EVENT", message[1], "junk"],
                ["EVENT", message[1], stored],
                ["EOSE", message[1]],
            ]
        if message[0] == "AUTH":
            return [["OK", message[1]["id"], True, ""]]
        return []

    requests_seen = []
    transport = FakeTransport(responder, greeting=_frame(["AUTH", "c"]))
    with _relay(transport) as relay:
        assert relay.query({"kinds": [10050]}) == [stored]

    assert [m[0] for m in transport.messages] == [
        "REQ",
        "AUTH",
        "REQ",
        "CLOSE",
    ]

    # A subscription closed for another reason returns what it has
    transport = FakeTransport(
        lambda m: [["CLOSED", m[1]]] if m[0] == "REQ" else []
    )
    with _relay(transport) as relay:
        assert relay.query({"kinds": [1]}) == []

    # No more events are kept than were asked for
    transport = FakeTransport(
        lambda m: (
            [["EVENT", m[1], stored], ["EVENT", m[1], stored]]
            if m[0] == "REQ"
            else []
        )
    )
    with _relay(transport) as relay:
        assert relay.query({"kinds": [10050], "limit": 1}) == [stored]
    assert [m[0] for m in transport.messages] == ["REQ", "CLOSE"]


def test_plugin_nostr_relay_errors():
    """NostrRelay raises socket errors for broken connections."""
    # Not upgraded to a websocket
    transport = FakeTransport(status=b"HTTP/1.1 403 Forbidden\r\n\r\n")
    with pytest.raises(AppriseSocketError), _relay(transport):
        pass

    # Upgraded, but without proof the server understood us
    transport = FakeTransport(
        status=b"HTTP/1.1 101 OK\r\nSec-WebSocket-Accept: nope\r\n\r\n"
    )
    with pytest.raises(AppriseSocketError), _relay(transport):
        pass

    # The relay hangs up on us
    transport = FakeTransport(lambda m: [_frame(b"", opcode=0x8)])
    with pytest.raises(AppriseSocketError), _relay(transport) as relay:
        relay.publish(SENDER.sign(1, "x"))

    # The relay never answers
    transport = FakeTransport()
    with (
        pytest.raises(AppriseSocketError),
        _relay(transport, timeout=0.05) as relay,
    ):
        relay.publish(SENDER.sign(1, "x"))

    # A relay from someone's list that only leads to private (or IPv6)
    # addresses, or can not be looked up, is never connected to
    def addresses(*hosts):
        return [
            (
                socket.AF_INET6 if ":" in host else socket.AF_INET,
                socket.SOCK_STREAM,
                6,
                "",
                (host, 443),
            )
            for host in hosts
        ]

    for found in (
        addresses("10.0.0.1", "127.0.0.1"),
        addresses("2606:4700::1"),
        socket.gaierror("unknown host"),
        UnicodeError("label too long"),
    ):
        transport = FakeTransport()
        with (
            mock.patch("socket.getaddrinfo", side_effect=[found]),
            pytest.raises(AppriseSocketError),
            _relay(transport, public_only=True),
        ):
            pass
        assert transport.connects == 0

    # ... while each public address is tried in turn until one works
    transport = FakeTransport()
    transport.refuse_hosts.add("93.184.216.34")
    with (
        mock.patch(
            "socket.getaddrinfo",
            return_value=addresses(
                "10.0.0.1", "2606:4700::1", "93.184.216.34", "93.184.216.35"
            ),
        ),
        _relay(transport, public_only=True),
    ):
        pass
    assert transport.host == "93.184.216.35"
    assert transport.connects == 2

    # Duplicates are tried once, only the first 4 are tried at all, and
    # every attempt shares one connection timeout
    many = ["93.184.216.{}".format(n) for n in range(1, 51)]
    transport = FakeTransport()
    transport.refuse_hosts.update(many)
    with (
        mock.patch(
            "socket.getaddrinfo",
            return_value=addresses(many[0], many[0], *many),
        ),
        pytest.raises(AppriseSocketError, match="refused"),
        _relay(transport, public_only=True),
    ):
        pass
    assert [host for host, _ in transport.tried] == many[:4]
    timeouts = [timeout for _, timeout in transport.tried]
    assert all(0 < t <= 1.0 for t in timeouts)
    assert timeouts == sorted(timeouts, reverse=True)

    # Slow refusals use up the shared timeout, so later addresses are
    # never tried
    transport = FakeTransport()
    transport.refuse_hosts.update(many)
    transport.refuse_delay = 0.06
    with (
        mock.patch("socket.getaddrinfo", return_value=addresses(*many)),
        pytest.raises(AppriseSocketError, match="Timed out"),
        _relay(transport, timeout=0.05, public_only=True),
    ):
        pass
    assert transport.connects == 1

    # ... and when none of them work, the last error is reported
    transport = FakeTransport()
    transport.refuse_hosts.add("93.184.216.34")
    with (
        mock.patch(
            "socket.getaddrinfo", return_value=addresses("93.184.216.34")
        ),
        pytest.raises(AppriseSocketError, match="refused"),
        _relay(transport, public_only=True),
    ):
        pass

    # The certificate is still checked against the relay's own name
    sock = RelayTransport("relay.example.com", "93.184.216.34", 443)
    assert sock._server_hostname_for_tls() == "relay.example.com"

    # Each connection can be given less time than the usual timeout
    with mock.patch("apprise.utils.socket.SocketTransport.connect") as conn:
        sock.connect(timeout=0.5)
        assert sock._connect_timeout == 0.5
        sock.connect()
        assert sock._connect_timeout == 0.5
        assert conn.call_count == 2

    # A handshake reply that never ends, or arrives too large all at once
    for status in (
        b"HTTP/1.1 101 OK\r\n" + b"X" * 20000,
        b"HTTP/1.1 101 OK\r\n" + b"X" * 20000 + b"\r\n\r\n",
    ):
        transport = FakeTransport(status=status)
        with pytest.raises(AppriseSocketError), _relay(transport):
            pass

    # A frame that claims to be enormous is refused before it arrives
    transport = FakeTransport(
        lambda m: [b"\x81\x7f" + (2**40).to_bytes(8, "big")]
    )
    with pytest.raises(AppriseSocketError), _relay(transport) as relay:
        relay.publish(SENDER.sign(1, "x"))

    # So is a message split into many frames that adds up to too much
    transport = FakeTransport(
        lambda m: (
            [_frame(b"x" * 60000, fin=False)]
            + [_frame(b"x" * 60000, opcode=0x0, fin=False)] * 20
        )
    )
    with pytest.raises(AppriseSocketError), _relay(transport) as relay:
        relay.publish(SENDER.sign(1, "x"))

    # A failing goodbye still closes the socket
    transport = FakeTransport()
    relay = _relay(transport)
    with mock.patch.object(transport, "write", side_effect=OSError):
        relay.close()
    assert transport.closed
