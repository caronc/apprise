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

from apprise import Apprise, AppriseAttachment, NotifyFormat
from apprise.attachment.memory import AttachMemory
from apprise.plugins.base import _delivery_memo, _delivery_tracker
from apprise.plugins.onebot import NotifyOneBot

logging.disable(logging.CRITICAL)

# Directory containing test attachments.
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), "var")

# URLs and expected results for the shared plugin tests.
apprise_url_tests = (
    (
        "onebot://",
        {
            # No hostname
            "instance": None,
        },
    ),
    (
        "onebot://localhost",
        {
            # No targets; loads but has nothing to notify
            "instance": NotifyOneBot,
            "notify_response": False,
        },
    ),
    (
        "onebot://localhost/abc",
        {
            # An invalid target only; loads but has nothing to notify
            "instance": NotifyOneBot,
            "notify_response": False,
            "privacy_url": "onebot://localhost/abc",
        },
    ),
    (
        "onebot://localhost/12345",
        {
            "instance": NotifyOneBot,
            "privacy_url": "onebot://localhost/@12345",
        },
    ),
    (
        "onebot://mytoken@localhost:3000/@12345/%2367890",
        {
            "instance": NotifyOneBot,
            "privacy_url": "onebot://m...n@localhost:3000/@12345/%2367890",
        },
    ),
    (
        "onebots://localhost:5700/?to=12345,%2367890&token=mytoken",
        {
            "instance": NotifyOneBot,
            "privacy_url": "onebots://m...n@localhost:5700/@12345/%2367890",
        },
    ),
    (
        "onebot://localhost/12345",
        {
            # A failed action still comes back as an HTTP 200
            "instance": NotifyOneBot,
            "requests_response_text": {
                "status": "failed",
                "retcode": 100,
                "wording": "bad",
            },
            "response": False,
        },
    ),
    (
        "onebot://localhost/12345",
        {
            # An async action is accepted
            "instance": NotifyOneBot,
            "requests_response_text": {"status": "async", "retcode": 1},
        },
    ),
    (
        "onebot://localhost/12345",
        {
            "instance": NotifyOneBot,
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "onebot://localhost/12345",
        {
            "instance": NotifyOneBot,
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "onebot://localhost/12345",
        {
            "instance": NotifyOneBot,
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_onebot_urls():
    """NotifyOneBot() Apprise URLs."""

    # Run the shared URL tests.
    AppriseURLTester(tests=apprise_url_tests).run_all()


def _mk_resp(d=None, code=requests.codes.ok):
    """Build a mocked OneBot response."""
    r = mock.Mock()
    r.status_code = code
    r.content = dumps(d if d is not None else {"status": "ok", "retcode": 0})
    return r


@mock.patch("requests.post")
def test_plugin_onebot_send(mock_post):
    """NotifyOneBot() text payloads for users and groups."""
    mock_post.return_value = _mk_resp()

    obj = Apprise.instantiate(
        "onebots://secret@bot.example:3000/@111/#222/bad"
    )
    assert isinstance(obj, NotifyOneBot)
    assert obj.users == ["111"]
    assert obj.groups == ["222"]
    assert obj.invalid_targets == ["bad"]
    assert len(obj) == 2
    assert obj.notify_format == NotifyFormat.TEXT

    assert obj.notify(title="A & <b>", body="x _ . ! * # <") is True
    assert mock_post.call_count == 2

    # The user is notified first
    url, kwargs = (
        mock_post.call_args_list[0][0][0],
        mock_post.call_args_list[0][1],
    )
    assert urlparse(url).hostname == "bot.example"
    assert urlparse(url).scheme == "https"
    assert urlparse(url).port == 3000
    assert urlparse(url).path == "/send_private_msg"
    assert kwargs["headers"]["Authorization"] == "Bearer secret"
    payload = loads(kwargs["data"])
    assert payload == {
        "user_id": 111,
        "message": [
            {"type": "text", "data": {"text": "A & <b>\r\nx _ . ! * # <"}}
        ],
    }

    # Then the group
    url, kwargs = (
        mock_post.call_args_list[1][0][0],
        mock_post.call_args_list[1][1],
    )
    assert urlparse(url).path == "/send_group_msg"
    payload = loads(kwargs["data"])
    assert payload["group_id"] == 222
    assert "user_id" not in payload

    # Without a token there is no Authorization header and no port
    mock_post.reset_mock()
    obj = Apprise.instantiate("onebot://bot.example/111")
    assert obj.notify(body="hello") is True
    url, kwargs = mock_post.call_args[0][0], mock_post.call_args[1]
    assert urlparse(url).scheme == "http"
    assert urlparse(url).port is None
    assert "Authorization" not in kwargs["headers"]

    # An unreadable body that came with an HTTP 200 is a success
    mock_post.reset_mock()
    mock_post.return_value.content = b"not json"
    assert obj.notify(body="hello") is True

    # A failure reported in the body is a failure
    mock_post.return_value = _mk_resp({"status": "failed", "retcode": 1404})
    assert obj.notify(body="hello") is False


def test_plugin_onebot_long_ids():
    """NotifyOneBot() rejects target IDs longer than 19 digits."""
    obj = NotifyOneBot(
        host="localhost", targets=["1" * 19, "#" + "2" * 19, "3" * 5000]
    )
    assert obj.users == ["1" * 19]
    assert obj.groups == ["2" * 19]
    assert obj.invalid_targets == ["3" * 5000]


@mock.patch("requests.post")
def test_plugin_onebot_url_round_trip(mock_post):
    """NotifyOneBot() url() survives a re-parse."""
    obj = NotifyOneBot(
        host="localhost",
        port=3000,
        token="abc/def",
        targets=["@1", "#2", "3", "bad"],
    )
    result = NotifyOneBot.parse_url(obj.url())
    obj2 = NotifyOneBot(**result)

    assert obj.url_identifier == obj2.url_identifier
    assert obj2.token == "abc/def"
    assert obj2.users == ["1", "3"]
    assert obj2.groups == ["2"]
    assert obj2.invalid_targets == ["bad"]

    # The token is part of the connection identity
    assert (
        NotifyOneBot(host="localhost", targets="1").url_identifier
        != obj.url_identifier
    )


@mock.patch("requests.post")
def test_plugin_onebot_attachments(mock_post):
    """NotifyOneBot() sends each attachment as its own message."""
    mock_post.return_value = _mk_resp()

    obj = Apprise.instantiate("onebot://localhost/@111")

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
    segments = [
        loads(c[1]["data"])["message"][0] for c in mock_post.call_args_list
    ]
    assert [s["type"] for s in segments] == [
        "text",
        "image",
        "video",
        "file",
        "record",
        "file",
    ]
    assert segments[1]["data"]["file"].startswith("base64://")
    assert "name" not in segments[1]["data"]
    assert segments[3]["data"]["name"] == "apprise-archive.zip"
    assert segments[5]["data"]["name"]

    # An attachment with no body sends no text
    mock_post.reset_mock()
    assert obj.notify(body="", attach=attach[0]) is True
    assert mock_post.call_count == 1
    assert loads(mock_post.call_args[1]["data"])["message"][0]["type"] == (
        "image"
    )

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
def test_plugin_onebot_retry_tracking(mock_post):
    """NotifyOneBot() retries resume where the last attempt stopped."""
    obj = Apprise.instantiate("onebot://localhost/@111")
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
        assert loads(mock_post.call_args[1]["data"])["message"][0]["data"][
            "file"
        ].startswith("base64://")

    finally:
        _delivery_memo.reset(memo)
        _delivery_tracker.reset(tracker)


@pytest.mark.parametrize(
    "code", [400, 401, 403, 404, 406, requests.codes.internal_server_error]
)
@mock.patch("requests.post")
def test_plugin_onebot_http_errors(mock_post, code):
    """NotifyOneBot() treats any non-200 reply as a failure."""
    mock_post.return_value = _mk_resp(code=code)
    obj = Apprise.instantiate("onebot://localhost/@111")
    assert obj.notify(body="hello") is False


@mock.patch("requests.post")
def test_plugin_onebot_attach_read_once(mock_post):
    """NotifyOneBot() reads each attachment once across all targets."""
    mock_post.return_value = _mk_resp()
    obj = Apprise.instantiate("onebot://localhost/@111/#222")
    attach = AppriseAttachment(
        [
            os.path.join(TEST_VAR_DIR, "apprise-test.gif"),
            os.path.join(TEST_VAR_DIR, "apprise-test.png"),
        ]
    )

    with mock.patch(
        "apprise.attachment.base.AttachBase.base64",
        autospec=True,
        return_value="abc",
    ) as mock_b64:
        assert obj.notify(body="hello", attach=attach) is True

    # Two reads serve both targets
    assert mock_b64.call_count == 2

    # Two texts, then each attachment to both targets
    assert mock_post.call_count == 6
    assert [
        loads(c[1]["data"])["message"][0]["type"]
        for c in mock_post.call_args_list
    ] == ["text", "text", "image", "image", "image", "image"]


@mock.patch("requests.post")
def test_plugin_onebot_attach_partial_failure(mock_post):
    """NotifyOneBot() keeps serving healthy targets when one fails."""

    def respond(url, data=None, **kwargs):
        # The group refuses every attachment, the user accepts everything
        payload = loads(data)
        if "group_id" in payload and payload["message"][0]["type"] != "text":
            return _mk_resp(code=500)
        return _mk_resp()

    mock_post.side_effect = respond
    obj = Apprise.instantiate("onebot://localhost/@111/#222")
    attach = AppriseAttachment(
        [
            os.path.join(TEST_VAR_DIR, "apprise-test.gif"),
            os.path.join(TEST_VAR_DIR, "apprise-test.png"),
        ]
    )

    assert obj.notify(body="hello", attach=attach) is False

    # Who received what, in the order it was sent
    sent = [
        (
            "group" if "group_id" in loads(c[1]["data"]) else "user",
            loads(c[1]["data"])["message"][0]["type"],
        )
        for c in mock_post.call_args_list
    ]

    # The user gets both attachments, the group stops after its first
    assert sent == [
        ("user", "text"),
        ("group", "text"),
        ("user", "image"),
        ("group", "image"),
        ("user", "image"),
    ]
