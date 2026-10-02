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

from inspect import cleandoc
from json import loads

# Disable logging for a cleaner testing output
import logging
import os
from timeit import default_timer
from unittest import mock

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise, AppriseAttachment, NotifyType
from apprise.config import ConfigBase
from apprise.exception import AppriseImproperlyConfigured
from apprise.plugins.base import NotifyFormat
from apprise.plugins.signal_api import NotifySignalAPI

logging.disable(logging.CRITICAL)

# Attachment Directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), "var")


@pytest.fixture
def request_mock(mocker):
    """Prepare requests mock."""
    mock_post = mocker.patch("requests.post")
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok
    mock_post.return_value.content = ""
    return mock_post


# Our Testing URLs
apprise_url_tests = (
    (
        "signal://",
        {
            # No host specified
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "signal://:@/",
        {
            # invalid host
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "signal://localhost",
        {
            # Just a host provided
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "signal://localhost",
        {
            # key and secret provided and from but invalid from no
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "signal://localhost/123",
        {
            # invalid from phone
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "signal://localhost/{}/123/".format("1" * 11),
        {
            # invalid 'to' phone number
            "instance": NotifySignalAPI,
            # Notify will fail because it couldn't send to anyone
            "response": False,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "signal://localhost/+{}/123".format("1" * 11),
        },
    ),
    (
        "signal://localhost:8080/{}/".format("1" * 11),
        {
            # one phone number will notify ourselves
            "instance": NotifySignalAPI,
        },
    ),
    (
        "signal://localhost:8082/+{}/@group.abcd/".format("2" * 11),
        {
            # a valid group
            "instance": NotifySignalAPI,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "signal://localhost:8082/+{}/@abcd".format(
                "2" * 11
            ),
        },
    ),
    (
        "signals://localhost/{}/{}?format=markdown".format("1" * 11, "3" * 11),
        {
            # Test our markdown flag
            "instance": NotifySignalAPI,
        },
    ),
    (
        "signal://localhost:8080/+{}/group.abcd/".format("1" * 11),
        {
            # another valid group (without @ symbol)
            "instance": NotifySignalAPI,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "signal://localhost:8080/+{}/@abcd".format(
                "1" * 11
            ),
        },
    ),
    (
        "signal://localhost:8080/?from={}&to={},{}".format(
            "1" * 11, "2" * 11, "3" * 11
        ),
        {
            # use get args to acomplish the same thing
            "instance": NotifySignalAPI,
        },
    ),
    (
        "signal://localhost:8080/?from={}&to={},{},{}".format(
            "1" * 11, "2" * 11, "3" * 11, "5" * 3
        ),
        {
            # 2 good targets and one invalid one
            "instance": NotifySignalAPI,
        },
    ),
    (
        "signal://localhost:8080/{}/{}/?from={}".format(
            "1" * 11, "2" * 11, "3" * 11
        ),
        {
            # If we have from= specified, then all elements take on the to=
            # value
            "instance": NotifySignalAPI,
        },
    ),
    (
        "signals://user@localhost/{}/{}".format("1" * 11, "3" * 11),
        {
            # use get args to acomplish the same thing (use source instead of
            # from)
            "instance": NotifySignalAPI,
            # Run through code with debug logging enabled
            "force_debug": True,
        },
    ),
    (
        "signals://user:password@localhost/{}/{}".format("1" * 11, "3" * 11),
        {
            # use get args to acomplish the same thing (use source instead of
            # from)
            "instance": NotifySignalAPI,
        },
    ),
    (
        "signals://user:password@localhost/{}/{}".format("1" * 11, "3" * 11),
        {
            "instance": NotifySignalAPI,
            # Test that a 201 response code is still accepted
            "requests_response_code": 201,
        },
    ),
    (
        "signals://localhost/{}/{}/{}?batch=True".format(
            "1" * 11, "3" * 11, "4" * 11
        ),
        {
            # test batch mode
            "instance": NotifySignalAPI,
        },
    ),
    (
        "signals://localhost/{}/{}/{}?status=True".format(
            "1" * 11, "3" * 11, "4" * 11
        ),
        {
            # test status switch
            "instance": NotifySignalAPI,
        },
    ),
    (
        "signal://localhost/{}/{}".format("1" * 11, "4" * 11),
        {
            "instance": NotifySignalAPI,
            # throw a bizarre code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "signal://localhost/{}/{}".format("1" * 11, "4" * 11),
        {
            "instance": NotifySignalAPI,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracefully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_signal_urls():
    """NotifySignalAPI() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


def test_plugin_signal_edge_cases(request_mock):
    """NotifySignalAPI() Edge Cases."""
    # Initialize some generic (but valid) tokens
    source = "+1 (555) 123-3456"
    target = "+1 (555) 987-5432"
    body = "test body"
    title = "My Title"

    # No apikey specified
    with pytest.raises(AppriseImproperlyConfigured):
        NotifySignalAPI(source=None)

    aobj = Apprise()
    assert aobj.add(f"signals://localhost:231/{source}/{target}")
    assert aobj.notify(title=title, body=body)

    assert request_mock.call_count == 1

    details = request_mock.call_args_list[0]
    assert details[0][0] == "https://localhost:231/v2/send"
    payload = loads(details[1]["data"])
    assert payload["message"] == "My Title\r\ntest body"

    # Reset our mock object
    request_mock.reset_mock()

    aobj = Apprise()
    assert aobj.add(
        f"signals://user@localhost:231/{source}/{target}?status=True"
    )
    assert aobj.notify(title=title, body=body)

    assert request_mock.call_count == 1

    details = request_mock.call_args_list[0]
    assert details[0][0] == "https://localhost:231/v2/send"
    payload = loads(details[1]["data"])
    # Status flag is set
    assert payload["message"] == "[i] My Title\r\ntest body"


def test_plugin_signal_yaml_config(request_mock):
    """NotifySignalAPI() YAML Configuration."""

    # Load our configuration
    result, _ = ConfigBase.config_parse_yaml(
        cleandoc("""
    urls:
      - signal://signal:8080/+1234567890:
         - to: +0987654321
           tag: signal
    """)
    )

    # Verify we loaded correctly
    assert isinstance(result, list)
    assert len(result) == 1
    assert len(result[0].tags) == 1
    assert "signal" in result[0].tags

    # Let's get our plugin
    plugin = result[0]
    assert len(plugin.targets) == 1
    assert plugin.source == "+1234567890"
    assert "+0987654321" in plugin.targets

    #
    # Test another way to get the same results
    #

    # Load our configuration
    result, _config = ConfigBase.config_parse_yaml(
        cleandoc("""
    urls:
      - signal://signal:8080/+1234567890/+0987654321:
         - tag: signal
    """)
    )

    # Verify we loaded correctly
    assert isinstance(result, list)
    assert len(result) == 1
    assert len(result[0].tags) == 1
    assert "signal" in result[0].tags

    # Let's get our plugin
    plugin = result[0]
    assert len(plugin.targets) == 1
    assert plugin.source == "+1234567890"
    assert "+0987654321" in plugin.targets


def test_plugin_signal_based_on_feedback(request_mock):
    """NotifySignalAPI() User Feedback Test."""
    body = "test body"
    title = "My Title"

    aobj = Apprise()
    aobj.add(
        "signal://10.0.0.112:8080/+12512222222/+12513333333/"
        "12514444444?batch=yes"
    )

    assert aobj.notify(title=title, body=body)

    # If a batch, there is only 1 post
    assert request_mock.call_count == 1

    details = request_mock.call_args_list[0]
    assert details[0][0] == "http://10.0.0.112:8080/v2/send"
    payload = loads(details[1]["data"])
    assert payload["message"] == "My Title\r\ntest body"
    assert payload["number"] == "+12512222222"
    assert len(payload["recipients"]) == 2
    assert "+12513333333" in payload["recipients"]
    # The + is appended
    assert "+12514444444" in payload["recipients"]

    # Reset our test and turn batch mode off
    request_mock.reset_mock()

    aobj = Apprise()
    aobj.add(
        "signal://10.0.0.112:8080/+12512222222/+12513333333/"
        "12514444444?batch=no"
    )

    assert aobj.notify(title=title, body=body)

    # If a batch, there is only 1 post
    assert request_mock.call_count == 2

    details = request_mock.call_args_list[0]
    assert details[0][0] == "http://10.0.0.112:8080/v2/send"
    payload = loads(details[1]["data"])
    assert payload["message"] == "My Title\r\ntest body"
    assert payload["number"] == "+12512222222"
    assert len(payload["recipients"]) == 1
    assert "+12513333333" in payload["recipients"]

    details = request_mock.call_args_list[1]
    assert details[0][0] == "http://10.0.0.112:8080/v2/send"
    payload = loads(details[1]["data"])
    assert payload["message"] == "My Title\r\ntest body"
    assert payload["number"] == "+12512222222"
    assert len(payload["recipients"]) == 1

    # The + is appended
    assert "+12514444444" in payload["recipients"]

    request_mock.reset_mock()

    # Test group names
    aobj = Apprise()
    aobj.add(
        "signal://10.0.0.112:8080/+12513333333/@group1/@group2/"
        "12514444444?batch=yes"
    )

    assert aobj.notify(title=title, body=body)

    # If a batch, there is only 1 post
    assert request_mock.call_count == 1

    details = request_mock.call_args_list[0]
    assert details[0][0] == "http://10.0.0.112:8080/v2/send"
    payload = loads(details[1]["data"])
    assert payload["message"] == "My Title\r\ntest body"
    assert payload["number"] == "+12513333333"
    assert len(payload["recipients"]) == 3
    assert "+12514444444" in payload["recipients"]
    # our groups
    assert "group.group1" in payload["recipients"]
    assert "group.group2" in payload["recipients"]
    # Groups are stored properly
    assert "/@group1" in aobj[0].url()
    assert "/@group2" in aobj[0].url()
    # Our target phone number is also in the path
    assert "/+12514444444" in aobj[0].url()


def test_notify_signal_plugin_attachments(request_mock):
    """NotifySignalAPI() Attachments."""

    obj = Apprise.instantiate(
        "signal://10.0.0.112:8080/+12512222222/+12513333333/"
        "12514444444?batch=no"
    )
    assert isinstance(obj, NotifySignalAPI)

    # Test Valid Attachment
    path = os.path.join(TEST_VAR_DIR, "apprise-test.gif")
    attach = AppriseAttachment(path)
    assert (
        bool(
            obj.notify(
                body="body",
                title="title",
                notify_type=NotifyType.INFO,
                attach=attach,
            )
        )
        is True
    )

    # Test invalid attachment
    path = os.path.join(TEST_VAR_DIR, "/invalid/path/to/an/invalid/file.jpg")
    assert (
        bool(
            obj.notify(
                body="body",
                title="title",
                notify_type=NotifyType.INFO,
                attach=path,
            )
        )
        is False
    )

    # Test Valid Attachment (load 3)
    path = (
        os.path.join(TEST_VAR_DIR, "apprise-test.gif"),
        os.path.join(TEST_VAR_DIR, "apprise-test.gif"),
        os.path.join(TEST_VAR_DIR, "apprise-test.gif"),
    )
    attach = AppriseAttachment(path)

    # Return our good configuration
    with mock.patch("builtins.open", side_effect=OSError()):
        # We can't send the message we can't open the attachment for reading
        assert (
            bool(
                obj.notify(
                    body="body",
                    title="title",
                    notify_type=NotifyType.INFO,
                    attach=attach,
                )
            )
            is False
        )

    # test the handling of our batch modes
    obj = Apprise.instantiate(
        "signal://10.0.0.112:8080/+12512222222/+12513333333/"
        "12514444444?batch=yes"
    )
    assert isinstance(obj, NotifySignalAPI)

    # Now send an attachment normally without issues
    request_mock.reset_mock()
    assert (
        bool(
            obj.notify(
                body="body",
                title="title",
                notify_type=NotifyType.INFO,
                attach=attach,
            )
        )
        is True
    )
    assert request_mock.call_count == 1


def test_plugin_signal_text_mode_markdown_from_url(request_mock):
    """NotifySignalAPI() sets text_mode=styled when ?format=markdown"""
    source = "+1 (555) 123-3456"
    target = "+1 (555) 987-5432"
    body = "Body **bold** _italic_"
    title = "Title"

    aobj = Apprise()
    # Use URL path tokens, add the markdown format via query string
    assert aobj.add(
        f"signals://localhost:231/{source}/{target}?format=markdown"
    )
    assert aobj.notify(title=title, body=body)

    assert request_mock.call_count == 1
    details = request_mock.call_args_list[0]

    payload = loads(details[1]["data"])
    # Core behaviour we are validating
    assert payload.get("text_mode") == "styled"


def test_plugin_signal_text_mode_markdown_from_library(request_mock):
    """NotifySignalAPI() sets text_mode=styled when class format=MARKDOWN"""
    source = "+1 (555) 123-3456"
    target = "+1 (555) 987-5432"

    obj = NotifySignalAPI(
        host="localhost",
        port=231,
        secure=True,
        source=source,
        targets=[target],
        format=NotifyFormat.MARKDOWN,
    )

    assert (
        bool(obj.notify(title="Title", body="Body **bold** _italic_")) is True
    )

    assert request_mock.call_count == 1
    details = request_mock.call_args_list[0]

    payload = loads(details[1]["data"])
    # Core behaviour we are validating
    assert payload.get("text_mode") == "styled"


@pytest.mark.parametrize(
    "markdown,expected",
    [
        # Headings have no Signal syntax, so they become bold
        ("# Alert", "**Alert**"),
        # Emphasis maps onto Signal's star syntax
        ("**bold** *it* _it_ __bold__", "**bold** *it* *it* **bold**"),
        # Strikethrough uses a single tilde in Signal
        ("~~gone~~ ~also~", "~gone~ ~also~"),
        # Tildes that do not pair up stay literal
        ("~~~x~~~ a ~~b~ c~", "\\~\\~\\~x\\~\\~\\~ a \\~\\~b\\~ c\\~"),
        # A pair drops any opener of the other size found inside it
        ("~a ~~b a~ b~~", "~a \\~\\~b a~ b\\~\\~"),
        # CommonMark escapes are dropped unless Signal needs them
        ("a\\_b \\# 2\\*3 \\~ \\| \\&", "a_b # 2\\*3 \\~ \\| &"),
        # Unmatched stars are literal
        ("2*3", "2\\*3"),
        # A backslash before a line break is a hard break
        ("a\\\nb", "a\nb"),
        # Other backslashes are kept as-is
        ("C:\\temp x\\", "C:\\temp x\\"),
        # A literal backslash never escapes the markup after it
        ("\\\\**b**", "\\\u200b**b**"),
        # An escaped star is kept apart from the markup after it
        ("**\\*T\\***", "**\\*T\\*\u200b**"),
        # Nested emphasis closers are kept apart from each other
        ("***bi***", "*\u200b**bi**\u200b*"),
        # A literal star is kept apart from an opener in the same run
        ("**a*", "\\*\u200b*a*"),
        # Code spans keep their content literal
        ("`a*b` ``x`y``", "`a\\*b` `x\\`y`"),
        # Fenced code drops its language line
        ("```python\nx*y\n```", "`x\\*y`"),
        # An unmatched backtick stays literal
        ("a ` b", "a \\` b"),
        # Links become "label (url)"
        ("[lbl](<https://x.com/~u>)", "lbl (https://x.com/\\~u)"),
        ("[lbl](https://x.com/a\\_b)", "lbl (https://x.com/a_b)"),
        ("[](<https://x.com>)", "https://x.com"),
        # Broken link forms stay literal
        ("[a](<b", "[a](<b"),
        ("[a](b c", "[a](b c"),
        ("[a] (b)", "[a] (b)"),
        # Autolinks lose their brackets
        ("<https://a.b/c~d>", "https://a.b/c\\~d"),
        ("a < b", "a < b"),
        ("<https://a.b/~c", "<https://a.b/\\~c"),
        # A raw spoiler is Signal's own syntax and is kept
        ("||spoiler||", "||spoiler||"),
    ],
)
def test_plugin_signal_markdown_dialect(markdown, expected):
    """CommonMark is translated to Signal styled text."""
    assert NotifySignalAPI._commonmark_to_signal(markdown) == expected


def test_plugin_signal_styled_text(request_mock):
    """Declared content reaches Signal as styled text."""
    obj = Apprise.instantiate(
        "signal://localhost/+15551234567/+15557654321?format=markdown"
    )

    # Plain text stays literal in styled mode
    assert obj.notify(
        title="Build *failed*",
        body="my_app 2*3 ~user",
        body_format=NotifyFormat.TEXT,
    )
    payload = loads(request_mock.call_args_list[-1][1]["data"])
    assert payload["text_mode"] == "styled"
    assert payload["message"] == (
        "**Build \\*failed\\*\u200b**\nmy_app 2\\*3 \\~user"
    )

    # HTML is rendered with Signal's own markup
    assert obj.notify(
        body="<b>bold</b> <i>it</i> a_b",
        body_format=NotifyFormat.HTML,
    )
    payload = loads(request_mock.call_args_list[-1][1]["data"])
    assert payload["message"] == "**bold** *it* a_b"

    # Content with no declared format is passed through untouched
    assert obj.notify(body="**bold** a\\_b")
    payload = loads(request_mock.call_args_list[-1][1]["data"])
    assert payload["message"] == "**bold** a\\_b"

    # Plain text mode never sees Signal markup
    obj = Apprise.instantiate("signal://localhost/+15551234567/+15557654321")
    assert obj.notify(body="**bold**", body_format=NotifyFormat.MARKDOWN)
    payload = loads(request_mock.call_args_list[-1][1]["data"])
    assert payload["text_mode"] == "normal"
    assert payload["message"] == "**bold**"


def test_plugin_signal_unpaired_tildes_are_fast():
    """Many tildes that never pair up are handled quickly."""

    # Double tilde openers followed by single tilde closers
    start = default_timer()
    result = NotifySignalAPI._commonmark_to_signal(
        "~~a " * 25000 + "a~ " * 33333
    )
    elapsed = default_timer() - start
    assert result.count("~") == 25000 * 2 + 33333
    assert "~" not in result.replace("\\~", "")
    assert elapsed < 5.0

    # Single tilde openers followed by double tilde closers
    start = default_timer()
    result = NotifySignalAPI._commonmark_to_signal(
        "~a " * 33333 + "a~~ " * 25000
    )
    elapsed = default_timer() - start
    assert result.count("~") == 33333 + 25000 * 2
    assert "~" not in result.replace("\\~", "")
    assert elapsed < 5.0


@pytest.mark.parametrize(
    "markdown, expected",
    [
        # A backslash then digits before Signal markup stays literal text
        ("\\2~", "\\2\\~"),
        ("\\1~~", "\\1\\~\\~"),
        ("\\0*", "\\0\\*"),
        ("\\3_", "\\3_"),
        ("a\\12~b~", "a\\12~b~"),
        ("\\0~~a~~", "\\0~a~"),
        # Private-use characters already in the message are left alone
        ("\\2~", "\\2\\~"),
        ("\\0*", "\\0\\*"),
    ],
)
def test_plugin_signal_backslash_digits(markdown, expected):
    """Backslash and digit sequences never break Signal conversion."""
    assert NotifySignalAPI._commonmark_to_signal(markdown) == expected


def test_plugin_signal_backslash_markers_stay_small():
    """Many backslashes never make Signal conversion slow or large."""
    # Every Private Use character is taken
    every = "".join(
        chr(c)
        for start, end in (
            (0xE000, 0xF8FF),
            (0xF0000, 0xFFFFD),
            (0x100000, 0x10FFFD),
        )
        for c in range(start, end + 1)
    )

    # Taken characters, a long run of the first one, and both together,
    # each followed by many backslashes before markup
    for prefix in (every, chr(0xE000) * 20000, every + chr(0xE000) * 20000):
        body = prefix + "\\2~" * 20000
        start = default_timer()
        result = NotifySignalAPI._commonmark_to_signal(body)
        assert default_timer() - start < 5.0
        assert result == prefix + "\\2\\~" * 20000
