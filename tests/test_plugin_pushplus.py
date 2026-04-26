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
import requests

from apprise import Apprise
from apprise.common import NotifyFormat
from apprise.plugins.pushplus import (
    PUSHPLUS_CHANNEL_DEFAULT,
    PUSHPLUS_CHANNELS,
    PUSHPLUS_FORMAT_MAP,
    NotifyPushplus,
    PushPlusChannel,
)

logging.disable(logging.CRITICAL)

# A 32-character token used throughout the tests (minimum valid length)
GOOD_TOKEN = "abc123def456ghi789jkl012mno345pq"

# A 64-character token (upper boundary of the allowed length range)
LONG_TOKEN = "a" * 64

# PushPlus always returns HTTP 200; success/failure lives in the JSON body
GOOD_RESPONSE = dumps({"code": 200, "msg": "ok", "data": "msgid"})
BAD_RESPONSE = dumps({"code": 907, "msg": "Token does not exist."})

# Our Testing URLs
apprise_url_tests = (
    # ----------------------------------------------------------------
    # Invalid / missing token cases
    # ----------------------------------------------------------------
    (
        "pushplus://",
        {
            # Empty token must raise
            "instance": TypeError,
        },
    ),
    (
        "pushplus://short",
        {
            # Token too short (fewer than 32 characters)
            "instance": TypeError,
        },
    ),
    (
        "pushplus://invalid!chars00000000000000000000000000000",
        {
            # Token contains characters not allowed by the regex
            "instance": TypeError,
        },
    ),
    # ----------------------------------------------------------------
    # Valid token -- basic personal notification (no targets)
    # ----------------------------------------------------------------
    (
        "pushplus://{}".format(GOOD_TOKEN),
        {
            "instance": NotifyPushplus,
            # Privacy URL must mask the token
            "privacy_url": "pushplus://****/",
            "requests_response_text": GOOD_RESPONSE,
        },
    ),
    # Token supplied as a query parameter instead of the URL host
    (
        "pushplus://?token={}".format(GOOD_TOKEN),
        {
            "instance": NotifyPushplus,
            "privacy_url": "pushplus://****/",
            "requests_response_text": GOOD_RESPONSE,
        },
    ),
    # 64-character (maximum-length) token
    (
        "pushplus://{}".format(LONG_TOKEN),
        {
            "instance": NotifyPushplus,
            "requests_response_text": GOOD_RESPONSE,
        },
    ),
    # ----------------------------------------------------------------
    # Group topic variations
    # ----------------------------------------------------------------
    # Single topic in the URL path (no prefix required)
    (
        "pushplus://{}/mygroup".format(GOOD_TOKEN),
        {
            "instance": NotifyPushplus,
            "privacy_url": "pushplus://****/mygroup/",
            "requests_response_text": GOOD_RESPONSE,
        },
    ),
    # Two topics in the path -- two API calls are made
    (
        "pushplus://{}/group1/group2".format(GOOD_TOKEN),
        {
            "instance": NotifyPushplus,
            "requests_response_text": GOOD_RESPONSE,
        },
    ),
    # Topic supplied via the backward-compatible ?topic= parameter
    (
        "pushplus://{}/?topic=mygroup".format(GOOD_TOKEN),
        {
            "instance": NotifyPushplus,
            "requests_response_text": GOOD_RESPONSE,
        },
    ),
    # Topic supplied via the ?to= convenience alias
    (
        "pushplus://{}/?to=mygroup".format(GOOD_TOKEN),
        {
            "instance": NotifyPushplus,
            "requests_response_text": GOOD_RESPONSE,
        },
    ),
    # Invalid topic characters are silently moved to invalid_targets;
    # the object still instantiates and sends a personal notification
    (
        "pushplus://{}/bad!topic".format(GOOD_TOKEN),
        {
            "instance": NotifyPushplus,
            "requests_response_text": GOOD_RESPONSE,
        },
    ),
    # ----------------------------------------------------------------
    # Delivery channel via ?channel= query parameter
    # ----------------------------------------------------------------
    (
        "pushplus://{}?channel=mail".format(GOOD_TOKEN),
        {
            "instance": NotifyPushplus,
            "requests_response_text": GOOD_RESPONSE,
        },
    ),
    (
        "pushplus://{}?channel=sms".format(GOOD_TOKEN),
        {
            "instance": NotifyPushplus,
            "requests_response_text": GOOD_RESPONSE,
        },
    ),
    (
        "pushplus://{}?channel=cp".format(GOOD_TOKEN),
        {
            "instance": NotifyPushplus,
            "requests_response_text": GOOD_RESPONSE,
        },
    ),
    # wecom is a friendly alias that maps to the "cp" API channel
    (
        "pushplus://{}?channel=wecom".format(GOOD_TOKEN),
        {
            "instance": NotifyPushplus,
            "requests_response_text": GOOD_RESPONSE,
        },
    ),
    # mode= is a synonym for channel=
    (
        "pushplus://{}?mode=mail".format(GOOD_TOKEN),
        {
            "instance": NotifyPushplus,
            "requests_response_text": GOOD_RESPONSE,
        },
    ),
    # ----------------------------------------------------------------
    # Schema alias that auto-sets the delivery channel
    # ----------------------------------------------------------------
    # wecom:// auto-sets channel=cp (WeCom / Enterprise WeChat)
    (
        "wecom://{}".format(GOOD_TOKEN),
        {
            "instance": NotifyPushplus,
            "requests_response_text": GOOD_RESPONSE,
        },
    ),
    # ----------------------------------------------------------------
    # Webhook channel with a named endpoint -- both input forms accepted
    # ----------------------------------------------------------------
    (
        "pushplus://{}?channel=webhook&name=myhook".format(GOOD_TOKEN),
        {
            "instance": NotifyPushplus,
            # url() emits the compact schema://name@token form
            "privacy_url": "pushplus://myhook@",
            "requests_response_text": GOOD_RESPONSE,
        },
    ),
    # schema://name@token form -- channel=webhook is implied
    (
        "pushplus://myhook@{}".format(GOOD_TOKEN),
        {
            "instance": NotifyPushplus,
            "privacy_url": "pushplus://myhook@",
            "requests_response_text": GOOD_RESPONSE,
        },
    ),
    # ----------------------------------------------------------------
    # Native PushPlus API URL (parse_native_url support)
    # ----------------------------------------------------------------
    (
        "https://www.pushplus.plus/send?token={}".format(GOOD_TOKEN),
        {
            "instance": NotifyPushplus,
            "requests_response_text": GOOD_RESPONSE,
        },
    ),
    # ----------------------------------------------------------------
    # API application-level failure (HTTP 200 but JSON code != 200)
    # ----------------------------------------------------------------
    (
        "pushplus://{}".format(GOOD_TOKEN),
        {
            "instance": NotifyPushplus,
            "response": False,
            "requests_response_text": BAD_RESPONSE,
        },
    ),
    # Unparsable JSON body is treated as a failure
    (
        "pushplus://{}".format(GOOD_TOKEN),
        {
            "instance": NotifyPushplus,
            "response": False,
            "requests_response_text": "{bad json",
        },
    ),
    # None body is treated as a failure
    (
        "pushplus://{}".format(GOOD_TOKEN),
        {
            "instance": NotifyPushplus,
            "response": False,
            "requests_response_text": None,
        },
    ),
    # ----------------------------------------------------------------
    # HTTP-level failures
    # ----------------------------------------------------------------
    (
        "pushplus://{}".format(GOOD_TOKEN),
        {
            "instance": NotifyPushplus,
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "pushplus://{}".format(GOOD_TOKEN),
        {
            "instance": NotifyPushplus,
            "response": False,
            "requests_response_code": 999,
        },
    ),
    # ----------------------------------------------------------------
    # Connection / socket exceptions
    # ----------------------------------------------------------------
    (
        "pushplus://{}".format(GOOD_TOKEN),
        {
            "instance": NotifyPushplus,
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_pushplus_urls():
    """NotifyPushplus() Apprise URL test suite."""
    AppriseURLTester(tests=apprise_url_tests).run_all()


def test_plugin_pushplus_init():
    """NotifyPushplus() initialisation and parameter handling."""

    # Minimal valid instantiation -- no targets
    obj = NotifyPushplus(token=GOOD_TOKEN)
    assert obj.token == GOOD_TOKEN
    assert obj.topics == []
    assert obj.channel == PUSHPLUS_CHANNEL_DEFAULT
    assert obj.webhook is None
    assert obj.invalid_targets == []

    # Single group topic via targets list (no prefix required)
    obj = NotifyPushplus(token=GOOD_TOKEN, targets=["mygroup"])
    assert obj.topics == ["mygroup"]
    assert obj.channel == PUSHPLUS_CHANNEL_DEFAULT

    # Multiple group topics
    obj = NotifyPushplus(
        token=GOOD_TOKEN, targets=["group1", "group2", "group3"]
    )
    assert obj.topics == ["group1", "group2", "group3"]

    # Explicit channel via channel= argument
    obj = NotifyPushplus(token=GOOD_TOKEN, channel="mail")
    assert obj.channel == PushPlusChannel.MAIL

    # wecom friendly alias normalises to the "cp" API value
    obj = NotifyPushplus(token=GOOD_TOKEN, channel="wecom")
    assert obj.channel == PushPlusChannel.WECOM
    assert obj.channel == "cp"

    # cp is the canonical API value (same result as wecom)
    obj = NotifyPushplus(token=GOOD_TOKEN, channel="cp")
    assert obj.channel == "cp"

    # Channel is case-insensitive
    obj = NotifyPushplus(token=GOOD_TOKEN, channel="MAIL")
    assert obj.channel == PushPlusChannel.MAIL

    # Invalid channel raises TypeError
    import pytest

    with pytest.raises(TypeError):
        NotifyPushplus(token=GOOD_TOKEN, channel="invalid_channel")

    # Invalid target (bad characters) goes to invalid_targets
    obj = NotifyPushplus(token=GOOD_TOKEN, targets=["bad!target"])
    assert obj.topics == []
    assert obj.invalid_targets == ["bad!target"]

    # Invalid token raises TypeError
    with pytest.raises(TypeError):
        NotifyPushplus(token="short")

    with pytest.raises(TypeError):
        NotifyPushplus(token="bad!token" + "0" * 30)

    # Webhook value stored as None when falsy
    obj = NotifyPushplus(token=GOOD_TOKEN, webhook="")
    assert obj.webhook is None

    # Webhook value stored when truthy
    obj = NotifyPushplus(
        token=GOOD_TOKEN,
        channel="webhook",
        webhook="myhook",
    )
    assert obj.webhook == "myhook"
    assert obj.channel == PushPlusChannel.WEBHOOK


def test_plugin_pushplus_schema_aliases():
    """NotifyPushplus() wecom:// schema alias."""

    # wecom:// schema sets channel=cp (WeCom API value)
    result = NotifyPushplus.parse_url("wecom://{}".format(GOOD_TOKEN))
    assert result is not None
    obj = NotifyPushplus(**result)
    assert obj.channel == PushPlusChannel.WECOM
    assert obj.channel == "cp"

    # An explicit channel= overrides the schema-implied channel
    result = NotifyPushplus.parse_url(
        "wecom://{}?channel=mail".format(GOOD_TOKEN)
    )
    assert result is not None
    obj = NotifyPushplus(**result)
    assert obj.channel == PushPlusChannel.MAIL


def test_plugin_pushplus_all_channels():
    """NotifyPushplus() accepts every documented API channel value."""

    for ch in PUSHPLUS_CHANNELS:
        # Each channel must initialise without raising
        obj = NotifyPushplus(token=GOOD_TOKEN, channel=ch)
        assert obj.channel == ch

        # Channel matching must be case-insensitive
        obj2 = NotifyPushplus(token=GOOD_TOKEN, channel=ch.upper())
        assert obj2.channel == ch


def test_plugin_pushplus_url():
    """NotifyPushplus() url() output and round-trip fidelity."""

    # Personal notification URL -- no topics in path, default channel omitted
    obj = NotifyPushplus(token=GOOD_TOKEN)
    url = obj.url()
    assert url.startswith("pushplus://")
    # Token appears in plain text
    assert GOOD_TOKEN in url
    # No topic path segment
    assert "/mygroup" not in url
    # Default channel is omitted from params
    assert "channel=" not in url

    # Privacy URL must mask the token
    priv = obj.url(privacy=True)
    assert GOOD_TOKEN not in priv
    assert "****" in priv

    # Group topic URL -- topic appears in the path
    obj = NotifyPushplus(token=GOOD_TOKEN, targets=["mygroup"])
    url = obj.url()
    assert "/mygroup/" in url
    priv = obj.url(privacy=True)
    assert "/mygroup/" in priv
    assert GOOD_TOKEN not in priv

    # Multiple topics all appear in the path
    obj = NotifyPushplus(token=GOOD_TOKEN, targets=["grp1", "grp2"])
    url = obj.url()
    assert "grp1" in url
    assert "grp2" in url

    # Non-default channel appears as ?channel= query parameter
    obj = NotifyPushplus(token=GOOD_TOKEN, channel="mail")
    url = obj.url()
    assert "channel=mail" in url

    # Default channel (wechat) is suppressed from the URL
    obj = NotifyPushplus(token=GOOD_TOKEN, channel="wechat")
    url = obj.url()
    assert "channel=" not in url

    # When channel=webhook with a name, url() uses schema://name@token form
    obj = NotifyPushplus(
        token=GOOD_TOKEN,
        channel="webhook",
        webhook="myhook",
    )
    url = obj.url()
    assert "pushplus://myhook@" in url
    # channel= and name= are both implied by user@ -- omitted from params
    assert "channel=" not in url
    assert "name=" not in url

    # Privacy URL preserves the webhook name but masks the token
    priv = obj.url(privacy=True)
    assert "pushplus://myhook@" in priv
    assert GOOD_TOKEN not in priv
    assert "****" in priv

    # Webhook prefix form with group topics -- schema://name@token/topic/ form
    obj = NotifyPushplus(
        token=GOOD_TOKEN,
        channel="webhook",
        webhook="myhook",
        targets=["mygroup"],
    )
    url = obj.url()
    assert "pushplus://myhook@" in url
    assert "mygroup" in url
    assert "channel=" not in url
    assert "name=" not in url

    # Webhook name suppressed when channel is not webhook
    obj = NotifyPushplus(
        token=GOOD_TOKEN,
        channel="mail",
        webhook="myhook",
    )
    url = obj.url()
    assert "name=" not in url
    assert "@" not in url

    # Webhook channel without a name uses the plain ?channel=webhook form
    obj = NotifyPushplus(token=GOOD_TOKEN, channel="webhook")
    url = obj.url()
    assert "name=" not in url
    assert "channel=webhook" in url
    assert "@" not in url

    # Invalid targets are preserved in the URL path for round-trip fidelity
    obj = NotifyPushplus(token=GOOD_TOKEN, targets=["bad!target"])
    url = obj.url()
    assert "bad" in url

    # url_identifier contains only the schema and token (no targets or channel)
    obj = NotifyPushplus(token=GOOD_TOKEN, targets=["grp"])
    assert obj.url_identifier == ("pushplus", GOOD_TOKEN)

    # Schema alias (wecom://) always normalises back to pushplus://
    result = NotifyPushplus.parse_url("wecom://{}".format(GOOD_TOKEN))
    obj = NotifyPushplus(**result)
    url = obj.url()
    assert url.startswith("pushplus://")
    assert "channel=cp" in url


@mock.patch("requests.post")
def test_plugin_pushplus_send_ok(mock_post):
    """NotifyPushplus() successful personal-notification send."""

    # Prepare a successful mock response
    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = GOOD_RESPONSE.encode("utf-8")
    mock_post.return_value = response

    # Personal notification (no topic) -- single API call
    obj = NotifyPushplus(token=GOOD_TOKEN)
    assert obj.send(body="hello", title="title") is True
    assert mock_post.call_count == 1

    # Verify the endpoint URL
    call = mock_post.call_args
    assert call[0][0] == "https://www.pushplus.plus/send"

    # Verify the core payload fields
    payload = loads(call[1]["data"])
    assert payload["token"] == GOOD_TOKEN
    assert payload["content"] == "hello"
    assert payload["title"] == "title"
    # Default format is HTML -- PushPlus template should be "html"
    assert payload["template"] == PUSHPLUS_FORMAT_MAP[NotifyFormat.HTML]
    assert payload["channel"] == PUSHPLUS_CHANNEL_DEFAULT
    # topic and webhook keys must be absent when not configured
    assert "topic" not in payload
    assert "webhook" not in payload

    mock_post.reset_mock()
    response.content = GOOD_RESPONSE.encode("utf-8")

    # When no title is supplied the body is used as the title fallback
    assert obj.send(body="only body") is True
    payload = loads(mock_post.call_args[1]["data"])
    assert payload["title"] == "only body"
    assert payload["content"] == "only body"


@mock.patch("requests.post")
def test_plugin_pushplus_send_formats(mock_post):
    """NotifyPushplus() maps notify_format to the PushPlus template field."""

    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = GOOD_RESPONSE.encode("utf-8")
    mock_post.return_value = response

    obj = NotifyPushplus(token=GOOD_TOKEN)

    # Markdown format -> "markdown" template
    obj.notify_format = NotifyFormat.MARKDOWN
    assert obj.send(body="# heading") is True
    payload = loads(mock_post.call_args[1]["data"])
    assert payload["template"] == "markdown"

    mock_post.reset_mock()
    response.content = GOOD_RESPONSE.encode("utf-8")

    # Text format -> "txt" template
    obj.notify_format = NotifyFormat.TEXT
    assert obj.send(body="plain text") is True
    payload = loads(mock_post.call_args[1]["data"])
    assert payload["template"] == "txt"

    mock_post.reset_mock()
    response.content = GOOD_RESPONSE.encode("utf-8")

    # HTML format -> "html" template
    obj.notify_format = NotifyFormat.HTML
    assert obj.send(body="<b>bold</b>") is True
    payload = loads(mock_post.call_args[1]["data"])
    assert payload["template"] == "html"


@mock.patch("requests.post")
def test_plugin_pushplus_send_topic(mock_post):
    """NotifyPushplus() includes the topic in the payload when configured."""

    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = GOOD_RESPONSE.encode("utf-8")
    mock_post.return_value = response

    # Single topic -- one API call, topic present in payload
    obj = NotifyPushplus(token=GOOD_TOKEN, targets=["mygroup"])
    assert obj.send(body="group msg") is True
    assert mock_post.call_count == 1
    payload = loads(mock_post.call_args[1]["data"])
    assert payload["topic"] == "mygroup"


@mock.patch("requests.post")
def test_plugin_pushplus_send_multiple_topics(mock_post):
    """NotifyPushplus() makes one API call per group topic."""

    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = GOOD_RESPONSE.encode("utf-8")
    mock_post.return_value = response

    # Three topics -> three separate API calls
    obj = NotifyPushplus(
        token=GOOD_TOKEN, targets=["topic1", "topic2", "topic3"]
    )
    assert len(obj.topics) == 3
    assert obj.send(body="multi msg") is True
    assert mock_post.call_count == 3

    # Verify each call carries the correct topic value
    calls = mock_post.call_args_list
    topics_sent = [loads(c[1]["data"])["topic"] for c in calls]
    assert topics_sent == ["topic1", "topic2", "topic3"]

    mock_post.reset_mock()
    response.content = GOOD_RESPONSE.encode("utf-8")

    # Topics with a channel override -- all API calls use the specified channel
    obj2 = NotifyPushplus(
        token=GOOD_TOKEN, targets=["grp1", "grp2"], channel="mail"
    )
    assert len(obj2.topics) == 2
    assert obj2.channel == PushPlusChannel.MAIL
    assert obj2.send(body="mixed") is True
    assert mock_post.call_count == 2
    for call in mock_post.call_args_list:
        assert loads(call[1]["data"])["channel"] == "mail"

    mock_post.reset_mock()

    # Partial failure: first topic succeeds, second fails -> overall False
    good_resp = mock.Mock()
    good_resp.status_code = requests.codes.ok
    good_resp.content = GOOD_RESPONSE.encode("utf-8")
    bad_resp = mock.Mock()
    bad_resp.status_code = requests.codes.ok
    bad_resp.content = BAD_RESPONSE.encode("utf-8")
    mock_post.side_effect = [good_resp, bad_resp]

    obj3 = NotifyPushplus(token=GOOD_TOKEN, targets=["grp1", "grp2"])
    assert obj3.send(body="partial") is False
    assert mock_post.call_count == 2


@mock.patch("requests.post")
def test_plugin_pushplus_send_webhook(mock_post):
    """NotifyPushplus() webhook channel behaviour."""

    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = GOOD_RESPONSE.encode("utf-8")
    mock_post.return_value = response

    # Webhook channel with a named endpoint -- webhook key in payload
    obj = NotifyPushplus(
        token=GOOD_TOKEN,
        channel="webhook",
        webhook="myhook",
    )
    assert obj.send(body="hook msg") is True
    payload = loads(mock_post.call_args[1]["data"])
    assert payload["channel"] == PushPlusChannel.WEBHOOK
    assert payload["webhook"] == "myhook"

    mock_post.reset_mock()
    response.content = GOOD_RESPONSE.encode("utf-8")

    # Webhook channel without a name -- webhook key must be absent
    obj2 = NotifyPushplus(token=GOOD_TOKEN, channel="webhook")
    assert obj2.send(body="hook no name") is True
    payload2 = loads(mock_post.call_args[1]["data"])
    assert "webhook" not in payload2

    mock_post.reset_mock()
    response.content = GOOD_RESPONSE.encode("utf-8")

    # Non-webhook channel with a webhook value set -- key must be absent
    obj3 = NotifyPushplus(
        token=GOOD_TOKEN,
        channel="mail",
        webhook="myhook",
    )
    assert obj3.send(body="mail msg") is True
    payload3 = loads(mock_post.call_args[1]["data"])
    assert "webhook" not in payload3


@mock.patch("requests.post")
def test_plugin_pushplus_send_http_error(mock_post):
    """NotifyPushplus() handles HTTP-level errors correctly."""

    response = mock.Mock()
    response.content = b""
    mock_post.return_value = response

    obj = NotifyPushplus(token=GOOD_TOKEN)

    # HTTP 500
    response.status_code = requests.codes.internal_server_error
    assert obj.send(body="msg") is False

    # Unknown HTTP status code
    response.status_code = 999
    assert obj.send(body="msg") is False


@mock.patch("requests.post")
def test_plugin_pushplus_send_api_error(mock_post):
    """NotifyPushplus() handles API-level failures (HTTP 200, bad code)."""

    response = mock.Mock()
    response.status_code = requests.codes.ok
    mock_post.return_value = response

    obj = NotifyPushplus(token=GOOD_TOKEN)

    # Known API error code (907 = Token does not exist)
    response.content = BAD_RESPONSE.encode("utf-8")
    assert obj.send(body="msg") is False

    # Unknown API error code with a msg field -- falls back to msg
    response.content = dumps({"code": 999, "msg": "some error"}).encode(
        "utf-8"
    )
    assert obj.send(body="msg") is False

    # Unknown API error code with no msg field -- generic fallback
    response.content = dumps({"code": 999}).encode("utf-8")
    assert obj.send(body="msg") is False

    # Unparsable JSON body
    response.content = b"{bad json"
    assert obj.send(body="msg") is False

    # None content -- treated as unparsable
    response.content = None
    assert obj.send(body="msg") is False


@mock.patch("requests.post")
def test_plugin_pushplus_send_exception(mock_post):
    """NotifyPushplus() handles connection exceptions gracefully."""
    mock_post.side_effect = requests.RequestException("connection error")
    obj = NotifyPushplus(token=GOOD_TOKEN)
    assert obj.send(body="msg") is False


@mock.patch("requests.post")
def test_plugin_pushplus_send_exception_multi_topic(mock_post):
    """NotifyPushplus() continues after a connection error on one topic."""

    # First call raises, second succeeds -- overall result is False
    good_resp = mock.Mock()
    good_resp.status_code = requests.codes.ok
    good_resp.content = GOOD_RESPONSE.encode("utf-8")
    mock_post.side_effect = [
        requests.RequestException("network error"),
        good_resp,
    ]

    obj = NotifyPushplus(token=GOOD_TOKEN, targets=["grp1", "grp2"])
    assert obj.send(body="msg") is False
    # Both topics must still be attempted
    assert mock_post.call_count == 2


def test_plugin_pushplus_parse_url():
    """NotifyPushplus() parse_url() extracts all supported fields."""

    # Token in the host position
    result = NotifyPushplus.parse_url("pushplus://{}".format(GOOD_TOKEN))
    assert result["token"] == GOOD_TOKEN
    assert result["targets"] == []

    # Token supplied as a ?token= query parameter
    result = NotifyPushplus.parse_url(
        "pushplus://?token={}".format(GOOD_TOKEN)
    )
    assert result["token"] == GOOD_TOKEN

    # Topic in the URL path becomes a plain targets entry
    result = NotifyPushplus.parse_url(
        "pushplus://{}/mygroup".format(GOOD_TOKEN)
    )
    assert "mygroup" in result["targets"]

    # Two topics in the path
    result = NotifyPushplus.parse_url(
        "pushplus://{}/grp1/grp2".format(GOOD_TOKEN)
    )
    assert "grp1" in result["targets"]
    assert "grp2" in result["targets"]

    # Backward compat: ?topic= adds a plain topic entry
    result = NotifyPushplus.parse_url(
        "pushplus://{}/?topic=mygroup".format(GOOD_TOKEN)
    )
    assert "mygroup" in result["targets"]

    # ?to= alias appends additional targets
    result = NotifyPushplus.parse_url(
        "pushplus://{}/?to=mygroup".format(GOOD_TOKEN)
    )
    assert "mygroup" in result["targets"]

    # Delivery channel via ?channel=
    result = NotifyPushplus.parse_url(
        "pushplus://{}?channel=mail".format(GOOD_TOKEN)
    )
    assert result.get("channel") == "mail"

    # Delivery channel via ?mode= alias
    result = NotifyPushplus.parse_url(
        "pushplus://{}?mode=sms".format(GOOD_TOKEN)
    )
    assert result.get("channel") == "sms"

    # channel= takes precedence over mode= when both are supplied
    result = NotifyPushplus.parse_url(
        "pushplus://{}?mode=sms&channel=mail".format(GOOD_TOKEN)
    )
    assert result.get("channel") == "mail"

    # Webhook name extracted into the "webhook" key from ?name=
    result = NotifyPushplus.parse_url(
        "pushplus://{}?channel=webhook&name=myhook".format(GOOD_TOKEN)
    )
    assert result.get("webhook") == "myhook"
    assert result.get("channel") == "webhook"

    # schema://name@token form: user@ -> webhook, implies channel=webhook
    result = NotifyPushplus.parse_url(
        "pushplus://myhook@{}".format(GOOD_TOKEN)
    )
    assert result.get("webhook") == "myhook"
    assert result.get("channel") == PushPlusChannel.WEBHOOK

    # Explicit ?channel= overrides the webhook implication from user@
    result = NotifyPushplus.parse_url(
        "pushplus://myhook@{}?channel=mail".format(GOOD_TOKEN)
    )
    assert result.get("webhook") == "myhook"
    assert result.get("channel") == "mail"

    # ?name= takes precedence over user@ when both are supplied
    result = NotifyPushplus.parse_url(
        "pushplus://other@{}?channel=webhook&name=myhook".format(GOOD_TOKEN)
    )
    assert result.get("webhook") == "myhook"
    assert result.get("channel") == "webhook"


def test_plugin_pushplus_parse_native_url():
    """NotifyPushplus() parse_native_url() handles all edge cases."""

    # Basic native URL -- token extracted correctly
    result = NotifyPushplus.parse_native_url(
        "https://www.pushplus.plus/send?token={}".format(GOOD_TOKEN)
    )
    assert result is not None
    obj = NotifyPushplus(**result)
    assert obj.token == GOOD_TOKEN

    # Native URL with topic parameter preserved via round-trip
    result = NotifyPushplus.parse_native_url(
        "https://www.pushplus.plus/send?token={}&topic=mygroup".format(
            GOOD_TOKEN
        )
    )
    assert result is not None
    obj = NotifyPushplus(**result)
    assert "mygroup" in obj.topics

    # Native URL with channel parameter preserved
    result = NotifyPushplus.parse_native_url(
        "https://www.pushplus.plus/send?token={}&channel=mail".format(
            GOOD_TOKEN
        )
    )
    assert result is not None
    obj = NotifyPushplus(**result)
    assert obj.channel == PushPlusChannel.MAIL

    # Native URL with webhook name parameter preserved
    result = NotifyPushplus.parse_native_url(
        "https://www.pushplus.plus/send"
        "?token={}&channel=webhook&name=myhook".format(GOOD_TOKEN)
    )
    assert result is not None
    obj = NotifyPushplus(**result)
    assert obj.webhook == "myhook"
    assert obj.channel == PushPlusChannel.WEBHOOK

    # Native URL without a token -- not matched, returns None
    assert (
        NotifyPushplus.parse_native_url(
            "https://www.pushplus.plus/send?channel=mail"
        )
        is None
    )

    # Completely different domain -- not matched, returns None
    assert (
        NotifyPushplus.parse_native_url(
            "https://other.example.com/send?token={}".format(GOOD_TOKEN)
        )
        is None
    )

    # Native URL with no query string -- not matched, returns None
    assert (
        NotifyPushplus.parse_native_url("https://www.pushplus.plus/send")
        is None
    )


@mock.patch("requests.post")
def test_plugin_pushplus_apprise_integration(mock_post):
    """NotifyPushplus() integrates correctly with the Apprise object."""

    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = GOOD_RESPONSE.encode("utf-8")
    mock_post.return_value = response

    # Personal URL -- single notification
    aobj = Apprise()
    assert aobj.add("pushplus://{}".format(GOOD_TOKEN))
    assert len(aobj) == 1
    assert aobj.notify(title="Test Title", body="Test Body") is True
    assert mock_post.call_count == 1

    mock_post.reset_mock()
    response.content = GOOD_RESPONSE.encode("utf-8")

    # Group URL with markdown format override
    aobj2 = Apprise()
    assert aobj2.add(
        "pushplus://{}/mygroup?format=markdown".format(GOOD_TOKEN)
    )
    assert aobj2.notify(body="Group message") is True
    assert mock_post.call_count == 1
    payload = loads(mock_post.call_args[1]["data"])
    # format=markdown must map to the PushPlus "markdown" template
    assert payload["template"] == "markdown"
    assert payload["topic"] == "mygroup"

    mock_post.reset_mock()
    response.content = GOOD_RESPONSE.encode("utf-8")

    # wecom:// schema alias -- channel=cp in payload
    aobj3 = Apprise()
    assert aobj3.add("wecom://{}".format(GOOD_TOKEN))
    assert aobj3.notify(body="WeCom message") is True
    payload = loads(mock_post.call_args[1]["data"])
    assert payload["channel"] == PushPlusChannel.WECOM
