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
from apprise.plugins.africas_talking import NotifyAfricasTalking

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    (
        "atalk://",
        {
            # Instantiated but no auth, so no notification can happen
            "instance": TypeError,
        },
    ),
    (
        "atalk://:@/",
        {
            # invalid auth
            "instance": TypeError
        },
    ),
    (
        "atalk://user@^/",
        {
            # invalid apikey
            "instance": TypeError
        },
    ),
    (
        "atalk://user@apikey/{}".format("3" * 5),
        {
            # invalid nubmer provided
            "instance": NotifyAfricasTalking,
            # Expected notify() response because we have no one to notify
            "notify_response": False,
        },
    ),
    (
        "atalk://user@apikey/123/{}/abcd/+{}".format("3" * 11, "4" * 11),
        {
            # includes a few invalid bits of info
            "instance": NotifyAfricasTalking,
            "privacy_url": "atalk://user@a...y/33333333333/+44444444444",
        },
    ),
    (
        "atalk://user@apikey/+{}?batch=y".format("4" * 11),
        {
            "instance": NotifyAfricasTalking,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "atalk://user@a...y/+44444444444",
        },
    ),
    (
        "atalk://user@apikey/+{}?mode=invalid".format("4" * 11),
        {"instance": TypeError},
    ),
    (
        "atalk://user@apikey/+{}?mode=s".format("4" * 11),
        {
            # S will match the sandbox
            "instance": NotifyAfricasTalking,
        },
    ),
    (
        "atalk://user@apikey/+{}?mode=PREM".format("4" * 11),
        {
            # PREM will match premium (not case sensitive)
            "instance": NotifyAfricasTalking,
        },
    ),
    (
        "atalk://{}?apikey=key&user=user&from=FROMUSER".format("1" * 11),
        {
            # use get args to acomplish the same thing
            "instance": NotifyAfricasTalking,
        },
    ),
    (
        "atalk://_?user=user&to={},{}&key={}&from={}".format(
            "1" * 11, "2" * 11, "b" * 10, "5" * 13
        ),
        {
            # use get args to acomplish the same thing
            "instance": NotifyAfricasTalking,
        },
    ),
    (
        "atalk://user@apikey/{}/".format("1" * 11),
        {
            "instance": NotifyAfricasTalking,
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "atalk://user@apikey/{}/".format("1" * 11),
        {
            "instance": NotifyAfricasTalking,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracfully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_atalk_urls():
    """NotifyTemplate() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.post")
def test_plugin_atalk_edge_cases(mock_post):
    """NotifyAfricasTalking() Edge Cases."""

    # Initialize some generic (but valid) tokens
    apikey = "my-api-key"
    appuser = "my-app-user"
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
    obj = Apprise.instantiate(
        "atalk://{}@{}/{}?batch=n".format(appuser, apikey, "/".join(targets))
    )

    assert (
        obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        is True
    )

    # We know there are 2 (valid) targets
    assert len(obj) == 2

    # Test our call count
    assert mock_post.call_count == 2

    # Test
    details = mock_post.call_args_list[0]
    headers = details[1]["headers"]
    assert headers["apiKey"] == apikey
    payload = details[1]["data"]
    assert payload["username"] == appuser
    assert payload["from"] == "AFRICASTKNG"
    assert payload["to"] == "+15551231234"
    assert payload["message"] == "title\r\nbody"

    details = mock_post.call_args_list[1]
    headers = details[1]["headers"]
    assert headers["apiKey"] == apikey
    payload = details[1]["data"]
    assert payload["username"] == appuser
    assert payload["from"] == "AFRICASTKNG"
    assert payload["to"] == "15555555555"
    assert payload["message"] == "title\r\nbody"

    # Verify our URL looks good
    assert obj.url().startswith(
        "atalk://{}@{}/{}".format(
            appuser, apikey, "/".join(["+15551231234", "15555555555"])
        )
    )

    assert "batch=no" in obj.url()

    # Reset our mock object
    mock_post.reset_mock()

    # With our batch in place, our calculations are different
    # Testing URL restructuring here as well where phone # is found
    # in host
    obj = Apprise.instantiate(
        "atalk://{}?user={}&apikey={}&batch=y&from=TEST".format(
            "/".join(targets), appuser, apikey
        )
    )

    # 2 phones were loaded but counted as 1 due to batch flag
    assert len(obj) == 1

    assert (
        obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        is True
    )

    # Test our call count (batched into 1)
    assert mock_post.call_count == 1

    details = mock_post.call_args_list[0]
    headers = details[1]["headers"]
    assert headers["apiKey"] == apikey
    payload = details[1]["data"]
    assert payload["username"] == appuser
    assert payload["from"] == "TEST"
    assert payload["to"] == "+15551231234,15555555555"
    assert payload["message"] == "title\r\nbody"
