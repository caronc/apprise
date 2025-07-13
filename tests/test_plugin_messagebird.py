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

# Disable logging for a cleaner testing output
import logging
from unittest import mock

from helpers import AppriseURLTester
import pytest
import requests

from apprise.plugins.messagebird import NotifyMessageBird

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    (
        "msgbird://",
        {
            # No hostname/apikey specified
            "instance": TypeError,
        },
    ),
    (
        "msgbird://{}/abcd".format("a" * 25),
        {
            # invalid characters in source phone number
            "instance": TypeError,
        },
    ),
    (
        "msgbird://{}/123".format("a" * 25),
        {
            # invalid source phone number
            "instance": TypeError,
        },
    ),
    (
        "msgbird://{}/15551232000".format("a" * 25),
        {
            # target phone number becomes who we text too; all is good
            "instance": NotifyMessageBird,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "msgbird://a...a/15551232000",
        },
    ),
    (
        "msgbird://{}/15551232000/abcd".format("a" * 25),
        {
            # valid credentials
            "instance": NotifyMessageBird,
            # Since there are no targets specified we expect a False return on
            # send()
            "notify_response": False,
        },
    ),
    (
        "msgbird://{}/15551232000/123".format("a" * 25),
        {
            # valid credentials
            "instance": NotifyMessageBird,
            # Since there are no targets specified we expect a False return on
            # send()
            "notify_response": False,
        },
    ),
    (
        "msgbird://{}/?from=15551233000&to=15551232000".format("a" * 25),
        {
            # reference to to= and from=
            "instance": NotifyMessageBird,
        },
    ),
    (
        "msgbird://{}/15551232000".format("a" * 25),
        {
            "instance": NotifyMessageBird,
            # force a failure
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "msgbird://{}/15551232000".format("a" * 25),
        {
            "instance": NotifyMessageBird,
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "msgbird://{}/15551232000".format("a" * 25),
        {
            "instance": NotifyMessageBird,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracfully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_messagebird_urls():
    """NotifyTemplate() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.post")
def test_plugin_messagebird_edge_cases(mock_post):
    """NotifyMessageBird() Edge Cases."""

    # Prepare our response
    response = requests.Request()
    response.status_code = requests.codes.ok

    # Prepare Mock
    mock_post.return_value = response

    # Initialize some generic (but valid) tokens
    # authkey = '{}'.format('a' * 24)
    source = "+1 (555) 123-3456"

    # No apikey specified
    with pytest.raises(TypeError):
        NotifyMessageBird(apikey=None, source=source)
    with pytest.raises(TypeError):
        NotifyMessageBird(apikey="     ", source=source)
