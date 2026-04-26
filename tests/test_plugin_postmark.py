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
import logging
import os
from unittest import mock

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise, AppriseAttachment, NotifyType
from apprise.plugins.postmark import NotifyPostmark

logging.disable(logging.CRITICAL)

# Attachment Directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), "var")

# Our Testing URLs
apprise_url_tests = (
    (
        "postmark://",
        {
            # No credentials
            "instance": TypeError,
        },
    ),
    (
        "postmark://:@/",
        {
            # Empty credentials
            "instance": TypeError,
        },
    ),
    (
        "postmark://abcd",
        {
            # API key only, no from email
            "instance": TypeError,
        },
    ),
    (
        "postmark://abcd@host",
        {
            # API key only, no from email
            "instance": TypeError,
        },
    ),
    (
        "postmark://abcd:user@example.com",
        {
            # No targets; defaults to from address
            "instance": NotifyPostmark,
        },
    ),
    (
        "postmark://abcd:user@example.com?format=text",
        {
            # Text format override
            "instance": NotifyPostmark,
        },
    ),
    (
        "postmark://abcd:user@example.com/newuser1@example.com",
        {
            # A good email with explicit target
            "instance": NotifyPostmark,
            "force_debug": True,
        },
    ),
    (
        "postmark://abcd:user@example.com/newuser2@example.com?name=John",
        {
            # With From display name
            "instance": NotifyPostmark,
            "privacy_url": (
                "postmark://a...d:user@example.com/newuser2@example.com"
            ),
            "url_matches": r"name=John",
        },
    ),
    (
        (
            "postmark://abcd:user@example.com/newuser3@example.com"
            "?reply=reply@example.com"
        ),
        {
            # With Reply-To
            "instance": NotifyPostmark,
            "url_matches": r"reply=",
        },
    ),
    (
        (
            "postmark://abcd:user@example.com/newuser4@example.com"
            "?bcc=bcc@nuxref.com"
        ),
        {
            # With Blind Carbon Copy
            "instance": NotifyPostmark,
        },
    ),
    (
        (
            "postmark://abcd:user@example.com/newuser5@example.com"
            "?cc=cc@nuxref.com"
        ),
        {
            # With Carbon Copy
            "instance": NotifyPostmark,
        },
    ),
    (
        (
            "postmark://abcd:user@example.com/newuser5@example.com"
            "?cc=Chris<cc@nuxref.com>"
        ),
        {
            # With named Carbon Copy
            "instance": NotifyPostmark,
        },
    ),
    (
        (
            "postmark://abcd:user@example.com/newuser6@example.com"
            "?to=extra@nuxref.com"
        ),
        {
            # Via ?to= for additional targets
            "instance": NotifyPostmark,
        },
    ),
    (
        "postmark://abcd:user@example.com/bademailaddress",
        {
            # Invalid target dropped; no valid recipients -- fails to send
            "instance": NotifyPostmark,
            "notify_response": False,
        },
    ),
    (
        "postmark://abcd:user@example.ca/newuser@example.ca",
        {
            "instance": NotifyPostmark,
            # force a failure
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "postmark://abcd:user@example.uk/newuser@example.uk",
        {
            "instance": NotifyPostmark,
            # throw a bizarre code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "postmark://abcd:user@example.au/newuser@example.au",
        {
            "instance": NotifyPostmark,
            # Throws a series of connection exceptions with this flag
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_postmark_urls():
    """NotifyPostmark() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.get")
@mock.patch("requests.post")
def test_plugin_postmark_edge_cases(mock_post, mock_get):
    """NotifyPostmark() Edge Cases."""

    # No API key
    with pytest.raises(TypeError):
        NotifyPostmark(apikey=None, from_email="user@example.com")

    # Invalid from email
    with pytest.raises(TypeError):
        NotifyPostmark(apikey="abcd", from_email="!invalid")

    # No from email (None)
    with pytest.raises(TypeError):
        NotifyPostmark(apikey="abcd", from_email=None)

    # Invalid target email -- plugin loads but target is dropped
    obj = NotifyPostmark(
        apikey="abcd",
        from_email="user@example.com",
        targets="!invalid",
    )
    # All targets dropped -> send() returns False
    assert isinstance(obj, NotifyPostmark)

    # Test invalid bcc/cc entries mixed with valid ones
    assert isinstance(
        NotifyPostmark(
            apikey="abcd",
            from_email="l2g@example.com",
            bcc=("abc@def.com", "!invalid"),
            cc=("abc@test.org", "!invalid"),
        ),
        NotifyPostmark,
    )

    # Test invalid reply_to entries mixed with valid ones
    assert isinstance(
        NotifyPostmark(
            apikey="abcd",
            from_email="l2g@example.com",
            reply_to=("reply@def.com", "!invalid"),
        ),
        NotifyPostmark,
    )


@mock.patch("requests.get")
@mock.patch("requests.post")
def test_plugin_postmark_send(mock_post, mock_get):
    """NotifyPostmark() Send."""

    def _mk_resp(code=requests.codes.ok):
        r = mock.Mock()
        r.status_code = code
        r.content = b""
        return r

    mock_post.return_value = _mk_resp()
    mock_get.return_value = _mk_resp()

    # Basic send to self (no explicit target)
    obj = Apprise.instantiate("postmark://abcd:user@example.com")
    assert isinstance(obj, NotifyPostmark)
    assert obj.notify(body="body", title="title") is True

    # Verify the X-Postmark-Server-Token header was set
    assert mock_post.call_count == 1
    call_kwargs = mock_post.call_args
    import json

    posted = json.loads(call_kwargs[1]["data"])
    assert posted["To"] == "user@example.com"
    assert "X-Postmark-Server-Token" in call_kwargs[1]["headers"]

    mock_post.reset_mock()

    # Send with an explicit target
    obj = Apprise.instantiate(
        "postmark://abcd:user@example.com/target@example.com"
    )
    assert obj.notify(body="body", title="title") is True
    posted = json.loads(mock_post.call_args[1]["data"])
    assert posted["To"] == "target@example.com"
    mock_post.reset_mock()

    # Send with cc and bcc
    obj = NotifyPostmark(
        apikey="abcd",
        from_email="user@example.com",
        targets=["target@example.com"],
        cc=["cc@example.com"],
        bcc=["bcc@example.com"],
    )
    assert obj.notify(body="body", title="title") is True
    posted = json.loads(mock_post.call_args[1]["data"])
    assert "Cc" in posted
    assert "Bcc" in posted
    mock_post.reset_mock()

    # Send with reply_to
    obj = NotifyPostmark(
        apikey="abcd",
        from_email="user@example.com",
        reply_to=["reply@example.com"],
    )
    assert obj.notify(body="body", title="title") is True
    posted = json.loads(mock_post.call_args[1]["data"])
    assert "ReplyTo" in posted
    mock_post.reset_mock()

    # Empty title falls back to default_empty_subject
    obj = NotifyPostmark(
        apikey="abcd",
        from_email="user@example.com",
    )
    assert obj.notify(body="body", title="") is True
    posted = json.loads(mock_post.call_args[1]["data"])
    assert posted["Subject"] == NotifyPostmark.default_empty_subject
    mock_post.reset_mock()

    # Text format
    obj = NotifyPostmark(
        apikey="abcd",
        from_email="user@example.com",
    )
    from apprise.common import NotifyFormat

    obj.notify_format = NotifyFormat.TEXT
    assert obj.notify(body="body", title="title") is True
    posted = json.loads(mock_post.call_args[1]["data"])
    assert "TextBody" in posted
    assert "HtmlBody" not in posted
    mock_post.reset_mock()

    # HTTP error response
    mock_post.return_value = _mk_resp(requests.codes.internal_server_error)
    obj = Apprise.instantiate(
        "postmark://abcd:user@example.com/target@example.com"
    )
    assert obj.notify(body="body", title="title") is False
    mock_post.reset_mock()

    # Unknown HTTP code
    mock_post.return_value = _mk_resp(999)
    assert obj.notify(body="body", title="title") is False
    mock_post.reset_mock()

    # RequestException
    mock_post.side_effect = requests.RequestException("Connection failed")
    assert obj.notify(body="body", title="title") is False
    mock_post.side_effect = None
    mock_post.reset_mock()

    # No valid targets -> False without any HTTP call
    obj = NotifyPostmark(
        apikey="abcd",
        from_email="user@example.com",
        targets=["!invalid"],
    )
    mock_post.return_value = _mk_resp()
    assert obj.notify(body="body", title="title") is False
    assert mock_post.call_count == 0

    # Multiple targets -- partial failure
    mock_post.reset_mock()
    responses = [_mk_resp(), _mk_resp(requests.codes.bad_request)]
    mock_post.side_effect = responses
    obj = NotifyPostmark(
        apikey="abcd",
        from_email="user@example.com",
        targets=["t1@example.com", "t2@example.com"],
    )
    assert obj.notify(body="body", title="title") is False
    assert mock_post.call_count == 2
    mock_post.side_effect = None


@mock.patch("requests.post")
def test_plugin_postmark_attachments(mock_post):
    """NotifyPostmark() Attachments."""

    def _mk_resp(code=requests.codes.ok):
        r = mock.Mock()
        r.status_code = code
        r.content = b""
        return r

    mock_post.return_value = _mk_resp()

    # Single attachment success
    path = os.path.join(TEST_VAR_DIR, "apprise-test.gif")
    attach = AppriseAttachment(path)
    obj = Apprise.instantiate("postmark://abcd:user@example.com")
    assert isinstance(obj, NotifyPostmark)
    assert (
        obj.notify(
            body="body",
            title="title",
            notify_type=NotifyType.INFO,
            attach=attach,
        )
        is True
    )

    import json

    posted = json.loads(mock_post.call_args[1]["data"])
    assert "Attachments" in posted
    assert len(posted["Attachments"]) == 1
    assert posted["Attachments"][0]["Name"] == "apprise-test.gif"
    mock_post.reset_mock()

    # Multiple attachments
    attach = AppriseAttachment(os.path.join(TEST_VAR_DIR, "apprise-test.gif"))
    attach.add(os.path.join(TEST_VAR_DIR, "apprise-test.png"))
    assert (
        obj.notify(
            body="body",
            title="title",
            notify_type=NotifyType.INFO,
            attach=attach,
        )
        is True
    )
    posted = json.loads(mock_post.call_args[1]["data"])
    assert len(posted["Attachments"]) == 2
    mock_post.reset_mock()

    # Attachment inaccessible (file not found)
    with mock.patch("os.path.isfile", return_value=False):
        assert (
            obj.notify(
                body="body",
                title="title",
                notify_type=NotifyType.INFO,
                attach=AppriseAttachment(
                    os.path.join(TEST_VAR_DIR, "apprise-test.gif")
                ),
            )
            is False
        )

    # Attachment read error (OSError)
    with mock.patch("builtins.open", side_effect=OSError):
        assert (
            obj.notify(
                body="body",
                title="title",
                notify_type=NotifyType.INFO,
                attach=AppriseAttachment(
                    os.path.join(TEST_VAR_DIR, "apprise-test.gif")
                ),
            )
            is False
        )


@mock.patch("requests.post")
def test_plugin_postmark_url_parsing(mock_post):
    """NotifyPostmark() URL parsing and round-trip."""

    def _mk_resp(code=requests.codes.ok):
        r = mock.Mock()
        r.status_code = code
        r.content = b""
        return r

    mock_post.return_value = _mk_resp()

    # Basic round-trip
    obj = NotifyPostmark(
        apikey="mytoken",
        from_email="user@example.com",
    )
    url = obj.url()
    result = NotifyPostmark.parse_url(url)
    assert result is not None
    obj2 = NotifyPostmark(**result)
    assert obj.url_identifier == obj2.url_identifier

    # With explicit target
    obj = NotifyPostmark(
        apikey="mytoken",
        from_email="user@example.com",
        targets=["target@example.com"],
    )
    url = obj.url()
    result = NotifyPostmark.parse_url(url)
    assert result is not None
    obj2 = NotifyPostmark(**result)
    assert len(obj.targets) == len(obj2.targets)

    # With from_name
    obj = NotifyPostmark(
        apikey="mytoken",
        from_email="user@example.com",
        from_name="Alice",
    )
    url = obj.url()
    assert "name=Alice" in url
    result = NotifyPostmark.parse_url(url)
    assert result is not None
    obj2 = NotifyPostmark(**result)
    assert obj2.from_addr[0] == "Alice"

    # With bcc and cc
    obj = NotifyPostmark(
        apikey="mytoken",
        from_email="user@example.com",
        targets=["target@example.com"],
        cc=["cc@example.com"],
        bcc=["bcc@example.com"],
    )
    url = obj.url()
    result = NotifyPostmark.parse_url(url)
    assert result is not None
    obj2 = NotifyPostmark(**result)
    assert "cc@example.com" in obj2.cc
    assert "bcc@example.com" in obj2.bcc

    # With reply_to
    obj = NotifyPostmark(
        apikey="mytoken",
        from_email="user@example.com",
        reply_to=["reply@example.com"],
    )
    url = obj.url()
    result = NotifyPostmark.parse_url(url)
    assert result is not None
    obj2 = NotifyPostmark(**result)
    assert "reply@example.com" in obj2.reply_to

    # parse_url returns None for completely unparseable input
    assert NotifyPostmark.parse_url(None) is None

    # ?apikey= override
    result = NotifyPostmark.parse_url(
        "postmark://?apikey=overridekey&from=sender@example.com"
        "&to=target@example.com"
    )
    assert result is not None
    assert result["apikey"] == "overridekey"

    # ?from= override (from address via query param)
    result = NotifyPostmark.parse_url(
        "postmark://tok@example.com/path@example.com?from=sender@example.com"
    )
    assert result is not None
    assert result["from_email"] == "sender@example.com"

    # privacy_url hides the API key
    obj = NotifyPostmark(
        apikey="secrettoken",
        from_email="user@example.com",
    )
    privacy = obj.url(privacy=True)
    assert "secrettoken" not in privacy
    assert "s...n" in privacy or "..." in privacy

    # __len__
    obj = NotifyPostmark(
        apikey="mytoken",
        from_email="user@example.com",
        targets=["a@example.com", "b@example.com"],
    )
    assert len(obj) == 2

    # url_identifier
    obj1 = NotifyPostmark(
        apikey="tok",
        from_email="user@example.com",
    )
    obj2 = NotifyPostmark(
        apikey="tok",
        from_email="user@example.com",
        targets=["other@example.com"],
    )
    assert obj1.url_identifier == obj2.url_identifier
