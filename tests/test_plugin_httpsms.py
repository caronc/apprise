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

from json import loads

# Disable logging for a cleaner testing output
import logging
from unittest import mock

from helpers import AppriseURLTester
import requests

from apprise import Apprise, NotifyType
from apprise.plugins.httpsms import NotifyHttpSMS

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    (
        "httpsms://",
        {
            # Instantiated but no auth, so no notification can happen
            "instance": TypeError,
        },
    ),
    (
        "httpsms://:@/",
        {
            # invalid token
            "instance": TypeError,
        },
    ),
    (
        "httpsms://{}:{}@{}".format("u" * 10, "p" * 10, "3" * 5),
        {
            # invalid source number provided
            "instance": TypeError,
        },
    ),
    (
        "httpsms://{}@{}/{}".format("p" * 10, "1" * 10, 2 * "5"),
        {
            # invalid target number provided
            "instance": NotifyHttpSMS,
            # Expected notify() response because we have no one to notify
            "notify_response": False,
        },
    ),
    (
        "httpsms://{}@{}".format("p" * 10, "2" * 10),
        {
            # default to ourselves
            "instance": NotifyHttpSMS,
        },
    ),
    (
        "httpsms://{}@9876543210/{}/abcd/".format("b" * 10, "3" * 11),
        {
            # included phone, short number (123) and garbage string (abcd)
            # dropped
            "instance": NotifyHttpSMS,
            "privacy_url": "httpsms://b...b@9876543210/33333333333",
        },
    ),
    (
        "httpsms://{}@{}".format("c" * 10, "4" * 11),
        {
            "instance": NotifyHttpSMS,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "httpsms://c...c@44444444444",
        },
    ),
    (
        "httpsms://{}@{}".format("b" * 10, "5" * 11),
        {
            # using phone no with no target - we text ourselves in this case
            "instance": NotifyHttpSMS,
        },
    ),
    (
        "httpsms://?key={}&from={}".format("y" * 10, "5" * 11),
        {
            # use get args to acomplish the same thing
            "instance": NotifyHttpSMS,
        },
    ),
    (
        "httpsms://?key={}&from={}&to={}".format("b" * 10, "5" * 11, "7" * 13),
        {
            # use to= and key=
            "instance": NotifyHttpSMS,
        },
    ),
    (
        "httpsms://{}@{}".format("b" * 10, "5" * 11),
        {
            "instance": NotifyHttpSMS,
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "httpsms://{}@{}".format("b" * 10, "5" * 11),
        {
            "instance": NotifyHttpSMS,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracfully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_httpsms_urls():
    """NotifyTemplate() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.post")
def test_plugin_httpsms_edge_cases(mock_post):
    """NotifyHttpSMS() Edge Cases."""

    # Initialize some generic (but valid) tokens
    apikey = "mykey123"
    source = "1 (405) 123 1234"
    targets = [
        "+1(555) 123-1234",
        "1555 5555555",
        # A garbage entry
        "12",
        # NOw a valid one because a group was implicit
        "@12",
    ]

    # Prepare our response
    response = requests.Request()
    response.status_code = requests.codes.ok

    # Prepare Mock
    mock_post.return_value = response

    # Instantiate our object
    obj = Apprise.instantiate(
        "httpsms://{}@{}/{}".format(apikey, source, "/".join(targets))
    )

    assert (
        obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        is True
    )

    # We know there are 2 targets
    assert len(obj) == 2

    # Test our call count
    assert mock_post.call_count == 2

    # Test
    details = mock_post.call_args_list[0]
    payload = loads(details[1]["data"])
    assert payload["from"] == "+14051231234"
    assert payload["to"] == "+15551231234"
    assert payload["content"] == "title\r\nbody"

    details = mock_post.call_args_list[1]
    payload = loads(details[1]["data"])
    assert payload["from"] == "+14051231234"
    assert payload["to"] == "+15555555555"
    assert payload["content"] == "title\r\nbody"

    # Verify our URL looks good
    assert obj.url().startswith(
        "httpsms://mykey123@14051231234/15551231234/15555555555"
    )
