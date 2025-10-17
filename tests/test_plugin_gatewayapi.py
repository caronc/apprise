# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2025, Chris Caron <lead2gold@gmail.com>
#
# GatewayAPI Plugin Tests
# Copyright (c) 2025, tombii
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
import requests

from apprise import Apprise, NotifyType
from apprise.plugins.gatewayapi import NotifyGatewayAPI

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    (
        "gatewayapi://",
        {
            # No API Key specified
            "instance": TypeError,
        },
    ),
    (
        "gatewayapi://:@/",
        {
            # invalid API Key
            "instance": TypeError,
        },
    ),
    (
        "gatewayapi://{}@{}".format("a" * 10, "3" * 5),
        {
            # invalid number provided (too short)
            "instance": TypeError,
        },
    ),
    (
        "gatewayapi://{}@{}".format("a" * 32, "4" * 11),
        {
            # valid API Key and phone number
            "instance": NotifyGatewayAPI,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "gatewayapi://****@",
        },
    ),
    (
        "gatewayapi://{}@{}/{}".format("b" * 32, "5" * 11, "6" * 11),
        {
            # multiple targets
            "instance": NotifyGatewayAPI,
            "privacy_url": "gatewayapi://****@",
        },
    ),
    (
        "gatewayapi://{}@{}?from=MyApp".format("c" * 32, "7" * 11),
        {
            # valid with sender
            "instance": NotifyGatewayAPI,
        },
    ),
    (
        "gatewayapi://{}@{}?key={}".format("d" * 32, "8" * 11, "e" * 32),
        {
            # API Key via query string
            "instance": NotifyGatewayAPI,
        },
    ),
    (
        "gatewayapi://{}@{}?to={}".format("f" * 32, "9" * 11, "1" * 13),
        {
            # use to= for additional targets
            "instance": NotifyGatewayAPI,
        },
    ),
    (
        "gatewayapi://{}@{}/{}".format("g" * 32, "2" * 11, "invalid"),
        {
            # invalid phone number in path
            "instance": NotifyGatewayAPI,
            # Expected notify() response because we have no valid targets
            "notify_response": False,
        },
    ),
    (
        "gatewayapi://{}@123/{}/abcd/+{}".format("h" * 32, "3" * 11, "4" * 11),
        {
            # includes a few invalid bits of info
            "instance": NotifyGatewayAPI,
            "privacy_url": "gatewayapi://****@",
        },
    ),
    (
        "gatewayapi://{}@{}".format("i" * 32, "5" * 11),
        {
            "instance": NotifyGatewayAPI,
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "gatewayapi://{}@{}".format("j" * 32, "6" * 11),
        {
            "instance": NotifyGatewayAPI,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracfully handle them
            "test_requests_exceptions": True,
        },
    ),
    (
        "gatewayapi://{}@{}".format("k" * 32, "7" * 11),
        {
            "instance": NotifyGatewayAPI,
            # Test 201 response code (also valid)
            "requests_response_code": 201,
        },
    ),
    (
        "gatewayapi://{}@{}".format("l" * 32, "8" * 11),
        {
            "instance": NotifyGatewayAPI,
            # Test 400 response code (failure)
            "response": False,
            "requests_response_code": 400,
        },
    ),
    (
        "gatewayapi://{}@{}".format("m" * 32, "9" * 11),
        {
            "instance": NotifyGatewayAPI,
            # Test 401 response code (unauthorized)
            "response": False,
            "requests_response_code": 401,
        },
    ),
    (
        "gatewayapi://{}@{}".format("n" * 32, "1" * 12),
        {
            "instance": NotifyGatewayAPI,
            # Test 500 response code (server error)
            "response": False,
            "requests_response_code": 500,
        },
    ),
)


def test_plugin_gatewayapi_urls():
    """NotifyGatewayAPI() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.post")
def test_plugin_gatewayapi_edge_cases(mock_post):
    """NotifyGatewayAPI() Edge Cases."""

    # Initialize some generic (but valid) tokens
    apikey = "a" * 32
    targets = [
        "+1(555) 123-1234",
        "1555 5555555",
        # A garbage entry
        "12",
    ]

    # Prepare our response
    response = requests.Request()
    response.status_code = requests.codes.ok

    # Prepare Mock
    mock_post.return_value = response

    # Instantiate our object
    obj = Apprise.instantiate("gatewayapi://{}@{}".format(apikey, "/".join(targets)))

    assert obj.notify(body="body", title="title", notify_type=NotifyType.INFO) is True

    # We know there are 2 valid targets (garbage entry excluded)
    assert len(obj) == 2

    # Test our call count
    assert mock_post.call_count == 2

    # Test first call
    details = mock_post.call_args_list[0]
    payload = details[1]["data"]
    assert payload["message"] == "title\r\nbody"
    assert payload["recipients.0.msisdn"] == 15551231234
    assert "sender" not in payload

    # Test second call
    details = mock_post.call_args_list[1]
    payload = details[1]["data"]
    assert payload["message"] == "title\r\nbody"
    assert payload["recipients.0.msisdn"] == 15555555555

    # Verify our URL looks good
    assert obj.url().startswith("gatewayapi://{}@".format("****"))

    # Verify full URL structure
    assert obj.url() == "gatewayapi://{}@{}/{}".format(
        "****", "+15551231234", "15555555555"
    )

    # Reset mock
    mock_post.reset_mock()

    # Test with sender
    obj = Apprise.instantiate(
        "gatewayapi://{}@{}?from=MyApp".format(apikey, targets[0])
    )

    assert obj.notify(body="body", title="title", notify_type=NotifyType.INFO) is True

    assert mock_post.call_count == 1

    details = mock_post.call_args_list[0]
    payload = details[1]["data"]
    assert payload["message"] == "title\r\nbody"
    assert payload["recipients.0.msisdn"] == 15551231234
    assert payload["sender"] == "MyApp"

    # Test authentication
    details = mock_post.call_args_list[0]
    assert details[1]["auth"] == (apikey, "")

    # Verify URL includes sender
    assert "from=MyApp" in obj.url()

    # Reset mock
    mock_post.reset_mock()

    # Test with body only (no title)
    obj = Apprise.instantiate("gatewayapi://{}@{}".format(apikey, targets[0]))

    assert obj.notify(body="body only", notify_type=NotifyType.INFO) is True

    assert mock_post.call_count == 1

    details = mock_post.call_args_list[0]
    payload = details[1]["data"]
    assert payload["message"] == "body only"

    # Reset mock
    mock_post.reset_mock()

    # Test URL restructuring with phone # in host and query args
    obj = Apprise.instantiate(
        "gatewayapi://{}?key={}&to={},{}".format(
            targets[0], apikey, targets[1], targets[2]
        )
    )

    # Should have 2 valid targets
    assert len(obj) == 2

    assert obj.notify(body="test", title="title", notify_type=NotifyType.INFO) is True

    # Test our call count
    assert mock_post.call_count == 2

    # Reset mock
    mock_post.reset_mock()

    # Test with no targets to notify
    obj = Apprise.instantiate("gatewayapi://{}@invalid".format(apikey))

    # Should fail with no valid targets
    assert obj.notify(body="test", notify_type=NotifyType.INFO) is False

    # No API calls should be made
    assert mock_post.call_count == 0

    # Reset mock
    mock_post.reset_mock()

    # Test with API key in password field
    obj = Apprise.instantiate("gatewayapi://:{}@{}".format(apikey, targets[0]))

    assert obj.notify(body="body", title="title", notify_type=NotifyType.INFO) is True

    assert mock_post.call_count == 1

    # Test authentication still works
    details = mock_post.call_args_list[0]
    assert details[1]["auth"] == (apikey, "")


@mock.patch("requests.post")
def test_plugin_gatewayapi_response_codes(mock_post):
    """NotifyGatewayAPI() Response Code Handling."""

    # Initialize tokens
    apikey = "b" * 32
    target = "+15551234567"

    # Test 201 Created response (also valid)
    response = requests.Request()
    response.status_code = 201
    mock_post.return_value = response

    obj = Apprise.instantiate("gatewayapi://{}@{}".format(apikey, target))

    assert obj.notify(body="test", notify_type=NotifyType.INFO) is True

    # Reset mock
    mock_post.reset_mock()

    # Test various error codes
    error_codes = [400, 401, 403, 404, 429, 500, 502, 503]

    for error_code in error_codes:
        response = requests.Request()
        response.status_code = error_code
        response.content = b"Error response"
        mock_post.return_value = response

        obj = Apprise.instantiate("gatewayapi://{}@{}".format(apikey, target))

        assert obj.notify(body="test", notify_type=NotifyType.INFO) is False

        mock_post.reset_mock()
