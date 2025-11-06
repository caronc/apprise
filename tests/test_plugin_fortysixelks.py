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
from apprise.plugins.fortysixelks import Notify46Elks

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    ("46elks://", False),
    ("46elks://user@/", False),
    ("46elks://:pass@/", False),

    ("46elks://user:pass@/", {
        "instance": Notify46Elks,
        # no target was specified
        "notify_response": False,
    }),

    ("46elks://user:pass@+15551234556", {
        "instance": Notify46Elks,
    }),

    ("46elks://user:pass@+15551234567/+46701234534?from=Acme", {
        "instance": Notify46Elks,
    }),

    # Support elks:// too!
    ("elks://user:pass@+15551234123/", {
        "instance": Notify46Elks,
    }),

    # Privacy mode redacts password
    ("46elks://user:pass@+15551234512", {
        "privacy_url": "46elks://user:****@+15551234512",
        "instance": Notify46Elks,
    }),

    # invalid phone no
    ("46elks://user:pass@Acme/234512", {
        "instance": Notify46Elks,
        "notify_response": False,
    }),
    # Native URL reversal
    (("https://user1:pass@"
      "api.46elks.com/a1/sms?to=+15551234511&from=Acme"), {
        "instance": Notify46Elks,
        "privacy_url": "46elks://user1:****@Acme/+15551234511",
    }),
    ("46elks://user:pass@+15551234567",
        {
            "instance": Notify46Elks,
            # throw a bizarre code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        }),
    ("46elks://user:pass@+15551234578",
        {
            "instance": Notify46Elks,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracefully handle them
            "test_requests_exceptions": True,
        }),
)


def test_plugin_46elks_urls():
    """NotifyTemplate() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.post")
def test_plugin_46elks_edge_cases(mock_post):
    """Notify46Elks() Edge Cases."""

    user = "user1"
    password = "pass123"
    phone = "+15551234591"

    response = requests.Request()
    response.status_code = requests.codes.ok

    # Prepare Mock
    mock_post.return_value = response

    obj = Apprise.instantiate(f"46elks://{user}:{password}@{phone}")
    assert (
        obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        is True
    )

    # We know there is 1 (valid) targets
    assert len(obj) == 1

    # Test our call count
    assert mock_post.call_count == 1

    # Test
    details = mock_post.call_args_list[0]
    headers = details[1]["headers"]
    assert headers["User-Agent"] == "Apprise"
    payload = details[1]["data"]
    assert payload["to"] == phone
    assert payload["from"] == phone
    assert payload["message"] == "title\r\nbody"

    # Verify our URL looks good
    assert obj.url().startswith(f"46elks://{user}:{password}@{phone}")
