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
from unittest import mock
from urllib.parse import urlparse

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise
from apprise.exception import AppriseImproperlyConfigured
from apprise.plugins.base import _delivery_memo, _delivery_tracker
from apprise.plugins.gorush import NotifyGorush

logging.disable(logging.CRITICAL)

# A successful Gorush reply
GORUSH_OK = dumps({"counts": 1, "logs": [], "success": "ok"})

# URLs and expected results for the shared plugin tests.
apprise_url_tests = (
    (
        "gorush://",
        {
            # No hostname
            "instance": None,
        },
    ),
    (
        "gorush://localhost",
        {
            # No device tokens; loads but has nothing to notify
            "instance": NotifyGorush,
            "notify_response": False,
        },
    ),
    (
        "gorush://localhost:8088/abcdef1234567890",
        {
            "instance": NotifyGorush,
            "requests_response_text": GORUSH_OK,
            "privacy_url": "gorush://localhost:8088/a...0",
        },
    ),
    (
        "gorushs://user:pass@localhost/token1/token2?platform=ios",
        {
            "instance": NotifyGorush,
            "requests_response_text": GORUSH_OK,
            "privacy_url": "gorushs://user:****@localhost/t...1/t...2",
        },
    ),
    (
        "gorush://user@localhost/?to=token1,token2&mode=huawei",
        {
            "instance": NotifyGorush,
            "requests_response_text": GORUSH_OK,
        },
    ),
    (
        "gorush://localhost/token?platform=invalid",
        {
            # An unknown platform
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "gorush://localhost/token?priority=invalid",
        {
            # An unknown priority
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "gorush://localhost/token?badge=abc",
        {
            # A badge that is not a number
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "gorush://localhost/token?badge=-1",
        {
            # A negative badge
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "gorush://localhost/token?priority=high&topic=com.example.app"
        "&sound=default&badge=3&+key=value",
        {
            "instance": NotifyGorush,
            "requests_response_text": GORUSH_OK,
        },
    ),
    (
        "gorush://localhost/token",
        {
            # An empty reply is still a success
            "instance": NotifyGorush,
            "requests_response_text": "",
        },
    ),
    (
        "gorush://localhost/token",
        {
            "instance": NotifyGorush,
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "gorush://localhost/token",
        {
            "instance": NotifyGorush,
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "gorush://localhost/token",
        {
            "instance": NotifyGorush,
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_gorush_urls():
    """NotifyGorush() Apprise URLs."""
    AppriseURLTester(tests=apprise_url_tests).run_all()


def _mk_resp(content=GORUSH_OK, code=requests.codes.ok):
    """Build a mocked Gorush response."""
    r = mock.Mock()
    r.status_code = code
    r.content = (
        content.encode("utf-8") if isinstance(content, str) else (content)
    )
    return r


@mock.patch("requests.post")
def test_plugin_gorush_payload(mock_post):
    """NotifyGorush() sends every option Gorush understands."""
    mock_post.return_value = _mk_resp()

    obj = Apprise.instantiate(
        "gorushs://user:pass@push.example.com:8443/tok1/tok2"
        "?platform=apns&priority=h&topic=com.example.app&sound=ping"
        "&badge=0&+key=value"
    )
    assert isinstance(obj, NotifyGorush)
    assert len(obj) == 1

    assert obj.notify(title="Title & <b>", body="body _ . ! * # <") is True
    assert mock_post.call_count == 1

    # Check where the request went and how it authenticated
    url = mock_post.call_args[0][0]
    assert urlparse(url).hostname == "push.example.com"
    assert urlparse(url).port == 8443
    assert urlparse(url).scheme == "https"
    assert urlparse(url).path == "/api/push"
    assert mock_post.call_args[1]["auth"] == ("user", "pass")

    # The text arrives untouched
    payload = loads(mock_post.call_args[1]["data"])
    assert payload == {
        "notifications": [
            {
                "tokens": ["tok1", "tok2"],
                "platform": 1,
                "title": "Title & <b>",
                "message": "body _ . ! * # <",
                "priority": "high",
                "topic": "com.example.app",
                "sound": "ping",
                "badge": 0,
                "data": {"key": "value"},
            }
        ]
    }

    # Every option survives a round trip
    obj2 = Apprise.instantiate(obj.url())
    assert obj2.url_identifier == obj.url_identifier
    assert obj2.targets == obj.targets
    assert obj2.platform == "ios"
    assert obj2.priority == "high"
    assert obj2.topic == "com.example.app"
    assert obj2.sound == "ping"
    assert obj2.badge == 0
    assert obj2.data_kwargs == {"key": "value"}


@mock.patch("requests.post")
def test_plugin_gorush_defaults(mock_post):
    """NotifyGorush() sends only what is needed by default."""
    mock_post.return_value = _mk_resp()

    obj = Apprise.instantiate("gorush://localhost/token")
    assert obj.platform == "android"
    assert obj.notify(body="body") is True

    # No title, no auth and no optional fields
    assert mock_post.call_args[1]["auth"] is None
    assert urlparse(mock_post.call_args[0][0]).scheme == "http"
    payload = loads(mock_post.call_args[1]["data"])
    assert payload == {
        "notifications": [
            {"tokens": ["token"], "platform": 2, "message": "body"}
        ]
    }

    # The platform= value wins over mode=
    obj = Apprise.instantiate("gorush://localhost/token?mode=ios&platform=3")
    assert obj.platform == "huawei"

    # Port, user and password stay out of the URL when unset
    assert obj.url().startswith("gorush://localhost/token?")
    obj = Apprise.instantiate("gorush://user@localhost/token")
    assert obj.url().startswith("gorush://user@localhost/token?")

    # Data entries are optional when building the object directly
    obj = NotifyGorush(host="localhost", targets="token")
    assert obj.data_kwargs == {}


@pytest.mark.parametrize(
    "content",
    [
        # Not a dict
        dumps(["unexpected"]),
        # logs is not a list
        dumps({"logs": "unexpected"}),
        # Entries that are not failures
        dumps({"logs": ["text", {"type": "succeeded-push"}]}),
        # Not JSON at all
        "<html/>",
    ],
)
@mock.patch("requests.post")
def test_plugin_gorush_odd_replies(mock_post, content):
    """NotifyGorush() treats an HTTP 200 without failures as success."""
    mock_post.return_value = _mk_resp(content)
    obj = Apprise.instantiate("gorush://localhost/token")
    assert obj.notify(body="body") is True


@mock.patch("requests.post")
def test_plugin_gorush_failed_devices(mock_post):
    """NotifyGorush() retries only the devices Gorush could not reach."""
    obj = Apprise.instantiate("gorush://localhost/tok1/tok2/tok3")

    tracker = _delivery_tracker.set(set())
    memo = _delivery_memo.set({})
    try:
        # tok2 fails; the others arrive
        mock_post.return_value = _mk_resp(
            dumps(
                {
                    "counts": 3,
                    "logs": [
                        {
                            "type": "failed-push",
                            "token": "tok2",
                            "error": "invalid token",
                        }
                    ],
                    "success": "ok",
                }
            )
        )
        assert obj.send(body="body") is False

        # The retry only contacts the device that failed
        mock_post.return_value = _mk_resp()
        assert obj.send(body="body") is True
        payload = loads(mock_post.call_args[1]["data"])
        assert payload["notifications"][0]["tokens"] == ["tok2"]

    finally:
        _delivery_memo.reset(memo)
        _delivery_tracker.reset(tracker)


@mock.patch("requests.post")
def test_plugin_gorush_hidden_tokens(mock_post):
    """NotifyGorush() retries every device when tokens are masked."""
    obj = Apprise.instantiate("gorush://localhost/tok1/tok2")

    tracker = _delivery_tracker.set(set())
    memo = _delivery_memo.set({})
    try:
        # Gorush's hide_token option masks the token in its reply
        mock_post.return_value = _mk_resp(
            dumps({"logs": [{"type": "failed-push", "token": "****"}]})
        )
        assert obj.send(body="body") is False

        # No device can be skipped safely
        mock_post.return_value = _mk_resp()
        assert obj.send(body="body") is True
        payload = loads(mock_post.call_args[1]["data"])
        assert payload["notifications"][0]["tokens"] == ["tok1", "tok2"]

    finally:
        _delivery_memo.reset(memo)
        _delivery_tracker.reset(tracker)
