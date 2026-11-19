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

from json import dumps, loads
import logging
import os
from unittest import mock
from urllib.parse import urlparse

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise, AppriseAttachment
from apprise.attachment.memory import AttachMemory
from apprise.exception import AppriseImproperlyConfigured
from apprise.plugins.base import _delivery_memo, _delivery_tracker
from apprise.plugins.messenger import NotifyMessenger

logging.disable(logging.CRITICAL)

# Attachment Directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), "var")

# A Facebook Page access token
TOKEN = "EAA" + "b" * 40

# Our Testing URLs
apprise_url_tests = (
    (
        "messenger://",
        {
            # No access token
            "instance": TypeError,
        },
    ),
    (
        "messenger://%25invalid%25/12345",
        {
            # An access token with characters that are not allowed
            "instance": TypeError,
        },
    ),
    (
        f"messenger://{TOKEN}",
        {
            # No targets; loads but has nothing to notify
            "instance": NotifyMessenger,
            "notify_response": False,
        },
    ),
    (
        f"messenger://{TOKEN}/abc",
        {
            # An invalid target only; loads but has nothing to notify
            "instance": NotifyMessenger,
            "notify_response": False,
            "privacy_url": "messenger://E...b/abc/",
        },
    ),
    (
        f"messenger://{TOKEN}/12345/67890",
        {
            "instance": NotifyMessenger,
            "privacy_url": "messenger://E...b/12345/67890/",
        },
    ),
    (
        f"messenger://?token={TOKEN}&to=12345,67890",
        {
            "instance": NotifyMessenger,
            "privacy_url": "messenger://E...b/12345/67890/",
        },
    ),
    (
        f"messenger://12345/?token={TOKEN}",
        {
            # With ?token= the hostname is treated as a target
            "instance": NotifyMessenger,
            "privacy_url": "messenger://E...b/12345/",
        },
    ),
    (
        f"messenger://{TOKEN}/12345?template=alert",
        {
            # A Utility template with the default language
            "instance": NotifyMessenger,
            "privacy_url": "messenger://E...b/12345/?template=alert&lang=en",
        },
    ),
    (
        f"messenger://{TOKEN}/12345?template=alert&lang=fr&language=en_US",
        {
            # ?language= wins over ?lang=
            "instance": NotifyMessenger,
            "privacy_url": (
                "messenger://E...b/12345/?template=alert&lang=en_US"
            ),
        },
    ),
    (
        f"messenger://{TOKEN}/12345?template=a%20b",
        {
            # A template name with a space
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        f"messenger://{TOKEN}/12345?template=alert&lang=123",
        {
            # A language code made of digits
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        f"messenger://{TOKEN}/12345",
        {
            "instance": NotifyMessenger,
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        f"messenger://{TOKEN}/12345",
        {
            "instance": NotifyMessenger,
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        f"messenger://{TOKEN}/12345",
        {
            "instance": NotifyMessenger,
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_messenger_urls():
    """NotifyMessenger() Apprise URLs."""

    # Run the shared URL tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


def _mk_resp(d=None, code=requests.codes.ok):
    """Build a mocked Messenger response."""
    r = mock.Mock()
    r.status_code = code
    r.content = dumps(
        d if d is not None else {"recipient_id": "1", "message_id": "m"}
    ).encode()
    return r


def test_plugin_messenger_bad_token():
    """NotifyMessenger() rejects a missing access token."""
    with pytest.raises(AppriseImproperlyConfigured):
        NotifyMessenger(token=None, targets="12345")


@mock.patch("requests.post")
def test_plugin_messenger_send(mock_post):
    """NotifyMessenger() text payload and endpoint."""
    mock_post.return_value = _mk_resp()

    obj = Apprise.instantiate(f"messenger://{TOKEN}/12345/bad/67890")
    assert len(obj) == 2

    # The title is merged into the body, which is sent untouched
    assert obj.notify(title="A & <b>", body="_x_ . ! * # <") is True
    assert mock_post.call_count == 2

    url = mock_post.call_args_list[0][0][0]
    assert urlparse(url).hostname == "graph.facebook.com"
    assert urlparse(url).path == "/v26.0/me/messages"

    kwargs = mock_post.call_args_list[0][1]
    assert kwargs["headers"]["Authorization"] == f"Bearer {TOKEN}"
    assert kwargs["headers"]["Content-Type"] == "application/json"
    assert kwargs["files"] is None
    assert loads(kwargs["data"]) == {
        "recipient": {"id": "12345"},
        "messaging_type": "UPDATE",
        "message": {"text": "A & <b>\r\n_x_ . ! * # <"},
    }
    assert loads(mock_post.call_args_list[1][1]["data"])["recipient"] == {
        "id": "67890"
    }


@mock.patch("requests.post")
def test_plugin_messenger_template(mock_post):
    """NotifyMessenger() sends the body as a Utility template parameter."""
    mock_post.return_value = _mk_resp()

    obj = Apprise.instantiate(
        f"messenger://{TOKEN}/12345?template=alert&lang=en_US"
    )
    assert obj.notify(title="Title", body="Server is down") is True
    assert loads(mock_post.call_args[1]["data"]) == {
        "recipient": {"id": "12345"},
        "messaging_type": "UTILITY",
        "message": {
            "template": {
                "name": "alert",
                "language": {"code": "en_US"},
                "components": [
                    {
                        "type": "body",
                        "parameters": [
                            {
                                "type": "text",
                                "text": "Title\r\nServer is down",
                            }
                        ],
                    }
                ],
            }
        },
    }


@mock.patch("requests.post")
def test_plugin_messenger_url_round_trip(mock_post):
    """NotifyMessenger() URLs survive a round trip."""
    obj1 = Apprise.instantiate(
        f"messenger://{TOKEN}/12345/abc/67890?template=alert&lang=fr"
    )
    obj2 = Apprise.instantiate(obj1.url())

    assert obj1.url_identifier == obj2.url_identifier
    assert obj1.url_identifier == ("messenger", TOKEN)
    assert obj2.targets == ["12345", "67890"]
    assert obj2.invalid_targets == ["abc"]
    assert obj2.template == "alert"
    assert obj2.language == "fr"


@mock.patch("requests.post")
def test_plugin_messenger_errors(mock_post):
    """NotifyMessenger() reports Meta error details."""
    obj = Apprise.instantiate(f"messenger://{TOKEN}/12345")

    # Meta's error object is used when present
    mock_post.return_value = _mk_resp(
        {"error": {"message": "outside of allowed window", "code": 10}},
        code=400,
    )
    assert obj.notify(body="hello") is False

    # An error object without a message keeps the HTTP description
    mock_post.return_value = _mk_resp({"error": {}}, code=400)
    assert obj.notify(body="hello") is False

    # A body that is not JSON keeps the HTTP description
    response = _mk_resp(code=400)
    response.content = b"not json"
    mock_post.return_value = response
    assert obj.notify(body="hello") is False

    # An empty body keeps the HTTP description
    response.content = None
    assert obj.notify(body="hello") is False


@mock.patch("requests.post")
def test_plugin_messenger_attachments(mock_post):
    """NotifyMessenger() uploads each attachment as its own message."""
    mock_post.return_value = _mk_resp()

    obj = Apprise.instantiate(f"messenger://{TOKEN}/12345")

    attach = AppriseAttachment(
        [
            os.path.join(TEST_VAR_DIR, "apprise-test.gif"),
            os.path.join(TEST_VAR_DIR, "apprise-test.mp4"),
            os.path.join(TEST_VAR_DIR, "apprise-archive.zip"),
        ]
    )
    attach.add(AttachMemory(content=b"abc", mimetype="audio/mpeg"))
    attach.add(
        AttachMemory(content=b"abc", name="", mimetype="application/pdf")
    )

    assert obj.notify(body="hello", attach=attach) is True

    # One text message, then one message per attachment
    assert mock_post.call_count == 6
    calls = mock_post.call_args_list[1:]
    assert [
        loads(c[1]["data"]["message"])["attachment"]["type"] for c in calls
    ] == ["image", "video", "file", "audio", "file"]

    # Files are sent as form data with no JSON Content-Type
    kwargs = calls[0][1]
    assert "Content-Type" not in kwargs["headers"]
    assert loads(kwargs["data"]["recipient"]) == {"id": "12345"}
    assert kwargs["data"]["messaging_type"] == "UPDATE"
    assert kwargs["files"]["filedata"][0] == "apprise-test.gif"
    assert kwargs["files"]["filedata"][2] == "image/gif"
    assert calls[2][1]["files"]["filedata"][0] == "apprise-archive.zip"
    assert calls[4][1]["files"]["filedata"][0]

    # An attachment with no body sends no text
    mock_post.reset_mock()
    assert obj.notify(body="", attach=attach[0]) is True
    assert mock_post.call_count == 1
    assert mock_post.call_args[1]["files"]

    # An inaccessible attachment fails before anything is sent
    mock_post.reset_mock()
    with mock.patch("os.path.isfile", return_value=False):
        assert obj.notify(body="hello", attach=attach[0]) is False
    assert mock_post.call_count == 0

    # An attachment that cannot be read fails after the text is sent
    with mock.patch("builtins.open", side_effect=OSError):
        assert obj.notify(body="hello", attach=attach[0]) is False
    assert mock_post.call_count == 1
    mock_post.reset_mock()

    # A failed attachment stops the rest for that target
    mock_post.side_effect = [_mk_resp(), _mk_resp(code=500)]
    assert obj.notify(body="hello", attach=attach) is False
    assert mock_post.call_count == 2

    # A failed text message skips that target's attachments
    mock_post.reset_mock()
    mock_post.side_effect = requests.RequestException("boom")
    assert obj.notify(body="hello", attach=attach) is False
    assert mock_post.call_count == 1


@mock.patch("requests.post")
def test_plugin_messenger_retry_tracking(mock_post):
    """NotifyMessenger() retries resume where the last attempt stopped."""
    obj = Apprise.instantiate(f"messenger://{TOKEN}/12345")
    attach = AppriseAttachment(
        [
            os.path.join(TEST_VAR_DIR, "apprise-test.gif"),
            os.path.join(TEST_VAR_DIR, "apprise-test.png"),
        ]
    )

    tracker = _delivery_tracker.set(set())
    memo = _delivery_memo.set({})
    try:
        # The text and first attachment arrive, the second fails
        mock_post.side_effect = [_mk_resp(), _mk_resp(), _mk_resp(code=500)]
        assert obj.send(body="hello", attach=attach) is False
        assert mock_post.call_count == 3

        # The retry only sends the attachment that failed
        mock_post.reset_mock()
        mock_post.side_effect = None
        mock_post.return_value = _mk_resp()
        assert obj.send(body="hello", attach=attach) is True
        assert mock_post.call_count == 1
        assert mock_post.call_args[1]["files"]["filedata"][0] == (
            "apprise-test.png"
        )

    finally:
        _delivery_memo.reset(memo)
        _delivery_tracker.reset(tracker)
