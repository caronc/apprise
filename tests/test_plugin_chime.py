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
from json import loads
import logging
from unittest import mock

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise, NotifyFormat
from apprise.plugins.chime import NotifyChime

logging.disable(logging.CRITICAL)

# Fake but realistic-looking credentials
TEST_WEBHOOK_ID = "aabbccdd-1234-5678-abcd-ef1234567890"
TEST_TOKEN = "AaBbCcDdEeFf1234567890=="


# Our Testing URLs
apprise_url_tests = (
    (
        # No webhook_id or token
        "chime://",
        {
            "instance": TypeError,
        },
    ),
    (
        # Empty URL
        "chime://:@/",
        {
            "instance": TypeError,
        },
    ),
    (
        # Webhook ID supplied but no token
        "chime://aabbccdd-1234-5678-abcd-ef1234567890",
        {
            "instance": TypeError,
        },
    ),
    (
        # Valid webhook_id + token in path (token has base64 padding)
        "chime://aabbccdd-1234-5678-abcd-ef1234567890/AaBbCcDd1234%3D%3D",
        {
            "instance": NotifyChime,
            # Expected privacy URL prefix; pprint shows the decoded token
            # character, so the trailing = of AaBbCcDd1234== appears as =
            "privacy_url": "chime://a...0/A...=/",
        },
    ),
    (
        # Webhook token supplied via query string
        "chime://aabbccdd-1234-5678-abcd-ef1234567890"
        "?token=AaBbCcDd1234%3D%3D",
        {
            "instance": NotifyChime,
        },
    ),
    (
        # Webhook ID supplied via query string
        "chime://?webhook_id=aabbccdd-1234-5678-abcd-ef1234567890"
        "&token=AaBbCcDd1234%3D%3D",
        {
            "instance": NotifyChime,
        },
    ),
    (
        # Valid credentials; HTTP 500 response
        "chime://aabbccdd-1234-5678-abcd-ef1234567890/AaBbCcDd1234%3D%3D",
        {
            "instance": NotifyChime,
            "response": False,
            "requests_response_code": (requests.codes.internal_server_error),
        },
    ),
    (
        # Valid credentials; unknown response code
        "chime://aabbccdd-1234-5678-abcd-ef1234567890/AaBbCcDd1234%3D%3D",
        {
            "instance": NotifyChime,
            # throw a bizarre code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        # Valid credentials; request exceptions
        "chime://aabbccdd-1234-5678-abcd-ef1234567890/AaBbCcDd1234%3D%3D",
        {
            "instance": NotifyChime,
            # Throws a series of i/o exceptions with this flag set
            # and tests that we gracefully handle them
            "test_requests_exceptions": True,
        },
    ),
    (
        # Native Chime webhook URL
        "https://hooks.chime.aws/incomingwebhooks/"
        "aabbccdd-1234-5678-abcd-ef1234567890"
        "?token=AaBbCcDd1234%3D%3D",
        {
            "instance": NotifyChime,
        },
    ),
)


def test_plugin_chime_urls():
    """NotifyChime() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.post")
def test_plugin_chime_init(mock_post):
    """NotifyChime() Initialization Checks."""

    # Prepare a valid mock response
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok

    # Missing webhook_id raises TypeError
    with pytest.raises(TypeError):
        NotifyChime(webhook_id=None, token=TEST_TOKEN)

    # Blank webhook_id raises TypeError
    with pytest.raises(TypeError):
        NotifyChime(webhook_id="  ", token=TEST_TOKEN)

    # Missing token raises TypeError
    with pytest.raises(TypeError):
        NotifyChime(webhook_id=TEST_WEBHOOK_ID, token=None)

    # Blank token raises TypeError
    with pytest.raises(TypeError):
        NotifyChime(webhook_id=TEST_WEBHOOK_ID, token="  ")

    # Valid object instantiates without error
    obj = NotifyChime(webhook_id=TEST_WEBHOOK_ID, token=TEST_TOKEN)
    assert isinstance(obj, NotifyChime)

    # Confirm the webhook_id and token are stored correctly
    assert obj.webhook_id == TEST_WEBHOOK_ID
    assert obj.token == TEST_TOKEN


@mock.patch("requests.post")
def test_plugin_chime_send(mock_post):
    """NotifyChime() Send Checks."""

    def _mk_resp(code):
        """Build a minimal mock response with the given status code."""
        resp = requests.Request()
        resp.status_code = code
        # content is accessed in error-path debug logging
        resp.content = b""
        return resp

    # Prepare a successful mock response
    mock_post.return_value = _mk_resp(requests.codes.ok)

    # Instantiate a valid object
    obj = NotifyChime(webhook_id=TEST_WEBHOOK_ID, token=TEST_TOKEN)
    assert isinstance(obj, NotifyChime)

    # Perform a successful send
    assert obj.notify(body="Test body", title="Test title") is True

    # Verify the POST was made exactly once
    assert mock_post.call_count == 1

    # Confirm the URL used matches the expected Chime webhook URL pattern
    call_url = mock_post.call_args_list[0][0][0]
    assert "hooks.chime.aws/incomingwebhooks/" in call_url
    assert TEST_WEBHOOK_ID in call_url
    # The token is URL-encoded in the query string
    assert "token=" in call_url

    mock_post.reset_mock()

    # A 401 response returns False
    mock_post.return_value = _mk_resp(requests.codes.unauthorized)
    assert obj.notify(body="Test body") is False

    mock_post.reset_mock()

    # A 403 response returns False
    mock_post.return_value = _mk_resp(requests.codes.forbidden)
    assert obj.notify(body="Test body") is False

    mock_post.reset_mock()

    # A 404 response returns False
    mock_post.return_value = _mk_resp(requests.codes.not_found)
    assert obj.notify(body="Test body") is False

    mock_post.reset_mock()

    # A 429 too-many-requests response returns False
    mock_post.return_value = _mk_resp(429)
    assert obj.notify(body="Test body") is False

    mock_post.reset_mock()

    # A 500 response returns False
    mock_post.return_value = _mk_resp(requests.codes.internal_server_error)
    assert obj.notify(body="Test body") is False

    mock_post.reset_mock()

    # An unknown response code returns False
    mock_post.return_value = _mk_resp(999)
    assert obj.notify(body="Test body") is False

    mock_post.reset_mock()

    # A RequestException returns False
    mock_post.side_effect = requests.RequestException("Network error")
    assert obj.notify(body="Test body") is False


@mock.patch("requests.post")
def test_plugin_chime_url_roundtrip(mock_post):
    """NotifyChime() URL round-trip invariant."""

    # Prepare our mock response
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok

    # Build a simple token that contains base64 padding (=)
    token_with_padding = "AaBbCcDd1234=="

    obj = NotifyChime(
        webhook_id=TEST_WEBHOOK_ID,
        token=token_with_padding,
    )
    assert isinstance(obj, NotifyChime)

    # Generate a URL and parse it back
    generated_url = obj.url()
    results = NotifyChime.parse_url(generated_url)
    assert results is not None

    # Reconstruct from parsed results
    obj2 = NotifyChime(**results)
    assert isinstance(obj2, NotifyChime)

    # The connection identity must be identical
    assert obj.url_identifier == obj2.url_identifier

    # Token must survive the round-trip (including = padding)
    assert obj.token == obj2.token
    assert obj.webhook_id == obj2.webhook_id


@mock.patch("requests.post")
def test_plugin_chime_url_parsing(mock_post):
    """NotifyChime() URL Parsing Checks."""

    # Prepare our mock response
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok

    # Parse a standard Apprise URL
    results = NotifyChime.parse_url(
        "chime://{}/{}".format(TEST_WEBHOOK_ID, TEST_TOKEN)
    )
    assert results is not None
    assert results["webhook_id"] == TEST_WEBHOOK_ID
    assert results["token"] == TEST_TOKEN

    # ?token= query parameter overrides path-supplied token
    results = NotifyChime.parse_url(
        "chime://{}/ignored-token?token={}".format(TEST_WEBHOOK_ID, TEST_TOKEN)
    )
    assert results is not None
    assert results["token"] == TEST_TOKEN

    # ?webhook_id= query parameter overrides host-supplied ID
    results = NotifyChime.parse_url(
        "chime://ignored-id/{}?webhook_id={}".format(
            TEST_TOKEN, TEST_WEBHOOK_ID
        )
    )
    assert results is not None
    assert results["webhook_id"] == TEST_WEBHOOK_ID

    # None is returned for an invalid URL
    assert NotifyChime.parse_url(None) is None

    # Missing token returns a result dict with no token
    results = NotifyChime.parse_url("chime://{}".format(TEST_WEBHOOK_ID))
    # split_path on an empty fullpath returns no entries
    assert results is not None
    assert not results.get("token")


@mock.patch("requests.post")
def test_plugin_chime_native_url(mock_post):
    """NotifyChime() Native URL Parsing."""

    # Prepare our mock response
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok

    # A native URL with a URL-encoded token
    native_url = (
        "https://hooks.chime.aws/incomingwebhooks/"
        "{webhook_id}?token={token}".format(
            webhook_id=TEST_WEBHOOK_ID,
            # URL-encode the token as it would appear in a real Chime URL
            token=NotifyChime.quote(TEST_TOKEN, safe=""),
        )
    )

    results = NotifyChime.parse_native_url(native_url)
    assert results is not None
    assert results["webhook_id"] == TEST_WEBHOOK_ID
    assert results["token"] == TEST_TOKEN

    # The constructed object must be functional
    obj = NotifyChime(**results)
    assert isinstance(obj, NotifyChime)
    assert obj.notify(body="Native URL test") is True

    # A non-matching URL returns None
    assert (
        NotifyChime.parse_native_url("https://example.com/not-a-chime-url")
        is None
    )


@mock.patch("requests.post")
def test_plugin_chime_privacy_url(mock_post):
    """NotifyChime() Privacy URL."""

    # Prepare our mock response
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok

    obj = NotifyChime(webhook_id=TEST_WEBHOOK_ID, token=TEST_TOKEN)
    assert isinstance(obj, NotifyChime)

    # Privacy URL must mask credentials
    privacy = obj.url(privacy=True)
    assert TEST_TOKEN not in privacy
    assert TEST_WEBHOOK_ID not in privacy
    # Scheme must still be present
    assert privacy.startswith("chime://")


@mock.patch("requests.post")
def test_plugin_chime_apprise_integration(mock_post):
    """NotifyChime() Apprise integration."""

    # Prepare a valid mock response
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok

    # Test loading via Apprise URL
    a = Apprise()
    url = "chime://{}/{}".format(TEST_WEBHOOK_ID, TEST_TOKEN)
    assert a.add(url) is True
    assert len(a) == 1
    assert isinstance(a[0], NotifyChime)

    # Notify succeeds
    assert a.notify(body="Test", title="Title") is True
    assert mock_post.call_count == 1

    mock_post.reset_mock()

    # Test failure response
    mock_post.return_value.status_code = requests.codes.internal_server_error
    assert a.notify(body="Test", title="Title") is False

    mock_post.reset_mock()

    # Test with native URL
    a2 = Apprise()
    native = (
        "https://hooks.chime.aws/incomingwebhooks/"
        "{webhook_id}?token={token}".format(
            webhook_id=TEST_WEBHOOK_ID,
            token=NotifyChime.quote(TEST_TOKEN, safe=""),
        )
    )
    assert a2.add(native) is True
    assert len(a2) == 1
    assert isinstance(a2[0], NotifyChime)

    mock_post.return_value.status_code = requests.codes.ok
    assert a2.notify(body="Native test", title="Title") is True


@mock.patch("requests.post")
def test_plugin_chime_url_identifier(mock_post):
    """NotifyChime() url_identifier uniqueness."""

    # Two objects with the same credentials share an identifier
    obj1 = NotifyChime(webhook_id=TEST_WEBHOOK_ID, token=TEST_TOKEN)
    obj2 = NotifyChime(webhook_id=TEST_WEBHOOK_ID, token=TEST_TOKEN)
    assert obj1.url_identifier == obj2.url_identifier

    # Different webhook_id produces a different identifier
    obj3 = NotifyChime(webhook_id="different-id-abcd", token=TEST_TOKEN)
    assert obj1.url_identifier != obj3.url_identifier

    # Different token produces a different identifier
    obj4 = NotifyChime(webhook_id=TEST_WEBHOOK_ID, token="DifferentToken123")
    assert obj1.url_identifier != obj4.url_identifier

    # Targets must not affect the identifier (no targets for Chime)
    assert obj1.url_identifier[0] == NotifyChime.secure_protocol
    assert obj1.url_identifier[1] == TEST_WEBHOOK_ID
    assert obj1.url_identifier[2] == TEST_TOKEN


@mock.patch("requests.post")
def test_plugin_chime_html_to_markdown_format(mock_post):
    """NotifyChime(): HTML body is converted to Markdown."""

    # Prepare Mock
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok

    # Chime's notify_format is MARKDOWN by default
    aobj = Apprise()
    assert aobj.add("chime://{}/{}".format(TEST_WEBHOOK_ID, TEST_TOKEN))

    # Notify with an HTML body; the framework should convert it
    # to Markdown before dispatching to Chime
    assert (
        aobj.notify(
            body="<b>hello</b> <i>world</i>",
            body_format=NotifyFormat.HTML,
        )
        is True
    )
    assert mock_post.call_count == 1

    # The body must arrive as Markdown, not as stripped plain text
    payload = loads(mock_post.call_args_list[0][1]["data"])
    assert payload["Content"] == "**hello** *world*"
