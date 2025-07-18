# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2025, Chris Caron <lead2gold@gmail.com>
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

from json import dumps

# Disable logging for a cleaner testing output
import logging
from unittest import mock

from helpers import AppriseURLTester
import pytest
import requests

from apprise.plugins.burstsms import NotifyBurstSMS

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    (
        "burstsms://",
        {
            # No API Key specified
            "instance": TypeError,
        },
    ),
    (
        "burstsms://:@/",
        {
            # invalid Auth key
            "instance": TypeError,
        },
    ),
    (
        "burstsms://{}@12345678".format("a" * 8),
        {
            # Just a key provided
            "instance": TypeError,
        },
    ),
    (
        "burstsms://{}:{}@%20".format("d" * 8, "e" * 16),
        {
            # Invalid source number
            "instance": TypeError,
        },
    ),
    (
        "burstsms://{}:{}@{}/123/{}/abcd/".format(
            "f" * 8, "g" * 16, "3" * 11, "9" * 15
        ),
        {
            # valid everything but target numbers
            "instance": NotifyBurstSMS,
            # Expected notify() response because not all targets are valid
            "notify_response": False,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "burstsms://f...f:****@",
        },
    ),
    (
        "burstsms://{}:{}@{}".format("h" * 8, "i" * 16, "5" * 11),
        {
            "instance": NotifyBurstSMS,
            # Expected notify() response because no targets are defined
            "notify_response": False,
        },
    ),
    (
        "burstsms://_?key={}&secret={}&from={}&to={}".format(
            "a" * 8, "b" * 16, "5" * 11, "6" * 11
        ),
        {
            # use get args to acomplish the same thing
            "instance": NotifyBurstSMS,
        },
    ),
    (
        "burstsms://_?key={}&secret={}&from={}&to={}&batch=y".format(
            "a" * 8, "b" * 16, "5" * 11, "6" * 11
        ),
        {
            # batch flag set
            "instance": NotifyBurstSMS,
        },
    ),
    # Test our country
    (
        "burstsms://_?key={}&secret={}&source={}&to={}&country=us".format(
            "a" * 8, "b" * 16, "5" * 11, "6" * 11
        ),
        {
            "instance": NotifyBurstSMS,
        },
    ),
    # Test an invalid country
    (
        "burstsms://_?key={}&secret={}&source={}&to={}&country=invalid".format(
            "a" * 8, "b" * 16, "5" * 11, "6" * 11
        ),
        {
            "instance": TypeError,
        },
    ),
    # Test our validity
    (
        "burstsms://_?key={}&secret={}&source={}&to={}&validity=10".format(
            "a" * 8, "b" * 16, "5" * 11, "6" * 11
        ),
        {
            "instance": NotifyBurstSMS,
        },
    ),
    # Test an invalid country
    (
        "burstsms://_?key={}&secret={}&source={}&to={}&validity=invalid"
        .format("a" * 8, "b" * 16, "5" * 11, "6" * 11),
        {
            "instance": TypeError,
        },
    ),
    (
        "burstsms://_?key={}&secret={}&from={}&to={}".format(
            "a" * 8, "b" * 16, "5" * 11, "7" * 11
        ),
        {
            # use to=
            "instance": NotifyBurstSMS,
        },
    ),
    (
        "burstsms://{}:{}@{}/{}".format("a" * 8, "b" * 16, "6" * 11, "7" * 11),
        {
            "instance": NotifyBurstSMS,
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "burstsms://{}:{}@{}/{}".format("a" * 8, "b" * 16, "6" * 11, "7" * 11),
        {
            "instance": NotifyBurstSMS,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracfully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_burstsms_urls():
    """NotifyBurstSMS() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.post")
def test_plugin_burstsms_edge_cases(mock_post):
    """NotifyBurstSMS() Edge Cases."""

    # Prepare our response
    response = requests.Request()
    response.status_code = requests.codes.ok

    # Prepare Mock
    mock_post.return_value = response

    # Initialize some generic (but valid) tokens
    apikey = "{}".format("b" * 8)
    secret = "{}".format("b" * 16)
    source = "+1 (555) 123-3456"

    # No apikey specified
    with pytest.raises(TypeError):
        NotifyBurstSMS(apikey=None, secret=secret, source=source)

    with pytest.raises(TypeError):
        NotifyBurstSMS(apikey="  ", secret=secret, source=source)

    # No secret specified
    with pytest.raises(TypeError):
        NotifyBurstSMS(apikey=apikey, secret=None, source=source)

    with pytest.raises(TypeError):
        NotifyBurstSMS(apikey=apikey, secret="  ", source=source)

    # a error response
    response.status_code = 400
    response.content = dumps({
        "error": {
            "code": "FIELD_INVALID",
            "description": (
                "Sender ID must be one of the numbers that are currently"
                " leased."
            ),
        },
    })
    mock_post.return_value = response

    # Initialize our object
    obj = NotifyBurstSMS(apikey=apikey, secret=secret, source=source)

    # We will fail with the above error code
    assert obj.notify("title", "body", "info") is False
