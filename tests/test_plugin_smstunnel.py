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

from json import dumps, loads

# Disable logging for a cleaner testing output
import logging
from unittest import mock

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise, NotifyType
from apprise.exception import AppriseImproperlyConfigured
from apprise.plugins.smstunnel import NotifySMSTunnel

logging.disable(logging.CRITICAL)

# A key in the format SMSTunnel hands out
APIKEY = "sk_live_" + "a" * 32

# A Device ID in the format SMSTunnel hands out
DEVICE = "0123456789abcdef01234567"

# Our Testing URLs
apprise_url_tests = (
    (
        "smstunnel://",
        {
            # No API Key
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "smstunnel://:@/",
        {
            # invalid API Key
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "smstunnel://14155550123?key=bad%20key",
        {
            # The API Key may not contain spaces
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        f"smstunnel://{APIKEY}",
        {
            # No phone number to notify
            "instance": NotifySMSTunnel,
            # Expected notify() response because we have no one to notify
            "notify_response": False,
        },
    ),
    (
        f"smstunnel://{APIKEY}/{'5' * 2}/abcd",
        {
            # Only invalid phone numbers were provided
            "instance": NotifySMSTunnel,
            # Expected notify() response because we have no one to notify
            "notify_response": False,
            # The invalid entries are kept in our URL
            "privacy_url": "smstunnel://s...a/55/abcd",
        },
    ),
    (
        f"smstunnel://{APIKEY}/+14155550123",
        {
            "instance": NotifySMSTunnel,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "smstunnel://s...a/+14155550123",
        },
    ),
    (
        f"smstunnel://{APIKEY}/14155550123/14155550124/abcd/",
        {
            # Valid phone numbers and a garbage string (abcd)
            "instance": NotifySMSTunnel,
            "privacy_url": (
                "smstunnel://s...a/+14155550123/+14155550124/abcd"
            ),
        },
    ),
    (
        f"smstunnel://{APIKEY}/0712345678?country=40",
        {
            # A local number completed with our country code
            "instance": NotifySMSTunnel,
            "privacy_url": "smstunnel://s...a/+40712345678",
            "url_matches": r"country=40",
        },
    ),
    (
        f"smstunnel://{APIKEY}/0712345678",
        {
            # A local number without a country code can not be used
            "instance": NotifySMSTunnel,
            "notify_response": False,
        },
    ),
    (
        f"smstunnel://{APIKEY}/14155550123?country=abc",
        {
            # An invalid country code
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        f"smstunnel://{APIKEY}/14155550123?device={DEVICE}",
        {
            # Send from one specific phone
            "instance": NotifySMSTunnel,
            "url_matches": rf"device={DEVICE}",
        },
    ),
    (
        f"smstunnel://{APIKEY}/14155550123?device=bad%20device",
        {
            # An invalid Device ID
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        f"smstunnel://?key={APIKEY}&to=14155550123,14155550124",
        {
            # use get args to acomplish the same thing
            "instance": NotifySMSTunnel,
            "privacy_url": "smstunnel://s...a/+14155550123/+14155550124",
        },
    ),
    (
        f"smstunnel://14155550123?key={APIKEY}",
        {
            # With ?key= the host is a phone number to notify
            "instance": NotifySMSTunnel,
            "privacy_url": "smstunnel://s...a/+14155550123",
        },
    ),
    (
        f"smstunnel://{APIKEY}/14155550123",
        {
            "instance": NotifySMSTunnel,
            # The phone was offline; the text waits for it
            "requests_response_text": {
                "success": True,
                "messageId": "1",
                "queued": True,
            },
        },
    ),
    (
        f"smstunnel://{APIKEY}/14155550123",
        {
            "instance": NotifySMSTunnel,
            # A response that is not a JSON object still counts on its
            # status code
            "requests_response_text": ["unexpected"],
        },
    ),
    (
        f"smstunnel://{APIKEY}/14155550123",
        {
            "instance": NotifySMSTunnel,
            # SMSTunnel answered but did not accept the text
            "response": False,
            "requests_response_code": requests.codes.ok,
            "requests_response_text": {
                "success": False,
                "error": "Unable to send",
            },
        },
    ),
    (
        f"smstunnel://{APIKEY}/14155550123",
        {
            "instance": NotifySMSTunnel,
            # The API Key lacks a permission
            "response": False,
            "requests_response_code": requests.codes.forbidden,
            "requests_response_text": {
                "message": "Missing permission: sms:send",
                "error": "Forbidden",
                "statusCode": 403,
            },
        },
    ),
    (
        f"smstunnel://{APIKEY}/14155550123",
        {
            "instance": NotifySMSTunnel,
            # throw a bizarre code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        f"smstunnel://{APIKEY}/14155550123",
        {
            "instance": NotifySMSTunnel,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracefully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_smstunnel_urls():
    """NotifySMSTunnel() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.post")
def test_plugin_smstunnel_edge_cases(mock_post):
    """NotifySMSTunnel() Edge Cases."""

    # Prepare our response
    response = requests.Request()
    response.status_code = requests.codes.ok
    response.content = dumps(
        {
            "success": True,
            "messageId": "1",
            "data": {"messageId": "1", "branded": False},
        }
    )

    # Prepare Mock
    mock_post.return_value = response

    targets = [
        "+1(415) 555-0123",
        "1415 5550124",
        # A garbage entry
        "12",
    ]

    # Instantiate our object
    obj = Apprise.instantiate(
        "smstunnel://{}/{}?device={}".format(APIKEY, "/".join(targets), DEVICE)
    )
    assert isinstance(obj, NotifySMSTunnel)

    # We know there are 2 targets
    assert len(obj) == 2

    assert (
        bool(
            obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        )
        is True
    )

    # One text is sent per phone number
    assert mock_post.call_count == 2

    details = mock_post.call_args_list[0]
    assert details[0][0] == "https://smstunnel.io/api/v1/sms/send"
    assert details[1]["headers"]["X-API-Key"] == APIKEY
    assert details[1]["headers"]["Content-Type"] == "application/json"
    payload = loads(details[1]["data"])
    assert payload == {
        "to": "+14155550123",
        "message": "title\r\nbody",
        "deviceId": DEVICE,
    }

    details = mock_post.call_args_list[1]
    payload = loads(details[1]["data"])
    assert payload["to"] == "+14155550124"
    assert payload["message"] == "title\r\nbody"

    # Verify our URL looks good
    assert obj.url().startswith(
        f"smstunnel://{APIKEY}/+14155550123/+14155550124/12?device={DEVICE}"
    )

    # The phone is only named when one was asked for
    mock_post.reset_mock()
    obj = Apprise.instantiate(f"smstunnel://{APIKEY}/14155550123")
    assert obj.notify(body="body") is True
    assert mock_post.call_count == 1
    payload = loads(mock_post.call_args_list[0][1]["data"])
    assert payload == {"to": "+14155550123", "message": "body"}


def test_plugin_smstunnel_phone_numbers():
    """NotifySMSTunnel() Phone number handling."""

    # International numbers are used as they are
    obj = NotifySMSTunnel(
        apikey=APIKEY,
        targets=["+40 712 345 678", "0040712345679", "14155550123"],
    )
    assert obj.targets == ["40712345678", "40712345679", "14155550123"]
    assert obj.invalid_targets == []
    assert obj.country is None

    # A local number needs a country code
    obj = NotifySMSTunnel(apikey=APIKEY, targets=["0712 345 678"])
    assert obj.targets == []
    assert obj.invalid_targets == ["0712 345 678"]
    assert len(obj) == 1

    # Each way of writing a country code means the same thing
    for country in ("40", "+40", "0040", " 40 "):
        obj = NotifySMSTunnel(
            apikey=APIKEY,
            targets=["0712 345 678", "+14155550123"],
            country=country,
        )
        assert obj.country == "40"

        # The leading 0 of a local number makes way for the country code;
        # a number with a + already has its own
        assert obj.targets == ["40712345678", "14155550123"]

    # Where local numbers have no leading 0, the country code is put in
    # front of them
    obj = NotifySMSTunnel(
        apikey=APIKEY, targets=["(415) 555-0124", "+40712345678"], country=1
    )
    assert obj.country == "1"
    assert obj.targets == ["14155550124", "40712345678"]

    # Bad country codes
    for country in ("abc", "0", "1234", "+"):
        with pytest.raises(AppriseImproperlyConfigured):
            NotifySMSTunnel(
                apikey=APIKEY, targets="14155550123", country=country
            )

    # A blank country code or Device ID is treated as unset
    obj = NotifySMSTunnel(
        apikey=APIKEY, targets="14155550123", country="  ", device="  "
    )
    assert obj.country is None
    assert obj.device is None
    assert "country=" not in obj.url()
    assert "device=" not in obj.url()

    # A missing API Key
    with pytest.raises(AppriseImproperlyConfigured):
        NotifySMSTunnel(apikey=None, targets="14155550123")

    # The URL we build loads back into the same targets
    obj = NotifySMSTunnel(
        apikey=APIKEY, targets=["0712345678", "abcd"], country="40"
    )
    clone = Apprise.instantiate(obj.url())
    assert clone.targets == obj.targets == ["40712345678"]
    assert clone.invalid_targets == obj.invalid_targets == ["abcd"]
    assert clone.country == "40"
    assert clone.url_identifier == obj.url_identifier

    # The phone that sends is part of what identifies us
    one = NotifySMSTunnel(apikey=APIKEY, targets="14155550123")
    two = NotifySMSTunnel(apikey=APIKEY, targets="14155550123", device=DEVICE)
    assert one.url_identifier != two.url_identifier
    assert one.url_id() != two.url_id()


@mock.patch("requests.post")
def test_plugin_smstunnel_errors(mock_post):
    """NotifySMSTunnel() Error reporting."""

    obj = NotifySMSTunnel(
        apikey=APIKEY, targets=["14155550123", "14155550124"]
    )

    # No delays between our requests
    obj.request_rate_per_sec = 0

    def answer(status_code, content):
        """Prepare the response SMSTunnel gives."""
        response = requests.Request()
        response.status_code = status_code
        response.content = content
        mock_post.return_value = response

    def warning():
        """Send and return the warning logged about the failure."""
        mock_post.reset_mock()
        with mock.patch.object(obj.logger, "warning") as mock_warning:
            assert obj.notify(body="body") is False

        # Each phone number was tried and reported on its own
        assert mock_post.call_count == 2
        assert mock_warning.call_count == 2
        return mock_warning.call_args_list[0][0]

    # SMSTunnel explains what went wrong; we keep its words
    answer(
        requests.codes.forbidden,
        dumps(
            {
                "message": "Missing permission: sms:send",
                "error": "Forbidden",
                "statusCode": 403,
            }
        ),
    )
    args = warning()
    assert args[1] == "+14155550123"
    assert args[2] == (
        "Forbidden - The API Key or plan does not allow this text. "
        "Missing permission: sms:send"
    )
    assert args[4] == 403

    # A bad API Key
    answer(
        requests.codes.unauthorized,
        dumps(
            {
                "message": "Invalid or expired API key",
                "error": "Unauthorized",
                "statusCode": 401,
            }
        ),
    )
    args = warning()
    assert args[2].startswith("Unauthorized - The API Key is invalid")
    assert args[2].endswith("Invalid or expired API key")

    # Every refused field is listed
    answer(
        requests.codes.bad_request,
        dumps(
            {
                "message": ["to must be a phone number", "message too long"],
                "error": "Bad Request",
                "statusCode": 400,
            }
        ),
    )
    args = warning()
    assert args[2].endswith("to must be a phone number; message too long")

    # Too many requests, without a JSON body
    answer(requests.codes.too_many_requests, b"Too Many Requests")
    args = warning()
    assert args[2] == "Too many requests were made; try again later."
    assert args[4] == 429

    # An empty answer
    answer(requests.codes.service_unavailable, None)
    args = warning()
    assert args[2] == "SMSTunnel is unavailable; try again later."

    # A status we know nothing about still carries SMSTunnel's words
    answer(999, dumps({"message": "Something odd happened"}))
    args = warning()
    assert args[2] == "Something odd happened"
    assert args[3] == ", "

    # A status we know nothing about and no explanation
    answer(999, b"")
    args = warning()
    assert args[2] == ""
    assert args[3] == ""
