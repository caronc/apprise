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
from unittest import mock
from urllib.parse import urlparse

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise
from apprise.plugins.stackfield import NotifyStackfield

logging.disable(logging.CRITICAL)

# A valid Stackfield webhook token (UUID format)
TEST_TOKEN = "11111111-2222-3333-4444-555555555555"

apprise_url_tests = (
    # Missing token
    (
        "stackfield://",
        {
            "instance": TypeError,
        },
    ),
    # Invalid token -- not a UUID
    (
        "stackfield://not-a-valid-uuid",
        {
            "instance": TypeError,
        },
    ),
    # Invalid token -- wrong UUID length
    (
        "stackfield://11111111-2222-3333-4444-55555555555",
        {
            "instance": TypeError,
        },
    ),
    # Valid token in URL path
    (
        f"stackfield://{TEST_TOKEN}",
        {
            "instance": NotifyStackfield,
            "privacy_url": "stackfield://****/",
        },
    ),
    # Valid token via ?token= query parameter
    (
        f"stackfield://?token={TEST_TOKEN}",
        {
            "instance": NotifyStackfield,
            "privacy_url": "stackfield://****/",
        },
    ),
    # Native Stackfield webhook URL
    (
        f"https://www.stackfield.com/apiwh/{TEST_TOKEN}",
        {
            "instance": NotifyStackfield,
        },
    ),
    # Native URL without www prefix
    (
        f"https://stackfield.com/apiwh/{TEST_TOKEN}",
        {
            "instance": NotifyStackfield,
        },
    ),
    # HTTP 500 response
    (
        f"stackfield://{TEST_TOKEN}",
        {
            "instance": NotifyStackfield,
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    # Unknown HTTP error code
    (
        f"stackfield://{TEST_TOKEN}",
        {
            "instance": NotifyStackfield,
            "response": False,
            "requests_response_code": 999,
        },
    ),
    # RequestException
    (
        "stackfield://abcdef01-2345-6789-abcd-ef0123456789",
        {
            "instance": NotifyStackfield,
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_stackfield_urls():
    """Run the standard AppriseURLTester against all URL test cases."""
    AppriseURLTester(tests=apprise_url_tests).run_all()


def test_plugin_stackfield_init():
    """Test NotifyStackfield init, url(), and url_identifier."""

    # Valid instantiation
    obj = NotifyStackfield(token=TEST_TOKEN)
    assert isinstance(obj, NotifyStackfield)

    # url_identifier returns (schema, token)
    assert obj.url_identifier == ("stackfield", TEST_TOKEN)

    # url() round-trips correctly
    url = obj.url()
    assert url.startswith("stackfield://")
    assert TEST_TOKEN in url

    # privacy URL masks the token
    privacy = obj.url(privacy=True)
    assert TEST_TOKEN not in privacy
    assert "stackfield://" in privacy

    # Round-trip: parse_url(url()) re-creates the same object
    result = NotifyStackfield.parse_url(obj.url())
    assert result is not None
    obj2 = NotifyStackfield(**result)
    assert obj2.url_identifier == obj.url_identifier

    # Missing token
    with pytest.raises(TypeError):
        NotifyStackfield(token=None)

    # Empty token
    with pytest.raises(TypeError):
        NotifyStackfield(token="")

    # Invalid token format (not a UUID)
    with pytest.raises(TypeError):
        NotifyStackfield(token="not-a-valid-uuid-at-all")

    # Wrong UUID length (too short)
    with pytest.raises(TypeError):
        NotifyStackfield(token="11111111-2222-3333-4444-55555555555")


@mock.patch("requests.post")
def test_plugin_stackfield_send(mock_post):
    """Test send() HTTP success, HTTP error, and RequestException paths."""

    def _mk_resp(code=requests.codes.ok):
        r = mock.Mock()
        r.status_code = code
        r.content = b""
        return r

    obj = NotifyStackfield(token=TEST_TOKEN)

    # Successful notification
    mock_post.return_value = _mk_resp(requests.codes.ok)
    assert obj.send(body="Hello, Stackfield!") is True
    assert mock_post.call_count == 1

    # Verify POST target hostname
    call_url = mock_post.call_args[0][0]
    assert urlparse(call_url).hostname == "www.stackfield.com"

    mock_post.reset_mock()

    # HTTP 500 -> send() returns False
    mock_post.return_value = _mk_resp(requests.codes.internal_server_error)
    assert obj.send(body="test") is False

    mock_post.reset_mock()

    # Unknown HTTP code 999 -> send() returns False
    mock_post.return_value = _mk_resp(999)
    assert obj.send(body="test") is False

    mock_post.reset_mock()

    # RequestException -> send() returns False
    mock_post.side_effect = requests.RequestException("connection error")
    assert obj.send(body="test") is False


def test_plugin_stackfield_url_parsing():
    """Test parse_url() and parse_native_url() edge cases."""

    # Token from URL path (host position)
    result = NotifyStackfield.parse_url(f"stackfield://{TEST_TOKEN}")
    assert result is not None
    assert result["token"] == TEST_TOKEN

    # Token from ?token= query string
    result = NotifyStackfield.parse_url(f"stackfield://?token={TEST_TOKEN}")
    assert result is not None
    assert result["token"] == TEST_TOKEN

    # ?token= wins over host position when both are present
    other = "abcdef01-2345-6789-abcd-ef0123456789"
    result = NotifyStackfield.parse_url(
        f"stackfield://{TEST_TOKEN}?token={other}"
    )
    assert result is not None
    assert result["token"] == other

    # parse_native_url: full https://www.stackfield.com/apiwh/TOKEN
    result = NotifyStackfield.parse_native_url(
        f"https://www.stackfield.com/apiwh/{TEST_TOKEN}"
    )
    assert result is not None
    assert result["token"] == TEST_TOKEN

    # parse_native_url: without www
    result = NotifyStackfield.parse_native_url(
        f"https://stackfield.com/apiwh/{TEST_TOKEN}"
    )
    assert result is not None
    assert result["token"] == TEST_TOKEN

    # parse_native_url: http variant
    result = NotifyStackfield.parse_native_url(
        f"http://www.stackfield.com/apiwh/{TEST_TOKEN}"
    )
    assert result is not None
    assert result["token"] == TEST_TOKEN

    # parse_native_url: invalid token format -> returns None
    result = NotifyStackfield.parse_native_url(
        "https://www.stackfield.com/apiwh/not-a-valid-uuid"
    )
    assert result is None

    # parse_native_url: unrelated URL -> returns None
    result = NotifyStackfield.parse_native_url(
        "https://example.com/webhook/12345"
    )
    assert result is None


@mock.patch("requests.post")
def test_plugin_stackfield_apprise_integration(mock_post):
    """Test that Apprise correctly loads and fires a Stackfield URL."""

    r = mock.Mock()
    r.status_code = requests.codes.ok
    r.content = b""
    mock_post.return_value = r

    a = Apprise()
    assert a.add(f"stackfield://{TEST_TOKEN}") is True
    assert a.notify(title="Test", body="Integration test") is True
    assert mock_post.call_count == 1
