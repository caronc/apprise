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
from apprise.plugins.webexteams import (
    NotifyWebexTeams,
    WebexTeamsMode,
)

logging.disable(logging.CRITICAL)

# Attachment Directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), "var")

# A valid webhook token (80 lowercase alphanumeric chars)
WEBHOOK_TOKEN = "a" * 80

# A valid bot access token (longer than 160 chars, contains hyphen)
# Must be > 160 chars or contain non-alphanumeric chars to bypass
# the webhook-token regex (which only allows [a-z0-9], 80-160 chars).
# Using 200 chars ending in '0' so the privacy URL ends in '0'.
BOT_TOKEN = "Bc10" * 50  # 200 chars, ends in '0'

# A valid Webex room ID (base64url-like, 50 chars)
ROOM_ID = "Y2lzY29zcGFyazovL3VzL1JPTU9NLzEyMzQ1Njc4OTAxMjM0"
ROOM_ID2 = "Y2lzY29zcGFyazovL3VzL1JPTU9NL2FiY2RlZjEyMzQ1Njc4"

# Our Testing URLs
apprise_url_tests = (
    (
        "wxteams://",
        {
            # Token missing
            "instance": TypeError,
        },
    ),
    (
        "wxteams://:@/",
        {
            # We don't have strict host checking on for wxteams, so this
            # URL actually becomes parseable and :@ becomes a hostname.
            # The below errors because a second token wasn't found
            "instance": TypeError,
        },
    ),
    (
        "wxteams://{}".format("a" * 80),
        {
            # webhook token provided - we're good
            "instance": NotifyWebexTeams,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "wxteams://a...a/",
        },
    ),
    (
        "wxteams://?token={}".format("a" * 80),
        {
            # token as query param - we're good
            "instance": NotifyWebexTeams,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "wxteams://a...a/",
        },
    ),
    (
        "webex://{}".format("a" * 140),
        {
            # token provided via 'webex' schema - we're good
            "instance": NotifyWebexTeams,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "wxteams://a...a/",
        },
    ),
    # Support Native Webhook URLs
    (
        "https://api.ciscospark.com/v1/webhooks/incoming/{}".format("a" * 80),
        {
            # token provided - we're good
            "instance": NotifyWebexTeams,
        },
    ),
    # Support New Native Webhook URLs
    (
        "https://webexapis.com/v1/webhooks/incoming/{}".format("a" * 100),
        {
            # token provided - we're good
            "instance": NotifyWebexTeams,
        },
    ),
    # Support Native Webhook URLs with arguments
    (
        "https://api.ciscospark.com/v1/webhooks/incoming/{}"
        "?format=text".format("a" * 80),
        {
            # token provided - we're good
            "instance": NotifyWebexTeams,
        },
    ),
    # Bot mode: access_token + room ID
    (
        "wxteams://{}/{}".format(BOT_TOKEN, ROOM_ID),
        {
            "instance": NotifyWebexTeams,
            "privacy_url": "wxteams://B...0/",
        },
    ),
    # Bot mode: explicit mode=bot with no room IDs - loads but fails to send
    (
        "wxteams://{}?mode=bot".format("a" * 80),
        {
            "instance": NotifyWebexTeams,
            # notify() returns False with no targets (no HTTP call needed)
            "notify_response": False,
        },
    ),
    # Explicit mode=webhook with a valid webhook token
    (
        "wxteams://{}?mode=webhook".format("a" * 80),
        {
            "instance": NotifyWebexTeams,
            "privacy_url": "wxteams://a...a/",
        },
    ),
    # Invalid mode
    (
        "wxteams://{}?mode=invalid".format("a" * 80),
        {
            "instance": TypeError,
        },
    ),
    # Webhook mode: HTTP 500 response
    (
        "wxteams://{}".format("a" * 80),
        {
            "instance": NotifyWebexTeams,
            "response": False,
            "requests_response_code": (requests.codes.internal_server_error),
        },
    ),
    # Webhook mode: unusual HTTP response code
    (
        "wxteams://{}".format("a" * 80),
        {
            "instance": NotifyWebexTeams,
            # throw a bizarre code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    # Webhook mode: request exception
    (
        "wxteams://{}".format("a" * 80),
        {
            "instance": NotifyWebexTeams,
            # Throws a series of i/o exceptions with this flag set and
            # tests that we gracefully handle them
            "test_requests_exceptions": True,
        },
    ),
    # Bot mode: HTTP 500 response
    (
        "wxteams://{}/{}".format(BOT_TOKEN, ROOM_ID),
        {
            "instance": NotifyWebexTeams,
            "response": False,
            "requests_response_code": (requests.codes.internal_server_error),
        },
    ),
    # Bot mode: unusual HTTP response code
    (
        "wxteams://{}/{}".format(BOT_TOKEN, ROOM_ID),
        {
            "instance": NotifyWebexTeams,
            "response": False,
            "requests_response_code": 999,
        },
    ),
    # Bot mode: request exception
    (
        "wxteams://{}/{}".format(BOT_TOKEN, ROOM_ID),
        {
            "instance": NotifyWebexTeams,
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_webex_teams_urls():
    """NotifyWebexTeams() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


def test_plugin_webex_teams_webhook_mode():
    """NotifyWebexTeams() Webhook mode direct tests."""

    # Valid webhook token
    token = "b" * 80

    obj = NotifyWebexTeams(token=token)
    assert isinstance(obj, NotifyWebexTeams)
    assert obj.mode == WebexTeamsMode.WEBHOOK

    # url() round-trip
    url = obj.url()
    assert "wxteams://" in url
    assert "mode=webhook" in url

    # parse_url round-trip
    result = NotifyWebexTeams.parse_url(url)
    assert result is not None
    obj2 = NotifyWebexTeams(**result)
    assert obj2.mode == WebexTeamsMode.WEBHOOK
    assert obj2.token == token

    # privacy URL
    priv = obj.url(privacy=True)
    assert obj.token not in priv

    # url_identifier
    assert obj.url_identifier == (
        NotifyWebexTeams.secure_protocol[0],
        token,
    )

    # 80-char token (minimum)
    assert NotifyWebexTeams(token="c" * 80)
    # 160-char token (maximum)
    assert NotifyWebexTeams(token="c" * 160)

    # Too short for webhook -> falls to bot mode (no targets), loads but
    # send() returns False
    obj_short = NotifyWebexTeams(token="c" * 79)
    assert obj_short.mode == WebexTeamsMode.BOT
    assert obj_short.send(body="test") is False

    # Too long for webhook -> bot mode, same behaviour
    obj_long = NotifyWebexTeams(token="c" * 161)
    assert obj_long.mode == WebexTeamsMode.BOT
    assert obj_long.send(body="test") is False

    # No token -> TypeError (no candidate at all)
    with pytest.raises(TypeError):
        NotifyWebexTeams(token=None)

    # Empty token -> TypeError
    with pytest.raises(TypeError):
        NotifyWebexTeams(token="")

    # Non-alphanumeric chars -> falls to bot mode (no targets)
    obj_hyph = NotifyWebexTeams(token="a-b-" * 20)
    assert obj_hyph.mode == WebexTeamsMode.BOT
    assert obj_hyph.send(body="test") is False


def test_plugin_webex_teams_bot_mode():
    """NotifyWebexTeams() Bot mode direct tests."""

    obj = NotifyWebexTeams(access_token=BOT_TOKEN, targets=[ROOM_ID])
    assert isinstance(obj, NotifyWebexTeams)
    assert obj.mode == WebexTeamsMode.BOT
    assert obj.access_token == BOT_TOKEN
    assert ROOM_ID in obj.targets

    # url() round-trip
    url = obj.url()
    assert "wxteams://" in url
    assert "mode=bot" in url

    result = NotifyWebexTeams.parse_url(url)
    assert result is not None
    obj2 = NotifyWebexTeams(**result)
    assert obj2.mode == WebexTeamsMode.BOT
    assert obj2.access_token == BOT_TOKEN
    assert ROOM_ID in obj2.targets

    # privacy URL masks the token
    priv = obj.url(privacy=True)
    assert BOT_TOKEN not in priv

    # url_identifier
    assert obj.url_identifier == (
        NotifyWebexTeams.secure_protocol[0],
        BOT_TOKEN,
    )

    # Multiple rooms
    obj3 = NotifyWebexTeams(
        access_token=BOT_TOKEN, targets=[ROOM_ID, ROOM_ID2]
    )
    assert len(obj3.targets) == 2

    # No room IDs -> loads fine, but send() returns False
    obj_no_rooms = NotifyWebexTeams(access_token=BOT_TOKEN, targets=[])
    assert isinstance(obj_no_rooms, NotifyWebexTeams)
    assert obj_no_rooms.send(body="test") is False

    # No access_token -> TypeError
    with pytest.raises(TypeError):
        NotifyWebexTeams(access_token=None, targets=[ROOM_ID])

    # Explicit bot mode with neither token nor access_token -> TypeError
    with pytest.raises(TypeError):
        NotifyWebexTeams(mode="bot", targets=[ROOM_ID])

    # Explicit mode=bot on a short (webhook-style) token
    obj4 = NotifyWebexTeams(token="a" * 80, mode="bot", targets=[ROOM_ID])
    assert obj4.mode == WebexTeamsMode.BOT
    # The 'token' argument is used as access_token in bot mode
    assert obj4.access_token == "a" * 80

    # Invalid mode
    with pytest.raises(TypeError):
        NotifyWebexTeams(
            access_token=BOT_TOKEN,
            targets=[ROOM_ID],
            mode="invalid",
        )


def test_plugin_webex_teams_body_maxlen():
    """NotifyWebexTeams() body_maxlen varies by mode."""

    # Webhook mode: 1000 chars
    obj = NotifyWebexTeams(token=WEBHOOK_TOKEN)
    assert obj.body_maxlen == 1000

    # Bot mode: 7439 chars
    obj = NotifyWebexTeams(access_token=BOT_TOKEN, targets=[ROOM_ID])
    assert obj.body_maxlen == 7439


def test_plugin_webex_teams_mode_detection():
    """NotifyWebexTeams() auto-detects mode from token format."""

    # 80-char lowercase alphanumeric -> WEBHOOK
    obj = NotifyWebexTeams(token="a" * 80)
    assert obj.mode == WebexTeamsMode.WEBHOOK

    # 80-char uppercase alphanumeric also matches webhook regex
    # (regex uses 'i' flag); no targets means webhook mode
    obj = NotifyWebexTeams(token="A" * 80)
    assert obj.mode == WebexTeamsMode.WEBHOOK

    # Token longer than 160 chars -> fails webhook regex -> BOT
    obj = NotifyWebexTeams(token="a" * 200, targets=[ROOM_ID])
    assert obj.mode == WebexTeamsMode.BOT

    # Token with hyphens (non-alphanumeric) -> fails webhook regex -> BOT
    obj = NotifyWebexTeams(access_token=BOT_TOKEN, targets=[ROOM_ID])
    assert obj.mode == WebexTeamsMode.BOT


def test_plugin_webex_teams_url_parsing():
    """NotifyWebexTeams() URL parsing edge cases."""

    # Webhook via ?token= param
    result = NotifyWebexTeams.parse_url("wxteams://?token={}".format("a" * 80))
    assert result is not None
    obj = NotifyWebexTeams(**result)
    assert obj.mode == WebexTeamsMode.WEBHOOK
    assert obj.token == "a" * 80

    # Bot mode: access_token in host, room ID in path
    result = NotifyWebexTeams.parse_url(
        "wxteams://{}/{}".format(BOT_TOKEN, ROOM_ID)
    )
    assert result is not None
    obj = NotifyWebexTeams(**result)
    assert obj.mode == WebexTeamsMode.BOT
    assert ROOM_ID in obj.targets

    # Bot mode: multiple room IDs in path
    result = NotifyWebexTeams.parse_url(
        "wxteams://{}/{}/{}".format(BOT_TOKEN, ROOM_ID, ROOM_ID2)
    )
    assert result is not None
    obj = NotifyWebexTeams(**result)
    assert obj.mode == WebexTeamsMode.BOT
    assert len(obj.targets) == 2

    # Bot mode: room IDs via ?to= param
    result = NotifyWebexTeams.parse_url(
        "wxteams://{}?to={}&mode=bot".format(BOT_TOKEN, ROOM_ID)
    )
    assert result is not None
    obj = NotifyWebexTeams(**result)
    assert obj.mode == WebexTeamsMode.BOT
    assert ROOM_ID in obj.targets

    # Native webhook URL
    result = NotifyWebexTeams.parse_native_url(
        "https://api.ciscospark.com/v1/webhooks/incoming/{}".format("a" * 80)
    )
    assert result is not None
    obj = NotifyWebexTeams(**result)
    assert obj.mode == WebexTeamsMode.WEBHOOK

    # New native webhook URL
    result = NotifyWebexTeams.parse_native_url(
        "https://webexapis.com/v1/webhooks/incoming/{}".format("a" * 100)
    )
    assert result is not None
    obj = NotifyWebexTeams(**result)
    assert obj.mode == WebexTeamsMode.WEBHOOK

    # parse_native_url returns None for non-matching URLs
    assert (
        NotifyWebexTeams.parse_native_url(
            "https://example.com/not/a/webex/url"
        )
        is None
    )

    # Webhook mode forced with ?mode=webhook even with path entries
    result = NotifyWebexTeams.parse_url(
        "wxteams://{}?mode=webhook".format("a" * 80)
    )
    assert result is not None
    obj = NotifyWebexTeams(**result)
    assert obj.mode == WebexTeamsMode.WEBHOOK


@mock.patch("requests.post")
def test_plugin_webex_teams_webhook_send(mock_post):
    """NotifyWebexTeams() Webhook send() coverage."""

    # Prepare a good response
    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = b""
    mock_post.return_value = response

    obj = NotifyWebexTeams(token=WEBHOOK_TOKEN)

    # Successful send
    assert obj.send(body="test message") is True
    assert mock_post.call_count == 1
    call_url = mock_post.call_args[0][0]
    assert "webhooks/incoming" in call_url
    assert WEBHOOK_TOKEN in call_url

    # Verify correct Content-Type header
    headers = mock_post.call_args[1]["headers"]
    assert headers["Content-Type"] == "application/json"

    mock_post.reset_mock()

    # 204 No Content is also acceptable
    response.status_code = requests.codes.no_content
    assert obj.send(body="test") is True

    mock_post.reset_mock()

    # HTTP error
    response.status_code = requests.codes.internal_server_error
    assert obj.send(body="test") is False

    mock_post.reset_mock()

    # Unknown HTTP error code
    response.status_code = 999
    assert obj.send(body="test") is False

    mock_post.reset_mock()

    # Connection error
    mock_post.side_effect = requests.RequestException()
    assert obj.send(body="test") is False

    mock_post.side_effect = None
    mock_post.return_value = response
    response.status_code = requests.codes.ok

    # Webhook warns about attachments (but still proceeds)
    mock_post.reset_mock()
    path = os.path.join(TEST_VAR_DIR, "apprise-test.gif")
    attach = AppriseAttachment(path)
    assert obj.send(body="test", attach=attach) is True
    # Only one POST call: text-only webhook
    assert mock_post.call_count == 1


@mock.patch("requests.post")
def test_plugin_webex_teams_bot_send(mock_post):
    """NotifyWebexTeams() Bot send() text-only coverage."""

    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = b""
    mock_post.return_value = response

    obj = NotifyWebexTeams(access_token=BOT_TOKEN, targets=[ROOM_ID])

    # Successful text send
    assert obj.send(body="hello from bot") is True
    assert mock_post.call_count == 1
    call_url = mock_post.call_args[0][0]
    assert call_url == "https://webexapis.com/v1/messages"

    # Verify Bearer authorization
    headers = mock_post.call_args[1]["headers"]
    assert headers["Authorization"] == f"Bearer {BOT_TOKEN}"
    assert headers["Content-Type"] == "application/json"

    mock_post.reset_mock()

    # Two rooms -> two calls
    obj2 = NotifyWebexTeams(
        access_token=BOT_TOKEN, targets=[ROOM_ID, ROOM_ID2]
    )
    assert obj2.send(body="broadcast") is True
    assert mock_post.call_count == 2

    mock_post.reset_mock()

    # HTTP error for bot mode
    response.status_code = requests.codes.internal_server_error
    assert obj.send(body="test") is False

    mock_post.reset_mock()

    response.status_code = 999
    assert obj.send(body="test") is False

    mock_post.reset_mock()

    # Connection error for bot mode
    mock_post.side_effect = requests.RequestException()
    assert obj.send(body="test") is False

    mock_post.side_effect = None
    response.status_code = requests.codes.ok
    mock_post.return_value = response

    # Two rooms: second fails -> overall failure reported
    mock_post.reset_mock()
    fail_response = mock.Mock()
    fail_response.status_code = requests.codes.internal_server_error
    fail_response.content = b""

    mock_post.side_effect = [response, fail_response]
    obj2 = NotifyWebexTeams(
        access_token=BOT_TOKEN, targets=[ROOM_ID, ROOM_ID2]
    )
    assert obj2.send(body="test") is False


@mock.patch("requests.post")
def test_plugin_webex_teams_bot_attachments(mock_post):
    """NotifyWebexTeams() Bot mode attachment coverage."""

    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = b""
    mock_post.return_value = response

    obj = NotifyWebexTeams(access_token=BOT_TOKEN, targets=[ROOM_ID])

    path = os.path.join(TEST_VAR_DIR, "apprise-test.gif")
    attach = AppriseAttachment(path)

    # Successful single attachment
    mock_post.reset_mock()
    assert (
        obj.notify(
            body="see attached",
            title="",
            notify_type=NotifyType.INFO,
            attach=attach,
        )
        is True
    )
    # One POST call for the single attachment
    assert mock_post.call_count == 1
    call_url = mock_post.call_args[0][0]
    assert call_url == "https://webexapis.com/v1/messages"
    # No Content-Type header set (multipart sets its own)
    headers = mock_post.call_args[1]["headers"]
    assert "Content-Type" not in headers
    # files kwarg was provided
    assert mock_post.call_args[1].get("files") is not None

    # Multiple attachments -> one POST per attachment
    mock_post.reset_mock()
    path2 = os.path.join(TEST_VAR_DIR, "apprise-test.png")
    attach2 = AppriseAttachment([path, path2])
    assert obj.send(body="two files", attach=attach2) is True
    assert mock_post.call_count == 2

    # Two rooms, one attachment -> 2 POST calls
    mock_post.reset_mock()
    obj2 = NotifyWebexTeams(
        access_token=BOT_TOKEN, targets=[ROOM_ID, ROOM_ID2]
    )
    assert obj2.send(body="room broadcast", attach=attach) is True
    assert mock_post.call_count == 2

    # Connection error on attachment POST
    mock_post.reset_mock()
    mock_post.side_effect = requests.RequestException()
    assert obj.send(body="test", attach=attach) is False

    mock_post.side_effect = None
    mock_post.return_value = response

    # OSError reading attachment
    mock_post.reset_mock()
    mock_post.side_effect = OSError()
    assert obj.send(body="test", attach=attach) is False

    mock_post.side_effect = None
    mock_post.return_value = response

    # HTTP error on attachment upload
    mock_post.reset_mock()
    bad_response = mock.Mock()
    bad_response.status_code = requests.codes.internal_server_error
    bad_response.content = b""
    mock_post.return_value = bad_response
    assert obj.send(body="test", attach=attach) is False

    mock_post.return_value = response

    # OSError raised by attachment.open() (before the file handle is used)
    mock_post.reset_mock()
    mock_post.side_effect = None
    with mock.patch(
        "apprise.attachment.file.AttachFile.open",
        side_effect=OSError("open failed"),
    ):
        assert obj.send(body="test", attach=attach) is False
    mock_post.side_effect = None
    mock_post.return_value = response

    # Invalid/inaccessible attachment
    mock_post.reset_mock()
    invalid_path = os.path.join(TEST_VAR_DIR, "/invalid/path/to/file.jpg")
    bad_attach = AppriseAttachment(invalid_path)
    assert (
        obj.notify(
            body="test",
            notify_type=NotifyType.INFO,
            attach=bad_attach,
        )
        is False
    )
    # No POST should have been made
    assert mock_post.call_count == 0


@mock.patch("requests.post")
def test_plugin_webex_teams_apprise_integration(mock_post):
    """NotifyWebexTeams() Apprise.notify() integration."""

    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = b""
    mock_post.return_value = response

    # Webhook mode via Apprise
    app = Apprise()
    assert app.add("wxteams://{}".format(WEBHOOK_TOKEN))
    assert app.notify(body="webhook test") is True

    mock_post.reset_mock()

    # Bot mode via Apprise
    app2 = Apprise()
    assert app2.add("wxteams://{}/{}".format(BOT_TOKEN, ROOM_ID))
    assert app2.notify(body="bot test") is True
