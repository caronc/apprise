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
from apprise.common import NotifyFormat, NotifyType
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
    response._content = dumps({"code": code, "msg": "ok"}).encode("utf-8")
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
def test_plugin_feishu_markdown_input(mock_post):
    """NotifyFeishu(): Markdown input is sent as a titled card."""

    mock_post.return_value = _feishu_response()

    aobj = Apprise()
    assert aobj.add("feishu://{}".format("a" * 8))
    assert aobj.notify(
        title="title", body="**body**", body_format=NotifyFormat.MARKDOWN
    )

    payload = loads(mock_post.call_args_list[0][1]["data"])
    assert payload["msg_type"] == "interactive"
    assert payload["card"]["header"]["title"]["content"] == "title"
    assert payload["card"]["elements"][0]["text"]["content"] == "**body**"

    # Text input on the same URL stays a plain text message
    mock_post.reset_mock()
    assert aobj.notify(
        title="title", body="body", body_format=NotifyFormat.TEXT
    )
    payload = loads(mock_post.call_args_list[0][1]["data"])
    assert payload["msg_type"] == "text"
    assert "card" not in payload


@mock.patch("requests.post")
def test_plugin_feishu_markdown_card(mock_post):
    """NotifyFeishu(): ?format=markdown is delivered as an interactive card."""

    mock_post.return_value = _feishu_response()

    title = "A & <B>"
    body = "**bold** _ . ! * # <"

    aobj = Apprise()
    assert aobj.add("feishu://{}?format=markdown".format("a" * 8))
    assert aobj.notify(
        title=title, body=body, body_format=NotifyFormat.MARKDOWN
    )
    assert mock_post.call_count == 1

    payload = loads(mock_post.call_args_list[0][1]["data"])
    assert payload["msg_type"] == "interactive"
    assert "content" not in payload

    # The title is plain text in the header and is never converted
    header = payload["card"]["header"]
    assert header["title"]["tag"] == "plain_text"
    assert header["title"]["content"] == title
    assert header["template"] == "blue"

    # Declared Markdown reaches the card untouched
    text = payload["card"]["elements"][0]["text"]
    assert text["tag"] == "lark_md"
    assert text["content"] == body

    # A direct call with no declared format passes the body through as is
    mock_post.reset_mock()
    obj = Apprise.instantiate("feishu://{}?format=markdown".format("a" * 8))
    assert obj.notify(title=title, body=body) is True
    payload = loads(mock_post.call_args_list[0][1]["data"])
    assert payload["card"]["header"]["title"]["content"] == title
    assert payload["card"]["elements"][0]["text"]["content"] == body


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
def test_plugin_feishu_utf8_payload(mock_post):
    """NotifyFeishu(): CJK text is sent as raw UTF-8, not escaped."""

    mock_post.return_value = _feishu_response()

    obj = Apprise.instantiate("feishu://{}".format("a" * 8))
    assert obj.notify(body="\u4e2d" * 10) is True

    raw = mock_post.call_args_list[0][1]["data"]
    assert ("\u4e2d" * 10).encode("utf-8") in raw
    assert b"\\u4e2d" not in raw


@mock.patch("requests.post")
def test_plugin_feishu_split_keeps_body(mock_post):
    """NotifyFeishu(): ?overflow=split delivers the whole body."""

    mock_post.return_value = _feishu_response()

    body = "\u4e2d" * 20000
    obj = Apprise.instantiate("feishu://{}?overflow=split".format("a" * 8))
    assert obj.notify(body=body) is True
    assert mock_post.call_count == 2

    sent = "".join(
        loads(call[1]["data"])["content"]["text"]
        for call in mock_post.call_args_list
    )
    assert sent == body


@pytest.mark.parametrize(
    "content,expected",
    [
        (dumps({"code": 9499, "msg": "Bad Request"}).encode("utf-8"), False),
        (dumps({"code": 0, "msg": "success"}).encode("utf-8"), True),
        (dumps({"StatusCode": 0}).encode("utf-8"), True),
        (b"[]", True),
        (b"not json", True),
        (None, True),
    ],
)
@mock.patch("requests.post")
def test_plugin_feishu_response_code(mock_post, content, expected):
    """NotifyFeishu(): a non-zero code in an HTTP 200 reply is a failure."""

    response = requests.Response()
    response.status_code = requests.codes.ok
    response._content = content
    mock_post.return_value = response

    obj = Apprise.instantiate("feishu://{}".format("a" * 8))
    assert obj.notify(body="body") is expected


@mock.patch("requests.post")
def test_plugin_feishu_markdown_url(mock_post):
    """NotifyFeishu(): format=markdown survives a URL round trip."""

    mock_post.return_value = _feishu_response()

    obj = Apprise.instantiate("feishu://{}?format=markdown".format("a" * 8))
    url = obj.url()
    assert "format=markdown" in url

    # The rebuilt URL still sends plain text input as a card
    again = Apprise.instantiate(url)
    assert again is not None
    assert again.notify(body="body", body_format=NotifyFormat.TEXT) is True

    payload = loads(mock_post.call_args_list[0][1]["data"])
    assert payload["msg_type"] == "interactive"

    # A plain URL does not pin a format, so it keeps following the input
    assert (
        "format="
        not in Apprise.instantiate("feishu://{}".format("a" * 8)).url()
    )
