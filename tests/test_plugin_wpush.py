#
# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2026, Chris Caron <lead2gold@gmail.com>
#

from json import dumps, loads
import logging
from unittest import mock

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise
from apprise.plugins.wpush import (
    WPUSH_CHANNEL_DEFAULT,
    WPUSH_CHANNELS,
    NotifyWPush,
    WPushChannel,
)

logging.disable(logging.CRITICAL)

# WPUSH + 32 alphanumeric characters
GOOD_KEY = "WPUSH" + ("a" * 32)

GOOD_RESPONSE = dumps(
    {"code": 0, "message": "success", "data": "1126950958891274240"}
)
BAD_RESPONSE = dumps({"code": 401, "message": "API Key error"})

apprise_url_tests = (
    (
        "wpush://",
        {"instance": TypeError},
    ),
    (
        "wpush://short",
        {"instance": TypeError},
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
        "wpush://{}?topic_code=mytopic".format(GOOD_KEY),
        {
            "instance": NotifyWPush,
            "requests_response_text": GOOD_RESPONSE,
        },
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
    obj = NotifyWPush(apikey=GOOD_KEY)
    assert obj.apikey == GOOD_KEY
    assert obj.channel == WPUSH_CHANNEL_DEFAULT
    assert obj.topic_code is None

    obj = NotifyWPush(apikey=GOOD_KEY, channel="mail")
    assert obj.channel == WPushChannel.MAIL

    with pytest.raises(TypeError):
        NotifyWPush(apikey=GOOD_KEY, channel="nope")

    with pytest.raises(TypeError):
        NotifyWPush(apikey="bad")


@mock.patch("requests.post")
def test_plugin_wpush_send_ok(mock_post):
    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = GOOD_RESPONSE.encode("utf-8")
    mock_post.return_value = response

    obj = NotifyWPush(apikey=GOOD_KEY)
    assert obj.send(body="hello", title="title") is True
    assert mock_post.call_count == 1
    assert mock_post.call_args[0][0] == "https://api.wpush.cn/api/v1/send"
    payload = loads(mock_post.call_args[1]["data"])
    assert payload["apikey"] == GOOD_KEY
    assert payload["title"] == "title"
    assert payload["content"] == "hello"
    assert payload["channel"] == WPUSH_CHANNEL_DEFAULT
    assert "topic_code" not in payload

    mock_post.reset_mock()
    assert obj.send(body="only body") is True
    payload = loads(mock_post.call_args[1]["data"])
    assert payload["title"] == "only body"


@mock.patch("requests.post")
def test_plugin_wpush_send_topic_and_channel(mock_post):
    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = GOOD_RESPONSE.encode("utf-8")
    mock_post.return_value = response

    obj = NotifyWPush(
        apikey=GOOD_KEY, channel="feishu", topic_code="abc123"
    )
    assert obj.send(body="msg", title="t") is True
    payload = loads(mock_post.call_args[1]["data"])
    assert payload["channel"] == "feishu"
    assert payload["topic_code"] == "abc123"


@mock.patch("requests.post")
def test_plugin_wpush_send_api_error(mock_post):
    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = BAD_RESPONSE.encode("utf-8")
    mock_post.return_value = response
    obj = NotifyWPush(apikey=GOOD_KEY)
    assert obj.send(body="msg") is False


@mock.patch("requests.post")
def test_plugin_wpush_apprise_integration(mock_post):
    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = GOOD_RESPONSE.encode("utf-8")
    mock_post.return_value = response

    aobj = Apprise()
    assert aobj.add("wpush://{}".format(GOOD_KEY))
    assert aobj.notify(title="T", body="B") is True
    assert mock_post.call_count == 1
