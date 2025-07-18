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

from inspect import cleandoc
from json import loads

# Disable logging for a cleaner testing output
import logging
from unittest import mock

from helpers import AppriseURLTester
import requests

from apprise.plugins.notifiarr import NotifyNotifiarr

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    (
        "notifiarr://:@/",
        {
            "instance": TypeError,
        },
    ),
    (
        "notifiarr://",
        {
            "instance": TypeError,
        },
    ),
    (
        "notifiarr://apikey",
        {
            "instance": NotifyNotifiarr,
            # Response will fail due to no targets defined
            "notify_response": False,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "notifiarr://a...y",
        },
    ),
    (
        "notifiarr://apikey/1234/?event=invalid",
        {
            "instance": TypeError,
        },
    ),
    (
        "notifiarr://apikey/%%invalid%%",
        {
            "instance": NotifyNotifiarr,
            # Response will fail due to no targets defined
            "notify_response": False,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "notifiarr://a...y",
        },
    ),
    (
        "notifiarr://apikey/#123",
        {
            "instance": NotifyNotifiarr,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "notifiarr://a...y/#123",
        },
    ),
    (
        "notifiarr://apikey/123?image=No",
        {
            "instance": NotifyNotifiarr,
        },
    ),
    (
        "notifiarr://apikey/123?image=yes",
        {
            "instance": NotifyNotifiarr,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "notifiarr://a...y/#123",
        },
    ),
    (
        "notifiarr://apikey/?to=123,432",
        {
            "instance": NotifyNotifiarr,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "notifiarr://a...y/#123/#432",
        },
    ),
    (
        "notifiarr://apikey/?to=123,432&event=1234",
        {
            # Test event
            "instance": NotifyNotifiarr,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "notifiarr://a...y/#123/#432",
        },
    ),
    (
        "notifiarr://123/?apikey=myapikey",
        {
            "instance": NotifyNotifiarr,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "notifiarr://m...y/#123",
        },
    ),
    (
        "notifiarr://123/?key=myapikey",
        {
            # Support key=
            "instance": NotifyNotifiarr,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "notifiarr://m...y/#123",
        },
    ),
    (
        "notifiarr://123/?apikey=myapikey&image=yes",
        {
            "instance": NotifyNotifiarr,
        },
    ),
    (
        "notifiarr://123/?apikey=myapikey&image=no",
        {
            "instance": NotifyNotifiarr,
        },
    ),
    (
        "notifiarr://123/?apikey=myapikey&source=My%20System",
        {
            "instance": NotifyNotifiarr,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "notifiarr://m...y/#123",
        },
    ),
    (
        "notifiarr://123/?apikey=myapikey&from=My%20System",
        {
            "instance": NotifyNotifiarr,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "notifiarr://m...y/#123",
        },
    ),
    (
        "notifiarr://?apikey=myapikey",
        {
            # No Channel or host
            "instance": NotifyNotifiarr,
            # Response will fail due to no targets defined
            "notify_response": False,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "notifiarr://m...y/",
        },
    ),
    (
        "notifiarr://invalid?apikey=myapikey",
        {
            # No Channel or host
            "instance": NotifyNotifiarr,
            # invalid channel
            "notify_response": False,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "notifiarr://m...y/",
        },
    ),
    (
        "notifiarr://123/325/?apikey=myapikey",
        {
            "instance": NotifyNotifiarr,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "notifiarr://m...y/#123/#325",
        },
    ),
    (
        "notifiarr://apikey/123/",
        {
            "instance": NotifyNotifiarr,
        },
    ),
    (
        "notifiarr://apikey/123",
        {
            "instance": NotifyNotifiarr,
            # force a failure
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "notifiarr://apikey/123",
        {
            "instance": NotifyNotifiarr,
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "notifiarr://apikey/123",
        {
            "instance": NotifyNotifiarr,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracfully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_notifiarr_urls():
    """NotifyNotifiarr() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.post")
def test_plugin_notifiarr_notifications(mock_post):
    """NotifyNotifiarr() Notifications/Ping Support."""

    # Test our header parsing when not lead with a header
    body = cleandoc("""
    # Heading
    @everyone and @admin, wake and meet our new user <@123> and <@987>;
    Attention Roles: <@&456> and <@&765>
     """)

    # Prepare a good response
    response = mock.Mock()
    response.status_code = requests.codes.ok

    # Prepare Mock return object
    mock_post.return_value = response

    results = NotifyNotifiarr.parse_url("notifiarr://apikey/12345")

    instance = NotifyNotifiarr(**results)
    assert isinstance(instance, NotifyNotifiarr)

    response = instance.send(body=body)
    assert response is True
    assert mock_post.call_count == 1

    details = mock_post.call_args_list[0]
    assert details[0][0] == "https://notifiarr.com/api/v1/notification/apprise"

    payload = loads(details[1]["data"])

    # First role and first user stored
    assert payload == {
        "source": "Apprise",
        "type": "info",
        "notification": {"update": False, "name": "Apprise", "event": ""},
        "discord": {
            "color": "#3AA3E3",
            "ping": {
                # Only supports 1 entry each; so first one is parsed
                "pingUser": "123",
                "pingRole": "456",
            },
            "text": {
                "title": "",
                "content": "👉 @everyone @admin <@123> <@987> <@&456> <@&765>",
                "description": (
                    "# Heading\n@everyone and @admin, wake and meet our new "
                    "user <@123> and <@987>;\nAttention Roles: <@&456> and "
                    "<@&765>\n "
                ),
                "footer": "Apprise Notifications",
            },
            "ids": {"channel": 12345},
        },
    }
