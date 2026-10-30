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
import os
import time
from unittest import mock
from urllib.parse import urlparse

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise, AppriseAttachment, NotifyFormat
from apprise.conversion import MAX_LINK_DEPTH
from apprise.exception import AppriseImproperlyConfigured
from apprise.plugins.whapi import NotifyWhapi

logging.disable(logging.CRITICAL)

# Attachment Directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), "var")

# A realistic Channel token
TOKEN = "AbCdEf0123456789AbCdEf0123456789"

# A group ID as Whapi.Cloud reports it
GROUP = "120363042829563251"

# A successful Whapi.Cloud response
OK_RESPONSE = dumps(
    {"sent": True, "message": {"id": "PsobWy36679._7w-wKmB9tMeGQ"}}
).encode("utf-8")

# Our Testing URLs
apprise_url_tests = (
    (
        "whapi://",
        {
            # Nothing specified
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "whapi://%20/15551234567",
        {
            # An invalid token
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        f"whapi://{TOKEN}/",
        {
            # No targets; we load but have nothing to notify
            "instance": NotifyWhapi,
            "notify_response": False,
        },
    ),
    (
        f"whapi://{TOKEN}/15551234567",
        {
            "instance": NotifyWhapi,
            "requests_response_text": OK_RESPONSE,
            # Our expected url(privacy=True) startswith() response
            "privacy_url": "whapi://A...9/15551234567",
        },
    ),
    (
        f"whapi://{TOKEN}/15551234567/{GROUP}/abc@newsletter?preview=no",
        {
            # A phone, a group and a WhatsApp Channel
            "instance": NotifyWhapi,
            "requests_response_text": OK_RESPONSE,
            "privacy_url": f"whapi://A...9/15551234567/{GROUP}@g.us/"
            "abc@newsletter?preview=no",
        },
    ),
    (
        f"whapi://?token={TOKEN}&to=15551234567,{GROUP}",
        {
            # Everything given as arguments
            "instance": NotifyWhapi,
            "requests_response_text": OK_RESPONSE,
            "privacy_url": f"whapi://A...9/15551234567/{GROUP}@g.us",
        },
    ),
    (
        f"whapi://{TOKEN}/15551234567",
        {
            "instance": NotifyWhapi,
            # Throw a bizzare code forcing us to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        f"whapi://{TOKEN}/15551234567",
        {
            "instance": NotifyWhapi,
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        f"whapi://{TOKEN}/15551234567",
        {
            "instance": NotifyWhapi,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracefully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def _mk_resp(content=OK_RESPONSE, code=requests.codes.ok):
    """Return a mocked Whapi.Cloud response."""
    r = mock.Mock()
    r.status_code = code
    r.content = content
    return r


def test_plugin_whapi_urls():
    """Run the shared URL tests against Whapi.Cloud."""
    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


def test_plugin_whapi_targets():
    """Each kind of target is turned into the chat ID Whapi.Cloud wants."""
    obj = NotifyWhapi(
        token=TOKEN,
        targets=[
            "+1 (555) 123-4567",
            GROUP,
            "#" + GROUP,
            "1234567890-1234567890",
            f"{GROUP}@g.us",
            "123456789@newsletter",
            "abc",
        ],
    )
    assert obj.targets == [
        "15551234567",
        f"{GROUP}@g.us",
        f"{GROUP}@g.us",
        "1234567890-1234567890@g.us",
        f"{GROUP}@g.us",
        "123456789@newsletter",
    ]
    assert obj.invalid_targets == ["abc"]
    assert len(obj) == 6

    # A group given with a leading # in ?to= loses its prefix cleanly
    obj = Apprise.instantiate(f"whapi://{TOKEN}?to=%23{GROUP}")
    assert obj.targets == [f"{GROUP}@g.us"]

    # No targets still counts as one notification
    assert len(NotifyWhapi(token=TOKEN)) == 1

    # A missing token is not accepted
    with pytest.raises(AppriseImproperlyConfigured):
        NotifyWhapi(token=None, targets="15551234567")


def test_plugin_whapi_round_trip():
    """A URL rebuilt from url() loads the same connection and targets."""
    obj1 = Apprise.instantiate(
        f"whapi://{TOKEN}/15551234567/{GROUP}/x@newsletter/bad?preview=no"
    )
    obj2 = Apprise.instantiate(obj1.url())

    assert obj1.url_identifier == obj2.url_identifier
    assert obj1.targets == obj2.targets
    assert obj1.invalid_targets == obj2.invalid_targets == ["bad"]
    assert obj2.preview is False

    # The default preview setting is not written out
    obj = Apprise.instantiate(f"whapi://{TOKEN}/15551234567?preview=yes")
    assert obj.preview is True
    assert "preview" not in obj.url()


@mock.patch("requests.post")
def test_plugin_whapi_text_payload(mock_post):
    """A text message carries our token, chat ID and WhatsApp formatting."""
    mock_post.return_value = _mk_resp()

    obj = Apprise.instantiate(f"whapi://{TOKEN}/15551234567?preview=no")
    assert (
        obj.notify(
            body="**bold** & <tag> _x_",
            title="A & B <c>",
            body_format=NotifyFormat.MARKDOWN,
        )
        is True
    )

    assert mock_post.call_count == 1
    url = mock_post.call_args[0][0]
    assert urlparse(url).hostname == "gate.whapi.cloud"
    assert urlparse(url).path == "/messages/text"

    headers = mock_post.call_args[1]["headers"]
    assert headers["Authorization"] == f"Bearer {TOKEN}"
    assert headers["Content-Type"] == "application/json"

    payload = loads(mock_post.call_args[1]["data"])
    assert payload["to"] == "15551234567"
    assert payload["no_link_preview"] is True
    # The title becomes a bold first line and markdown becomes WhatsApp's
    assert payload["body"] == "*A & B <c>*\n*bold* & <tag> _x_"

    # Plain text keeps every character exactly as typed
    mock_post.reset_mock()
    assert (
        obj.notify(body="1 * 2 _ 3 . 4 ! # <", body_format=NotifyFormat.TEXT)
        is True
    )
    payload = loads(mock_post.call_args[1]["data"])
    assert payload["body"] == "1 * 2 _ 3 . 4 ! # <"

    # Undeclared content is passed along untouched
    mock_post.reset_mock()
    obj = Apprise.instantiate(f"whapi://{TOKEN}/15551234567")
    assert obj.notify(body="**as is**", body_format=None) is True
    payload = loads(mock_post.call_args[1]["data"])
    assert payload["body"] == "**as is**"
    assert "no_link_preview" not in payload


@mock.patch("requests.post")
def test_plugin_whapi_responses(mock_post):
    """Whapi.Cloud error answers are reported as failures."""
    obj = Apprise.instantiate(f"whapi://{TOKEN}/15551234567")

    # A 200 that says nothing was sent
    mock_post.return_value = _mk_resp(dumps({"sent": False}).encode())
    assert obj.notify(body="test") is False

    # An error with Whapi.Cloud's own explanation
    mock_post.return_value = _mk_resp(
        dumps({"error": {"code": 401, "message": "Unauthorized"}}).encode(),
        code=401,
    )
    assert obj.notify(body="test") is False

    # An error with an unexpected shape
    mock_post.return_value = _mk_resp(
        dumps({"error": "nope"}).encode(), code=402
    )
    assert obj.notify(body="test") is False

    # A 2xx answer only counts when it confirms the message was sent
    for content in (b"", b"<html></html>", b"[]", b"{}"):
        mock_post.return_value = _mk_resp(content)
        assert obj.notify(body="test") is False

    # Any 2xx code is accepted when the message was sent
    mock_post.return_value = _mk_resp(code=requests.codes.created)
    assert obj.notify(body="test") is True


def test_plugin_whapi_deeply_nested_links():
    """Deeply nested link labels convert quickly and keep their text."""
    depth = 20000
    body = "[" * depth + "x" + "](u)" * depth

    start = time.monotonic()
    result = NotifyWhapi._commonmark_to_whatsapp(body)
    assert time.monotonic() - start < 5

    # The innermost links still convert; the extra brackets stay as text
    assert result.startswith("[" * (depth - MAX_LINK_DEPTH))
    assert "x (u)" in result


@mock.patch("requests.post")
def test_plugin_whapi_partial_failure(mock_post):
    """One failing target does not stop the others."""
    mock_post.side_effect = [
        _mk_resp(code=500),
        _mk_resp(),
    ]
    obj = Apprise.instantiate(f"whapi://{TOKEN}/15551234567/{GROUP}")
    assert obj.notify(body="test") is False
    assert mock_post.call_count == 2
    assert (
        loads(mock_post.call_args_list[1][1]["data"])["to"] == f"{GROUP}@g.us"
    )


@mock.patch("requests.post")
def test_plugin_whapi_attachments(mock_post):
    """Files are posted raw to the media call matching their type."""
    mock_post.return_value = _mk_resp()

    attach = AppriseAttachment(
        [
            os.path.join(TEST_VAR_DIR, "apprise-test.png"),
            os.path.join(TEST_VAR_DIR, "apprise-test.mp4"),
            os.path.join(TEST_VAR_DIR, "apprise-test.gif"),
        ]
    )
    obj = Apprise.instantiate(f"whapi://{TOKEN}/15551234567")
    assert obj.notify(body="test", attach=attach) is True

    # Our text, then one call per file
    assert mock_post.call_count == 4
    calls = mock_post.call_args_list
    paths = [urlparse(c[0][0]).path for c in calls]
    assert paths == [
        "/messages/text",
        "/messages/media/image",
        "/messages/media/video",
        "/messages/media/document",
    ]

    # Who the file goes to travels in the query string
    assert calls[1][1]["params"] == {"to": "15551234567"}
    assert calls[1][1]["headers"]["Content-Type"] == "image/png"
    assert calls[1][1]["headers"]["Authorization"] == f"Bearer {TOKEN}"

    # A document keeps its file name
    assert calls[3][1]["params"] == {
        "to": "15551234567",
        "filename": "apprise-test.gif",
    }

    # An audio file is sent as audio
    mock_post.reset_mock()
    with mock.patch(
        "apprise.attachment.base.AttachBase.mimetype",
        new_callable=mock.PropertyMock,
        return_value="audio/mpeg",
    ):
        assert obj.notify(body="test", attach=attach[0]) is True
    assert urlparse(mock_post.call_args[0][0]).path == "/messages/media/audio"

    # Attachments alone send no text
    mock_post.reset_mock()
    assert obj.notify(body="", attach=attach[0]) is True
    assert mock_post.call_count == 1
    assert urlparse(mock_post.call_args[0][0]).path == "/messages/media/image"


@mock.patch("requests.post")
def test_plugin_whapi_attach_errors(mock_post):
    """A file that cannot be read or sent fails the notification."""
    mock_post.return_value = _mk_resp()
    path = os.path.join(TEST_VAR_DIR, "apprise-test.png")
    obj = Apprise.instantiate(f"whapi://{TOKEN}/15551234567")

    # An inaccessible file is never posted
    with mock.patch("os.path.isfile", return_value=False):
        assert obj.notify(body="", attach=AppriseAttachment(path)) is False
    assert mock_post.call_count == 0

    # A file that fails to open is never posted
    with mock.patch("builtins.open", side_effect=OSError):
        assert obj.notify(body="", attach=AppriseAttachment(path)) is False
    assert mock_post.call_count == 0

    # The media call is refused
    mock_post.return_value = _mk_resp(code=500)
    assert obj.notify(body="", attach=AppriseAttachment(path)) is False
    assert mock_post.call_count == 1

    # The media call raises a connection error
    mock_post.reset_mock()
    mock_post.side_effect = requests.RequestException("boom")
    assert obj.notify(body="", attach=AppriseAttachment(path)) is False
    assert mock_post.call_count == 1

    # A refused text message is not followed by its files
    mock_post.reset_mock()
    mock_post.side_effect = None
    mock_post.return_value = _mk_resp(code=500)
    assert obj.notify(body="test", attach=AppriseAttachment(path)) is False
    assert mock_post.call_count == 1

    # A file that was sent but fails to close still counts as sent
    mock_post.reset_mock()
    mock_post.return_value = _mk_resp()
    handle = mock.Mock()
    handle.close.side_effect = OSError("close failed")
    with mock.patch(
        "apprise.attachment.base.AttachBase.open", return_value=handle
    ):
        assert obj.notify(body="", attach=AppriseAttachment(path)) is True
    assert mock_post.call_count == 1
    handle.close.assert_called_once()


@mock.patch("requests.post")
def test_plugin_whapi_attach_retry(mock_post):
    """A retry sends only the file that failed, not the text again."""
    mock_post.side_effect = [
        _mk_resp(),
        _mk_resp(),
        _mk_resp(code=500),
        _mk_resp(),
    ]
    attach = [
        os.path.join(TEST_VAR_DIR, "apprise-test.png"),
        os.path.join(TEST_VAR_DIR, "apprise-test.gif"),
    ]

    aobj = Apprise()
    assert aobj.add(f"whapi://{TOKEN}/15551234567?retry=1&wait=0")
    with mock.patch("apprise.apprise.time.sleep"):
        assert bool(aobj.notify(body="test", attach=attach)) is True

    paths = [urlparse(c[0][0]).path for c in mock_post.call_args_list]
    assert paths == [
        "/messages/text",
        "/messages/media/image",
        "/messages/media/document",
        "/messages/media/document",
    ]


@mock.patch("requests.post")
def test_plugin_whapi_html_to_whatsapp(mock_post):
    """HTML is delivered in WhatsApp's own formatting."""
    mock_post.return_value = _mk_resp()
    obj = Apprise.instantiate(f"whapi://{TOKEN}/15551234567")

    def notify(body):
        """Send one HTML body and return the text Whapi.Cloud received."""
        assert obj.notify(body=body, body_format=NotifyFormat.HTML) is True
        return loads(mock_post.call_args[1]["data"])["body"]

    assert notify("<b>hello</b> <i>world</i>") == "*hello* _world_"
    assert notify("<code>inline</code>") == "```inline```"
    assert (
        notify('<a href="https://example.com/x">click here</a>')
        == "click here (https://example.com/x)"
    )
    assert notify("<p>literal * asterisk</p>") == "literal * asterisk"

    # Formats WhatsApp does not translate are left alone
    assert obj.dialect_convert("*bold*", NotifyFormat.HTML) == "*bold*"


def test_plugin_whapi_markdown_dialect():
    """CommonMark edge cases convert safely to WhatsApp formatting."""
    f = NotifyWhapi._commonmark_to_whatsapp

    # Headings become bold
    assert f("# Heading\nbody") == "*Heading*\nbody"

    # Unmatched and oversized backtick runs
    assert f("text ``unterminated") == "text ``unterminated"
    assert f("`` code```here ``") == "``` code``here ```"

    # Unmatched emphasis stays literal
    assert f("**unterminated") == "**unterminated"

    # Angle links, including escapes, empty labels and broken ones
    assert f("[click](<https://e/x\\>y>)") == "click (https://e/x>y)"
    assert f("[](<https://example.com/x>)") == "https://example.com/x"
    assert f("[text](<https://e/unterminated") == (
        "[text](<https://e/unterminated"
    )

    # Bare links, including broken ones
    assert f("[click here](https://a*b)") == "click here (https://a*b)"
    assert f("[label](has space)") == "[label](has space)"

    # A nested invalid link keeps the outer one working
    assert f("[OUTER [INNER](<bad)](https://e.com)") == (
        "OUTER [INNER](<bad) (https://e.com)"
    )

    # A stray "]" does not pair with a later, unrelated link
    assert f("[label] and ](https://e.com) end") == (
        "[label] and ](https://e.com) end"
    )

    # Autolinks lose their brackets; anything else stays literal
    assert f("see <https://a*b> now") == "see https://a*b now"
    assert f("a < b") == "a < b"
    assert f("see <https://a*b end") == "see <https://a*b end"
