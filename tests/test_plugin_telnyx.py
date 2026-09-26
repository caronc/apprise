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

from helpers import AppriseURLTester
import requests

from apprise import Apprise, NotifyType
from apprise.exception import AppriseImproperlyConfigured
from apprise.plugins.telnyx import NotifyTelnyx

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    (
        "telnyx://",
        {
            # Instantiated but no auth, so no notification can happen
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "telnyx://:@/",
        {
            # invalid token
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "telnyx://{}:{}@{}".format("u" * 10, "p" * 10, "3" * 5),
        {
            # invalid source number provided
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "telnyx://{}@{}/{}".format("p" * 10, "1" * 10, 2 * "5"),
        {
            # invalid target number provided
            "instance": NotifyTelnyx,
            # Expected notify() response because we have no one to notify
            "notify_response": False,
        },
    ),
    (
        "telnyx://{}@{}".format("p" * 10, "2" * 10),
        {
            # default to ourselves
            "instance": NotifyTelnyx,
        },
    ),
    (
        "telnyx://{}@9876543210/{}/abcd/".format("b" * 10, "3" * 11),
        {
            # included phone, short number (123) and garbage string (abcd)
            # dropped
            "instance": NotifyTelnyx,
            "privacy_url": "telnyx://b...b@9876543210/33333333333",
        },
    ),
    (
        "telnyx://{}@{}".format("c" * 10, "4" * 11),
        {
            "instance": NotifyTelnyx,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "telnyx://c...c@44444444444",
        },
    ),
    (
        "telnyx://{}@{}".format("b" * 10, "5" * 11),
        {
            # using phone no with no target - we text ourselves in this case
            "instance": NotifyTelnyx,
        },
    ),
    (
        "telnyx://?key={}&from={}".format("y" * 10, "5" * 11),
        {
            # use get args to acomplish the same thing
            "instance": NotifyTelnyx,
        },
    ),
    (
        "telnyx://?key={}&from={}&to={}".format("b" * 10, "5" * 11, "7" * 13),
        {
            # use to= and key=
            "instance": NotifyTelnyx,
        },
    ),
    (
        "telnyx://{}@{}?profile=abcd-1234".format("d" * 10, "5" * 11),
        {
            # Messaging Profile ID specified
            "instance": NotifyTelnyx,
            "privacy_url": "telnyx://d...d@55555555555/?profile=abcd-1234",
        },
    ),
    (
        "telnyx://{}@{}".format("b" * 10, "5" * 11),
        {
            "instance": NotifyTelnyx,
            # A failure from the upstream server
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "telnyx://{}@{}".format("b" * 10, "5" * 11),
        {
            "instance": NotifyTelnyx,
            # throw a bizarre code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "telnyx://{}@{}".format("b" * 10, "5" * 11),
        {
            "instance": NotifyTelnyx,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracefully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_telnyx_urls():
    """NotifyTemplate() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.post")
def test_plugin_telnyx_edge_cases(mock_post):
    """NotifyTelnyx() Edge Cases."""

    # Initialize some generic (but valid) tokens
    apikey = "KEY0123456789ABCDEF_abcdefghij"
    source = "1 (405) 123 1234"
    targets = [
        "+1(555) 123-1234",
        "1555 5555555",
        # A garbage entry
        "12",
        # Now a valid one because a group was implicit
        "@12",
    ]

    # Prepare our response
    response = requests.Request()
    response.status_code = requests.codes.ok

    # Prepare Mock
    mock_post.return_value = response

    # Instantiate our object
    obj = Apprise.instantiate(
        "telnyx://{}@{}/{}".format(apikey, source, "/".join(targets))
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
    assert details[0][0] == "https://api.telnyx.com/v2/messages"
    assert (
        details[1]["headers"]["Authorization"]
        == "Bearer KEY0123456789ABCDEF_abcdefghij"
    )
    payload = loads(details[1]["data"])
    assert payload["from"] == "+14051231234"
    assert payload["to"] == "+15551231234"
    assert payload["text"] == "title\r\nbody"
    assert "messaging_profile_id" not in payload

    details = mock_post.call_args_list[1]
    payload = loads(details[1]["data"])
    assert payload["from"] == "+14051231234"
    assert payload["to"] == "+15555555555"
    assert payload["text"] == "title\r\nbody"
    assert "messaging_profile_id" not in payload

    # Verify our URL looks good
    assert obj.url().startswith(
        "telnyx://KEY0123456789ABCDEF_abcdefghij@14051231234/"
        "15551231234/15555555555"
    )

    # Messaging Profile ID is passed along when specified
    mock_post.reset_mock()
    obj = Apprise.instantiate(
        "telnyx://{}@{}/{}?profile={}".format(
            apikey, source, targets[0], "40017-abcd"
        )
    )
    assert obj.notify(body="body") is True
    assert mock_post.call_count == 1
    payload = loads(mock_post.call_args_list[0][1]["data"])
    assert payload["to"] == "+15551231234"
    assert payload["messaging_profile_id"] == "40017-abcd"
    assert "profile=40017-abcd" in obj.url()

    # Our URL round-trips
    obj2 = Apprise.instantiate(obj.url())
    assert obj2.url_id() == obj.url_id()
    assert obj2.profile == "40017-abcd"
