#
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
from json import dumps, loads
import logging
from unittest import mock

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise
from apprise.exception import AppriseImproperlyConfigured
from apprise.plugins.wpush import (
    WPUSH_CHANNEL_DEFAULT,
    NotifyWPush,
    WPushChannel,
)

logging.disable(logging.CRITICAL)

# WPUSH + exactly 27 more alphanumeric characters (32 total)
GOOD_KEY = "WPUSH" + ("a" * 27)

GOOD_RESPONSE = dumps(
    {"code": 0, "message": "success", "data": "1126950958891274240"}
)
BAD_RESPONSE = dumps({"code": 401, "message": "API Key error"})

apprise_url_tests = (
    (
        "wpush://",
        {"instance": AppriseImproperlyConfigured},
    ),
    (
        "wpush://short",
        {"instance": AppriseImproperlyConfigured},
    ),
    (
        "wpush://{}".format(GOOD_KEY),
        {
            "instance": NotifyWPush,
            "privacy_url": "wpush://****/",
            "requests_response_text": GOOD_RESPONSE,
        },
    ),
    (
        "wpush://?apikey={}".format(GOOD_KEY),
        {
            "instance": NotifyWPush,
            "privacy_url": "wpush://****/",
            "requests_response_text": GOOD_RESPONSE,
        },
    ),
    (
        "wpush://{}?channel=feishu".format(GOOD_KEY),
        {
            "instance": NotifyWPush,
            "requests_response_text": GOOD_RESPONSE,
        },
    ),
    (
        "wpush://{}?channel=feishu,dingtalk,qqbot".format(GOOD_KEY),
        {
            "instance": NotifyWPush,
            "requests_response_text": GOOD_RESPONSE,
        },
    ),
    (
        "wpush://{}/topic1/topic2".format(GOOD_KEY),
        {
            "instance": NotifyWPush,
            "requests_response_text": GOOD_RESPONSE,
        },
    ),
    (
        "wpush://{}?to=topic1,topic2".format(GOOD_KEY),
        {
            "instance": NotifyWPush,
            "requests_response_text": GOOD_RESPONSE,
        },
    ),
    (
        "wpush://{}?topic_code=mytopic".format(GOOD_KEY),
        {
            "instance": NotifyWPush,
            "requests_response_text": GOOD_RESPONSE,
        },
    ),
    (
        "wpush://{}?topic=mytopic".format(GOOD_KEY),
        {
            "instance": NotifyWPush,
            "requests_response_text": GOOD_RESPONSE,
        },
    ),
    (
        "wpush://{}?channel=qqbot&group=123456".format(GOOD_KEY),
        {
            "instance": NotifyWPush,
            "requests_response_text": GOOD_RESPONSE,
        },
    ),
    (
        "wpush://{}?channel=qqbot&option=123456".format(GOOD_KEY),
        {
            "instance": NotifyWPush,
            "requests_response_text": GOOD_RESPONSE,
        },
    ),
    (
        "wpush://{}?url=https://example.com/".format(GOOD_KEY),
        {
            "instance": NotifyWPush,
            "requests_response_text": GOOD_RESPONSE,
        },
    ),
    (
        "wpush://{}?channel=nope".format(GOOD_KEY),
        {"instance": AppriseImproperlyConfigured},
    ),
    (
        "wpush://{}?group=123456&topic_code=mytopic".format(GOOD_KEY),
        {"instance": AppriseImproperlyConfigured},
    ),
    (
        "https://api.wpush.cn/api/v1/send?apikey={}".format(GOOD_KEY),
        {
            "instance": NotifyWPush,
            "requests_response_text": GOOD_RESPONSE,
        },
    ),
    (
        "wpush://{}".format(GOOD_KEY),
        {
            "instance": NotifyWPush,
            "response": False,
            "requests_response_text": BAD_RESPONSE,
        },
    ),
    (
        "wpush://{}".format(GOOD_KEY),
        {
            "instance": NotifyWPush,
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "wpush://{}".format(GOOD_KEY),
        {
            "instance": NotifyWPush,
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_wpush_urls():
    """NotifyWPush() Apprise URL test suite."""
    AppriseURLTester(tests=apprise_url_tests).run_all()


def test_plugin_wpush_init():
    """NotifyWPush() object initialization."""
    obj = NotifyWPush(apikey=GOOD_KEY)
    assert obj.apikey == GOOD_KEY
    assert obj.channels == [WPUSH_CHANNEL_DEFAULT]
    assert obj.topics == []
    assert obj.group is None
    assert obj.click_url is None
    assert len(obj) == 1

    obj = NotifyWPush(apikey=GOOD_KEY, channel="mail")
    assert obj.channels == [WPushChannel.MAIL]

    # Channels are stored once in alphabetical order
    obj = NotifyWPush(apikey=GOOD_KEY, channel="feishu,dingtalk,qqbot")
    assert obj.channels == [
        WPushChannel.DINGTALK,
        WPushChannel.FEISHU,
        WPushChannel.QQBOT,
    ]

    obj = NotifyWPush(apikey=GOOD_KEY, targets=["topic1", "topic2"])
    assert obj.topics == ["topic1", "topic2"]
    assert len(obj) == 2

    obj = NotifyWPush(apikey=GOOD_KEY, channel="qqbot", group="123456")
    assert obj.group == "123456"

    # Channel matching ignores case and duplicates
    obj = NotifyWPush(apikey=GOOD_KEY, channel="Feishu,dingtalk,feishu")
    assert obj.channels == [WPushChannel.DINGTALK, WPushChannel.FEISHU]

    obj = NotifyWPush(apikey=GOOD_KEY, click_url="https://example.com/")
    assert obj.click_url == "https://example.com/"

    with pytest.raises(AppriseImproperlyConfigured):
        NotifyWPush(apikey=GOOD_KEY, channel="nope")

    with pytest.raises(AppriseImproperlyConfigured):
        NotifyWPush(apikey=GOOD_KEY, channel="feishu,nope")

    with pytest.raises(AppriseImproperlyConfigured):
        NotifyWPush(apikey="bad")

    with pytest.raises(AppriseImproperlyConfigured):
        # Group and topic targets cannot be combined
        NotifyWPush(apikey=GOOD_KEY, group="123456", targets=["topic1"])


def test_plugin_wpush_url_round_trip():
    """NotifyWPush() url() round trip through parse_url()."""
    obj = NotifyWPush(
        apikey=GOOD_KEY,
        channel="feishu,dingtalk",
        targets=["topic1", "topic2"],
        click_url="https://example.com/",
    )
    results = NotifyWPush.parse_url(obj.url())
    obj2 = NotifyWPush(**results)

    assert obj.url_identifier == obj2.url_identifier
    assert obj.topics == obj2.topics
    # Channels are stored once in alphabetical order
    assert obj2.channels == [WPushChannel.DINGTALK, WPushChannel.FEISHU]
    assert obj2.click_url == "https://example.com/"

    # Round trip a QQ Robot group without a topic
    obj3 = NotifyWPush(apikey=GOOD_KEY, channel="qqbot", group="123456")
    results3 = NotifyWPush.parse_url(obj3.url())
    obj4 = NotifyWPush(**results3)
    assert obj4.group == "123456"
    assert obj4.channels == [WPushChannel.QQBOT]


@mock.patch("requests.post")
def test_plugin_wpush_send_ok(mock_post):
    """Send once when no topic is set."""
    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = GOOD_RESPONSE.encode("utf-8")
    mock_post.return_value = response

    obj = NotifyWPush(apikey=GOOD_KEY)
    assert obj.send(body="hello", title="title") is True
    assert mock_post.call_count == 1
    assert mock_post.call_args[0][0] == "https://api.wpush.cn/api/v1/send"
    assert mock_post.call_args[1]["headers"]["X-API-Key"] == GOOD_KEY
    assert "X-Idempotency-Key" in mock_post.call_args[1]["headers"]
    payload = loads(mock_post.call_args[1]["data"])
    assert payload["apikey"] == GOOD_KEY
    assert payload["title"] == "title"
    assert payload["content"] == "hello"
    assert payload["channel"] == WPUSH_CHANNEL_DEFAULT
    assert "topic_code" not in payload
    assert "option" not in payload
    assert "url" not in payload

    mock_post.reset_mock()
    assert obj.send(body="only body") is True
    payload = loads(mock_post.call_args[1]["data"])
    assert payload["title"] == "only body"


@mock.patch("requests.post")
def test_plugin_wpush_send_multi_channel(mock_post):
    """Send to several channels in one request."""
    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = GOOD_RESPONSE.encode("utf-8")
    mock_post.return_value = response

    # The payload keeps the stored alphabetical order
    obj = NotifyWPush(apikey=GOOD_KEY, channel="feishu,dingtalk,qqbot")
    assert obj.send(body="msg", title="t") is True
    assert mock_post.call_count == 1
    payload = loads(mock_post.call_args[1]["data"])
    assert payload["channel"] == "dingtalk,feishu,qqbot"


@mock.patch("requests.post")
def test_plugin_wpush_send_topic_and_channel(mock_post):
    """Send to one topic through a selected channel."""
    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = GOOD_RESPONSE.encode("utf-8")
    mock_post.return_value = response

    obj = NotifyWPush(apikey=GOOD_KEY, channel="feishu", targets="abc123")
    assert obj.send(body="msg", title="t") is True
    payload = loads(mock_post.call_args[1]["data"])
    assert payload["channel"] == "feishu"
    assert payload["topic_code"] == "abc123"


@mock.patch("requests.post")
def test_plugin_wpush_send_qqbot_group(mock_post):
    """NotifyWPush() includes API option whenever group/option is set."""
    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = GOOD_RESPONSE.encode("utf-8")
    mock_post.return_value = response

    # Send the group code for QQ Robot
    obj = NotifyWPush(apikey=GOOD_KEY, channel="qqbot", group="123456")
    assert obj.send(body="msg") is True
    payload = loads(mock_post.call_args[1]["data"])
    assert payload["option"] == "123456"

    # Other supported channels use option to select a bound instance
    mock_post.reset_mock()
    obj = NotifyWPush(apikey=GOOD_KEY, channel="mail", group="123456")
    assert obj.send(body="msg") is True
    payload = loads(mock_post.call_args[1]["data"])
    assert payload["option"] == "123456"


@mock.patch("requests.post")
def test_plugin_wpush_send_click_url(mock_post):
    """Include an optional click-through URL."""
    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = GOOD_RESPONSE.encode("utf-8")
    mock_post.return_value = response

    obj = NotifyWPush(apikey=GOOD_KEY, click_url="https://example.com/")
    assert obj.send(body="msg") is True
    payload = loads(mock_post.call_args[1]["data"])
    assert payload["url"] == "https://example.com/"


@mock.patch("requests.post")
def test_plugin_wpush_send_multiple_topics(mock_post):
    """NotifyWPush() sends once per topic and reports partial failure."""
    ok_response = mock.Mock()
    ok_response.status_code = requests.codes.ok
    ok_response.content = GOOD_RESPONSE.encode("utf-8")

    bad_response = mock.Mock()
    bad_response.status_code = requests.codes.ok
    bad_response.content = BAD_RESPONSE.encode("utf-8")

    # Capture each key while the shared headers dictionary changes
    seen_keys = []
    responses = [ok_response, bad_response]

    def _side_effect(*args, **kwargs):
        seen_keys.append(kwargs["headers"]["X-Idempotency-Key"])
        return responses[len(seen_keys) - 1]

    mock_post.side_effect = _side_effect

    obj = NotifyWPush(apikey=GOOD_KEY, targets=["topic1", "topic2"])
    assert obj.send(body="msg") is False
    assert mock_post.call_count == 2

    # Each request must use a different key
    assert seen_keys[0] != seen_keys[1]


@mock.patch("requests.post")
def test_plugin_wpush_send_api_error(mock_post):
    """Handle a WPUSH error returned with HTTP 200."""
    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = BAD_RESPONSE.encode("utf-8")
    mock_post.return_value = response
    obj = NotifyWPush(apikey=GOOD_KEY)
    assert obj.send(body="msg") is False


@mock.patch("requests.post")
def test_plugin_wpush_bad_json(mock_post):
    """Handle a response that is not JSON."""
    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = b"not-json"
    mock_post.return_value = response

    obj = NotifyWPush(apikey=GOOD_KEY)
    assert obj.send(body="msg") is False


@mock.patch("requests.post")
def test_plugin_wpush_apprise_integration(mock_post):
    """Send through Apprise."""
    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = GOOD_RESPONSE.encode("utf-8")
    mock_post.return_value = response

    aobj = Apprise()
    assert aobj.add("wpush://{}".format(GOOD_KEY))
    assert bool(aobj.notify(title="T", body="B")) is True
    assert mock_post.call_count == 1


def test_plugin_wpush_instance_options():
    """Send instance codes through the option field."""
    from json import loads

    for channel in ("feishu", "dingtalk", "webhook", "wechat_work"):
        obj = Apprise.instantiate(
            "wpush://{}?channel={}&option=ops".format(GOOD_KEY, channel)
        )
        assert isinstance(obj, NotifyWPush)
        assert obj.group == "ops"

        with mock.patch("requests.post") as mock_post:
            mock_post.return_value = mock.Mock(
                status_code=200,
                content=GOOD_RESPONSE.encode("utf-8"),
            )
            assert obj.notify(title="t", body="b") is True
            assert mock_post.called
            payload = loads(mock_post.call_args[1]["data"].decode("utf-8"))
            assert payload.get("option") == "ops"
            assert payload.get("channel") == channel


def test_plugin_wpush_parse_native_url():
    """Parse supported and invalid native URLs."""

    # Parse the API Key
    result = NotifyWPush.parse_native_url(
        "https://api.wpush.cn/api/v1/send?apikey={}".format(GOOD_KEY)
    )
    assert result is not None
    obj = NotifyWPush(**result)
    assert obj.apikey == GOOD_KEY

    # Preserve the channel parameter
    result = NotifyWPush.parse_native_url(
        "https://api.wpush.cn/api/v1/send?apikey={}&channel=mail".format(
            GOOD_KEY
        )
    )
    assert result is not None
    obj = NotifyWPush(**result)
    assert obj.channels == [WPushChannel.MAIL]

    # Reject a URL without an API Key
    assert (
        NotifyWPush.parse_native_url(
            "https://api.wpush.cn/api/v1/send?channel=mail"
        )
        is None
    )

    # Reject other domains
    assert (
        NotifyWPush.parse_native_url(
            "https://other.example.com/api/v1/send?apikey={}".format(GOOD_KEY)
        )
        is None
    )

    # Reject a URL without query parameters
    assert (
        NotifyWPush.parse_native_url("https://api.wpush.cn/api/v1/send")
        is None
    )


def test_plugin_wpush_rejects_boolean_code():
    """Reject Boolean codes even though False equals zero in Python."""
    obj = Apprise.instantiate("wpush://{}".format(GOOD_KEY))
    with mock.patch("requests.post") as mock_post:
        mock_post.return_value = mock.Mock(
            status_code=200,
            content=dumps({"code": False, "message": "nope"}).encode("utf-8"),
        )
        assert obj.notify(title="t", body="b") is False
