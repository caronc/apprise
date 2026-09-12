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

from json import loads

# Disable logging for a cleaner testing output
import logging
from unittest import mock

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise, AppriseAsset, NotifyType
from apprise.plugins.youlmk import NotifyYouLMK, youlmk_priority

logging.disable(logging.CRITICAL)

# The handoff's placeholder key and a token of the same shape; neither is real
TOKEN = "ylk_" + "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"
KEY = "k_7hq2nk3f9qd8w4"

# Our Testing URLs
apprise_url_tests = (
    (
        "youlmk://",
        {
            # No token specified
            "instance": TypeError,
        },
    ),
    (
        "youlmk://invalid",
        {
            # Neither a ylk_ token nor a k_ key
            "instance": TypeError,
        },
    ),
    (
        "youlmk://ylk_tooshort",
        {
            # The token's shape is ylk_ and 32 characters
            "instance": TypeError,
        },
    ),
    (
        f"youlmk://{TOKEN}",
        {
            # A valid bearer token
            "instance": NotifyYouLMK,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "youlmk://y...6/",
        },
    ),
    (
        f"youlmk://{KEY}",
        {
            # A valid URL key
            "instance": NotifyYouLMK,
            "privacy_url": "youlmk://k...4/",
        },
    ),
    (
        f"youlmk://?token={TOKEN}",
        {
            # The token provided as a query argument
            "instance": NotifyYouLMK,
            "privacy_url": "youlmk://y...6/",
        },
    ),
    (
        f"youlmk://{TOKEN}?priority=critical",
        {
            # A forced priority
            "instance": NotifyYouLMK,
        },
    ),
    (
        f"youlmk://{TOKEN}?priority=bogus",
        {
            # An unknown priority
            "instance": TypeError,
        },
    ),
    (
        f"youlmk://{TOKEN}?failure=critical&info=low",
        {
            # Per-type priorities
            "instance": NotifyYouLMK,
        },
    ),
    (
        f"youlmk://{TOKEN}?warning=bogus",
        {
            # An unknown per-type priority
            "instance": TypeError,
        },
    ),
    (
        f"youlmk://{TOKEN}?url=https://example.com/runs/1&group=deploys",
        {
            # A link and a group
            "instance": NotifyYouLMK,
        },
    ),
    (
        f"youlmk://{TOKEN}",
        {
            "instance": NotifyYouLMK,
            # Throw an exception on the send
            "test_requests_exceptions": True,
        },
    ),
    (
        f"youlmk://{TOKEN}",
        {
            "instance": NotifyYouLMK,
            # An unknown key
            "response": False,
            "requests_response_code": 401,
        },
    ),
    (
        f"youlmk://{TOKEN}",
        {
            "instance": NotifyYouLMK,
            # The trial's notifications are used
            "response": False,
            "requests_response_code": 402,
        },
    ),
    (
        f"youlmk://{TOKEN}",
        {
            "instance": NotifyYouLMK,
            # A code the map does not name
            "response": False,
            "requests_response_code": 999,
        },
    ),
)


def test_plugin_youlmk_urls():
    """NotifyYouLMK() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


def test_plugin_youlmk_edge_cases():
    """NotifyYouLMK() Edge Cases."""

    # No token
    with pytest.raises(TypeError):
        NotifyYouLMK(token=None)

    # An empty token
    with pytest.raises(TypeError):
        NotifyYouLMK(token="  ")

    # The wrong shape
    with pytest.raises(TypeError):
        NotifyYouLMK(token="ylk_" + "x" * 31)

    # A bad forced priority
    with pytest.raises(TypeError):
        NotifyYouLMK(token=TOKEN, priority="bogus")

    # A bad per-type priority
    with pytest.raises(TypeError):
        NotifyYouLMK(token=TOKEN, failure="bogus")

    # Both shapes are accepted, and the case of the token is kept
    obj = NotifyYouLMK(token=TOKEN.upper())
    assert obj.token == TOKEN.upper()
    assert obj.is_token is True

    obj = NotifyYouLMK(token=KEY)
    assert obj.is_token is False


@mock.patch("requests.post")
def test_plugin_youlmk_send_token(mock_post):
    """NotifyYouLMK() Send with the bearer token."""

    response = mock.Mock()
    response.status_code = requests.codes.ok
    mock_post.return_value = response

    obj = Apprise.instantiate(f"youlmk://{TOKEN}")
    assert isinstance(obj, NotifyYouLMK)

    assert obj.notify(title="backup finished", body="4.2 GB") is True
    assert mock_post.call_count == 1

    # The bearer door, with the token in the header
    assert mock_post.call_args[0][0] == "https://youlmk.com/v1/notify"
    headers = mock_post.call_args[1]["headers"]
    assert headers["Authorization"] == f"Bearer {TOKEN}"
    assert headers["Content-Type"] == "application/json; charset=utf-8"

    payload = loads(mock_post.call_args[1]["data"])
    assert payload["title"] == "backup finished"
    assert payload["body"] == "4.2 GB"
    # INFO maps to normal by default
    assert payload["priority"] == "normal"
    assert "url" not in payload
    assert "group" not in payload


@mock.patch("requests.post")
def test_plugin_youlmk_send_key(mock_post):
    """NotifyYouLMK() Send with the URL key."""

    response = mock.Mock()
    response.status_code = requests.codes.ok
    mock_post.return_value = response

    obj = Apprise.instantiate(f"youlmk://{KEY}")
    assert isinstance(obj, NotifyYouLMK)

    assert obj.notify(title="deployed", body="v2.4.1") is True
    assert mock_post.call_count == 1

    # The key door, with the key in the address and no bearer header
    assert mock_post.call_args[0][0] == f"https://youlmk.com/k/{KEY}"
    assert "Authorization" not in mock_post.call_args[1]["headers"]

    payload = loads(mock_post.call_args[1]["data"])
    assert payload["title"] == "deployed"
    assert payload["priority"] == "normal"


@mock.patch("requests.post")
def test_plugin_youlmk_notify_type_mapping(mock_post):
    """NotifyYouLMK() Priority derived from the notification type."""

    response = mock.Mock()
    response.status_code = requests.codes.ok
    mock_post.return_value = response

    obj = Apprise.instantiate(f"youlmk://{TOKEN}")

    expected = {
        NotifyType.INFO: "normal",
        NotifyType.SUCCESS: "normal",
        NotifyType.WARNING: "high",
        NotifyType.FAILURE: "high",
    }
    for notify_type, priority in expected.items():
        mock_post.reset_mock()
        assert obj.notify(title="t", body="b", notify_type=notify_type) is True
        payload = loads(mock_post.call_args[1]["data"])
        assert payload["priority"] == priority


@mock.patch("requests.post")
def test_plugin_youlmk_priority_override(mock_post):
    """NotifyYouLMK() A forced priority wins over the type."""

    response = mock.Mock()
    response.status_code = requests.codes.ok
    mock_post.return_value = response

    obj = Apprise.instantiate(f"youlmk://{TOKEN}?priority=crit")
    assert obj.priority == "critical"

    assert obj.notify(title="t", body="b", notify_type=NotifyType.INFO) is True
    payload = loads(mock_post.call_args[1]["data"])
    assert payload["priority"] == "critical"


@mock.patch("requests.post")
def test_plugin_youlmk_per_type_priorities(mock_post):
    """NotifyYouLMK() Per-type priorities from the URL."""

    response = mock.Mock()
    response.status_code = requests.codes.ok
    mock_post.return_value = response

    obj = Apprise.instantiate(
        f"youlmk://{TOKEN}?info=low&success=l&warning=n&failure=critical"
    )
    assert obj.priority is None
    assert obj.priority_map[NotifyType.INFO] == "low"
    assert obj.priority_map[NotifyType.SUCCESS] == "low"
    assert obj.priority_map[NotifyType.WARNING] == "normal"
    assert obj.priority_map[NotifyType.FAILURE] == "critical"

    assert (
        obj.notify(title="t", body="b", notify_type=NotifyType.FAILURE) is True
    )
    payload = loads(mock_post.call_args[1]["data"])
    assert payload["priority"] == "critical"

    # Every changed mapping is carried by the URL
    url = obj.url()
    assert "info=low" in url
    assert "success=low" in url
    assert "warning=normal" in url
    assert "failure=critical" in url


@mock.patch("requests.post")
def test_plugin_youlmk_link_and_group(mock_post):
    """NotifyYouLMK() A link and a group travel with the payload."""

    response = mock.Mock()
    response.status_code = requests.codes.ok
    mock_post.return_value = response

    obj = Apprise.instantiate(
        f"youlmk://{TOKEN}?url=https://example.com/runs/1&group=deploys"
    )
    assert obj.link == "https://example.com/runs/1"
    assert obj.group == "deploys"

    assert obj.notify(title="deployed", body="v2.4.1") is True
    payload = loads(mock_post.call_args[1]["data"])
    assert payload["url"] == "https://example.com/runs/1"
    assert payload["group"] == "deploys"

    # And come back out of the URL
    url = obj.url()
    assert "url=https%3A%2F%2Fexample.com%2Fruns%2F1" in url
    assert "group=deploys" in url


@mock.patch("requests.post")
def test_plugin_youlmk_empty_title(mock_post):
    """NotifyYouLMK() A title is always sent."""

    response = mock.Mock()
    response.status_code = requests.codes.ok
    mock_post.return_value = response

    # The application description stands in for a missing title
    asset = AppriseAsset(app_desc="My App")
    obj = Apprise.instantiate(f"youlmk://{TOKEN}", asset=asset)
    assert obj.notify(body="b", title="") is True
    payload = loads(mock_post.call_args[1]["data"])
    assert payload["title"] == "My App"

    # And the application id when there is no description either
    mock_post.reset_mock()
    asset = AppriseAsset(app_desc="", app_id="apprise")
    obj = Apprise.instantiate(f"youlmk://{TOKEN}", asset=asset)
    assert obj.notify(body="b", title="") is True
    payload = loads(mock_post.call_args[1]["data"])
    assert payload["title"] == "apprise"


@mock.patch("requests.post")
def test_plugin_youlmk_failures(mock_post):
    """NotifyYouLMK() The door's own codes read as failures."""

    for code in (401, 402, 410, 413, 422, 429, 503):
        response = mock.Mock()
        response.status_code = code
        response.content = b'{"error":"code"}'
        mock_post.return_value = response

        obj = Apprise.instantiate(f"youlmk://{TOKEN}")
        assert obj.notify(title="t", body="b") is False

    # A connection error
    mock_post.side_effect = requests.RequestException("down")
    obj = Apprise.instantiate(f"youlmk://{TOKEN}")
    assert obj.notify(title="t", body="b") is False


@mock.patch("requests.post")
def test_plugin_youlmk_url_roundtrip(mock_post):
    """NotifyYouLMK() A URL survives a round trip."""

    response = mock.Mock()
    response.status_code = requests.codes.ok
    mock_post.return_value = response

    source = f"youlmk://{TOKEN}?priority=high&failure=critical&group=g"
    obj = Apprise.instantiate(source)
    url = obj.url()
    assert url.startswith(f"youlmk://{TOKEN}/?")
    assert "priority=high" in url
    assert "failure=critical" in url
    assert "group=g" in url

    again = Apprise.instantiate(url)
    assert isinstance(again, NotifyYouLMK)
    assert again.token == TOKEN
    assert again.priority == "high"
    assert again.priority_map[NotifyType.FAILURE] == "critical"
    assert again.group == "g"
    assert again.url_identifier == obj.url_identifier

    # Two credentials are two identifiers
    other = Apprise.instantiate(f"youlmk://{KEY}")
    assert other.url_identifier != obj.url_identifier


def test_plugin_youlmk_parse_url():
    """NotifyYouLMK() parse_url()."""

    # An unparseable (non-string) URL returns None
    assert NotifyYouLMK.parse_url(None) is None

    results = NotifyYouLMK.parse_url(f"youlmk://{TOKEN}")
    assert results["token"] == TOKEN
    assert "priority" not in results
    assert "link" not in results

    results = NotifyYouLMK.parse_url(
        f"youlmk://ignored?token={TOKEN}&priority=low&info=high"
        "&url=https://example.com&group=g"
    )
    assert results["token"] == TOKEN
    assert results["priority"] == "low"
    assert results["info"] == "high"
    assert results["link"] == "https://example.com"
    assert results["group"] == "g"


def test_plugin_youlmk_priority_resolution():
    """youlmk_priority() resolves short forms and refuses the rest."""

    assert youlmk_priority("low") == "low"
    assert youlmk_priority("l") == "low"
    assert youlmk_priority("NORMAL") == "normal"
    assert youlmk_priority("hi") == "high"
    assert youlmk_priority("crit") == "critical"
    assert youlmk_priority("") is None
    assert youlmk_priority("   ") is None
    assert youlmk_priority("bogus") is None
