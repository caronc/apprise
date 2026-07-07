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
import os
from unittest import mock
from urllib.parse import urlparse

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise, AppriseAttachment, NotifyType
from apprise.plugins.eight00com import NotifyEight00com

logging.disable(logging.CRITICAL)

# Attachment Directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), "var")

# Our Testing URLs
apprise_url_tests = (
    (
        "eight00com://",
        {
            # No token -> TypeError
            "instance": TypeError,
        },
    ),
    (
        "eight00com://:@/",
        {
            # Empty token -> TypeError
            "instance": TypeError,
        },
    ),
    (
        "eight00com://GOODTOKEN@badphone",
        {
            # Non-numeric from-phone -> TypeError
            "instance": TypeError,
        },
    ),
    (
        "eight00com://GOODTOKEN@9876543210/12",
        {
            # Target too short to be a valid phone number; it is
            # dropped, leaving no targets -> notify_response False
            "instance": NotifyEight00com,
            "notify_response": False,
        },
    ),
    (
        "eight00com://{}@{}".format("t" * 10, "8" * 10),
        {
            # Valid token + source only; defaults to texting ourselves
            "instance": NotifyEight00com,
        },
    ),
    (
        "eight00com://{}@{}/{}".format("t" * 10, "8" * 10, "5" * 11),
        {
            # Valid token, source, and one target
            "instance": NotifyEight00com,
            "privacy_url": (
                "eight00com://t...t@{}/{}".format("8" * 10, "5" * 11)
            ),
        },
    ),
    (
        "eight00com://{}@{}/{}/{}".format(
            "t" * 10, "8" * 10, "5" * 11, "6" * 11
        ),
        {
            # Multiple targets
            "instance": NotifyEight00com,
        },
    ),
    (
        "eight00com://?token={}&from={}".format("t" * 10, "8" * 10),
        {
            # Token and source via query params
            "instance": NotifyEight00com,
        },
    ),
    (
        "eight00com://?token={}&from={}&to={}".format(
            "t" * 10, "8" * 10, "5" * 11
        ),
        {
            # Token, source, and target all via query params
            "instance": NotifyEight00com,
        },
    ),
    (
        "eight00com://{}@{}".format("t" * 10, "8" * 10),
        {
            "instance": NotifyEight00com,
            # HTTP 500 -> failure
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "eight00com://{}@{}".format("t" * 10, "8" * 10),
        {
            "instance": NotifyEight00com,
            # Unknown HTTP code -> failure
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "eight00com://{}@{}".format("t" * 10, "8" * 10),
        {
            "instance": NotifyEight00com,
            # Simulate network I/O exceptions
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_eight00com_urls():
    """NotifyEight00com() Apprise URLs."""
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.post")
def test_plugin_eight00com_init(mock_post):
    """NotifyEight00com() initialization and edge cases."""

    # Prepare a generic success response
    response = requests.Request()
    response.status_code = requests.codes.ok
    mock_post.return_value = response

    # Missing token -> TypeError
    with pytest.raises(TypeError):
        NotifyEight00com(token=None, source="8005551234")

    # Empty token -> TypeError
    with pytest.raises(TypeError):
        NotifyEight00com(token="", source="8005551234")

    # Invalid source phone -> TypeError
    with pytest.raises(TypeError):
        NotifyEight00com(token="mytoken", source="notaphone")

    # Valid with source only: defaults to texting ourselves
    obj = NotifyEight00com(token="mytoken", source="8005551234")
    assert obj.targets == ["8005551234"]
    assert len(obj) == 1

    # Invalid target is dropped with a warning logged
    obj = NotifyEight00com(
        token="mytoken",
        source="8005551234",
        targets=["12"],
    )
    assert obj.targets == []
    # __len__ returns 1 minimum (consistent with httpsms pattern)
    assert len(obj) == 1

    # Multiple valid targets
    obj = NotifyEight00com(
        token="mytoken",
        source="8005551234",
        targets=["5551234567", "6661234567"],
    )
    assert len(obj.targets) == 2
    assert len(obj) == 2


@mock.patch("requests.post")
def test_plugin_eight00com_sms(mock_post):
    """NotifyEight00com() SMS send path."""

    response = requests.Request()
    response.status_code = requests.codes.ok
    response.content = b"{}"
    mock_post.return_value = response

    # Single target
    obj = NotifyEight00com(
        token="mytoken",
        source="8005551234",
        targets=["5559876543"],
    )
    assert bool(obj.notify(body="Test", title="Title")) is True
    assert mock_post.call_count == 1

    # Verify payload
    payload = loads(mock_post.call_args[1]["data"])
    assert payload["sender"] == "+8005551234"
    assert payload["recipient"] == "+5559876543"
    assert payload["message"] == "Title\r\nTest"

    # Verify Authorization header
    headers = mock_post.call_args[1]["headers"]
    assert headers["Authorization"] == "Bearer mytoken"

    mock_post.reset_mock()

    # Two targets -> two POST calls
    obj = NotifyEight00com(
        token="mytoken",
        source="8005551234",
        targets=["5559876543", "4445551234"],
    )
    assert bool(obj.notify(body="Hello")) is True
    assert mock_post.call_count == 2

    mock_post.reset_mock()

    # HTTP 500 -> failure
    response.status_code = requests.codes.internal_server_error
    obj = NotifyEight00com(
        token="mytoken",
        source="8005551234",
        targets=["5559876543"],
    )
    assert bool(obj.notify(body="Test")) is False

    mock_post.reset_mock()

    # Unknown status code -> failure
    response.status_code = 999
    assert bool(obj.notify(body="Test")) is False

    mock_post.reset_mock()

    # RequestException -> failure
    mock_post.side_effect = requests.RequestException("Connection error")
    response.status_code = requests.codes.ok
    assert bool(obj.notify(body="Test")) is False

    mock_post.side_effect = None

    # No targets after bad-number drops -> failure without HTTP call
    obj = NotifyEight00com(
        token="mytoken",
        source="8005551234",
        targets=["12"],
    )
    mock_post.reset_mock()
    assert bool(obj.notify(body="Test")) is False
    assert mock_post.call_count == 0


@mock.patch("requests.post")
def test_plugin_eight00com_url_round_trip(mock_post):
    """NotifyEight00com() URL round-trip and privacy_url."""

    response = requests.Request()
    response.status_code = requests.codes.ok
    mock_post.return_value = response

    # Round-trip with one target
    obj1 = NotifyEight00com(
        token="secrettoken",
        source="8005551234",
        targets=["5559876543"],
    )
    result = NotifyEight00com.parse_url(obj1.url())
    obj2 = NotifyEight00com(**result)
    assert obj1.url_identifier == obj2.url_identifier
    assert len(obj1.targets) == len(obj2.targets)

    # Privacy URL masks the token
    privacy = obj1.url(privacy=True)
    assert "secrettoken" not in privacy
    assert "s...n" in privacy

    # Round-trip with no explicit target (self-send omits path)
    obj3 = NotifyEight00com(token="mytoken", source="8005551234")
    result = NotifyEight00com.parse_url(obj3.url())
    obj4 = NotifyEight00com(**result)
    assert obj3.url_identifier == obj4.url_identifier
    # Self-send: targets are preserved
    assert obj3.targets == obj4.targets

    # url_identifier is schema / source / token -- not targets
    assert obj1.url_identifier == (
        "eight00com",
        "8005551234",
        "secrettoken",
    )


@mock.patch("requests.post")
def test_plugin_eight00com_parse_url(mock_post):
    """NotifyEight00com() parse_url edge cases."""

    response = requests.Request()
    response.status_code = requests.codes.ok
    mock_post.return_value = response

    # Standard form: token@source/target
    result = NotifyEight00com.parse_url(
        "eight00com://mytoken@8005551234/5559876543"
    )
    assert result["token"] == "mytoken"
    assert result["source"] == "8005551234"
    assert "5559876543" in result["targets"]

    # ?token= override
    result = NotifyEight00com.parse_url(
        "eight00com://8005551234?token=newtoken&from=8009876543&to=5551234567"
    )
    assert result["token"] == "newtoken"
    assert result["source"] == "8009876543"

    # ?from= causes host to become a target instead of source
    result = NotifyEight00com.parse_url(
        "eight00com://mytoken@9998887776?from=8005551234"
    )
    assert result["token"] == "mytoken"
    assert result["source"] == "8005551234"
    # The host (9998887776) becomes a target
    assert "9998887776" in " ".join(result["targets"])

    # ?to= adds targets
    result = NotifyEight00com.parse_url(
        "eight00com://mytoken@8005551234?to=5559876543"
    )
    assert "5559876543" in " ".join(result["targets"])

    # Unparseable URL -> None
    assert NotifyEight00com.parse_url(None) is None


@mock.patch("requests.post")
def test_plugin_eight00com_attach_success(mock_post):
    """NotifyEight00com() attachment send -- success path."""

    response = requests.Request()
    response.status_code = requests.codes.ok
    mock_post.return_value = response

    obj = NotifyEight00com(
        token="mytoken",
        source="8005551234",
        targets=["5559876543"],
    )

    attach = AppriseAttachment.instantiate(
        os.path.join(TEST_VAR_DIR, "apprise-test.gif")
    )
    assert (
        bool(
            obj.notify(
                body="Test MMS",
                title="",
                notify_type=NotifyType.INFO,
                attach=attach,
            )
        )
        is True
    )

    # Exactly one POST for one target
    assert mock_post.call_count == 1

    # Confirm the MMS fields were sent as multipart (files kwarg set)
    call_kwargs = mock_post.call_args[1]
    assert call_kwargs["files"] is not None
    assert call_kwargs["data"]["sender"] == "+8005551234"
    assert call_kwargs["data"]["recipient"] == "+5559876543"
    assert call_kwargs["data"]["message"] == "Test MMS"

    # Confirm authorization header is present
    assert call_kwargs["headers"]["Authorization"] == "Bearer mytoken"

    # Verify the URL host is correct
    call_url = mock_post.call_args[0][0]
    assert urlparse(call_url).hostname == "api.800.com"


@mock.patch("requests.post")
def test_plugin_eight00com_attach_multi(mock_post):
    """NotifyEight00com() MMS with multiple attachments."""

    response = requests.Request()
    response.status_code = requests.codes.ok
    mock_post.return_value = response

    obj = NotifyEight00com(
        token="mytoken",
        source="8005551234",
        targets=["5559876543"],
    )

    attach = AppriseAttachment()
    attach.add(os.path.join(TEST_VAR_DIR, "apprise-test.gif"))
    attach.add(os.path.join(TEST_VAR_DIR, "apprise-test.png"))

    assert (
        bool(
            obj.notify(
                body="Multi-attachment MMS",
                attach=attach,
            )
        )
        is True
    )
    assert mock_post.call_count == 1

    # Two media[] tuples in the files list
    files = mock_post.call_args[1]["files"]
    assert len(files) == 2
    assert all(f[0] == "media[]" for f in files)


@mock.patch("requests.post")
def test_plugin_eight00com_attach_inaccessible(mock_post):
    """NotifyEight00com() attachment -- inaccessible file guard."""

    response = requests.Request()
    response.status_code = requests.codes.ok
    mock_post.return_value = response

    obj = NotifyEight00com(
        token="mytoken",
        source="8005551234",
        targets=["5559876543"],
    )

    attach = AppriseAttachment.instantiate(
        os.path.join(TEST_VAR_DIR, "apprise-test.gif")
    )

    # Simulate the file being inaccessible (os.path.isfile -> False)
    with mock.patch("os.path.isfile", return_value=False):
        assert bool(obj.notify(body="Test", attach=attach)) is False

    # No HTTP call should have been made
    assert mock_post.call_count == 0


@mock.patch("requests.post")
def test_plugin_eight00com_attach_oserror(mock_post):
    """NotifyEight00com() attachment -- OSError on open guard."""

    response = requests.Request()
    response.status_code = requests.codes.ok
    mock_post.return_value = response

    obj = NotifyEight00com(
        token="mytoken",
        source="8005551234",
        targets=["5559876543"],
    )

    attach = AppriseAttachment.instantiate(
        os.path.join(TEST_VAR_DIR, "apprise-test.gif")
    )

    with mock.patch("builtins.open", side_effect=OSError("IO fail")):
        assert bool(obj.notify(body="Test", attach=attach)) is False

    # No HTTP call should have been made
    assert mock_post.call_count == 0


@mock.patch("requests.post")
def test_plugin_eight00com_attach_http_error(mock_post):
    """NotifyEight00com() attachment -- server HTTP error response."""

    response = requests.Request()
    response.status_code = requests.codes.internal_server_error
    response.content = b"{}"
    mock_post.return_value = response

    obj = NotifyEight00com(
        token="mytoken",
        source="8005551234",
        targets=["5559876543"],
    )

    attach = AppriseAttachment.instantiate(
        os.path.join(TEST_VAR_DIR, "apprise-test.gif")
    )
    assert bool(obj.notify(body="Test", attach=attach)) is False
    assert mock_post.call_count == 1


@mock.patch("requests.post")
def test_plugin_eight00com_attach_request_exception(mock_post):
    """NotifyEight00com() attachment -- RequestException guard."""

    mock_post.side_effect = requests.RequestException("Connection error")

    obj = NotifyEight00com(
        token="mytoken",
        source="8005551234",
        targets=["5559876543"],
    )

    attach = AppriseAttachment.instantiate(
        os.path.join(TEST_VAR_DIR, "apprise-test.gif")
    )
    assert bool(obj.notify(body="Test", attach=attach)) is False


@mock.patch("requests.post")
def test_plugin_eight00com_attach_partial_failure(mock_post):
    """NotifyEight00com() MMS partial target failure."""

    def _side_effect(*args, **kwargs):
        # First call succeeds, second fails
        if mock_post.call_count == 1:
            resp = requests.Request()
            resp.status_code = requests.codes.ok
            return resp

        resp = requests.Request()
        resp.status_code = requests.codes.internal_server_error
        resp.content = b"{}"
        return resp

    mock_post.side_effect = _side_effect

    obj = NotifyEight00com(
        token="mytoken",
        source="8005551234",
        targets=["5559876543", "4441234567"],
    )

    attach = AppriseAttachment.instantiate(
        os.path.join(TEST_VAR_DIR, "apprise-test.gif")
    )
    # One success and one failure -> overall False
    assert bool(obj.notify(body="Test", attach=attach)) is False
    assert mock_post.call_count == 2


@mock.patch("requests.post")
def test_plugin_eight00com_apprise_integration(mock_post):
    """NotifyEight00com() integration with Apprise."""

    response = requests.Request()
    response.status_code = requests.codes.ok
    mock_post.return_value = response

    # Load via URL
    a = Apprise()
    assert a.add("eight00com://mytoken@8005551234/5559876543") is True
    assert bool(a.notify(body="Integration test")) is True
    assert mock_post.call_count == 1

    mock_post.reset_mock()

    # Load via URL with ?to= and ?from=
    a2 = Apprise()
    assert (
        a2.add("eight00com://?token=mytoken&from=8005551234&to=5559876543")
        is True
    )
    assert bool(a2.notify(body="Integration test 2")) is True
    assert mock_post.call_count == 1
