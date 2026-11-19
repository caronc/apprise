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

from json import dumps

# Disable logging for a cleaner testing output
import logging
import os
from unittest import mock
from urllib.parse import urlparse

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise, AppriseAttachment, NotifyType
from apprise.exception import AppriseImproperlyConfigured
from apprise.plugins.bale import NotifyBale

logging.disable(logging.CRITICAL)

# Attachment Directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), "var")

# A Bot Token in the form @botfather hands out
TOKEN = "123456789:abcdefghijKLMNOPqrst"

# Our Chat IDs
CHAT_ID = "987654321"
GROUP_CHAT_ID = "-987654321"

# Apprise URL Tests
apprise_url_tests = (
    (
        "bale://",
        {
            # No Bot Token
            "instance": TypeError,
        },
    ),
    (
        "bale://123456789",
        {
            # Only half of a Bot Token
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "bale://abcdefghi:abcdefghij/987654321",
        {
            # The first part of a Bot Token is numeric
            "instance": TypeError,
        },
    ),
    (
        f"bale://{TOKEN}",
        {
            # Valid Bot Token, but no Chat IDs to notify
            "instance": NotifyBale,
            "notify_response": False,
        },
    ),
    (
        f"bale://{TOKEN}/{CHAT_ID}",
        {
            "instance": NotifyBale,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": f"bale://1...t/{CHAT_ID}",
        },
    ),
    (
        f"bale://{TOKEN}/{GROUP_CHAT_ID}/@mychannel/%40other/",
        {
            # A group, and channels with and without an encoded @
            "instance": NotifyBale,
            "privacy_url": (f"bale://1...t/{GROUP_CHAT_ID}/@mychannel/@other"),
        },
    ),
    (
        f"bale://{TOKEN}/{CHAT_ID}/invalid!/",
        {
            # One invalid Chat ID is dropped; the valid one is notified
            "instance": NotifyBale,
        },
    ),
    (
        f"bale://{TOKEN}/invalid!/",
        {
            # Only invalid Chat IDs leaves nothing to notify
            "instance": NotifyBale,
            "notify_response": False,
        },
    ),
    (
        "bale://123456789%3Aabcdefghij/987654321",
        {
            # An encoded colon in the Bot Token
            "instance": NotifyBale,
        },
    ),
    (
        f"bale://?token={TOKEN}&to={CHAT_ID},{GROUP_CHAT_ID}",
        {
            # Bot Token and Chat IDs as URL parameters
            "instance": NotifyBale,
            "privacy_url": f"bale://1...t/{GROUP_CHAT_ID}/{CHAT_ID}",
        },
    ),
    (
        f"bale://{CHAT_ID}?token={TOKEN}",
        {
            # With ?token=, the host is a Chat ID
            "instance": NotifyBale,
        },
    ),
    (
        f"bale://{TOKEN}/{CHAT_ID}",
        {
            "instance": NotifyBale,
            # Bale says no
            "requests_response_text": {"ok": False},
            "response": False,
        },
    ),
    (
        f"bale://{TOKEN}/{CHAT_ID}",
        {
            "instance": NotifyBale,
            # A non-JSON reply relies on the status code alone
            "requests_response_text": "not json",
        },
    ),
    (
        f"bale://{TOKEN}/{CHAT_ID}",
        {
            "instance": NotifyBale,
            # throw a bizarre code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        f"bale://{TOKEN}/{CHAT_ID}",
        {
            "instance": NotifyBale,
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        f"bale://{TOKEN}/{CHAT_ID}",
        {
            "instance": NotifyBale,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracefully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_bale_urls():
    """NotifyBale() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.post")
def test_plugin_bale_send(mock_post):
    """NotifyBale() sends the title and body to every Chat ID."""

    mock_post.return_value = mock.Mock(
        status_code=requests.codes.ok, content=dumps({"ok": True})
    )

    obj = Apprise.instantiate(f"bale://{TOKEN}/{CHAT_ID}/@mychannel")
    assert isinstance(obj, NotifyBale)
    assert len(obj) == 2
    assert obj.notify(title="Alert", body="body", notify_type=NotifyType.INFO)

    # One message per Chat ID
    assert mock_post.call_count == 2
    url = mock_post.call_args_list[0][0][0]
    assert urlparse(url).hostname == "tapi.bale.ai"
    assert urlparse(url).path == f"/bot{TOKEN}/sendMessage"

    # The title is placed above the body
    payloads = [c[1]["data"] for c in mock_post.call_args_list]
    assert payloads[0] == {"chat_id": CHAT_ID, "text": "Alert\r\nbody"}
    assert payloads[1] == {"chat_id": "@mychannel", "text": "Alert\r\nbody"}

    # Redirects follow the global setting
    assert mock_post.call_args_list[0][1]["allow_redirects"] is True

    # The URL survives a round trip
    obj2 = Apprise.instantiate(obj.url())
    assert obj2.url_identifier == obj.url_identifier
    assert obj2.targets == obj.targets


@pytest.mark.parametrize(
    ("title", "body_length", "overflow", "calls"),
    (
        ("", 4097, "split", 2),
        ("", 4097, "truncate", 1),
        ("Alert", 4091, "split", 2),
        ("Alert", 4091, "truncate", 1),
        ("T" * 250, 3846, "split", 2),
    ),
)
@mock.patch("requests.post")
def test_plugin_bale_message_limit(
    mock_post, title, body_length, overflow, calls
):
    """Keep every message, title included, within 4096 characters."""

    mock_post.return_value = mock.Mock(
        status_code=requests.codes.ok, content=dumps({"ok": True})
    )

    obj = Apprise.instantiate(f"bale://{TOKEN}/{CHAT_ID}?overflow={overflow}")
    assert obj.notify(body="x" * body_length, title=title)

    texts = [c[1]["data"]["text"] for c in mock_post.call_args_list]
    assert len(texts) == calls
    assert all(len(text) <= 4096 for text in texts)


@mock.patch("requests.post")
def test_plugin_bale_hides_token(mock_post):
    """The Bot Token never reaches the logs."""

    mock_post.side_effect = requests.ConnectionError("boom")

    obj = Apprise.instantiate(f"bale://{TOKEN}/{CHAT_ID}")
    with mock.patch.multiple(
        obj.logger, warning=mock.DEFAULT, debug=mock.DEFAULT
    ) as logged:
        assert not obj.notify(body="body")

    assert "abcdefghijKLMNOPqrst" not in repr(logged["warning"].call_args_list)
    assert "abcdefghijKLMNOPqrst" not in repr(logged["debug"].call_args_list)


@mock.patch("requests.post")
def test_plugin_bale_attachments(mock_post):
    """NotifyBale() uploads photos and files after the message."""

    mock_post.return_value = mock.Mock(
        status_code=requests.codes.ok, content=dumps({"ok": True})
    )

    obj = Apprise.instantiate(f"bale://{TOKEN}/{CHAT_ID}")
    attach = AppriseAttachment(
        [
            os.path.join(TEST_VAR_DIR, "apprise-test.gif"),
            os.path.join(TEST_VAR_DIR, "apprise-test.mp4"),
        ]
    )

    # Message, then a photo, then a file
    assert obj.notify(body="body", attach=attach)
    assert mock_post.call_count == 3
    paths = [urlparse(c[0][0]).path for c in mock_post.call_args_list]
    assert paths == [
        f"/bot{TOKEN}/sendMessage",
        f"/bot{TOKEN}/sendPhoto",
        f"/bot{TOKEN}/sendDocument",
    ]
    assert "photo" in mock_post.call_args_list[1][1]["files"]
    assert "document" in mock_post.call_args_list[2][1]["files"]
    assert mock_post.call_args_list[1][1]["data"] == {"chat_id": CHAT_ID}

    # An attachment on its own sends no text
    mock_post.reset_mock()
    assert obj.notify(body="", attach=attach[0])
    assert mock_post.call_count == 1
    assert urlparse(mock_post.call_args[0][0]).path.endswith("/sendPhoto")

    # An attachment that can not be accessed is not sent
    mock_post.reset_mock()
    with mock.patch("os.path.isfile", return_value=False):
        assert not obj.notify(body="body", attach=attach)
    assert mock_post.call_count == 1

    # An attachment that can not be opened is not sent
    mock_post.reset_mock()
    with mock.patch("builtins.open", side_effect=OSError):
        assert not obj.notify(body="body", attach=attach)
    assert mock_post.call_count == 1

    # A refused upload stops the remaining attachments
    mock_post.reset_mock()
    mock_post.side_effect = (
        mock.Mock(status_code=requests.codes.ok, content=b"{}"),
        mock.Mock(status_code=requests.codes.bad_request, content=b"{}"),
    )
    assert not obj.notify(body="body", attach=attach)
    assert mock_post.call_count == 2


@mock.patch("requests.post")
def test_plugin_bale_retry_skips_delivered(mock_post):
    """A retry re-sends only the attachment that failed."""

    ok = mock.Mock(status_code=requests.codes.ok, content=b"{}")
    bad = mock.Mock(status_code=requests.codes.bad_request, content=b"{}")

    # Message ok, photo ok, file refused, then the retried file ok
    mock_post.side_effect = (ok, ok, bad, ok)

    obj = Apprise.instantiate(f"bale://{TOKEN}/{CHAT_ID}?retry=1&wait=0")
    attach = AppriseAttachment(
        [
            os.path.join(TEST_VAR_DIR, "apprise-test.gif"),
            os.path.join(TEST_VAR_DIR, "apprise-test.mp4"),
        ]
    )

    with mock.patch("apprise.apprise.time.sleep"):
        aobj = Apprise()
        aobj.add(obj)
        assert aobj.notify(body="body", attach=attach)

    paths = [urlparse(c[0][0]).path for c in mock_post.call_args_list]
    assert paths == [
        f"/bot{TOKEN}/sendMessage",
        f"/bot{TOKEN}/sendPhoto",
        f"/bot{TOKEN}/sendDocument",
        f"/bot{TOKEN}/sendDocument",
    ]
