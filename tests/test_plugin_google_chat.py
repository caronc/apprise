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

from apprise import Apprise, NotifyFormat, NotifyType
from apprise.plugins.google_chat import NotifyGoogleChat

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    (
        "gchat://",
        {
            "instance": TypeError,
        },
    ),
    (
        "gchat://:@/",
        {
            "instance": TypeError,
        },
    ),
    # Workspace, but not Key or Token
    (
        "gchat://workspace",
        {
            "instance": TypeError,
        },
    ),
    # Workspace and key, but no Token
    (
        "gchat://workspace/key/",
        {
            "instance": TypeError,
        },
    ),
    # Credentials are good
    (
        "gchat://workspace/key/token",
        {
            "instance": NotifyGoogleChat,
            "privacy_url": "gchat://w...e/k...y/t...n",
        },
    ),
    # Test arguments
    (
        "gchat://?workspace=ws&key=mykey&token=mytoken",
        {
            "instance": NotifyGoogleChat,
            "privacy_url": "gchat://w...s/m...y/m...n",
        },
    ),
    (
        "gchat://?workspace=ws&key=mykey&token=mytoken&thread=abc123",
        {
            # Test our thread key
            "instance": NotifyGoogleChat,
            "privacy_url": "gchat://w...s/m...y/m...n/a...3",
        },
    ),
    (
        "gchat://?workspace=ws&key=mykey&token=mytoken&threadKey=abc345",
        {
            # Test our thread key
            "instance": NotifyGoogleChat,
            "privacy_url": "gchat://w...s/m...y/m...n/a...5",
        },
    ),
    # Google Native Webhook URL
    (
        (
            "https://chat.googleapis.com/v1/spaces/myworkspace/messages"
            "?key=mykey&token=mytoken"
        ),
        {
            "instance": NotifyGoogleChat,
            "privacy_url": "gchat://m...e/m...y/m...n",
        },
    ),
    (
        (
            "https://chat.googleapis.com/v1/spaces/myworkspace/messages"
            "?key=mykey&token=mytoken&threadKey=mythreadkey"
        ),
        {
            "instance": NotifyGoogleChat,
            "privacy_url": "gchat://m...e/m...y/m...n/m...y",
        },
    ),
    (
        "gchat://workspace/key/token",
        {
            "instance": NotifyGoogleChat,
            # force a failure
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "gchat://workspace/key/token",
        {
            "instance": NotifyGoogleChat,
            # throw a bizarre code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "gchat://workspace/key/token",
        {
            "instance": NotifyGoogleChat,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracefully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_google_chat_urls():
    """NotifyGoogleChat() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.post")
def test_plugin_google_chat_general(mock_post):
    """NotifyGoogleChat() General Checks."""

    # Initialize some generic (but valid) tokens
    workspace = "ws"
    key = "key"
    threadkey = "threadkey"
    token = "token"

    # Prepare Mock
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok

    # Test our messaging
    obj = Apprise.instantiate(f"gchat://{workspace}/{key}/{token}")
    assert isinstance(obj, NotifyGoogleChat)
    assert (
        bool(
            obj.notify(
                body="test body", title="title", notify_type=NotifyType.INFO
            )
        )
        is True
    )

    # Test our call count
    assert mock_post.call_count == 1
    assert (
        mock_post.call_args_list[0][0][0]
        == "https://chat.googleapis.com/v1/spaces/ws/messages"
    )
    params = mock_post.call_args_list[0][1]["params"]
    assert params.get("token") == token
    assert params.get("key") == key
    assert "messageReplyOption" not in params
    payload = loads(mock_post.call_args_list[0][1]["data"])
    assert "thread" not in payload
    assert payload["text"] == "title\r\ntest body"

    mock_post.reset_mock()

    # Test our messaging with the thread_key
    obj = Apprise.instantiate(f"gchat://{workspace}/{key}/{token}/{threadkey}")
    assert isinstance(obj, NotifyGoogleChat)
    assert (
        bool(
            obj.notify(
                body="test body", title="title", notify_type=NotifyType.INFO
            )
        )
        is True
    )

    # Test our call count
    assert mock_post.call_count == 1
    assert (
        mock_post.call_args_list[0][0][0]
        == "https://chat.googleapis.com/v1/spaces/ws/messages"
    )
    params = mock_post.call_args_list[0][1]["params"]
    assert params.get("token") == token
    assert params.get("key") == key
    assert (
        params.get("messageReplyOption")
        == "REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD"
    )
    payload = loads(mock_post.call_args_list[0][1]["data"])
    assert "thread" in payload
    assert payload["text"] == "title\r\ntest body"
    assert payload["thread"].get("thread_key") == threadkey


def test_plugin_google_chat_edge_case():
    """NotifyGoogleChat() Edge Cases."""
    with pytest.raises(TypeError):
        NotifyGoogleChat("workspace", "webhook", "token", thread_key=object())


@mock.patch("requests.post")
def test_plugin_google_chat_html_to_markdown_hardening(mock_post):
    """Test edge cases in the CommonMark-to-Google-Chat dialect
    adaptation."""

    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok
    mock_post.return_value.content = b"{}"
    mock_post.return_value.text = "{}"

    def notify(body):
        """Send one HTML body through the configured Google Chat plugin."""
        aobj = Apprise()
        assert aobj.add("gchat://workspace/key/token")
        assert (
            bool(aobj.notify(body=body, body_format=NotifyFormat.HTML)) is True
        )
        payload = loads(mock_post.call_args_list[-1][1]["data"])
        mock_post.reset_mock()
        return payload["text"]

    # Convert CommonMark emphasis to Google Chat delimiters.
    assert notify("<b>hello</b> <i>world</i>") == "*hello* _world_"

    # A CommonMark link ("[text](<url>)", html_to_markdown's output) must
    # arrive as Chat's own "<url|text>" syntax.
    assert (
        notify('<a href="https://example.com/x">click here</a>')
        == "<https://example.com/x|click here>"
    )

    # '&'/'<'/'>' need entity escaping, since Chat's own <...> link/mention
    # syntax reserves them.
    assert notify("<p>2 &lt; 3 &amp; 4</p>") == "2 &lt; 3 &amp; 4"

    # Escape Chat control characters in link destinations.
    assert (
        notify('<a href="https://e/x>TAIL">click</a>')
        == "<https://e/x&gt;TAIL|click>"
    )

    # Percent-encode Chat's URL-label separator inside destinations.
    assert (
        notify('<a href="https://e/x|evil">click</a>')
        == "<https://e/x%7Cevil|click>"
    )

    # Entity-escape Chat controls inside code spans.
    assert notify("<code>a &lt; b &amp; c</code>") == "`a &lt; b &amp; c`"

    # Adjacent nested tags flatten to CommonMark italic around bold.
    assert notify("<b><i>x</i></b>") == "_*x*_"

    # Non-adjacent nesting and sibling spans are unaffected.
    assert notify("<b>bold <i>italic</i> still bold</b>") == (
        "*bold _italic_ still bold*"
    )
    # Adjacent bold tags retain their ambiguous middle markers as literals.
    assert notify("<b>A</b><b>B</b>") == "*A****B*"

    # Direct Google Chat Markdown remains unchanged.
    aobj = Apprise()
    assert aobj.add("gchat://workspace/key/token")
    assert bool(aobj.notify(body="*already* chat-bound markdown")) is True
    payload = loads(mock_post.call_args_list[-1][1]["data"])
    assert payload["text"] == "*already* chat-bound markdown"
    mock_post.reset_mock()

    # Preserve unmatched backticks as literal text.
    assert (
        NotifyGoogleChat._commonmark_to_google_chat("text ``unterminated")
        == "text ``unterminated"
    )

    # Preserve an opener with no closer.
    assert NotifyGoogleChat._commonmark_to_google_chat("****x") == "****x"

    # A backslash-escaped '>' outside of link syntax still needs entity
    # escaping, the same as a bare one.
    f = NotifyGoogleChat._commonmark_to_google_chat
    assert f("\\>literal") == "&gt;literal"

    # Drop CommonMark escapes that Google Chat does not use.
    assert f("\\!text") == "!text"

    # A three-backtick content line cannot close a four-backtick fence.
    # Preserve indentation until the matching four-backtick closing fence.
    assert f("````\n``` nested\n  indented\nlast\n````") == (
        "````\n``` nested\n  indented\nlast\n````"
    )

    # Preserve escapes so Chat formatting characters remain literal.
    assert f("\\*text\\*") == "\\*text\\*"
    assert f("\\_text\\_") == "\\_text\\_"
    assert f("\\~text\\~") == "\\~text\\~"
    assert f("\\`text\\`") == "\\`text\\`"

    # Preserve an incomplete link as literal text.
    assert f("[text](<https://example.com/unterminated") == (
        "[text](<https://example.com/unterminated"
    )

    # Preserve unmatched markers in a complete body.
    assert f("**unterminated") == "**unterminated"
    assert f("**") == "**"

    # User-provided Private Use text must not collide with placeholders.
    marker = chr(0xE000)
    attack = f"before {marker}0{marker} after"
    assert f(attack) == attack
    assert f(f"*bold* {attack}") == f"_bold_ {attack}"

    # Merge the title as a heading before Chat dialect conversion.
    aobj = Apprise()
    assert aobj.add("gchat://workspace/key/token")
    assert (
        bool(
            aobj.notify(
                body="<b>hello</b>",
                title="My Title",
                body_format=NotifyFormat.HTML,
            )
        )
        is True
    )
    payload = loads(mock_post.call_args_list[-1][1]["data"])
    assert payload["text"] == "# My Title\n*hello*"
    mock_post.reset_mock()

    # Title that reduces to an empty string after stripping leading heading
    # and list characters (html_to_markdown converts "  - " to "-").
    # The heading is skipped and the title field is cleared regardless.
    assert (
        bool(
            aobj.notify(
                body="<b>hello</b>",
                title="  - ",
                body_format=NotifyFormat.HTML,
            )
        )
        is True
    )
    payload = loads(mock_post.call_args_list[-1][1]["data"])
    assert payload["text"] == "*hello*"


@mock.patch("requests.post")
def test_plugin_google_chat_markdown_dialect_conversion(
    mock_post,
):
    """Declared Markdown gets Google Chat dialect completion."""

    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok
    mock_post.return_value.content = b"{}"

    aobj = Apprise()
    assert aobj.add("gchat://workspace/key/token")

    assert (
        bool(
            aobj.notify(
                body="*bold* [click here](<https://example.com/x>)",
                body_format=NotifyFormat.MARKDOWN,
            )
        )
        is True
    )
    payload = loads(mock_post.call_args_list[-1][1]["data"])
    assert payload["text"] == "_bold_ <https://example.com/x|click here>"
    mock_post.reset_mock()

    # Directly verify the hook leaves unsupported formats unchanged.
    inst = aobj[0]
    body = "*bold*"
    assert inst.dialect_convert(body, NotifyFormat.HTML) == body


def test_plugin_google_chat_bare_link_and_autolink_dialect():
    """Bare-paren links and standalone autolinks convert safely."""

    # Bare destinations convert without treating URL punctuation as emphasis.
    assert (
        NotifyGoogleChat._commonmark_to_google_chat(
            "[click here](https://a*b)"
        )
        == "<https://a*b|click here>"
    )

    # Complete autolinks become Chat's unlabeled anchors.
    assert (
        NotifyGoogleChat._commonmark_to_google_chat("see <https://a*b> now")
        == "see <https://a*b> now"
    )

    # A "<" that never forms a valid scheme is passed through literally.
    assert NotifyGoogleChat._commonmark_to_google_chat("a < b") == "a < b"


@mock.patch("requests.post")
def test_plugin_google_chat_dialect_overflow(mock_post):
    """Apply the selected overflow mode after Chat escaping expands text."""

    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok
    mock_post.return_value.content = b"{}"
    mock_post.return_value.text = "{}"

    def notify(overflow):
        aobj = Apprise()
        assert aobj.add(f"gchat://workspace/key/token?overflow={overflow}")
        # Entity escaping makes this body exceed the post-conversion limit.
        assert aobj.notify(
            body="& " * 10000, body_format=NotifyFormat.MARKDOWN
        )
        texts = [loads(c[1]["data"])["text"] for c in mock_post.call_args_list]
        mock_post.reset_mock()
        return texts

    # UPSTREAM: exactly one message, sent oversized rather than split.
    texts = notify("upstream")
    assert len(texts) == 1
    assert len(texts[0]) > NotifyGoogleChat.body_maxlen

    # TRUNCATE: exactly one message, clipped to fit.
    texts = notify("truncate")
    assert len(texts) == 1
    assert len(texts[0]) <= NotifyGoogleChat.body_maxlen

    # SPLIT: as many messages as needed, each one within the limit.
    texts = notify("split")
    assert len(texts) > 1
    for text in texts:
        assert len(text) <= NotifyGoogleChat.body_maxlen
