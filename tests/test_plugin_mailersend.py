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
from apprise.plugins.mailersend import NotifyMailerSend

logging.disable(logging.CRITICAL)

# Attachment Directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), "var")

# A representative MailerSend API key
APIKEY = "mlsn.abc123def456abc123def456abc123def456"

# Our Testing URLs
apprise_url_tests = (
    (
        "mailersend://",
        {
            "instance": None,
        },
    ),
    (
        "mailersend://:@/",
        {
            "instance": None,
        },
    ),
    (
        # API key only, no from email
        "mailersend://abcd",
        {
            "instance": None,
        },
    ),
    (
        # host only, no user (API key)
        "mailersend://abcd@host",
        {
            "instance": None,
        },
    ),
    (
        # invalid API key (contains disallowed characters)
        "mailersend://bad+key*!:user@example.com",
        {
            "instance": TypeError,
        },
    ),
    (
        # No To/Target Address; use From address as default
        "mailersend://abcd:user@example.com",
        {
            "instance": NotifyMailerSend,
        },
    ),
    (
        # Single explicit To address
        "mailersend://abcd:user@example.com/newuser@example.com",
        {
            "instance": NotifyMailerSend,
            "privacy_url": (
                "mailersend://a...d:user@example.com/newuser@example.com"
            ),
        },
    ),
    (
        # Multiple To addresses in the URL path
        ("mailersend://abcd:user@example.com/one@example.com/two@example.com"),
        {
            "instance": NotifyMailerSend,
        },
    ),
    (
        # Extra To addresses via ?to=
        (
            "mailersend://abcd:user@example.com"
            "/one@example.com?to=two@example.com"
        ),
        {
            "instance": NotifyMailerSend,
        },
    ),
    (
        # Carbon Copy via ?cc=
        (
            "mailersend://abcd:user@example.com"
            "/newuser@example.com?cc=cc@nuxref.com"
        ),
        {
            "instance": NotifyMailerSend,
        },
    ),
    (
        # Blind Carbon Copy via ?bcc=
        (
            "mailersend://abcd:user@example.com"
            "/newuser@example.com?bcc=bcc@nuxref.com"
        ),
        {
            "instance": NotifyMailerSend,
        },
    ),
    (
        # Reply-To via ?reply=
        ("mailersend://abcd:user@example.com?reply=reply@example.com"),
        {
            "instance": NotifyMailerSend,
            "url_matches": r"reply=reply%40example.com",
        },
    ),
    (
        # Invalid Reply-To address
        ("mailersend://abcd:user@example.com/newuser@example.com?reply=%20!"),
        {
            "instance": TypeError,
        },
    ),
    (
        # Invalid To address is dropped but plugin still loads
        "mailersend://abcd:user@example.com/bademailaddress",
        {
            "instance": NotifyMailerSend,
            "notify_response": False,
        },
    ),
    (
        # Invalid CC and BCC (mixed with good ones)
        (
            "mailersend://abcd:user@example.com"
            "/newuser@example.com"
            "?cc=l2g@nuxref.com,!bad"
            "&bcc=l2g@nuxref.com,!bad"
        ),
        {
            "instance": NotifyMailerSend,
        },
    ),
    (
        # plain-text format
        "mailersend://abcd:user@example.com?format=text",
        {
            "instance": NotifyMailerSend,
        },
    ),
    (
        # Force debug output
        ("mailersend://abcd:user@example.com/newuser@example.com"),
        {
            "instance": NotifyMailerSend,
            "force_debug": True,
        },
    ),
    (
        # HTTP 500 from server
        "mailersend://abcd:user@example.ca/newuser@example.ca",
        {
            "instance": NotifyMailerSend,
            "response": False,
            "requests_response_code": (requests.codes.internal_server_error),
        },
    ),
    (
        # Unknown HTTP response code
        "mailersend://abcd:user@example.uk/newuser@example.uk",
        {
            "instance": NotifyMailerSend,
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        # RequestException
        "mailersend://abcd:user@example.au/newuser@example.au",
        {
            "instance": NotifyMailerSend,
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_mailersend_urls():
    """NotifyMailerSend() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.get")
@mock.patch("requests.post")
def test_plugin_mailersend_edge_cases(mock_post, mock_get):
    """NotifyMailerSend() Edge Cases."""

    # No API key
    with pytest.raises(TypeError):
        NotifyMailerSend(apikey=None, from_email="user@example.com")

    # Invalid API key
    with pytest.raises(TypeError):
        NotifyMailerSend(apikey="bad+key*!", from_email="user@example.com")

    # Invalid From email
    with pytest.raises(TypeError):
        NotifyMailerSend(apikey="abcd", from_email="!invalid")

    # No From email
    with pytest.raises(TypeError):
        NotifyMailerSend(apikey="abcd", from_email=None)

    # Invalid Reply-To email raises TypeError
    with pytest.raises(TypeError):
        NotifyMailerSend(
            apikey="abcd",
            from_email="user@example.com",
            reply_to="!invalid",
        )

    # Invalid To email is dropped; object still created
    obj = NotifyMailerSend(
        apikey="abcd",
        from_email="user@example.com",
        targets="!invalid",
    )
    # When all To addresses are invalid the targets list is empty, so
    # send() will return False
    assert isinstance(obj, NotifyMailerSend)

    # Mixed good and bad cc/bcc entries
    obj = NotifyMailerSend(
        apikey="abcd",
        from_email="l2g@example.com",
        bcc=("abc@def.com", "!invalid"),
        cc=("abc@test.org", "!invalid"),
    )
    assert isinstance(obj, NotifyMailerSend)


@mock.patch("requests.get")
@mock.patch("requests.post")
def test_plugin_mailersend_send(mock_post, mock_get):
    """NotifyMailerSend() send logic."""

    def _mk_resp(code=requests.codes.accepted):
        r = mock.Mock()
        r.status_code = code
        r.content = b""
        return r

    mock_post.return_value = _mk_resp()
    mock_get.return_value = _mk_resp()

    # Single target -- success
    obj = Apprise.instantiate(
        "mailersend://abcd:user@example.com/to@example.com"
    )
    assert isinstance(obj, NotifyMailerSend)
    assert bool(obj.notify(body="body", title="title")) is True
    assert mock_post.call_count == 1

    mock_post.reset_mock()

    # Multiple targets -- all succeed
    obj = NotifyMailerSend(
        apikey="abcd",
        from_email="user@example.com",
        targets=["t1@example.com", "t2@example.com"],
    )
    assert bool(obj.notify(body="body")) is True
    assert mock_post.call_count == 2

    mock_post.reset_mock()

    # No targets -- send returns False without any HTTP call
    obj = NotifyMailerSend(
        apikey="abcd",
        from_email="user@example.com",
        targets=["!invalid"],
    )
    assert bool(obj.notify(body="body")) is False
    assert mock_post.call_count == 0

    mock_post.reset_mock()

    # HTTP error on one of two targets -- partial failure
    mock_post.side_effect = [
        _mk_resp(requests.codes.accepted),
        _mk_resp(requests.codes.internal_server_error),
    ]
    obj = NotifyMailerSend(
        apikey="abcd",
        from_email="user@example.com",
        targets=["t1@example.com", "t2@example.com"],
    )
    assert bool(obj.notify(body="body")) is False

    mock_post.reset_mock()
    mock_post.side_effect = None

    # RequestException -- marks failure
    mock_post.side_effect = requests.RequestException("boom")
    obj = Apprise.instantiate(
        "mailersend://abcd:user@example.com/to@example.com"
    )
    assert bool(obj.notify(body="body")) is False

    mock_post.side_effect = None

    # CC and BCC are excluded from the To list de-duplication
    mock_post.return_value = _mk_resp()
    obj = NotifyMailerSend(
        apikey="abcd",
        from_email="user@example.com",
        targets=["to@example.com"],
        cc=["cc@example.com", "to@example.com"],
        bcc=["bcc@example.com", "to@example.com"],
        reply_to="reply@example.com",
    )
    assert bool(obj.notify(body="body")) is True
    call_payload = mock_post.call_args
    assert call_payload is not None

    # text format triggers html conversion
    mock_post.reset_mock()
    mock_post.return_value = _mk_resp()
    obj = Apprise.instantiate(
        "mailersend://abcd:user@example.com/to@example.com?format=text"
    )
    assert bool(obj.notify(body="<p>body</p>")) is True

    # unknown response code (not 202) is treated as failure
    mock_post.reset_mock()
    mock_post.return_value = _mk_resp(999)
    obj = Apprise.instantiate(
        "mailersend://abcd:user@example.com/to@example.com"
    )
    assert bool(obj.notify(body="body")) is False


@mock.patch("requests.post")
def test_plugin_mailersend_attachments(mock_post):
    """NotifyMailerSend() Attachment handling."""

    def _mk_resp(code=requests.codes.accepted):
        r = mock.Mock()
        r.status_code = code
        r.content = b""
        return r

    mock_post.return_value = _mk_resp()

    # Success -- valid attachment
    path = os.path.join(TEST_VAR_DIR, "apprise-test.gif")
    attach = AppriseAttachment(path)
    obj = Apprise.instantiate(
        "mailersend://abcd:user@example.com/to@example.com"
    )
    assert isinstance(obj, NotifyMailerSend)
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

    mock_post.reset_mock()

    # Inaccessible file -- os.path.isfile returns False
    with mock.patch("os.path.isfile", return_value=False):
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

    mock_post.reset_mock()

    # OSError on open
    with mock.patch("builtins.open", side_effect=OSError):
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

    mock_post.reset_mock()

    # HTTP error after successful open
    mock_post.return_value = _mk_resp(requests.codes.internal_server_error)
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

    mock_post.reset_mock()

    # RequestException after successful open
    mock_post.side_effect = requests.RequestException("boom")
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

    mock_post.side_effect = None

    # Multiple attachments -- all succeed
    mock_post.return_value = _mk_resp()
    paths = [
        os.path.join(TEST_VAR_DIR, "apprise-test.gif"),
        os.path.join(TEST_VAR_DIR, "apprise-test.png"),
    ]
    multi_attach = AppriseAttachment(paths)
    assert (
        bool(
            obj.notify(
                body="body",
                title="title",
                notify_type=NotifyType.INFO,
                attach=multi_attach,
            )
        )
        is True
    )


@mock.patch("requests.get")
@mock.patch("requests.post")
def test_plugin_mailersend_url_parsing(mock_post, mock_get):
    """NotifyMailerSend() URL parsing."""

    # Empty URL
    assert NotifyMailerSend.parse_url("") is None

    # Missing API key (no user segment)
    result = NotifyMailerSend.parse_url(
        "mailersend://user@host.com/to@example.com"
    )
    assert result is None

    # Valid round-trip
    obj = NotifyMailerSend(
        apikey="mlsn.abc123",
        from_email="sender@example.com",
        targets=["to@example.com"],
        cc=["cc@example.com"],
        bcc=["bcc@example.com"],
        reply_to="reply@example.com",
    )
    url = obj.url()
    result = NotifyMailerSend.parse_url(url)
    assert result is not None
    obj2 = NotifyMailerSend(**result)
    assert obj.url_identifier == obj2.url_identifier
    assert len(obj.targets) == len(obj2.targets)

    # url() with privacy=True masks the API key
    priv = obj.url(privacy=True)
    assert "mlsn.abc123" not in priv

    # len() returns number of targets (at least 1)
    obj_self = NotifyMailerSend(
        apikey="abcd",
        from_email="user@example.com",
    )
    assert len(obj_self) >= 1

    # CC/BCC round-trip preserved
    assert "cc=" in url
    assert "bcc=" in url
    assert "reply=" in url

    # ?to= alias
    result = NotifyMailerSend.parse_url(
        "mailersend://abcd:user@example.com?to=extra@example.com"
    )
    assert result is not None
    assert "extra@example.com" in result["targets"]


@mock.patch("requests.get")
@mock.patch("requests.post")
def test_plugin_mailersend_apprise_integration(mock_post, mock_get):
    """NotifyMailerSend() Apprise integration test."""

    def _mk_resp(code=requests.codes.accepted):
        r = mock.Mock()
        r.status_code = code
        r.content = b""
        return r

    mock_post.return_value = _mk_resp()
    mock_get.return_value = _mk_resp()

    a = Apprise()
    assert a.add("mailersend://abcd:user@example.com/to@example.com")
    assert bool(a.notify(body="body", title="title")) is True
