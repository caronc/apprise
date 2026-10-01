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

import base64
import hashlib
import json

# Disable logging for a cleaner testing output
import logging
from unittest import mock

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise, AppriseAttachment
from apprise.exception import AppriseImproperlyConfigured
from apprise.plugins import simplepush
from apprise.plugins.simplepush import (
    NOTIFY_SIMPLEPUSH_ENCRYPTION,
    NotifySimplePush,
)

logging.disable(logging.CRITICAL)

# A key wrap made with libsodium in JavaScript, the way the Simplepush CLI
# wraps organization keys to an integration token
SEED = "RfD2e8N6R92NKuRlF1RHlK7HHe3g2-3pGtdcuc9hOw8"
SPI = "spi_cred." + SEED
ADMIN_PUBKEY = "+YniNIIKOH65XTGVPLUsdswQU/1CGu2QYYkurmD52k4="
WRAP = (
    "YUb0wK3wrPMFzt6i7a3gkoDmbJ/QG8gbsLvAQDEnpQKgzbJ089V6m4yGCr2uZ7dvu4Hsh1Tb"
    "tFhddcrSfDBtH0xbIzRU4zzm"
)
MASTER_KEY = base64.b64decode("9g21kyfkj0gn/gllmJEtXYvUqV/BFDdcZ/wrc2qrQ0E=")

# Our Testing URLs
apprise_url_tests = (
    (
        "spush://",
        {
            # No API Token
            "instance": TypeError,
        },
    ),
    (
        "spush://{}".format("A" * 14),
        {
            # Send to your own devices
            "instance": NotifySimplePush,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "spush://A...A/?",
        },
    ),
    (
        "simplepush://{}/alerts".format("A" * 14),
        {
            # The simplepush:// alias resolves to spush://
            "instance": NotifySimplePush,
            "privacy_url": "spush://A...A/alerts?",
        },
    ),
    (
        "spush://{}/alerts/deploys".format("B" * 14),
        {
            # Send to two topics
            "instance": NotifySimplePush,
            "privacy_url": "spush://B...B/alerts/deploys?",
        },
    ),
    (
        "spush://{}/?to=alerts,deploys".format("B" * 14),
        {
            # Topics through the to= argument
            "instance": NotifySimplePush,
        },
    ),
    (
        "spush://{}/alerts?priority=5&critical_volume=0.5"
        "&sptag=db&links=https://a.example%20https://b.example&shared=yes"
        "&format=text".format("C" * 14),
        {
            "instance": NotifySimplePush,
        },
    ),
    (
        "spush://{}/alerts?priority=emergency".format("C" * 14),
        {
            "instance": NotifySimplePush,
        },
    ),
    (
        "spush://{}/alerts?priority=invalid".format("C" * 14),
        {
            "instance": TypeError,
        },
    ),
    (
        "spush://{}/alerts?priority=10".format("C" * 14),
        {
            # Not a level from 1 to 5
            "instance": TypeError,
        },
    ),
    (
        "spush://{}/alerts?priority=3.5".format("C" * 14),
        {
            "instance": TypeError,
        },
    ),
    (
        "spush://{}/alerts?priority=4&critical_volume=0.5".format("C" * 14),
        {
            # The critical volume only applies to priority 5
            "instance": TypeError,
        },
    ),
    (
        "spush://{}/alerts?priority=5&critical_volume=2".format("C" * 14),
        {
            # Out of range
            "instance": TypeError,
        },
    ),
    (
        "spush://{}/alerts?priority=5&critical_volume=loud".format("C" * 14),
        {
            "instance": TypeError,
        },
    ),
    (
        "spush://{}/alerts?topic_auth_token=abcd".format("C" * 14),
        {
            "instance": NotifySimplePush,
            "privacy_url": "spush://C...C/alerts?",
        },
    ),
    (
        "spush://{}/alerts?links={}".format(
            "C" * 14, "%20".join(["a:b"] * 26)
        ),
        {
            # Too many links
            "instance": TypeError,
        },
    ),
    (
        "spush://{}/@Alice".format("D" * 14),
        {
            # Members require an integration token
            "instance": TypeError,
        },
    ),
    (
        "spush://{}/?broadcast=yes".format("D" * 14),
        {
            # Broadcast requires an integration token
            "instance": TypeError,
        },
    ),
    (
        "spush://{}/@Alice/@Bob/site".format(SPI),
        {
            "instance": NotifySimplePush,
            "requests_response_text": {"scopes": ["send"], "enabled": False},
            "privacy_url": "spush://s...8/site/@Alice/@Bob?",
        },
    ),
    (
        "spush://{}/?broadcast=yes".format(SPI),
        {
            "instance": NotifySimplePush,
            "requests_response_text": {"scopes": ["send"], "enabled": False},
        },
    ),
    (
        "spush://{}/?broadcast=yes".format(SPI),
        {
            "instance": NotifySimplePush,
            # The keys lookup fails
            "response": False,
            "requests_response_code": requests.codes.unauthorized,
        },
    ),
    (
        "spush://{}/site?broadcast=yes".format(SPI),
        {
            # Broadcast can not be combined with targets
            "instance": TypeError,
        },
    ),
    (
        "spush://{}".format(SPI),
        {
            # An organization send needs a target
            "instance": TypeError,
        },
    ),
    (
        "spush://secret@{}/site".format(SPI),
        {
            # No password encryption for organizations
            "instance": TypeError,
        },
    ),
    (
        "spush://spi_cred/site",
        {
            # No seed
            "instance": TypeError,
        },
    ),
    (
        "spush://spi_.{}/site".format(SEED),
        {
            # No credential
            "instance": TypeError,
        },
    ),
    (
        "spush://spi_cred.AAAA/site",
        {
            # The seed is not 32 bytes
            "instance": TypeError,
        },
    ),
    (
        "spush://spi_cred.A/site",
        {
            # The seed is not base64
            "instance": TypeError,
        },
    ),
    (
        "spush://{}".format("F" * 14),
        {
            "instance": NotifySimplePush,
            # The server rejects the send
            "response": False,
            "requests_response_code": requests.codes.unauthorized,
            "requests_response_text": {
                "error": "authorization_error",
                "msg": "Invalid API token",
            },
        },
    ),
    (
        "spush://{}".format("F" * 14),
        {
            "instance": NotifySimplePush,
            # throw a bizarre code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "spush://{}".format("G" * 14),
        {
            "instance": NotifySimplePush,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracefully handle them
            "test_requests_exceptions": True,
        },
    ),
)


# Our encrypted Testing URLs
apprise_url_encrypted_tests = (
    (
        "spush://secret@{}/alerts".format("E" * 14),
        {
            # Encrypted with the topic password
            "instance": NotifySimplePush,
            "privacy_url": "spush://****@E...E/alerts?",
        },
    ),
    (
        "spush://{}/alerts?password=secret".format("E" * 14),
        {
            # Password through the password= argument
            "instance": NotifySimplePush,
            "privacy_url": "spush://****@E...E/alerts?",
        },
    ),
)


class EncryptedURLTester(AppriseURLTester):
    """A title whose ciphertext fits the server limit."""

    title_len = NotifySimplePush.title_maxlen


def decrypt(ciphertext, key):
    """Reverses NotifySimplePush._encrypt()."""
    from nacl.bindings import crypto_aead_xchacha20poly1305_ietf_decrypt

    blob = base64.b64decode(ciphertext)
    return crypto_aead_xchacha20poly1305_ietf_decrypt(
        blob[24:], None, blob[:24], key
    ).decode("utf-8")


def ok_response(**kwargs):
    response = mock.Mock()
    response.content = json.dumps(kwargs)
    response.status_code = requests.codes.ok
    return response


def test_plugin_simplepush_urls():
    """NotifySimplePush() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@pytest.mark.skipif(
    not NOTIFY_SIMPLEPUSH_ENCRYPTION, reason="PyNaCl not installed"
)
def test_plugin_simplepush_encrypted_urls():
    """NotifySimplePush() encrypted Apprise URLs."""

    # Run our encrypted tests
    EncryptedURLTester(tests=apprise_url_encrypted_tests).run_all()


def test_plugin_simplepush_schema_alias():
    """NotifySimplePush() simplepush:// is the same service as spush://."""

    alias = Apprise.instantiate("simplepush://token123/alerts")
    primary = Apprise.instantiate("spush://token123/alerts")
    assert isinstance(alias, NotifySimplePush)

    # Both forms identify the same connection and write the same URL
    assert alias.url_identifier == primary.url_identifier
    assert alias.url() == primary.url()
    assert alias.url().startswith("spush://")


def test_plugin_simplepush_edge_cases():
    """NotifySimplePush() Edge Cases."""

    # No token
    with pytest.raises(AppriseImproperlyConfigured):
        NotifySimplePush(token=None)

    with pytest.raises(AppriseImproperlyConfigured):
        NotifySimplePush(token="  ")

    # Empty member
    with pytest.raises(AppriseImproperlyConfigured):
        NotifySimplePush(token=SPI, targets=["@"])

    # Blank targets are ignored
    obj = NotifySimplePush(token="abc", targets=["  "], priority="")
    assert obj.topics == []
    assert obj.priority is None
    assert len(obj) == 1

    # Priority names follow the Simplepush levels
    for priority, level in (
        ("minimal", 1),
        ("min", 1),
        ("low", 2),
        ("default", 3),
        ("normal", 3),
        ("High", 4),
        ("critical", 5),
        ("emergency", 5),
        ("max", 5),
        (" 4 ", 4),
        (2, 2),
    ):
        obj = NotifySimplePush(token="abc", priority=priority)
        assert obj.priority == level


@mock.patch("requests.post")
def test_plugin_simplepush_payload(mock_post):
    """NotifySimplePush() request payloads."""

    mock_post.return_value = ok_response(notificationId="ntf_1")

    # Your own devices
    obj = Apprise.instantiate("spush://token123")
    assert obj.notify(title="Title", body="Body") is True
    assert mock_post.call_count == 1
    url = mock_post.call_args[0][0]
    assert url == "https://api.simplepu.sh/v1/tasks/json"
    headers = mock_post.call_args[1]["headers"]
    assert headers["API-Token"] == "token123"
    assert "Authorization" not in headers
    assert json.loads(mock_post.call_args[1]["data"]) == {
        "contentFormat": "markdown",
        "title": "Title",
        "content": "Body",
    }

    # One request per topic, with every option
    mock_post.reset_mock()
    obj = Apprise.instantiate(
        "spush://token123/alerts/deploys?priority=5&critical_volume=0.5"
        "&sptag=db&links=https://a.example%20https://b.example&shared=yes"
        "&topic_auth_token=abcd&format=text"
    )
    assert obj.notify(body="Body") is True
    assert mock_post.call_count == 2
    payloads = [json.loads(c[1]["data"]) for c in mock_post.call_args_list]
    assert payloads[0] == {
        "topic": "alerts",
        "shared": True,
        "topicAuthToken": "abcd",
        "priority": 5,
        "criticalVolume": 0.5,
        "content": "Body",
        "tag": "db",
        "links": ["https://a.example", "https://b.example"],
    }
    assert payloads[1]["topic"] == "deploys"

    # Organization members and topics, organization without encryption
    mock_post.reset_mock()
    with mock.patch("requests.get") as mock_get:
        mock_get.return_value = ok_response(scopes=["send"], enabled=False)
        obj = Apprise.instantiate(
            "spush://{}/site/@Alice%20B?format=text".format(SPI)
        )
        assert obj.notify(body="Body") is True
        assert obj.notify(body="Body") is True

        # The keys are fetched once, with the credential half only
        assert mock_get.call_count == 1
        assert mock_get.call_args[0][0] == (
            "https://api.simplepu.sh/v1/org/integration/keys"
        )
        assert mock_get.call_args[1]["headers"]["Authorization"] == (
            "Bearer spi_cred"
        )

    assert mock_post.call_count == 4
    headers = mock_post.call_args[1]["headers"]
    assert headers["Authorization"] == "Bearer spi_cred"
    assert "API-Token" not in headers
    payloads = [json.loads(c[1]["data"]) for c in mock_post.call_args_list]
    assert payloads[0] == {"topic": "site", "content": "Body"}
    assert payloads[1] == {"member": "Alice B", "content": "Body"}

    # Organization broadcast
    mock_post.reset_mock()
    with mock.patch("requests.get") as mock_get:
        mock_get.return_value = ok_response(scopes=["send"], enabled=False)
        obj = Apprise.instantiate(
            "spush://{}/?broadcast=yes&format=text".format(SPI)
        )
        assert obj.notify(body="Body") is True

    assert json.loads(mock_post.call_args[1]["data"]) == {
        "broadcast": True,
        "content": "Body",
    }

    # One failing target fails the notification but the rest still send
    mock_post.reset_mock()
    bad = mock.Mock()
    bad.content = b""
    bad.status_code = requests.codes.forbidden
    mock_post.side_effect = [bad, ok_response()]
    obj = Apprise.instantiate("spush://token123/alerts/deploys")
    assert obj.notify(body="Body") is False
    assert mock_post.call_count == 2


@pytest.mark.skipif(
    not NOTIFY_SIMPLEPUSH_ENCRYPTION, reason="PyNaCl not installed"
)
@mock.patch("requests.get")
@mock.patch("requests.post")
def test_plugin_simplepush_encryption(mock_post, mock_get):
    """NotifySimplePush() end-to-end encryption."""

    mock_post.return_value = ok_response(notificationId="ntf_1")
    mock_get.return_value = ok_response(passwordSalt="salt123")

    # Topic send: encrypted with the topic password, salted with the topic
    obj = Apprise.instantiate(
        "spush://secret@token123/alerts?sptag=db&links=https://a.example"
    )
    assert obj.notify(title="Title", body="Body") is True
    assert obj.notify(title="Title", body="Body") is True
    assert mock_get.call_count == 0

    key, fingerprint = obj._derive_key("alerts")
    payload = json.loads(mock_post.call_args[1]["data"])
    assert payload["topic"] == "alerts"
    assert payload["encryption"] == {
        "type": "personal",
        "keyFingerprint": fingerprint,
    }
    assert decrypt(payload["title"], key) == "Title"
    assert decrypt(payload["content"], key) == "Body"
    assert decrypt(payload["tag"], key) == "db"
    assert [decrypt(v, key) for v in payload["links"]] == ["https://a.example"]
    # The render hint stays readable
    assert payload["contentFormat"] == "markdown"

    # Reference vector: the key and fingerprint every Simplepush client
    # derives for the password "secret" and the topic "alerts"
    assert key == base64.b64decode(
        "9mI0HX1p1U2VckiSHX8jBmHx/6gqIXYEPctmfuN9ak4="
    )
    assert fingerprint == "CQaZgA2pRm0="

    # Send to your own devices: encrypted with the Personal Password, salted
    # with the account password salt (fetched once)
    mock_post.reset_mock()
    obj = Apprise.instantiate("spush://secret@token123")
    assert obj.notify(body="Body") is True
    assert obj.notify(body="Body") is True
    assert mock_get.call_count == 1
    assert mock_get.call_args[0][0] == "https://api.simplepu.sh/v1/user"
    assert mock_get.call_args[1]["headers"]["API-Token"] == "token123"

    key, fingerprint = obj._derive_key("salt123")
    payload = json.loads(mock_post.call_args[1]["data"])
    assert "topic" not in payload
    assert "title" not in payload
    assert payload["encryption"]["keyFingerprint"] == fingerprint
    assert decrypt(payload["content"], key) == "Body"

    # Multi-byte text within the character limits can exceed the server
    # limits once encrypted; nothing is sent
    mock_post.reset_mock()
    obj = Apprise.instantiate("spush://secret@token123/alerts")
    assert obj.notify(body="日" * 7000) is False
    assert obj.notify(title="日" * 300, body="Body") is False
    assert mock_post.call_count == 0

    # ASCII text of the same length fits
    assert obj.notify(title="a" * 300, body="a" * 7000) is True
    assert mock_post.call_count == 1

    # Unencrypted sends are not affected
    mock_post.reset_mock()
    obj = Apprise.instantiate("spush://token123/alerts")
    assert obj.notify(title="日" * 300, body="日" * 7000) is True
    assert mock_post.call_count == 1

    # The salt lookup fails
    mock_post.reset_mock()
    bad = mock.Mock()
    bad.content = json.dumps({"error": "authorization_error", "msg": "no"})
    bad.status_code = requests.codes.unauthorized
    mock_get.return_value = bad
    obj = Apprise.instantiate("spush://secret@token123")
    assert obj.notify(body="Body") is False
    assert mock_post.call_count == 0

    # The account has no salt
    mock_get.return_value = ok_response()
    obj = Apprise.instantiate("spush://secret@token123")
    assert obj.notify(body="Body") is False

    # An unparsable response
    bad = mock.Mock()
    bad.content = b"garbage"
    bad.status_code = requests.codes.ok
    mock_get.return_value = bad
    obj = Apprise.instantiate("spush://secret@token123")
    assert obj.notify(body="Body") is False

    # A connection error
    mock_get.side_effect = requests.RequestException("down")
    obj = Apprise.instantiate("spush://secret@token123")
    assert obj.notify(body="Body") is False
    assert mock_post.call_count == 0


@mock.patch("requests.post")
def test_plugin_simplepush_without_pynacl(mock_post):
    """NotifySimplePush() without PyNaCl installed."""

    mock_post.return_value = ok_response()

    with mock.patch.object(simplepush, "NOTIFY_SIMPLEPUSH_ENCRYPTION", False):
        # Plain sends still work
        obj = Apprise.instantiate("spush://token123/alerts")
        assert obj.notify(body="Body") is True

        # Encrypted sends need PyNaCl
        with pytest.raises(AppriseImproperlyConfigured):
            NotifySimplePush(token="token123", password="secret")

        # An organization with encryption turned on needs PyNaCl
        with mock.patch("requests.get") as mock_get:
            mock_get.return_value = ok_response(
                scopes=["send"],
                enabled=True,
                adminPubkeyB64=ADMIN_PUBKEY,
                wrappedKeys=[{"version": 1, "blob": WRAP}],
            )
            obj = Apprise.instantiate("spush://{}/site".format(SPI))
            assert obj.notify(body="Body") is False


def upload_mocks(mock_post, mock_put, attachment_ids):
    """Task create, then presign / complete per attachment."""
    task = ok_response(
        taskId="tsk_1",
        attachments=[{"id": i, "filename": "x"} for i in attachment_ids],
    )
    presign = ok_response(presignedPutUrl="https://s3.example/put")
    mock_post.side_effect = lambda url, **kw: (
        task
        if url.endswith("/tasks/json")
        else presign
        if url.endswith("/upload-url")
        else ok_response()
    )
    mock_put.return_value = ok_response()


@mock.patch("requests.put")
@mock.patch("requests.post")
def test_plugin_simplepush_attachments(mock_post, mock_put, tmpdir):
    """NotifySimplePush() attachments."""

    path = tmpdir.join("photo.jpg")
    path.write_binary(b"jpeg-bytes")
    attach = AppriseAttachment(str(path))

    upload_mocks(mock_post, mock_put, ["att_1"])
    obj = Apprise.instantiate("spush://token123/alerts")
    assert obj.notify(body="Body", attach=attach) is True

    payload = json.loads(mock_post.call_args_list[0][1]["data"])
    assert payload["files"] == [
        {
            "filename": "photo.jpg",
            "contentType": "image/jpeg",
            "size": 10,
            "checksumSha256": base64.b64encode(
                hashlib.sha256(b"jpeg-bytes").digest()
            ).decode("ascii"),
        }
    ]
    urls = [c[0][0] for c in mock_post.call_args_list]
    assert urls == [
        "https://api.simplepu.sh/v1/tasks/json",
        "https://api.simplepu.sh/v1/attachments/att_1/upload-url",
        "https://api.simplepu.sh/v1/attachments/att_1/complete",
    ]
    assert mock_put.call_args[0][0] == "https://s3.example/put"
    assert mock_put.call_args[1]["data"] == b"jpeg-bytes"

    # Without a body the content is the title
    mock_post.reset_mock()
    upload_mocks(mock_post, mock_put, ["att_1"])
    assert obj.notify(title="Title", body="", attach=attach) is True
    payload = json.loads(mock_post.call_args_list[0][1]["data"])
    assert payload["content"] == "Title"
    assert "title" not in payload
    assert "contentFormat" not in payload

    # Without a body and a title the content is the attachment names
    mock_post.reset_mock()
    upload_mocks(mock_post, mock_put, ["att_1"])
    assert obj.notify(attach=attach) is True
    payload = json.loads(mock_post.call_args_list[0][1]["data"])
    assert payload["content"] == "photo.jpg"
    assert "title" not in payload
    assert "contentFormat" not in payload

    # The upload fails; the server is told so
    mock_post.reset_mock()
    upload_mocks(mock_post, mock_put, ["att_3"])
    bad = mock.Mock()
    bad.content = b""
    bad.status_code = requests.codes.forbidden
    mock_put.return_value = bad
    obj = Apprise.instantiate("spush://token123/alerts")
    assert obj.notify(body="Body", attach=attach) is False
    assert mock_post.call_args[0][0] == (
        "https://api.simplepu.sh/v1/attachments/att_3/failed"
    )

    # Presigning fails, and so does reporting it
    mock_post.reset_mock()
    upload_mocks(mock_post, mock_put, ["att_4"])
    task = ok_response(taskId="tsk_1", attachments=[{"id": "att_4"}])
    mock_post.side_effect = [task, bad, requests.RequestException("down")]
    assert obj.notify(body="Body", attach=attach) is False

    # The server returned no attachment id
    mock_post.reset_mock()
    mock_post.side_effect = None
    mock_post.return_value = ok_response(attachments=[{}])
    assert obj.notify(body="Body", attach=attach) is False

    # An unparsable task response still counts as sent
    garbage = mock.Mock()
    garbage.content = b"garbage"
    garbage.status_code = requests.codes.ok
    mock_post.return_value = garbage
    assert obj.notify(body="Body") is True

    # An inaccessible attachment
    mock_post.reset_mock()
    assert (
        obj.notify(
            body="Body",
            attach=AppriseAttachment(str(tmpdir.join("missing.jpg"))),
        )
        is False
    )
    assert mock_post.call_count == 0

    # An unreadable attachment
    with mock.patch("builtins.open", side_effect=OSError()):
        assert obj.notify(body="Body", attach=attach) is False
    assert mock_post.call_count == 0


@pytest.mark.skipif(
    not NOTIFY_SIMPLEPUSH_ENCRYPTION, reason="PyNaCl not installed"
)
@mock.patch("requests.put")
@mock.patch("requests.post")
def test_plugin_simplepush_encrypted_attachments(mock_post, mock_put, tmpdir):
    """NotifySimplePush() seals uploaded attachments with the topic key."""

    path = tmpdir.join("photo.jpg")
    path.write_binary(b"jpeg-bytes")
    attach = AppriseAttachment(str(path))

    # Encrypted: the uploaded bytes are sealed with the topic key
    upload_mocks(mock_post, mock_put, ["att_2"])
    obj = Apprise.instantiate("spush://secret@token123/alerts")
    assert obj.notify(body="Body", attach=attach) is True
    key, _ = obj._derive_key("alerts")
    blob = mock_put.call_args[1]["data"]
    assert decrypt(base64.b64encode(blob), key) == "jpeg-bytes"
    payload = json.loads(mock_post.call_args_list[0][1]["data"])
    assert payload["files"][0]["size"] == len(blob)


@mock.patch("requests.post")
def test_plugin_simplepush_retry(mock_post):
    """NotifySimplePush() retries skip the topics that already have a task."""

    bad = mock.Mock()
    bad.content = b""
    bad.status_code = requests.codes.service_unavailable
    mock_post.side_effect = [ok_response(), bad, ok_response()]

    aobj = Apprise()
    assert aobj.add("spush://token123/alerts/deploys?retry=1&wait=0")
    assert bool(aobj.notify(body="Body")) is True

    topics = [
        json.loads(c[1]["data"])["topic"] for c in mock_post.call_args_list
    ]
    assert topics == ["alerts", "deploys", "deploys"]


@pytest.mark.skipif(
    not NOTIFY_SIMPLEPUSH_ENCRYPTION, reason="PyNaCl not installed"
)
@mock.patch("requests.get")
@mock.patch("requests.post")
def test_plugin_simplepush_organization_encryption(mock_post, mock_get):
    """NotifySimplePush() organization keys opened by the integration
    token."""

    mock_post.return_value = ok_response(taskId="tsk_1")
    mock_get.return_value = ok_response(
        scopes=["send", "read"],
        enabled=True,
        adminPubkeyB64=ADMIN_PUBKEY,
        wrappedKeys=[
            {"version": 1, "blob": WRAP},
            {"version": 3, "blob": WRAP},
            {"version": 2, "blob": WRAP},
        ],
    )

    obj = Apprise.instantiate(
        "spush://{}/@Alice?sptag=db&links=https://a.example".format(SPI)
    )
    assert obj.notify(title="Title", body="Body") is True

    payload = json.loads(mock_post.call_args[1]["data"])
    # Encrypted with the newest organization key
    assert payload["encryption"] == {"type": "org", "v": 3}
    assert payload["member"] == "Alice"
    assert decrypt(payload["title"], MASTER_KEY) == "Title"
    assert decrypt(payload["content"], MASTER_KEY) == "Body"
    assert decrypt(payload["tag"], MASTER_KEY) == "db"
    assert decrypt(payload["links"][0], MASTER_KEY) == "https://a.example"

    def fails(**response):
        mock_post.reset_mock()
        mock_get.return_value = ok_response(**response)
        obj = Apprise.instantiate("spush://{}/site".format(SPI))
        assert obj.notify(body="Body") is False
        assert mock_post.call_count == 0

    # The token lacks the send scope
    fails(scopes=["read"], enabled=False)

    # Encryption is on but nothing was wrapped for this token
    fails(scopes=["send"], enabled=True, adminPubkeyB64=ADMIN_PUBKEY)

    # A wrap made for someone else
    fails(
        scopes=["send"],
        enabled=True,
        adminPubkeyB64=base64.b64encode(b"x" * 32).decode(),
        wrappedKeys=[{"version": 1, "blob": WRAP}],
    )

    # A malformed response
    fails(scopes=["send"], enabled=True, wrappedKeys=[{"version": 1}])

    # Not a JSON object
    mock_post.reset_mock()
    mock_get.return_value = ok_response()
    mock_get.return_value.content = b"[]"
    obj = Apprise.instantiate("spush://{}/site".format(SPI))
    assert obj.notify(body="Body") is False
    assert mock_post.call_count == 0
