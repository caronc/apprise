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

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise, NotifyType
from apprise.plugins.octopush import NotifyOctopush

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    (
        "octopush://",
        {
            # No API Login or API Key specified
            "instance": TypeError,
        },
    ),
    (
        "octopush://:@/",
        {
            # Invalid API Login
            "instance": TypeError,
        },
    ),
    (
        "octopush://user@myaccount.com",
        {
            # Valid API Login, but no API Key provided
            "instance": TypeError,
        },
    ),
    (
        "octopush://_/apikey?login=invalid",
        {
            # Invalid login
            "instance": TypeError,
        },
    ),
    (
        "octopush://user@myaccount.com/%20",
        {
            # Valid API Login, but invalid API Key provided
            "instance": TypeError,
        },
    ),
    (
        "octopush://%20:user@myaccount.com/apikey",
        {
            # All valid entries, but invalid sender
            "instance": TypeError,
        },
    ),
    (
        "octopush://user@myaccount.com/apikey",
        {
            # All valid entries, but no target phone numbers defined
            "instance": NotifyOctopush,
            "response": False,
        },
    ),
    (
        "octopush://user@myaccount.com/apikey/+0987654321",
        {
            # A valid url
            "instance": NotifyOctopush,
            "requests_response_code": requests.codes.created,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "octopush://u...m/****/+0987654321",
        },
    ),
    (
        "octopush://sender:user@myaccount.com/apikey/+1111111111",
        {
            # A valid url with sender
            "instance": NotifyOctopush,
            "requests_response_code": requests.codes.created,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "octopush://sender:u...m/****/+1111111111",
        },
    ),
    (
        "octopush://?login=user@myaccount.com&key=key&to=9999999999"
        "&purpose=wholesale",
        {
            # Testing valid purpose change
            "instance": NotifyOctopush,
            "requests_response_code": requests.codes.created,
        },
    ),
    (
        "octopush://?login=user@myaccount.com&key=key&to=9999999999"
        "&purpose=invalid",
        {
            # Testing invalid purpose change
            "instance": TypeError,
        },
    ),
    (
        "octopush://?login=user@myaccount.com&key=key&to=9999999999"
        "&type=premium",
        {
            # Testing valid type change
            "instance": NotifyOctopush,
            "requests_response_code": requests.codes.created,
        },
    ),
    (
        "octopush://?login=user@myaccount.com&key=key&to=9999999999"
        "&type=invalid",
        {
            # Testing invalid type change
            "instance": TypeError,
        },
    ),
    (
        "octopush://user@myaccount.com/apikey/+3333333333?replies=yes",
        {
            # Test replies
            "instance": NotifyOctopush,
            "requests_response_code": requests.codes.created,
        },
    ),
    (
        "octopush://sender:user@myaccount.com/apikey/{}/{}/{}/?batch=yes".format(
            "1" * 10, "2" * 3, "3" * 11
        ),
        {
            # batch mode, 2 valid targets (1 is invalid and skipped)
            "instance": NotifyOctopush,
            "requests_response_code": requests.codes.created,
        },
    ),
    (
        "octopush://_?key=abc123&login=user@myaccount.com&sender=abc"
        "&to=2222222222",
        {
            # use get args to accomplish the same thing
            "instance": NotifyOctopush,
            "requests_response_code": requests.codes.created,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "octopush://abc:u...m/****/+2222222222",
        },
    ),
    (
        "octopush://user@myaccount.com/apikey/1234567890",
        {
            "instance": NotifyOctopush,
            # throw a bizarre code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "octopush://user@myaccount.com/apikey/1234567890",
        {
            "instance": NotifyOctopush,
            # Throws a series of connection and transfer exceptions when this
            # flag is set and tests that we gracefully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_octopush_urls():
    """NotifyOctopush() Apprise URLs."""

    assert (
        NotifyOctopush.setup_url == "https://appriseit.com/services/octopush/"
    )

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


def test_plugin_octopush_parse_url_and_validation():
    """NotifyOctopush() parse_url() and validation coverage."""

    assert NotifyOctopush.parse_url(None) is None

    with pytest.raises(TypeError):
        NotifyOctopush(
            api_login="user@myaccount.com",
            api_key="apikey",
            targets=("1234567890",),
            purpose=" ",
        )

    results = NotifyOctopush.parse_url(
        "octopush://sender:user@myaccount.com/apikey/1234567890"
        "?to=2345678901&type=sms_premium&purpose=alert&batch=yes"
        "&replies=no"
    )
    assert isinstance(results, dict)
    assert results["api_key"] == "apikey"
    assert results["api_login"] == "user@myaccount.com"
    assert results["sender"] == "sender"
    assert results["targets"] == ["1234567890", "2345678901"]
    assert results["mtype"] == "sms_premium"
    assert results["purpose"] == "alert"
    assert results["batch"] is True
    assert results["replies"] is False

    results = NotifyOctopush.parse_url(
        "octopush://_?login=user@myaccount.com&key=apikey&sender=abc"
        "&to=3456789012&type=sms_low_cost&purpose=wholesale"
        "&batch=no&replies=yes"
    )
    assert isinstance(results, dict)
    assert results["api_key"] == "apikey"
    assert results["api_login"] == "user@myaccount.com"
    assert results["sender"] == "abc"
    assert results["targets"] == ["3456789012"]
    assert results["mtype"] == "sms_low_cost"
    assert results["purpose"] == "wholesale"
    assert results["batch"] is False
    assert results["replies"] is True


@mock.patch("requests.post")
def test_plugin_octopush_edge_cases(mock_post):
    """NotifyOctopush() Edge Cases."""

    response = requests.Request()
    response.status_code = requests.codes.created
    mock_post.return_value = response

    obj = Apprise.instantiate(
        "octopush://sender:user@myaccount.com/apikey/1234567890/2345678901"
        "?batch=yes&replies=yes&type=low_cost&purpose=wholesale"
    )

    assert isinstance(obj, NotifyOctopush)
    assert len(obj) == 1
    assert obj.targets == ["+1234567890", "+2345678901"]
    assert obj.mtype == "sms_low_cost"
    assert obj.purpose == "wholesale"
    assert obj.replies is True

    assert obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
    assert mock_post.call_count == 1

    call = mock_post.call_args_list[0]
    assert call[0][0] == "https://api.octopush.com/v1/public/sms-campaign/send"

    headers = call[1]["headers"]
    assert headers["api-login"] == "user@myaccount.com"
    assert headers["api-key"] == "apikey"
    assert headers["Content-Type"] == "application/json; charset=utf-8"

    payload = call[1]["data"]
    assert '"type": "sms_low_cost"' in payload
    assert '"purpose": "wholesale"' in payload
    assert '"with_replies": true' in payload
    assert '"phone_number": "+1234567890"' in payload
    assert '"phone_number": "+2345678901"' in payload

    obj = NotifyOctopush(
        api_login="user@myaccount.com",
        api_key="apikey",
        targets=tuple(str(1000000000 + i) for i in range(501)),
        batch=True,
    )
    assert len(obj) == 2

    mock_post.reset_mock()
    assert obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
    assert mock_post.call_count == 2

    first_payload = mock_post.call_args_list[0][1]["data"]
    assert first_payload.count('"phone_number"') == 500

    second_payload = mock_post.call_args_list[1][1]["data"]
    assert second_payload.count('"phone_number"') == 1
