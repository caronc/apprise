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

from apprise import Apprise
from apprise.plugins.home_assistant import NotifyHomeAssistant

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    (
        "hassio://:@/",
        {
            "instance": TypeError,
        },
    ),
    (
        "hassio://",
        {
            "instance": TypeError,
        },
    ),
    (
        "hassios://",
        {
            "instance": TypeError,
        },
    ),
    # No Long Lived Access Token specified
    (
        "hassio://user@localhost",
        {
            "instance": TypeError,
        },
    ),
    (
        "hassio://localhost/long-lived-access-token",
        {
            "instance": NotifyHomeAssistant,
        },
    ),
    (
        "hassio://user:pass@localhost/long-lived-access-token/",
        {
            "instance": NotifyHomeAssistant,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "hassio://user:****@localhost/l...n",
        },
    ),
    (
        "hassio://localhost:80/long-lived-access-token",
        {
            "instance": NotifyHomeAssistant,
        },
    ),
    (
        "hassio://user@localhost:8123/llat",
        {
            "instance": NotifyHomeAssistant,
            "privacy_url": "hassio://user@localhost/l...t",
        },
    ),
    (
        "hassios://localhost/llat?nid=!%",
        {
            # Invalid notification_id
            "instance": TypeError,
        },
    ),
    (
        "hassios://localhost/llat?nid=abcd",
        {
            # Valid notification_id
            "instance": NotifyHomeAssistant,
        },
    ),
    (
        "hassios://user:pass@localhost/llat",
        {
            "instance": NotifyHomeAssistant,
            "privacy_url": "hassios://user:****@localhost/l...t",
        },
    ),
    (
        "hassios://localhost:8443/path/llat/",
        {
            "instance": NotifyHomeAssistant,
            "privacy_url": "hassios://localhost:8443/path/l...t",
        },
    ),
    (
        "hassio://localhost:8123/a/path?accesstoken=llat",
        {
            "instance": NotifyHomeAssistant,
            # Default port; so it's stripped off
            # accesstoken was specified as kwarg
            "privacy_url": "hassio://localhost/a/path/l...t",
        },
    ),
    (
        "hassios://user:password@localhost:80/llat/",
        {
            "instance": NotifyHomeAssistant,
            "privacy_url": "hassios://user:****@localhost:80",
        },
    ),
    (
        "hassio://user:pass@localhost:8123/llat",
        {
            "instance": NotifyHomeAssistant,
            # force a failure
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "hassio://user:pass@localhost/llat",
        {
            "instance": NotifyHomeAssistant,
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "hassio://user:pass@localhost/llat",
        {
            "instance": NotifyHomeAssistant,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracfully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_homeassistant_urls():
    """NotifyHomeAssistant() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.post")
def test_plugin_homeassistant_general(mock_post):
    """NotifyHomeAssistant() General Checks."""

    response = mock.Mock()
    response.content = ""
    response.status_code = requests.codes.ok

    # Prepare Mock
    mock_post.return_value = response

    # Variation Initializations
    obj = Apprise.instantiate("hassio://localhost/accesstoken")
    assert isinstance(obj, NotifyHomeAssistant) is True
    assert isinstance(obj.url(), str) is True

    # Send Notification
    assert obj.send(body="test") is True

    assert mock_post.call_count == 1
    assert (
        mock_post.call_args_list[0][0][0]
        == "http://localhost:8123/api/services/persistent_notification/create"
    )
