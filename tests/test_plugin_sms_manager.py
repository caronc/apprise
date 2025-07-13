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
import requests

from apprise import Apprise, NotifyType
from apprise.plugins.smsmanager import NotifySMSManager

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    (
        "smsmgr://",
        {
            # Instantiated but no auth, so no otification can happen
            "instance": TypeError,
        },
    ),
    (
        "smsmgr://:@/",
        {
            # invalid auth
            "instance": TypeError
        },
    ),
    (
        "smsmgr://{}@{}".format("b" * 10, "3" * 5),
        {
            # invalid nubmer provided
            "instance": NotifySMSManager,
            # Expected notify() response because we have no one to notify
            "notify_response": False,
        },
    ),
    (
        "smsmgr://{}@123/{}/abcd/+{}".format("z" * 10, "3" * 11, "4" * 11),
        {
            # includes a few invalid bits of info
            "instance": NotifySMSManager,
            "privacy_url": "smsmgr://z...z@33333333333/+44444444444",
        },
    ),
    (
        "smsmgr://{}@{}?batch=y".format("b" * 5, "4" * 11),
        {
            "instance": NotifySMSManager,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "smsmgr://b...b@44444444444",
        },
    ),
    # Test gateway group
    (
        "smsmgr://{}@{}?gateway=low".format("a" * 10, "1" * 11),
        {
            "instance": NotifySMSManager,
        },
    ),
    (
        "smsmgr://{}@{}?gateway=invalid".format("a" * 10, "1" * 11),
        {
            # invalid gatewwway
            "instance": TypeError,
        },
    ),
    (
        "smsmgr://{}?key={}&from=user".format("1" * 11, "a" * 10),
        {
            # use get args to acomplish the same thing
            "instance": NotifySMSManager,
        },
    ),
    (
        "smsmgr://_?to={},{}&key={}&sender={}".format(
            "1" * 11, "2" * 11, "b" * 10, "5" * 13
        ),
        {
            # use get args to acomplish the same thing
            "instance": NotifySMSManager,
        },
    ),
    (
        "smsmgr://{}@{}".format("a" * 10, "1" * 11),
        {
            "instance": NotifySMSManager,
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "smsmgr://{}@{}".format("a" * 10, "1" * 11),
        {
            "instance": NotifySMSManager,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracfully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_smsmgr_urls():
    """NotifyTemplate() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.get")
def test_plugin_smsmgr_edge_cases(mock_get):
    """NotifySMSManager() Edge Cases."""

    # Initialize some generic (but valid) tokens
    apikey = "my-api-key"
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
    mock_get.return_value = response

    # Instantiate our object
    obj = Apprise.instantiate(
        "smsmgr://{}@{}?batch=n".format(apikey, "/".join(targets))
    )

    assert (
        obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        is True
    )

    # We know there are 2 (valid) targets
    assert len(obj) == 2

    # Test our call count
    assert mock_get.call_count == 2

    # Test
    details = mock_get.call_args_list[0]
    payload = details[1]["params"]
    assert payload["apikey"] == apikey
    assert payload["gateway"] == "high"
    assert payload["number"] == "+15551231234"
    assert payload["message"] == "title\r\nbody"

    details = mock_get.call_args_list[1]
    payload = details[1]["params"]
    assert payload["apikey"] == apikey
    assert payload["gateway"] == "high"
    assert payload["number"] == "15555555555"
    assert payload["message"] == "title\r\nbody"

    # Verify our URL looks good
    assert obj.url().startswith(
        "smsmgr://{}@{}".format(
            apikey, "/".join(["+15551231234", "15555555555"])
        )
    )

    assert "batch=no" in obj.url()

    # Reset our mock object
    mock_get.reset_mock()

    # With our batch in place, our calculations are different
    obj = Apprise.instantiate(
        "smsmgr://{}@{}?batch=y".format(apikey, "/".join(targets))
    )

    # 2 phones were loaded but counted as 1 due to batch flag
    assert len(obj) == 1

    assert (
        obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        is True
    )

    # Test our call count (batched into 1)
    assert mock_get.call_count == 1

    details = mock_get.call_args_list[0]
    payload = details[1]["params"]
    assert payload["apikey"] == apikey
    assert payload["gateway"] == "high"
    assert payload["number"] == "+15551231234;15555555555"
    assert payload["message"] == "title\r\nbody"
