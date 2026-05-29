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
from urllib.parse import urlparse

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise, AppriseAttachment
from apprise.plugins.groupme import NotifyGroupMe

logging.disable(logging.CRITICAL)

# Attachment directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), "var")

# Realistic test credentials
TEST_BOT_ID = "68ca900a7d17f9b9891a73af2a"
TEST_TOKEN = "abc123def456gh789ijklmn0op"

# A valid image URL returned by the GroupMe image service
TEST_IMAGE_URL = "https://i.groupme.com/somethingsomething.large"

# Fake image-service response payload
IMAGE_UPLOAD_RESP = b'{"payload":{"url":"' + TEST_IMAGE_URL.encode() + b'"}}'


# Our Testing URLs
apprise_url_tests = (
    (
        # No bot_id
        "groupme://",
        {
            "instance": TypeError,
        },
    ),
    (
        # Empty URL
        "groupme://:@/",
        {
            "instance": TypeError,
        },
    ),
    (
        # Invalid bot_id containing non-hex characters
        "groupme://not-a-valid-bot-id!",
        {
            "instance": TypeError,
        },
    ),
    (
        # Valid bot_id (text only)
        "groupme://{}".format(TEST_BOT_ID),
        {
            "instance": NotifyGroupMe,
            "privacy_url": "groupme://6...a/",
        },
    ),
    (
        # bot_id via query string
        "groupme://?bot_id={}".format(TEST_BOT_ID),
        {
            "instance": NotifyGroupMe,
        },
    ),
    (
        # Access token in the path (canonical form with attachments)
        "groupme://{}/{}".format(TEST_BOT_ID, TEST_TOKEN),
        {
            "instance": NotifyGroupMe,
            "privacy_url": "groupme://6...a/",
            # Image upload fails under URL tester mock (no payload.url)
            "attach_response": False,
        },
    ),
    (
        # Access token supplied via ?token= query parameter (alias form)
        "groupme://{}?token={}".format(TEST_BOT_ID, TEST_TOKEN),
        {
            "instance": NotifyGroupMe,
            # Image upload fails under URL tester mock (no payload.url)
            "attach_response": False,
        },
    ),
    (
        # HTTP 500 response
        "groupme://{}".format(TEST_BOT_ID),
        {
            "instance": NotifyGroupMe,
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        # Unknown response code
        "groupme://{}".format(TEST_BOT_ID),
        {
            "instance": NotifyGroupMe,
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        # Request exception
        "groupme://{}".format(TEST_BOT_ID),
        {
            "instance": NotifyGroupMe,
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_groupme_urls():
    """NotifyGroupMe() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.post")
def test_plugin_groupme_init(mock_post):
    """NotifyGroupMe() Initialization checks."""

    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.accepted

    # Missing bot_id raises TypeError
    with pytest.raises(TypeError):
        NotifyGroupMe(bot_id=None)

    # Blank bot_id raises TypeError
    with pytest.raises(TypeError):
        NotifyGroupMe(bot_id="")

    # bot_id with invalid characters raises TypeError
    with pytest.raises(TypeError):
        NotifyGroupMe(bot_id="not-valid!")

    # Valid bot_id instantiates without error
    obj = NotifyGroupMe(bot_id=TEST_BOT_ID)
    assert isinstance(obj, NotifyGroupMe)
    assert obj.bot_id == TEST_BOT_ID
    assert obj.token is None

    # Valid bot_id + token
    obj = NotifyGroupMe(bot_id=TEST_BOT_ID, token=TEST_TOKEN)
    assert isinstance(obj, NotifyGroupMe)
    assert obj.bot_id == TEST_BOT_ID
    assert obj.token == TEST_TOKEN


@mock.patch("requests.post")
def test_plugin_groupme_send(mock_post):
    """NotifyGroupMe() Send checks."""

    def _mk_resp(code, content=b""):
        """Build a mock response."""
        resp = requests.Request()
        resp.status_code = code
        resp.content = content
        return resp

    # 202 Accepted is the expected success code
    mock_post.return_value = _mk_resp(requests.codes.accepted)

    obj = NotifyGroupMe(bot_id=TEST_BOT_ID)
    assert isinstance(obj, NotifyGroupMe)

    # Successful send
    assert obj.notify(body="Test message") is True
    assert mock_post.call_count == 1

    # Verify the correct URL host was used
    call_url = mock_post.call_args[0][0]
    assert urlparse(call_url).hostname == "api.groupme.com"

    mock_post.reset_mock()

    # 200 OK also accepted as success
    mock_post.return_value = _mk_resp(requests.codes.ok)
    assert obj.notify(body="Test message") is True

    mock_post.reset_mock()

    # HTTP 400 returns False
    mock_post.return_value = _mk_resp(requests.codes.bad_request)
    assert obj.notify(body="Test message") is False

    mock_post.reset_mock()

    # HTTP 401 returns False
    mock_post.return_value = _mk_resp(requests.codes.unauthorized)
    assert obj.notify(body="Test message") is False

    mock_post.reset_mock()

    # HTTP 404 returns False
    mock_post.return_value = _mk_resp(requests.codes.not_found)
    assert obj.notify(body="Test message") is False

    mock_post.reset_mock()

    # HTTP 429 returns False
    mock_post.return_value = _mk_resp(429)
    assert obj.notify(body="Test message") is False

    mock_post.reset_mock()

    # HTTP 500 returns False
    mock_post.return_value = _mk_resp(requests.codes.internal_server_error)
    assert obj.notify(body="Test message") is False

    mock_post.reset_mock()

    # Unknown error code returns False
    mock_post.return_value = _mk_resp(999)
    assert obj.notify(body="Test message") is False

    mock_post.reset_mock()

    # RequestException returns False
    mock_post.side_effect = requests.RequestException("Network error")
    assert obj.notify(body="Test message") is False


@mock.patch("requests.post")
def test_plugin_groupme_attach_no_token(mock_post):
    """NotifyGroupMe() warns but still sends text when token is absent."""

    def _mk_resp(code, content=b""):
        """Build a mock response."""
        resp = requests.Request()
        resp.status_code = code
        resp.content = content
        return resp

    mock_post.return_value = _mk_resp(requests.codes.accepted)

    obj = NotifyGroupMe(bot_id=TEST_BOT_ID)
    assert obj.token is None

    # Load a real attachment file
    attach = AppriseAttachment(os.path.join(TEST_VAR_DIR, "apprise-test.png"))

    # Attachment send without token -- text message still succeeds
    assert obj.notify(body="Test", attach=attach) is True

    # Only the bot POST is made (no upload call since no token)
    assert mock_post.call_count == 1


@mock.patch("requests.post")
def test_plugin_groupme_attach_success(mock_post):
    """NotifyGroupMe() image upload and attachment send succeeds."""

    def _mk_resp(code, content=b""):
        """Build a mock response."""
        resp = requests.Request()
        resp.status_code = code
        resp.content = content
        return resp

    # First call: image upload returns 200 with URL
    # Second call: bot post returns 202
    mock_post.side_effect = [
        _mk_resp(requests.codes.ok, IMAGE_UPLOAD_RESP),
        _mk_resp(requests.codes.accepted),
    ]

    obj = NotifyGroupMe(bot_id=TEST_BOT_ID, token=TEST_TOKEN)

    attach = AppriseAttachment(os.path.join(TEST_VAR_DIR, "apprise-test.png"))
    assert obj.notify(body="Test", attach=attach) is True

    # Two requests: upload + bot post
    assert mock_post.call_count == 2

    # Verify the image service URL host was called first
    upload_url = mock_post.call_args_list[0][0][0]
    assert urlparse(upload_url).hostname == "image.groupme.com"

    # Verify the bot post URL host was called second
    post_url = mock_post.call_args_list[1][0][0]
    assert urlparse(post_url).hostname == "api.groupme.com"


@mock.patch("requests.post")
def test_plugin_groupme_attach_inaccessible(mock_post):
    """NotifyGroupMe() aborts upload when attachment is inaccessible."""

    def _mk_resp(code, content=b""):
        """Build a mock response."""
        resp = requests.Request()
        resp.status_code = code
        resp.content = content
        return resp

    mock_post.return_value = _mk_resp(requests.codes.ok, IMAGE_UPLOAD_RESP)

    obj = NotifyGroupMe(bot_id=TEST_BOT_ID, token=TEST_TOKEN)

    attach = AppriseAttachment(os.path.join(TEST_VAR_DIR, "apprise-test.png"))

    # Simulate the file being inaccessible (isfile returns False)
    with mock.patch("os.path.isfile", return_value=False):
        assert obj.notify(body="Test", attach=attach) is False

    # No HTTP calls should have been made
    assert mock_post.call_count == 0


@mock.patch("requests.post")
def test_plugin_groupme_attach_oserror(mock_post):
    """NotifyGroupMe() aborts upload when open() raises OSError."""

    def _mk_resp(code, content=b""):
        """Build a mock response."""
        resp = requests.Request()
        resp.status_code = code
        resp.content = content
        return resp

    mock_post.return_value = _mk_resp(requests.codes.ok, IMAGE_UPLOAD_RESP)

    obj = NotifyGroupMe(bot_id=TEST_BOT_ID, token=TEST_TOKEN)

    attach = AppriseAttachment(os.path.join(TEST_VAR_DIR, "apprise-test.png"))

    # Simulate an I/O error when opening the file
    with mock.patch("builtins.open", side_effect=OSError("disk error")):
        assert obj.notify(body="Test", attach=attach) is False

    # No HTTP calls should have been made
    assert mock_post.call_count == 0


@mock.patch("requests.post")
def test_plugin_groupme_attach_upload_http_error(mock_post):
    """NotifyGroupMe() returns False when the image upload gets HTTP error."""

    def _mk_resp(code, content=b""):
        """Build a mock response."""
        resp = requests.Request()
        resp.status_code = code
        resp.content = content
        return resp

    # Image upload returns 401
    mock_post.return_value = _mk_resp(requests.codes.unauthorized)

    obj = NotifyGroupMe(bot_id=TEST_BOT_ID, token=TEST_TOKEN)

    attach = AppriseAttachment(os.path.join(TEST_VAR_DIR, "apprise-test.png"))
    assert obj.notify(body="Test", attach=attach) is False

    # Only the upload attempt was made (bot post never called)
    assert mock_post.call_count == 1


@mock.patch("requests.post")
def test_plugin_groupme_attach_upload_request_exception(mock_post):
    """NotifyGroupMe() returns False on RequestException during upload."""

    obj = NotifyGroupMe(bot_id=TEST_BOT_ID, token=TEST_TOKEN)

    attach = AppriseAttachment(os.path.join(TEST_VAR_DIR, "apprise-test.png"))

    # Simulate a network error during the image upload
    mock_post.side_effect = requests.RequestException("Network error")
    assert obj.notify(body="Test", attach=attach) is False

    # Only the upload attempt was made
    assert mock_post.call_count == 1


@mock.patch("requests.post")
def test_plugin_groupme_attach_bad_response(mock_post):
    """NotifyGroupMe() returns False when upload response has no URL."""

    def _mk_resp(code, content=b""):
        """Build a mock response."""
        resp = requests.Request()
        resp.status_code = code
        resp.content = content
        return resp

    # Upload returns 200 but with a response missing the URL field
    mock_post.return_value = _mk_resp(requests.codes.ok, b"{}")

    obj = NotifyGroupMe(bot_id=TEST_BOT_ID, token=TEST_TOKEN)

    attach = AppriseAttachment(os.path.join(TEST_VAR_DIR, "apprise-test.png"))
    assert obj.notify(body="Test", attach=attach) is False

    mock_post.reset_mock()

    # Upload returns 200 but with invalid JSON
    mock_post.return_value = _mk_resp(requests.codes.ok, b"not-json")
    assert obj.notify(body="Test", attach=attach) is False


@mock.patch("requests.post")
def test_plugin_groupme_attach_multi(mock_post):
    """NotifyGroupMe() sends multiple attachments in one bot post."""

    def _mk_resp(code, content=b""):
        """Build a mock response."""
        resp = requests.Request()
        resp.status_code = code
        resp.content = content
        return resp

    # Two image uploads + one bot post
    mock_post.side_effect = [
        _mk_resp(requests.codes.ok, IMAGE_UPLOAD_RESP),
        _mk_resp(requests.codes.ok, IMAGE_UPLOAD_RESP),
        _mk_resp(requests.codes.accepted),
    ]

    obj = NotifyGroupMe(bot_id=TEST_BOT_ID, token=TEST_TOKEN)

    # Load two different attachment files
    attach = AppriseAttachment()
    attach.add(os.path.join(TEST_VAR_DIR, "apprise-test.png"))
    attach.add(os.path.join(TEST_VAR_DIR, "apprise-test.jpeg"))

    assert obj.notify(body="Test", attach=attach) is True

    # 2 uploads + 1 bot post
    assert mock_post.call_count == 3


@mock.patch("requests.post")
def test_plugin_groupme_url_roundtrip(mock_post):
    """NotifyGroupMe() URL round-trip invariant."""

    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.accepted

    # Without token
    obj1 = NotifyGroupMe(bot_id=TEST_BOT_ID)
    results = NotifyGroupMe.parse_url(obj1.url())
    assert results is not None
    obj2 = NotifyGroupMe(**results)
    assert obj1.url_identifier == obj2.url_identifier
    assert obj1.bot_id == obj2.bot_id

    # With token
    obj3 = NotifyGroupMe(bot_id=TEST_BOT_ID, token=TEST_TOKEN)
    results = NotifyGroupMe.parse_url(obj3.url())
    assert results is not None
    obj4 = NotifyGroupMe(**results)
    assert obj3.url_identifier == obj4.url_identifier
    assert obj3.bot_id == obj4.bot_id
    assert obj3.token == obj4.token


@mock.patch("requests.post")
def test_plugin_groupme_url_parsing(mock_post):
    """NotifyGroupMe() URL parsing checks."""

    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.accepted

    # Standard URL (no token)
    results = NotifyGroupMe.parse_url("groupme://{}".format(TEST_BOT_ID))
    assert results is not None
    assert results["bot_id"] == TEST_BOT_ID
    assert not results.get("token")

    # Token in path (canonical form)
    results = NotifyGroupMe.parse_url(
        "groupme://{}/{}".format(TEST_BOT_ID, TEST_TOKEN)
    )
    assert results is not None
    assert results["bot_id"] == TEST_BOT_ID
    assert results["token"] == TEST_TOKEN

    # Token via ?token= query parameter (alias form)
    results = NotifyGroupMe.parse_url(
        "groupme://{}?token={}".format(TEST_BOT_ID, TEST_TOKEN)
    )
    assert results is not None
    assert results["bot_id"] == TEST_BOT_ID
    assert results["token"] == TEST_TOKEN

    # ?token= overrides path-supplied token
    other_token = "zzz999yyy888xxx777"
    results = NotifyGroupMe.parse_url(
        "groupme://{}/{}?token={}".format(TEST_BOT_ID, TEST_TOKEN, other_token)
    )
    assert results is not None
    assert results["token"] == other_token

    # ?bot_id= query override
    results = NotifyGroupMe.parse_url(
        "groupme://ignored?bot_id={}".format(TEST_BOT_ID)
    )
    assert results is not None
    assert results["bot_id"] == TEST_BOT_ID

    # None URL returns None
    assert NotifyGroupMe.parse_url(None) is None


@mock.patch("requests.post")
def test_plugin_groupme_privacy_url(mock_post):
    """NotifyGroupMe() privacy URL masks credentials."""

    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.accepted

    obj = NotifyGroupMe(bot_id=TEST_BOT_ID, token=TEST_TOKEN)

    privacy = obj.url(privacy=True)
    assert TEST_BOT_ID not in privacy
    assert TEST_TOKEN not in privacy
    assert privacy.startswith("groupme://")


@mock.patch("requests.post")
def test_plugin_groupme_url_identifier(mock_post):
    """NotifyGroupMe() url_identifier uniqueness."""

    obj1 = NotifyGroupMe(bot_id=TEST_BOT_ID)
    obj2 = NotifyGroupMe(bot_id=TEST_BOT_ID)
    assert obj1.url_identifier == obj2.url_identifier

    # Different bot_id produces a different identifier
    obj3 = NotifyGroupMe(bot_id="aabbccddeeff00112233445566")
    assert obj1.url_identifier != obj3.url_identifier

    # token must not affect the identifier
    obj4 = NotifyGroupMe(bot_id=TEST_BOT_ID, token=TEST_TOKEN)
    assert obj1.url_identifier == obj4.url_identifier

    # Schema is the first element
    assert obj1.url_identifier[0] == NotifyGroupMe.secure_protocol
    assert obj1.url_identifier[1] == TEST_BOT_ID


@mock.patch("requests.post")
def test_plugin_groupme_apprise_integration(mock_post):
    """NotifyGroupMe() Apprise integration."""

    def _mk_resp(code, content=b""):
        """Build a mock response."""
        resp = requests.Request()
        resp.status_code = code
        resp.content = content
        return resp

    mock_post.return_value = _mk_resp(requests.codes.accepted)

    # Load via Apprise URL
    a = Apprise()
    assert a.add("groupme://{}".format(TEST_BOT_ID)) is True
    assert len(a) == 1
    assert isinstance(a[0], NotifyGroupMe)

    assert a.notify(body="Test", title="Title") is True
    assert mock_post.call_count == 1

    mock_post.reset_mock()

    # Load with token
    a2 = Apprise()
    assert (
        a2.add("groupme://{}?token={}".format(TEST_BOT_ID, TEST_TOKEN)) is True
    )
    assert len(a2) == 1
    assert isinstance(a2[0], NotifyGroupMe)

    mock_post.return_value = _mk_resp(requests.codes.accepted)
    assert a2.notify(body="Test", title="Title") is True
    assert mock_post.call_count == 1

    mock_post.reset_mock()

    # Failure response
    mock_post.return_value = _mk_resp(requests.codes.internal_server_error)
    assert a.notify(body="Test") is False
