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
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
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
from unittest import mock

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise, NotifyType
from apprise.plugins.zoom import (
    ZOOM_MODE_DEFAULT,
    NotifyZoom,
    ZoomMode,
)

logging.disable(logging.CRITICAL)

# Reusable test credentials
WEBHOOK_ID = "abcHook123"
TOKEN = "xyzVerify456"

# Our Testing URLs
apprise_url_tests = (
    # Missing everything
    (
        "zoom://",
        {
            "instance": TypeError,
        },
    ),
    # Empty user/host segment
    (
        "zoom://:@/",
        {
            "instance": TypeError,
        },
    ),
    # Missing token (webhook_id present but no path segment)
    (
        "zoom://{}".format(WEBHOOK_ID),
        {
            "instance": TypeError,
        },
    ),
    # Valid full-mode (default)
    (
        "zoom://{}/{}".format(WEBHOOK_ID, TOKEN),
        {
            "instance": NotifyZoom,
            "privacy_url": "zoom://a...3/x...6/",
        },
    ),
    # Explicit mode=full
    (
        "zoom://{}/{}?mode=full".format(WEBHOOK_ID, TOKEN),
        {
            "instance": NotifyZoom,
            "privacy_url": "zoom://a...3/x...6/",
        },
    ),
    # Explicit mode=simple
    (
        "zoom://{}/{}?mode=simple".format(WEBHOOK_ID, TOKEN),
        {
            "instance": NotifyZoom,
            "privacy_url": "zoom://a...3/x...6/",
        },
    ),
    # Invalid mode
    (
        "zoom://{}/{}?mode=invalid".format(WEBHOOK_ID, TOKEN),
        {
            "instance": TypeError,
        },
    ),
    # Native URL with ?token= query param
    (
        "https://inbots.zoom.us/incoming/hook/{}?token={}".format(
            WEBHOOK_ID, TOKEN
        ),
        {
            "instance": NotifyZoom,
        },
    ),
    # Full mode: HTTP 500
    (
        "zoom://{}/{}".format(WEBHOOK_ID, TOKEN),
        {
            "instance": NotifyZoom,
            "response": False,
            "requests_response_code": (requests.codes.internal_server_error),
        },
    ),
    # Full mode: unusual status code
    (
        "zoom://{}/{}".format(WEBHOOK_ID, TOKEN),
        {
            "instance": NotifyZoom,
            "response": False,
            "requests_response_code": 999,
        },
    ),
    # Full mode: request exception
    (
        "zoom://{}/{}".format(WEBHOOK_ID, TOKEN),
        {
            "instance": NotifyZoom,
            "test_requests_exceptions": True,
        },
    ),
    # Simple mode: HTTP 500
    (
        "zoom://{}/{}?mode=simple".format(WEBHOOK_ID, TOKEN),
        {
            "instance": NotifyZoom,
            "response": False,
            "requests_response_code": (requests.codes.internal_server_error),
        },
    ),
    # Simple mode: unusual status code
    (
        "zoom://{}/{}?mode=simple".format(WEBHOOK_ID, TOKEN),
        {
            "instance": NotifyZoom,
            "response": False,
            "requests_response_code": 999,
        },
    ),
    # Simple mode: request exception
    (
        "zoom://{}/{}?mode=simple".format(WEBHOOK_ID, TOKEN),
        {
            "instance": NotifyZoom,
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_zoom_urls():
    """NotifyZoom() Apprise URLs."""
    AppriseURLTester(tests=apprise_url_tests).run_all()


def test_plugin_zoom_init():
    """Test NotifyZoom initialization and validation."""

    # Missing webhook_id
    with pytest.raises(TypeError):
        NotifyZoom(webhook_id=None, token=TOKEN)

    # Empty webhook_id
    with pytest.raises(TypeError):
        NotifyZoom(webhook_id="", token=TOKEN)

    # Webhook ID with invalid characters (slash)
    with pytest.raises(TypeError):
        NotifyZoom(webhook_id="bad/id", token=TOKEN)

    # Missing token
    with pytest.raises(TypeError):
        NotifyZoom(webhook_id=WEBHOOK_ID, token=None)

    # Empty token
    with pytest.raises(TypeError):
        NotifyZoom(webhook_id=WEBHOOK_ID, token="")

    # Invalid mode
    with pytest.raises(TypeError):
        NotifyZoom(webhook_id=WEBHOOK_ID, token=TOKEN, mode="bogus")

    # Empty string mode is also invalid (must not silently resolve to simple)
    with pytest.raises(TypeError):
        NotifyZoom(webhook_id=WEBHOOK_ID, token=TOKEN, mode="")

    # Whitespace-only mode is also invalid
    with pytest.raises(TypeError):
        NotifyZoom(webhook_id=WEBHOOK_ID, token=TOKEN, mode="   ")

    # Valid: default mode
    obj = NotifyZoom(webhook_id=WEBHOOK_ID, token=TOKEN)
    assert obj.mode == ZOOM_MODE_DEFAULT

    # Valid: explicit full mode
    obj = NotifyZoom(webhook_id=WEBHOOK_ID, token=TOKEN, mode="full")
    assert obj.mode == ZoomMode.FULL

    # Valid: explicit simple mode
    obj = NotifyZoom(webhook_id=WEBHOOK_ID, token=TOKEN, mode="simple")
    assert obj.mode == ZoomMode.SIMPLE

    # Partial prefix matching: "sim" -> "simple"
    obj = NotifyZoom(webhook_id=WEBHOOK_ID, token=TOKEN, mode="sim")
    assert obj.mode == ZoomMode.SIMPLE

    # Partial prefix matching: "f" -> "full"
    obj = NotifyZoom(webhook_id=WEBHOOK_ID, token=TOKEN, mode="f")
    assert obj.mode == ZoomMode.FULL


def test_plugin_zoom_url_round_trip():
    """Verify that url() -> parse_url() -> __init__ is lossless."""

    # Full mode round-trip
    obj1 = NotifyZoom(webhook_id=WEBHOOK_ID, token=TOKEN, mode="full")
    result = NotifyZoom.parse_url(obj1.url())
    obj2 = NotifyZoom(**result)
    assert obj1.url_identifier == obj2.url_identifier
    assert obj1.mode == obj2.mode

    # Simple mode round-trip
    obj1 = NotifyZoom(webhook_id=WEBHOOK_ID, token=TOKEN, mode="simple")
    result = NotifyZoom.parse_url(obj1.url())
    obj2 = NotifyZoom(**result)
    assert obj1.url_identifier == obj2.url_identifier
    assert obj1.mode == obj2.mode


def test_plugin_zoom_url_privacy():
    """Verify url(privacy=True) masks webhook_id and token."""
    obj = NotifyZoom(webhook_id=WEBHOOK_ID, token=TOKEN)
    priv = obj.url(privacy=True)
    assert WEBHOOK_ID not in priv
    assert TOKEN not in priv
    # Schema is still present
    assert priv.startswith("zoom://")


def test_plugin_zoom_url_identifier():
    """Verify url_identifier contains webhook_id, token, and mode."""
    obj = NotifyZoom(webhook_id=WEBHOOK_ID, token=TOKEN)
    uid = obj.url_identifier
    assert "zoom" in uid
    assert WEBHOOK_ID in uid
    assert TOKEN in uid

    # Two instances with different tokens are distinct
    obj2 = NotifyZoom(webhook_id=WEBHOOK_ID, token="other")
    assert obj.url_identifier != obj2.url_identifier

    # Same credentials but different modes produce different identifiers
    obj_full = NotifyZoom(webhook_id=WEBHOOK_ID, token=TOKEN, mode="full")
    obj_simple = NotifyZoom(webhook_id=WEBHOOK_ID, token=TOKEN, mode="simple")
    assert obj_full.url_identifier != obj_simple.url_identifier
    assert ZoomMode.FULL in obj_full.url_identifier
    assert ZoomMode.SIMPLE in obj_simple.url_identifier


@mock.patch("requests.post")
def test_plugin_zoom_full_send(mock_post):
    """Test _send_full() success and failure paths."""

    def _mk_resp(code=requests.codes.ok):
        r = mock.Mock()
        r.status_code = code
        r.content = b""
        return r

    mock_post.return_value = _mk_resp()

    # Success: with title
    obj = NotifyZoom(webhook_id=WEBHOOK_ID, token=TOKEN)
    assert obj.notify(
        body="body text",
        title="My Title",
        notify_type=NotifyType.INFO,
    )
    assert mock_post.call_count == 1
    # Verify ?format=full in URL
    call_url = mock_post.call_args[0][0]
    assert "format=full" in call_url

    mock_post.reset_mock()

    # Success: without title (no head section)
    assert obj.notify(
        body="body only",
        title="",
        notify_type=NotifyType.INFO,
    )
    assert mock_post.call_count == 1

    mock_post.reset_mock()

    # HTTP 204 is also a success
    mock_post.return_value = _mk_resp(requests.codes.no_content)
    assert obj.notify(body="test", notify_type=NotifyType.INFO)

    mock_post.reset_mock()

    # HTTP 500 -> failure
    mock_post.return_value = _mk_resp(requests.codes.internal_server_error)
    assert not obj.notify(body="test", notify_type=NotifyType.INFO)

    mock_post.reset_mock()

    # Unknown status code -> failure
    mock_post.return_value = _mk_resp(999)
    assert not obj.notify(body="test", notify_type=NotifyType.INFO)

    mock_post.reset_mock()

    # RequestException -> failure
    mock_post.side_effect = requests.RequestException("boom")
    assert not obj.notify(body="test", notify_type=NotifyType.INFO)


@mock.patch("requests.post")
def test_plugin_zoom_simple_send(mock_post):
    """Test _send_simple() success and failure paths."""

    def _mk_resp(code=requests.codes.ok):
        r = mock.Mock()
        r.status_code = code
        r.content = b""
        return r

    mock_post.return_value = _mk_resp()

    # Create a simple-mode instance
    obj = NotifyZoom(webhook_id=WEBHOOK_ID, token=TOKEN, mode="simple")

    # Success: with title (title prepended to body)
    assert obj.notify(
        body="msg body",
        title="Alert",
        notify_type=NotifyType.INFO,
    )
    assert mock_post.call_count == 1
    # Verify no ?format= in simple mode URL
    call_url = mock_post.call_args[0][0]
    assert "format" not in call_url

    mock_post.reset_mock()

    # Success: without title
    assert obj.notify(
        body="no title",
        title="",
        notify_type=NotifyType.INFO,
    )

    mock_post.reset_mock()

    # HTTP 204 is also a success
    mock_post.return_value = _mk_resp(requests.codes.no_content)
    assert obj.notify(body="test", notify_type=NotifyType.INFO)

    mock_post.reset_mock()

    # HTTP 500 -> failure
    mock_post.return_value = _mk_resp(requests.codes.internal_server_error)
    assert not obj.notify(body="test", notify_type=NotifyType.INFO)

    mock_post.reset_mock()

    # Unknown status code -> failure
    mock_post.return_value = _mk_resp(999)
    assert not obj.notify(body="test", notify_type=NotifyType.INFO)

    mock_post.reset_mock()

    # RequestException -> failure
    mock_post.side_effect = requests.RequestException("err")
    assert not obj.notify(body="test", notify_type=NotifyType.INFO)


def test_plugin_zoom_parse_url():
    """Exercise parse_url() edge cases."""

    # Basic: webhook_id in host, token in path
    result = NotifyZoom.parse_url("zoom://myhookid/mytoken/")
    assert result["webhook_id"] == "myhookid"
    assert result["token"] == "mytoken"

    # ?token= override
    result = NotifyZoom.parse_url("zoom://myhookid/?token=override123")
    assert result["webhook_id"] == "myhookid"
    assert result["token"] == "override123"

    # ?mode= parameter
    result = NotifyZoom.parse_url("zoom://myhookid/mytoken/?mode=simple")
    assert result["mode"] == "simple"

    # A URL that fails base parsing returns None
    result = NotifyZoom.parse_url(None)
    assert result is None


def test_plugin_zoom_parse_native_url():
    """Exercise parse_native_url()."""

    # Native URL with ?token= appended
    result = NotifyZoom.parse_native_url(
        "https://inbots.zoom.us/incoming/hook/{}?token={}".format(
            WEBHOOK_ID, TOKEN
        )
    )
    assert result is not None
    assert result["webhook_id"] == WEBHOOK_ID
    assert result["token"] == TOKEN

    # Native URL without token -> parse succeeds but
    # token will be None/missing (instantiation would fail)
    result = NotifyZoom.parse_native_url(
        "https://inbots.zoom.us/incoming/hook/{}".format(WEBHOOK_ID)
    )
    assert result is not None
    assert result["webhook_id"] == WEBHOOK_ID

    # Non-matching URL -> None
    assert (
        NotifyZoom.parse_native_url("https://example.com/not/a/zoom/url")
        is None
    )


@mock.patch("requests.post")
def test_plugin_zoom_apprise_integration(mock_post):
    """Test end-to-end via Apprise.add() and Apprise.notify()."""
    r = mock.Mock()
    r.status_code = requests.codes.ok
    r.content = b""
    mock_post.return_value = r

    app = Apprise()
    assert app.add("zoom://{}/{}".format(WEBHOOK_ID, TOKEN))
    assert app.notify(title="Hello", body="World")
    assert mock_post.call_count == 1
