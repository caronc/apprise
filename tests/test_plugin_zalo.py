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
import json
import logging
from unittest import mock
from urllib.parse import urlparse

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise, NotifyFormat
from apprise.exception import AppriseImproperlyConfigured
from apprise.plugins.zalo import NotifyZalo

logging.disable(logging.CRITICAL)

# A realistic Bot Token
TOKEN = "123456789:abcdefghijKLMNOPqrst"

# A successful Zalo response
OK_RESPONSE = json.dumps(
    {"ok": True, "result": {"message_id": "82599fa32f", "date": 1749632637}}
).encode("utf-8")

# Our Testing URLs
apprise_url_tests = (
    (
        "zalo://",
        {
            # No token specified
            "instance": TypeError,
        },
    ),
    (
        "zalo://123456789",
        {
            # Only half of a token
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "zalo://abc:def/chat1",
        {
            # The bot id must be numeric
            "instance": TypeError,
        },
    ),
    (
        f"zalo://{TOKEN}",
        {
            # No Chat IDs; we load but have nothing to notify
            "instance": NotifyZalo,
            "notify_response": False,
        },
    ),
    (
        f"zalo://{TOKEN}/chat1",
        {
            "instance": NotifyZalo,
            "requests_response_text": OK_RESPONSE,
            # Our expected url(privacy=True) startswith() response
            "privacy_url": "zalo://1...t/chat1",
        },
    ),
    (
        "zalo://123456789%3Aabcdefghij/chat1/chat.2/",
        {
            # An encoded colon is accepted too
            "instance": NotifyZalo,
        },
    ),
    (
        "zalo://123456789/abcdefghij/chat1/",
        {
            # A slash in place of the colon is accepted too
            "instance": NotifyZalo,
        },
    ),
    (
        f"zalo://chat1/?token={TOKEN}&to=chat2,chat3",
        {
            # Token and Chat IDs given as arguments
            "instance": NotifyZalo,
            "privacy_url": "zalo://1...t/chat1/chat2/chat3",
        },
    ),
    (
        f"zalo://?token={TOKEN}&to=chat1",
        {
            # No host at all
            "instance": NotifyZalo,
        },
    ),
    (
        f"zalo://{TOKEN}/chat1/invalid!id",
        {
            # One bad Chat ID is dropped; the good one still works
            "instance": NotifyZalo,
        },
    ),
    (
        f"zalo://{TOKEN}/invalid!id",
        {
            # Nothing valid to notify
            "instance": NotifyZalo,
            "notify_response": False,
        },
    ),
    (
        f"zalo://{TOKEN}/chat1",
        {
            # Zalo refused the message
            "instance": NotifyZalo,
            "requests_response_text": {
                "ok": False,
                "error_code": 400,
                "description": "Bad Request",
            },
            "response": False,
        },
    ),
    (
        f"zalo://{TOKEN}/chat1",
        {
            "instance": NotifyZalo,
            # throw a bizarre code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        f"zalo://{TOKEN}/chat1",
        {
            "instance": NotifyZalo,
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        f"zalo://{TOKEN}/chat1",
        {
            "instance": NotifyZalo,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracefully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def _mk_resp(content=OK_RESPONSE, code=requests.codes.ok):
    """Build a mock Zalo response."""
    r = mock.Mock()
    r.status_code = code
    r.content = content
    return r


def test_plugin_zalo_urls():
    """NotifyZalo() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


def test_plugin_zalo_init():
    """NotifyZalo() validates its token and Chat IDs."""

    # Bad tokens are refused
    for token in (None, "", "123456789", "abc:def", "123:bad token"):
        with pytest.raises(AppriseImproperlyConfigured):
            NotifyZalo(token=token, targets="chat1")

    # Good and bad Chat IDs are kept apart
    obj = NotifyZalo(token=TOKEN, targets=["chat1", "a.b-c_d", "bad!id"])
    assert obj.targets == ["a.b-c_d", "chat1"]
    assert obj.invalid_targets == ["bad!id"]
    assert len(obj) == 2

    # No targets still counts as one notification
    assert len(NotifyZalo(token=TOKEN)) == 1


def test_plugin_zalo_round_trip():
    """NotifyZalo() url() reloads into the same object."""

    obj = NotifyZalo(
        token=TOKEN, targets=["chat1", "bad!id"], format=NotifyFormat.TEXT
    )
    url = obj.url()
    assert url.startswith(f"zalo://{TOKEN}/chat1/bad%21id?")
    assert "format=text" in url

    result = NotifyZalo.parse_url(url)
    assert result["token"] == TOKEN
    obj2 = NotifyZalo(**result)
    assert obj2.url_identifier == obj.url_identifier
    assert obj2.targets == obj.targets
    assert obj2.invalid_targets == obj.invalid_targets
    assert obj2.url() == url

    # Different targets are still the same bot
    assert (
        NotifyZalo(token=TOKEN, targets="other").url_identifier
        == obj.url_identifier
    )

    # Nothing to parse
    assert NotifyZalo.parse_url(None) is None


@mock.patch("requests.post")
def test_plugin_zalo_payload(mock_post):
    """NotifyZalo() posts one message to each Chat ID."""

    mock_post.return_value = _mk_resp()
    obj = NotifyZalo(token=TOKEN, targets=["chat1", "chat2"])

    assert obj.notify(body="body", title="title")
    assert mock_post.call_count == 2

    # The Bot Token is part of the API path
    url = mock_post.call_args_list[0][0][0]
    assert urlparse(url).hostname == "bot-api.zaloplatforms.com"
    assert urlparse(url).path == f"/bot{TOKEN}/sendMessage"

    # Each Chat ID gets its own copy
    first = json.loads(mock_post.call_args_list[0][1]["data"])
    second = json.loads(mock_post.call_args_list[1][1]["data"])
    assert first["chat_id"] == "chat1"
    assert second["chat_id"] == "chat2"

    # Undeclared content takes the Markdown path, title on its own line
    assert first["text"] == "title\r\nbody"
    assert first["parse_mode"] == "markdown"


@mock.patch("requests.post")
def test_plugin_zalo_partial_failure(mock_post):
    """NotifyZalo() reports a failure when one Chat ID is refused."""

    mock_post.side_effect = (
        _mk_resp(),
        _mk_resp(b"", requests.codes.unauthorized),
    )
    obj = NotifyZalo(token=TOKEN, targets=["chat1", "chat2"])
    assert not obj.notify(body="body")
    assert mock_post.call_count == 2

    # An empty body with a 200 is still a success
    mock_post.side_effect = None
    mock_post.return_value = _mk_resp(None)
    assert obj.notify(body="body")


@mock.patch("requests.post")
def test_plugin_zalo_formats(mock_post):
    """NotifyZalo() asks Zalo to style Markdown and leaves text alone."""

    mock_post.return_value = _mk_resp()
    obj = NotifyZalo(token=TOKEN, targets="chat1")

    # Markdown keeps its markup and turns on parse_mode
    assert obj.notify(
        body="**bold** _it_ \\*",
        title="T & <x>",
        body_format=NotifyFormat.MARKDOWN,
    )
    payload = json.loads(mock_post.call_args[1]["data"])
    assert payload["parse_mode"] == "markdown"
    assert payload["text"].endswith("**bold** _it_ \\*")
    assert payload["text"].startswith("# T")

    # HTML is converted to Markdown
    assert obj.notify(
        body="<b>bold</b> <i>it</i>", body_format=NotifyFormat.HTML
    )
    payload = json.loads(mock_post.call_args[1]["data"])
    assert payload["parse_mode"] == "markdown"
    assert payload["text"] == "**bold** *it*"

    # Plain text reaches Zalo exactly as it was typed
    assert obj.notify(
        body="5 * 3 = a_b <tag> # x", body_format=NotifyFormat.TEXT
    )
    payload = json.loads(mock_post.call_args[1]["data"])
    assert payload["text"] == "5 * 3 = a_b <tag> # x"
    assert "parse_mode" not in payload

    # Content with no declared format is not touched
    assert obj.notify(body="**raw** \\*")
    payload = json.loads(mock_post.call_args[1]["data"])
    assert payload["text"] == "**raw** \\*"
    assert payload["parse_mode"] == "markdown"

    # ?format=text sends passthrough content as plain text
    obj = NotifyZalo(token=TOKEN, targets="chat1", format="text")
    assert obj.notify(body="**raw**")
    payload = json.loads(mock_post.call_args[1]["data"])
    assert payload["text"] == "**raw**"
    assert "parse_mode" not in payload


@mock.patch("requests.post")
def test_plugin_zalo_apprise_integration(mock_post):
    """Apprise() loads and notifies a zalo:// URL."""

    mock_post.return_value = _mk_resp()
    apobj = Apprise()
    assert apobj.add(f"zalo://{TOKEN}/chat1")
    assert apobj.notify(body="hello")
    assert mock_post.call_count == 1
