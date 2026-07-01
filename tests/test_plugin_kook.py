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
from json import dumps
from unittest import mock
from urllib.parse import urlparse

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise, AppriseAttachment, NotifyType
from apprise.plugins.kook import (
    KOOK_MODES,
    KOOK_MSG_TYPES,
    KookMode,
    KookMsgType,
    NotifyKook,
)

logging.disable(logging.CRITICAL)

# Attachment directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), "var")

# A realistic-looking fake bot token
BOT_TOKEN = "1/MTQ3OTE5MTA3MzQ1ODE4OTQ0/YJVvSXB0IK+ABC123XYZ"

# Fake channel / user IDs (numeric snowflakes)
CHANNEL_ID = "1234567890"
CHANNEL_ID2 = "9876543210"
USER_ID = "5555555555"

# Fake webhook key
WEBHOOK_KEY = "abc123webhookkey"


# -----------------------------------------------------------------------
# URL tester table
# -----------------------------------------------------------------------
TEST_URLS = (
    ##
    # Invalid cases
    ##
    # Missing token
    (
        "kook://",
        {
            "instance": TypeError,
        },
    ),
    # Invalid mode
    (
        f"kook://{BOT_TOKEN}/?mode=invalid",
        {
            "instance": TypeError,
        },
    ),
    # Invalid msg_type
    (
        f"kook://{BOT_TOKEN}/{CHANNEL_ID}/?msg_type=invalid",
        {
            "instance": TypeError,
        },
    ),
    ##
    # Webhook mode
    ##
    # Basic webhook
    (
        f"kook://{WEBHOOK_KEY}/?mode=webhook",
        {
            "instance": NotifyKook,
            "privacy_url": "kook://a...y/?mode=webhook",
        },
    ),
    # Webhook via ?token= override
    (
        f"kook://ignored/?token={WEBHOOK_KEY}&mode=webhook",
        {
            "instance": NotifyKook,
        },
    ),
    # Webhook HTTP 500
    (
        f"kook://{WEBHOOK_KEY}/?mode=webhook",
        {
            "instance": NotifyKook,
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    # Webhook unknown response code
    (
        f"kook://{WEBHOOK_KEY}/?mode=webhook",
        {
            "instance": NotifyKook,
            "response": False,
            "requests_response_code": 999,
        },
    ),
    # Webhook RequestException
    (
        f"kook://{WEBHOOK_KEY}/?mode=webhook",
        {
            "instance": NotifyKook,
            "test_requests_exceptions": True,
        },
    ),
    ##
    # Bot mode - single channel
    # attach_response=False because _upload() needs a CDN URL in the
    # response body; the default mock returns empty content so the CDN
    # upload step returns None and the send returns False.
    ##
    (
        f"kook://{BOT_TOKEN}/{CHANNEL_ID}",
        {
            "instance": NotifyKook,
            "attach_response": False,
        },
    ),
    # Bot mode - multiple channels
    (
        f"kook://{BOT_TOKEN}/{CHANNEL_ID}/{CHANNEL_ID2}",
        {
            "instance": NotifyKook,
            "attach_response": False,
        },
    ),
    # Bot mode - DM target
    (
        f"kook://{BOT_TOKEN}/@{USER_ID}",
        {
            "instance": NotifyKook,
            "attach_response": False,
        },
    ),
    # Bot mode - channel + DM mixed
    (
        f"kook://{BOT_TOKEN}/{CHANNEL_ID}/@{USER_ID}",
        {
            "instance": NotifyKook,
            "attach_response": False,
        },
    ),
    # Bot mode - no targets (loads but notify() returns False)
    (
        f"kook://{BOT_TOKEN}",
        {
            "instance": NotifyKook,
            "notify_response": False,
        },
    ),
    # Bot mode via ?to=
    (
        f"kook://{BOT_TOKEN}/?to={CHANNEL_ID}",
        {
            "instance": NotifyKook,
            "attach_response": False,
        },
    ),
    # Bot mode with msg_type=text
    (
        f"kook://{BOT_TOKEN}/{CHANNEL_ID}/?msg_type=text",
        {
            "instance": NotifyKook,
            "attach_response": False,
        },
    ),
    # Bot mode HTTP 500
    (
        f"kook://{BOT_TOKEN}/{CHANNEL_ID}",
        {
            "instance": NotifyKook,
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    # Bot mode unknown response code
    (
        f"kook://{BOT_TOKEN}/{CHANNEL_ID}",
        {
            "instance": NotifyKook,
            "response": False,
            "requests_response_code": 999,
        },
    ),
    # Bot mode RequestException
    (
        f"kook://{BOT_TOKEN}/{CHANNEL_ID}",
        {
            "instance": NotifyKook,
            "test_requests_exceptions": True,
        },
    ),
    # Native webhook URL
    (
        "https://www.kookapp.cn/api/v3/incoming/nativekey123",
        {
            "instance": NotifyKook,
            "privacy_url": "kook://n...3/?mode=webhook",
        },
    ),
)


@pytest.fixture
def apprise_url_tester():
    return AppriseURLTester(tests=TEST_URLS)


def test_plugin_kook_urls(apprise_url_tester):
    """Run all URL test table entries through AppriseURLTester."""
    apprise_url_tester.run_all()


# -----------------------------------------------------------------------
# __init__ and url() round-trip tests
# -----------------------------------------------------------------------


def test_plugin_kook_bot_mode():
    """Verify bot-mode init, url(), url_identifier, and round-trip."""

    # Single channel
    obj = NotifyKook(token=BOT_TOKEN, targets=[CHANNEL_ID])
    assert obj.mode == KookMode.BOT
    assert obj.msg_type == KookMsgType.KMARKDOWN
    assert obj.channels == [CHANNEL_ID]
    assert obj.dm_users == []
    assert obj.attachment_support is True

    # url_identifier must only reference connection identity, not targets
    ident = obj.url_identifier
    assert ident == ("kook", KookMode.BOT, BOT_TOKEN)

    # Round-trip
    url = obj.url()
    parsed = NotifyKook.parse_url(url)
    assert parsed is not None
    obj2 = NotifyKook(**parsed)
    assert obj2.url_identifier == obj.url_identifier
    assert len(obj2.channels) == len(obj.channels)

    # privacy_url should mask the token
    purl = obj.url(privacy=True)
    assert BOT_TOKEN not in purl

    # Multiple channels
    obj = NotifyKook(token=BOT_TOKEN, targets=[CHANNEL_ID, CHANNEL_ID2])
    assert len(obj.channels) == 2
    url = obj.url()
    parsed = NotifyKook.parse_url(url)
    obj2 = NotifyKook(**parsed)
    assert len(obj2.channels) == 2

    # DM target
    obj = NotifyKook(token=BOT_TOKEN, targets=[f"@{USER_ID}"])
    assert obj.dm_users == [USER_ID]
    assert obj.channels == []
    url = obj.url()
    parsed = NotifyKook.parse_url(url)
    obj2 = NotifyKook(**parsed)
    assert obj2.dm_users == [USER_ID]

    # Mixed channel + DM
    obj = NotifyKook(
        token=BOT_TOKEN,
        targets=[CHANNEL_ID, f"@{USER_ID}"],
    )
    assert len(obj.channels) == 1
    assert len(obj.dm_users) == 1
    url = obj.url()
    parsed = NotifyKook.parse_url(url)
    obj2 = NotifyKook(**parsed)
    assert len(obj2.channels) == 1
    assert len(obj2.dm_users) == 1

    # # prefix stripped from channel
    obj = NotifyKook(token=BOT_TOKEN, targets=[f"#{CHANNEL_ID}"])
    assert obj.channels == [CHANNEL_ID]

    # Invalid channel and DM IDs are stored in _invalid_targets and
    # survive the round-trip
    obj = NotifyKook(
        token=BOT_TOKEN,
        targets=["notanumber", "@notanumber"],
    )
    assert obj.channels == []
    assert obj.dm_users == []
    assert len(obj._invalid_targets) == 2
    url = obj.url()
    parsed = NotifyKook.parse_url(url)
    obj2 = NotifyKook(**parsed)
    assert len(obj2._invalid_targets) == 2

    # No targets
    obj = NotifyKook(token=BOT_TOKEN)
    assert obj.channels == []
    assert obj.dm_users == []

    # msg_type = text
    obj = NotifyKook(
        token=BOT_TOKEN, targets=[CHANNEL_ID], msg_type="text"
    )
    assert obj.msg_type == KookMsgType.TEXT
    url = obj.url()
    assert "msg_type=text" in url
    parsed = NotifyKook.parse_url(url)
    obj2 = NotifyKook(**parsed)
    assert obj2.msg_type == KookMsgType.TEXT

    # Default msg_type not emitted in URL
    obj = NotifyKook(token=BOT_TOKEN, targets=[CHANNEL_ID])
    url = obj.url()
    assert "msg_type" not in url

    # Default mode not emitted in URL
    assert "mode" not in url


def test_plugin_kook_webhook_mode():
    """Verify webhook-mode init, url(), and url_identifier."""

    obj = NotifyKook(token=WEBHOOK_KEY, mode="webhook")
    assert obj.mode == KookMode.WEBHOOK
    assert obj.attachment_support is False
    assert obj.channels == []
    assert obj.dm_users == []

    # url_identifier includes mode
    assert obj.url_identifier == ("kook", KookMode.WEBHOOK, WEBHOOK_KEY)

    # url() emits mode=webhook
    url = obj.url()
    assert "mode=webhook" in url

    # Round-trip
    parsed = NotifyKook.parse_url(url)
    obj2 = NotifyKook(**parsed)
    assert obj2.url_identifier == obj.url_identifier
    assert obj2.mode == KookMode.WEBHOOK

    # Missing token
    with pytest.raises(TypeError):
        NotifyKook(token=None)

    with pytest.raises(TypeError):
        NotifyKook(token="")


def test_plugin_kook_mode_invalid():
    """Invalid mode raises TypeError."""
    with pytest.raises(TypeError):
        NotifyKook(token=BOT_TOKEN, mode="invalid_mode")


def test_plugin_kook_msg_type_invalid():
    """Invalid msg_type raises TypeError."""
    with pytest.raises(TypeError):
        NotifyKook(
            token=BOT_TOKEN, targets=[CHANNEL_ID], msg_type="card"
        )


def test_plugin_kook_url_parsing():
    """Exercise parse_url edge cases."""

    # ?token= query param overrides the host
    url = f"kook://ignored/?token={BOT_TOKEN}&to={CHANNEL_ID}"
    parsed = NotifyKook.parse_url(url)
    assert parsed is not None
    assert parsed["token"] == BOT_TOKEN
    assert CHANNEL_ID in parsed["targets"]

    # split_path collects multiple targets
    url = f"kook://{BOT_TOKEN}/{CHANNEL_ID}/{CHANNEL_ID2}"
    parsed = NotifyKook.parse_url(url)
    assert CHANNEL_ID in parsed["targets"]
    assert CHANNEL_ID2 in parsed["targets"]

    # None input returns None
    assert NotifyKook.parse_url(None) is None


def test_plugin_kook_native_url():
    """parse_native_url accepts a full Kook webhook URL."""
    url = "https://www.kookapp.cn/api/v3/incoming/mywebhookkey"
    parsed = NotifyKook.parse_native_url(url)
    assert parsed is not None
    assert parsed["token"] == "mywebhookkey"
    assert parsed["mode"] == KookMode.WEBHOOK

    # Native URL with trailing slash
    url = "https://www.kookapp.cn/api/v3/incoming/mywebhookkey/"
    parsed = NotifyKook.parse_native_url(url)
    assert parsed is not None
    assert parsed["token"] == "mywebhookkey"

    # Non-matching URL returns None
    assert NotifyKook.parse_native_url("https://example.com/") is None


# -----------------------------------------------------------------------
# send() tests - webhook mode
# -----------------------------------------------------------------------


@mock.patch("requests.post")
def test_plugin_kook_webhook_send(mock_post):
    """Webhook mode send: success, HTTP error, API error, RequestException."""

    def _mk_resp(code=requests.codes.ok, api_code=0):
        r = mock.Mock()
        r.status_code = code
        r.content = dumps({"code": api_code, "message": "ok"}).encode()
        return r

    # Success
    mock_post.return_value = _mk_resp()
    obj = NotifyKook(token=WEBHOOK_KEY, mode="webhook")
    assert obj.notify(body="hello") is True
    assert mock_post.call_count == 1

    # Verify the endpoint URL
    call_url = mock_post.call_args[0][0]
    assert urlparse(call_url).hostname == "www.kookapp.cn"
    assert "/incoming/" in call_url

    # HTTP 500 -> False
    mock_post.return_value = _mk_resp(
        code=requests.codes.internal_server_error
    )
    assert obj.notify(body="hello") is False

    # Unknown HTTP code -> False
    mock_post.return_value = _mk_resp(code=999)
    assert obj.notify(body="hello") is False

    # API-level error (code != 0) -> False
    mock_post.return_value = _mk_resp(api_code=40001)
    assert obj.notify(body="hello") is False

    # Unparseable JSON body is handled gracefully
    r = mock.Mock()
    r.status_code = requests.codes.ok
    r.content = b"not-json"
    mock_post.return_value = r
    # code defaults to 0 -> success (unparseable treated as ok)
    assert obj.notify(body="hello") is True

    # RequestException -> False
    mock_post.side_effect = requests.RequestException("conn error")
    assert obj.notify(body="hello") is False
    mock_post.side_effect = None


# -----------------------------------------------------------------------
# send() tests - bot mode
# -----------------------------------------------------------------------


@mock.patch("requests.post")
def test_plugin_kook_bot_send(mock_post):
    """Bot mode send: no targets, single channel, multiple, DM, error."""

    def _ok():
        r = mock.Mock()
        r.status_code = requests.codes.ok
        r.content = dumps({"code": 0}).encode()
        return r

    def _err(code=requests.codes.internal_server_error):
        r = mock.Mock()
        r.status_code = code
        r.content = b""
        return r

    # No targets -> False without making a network call
    obj = NotifyKook(token=BOT_TOKEN)
    mock_post.reset_mock()
    assert obj.notify(body="hello") is False
    assert mock_post.call_count == 0

    # Single channel success
    mock_post.return_value = _ok()
    obj = NotifyKook(token=BOT_TOKEN, targets=[CHANNEL_ID])
    assert obj.notify(body="hello") is True
    assert mock_post.call_count == 1

    # Verify Authorization header
    call_kwargs = mock_post.call_args[1]
    assert f"Bot {BOT_TOKEN}" in call_kwargs["headers"]["Authorization"]

    # Multiple channels
    mock_post.return_value = _ok()
    obj = NotifyKook(
        token=BOT_TOKEN, targets=[CHANNEL_ID, CHANNEL_ID2]
    )
    mock_post.reset_mock()
    assert obj.notify(body="hello") is True
    assert mock_post.call_count == 2

    # DM target (uses dm_url endpoint)
    mock_post.return_value = _ok()
    obj = NotifyKook(token=BOT_TOKEN, targets=[f"@{USER_ID}"])
    mock_post.reset_mock()
    assert obj.notify(body="hello") is True
    assert mock_post.call_count == 1
    call_url = mock_post.call_args[0][0]
    assert "direct-message" in call_url

    # Mixed channel + DM
    mock_post.return_value = _ok()
    obj = NotifyKook(
        token=BOT_TOKEN, targets=[CHANNEL_ID, f"@{USER_ID}"]
    )
    mock_post.reset_mock()
    assert obj.notify(body="hello") is True
    assert mock_post.call_count == 2

    # HTTP 500 on one target -> has_error=True -> False
    mock_post.return_value = _err()
    obj = NotifyKook(token=BOT_TOKEN, targets=[CHANNEL_ID])
    assert obj.notify(body="hello") is False

    # Unknown HTTP code
    mock_post.return_value = _err(code=999)
    assert obj.notify(body="hello") is False

    # API-level error code
    r = mock.Mock()
    r.status_code = requests.codes.ok
    r.content = dumps({"code": 40001, "message": "error"}).encode()
    mock_post.return_value = r
    assert obj.notify(body="hello") is False

    # RequestException
    mock_post.side_effect = requests.RequestException("boom")
    obj = NotifyKook(token=BOT_TOKEN, targets=[CHANNEL_ID])
    assert obj.notify(body="hello") is False
    mock_post.side_effect = None

    # Partial failure: first channel fails, second would succeed,
    # but has_error is still True so overall False
    obj = NotifyKook(
        token=BOT_TOKEN, targets=[CHANNEL_ID, CHANNEL_ID2]
    )
    mock_post.side_effect = [_err(), _ok()]
    assert obj.notify(body="hello") is False
    mock_post.side_effect = None

    # msg_type=text uses Kook type integer 1 in the payload
    mock_post.return_value = _ok()
    obj = NotifyKook(
        token=BOT_TOKEN, targets=[CHANNEL_ID], msg_type="text"
    )
    mock_post.reset_mock()
    assert obj.notify(body="hello") is True
    import json
    payload = json.loads(mock_post.call_args[1]["data"])
    assert payload["type"] == 1

    # Default (kmarkdown) uses Kook type integer 9
    mock_post.return_value = _ok()
    obj = NotifyKook(token=BOT_TOKEN, targets=[CHANNEL_ID])
    mock_post.reset_mock()
    assert obj.notify(body="hello") is True
    payload = json.loads(mock_post.call_args[1]["data"])
    assert payload["type"] == 9


# -----------------------------------------------------------------------
# Attachment tests
# -----------------------------------------------------------------------


@mock.patch("requests.post")
def test_plugin_kook_attachments_success(mock_post):
    """Attachment upload succeeds and a follow-up message is posted."""

    def _ok(cdn_url="https://img.kookapp.cn/assets/test.png"):
        r = mock.Mock()
        r.status_code = requests.codes.ok
        r.content = dumps({
            "code": 0, "data": {"url": cdn_url},
        }).encode()
        return r

    # call order: (1) text message, (2) CDN upload, (3) attach-msg POST
    mock_post.side_effect = [_ok(), _ok(), _ok()]

    attach = AppriseAttachment(
        os.path.join(TEST_VAR_DIR, "apprise-test.png")
    )

    obj = NotifyKook(token=BOT_TOKEN, targets=[CHANNEL_ID])
    assert obj.notify(body="hello", attach=attach) is True
    assert mock_post.call_count == 3


@mock.patch("requests.post")
def test_plugin_kook_attachments_inaccessible(mock_post):
    """Attachment that cannot be accessed returns False without HTTP call."""
    mock_post.return_value = mock.Mock(
        status_code=requests.codes.ok,
        content=dumps({"code": 0}).encode(),
    )

    attach = AppriseAttachment(
        os.path.join(TEST_VAR_DIR, "apprise-test.png")
    )

    obj = NotifyKook(token=BOT_TOKEN, targets=[CHANNEL_ID])

    with mock.patch("os.path.isfile", return_value=False):
        # Text message succeeds; attachment upload returns None -> False
        assert obj.notify(body="hello", attach=attach) is False


@mock.patch("requests.post")
def test_plugin_kook_attachments_oserror(mock_post):
    """OSError on attachment open is handled gracefully."""
    # Text message POST returns ok
    mock_post.return_value = mock.Mock(
        status_code=requests.codes.ok,
        content=dumps({"code": 0}).encode(),
    )

    attach = AppriseAttachment(
        os.path.join(TEST_VAR_DIR, "apprise-test.png")
    )

    obj = NotifyKook(token=BOT_TOKEN, targets=[CHANNEL_ID])

    with mock.patch("builtins.open", side_effect=OSError("read error")):
        assert obj.notify(body="hello", attach=attach) is False


@mock.patch("requests.post")
def test_plugin_kook_attachments_upload_http_error(mock_post):
    """HTTP error during CDN upload returns False."""
    ok_resp = mock.Mock()
    ok_resp.status_code = requests.codes.ok
    ok_resp.content = dumps({"code": 0}).encode()

    upload_err = mock.Mock()
    upload_err.status_code = requests.codes.internal_server_error
    upload_err.content = b""

    # Text message OK, then upload fails
    mock_post.side_effect = [ok_resp, upload_err]

    attach = AppriseAttachment(
        os.path.join(TEST_VAR_DIR, "apprise-test.png")
    )

    obj = NotifyKook(token=BOT_TOKEN, targets=[CHANNEL_ID])
    assert obj.notify(body="hello", attach=attach) is False


@mock.patch("requests.post")
def test_plugin_kook_attachments_upload_no_url(mock_post):
    """CDN upload returns HTTP 200 but no URL in response body -> False."""
    ok_resp = mock.Mock()
    ok_resp.status_code = requests.codes.ok
    ok_resp.content = dumps({"code": 0}).encode()

    no_url_resp = mock.Mock()
    no_url_resp.status_code = requests.codes.ok
    no_url_resp.content = dumps({"code": 0, "data": {}}).encode()

    mock_post.side_effect = [ok_resp, no_url_resp]

    attach = AppriseAttachment(
        os.path.join(TEST_VAR_DIR, "apprise-test.png")
    )

    obj = NotifyKook(token=BOT_TOKEN, targets=[CHANNEL_ID])
    assert obj.notify(body="hello", attach=attach) is False


@mock.patch("requests.post")
def test_plugin_kook_attachments_upload_request_exception(mock_post):
    """RequestException during CDN upload returns False."""
    ok_resp = mock.Mock()
    ok_resp.status_code = requests.codes.ok
    ok_resp.content = dumps({"code": 0}).encode()

    mock_post.side_effect = [
        ok_resp,
        requests.RequestException("upload error"),
    ]

    attach = AppriseAttachment(
        os.path.join(TEST_VAR_DIR, "apprise-test.png")
    )

    obj = NotifyKook(token=BOT_TOKEN, targets=[CHANNEL_ID])
    assert obj.notify(body="hello", attach=attach) is False


@mock.patch("requests.post")
def test_plugin_kook_attachments_post_http_error(mock_post):
    """HTTP error when posting attachment message returns False."""

    def _ok(cdn_url="https://img.kookapp.cn/assets/test.png"):
        r = mock.Mock()
        r.status_code = requests.codes.ok
        r.content = dumps({
            "code": 0, "data": {"url": cdn_url},
        }).encode()
        return r

    err_resp = mock.Mock()
    err_resp.status_code = requests.codes.internal_server_error
    err_resp.content = b""

    # Text message OK, CDN upload OK, attachment-message POST fails
    mock_post.side_effect = [_ok(), _ok(), err_resp]

    attach = AppriseAttachment(
        os.path.join(TEST_VAR_DIR, "apprise-test.png")
    )

    obj = NotifyKook(token=BOT_TOKEN, targets=[CHANNEL_ID])
    assert obj.notify(body="hello", attach=attach) is False


@mock.patch("requests.post")
def test_plugin_kook_attachments_post_request_exception(mock_post):
    """RequestException when posting attachment message returns False."""

    def _ok(cdn_url="https://img.kookapp.cn/assets/test.png"):
        r = mock.Mock()
        r.status_code = requests.codes.ok
        r.content = dumps({
            "code": 0, "data": {"url": cdn_url},
        }).encode()
        return r

    # Text message OK, CDN upload OK, attachment-message POST raises
    mock_post.side_effect = [
        _ok(),
        _ok(),
        requests.RequestException("post error"),
    ]

    attach = AppriseAttachment(
        os.path.join(TEST_VAR_DIR, "apprise-test.png")
    )

    obj = NotifyKook(token=BOT_TOKEN, targets=[CHANNEL_ID])
    assert obj.notify(body="hello", attach=attach) is False


@mock.patch("requests.post")
def test_plugin_kook_attachments_image_and_file(mock_post):
    """Image attachment uses type=2; non-image uses type=4."""
    import json as _json

    def _ok(cdn_url="https://img.kookapp.cn/assets/f"):
        r = mock.Mock()
        r.status_code = requests.codes.ok
        r.content = dumps({
            "code": 0, "data": {"url": cdn_url},
        }).encode()
        return r

    obj = NotifyKook(token=BOT_TOKEN, targets=[CHANNEL_ID])

    # --- Image attachment (PNG) ---
    # call order: text-msg, upload, attach-msg
    mock_post.side_effect = [_ok(), _ok(), _ok()]
    attach_img = AppriseAttachment(
        os.path.join(TEST_VAR_DIR, "apprise-test.png")
    )
    assert obj.notify(body="hello", attach=attach_img) is True
    attach_msg_payload = _json.loads(mock_post.call_args_list[2][1]["data"])
    assert attach_msg_payload["type"] == 2

    # --- Non-image attachment (mp4 file) ---
    mock_post.side_effect = [_ok(), _ok(), _ok()]
    attach_file = AppriseAttachment(
        os.path.join(TEST_VAR_DIR, "apprise-test.mp4")
    )
    mock_post.reset_mock()
    mock_post.side_effect = [_ok(), _ok(), _ok()]
    assert obj.notify(body="hello", attach=attach_file) is True
    attach_msg_payload = _json.loads(mock_post.call_args_list[2][1]["data"])
    assert attach_msg_payload["type"] == 4


@mock.patch("requests.post")
def test_plugin_kook_webhook_no_attachment_support(mock_post):
    """Webhook mode ignores attachments since attachment_support=False."""
    r = mock.Mock()
    r.status_code = requests.codes.ok
    r.content = dumps({"code": 0}).encode()
    mock_post.return_value = r

    attach = AppriseAttachment(
        os.path.join(TEST_VAR_DIR, "apprise-test.png")
    )

    obj = NotifyKook(token=WEBHOOK_KEY, mode="webhook")
    assert obj.attachment_support is False
    # Apprise framework skips attach when attachment_support=False
    assert obj.notify(body="hello", attach=attach) is True
    # Only one POST (the webhook message itself)
    assert mock_post.call_count == 1


# -----------------------------------------------------------------------
# Apprise integration test
# -----------------------------------------------------------------------


@mock.patch("requests.post")
def test_plugin_kook_invalid_json_responses(mock_post):
    """Verify invalid JSON in API responses is handled gracefully."""

    # --- _send_bot: API response with unparseable JSON (lines 493-494) ---
    # The message POST returns 200 but with invalid JSON body; the except
    # clause must handle it and fall back to code=0 (success).
    r = mock.Mock()
    r.status_code = requests.codes.ok
    r.content = b"not-json"
    mock_post.return_value = r

    obj = NotifyKook(token=BOT_TOKEN, targets=[CHANNEL_ID])
    assert obj.notify(body="hello") is True

    # --- _upload: CDN upload response with unparseable JSON (lines 660-661)
    # Text message POST returns ok with bad JSON; CDN upload also returns ok
    # with bad JSON. The except fires, cdn_url is None, send returns False.
    mock_post.return_value = r  # same bad JSON response for all calls
    obj = NotifyKook(token=BOT_TOKEN, targets=[CHANNEL_ID])
    attach = AppriseAttachment(
        os.path.join(TEST_VAR_DIR, "apprise-test.png")
    )
    # Text succeeds (code defaults to 0); CDN upload has no URL -> False
    assert obj.notify(body="hello", attach=attach) is False


@mock.patch("requests.post")
def test_plugin_kook_apprise_integration(mock_post):
    """Apprise().add() and notify() work for both modes."""
    r = mock.Mock()
    r.status_code = requests.codes.ok
    r.content = dumps({"code": 0}).encode()
    mock_post.return_value = r

    # Bot mode
    a = Apprise()
    assert a.add(f"kook://{BOT_TOKEN}/{CHANNEL_ID}") is True
    assert a.notify(title="Test", body="Message") is True

    # Webhook mode
    a = Apprise()
    assert a.add(f"kook://{WEBHOOK_KEY}/?mode=webhook") is True
    assert a.notify(body="webhook message") is True
