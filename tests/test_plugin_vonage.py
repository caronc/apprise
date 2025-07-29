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

from apprise.plugins.vonage import NotifyVonage

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    (
        "vonage://",
        {
            # No API Key specified
            "instance": TypeError,
        },
    ),
    (
        "vonage://:@/",
        {
            # invalid Auth key
            "instance": TypeError,
        },
    ),
    (
        "vonage://AC{}@12345678".format("a" * 8),
        {
            # Just a key provided
            "instance": TypeError,
        },
    ),
    (
        "vonage://AC{}:{}@{}".format("a" * 8, "b" * 16, "3" * 9),
        {
            # key and secret provided and from but invalid from no
            "instance": TypeError,
        },
    ),
    (
        "vonage://AC{}:{}@{}/?ttl=0".format("b" * 8, "c" * 16, "3" * 11),
        {
            # Invalid ttl defined
            "instance": TypeError,
        },
    ),
    (
        "vonage://AC{}:{}@{}".format("d" * 8, "e" * 16, "a" * 11),
        {
            # Invalid source number
            "instance": TypeError,
        },
    ),
    (
        "vonage://AC{}:{}@{}/123/{}/abcd/".format(
            "f" * 8, "g" * 16, "3" * 11, "9" * 15
        ),
        {
            # valid everything but target numbers
            "instance": NotifyVonage,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "vonage://A...f:****@",
        },
    ),
    (
        "vonage://AC{}:{}@{}".format("h" * 8, "i" * 16, "5" * 11),
        {
            # using phone no with no target - we text ourselves in
            # this case
            "instance": NotifyVonage,
        },
    ),
    (
        "vonage://_?key=AC{}&secret={}&from={}".format(
            "a" * 8, "b" * 16, "5" * 11
        ),
        {
            # use get args to acomplish the same thing
            "instance": NotifyVonage,
        },
    ),
    (
        "vonage://_?key=AC{}&secret={}&source={}".format(
            "a" * 8, "b" * 16, "5" * 11
        ),
        {
            # use get args to acomplish the same thing (use source instead
            # of from)
            "instance": NotifyVonage,
        },
    ),
    (
        "vonage://_?key=AC{}&secret={}&from={}&to={}".format(
            "a" * 8, "b" * 16, "5" * 11, "7" * 13
        ),
        {
            # use to=
            "instance": NotifyVonage,
        },
    ),
    (
        "vonage://AC{}:{}@{}".format("a" * 8, "b" * 16, "6" * 11),
        {
            "instance": NotifyVonage,
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "vonage://AC{}:{}@{}".format("a" * 8, "b" * 16, "6" * 11),
        {
            "instance": NotifyVonage,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracfully handle them
            "test_requests_exceptions": True,
        },
    ),
    # Nexmo Backwards Support
    (
        "nexmo://",
        {
            # No API Key specified
            "instance": TypeError,
        },
    ),
    (
        "nexmo://:@/",
        {
            # invalid Auth key
            "instance": TypeError,
        },
    ),
    (
        "nexmo://AC{}@12345678".format("a" * 8),
        {
            # Just a key provided
            "instance": TypeError,
        },
    ),
    (
        "nexmo://AC{}:{}@{}".format("a" * 8, "b" * 16, "3" * 9),
        {
            # key and secret provided and from but invalid from no
            "instance": TypeError,
        },
    ),
    (
        "nexmo://AC{}:{}@{}/?ttl=0".format("b" * 8, "c" * 16, "3" * 11),
        {
            # Invalid ttl defined
            "instance": TypeError,
        },
    ),
    (
        "nexmo://AC{}:{}@{}".format("d" * 8, "e" * 16, "a" * 11),
        {
            # Invalid source number
            "instance": TypeError,
        },
    ),
    (
        "nexmo://AC{}:{}@{}/123/{}/abcd/".format(
            "f" * 8, "g" * 16, "3" * 11, "9" * 15
        ),
        {
            # valid everything but target numbers
            "instance": NotifyVonage,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "vonage://A...f:****@",
        },
    ),
    (
        "nexmo://AC{}:{}@{}".format("h" * 8, "i" * 16, "5" * 11),
        {
            # using phone no with no target - we text ourselves in
            # this case
            "instance": NotifyVonage,
        },
    ),
    (
        "nexmo://_?key=AC{}&secret={}&from={}".format(
            "a" * 8, "b" * 16, "5" * 11
        ),
        {
            # use get args to acomplish the same thing
            "instance": NotifyVonage,
        },
    ),
    (
        "nexmo://_?key=AC{}&secret={}&source={}".format(
            "a" * 8, "b" * 16, "5" * 11
        ),
        {
            # use get args to acomplish the same thing (use source instead of
            # from)
            "instance": NotifyVonage,
        },
    ),
    (
        "nexmo://_?key=AC{}&secret={}&from={}&to={}".format(
            "a" * 8, "b" * 16, "5" * 11, "7" * 13
        ),
        {
            # use to=
            "instance": NotifyVonage,
        },
    ),
    (
        "nexmo://AC{}:{}@{}".format("a" * 8, "b" * 16, "6" * 11),
        {
            "instance": NotifyVonage,
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "nexmo://AC{}:{}@{}".format("a" * 8, "b" * 16, "6" * 11),
        {
            "instance": NotifyVonage,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracfully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_vonage_urls():
    """NotifyVonage() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.post")
def test_plugin_vonage_edge_cases(mock_post):
    """NotifyVonage() Edge Cases."""

    # Prepare our response
    response = requests.Request()
    response.status_code = requests.codes.ok

    # Prepare Mock
    mock_post.return_value = response

    # Initialize some generic (but valid) tokens
    apikey = "AC{}".format("b" * 8)
    secret = "{}".format("b" * 16)
    source = "+1 (555) 123-3456"

    # No apikey specified
    with pytest.raises(TypeError):
        NotifyVonage(apikey=None, secret=secret, source=source)

    with pytest.raises(TypeError):
        NotifyVonage(apikey="  ", secret=secret, source=source)

    # No secret specified
    with pytest.raises(TypeError):
        NotifyVonage(apikey=apikey, secret=None, source=source)

    with pytest.raises(TypeError):
        NotifyVonage(apikey=apikey, secret="  ", source=source)

    # a error response
    response.status_code = 400
    response.content = dumps({
        "code": 21211,
        "message": "The 'To' number +1234567 is not a valid phone number.",
    })
    mock_post.return_value = response

    # Initialize our object
    obj = NotifyVonage(apikey=apikey, secret=secret, source=source)

    # We will fail with the above error code
    assert obj.notify("title", "body", "info") is False
