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
from apprise.common import NotifyType
from apprise.exception import AppriseImproperlyConfigured
from apprise.plugins.feishu import NotifyFeishu

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    (
        "feishu://",
        {
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "feishu://:@/",
        {
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "feishu://%badtoken%",
        {
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "feishu://abc123",
        {
            # Test token
            "instance": NotifyFeishu,
        },
    ),
    (
        "feishu://?token=abc123",
        {
            # Test token
            "instance": NotifyFeishu,
        },
    ),
    (
        "feishu://token",
        {
            "instance": NotifyFeishu,
            # force a failure
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "feishu://token",
        {
            "instance": NotifyFeishu,
            # throw a bizarre code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "feishu://token",
        {
            "instance": NotifyFeishu,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracefully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_feishu_urls():
    """NotifyFeishu() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


def _feishu_response(code=0):
    """Build a Feishu webhook response."""
    response = requests.Response()
    response.status_code = requests.codes.ok
    response._content = dumps(
        {"StatusCode": code if code else 0, "code": code, "msg": "ok"}
    ).encode("utf-8")
    return response


@mock.patch("requests.post")
def test_plugin_feishu_text_is_default(mock_post):
    """NotifyFeishu(): plain text stays the default message type."""

    mock_post.return_value = _feishu_response()

    aobj = Apprise()
    assert aobj.add("feishu://{}".format("a" * 8))
    assert bool(aobj.notify(title="title", body="body")) is True
    assert mock_post.call_count == 1

    payload = loads(mock_post.call_args_list[0][1]["data"])
    assert payload["msg_type"] == "text"
    assert payload["content"]["text"] == "title\r\nbody"
    assert "card" not in payload


@mock.patch("requests.post")
def test_plugin_feishu_markdown_card(mock_post):
    """NotifyFeishu(): Markdown is delivered as an interactive card."""

    mock_post.return_value = _feishu_response()

    aobj = Apprise()
    assert aobj.add("feishu://{}?format=markdown".format("a" * 8))
    assert bool(aobj.notify(title="title", body="**body**")) is True
    assert mock_post.call_count == 1

    payload = loads(mock_post.call_args_list[0][1]["data"])
    assert payload["msg_type"] == "interactive"
    assert payload["card"]["header"]["title"]["content"] == "title"
    assert payload["card"]["header"]["template"] == "blue"
    assert payload["card"]["elements"][0]["text"]["tag"] == "lark_md"
    assert payload["card"]["elements"][0]["text"]["content"] == "**body**"


@mock.patch("requests.post")
def test_plugin_feishu_markdown_card_no_title(mock_post):
    """NotifyFeishu(): a card always carries a title."""

    mock_post.return_value = _feishu_response()

    obj = Apprise.instantiate("feishu://{}?format=markdown".format("a" * 8))
    assert obj.notify(body="body") is True
    assert mock_post.call_count == 1

    payload = loads(mock_post.call_args_list[0][1]["data"])
    assert payload["card"]["header"]["title"]["content"] == obj.app_desc


@pytest.mark.parametrize(
    "notify_type,colour",
    [
        (NotifyType.INFO, "blue"),
        (NotifyType.SUCCESS, "green"),
        (NotifyType.WARNING, "orange"),
        (NotifyType.FAILURE, "red"),
    ],
)
@mock.patch("requests.post")
def test_plugin_feishu_card_colours(mock_post, notify_type, colour):
    """NotifyFeishu(): the card header colour tracks the notification type."""

    mock_post.return_value = _feishu_response()

    obj = Apprise.instantiate("feishu://{}?format=markdown".format("a" * 8))
    assert obj.notify(body="body", notify_type=notify_type) is True

    payload = loads(mock_post.call_args_list[0][1]["data"])
    assert payload["card"]["header"]["template"] == colour


@mock.patch("requests.post")
def test_plugin_feishu_card_byte_budget(mock_post):
    """NotifyFeishu(): a CJK card is trimmed to the 20 KB byte cap.

    Feishu measures its 20 KB limit in bytes, while body_maxlen counts
    characters; a Chinese body therefore needs trimming well before the
    character limit is reached.
    """

    mock_post.return_value = _feishu_response()

    obj = Apprise.instantiate("feishu://{}?format=markdown".format("a" * 8))
    assert obj.notify(body="\u4e2d" * 20000) is True
    assert mock_post.call_count == 1

    raw = mock_post.call_args_list[0][1]["data"]
    assert len(raw) <= NotifyFeishu.max_payload_bytes

    content = loads(raw)["card"]["elements"][0]["text"]["content"]
    assert content.endswith("\u2026")
    assert len(content.encode("utf-8")) < 20000 * 3


@mock.patch("requests.post")
def test_plugin_feishu_rejected_payload(mock_post):
    """NotifyFeishu(): a non-zero response code fails the notification."""

    mock_post.return_value = _feishu_response(code=9499)

    obj = Apprise.instantiate("feishu://{}".format("a" * 8))
    assert obj.notify(body="body") is False


def test_plugin_feishu_markdown_url():
    """NotifyFeishu(): format=markdown survives a URL round trip."""

    obj = Apprise.instantiate("feishu://{}?format=markdown".format("a" * 8))
    assert obj.title_maxlen == NotifyFeishu.card_title_maxlen

    url = obj.url()
    assert "format=markdown" in url

    again = Apprise.instantiate(url)
    assert again is not None
    assert again.title_maxlen == NotifyFeishu.card_title_maxlen

    # Plain text keeps blending the title into the body
    assert Apprise.instantiate("feishu://{}".format("a" * 8)).title_maxlen == 0
