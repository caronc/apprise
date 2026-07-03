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

from json import loads

# Disable logging for a cleaner testing output
import logging
from unittest import mock
from urllib.parse import urlparse

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise, NotifyType
from apprise.plugins.serwersms import NotifySerwerSMS

logging.disable(logging.CRITICAL)

# The API always returns 200 with a JSON body; use this as the mock response
# for successful cases so our success-field check passes.
SUCCESS_RESPONSE = {"success": True}
FAILURE_RESPONSE = {"success": False, "error": {"code": 101, "message": "err"}}
FAILURE_NO_ERROR = {"success": False}

# Our Testing URLs
apprise_url_tests = (
    (
        "serwersms://",
        {
            # Missing credentials
            "instance": TypeError,
        },
    ),
    (
        "serwersms://:@/",
        {
            # Empty credentials
            "instance": TypeError,
        },
    ),
    (
        "serwersms://user@SenderA/+48123456789",
        {
            # Missing password
            "instance": TypeError,
        },
    ),
    (
        "serwersms://user:pass@/+48123456789",
        {
            # Missing sender (empty host)
            "instance": TypeError,
        },
    ),
    (
        "serwersms://user:pass@!!invalid!!",
        {
            # Invalid sender name (fails regex)
            "instance": TypeError,
        },
    ),
    (
        "serwersms://user:pass@SenderA",
        {
            # Valid credentials + sender but no targets
            "instance": NotifySerwerSMS,
            # No targets -- send() returns False
            "notify_response": False,
        },
    ),
    (
        "serwersms://user:pass@SenderA/+48123456789",
        {
            # Single phone number target
            "instance": NotifySerwerSMS,
            "privacy_url": "serwersms://u...r:****@SenderA/+48123456789?",
            "requests_response_text": SUCCESS_RESPONSE,
        },
    ),
    (
        "serwersms://user:pass@SenderA/%23456",
        {
            # Single group ID target (# encoded as %23)
            "instance": NotifySerwerSMS,
            "privacy_url": "serwersms://u...r:****@SenderA/%23456?",
            "requests_response_text": SUCCESS_RESPONSE,
        },
    ),
    (
        "serwersms://user:pass@SenderA/+48123456789/%23789",
        {
            # Mixed: one phone + one group
            "instance": NotifySerwerSMS,
            "requests_response_text": SUCCESS_RESPONSE,
        },
    ),
    (
        "serwersms://user:pass@SenderA/+48111222333?to=%23999",
        {
            # Phone in path + group via ?to=
            "instance": NotifySerwerSMS,
            "requests_response_text": SUCCESS_RESPONSE,
        },
    ),
    (
        "serwersms://user:pass@SenderA/+48123456789",
        {
            # HTTP 500 error
            "instance": NotifySerwerSMS,
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "serwersms://user:pass@SenderA/+48123456789",
        {
            # Unknown HTTP status code
            "instance": NotifySerwerSMS,
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "serwersms://user:pass@SenderA/+48123456789",
        {
            # Connection exceptions
            "instance": NotifySerwerSMS,
            "test_requests_exceptions": True,
        },
    ),
    (
        "serwersms://user:pass@SenderA/%23123",
        {
            # Group target -- HTTP 500
            "instance": NotifySerwerSMS,
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "serwersms://user:pass@SenderA/%23123",
        {
            # Group target -- connection exceptions
            "instance": NotifySerwerSMS,
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_serwersms_urls():
    """NotifySerwerSMS() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.post")
def test_plugin_serwersms_init(mock_post):
    """NotifySerwerSMS() Initialisation tests."""

    # Missing username
    with pytest.raises(TypeError):
        NotifySerwerSMS(sender="SenderA", targets=["+48123456789"])

    # Missing password
    with pytest.raises(TypeError):
        NotifySerwerSMS(
            user="user",
            sender="SenderA",
            targets=["+48123456789"],
        )

    # Missing sender
    with pytest.raises(TypeError):
        NotifySerwerSMS(
            user="user",
            password="pass",
            targets=["+48123456789"],
        )

    # Invalid sender (too long - >11 chars)
    with pytest.raises(TypeError):
        NotifySerwerSMS(
            user="user",
            password="pass",
            sender="A" * 12,
            targets=["+48123456789"],
        )

    # Invalid sender (starts with non-alphanumeric)
    with pytest.raises(TypeError):
        NotifySerwerSMS(
            user="user",
            password="pass",
            sender="!invalid",
            targets=["+48123456789"],
        )

    # Valid instance with no targets -- loads OK; __len__ returns minimum 1
    obj = NotifySerwerSMS(
        user="user",
        password="pass",
        sender="SenderA",
    )
    assert obj is not None
    assert len(obj) == 1

    # Valid instance with a phone target
    obj = NotifySerwerSMS(
        user="user",
        password="pass",
        sender="SenderA",
        targets=["+48123456789"],
    )
    assert len(obj.target_phones) == 1
    assert len(obj.target_groups) == 0

    # Valid instance with a group target (#123)
    obj = NotifySerwerSMS(
        user="user",
        password="pass",
        sender="SenderA",
        targets=["#456"],
    )
    assert len(obj.target_phones) == 0
    assert len(obj.target_groups) == 1
    assert obj.target_groups[0] == "456"

    # Group target with %23 prefix is also accepted
    obj = NotifySerwerSMS(
        user="user",
        password="pass",
        sender="SenderA",
        targets=["%23789"],
    )
    assert len(obj.target_groups) == 1
    assert obj.target_groups[0] == "789"

    # Invalid targets are stored in invalid_targets
    obj = NotifySerwerSMS(
        user="user",
        password="pass",
        sender="SenderA",
        targets=["notaphone", "+48123456789"],
    )
    assert len(obj.invalid_targets) == 1
    assert len(obj.target_phones) == 1


@mock.patch("requests.post")
def test_plugin_serwersms_send_phone(mock_post):
    """NotifySerwerSMS() send to phone numbers."""

    # Prepare our success response
    mock_post.return_value = mock.Mock()
    mock_post.return_value.status_code = requests.codes.ok
    mock_post.return_value.content = b'{"success": true}'

    obj = NotifySerwerSMS(
        user="myuser",
        password="mypass",
        sender="AppName",
        targets=["+48111222333", "+48444555666"],
    )

    # Two phone targets means two POST calls
    assert obj.send(body="Hello", title="Title") is True
    assert mock_post.call_count == 2

    # Verify request URL
    call_url = mock_post.call_args_list[0][0][0]
    assert urlparse(call_url).hostname == "api2.serwersms.pl"

    # Verify payload contents for first call
    payload = loads(mock_post.call_args_list[0][1]["data"])
    assert payload["username"] == "myuser"
    assert payload["password"] == "mypass"
    assert payload["sender"] == "AppName"
    assert payload["text"] == "Hello"
    assert payload["phone"] == "+48111222333"
    assert "group_id" not in payload

    # Verify second call targets the second number
    payload2 = loads(mock_post.call_args_list[1][1]["data"])
    assert payload2["phone"] == "+48444555666"


@mock.patch("requests.post")
def test_plugin_serwersms_send_group(mock_post):
    """NotifySerwerSMS() send to contact groups."""

    # Prepare our success response
    mock_post.return_value = mock.Mock()
    mock_post.return_value.status_code = requests.codes.ok
    mock_post.return_value.content = b'{"success": true}'

    obj = NotifySerwerSMS(
        user="myuser",
        password="mypass",
        sender="AppName",
        targets=["#100", "#200"],
    )

    # Two group targets means two POST calls
    assert obj.send(body="Hello") is True
    assert mock_post.call_count == 2

    # Verify payload for group send
    payload = loads(mock_post.call_args_list[0][1]["data"])
    assert payload["group_id"] == "100"
    assert "phone" not in payload

    payload2 = loads(mock_post.call_args_list[1][1]["data"])
    assert payload2["group_id"] == "200"


@mock.patch("requests.post")
def test_plugin_serwersms_send_mixed(mock_post):
    """NotifySerwerSMS() send to phones and groups together."""

    mock_post.return_value = mock.Mock()
    mock_post.return_value.status_code = requests.codes.ok
    mock_post.return_value.content = b'{"success": true}'

    obj = NotifySerwerSMS(
        user="u",
        password="p",
        sender="Sender",
        targets=["+48123456789", "#500"],
    )

    # One phone + one group = two calls
    assert obj.send(body="msg") is True
    assert mock_post.call_count == 2

    # First call: phone
    p1 = loads(mock_post.call_args_list[0][1]["data"])
    assert "phone" in p1

    # Second call: group
    p2 = loads(mock_post.call_args_list[1][1]["data"])
    assert "group_id" in p2


@mock.patch("requests.post")
def test_plugin_serwersms_no_targets(mock_post):
    """NotifySerwerSMS() with no targets returns False without calling API."""

    obj = NotifySerwerSMS(
        user="u",
        password="p",
        sender="Sender",
    )
    assert obj.send(body="msg") is False
    assert mock_post.call_count == 0


@mock.patch("requests.post")
def test_plugin_serwersms_http_error(mock_post):
    """NotifySerwerSMS() handles HTTP errors gracefully."""

    mock_post.return_value = mock.Mock()
    mock_post.return_value.status_code = requests.codes.internal_server_error
    mock_post.return_value.content = b""

    obj = NotifySerwerSMS(
        user="u",
        password="p",
        sender="Sender",
        targets=["+48123456789", "#100"],
    )

    # Both calls fail due to HTTP 500
    assert obj.send(body="msg") is False
    assert mock_post.call_count == 2


@mock.patch("requests.post")
def test_plugin_serwersms_http_error_partial(mock_post):
    """NotifySerwerSMS() returns False on any partial HTTP failure."""

    # First call succeeds, second fails
    good = mock.Mock()
    good.status_code = requests.codes.ok
    good.content = b'{"success": true}'

    bad = mock.Mock()
    bad.status_code = 999
    bad.content = b""

    mock_post.side_effect = [good, bad]

    obj = NotifySerwerSMS(
        user="u",
        password="p",
        sender="Sender",
        targets=["+48111000000", "+48222000000"],
    )

    # One success, one failure -> overall False
    assert obj.send(body="msg") is False
    assert mock_post.call_count == 2


@mock.patch("requests.post")
def test_plugin_serwersms_request_exception(mock_post):
    """NotifySerwerSMS() handles RequestException gracefully."""

    mock_post.side_effect = requests.RequestException("Connection refused")

    obj = NotifySerwerSMS(
        user="u",
        password="p",
        sender="Sender",
        targets=["+48123456789"],
    )

    assert obj.send(body="msg") is False


@mock.patch("requests.post")
def test_plugin_serwersms_request_exception_group(mock_post):
    """NotifySerwerSMS() handles RequestException on group send."""

    mock_post.side_effect = requests.RequestException("timeout")

    obj = NotifySerwerSMS(
        user="u",
        password="p",
        sender="Sender",
        targets=["#100"],
    )

    assert obj.send(body="msg") is False


@mock.patch("requests.post")
def test_plugin_serwersms_api_failure_with_error(mock_post):
    """NotifySerwerSMS() handles API success=false with error object."""

    mock_post.return_value = mock.Mock()
    mock_post.return_value.status_code = requests.codes.ok
    mock_post.return_value.content = (
        b'{"success": false, "error": {"code": 101, "message": "Auth fail"}}'
    )

    obj = NotifySerwerSMS(
        user="u",
        password="p",
        sender="Sender",
        targets=["+48123456789"],
    )

    assert obj.send(body="msg") is False


@mock.patch("requests.post")
def test_plugin_serwersms_api_failure_no_error(mock_post):
    """NotifySerwerSMS() handles API success=false without error detail."""

    mock_post.return_value = mock.Mock()
    mock_post.return_value.status_code = requests.codes.ok
    mock_post.return_value.content = b'{"success": false}'

    obj = NotifySerwerSMS(
        user="u",
        password="p",
        sender="Sender",
        targets=["#200"],
    )

    assert obj.send(body="msg") is False


@mock.patch("requests.post")
def test_plugin_serwersms_api_bad_json(mock_post):
    """NotifySerwerSMS() handles unparseable JSON response body."""

    mock_post.return_value = mock.Mock()
    mock_post.return_value.status_code = requests.codes.ok
    mock_post.return_value.content = b"not-json"

    obj = NotifySerwerSMS(
        user="u",
        password="p",
        sender="Sender",
        targets=["+48123456789"],
    )

    # Bad JSON treated as failure (success field absent -> falsy)
    assert obj.send(body="msg") is False


@mock.patch("requests.post")
def test_plugin_serwersms_api_null_json(mock_post):
    """NotifySerwerSMS() handles null JSON response body."""

    mock_post.return_value = mock.Mock()
    mock_post.return_value.status_code = requests.codes.ok
    # JSON null parses to Python None; plugin normalises to {}
    mock_post.return_value.content = b"null"

    obj = NotifySerwerSMS(
        user="u",
        password="p",
        sender="Sender",
        targets=["+48123456789"],
    )

    assert obj.send(body="msg") is False


@mock.patch("requests.post")
def test_plugin_serwersms_url(mock_post):
    """NotifySerwerSMS() url() and url_identifier() tests."""

    obj = NotifySerwerSMS(
        user="myuser",
        password="mypass",
        sender="AppName",
        targets=["+48123456789", "#100"],
    )

    # url() produces a string
    full_url = obj.url()
    assert full_url.startswith("serwersms://")
    assert "myuser" in full_url
    assert "mypass" in full_url
    assert "AppName" in full_url

    # Privacy URL masks the password and abbreviates the user
    priv = obj.url(privacy=True)
    assert "mypass" not in priv
    assert "myuser" not in priv
    assert "AppName" in priv

    # url_identifier excludes targets
    ident = obj.url_identifier
    assert "serwersms" in ident
    assert "myuser" in ident
    assert "AppName" in ident
    assert "+48123456789" not in str(ident)


@mock.patch("requests.post")
def test_plugin_serwersms_url_roundtrip(mock_post):
    """NotifySerwerSMS() round-trips through url() -> parse_url()."""

    obj = NotifySerwerSMS(
        user="myuser",
        password="mypass",
        sender="AppName",
        targets=["+48123456789", "#100"],
    )

    # Parse the generated URL back into a new object
    result = NotifySerwerSMS.parse_url(obj.url())
    assert result is not None

    obj2 = NotifySerwerSMS(**result)
    assert obj.url_identifier == obj2.url_identifier
    assert len(obj.target_phones) == len(obj2.target_phones)
    assert len(obj.target_groups) == len(obj2.target_groups)


@mock.patch("requests.post")
def test_plugin_serwersms_url_invalid_targets(mock_post):
    """NotifySerwerSMS() preserves invalid targets in url() round-trip."""

    obj = NotifySerwerSMS(
        user="u",
        password="p",
        sender="S",
        targets=["+48123456789", "badtarget"],
    )

    assert len(obj.invalid_targets) == 1
    assert len(obj.target_phones) == 1

    # The generated URL must include the invalid target so it survives
    # a round-trip without silent loss.
    url = obj.url()
    assert "badtarget" in url


def test_plugin_serwersms_parse_url():
    """NotifySerwerSMS() parse_url() edge cases."""

    # Standard URL with phone and group
    result = NotifySerwerSMS.parse_url(
        "serwersms://user:pass@SenderA/+48123456789/%23100"
    )
    assert result is not None
    assert result["user"] == "user"
    assert result["password"] == "pass"
    assert result["sender"] == "SenderA"
    # Path entries come back decoded; +48123456789 and #100
    assert "+48123456789" in result["targets"]
    assert "#100" in result["targets"]

    # ?to= query param adds targets
    result = NotifySerwerSMS.parse_url(
        "serwersms://user:pass@SenderA?to=%2348123456789"
    )
    assert result is not None
    assert len(result["targets"]) >= 1

    # ?from= sets the sender
    result = NotifySerwerSMS.parse_url(
        "serwersms://user:pass@SenderA/+48111?from=NewSender"
    )
    assert result["sender"] == "NewSender"

    # ?sender= sets the sender (takes priority over ?from=)
    result = NotifySerwerSMS.parse_url(
        "serwersms://user:pass@SenderA/+48111?from=Old&sender=New"
    )
    assert result["sender"] == "New"

    # A URL with verify_host=False accepts empty host; verify None is returned
    # for a genuinely unparseable URL (non-string)
    assert NotifySerwerSMS.parse_url(None) is None


@mock.patch("requests.post")
def test_plugin_serwersms_apprise_integration(mock_post):
    """NotifySerwerSMS() integration with Apprise object."""

    mock_post.return_value = mock.Mock()
    mock_post.return_value.status_code = requests.codes.ok
    mock_post.return_value.content = b'{"success": true}'

    aobj = Apprise()
    assert aobj.add("serwersms://user:pass@AppName/+48123456789")

    assert aobj.notify(
        body="Integration test",
        title="Title",
        notify_type=NotifyType.INFO,
    )
    assert mock_post.call_count == 1
