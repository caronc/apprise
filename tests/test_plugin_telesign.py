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
from unittest import mock

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise
from apprise.exception import AppriseImproperlyConfigured
from apprise.plugins.telesign import NotifyTelesign

logging.disable(logging.CRITICAL)

# A realistic Customer ID and API Key; the key holds a slash and plus
CUSTOMER_ID = "FFFFFFFF-EEEE-DDDD-1234-AB1234567890"
APIKEY = "EXAMPLE/abcdefghijklmnopqrstuvwxyz+0123456789=="

# The same API Key, written so it fits in a URL
APIKEY_URL = "EXAMPLE%2Fabcdefghijklmnopqrstuvwxyz%2B0123456789%3D%3D"

# A successful Telesign response
OK_RESPONSE = json.dumps(
    {
        "reference_id": "0123456789ABCDEF0123456789ABCDEF",
        "status": {
            "code": 290,
            "description": "Message in progress",
        },
    }
).encode("utf-8")

# Our Testing URLs
apprise_url_tests = (
    (
        "telesign://",
        {
            # Nothing specified
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "telesign://15551234567",
        {
            # No Customer ID or API Key specified
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        f"telesign://{CUSTOMER_ID}@15551234567",
        {
            # No API Key specified
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        f"telesign://{CUSTOMER_ID}:{APIKEY_URL}@15551234567?type=invalid",
        {
            # An unknown message type
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        f"telesign://{CUSTOMER_ID}:{APIKEY_URL}@",
        {
            # No phone numbers; we load but have nothing to notify
            "instance": NotifyTelesign,
            "notify_response": False,
        },
    ),
    (
        f"telesign://{CUSTOMER_ID}:{APIKEY_URL}@15551234567",
        {
            "instance": NotifyTelesign,
            "requests_response_text": OK_RESPONSE,
            # Our expected url(privacy=True) startswith() response
            "privacy_url": f"telesign://{CUSTOMER_ID}:E...=@15551234567",
        },
    ),
    (
        f"telesign://{CUSTOMER_ID}:{APIKEY_URL}@15551234567/15551234568"
        "?from=Alerts&type=mkt",
        {
            # A sender and a marketing message type
            "instance": NotifyTelesign,
            "privacy_url": f"telesign://{CUSTOMER_ID}:E...=@15551234567/"
            "15551234568?type=mkt&from=Alerts",
        },
    ),
    (
        f"telesign://{CUSTOMER_ID}@?key={APIKEY_URL}"
        "&to=15551234567,15551234568",
        {
            # API Key and phone numbers given as arguments
            "instance": NotifyTelesign,
            "privacy_url": f"telesign://{CUSTOMER_ID}:E...=@15551234567/"
            "15551234568",
        },
    ),
    (
        f"telesign://{CUSTOMER_ID}:{APIKEY_URL}@15551234567/123",
        {
            # One bad phone number is dropped; the good one still works
            "instance": NotifyTelesign,
        },
    ),
    (
        f"telesign://{CUSTOMER_ID}:{APIKEY_URL}@123",
        {
            # Nothing valid to notify
            "instance": NotifyTelesign,
            "notify_response": False,
        },
    ),
    (
        f"telesign://{CUSTOMER_ID}:{APIKEY_URL}@15551234567",
        {
            "instance": NotifyTelesign,
            # throw a bizarre code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        f"telesign://{CUSTOMER_ID}:{APIKEY_URL}@15551234567",
        {
            "instance": NotifyTelesign,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracefully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def _mk_resp(content=OK_RESPONSE, code=requests.codes.ok):
    """Build a mock Telesign response."""
    r = mock.Mock()
    r.status_code = code
    r.content = content
    return r


def test_plugin_telesign_urls():
    """Telesign URLs load and behave as expected."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


def test_plugin_telesign_init():
    """Telesign settings are validated and normalised."""

    # The message type defaults to alerts
    obj = NotifyTelesign(
        user=CUSTOMER_ID, password=APIKEY, targets="+1 555 123 4567"
    )
    assert obj.message_type == "ARN"
    assert obj.source is None
    assert obj.targets == ["15551234567"]
    assert len(obj) == 1

    # The message type and sender are cleaned up
    obj = NotifyTelesign(
        user=CUSTOMER_ID,
        password=APIKEY,
        message_type=" otp ",
        source=" Alerts ",
        targets=["15551234567", "15551234568"],
    )
    assert obj.message_type == "OTP"
    assert obj.source == "Alerts"
    assert len(obj) == 2

    # No phone numbers still counts as one notification
    obj = NotifyTelesign(user=CUSTOMER_ID, password=APIKEY)
    assert len(obj) == 1

    # A missing Customer ID or API Key is refused
    with pytest.raises(AppriseImproperlyConfigured):
        NotifyTelesign(password=APIKEY, targets="15551234567")

    with pytest.raises(AppriseImproperlyConfigured):
        NotifyTelesign(user=CUSTOMER_ID, targets="15551234567")

    # An unknown message type is refused
    with pytest.raises(AppriseImproperlyConfigured):
        NotifyTelesign(user=CUSTOMER_ID, password=APIKEY, message_type="spam")


def test_plugin_telesign_round_trip():
    """A Telesign URL survives url() and parse_url() unchanged."""

    obj = NotifyTelesign(
        user=CUSTOMER_ID,
        password=APIKEY,
        message_type="mkt",
        source="Alerts",
        targets=["15551234567", "15551234568", "bad"],
    )

    # Rebuild it from its own URL
    result = NotifyTelesign.parse_url(obj.url())
    obj2 = NotifyTelesign(**result)

    assert obj.url_identifier == obj2.url_identifier
    assert obj2.password == APIKEY
    assert obj2.targets == obj.targets
    assert obj2.invalid_targets == obj.invalid_targets
    assert obj2.message_type == "MKT"
    assert obj2.source == "Alerts"

    # The default message type is not written to the URL
    obj = NotifyTelesign(
        user=CUSTOMER_ID, password=APIKEY, targets="15551234567"
    )
    assert "type=" not in obj.url()

    # The API Key is hidden in a private URL
    assert APIKEY not in obj.url(privacy=True)

    # A different account is a different connection
    obj3 = NotifyTelesign(user="other", password=APIKEY, targets="15551234567")
    assert obj.url_identifier != obj3.url_identifier


@mock.patch("requests.post")
def test_plugin_telesign_payload(mock_post):
    """Telesign receives the expected request."""

    mock_post.return_value = _mk_resp()

    obj = Apprise.instantiate(
        f"telesign://{CUSTOMER_ID}:{APIKEY_URL}@15551234567?from=Alerts"
    )
    assert isinstance(obj, NotifyTelesign)
    assert obj.notify(title="Title & <b>", body="Body _ . ! * # <")

    assert mock_post.call_count == 1
    args, kwargs = mock_post.call_args
    assert args[0] == "https://rest-ww.telesign.com/v1/messaging"

    # Our credentials are sent with Basic auth
    assert kwargs["auth"] == (CUSTOMER_ID, APIKEY)

    # The title is placed in the body untouched
    assert kwargs["data"] == {
        "phone_number": "15551234567",
        "message": "Title & <b>\r\nBody _ . ! * # <",
        "message_type": "ARN",
        "sender_id": "Alerts",
    }

    # Without a sender, none is sent
    mock_post.reset_mock()
    obj = Apprise.instantiate(
        f"telesign://{CUSTOMER_ID}:{APIKEY_URL}@15551234567?type=otp"
    )
    assert obj.notify(body="123456")
    data = mock_post.call_args[1]["data"]
    assert "sender_id" not in data
    assert data["message_type"] == "OTP"


@mock.patch("requests.post")
def test_plugin_telesign_responses(mock_post):
    """Telesign error responses are reported as failures."""

    obj = Apprise.instantiate(
        f"telesign://{CUSTOMER_ID}:{APIKEY_URL}@15551234567"
    )

    # Telesign explains the error
    mock_post.return_value = _mk_resp(
        json.dumps(
            {
                "reference_id": "0123456789ABCDEF0123456789ABCDEF",
                "status": {
                    "code": 11000,
                    "description": "Invalid value for phone_number.",
                },
            }
        ).encode("utf-8"),
        code=requests.codes.bad_request,
    )
    assert obj.notify(body="test") is False

    # A known HTTP error with no usable body
    mock_post.return_value = _mk_resp(
        b"not json", code=requests.codes.unauthorized
    )
    assert obj.notify(body="test") is False

    # A JSON body that is not an object
    mock_post.return_value = _mk_resp(
        b"[]", code=requests.codes.too_many_requests
    )
    assert obj.notify(body="test") is False

    # A status that is not an object
    mock_post.return_value = _mk_resp(
        b'{"status": "bad"}', code=requests.codes.internal_server_error
    )
    assert obj.notify(body="test") is False

    # No content at all
    mock_post.return_value = _mk_resp(None, code=requests.codes.forbidden)
    assert obj.notify(body="test") is False


@mock.patch("requests.post")
def test_plugin_telesign_partial_failure(mock_post):
    """One refused phone number fails the send but not the others."""

    mock_post.side_effect = [
        _mk_resp(),
        _mk_resp(b"{}", code=requests.codes.bad_request),
    ]

    obj = Apprise.instantiate(
        f"telesign://{CUSTOMER_ID}:{APIKEY_URL}@15551234567/15551234568"
    )
    assert obj.notify(body="test") is False
    assert mock_post.call_count == 2


@mock.patch("requests.post")
def test_plugin_telesign_apprise_integration(mock_post):
    """Telesign works through the Apprise object."""

    mock_post.return_value = _mk_resp()

    aobj = Apprise()
    assert aobj.add(f"telesign://{CUSTOMER_ID}:{APIKEY_URL}@15551234567")
    assert aobj.notify(title="Title", body="Body")
    assert mock_post.call_count == 1
