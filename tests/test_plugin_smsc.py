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
import json
import logging
import os
from unittest import mock
from urllib.parse import urlparse

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise, AppriseAttachment, NotifyType
from apprise.plugins.smsc import NotifySMSC

logging.disable(logging.CRITICAL)

# Attachment test directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), "var")

# Valid login/password
LOGIN = "mylogin"
PASSWORD = "mypassword"
# A valid E.164 phone number (without + prefix in stored form)
PHONE = "71234567890"
PHONE2 = "79876543210"


# Our Testing URLs
apprise_url_tests = (
    # Missing everything
    (
        "smsc://",
        {"instance": TypeError},
    ),
    # Missing password
    (
        "smsc://login@+71234567890",
        {"instance": TypeError},
    ),
    # Missing login
    (
        "smsc://:password@+71234567890",
        {"instance": TypeError},
    ),
    # Valid single target
    (
        "smsc://login:password@+71234567890",
        {
            "instance": NotifySMSC,
            "privacy_url": "smsc://l...n:****@71234567890/",
        },
    ),
    # Valid two targets in path
    (
        "smsc://login:password@+71234567890/+79876543210",
        {
            "instance": NotifySMSC,
            "privacy_url": "smsc://l...n:****@71234567890/79876543210/",
        },
    ),
    # With sender ID
    (
        "smsc://login:password@+71234567890?sender=MySender",
        {"instance": NotifySMSC},
    ),
    # With translit enabled
    (
        "smsc://login:password@+71234567890?translit=yes",
        {"instance": NotifySMSC},
    ),
    # ?to= alias for additional targets
    (
        "smsc://login:password@+71234567890?to=+79876543210",
        {"instance": NotifySMSC},
    ),
    # Invalid phone number (only one bad; loads with warning but works)
    (
        "smsc://login:password@+71234567890/notaphone",
        {
            "instance": NotifySMSC,
            "privacy_url": "smsc://l...n:****@71234567890/",
        },
    ),
    # Only invalid phone numbers -- loads but notify returns False
    (
        "smsc://login:password@notaphone",
        {
            "instance": NotifySMSC,
            "notify_response": False,
        },
    ),
    # HTTP 500 response
    (
        "smsc://login:password@+71234567890",
        {
            "instance": NotifySMSC,
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    # Unknown HTTP status
    (
        "smsc://login:password@+71234567890",
        {
            "instance": NotifySMSC,
            "response": False,
            "requests_response_code": 999,
        },
    ),
    # RequestException
    (
        "smsc://login:password@+71234567890",
        {
            "instance": NotifySMSC,
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_smsc_urls():
    """NotifySMSC() Apprise URLs."""
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.post")
def test_plugin_smsc_init(mock_post):
    """NotifySMSC() initialization and validation."""

    # Missing login raises TypeError
    with pytest.raises(TypeError):
        NotifySMSC(targets=["+71234567890"])

    # Missing password raises TypeError
    with pytest.raises(TypeError):
        NotifySMSC(user=LOGIN, targets=["+71234567890"])

    # Whitespace-only sender is invalid (validate_regex strips to empty)
    with pytest.raises(TypeError):
        NotifySMSC(
            user=LOGIN,
            password=PASSWORD,
            targets=["+71234567890"],
            sender="   ",
        )

    # Valid instance, default settings
    obj = NotifySMSC(
        user=LOGIN,
        password=PASSWORD,
        targets=["+71234567890"],
    )
    assert isinstance(obj, NotifySMSC)
    assert obj.sender is None
    assert obj.translit is False
    assert len(obj) == 1

    # Valid instance with sender and translit
    obj = NotifySMSC(
        user=LOGIN,
        password=PASSWORD,
        targets=["+71234567890"],
        sender="MyBiz",
        translit=True,
    )
    assert obj.sender == "MyBiz"
    assert obj.translit is True

    # No targets - __len__ returns 1 (not 0) per convention
    obj = NotifySMSC(user=LOGIN, password=PASSWORD, targets=[])
    assert len(obj) == 1


@mock.patch("requests.post")
def test_plugin_smsc_url(mock_post):
    """NotifySMSC() URL building and round-trip."""

    obj = NotifySMSC(
        user=LOGIN,
        password=PASSWORD,
        targets=["+71234567890", "+79876543210"],
        sender="Apprise",
        translit=True,
    )

    # url() must contain all relevant parts
    generated = obj.url()
    assert "smsc://" in generated
    assert "71234567890" in generated
    assert "79876543210" in generated
    assert "sender=Apprise" in generated
    assert "translit=yes" in generated

    # privacy URL must mask the password and redact the user
    priv = obj.url(privacy=True)
    assert PASSWORD not in priv
    assert "m...n" in priv

    # url_identifier uniqueness
    obj2 = NotifySMSC(
        user=LOGIN,
        password=PASSWORD,
        targets=["+71234567890"],
    )
    assert obj.url_identifier == obj2.url_identifier

    # Round-trip via parse_url
    result = NotifySMSC.parse_url(obj.url())
    assert result is not None
    obj3 = NotifySMSC(**result)
    assert obj3.url_identifier == obj.url_identifier
    assert len(obj3.targets) == len(obj.targets)


@mock.patch("requests.post")
def test_plugin_smsc_send_sms(mock_post):
    """NotifySMSC() SMS send - success and failure paths."""

    def _mk_resp(data, code=requests.codes.ok):
        r = mock.Mock()
        r.status_code = code
        r.content = json.dumps(data).encode()
        return r

    # Happy path
    mock_post.return_value = _mk_resp({"id": "1234", "cnt": 1})

    obj = NotifySMSC(user=LOGIN, password=PASSWORD, targets=["+71234567890"])
    assert bool(obj.notify(body="Hello")) is True
    assert mock_post.call_count == 1

    # Verify POST went to the SMSC endpoint
    call_url = mock_post.call_args[0][0]
    assert urlparse(call_url).hostname == "smsc.ru"

    # Verify payload fields
    payload = mock_post.call_args[1]["data"]
    assert payload["login"] == LOGIN
    assert payload["psw"] == PASSWORD
    assert "71234567890" in payload["phones"]
    assert payload["mes"] == "Hello"

    mock_post.reset_mock()

    # API-level error in JSON response
    mock_post.return_value = _mk_resp(
        {"error": "Invalid login", "error_code": 2}
    )
    assert bool(obj.notify(body="Hello")) is False

    mock_post.reset_mock()

    # HTTP error status
    mock_post.return_value = _mk_resp({}, code=requests.codes.bad_request)
    assert bool(obj.notify(body="Hello")) is False

    mock_post.reset_mock()

    # Unknown HTTP status
    mock_post.return_value = _mk_resp({}, code=999)
    assert bool(obj.notify(body="Hello")) is False

    mock_post.reset_mock()

    # RequestException
    mock_post.side_effect = requests.RequestException("bang")
    assert bool(obj.notify(body="Hello")) is False

    mock_post.reset_mock()
    mock_post.side_effect = None

    # Non-JSON response body (loads raises ValueError) -- still succeeds
    # because HTTP 200 is authoritative; the loads exception handler fires
    r = mock.Mock()
    r.status_code = requests.codes.ok
    r.content = b"OK"
    mock_post.return_value = r
    assert bool(obj.notify(body="Hello")) is True


@mock.patch("requests.post")
def test_plugin_smsc_no_targets(mock_post):
    """NotifySMSC() returns False when no valid targets present."""

    obj = NotifySMSC(
        user=LOGIN,
        password=PASSWORD,
        targets=["notaphone"],
    )
    # notify() must return False without calling the API
    assert bool(obj.notify(body="Hello")) is False
    assert mock_post.call_count == 0


@mock.patch("requests.post")
def test_plugin_smsc_sender_translit(mock_post):
    """NotifySMSC() sender and translit params appear in the request."""

    def _mk_resp(data, code=requests.codes.ok):
        r = mock.Mock()
        r.status_code = code
        r.content = json.dumps(data).encode()
        return r

    mock_post.return_value = _mk_resp({"id": "99", "cnt": 1})

    obj = NotifySMSC(
        user=LOGIN,
        password=PASSWORD,
        targets=["+71234567890"],
        sender="MyBiz",
        translit=True,
    )
    assert bool(obj.notify(body="Привет")) is True

    payload = mock_post.call_args[1]["data"]
    assert payload.get("sender") == "MyBiz"
    assert payload.get("translit") == 1


@mock.patch("requests.post")
def test_plugin_smsc_send_mms_success(mock_post):
    """NotifySMSC() MMS send succeeds with valid attachment."""

    def _mk_resp(data, code=requests.codes.ok):
        r = mock.Mock()
        r.status_code = code
        r.content = json.dumps(data).encode()
        return r

    mock_post.return_value = _mk_resp({"id": "5678", "cnt": 1})

    obj = NotifySMSC(user=LOGIN, password=PASSWORD, targets=["+71234567890"])

    attach = AppriseAttachment(os.path.join(TEST_VAR_DIR, "apprise-test.png"))
    assert bool(obj.notify(body="Image", attach=attach)) is True
    assert mock_post.call_count == 1

    # Confirm MMS flag is set in the payload
    payload = mock_post.call_args[1]["data"]
    assert payload.get("mms") == 1

    # Confirm a file was included in the files parameter
    files_arg = mock_post.call_args[1]["files"]
    assert len(files_arg) == 1


@mock.patch("requests.post")
def test_plugin_smsc_mms_multi_attach(mock_post):
    """NotifySMSC() MMS send with multiple attachments."""

    def _mk_resp(data, code=requests.codes.ok):
        r = mock.Mock()
        r.status_code = code
        r.content = json.dumps(data).encode()
        return r

    mock_post.return_value = _mk_resp({"id": "9999", "cnt": 1})

    obj = NotifySMSC(user=LOGIN, password=PASSWORD, targets=["+71234567890"])

    attach = AppriseAttachment(
        [
            os.path.join(TEST_VAR_DIR, "apprise-test.png"),
            os.path.join(TEST_VAR_DIR, "apprise-test.gif"),
        ]
    )
    assert bool(obj.notify(body="Two files", attach=attach)) is True

    files_arg = mock_post.call_args[1]["files"]
    assert len(files_arg) == 2


@mock.patch("requests.post")
def test_plugin_smsc_mms_inaccessible(mock_post):
    """NotifySMSC() MMS fails when attachment file is inaccessible."""

    obj = NotifySMSC(user=LOGIN, password=PASSWORD, targets=["+71234567890"])

    attach = AppriseAttachment(os.path.join(TEST_VAR_DIR, "apprise-test.png"))

    with mock.patch("os.path.isfile", return_value=False):
        assert bool(obj.notify(body="Image", attach=attach)) is False

    # The HTTP client must not have been called
    assert mock_post.call_count == 0


@mock.patch("requests.post")
def test_plugin_smsc_mms_oserror(mock_post):
    """NotifySMSC() MMS fails cleanly on OSError during open."""

    obj = NotifySMSC(user=LOGIN, password=PASSWORD, targets=["+71234567890"])

    attach = AppriseAttachment(os.path.join(TEST_VAR_DIR, "apprise-test.png"))

    with mock.patch("builtins.open", side_effect=OSError("disk error")):
        assert bool(obj.notify(body="Image", attach=attach)) is False

    assert mock_post.call_count == 0


@mock.patch("requests.post")
def test_plugin_smsc_mms_http_error(mock_post):
    """NotifySMSC() MMS returns False on HTTP error response."""

    r = mock.Mock()
    r.status_code = requests.codes.internal_server_error
    r.content = b""
    mock_post.return_value = r

    obj = NotifySMSC(user=LOGIN, password=PASSWORD, targets=["+71234567890"])

    attach = AppriseAttachment(os.path.join(TEST_VAR_DIR, "apprise-test.png"))
    assert bool(obj.notify(body="Image", attach=attach)) is False


@mock.patch("requests.post")
def test_plugin_smsc_mms_api_error(mock_post):
    """NotifySMSC() MMS returns False on API-level error."""

    r = mock.Mock()
    r.status_code = requests.codes.ok
    r.content = json.dumps(
        {"error": "Insufficient funds", "error_code": 3}
    ).encode()
    mock_post.return_value = r

    obj = NotifySMSC(user=LOGIN, password=PASSWORD, targets=["+71234567890"])

    attach = AppriseAttachment(os.path.join(TEST_VAR_DIR, "apprise-test.png"))
    assert bool(obj.notify(body="Image", attach=attach)) is False


@mock.patch("requests.post")
def test_plugin_smsc_mms_request_exception(mock_post):
    """NotifySMSC() MMS returns False on RequestException."""

    mock_post.side_effect = requests.RequestException("timeout")

    obj = NotifySMSC(user=LOGIN, password=PASSWORD, targets=["+71234567890"])

    attach = AppriseAttachment(os.path.join(TEST_VAR_DIR, "apprise-test.png"))
    assert bool(obj.notify(body="Image", attach=attach)) is False


@mock.patch("requests.post")
def test_plugin_smsc_mms_non_json(mock_post):
    """NotifySMSC() MMS succeeds with non-JSON response body on HTTP 200."""

    # A non-JSON success body exercises the response parsing fallback.
    r = mock.Mock()
    r.status_code = requests.codes.ok
    r.content = b"OK"
    mock_post.return_value = r

    obj = NotifySMSC(user=LOGIN, password=PASSWORD, targets=["+71234567890"])

    attach = AppriseAttachment(os.path.join(TEST_VAR_DIR, "apprise-test.png"))
    assert bool(obj.notify(body="Image", attach=attach)) is True


@mock.patch("requests.post")
def test_plugin_smsc_parse_url(mock_post):
    """NotifySMSC() parse_url covers all input forms."""

    # Standard form
    result = NotifySMSC.parse_url(
        "smsc://login:pass@+71234567890/+79876543210"
    )
    assert result is not None
    obj = NotifySMSC(**result)
    assert len(obj.targets) == 2

    # ?to= alias
    result = NotifySMSC.parse_url(
        "smsc://login:pass@+71234567890?to=%2B79876543210"
    )
    assert result is not None
    obj = NotifySMSC(**result)
    assert len(obj.targets) == 2

    # ?sender= and ?translit=
    result = NotifySMSC.parse_url(
        "smsc://login:pass@+71234567890?sender=Biz&translit=yes"
    )
    assert result is not None
    obj = NotifySMSC(**result)
    assert obj.sender == "Biz"
    assert obj.translit is True

    # Bad URL (None) returns None
    result = NotifySMSC.parse_url(None)
    assert result is None


@mock.patch("requests.post")
def test_plugin_smsc_apprise_integration(mock_post):
    """NotifySMSC() integrates correctly with the Apprise engine."""

    r = mock.Mock()
    r.status_code = requests.codes.ok
    r.content = json.dumps({"id": "42", "cnt": 1}).encode()
    mock_post.return_value = r

    a = Apprise()
    assert a.add("smsc://login:password@+71234567890")
    assert a.notify(body="Integration test", notify_type=NotifyType.INFO)
    assert mock_post.call_count == 1
