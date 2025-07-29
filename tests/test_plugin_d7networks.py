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
from apprise.plugins.d7networks import NotifyD7Networks

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    (
        "d7sms://",
        {
            # We failed to identify any valid authentication
            "instance": TypeError,
        },
    ),
    (
        "d7sms://:@/",
        {
            # We failed to identify any valid authentication
            "instance": TypeError,
        },
    ),
    (
        "d7sms://token@{}/{}/{}".format("1" * 9, "2" * 15, "a" * 13),
        {
            # No valid targets to notify
            "instance": NotifyD7Networks,
            # Since there are no targets specified we expect a False return on
            # send()
            "notify_response": False,
        },
    ),
    (
        "d7sms://token1@{}?batch=yes".format("3" * 14),
        {
            # valid number
            "instance": NotifyD7Networks,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "d7sms://t...1@",
        },
    ),
    (
        "d7sms://token:colon2@{}?batch=yes".format("3" * 14),
        {
            # valid number - token containing a colon
            "instance": NotifyD7Networks,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "d7sms://t...2@",
        },
    ),
    (
        "d7sms://:token3@{}?batch=yes".format("3" * 14),
        {
            # valid number - token starting wit a colon
            "instance": NotifyD7Networks,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "d7sms://:...3@",
        },
    ),
    (
        "d7sms://{}?token=token6".format("3" * 14),
        {
            # valid number - token starting wit a colon
            "instance": NotifyD7Networks,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "d7sms://t...6@",
        },
    ),
    (
        "d7sms://token4@{}?unicode=no".format("3" * 14),
        {
            # valid number - test unicode
            "instance": NotifyD7Networks,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "d7sms://t...4@",
        },
    ),
    (
        "d7sms://token8@{}/{}/?unicode=yes".format("3" * 14, "4" * 14),
        {
            # valid number - test unicode
            "instance": NotifyD7Networks,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "d7sms://t...8@",
        },
    ),
    (
        "d7sms://token@{}?batch=yes&to={}".format("3" * 14, "6" * 14),
        {
            # valid number
            "instance": NotifyD7Networks,
        },
    ),
    (
        "d7sms://token@{}?batch=yes&from=apprise".format("3" * 14),
        {
            # valid number, utilizing the optional from= variable
            "instance": NotifyD7Networks,
        },
    ),
    (
        "d7sms://token@{}?batch=yes&source=apprise".format("3" * 14),
        {
            # valid number, utilizing the optional source= variable (same as
            # from)
            "instance": NotifyD7Networks,
        },
    ),
    (
        "d7sms://token@{}?batch=no".format("3" * 14),
        {
            # valid number - no batch
            "instance": NotifyD7Networks,
        },
    ),
    (
        "d7sms://token@{}".format("3" * 14),
        {
            "instance": NotifyD7Networks,
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "d7sms://token@{}".format("3" * 14),
        {
            "instance": NotifyD7Networks,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracfully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_d7networks_urls():
    """NotifyD7Networks() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.post")
def test_plugin_d7networks_edge_cases(mock_post):
    """NotifyD7Networks() Edge Cases tests."""

    # Prepare Mock
    request = mock.Mock()
    request.content = "{}"
    request.status_code = requests.codes.ok
    mock_post.return_value = request

    # Initializations
    aobj = Apprise()
    assert aobj.add("d7sms://Token@15551231234/15551231236")

    body = "test message"

    # Send our notification
    assert aobj.notify(body=body, title="title", notify_type=NotifyType.INFO)

    # Not set to batch, so we send 2 different messages
    assert mock_post.call_count == 2
    assert (
        mock_post.call_args_list[0][0][0]
        == "https://api.d7networks.com/messages/v1/send"
    )
    assert (
        mock_post.call_args_list[1][0][0]
        == "https://api.d7networks.com/messages/v1/send"
    )

    # our first post
    data = loads(mock_post.call_args_list[0][1]["data"])
    assert len(data["messages"]) == 1
    message = data["messages"][0]
    assert len(message["recipients"]) == 1
    assert message["content"] == "title\r\ntest message"
    assert message["data_coding"] == "auto"

    # our second post
    data = loads(mock_post.call_args_list[1][1]["data"])
    assert len(data["messages"]) == 1
    message = data["messages"][0]
    assert len(message["recipients"]) == 1
    assert message["content"] == "title\r\ntest message"
    assert message["data_coding"] == "auto"

    #
    # Do a batch test now
    #

    mock_post.reset_mock()

    # Initializations
    aobj = Apprise()
    assert aobj.add("d7sms://Token@15551231234/15551231236?batch=yes")

    body = "test message"

    # Send our notification
    assert aobj.notify(body=body, title="title", notify_type=NotifyType.INFO)

    # All notifications go through in a batch
    assert mock_post.call_count == 1
    assert (
        mock_post.call_args_list[0][0][0]
        == "https://api.d7networks.com/messages/v1/send"
    )

    data = loads(mock_post.call_args_list[0][1]["data"])
    assert len(data["messages"]) == 1
    message = data["messages"][0]
    # All of our phone numbers were added here
    assert len(message["recipients"]) == 2
    assert "15551231234" in message["recipients"]
    assert "15551231236" in message["recipients"]
    assert message["content"] == "title\r\ntest message"
    assert message["data_coding"] == "auto"
