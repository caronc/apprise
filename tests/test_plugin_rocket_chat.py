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

from apprise import NotifyType
from apprise.plugins.rocketchat import NotifyRocketChat

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    (
        "rocket://",
        {
            "instance": None,
        },
    ),
    (
        "rockets://",
        {
            "instance": None,
        },
    ),
    (
        "rocket://:@/",
        {
            "instance": None,
        },
    ),
    # No username or pass
    (
        "rocket://localhost",
        {
            "instance": TypeError,
        },
    ),
    # No room or channel
    (
        "rocket://user:pass@localhost",
        {
            "instance": TypeError,
        },
    ),
    # No valid rooms or channels
    (
        "rocket://user:pass@localhost/#/!/@",
        {
            "instance": TypeError,
        },
    ),
    # No user/pass combo
    (
        "rocket://user@localhost/room/",
        {
            "instance": TypeError,
        },
    ),
    # No user/pass combo
    (
        "rocket://localhost/room/",
        {
            "instance": TypeError,
        },
    ),
    # A room and port identifier
    (
        "rocket://user:pass@localhost:8080/room/",
        {
            "instance": NotifyRocketChat,
            # The response text is expected to be the following on a success
            "requests_response_text": {
                "status": "success",
                "data": {
                    "authToken": "abcd",
                    "userId": "user",
                },
            },
            "privacy_url": "rocket://user:****@localhost",
        },
    ),
    # A channel (using the to=)
    (
        "rockets://user:pass@localhost?to=#channel",
        {
            "instance": NotifyRocketChat,
            # The response text is expected to be the following on a success
            "requests_response_text": {
                "status": "success",
                "data": {
                    "authToken": "abcd",
                    "userId": "user",
                },
            },
            "privacy_url": "rockets://user:****@localhost",
        },
    ),
    # A channel
    (
        "rockets://user:pass@localhost/#channel",
        {
            "instance": NotifyRocketChat,
            # The response text is expected to be the following on a success
            "requests_response_text": {
                "status": "success",
                "data": {
                    "authToken": "abcd",
                    "userId": "user",
                },
            },
            "privacy_url": "rockets://user:****@localhost",
        },
    ),
    # A channel using token based
    (
        "rockets://user:token@localhost/#channel?mode=token",
        {
            "instance": NotifyRocketChat,
            "privacy_url": "rockets://user:****@localhost",
        },
    ),
    # Token is detected based o it's length
    (
        "rockets://user:{}@localhost/#channel".format("t" * 40),
        {
            "instance": NotifyRocketChat,
            "privacy_url": "rockets://user:****@localhost",
        },
    ),
    # Several channels
    (
        "rocket://user:pass@localhost/#channel1/#channel2/?avatar=Yes",
        {
            "instance": NotifyRocketChat,
            # The response text is expected to be the following on a success
            "requests_response_text": {
                "status": "success",
                "data": {
                    "authToken": "abcd",
                    "userId": "user",
                },
            },
            "privacy_url": "rocket://user:****@localhost",
        },
    ),
    # Several Rooms
    (
        "rocket://user:pass@localhost/room1/room2",
        {
            "instance": NotifyRocketChat,
            # The response text is expected to be the following on a success
            "requests_response_text": {
                "status": "success",
                "data": {
                    "authToken": "abcd",
                    "userId": "user",
                },
            },
            "privacy_url": "rocket://user:****@localhost",
        },
    ),
    # A room and channel
    (
        "rocket://user:pass@localhost/room/#channel?mode=basic&avatar=Yes",
        {
            "instance": NotifyRocketChat,
            # The response text is expected to be the following on a success
            "requests_response_text": {
                "status": "success",
                "data": {
                    "authToken": "abcd",
                    "userId": "user",
                },
            },
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "rocket://user:****@localhost",
        },
    ),
    # A user/pass where the pass matches a webtoken
    # to ensure we get the right mode, we enforce basic mode
    # so that web/token gets interpreted as a password
    (
        "rockets://user:pass%2Fwithslash@localhost/#channel/?mode=basic",
        {
            "instance": NotifyRocketChat,
            # The response text is expected to be the following on a success
            "requests_response_text": {
                "status": "success",
                "data": {
                    "authToken": "abcd",
                    "userId": "user",
                },
            },
            "privacy_url": "rockets://user:****@localhost",
        },
    ),
    # A room and channel
    (
        "rockets://user:pass@localhost/rooma/#channela",
        {
            # The response text is expected to be the following on a success
            "requests_response_code": requests.codes.ok,
            "requests_response_text": {
                # return something other then a success message type
                "status": "failure",
            },
            # Exception is thrown in this case
            "instance": NotifyRocketChat,
            # Notifications will fail in this event
            "response": False,
        },
    ),
    # A web token
    (
        "rockets://web/token@localhost/@user/#channel/roomid",
        {
            "instance": NotifyRocketChat,
            "privacy_url": "rockets://****@localhost/#channel/roomid",
        },
    ),
    (
        "rockets://user:web/token@localhost/@user/?mode=webhook",
        {
            "instance": NotifyRocketChat,
            "privacy_url": "rockets://user:****@localhost",
        },
    ),
    (
        "rockets://user:web/token@localhost?to=@user2,#channel2",
        {
            "instance": NotifyRocketChat,
        },
    ),
    (
        "rockets://web/token@localhost/?avatar=No",
        {
            # a simple webhook token with default values
            "instance": NotifyRocketChat,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "rockets://****@localhost/",
        },
    ),
    (
        "rockets://localhost/@user/?mode=webhook&webhook=web/token",
        {
            "instance": NotifyRocketChat,
            "privacy_url": "rockets://****@localhost/@user",
        },
    ),
    (
        "rockets://user:web/token@localhost/@user/?mode=invalid",
        {
            # invalid mode
            "instance": TypeError,
        },
    ),
    (
        "rocket://user:pass@localhost:8081/room1/room2",
        {
            "instance": NotifyRocketChat,
            # force a failure using basic mode
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "rockets://user:web/token@localhost?to=@user3,#channel3",
        {
            "instance": NotifyRocketChat,
            # force a failure using webhook mode
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "rocket://user:pass@localhost:8082/#channel",
        {
            "instance": NotifyRocketChat,
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "rocket://user:pass@localhost:8083/#chan1/#chan2/room",
        {
            "instance": NotifyRocketChat,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracfully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_rocket_chat_urls():
    """NotifyRocketChat() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.get")
@mock.patch("requests.post")
def test_plugin_rocket_chat_edge_cases(mock_post, mock_get):
    """NotifyRocketChat() Edge Cases."""

    # Chat ID
    recipients = "AbcD1245, @l2g, @lead2gold, #channel, #channel2"

    # Authentication
    user = "myuser"
    password = "mypass"

    # Prepare Mock
    mock_get.return_value = requests.Request()
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok
    mock_get.return_value.status_code = requests.codes.ok
    mock_post.return_value.content = ""
    mock_get.return_value.content = ""

    obj = NotifyRocketChat(user=user, password=password, targets=recipients)
    assert isinstance(obj, NotifyRocketChat) is True
    assert len(obj.channels) == 2
    assert len(obj.users) == 2
    assert len(obj.rooms) == 1

    # No Webhook specified
    with pytest.raises(TypeError):
        obj = NotifyRocketChat(webhook=None, mode="webhook")

    #
    # Logout
    #
    assert obj.logout() is True

    # Invalid JSON during Login
    mock_post.return_value.content = "{"
    mock_get.return_value.content = "}"
    assert obj.login() is False

    # Prepare Mock to fail
    mock_post.return_value.content = ""
    mock_get.return_value.content = ""
    mock_post.return_value.status_code = requests.codes.internal_server_error
    mock_get.return_value.status_code = requests.codes.internal_server_error

    #
    # Send Notification
    #
    assert (
        obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        is False
    )
    assert obj._send(payload="test", notify_type=NotifyType.INFO) is False

    #
    # Logout
    #
    assert obj.logout() is False

    # KeyError handling
    mock_post.return_value.status_code = 999
    mock_get.return_value.status_code = 999

    #
    # Send Notification
    #
    assert (
        obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        is False
    )
    assert obj._send(payload="test", notify_type=NotifyType.INFO) is False

    #
    # Logout
    #
    assert obj.logout() is False

    # Generate exceptions
    mock_get.side_effect = requests.ConnectionError(
        0, "requests.ConnectionError() not handled"
    )
    mock_post.side_effect = mock_get.side_effect

    #
    # Send Notification
    #
    assert obj._send(payload="test", notify_type=NotifyType.INFO) is False

    # Attempt the check again but fake a successful login
    obj.login = mock.Mock()
    obj.login.return_value = True
    assert (
        obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        is False
    )
    #
    # Logout
    #
    assert obj.logout() is False
