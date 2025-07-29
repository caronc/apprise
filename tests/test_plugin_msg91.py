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
import pytest
import requests

from apprise import Apprise
from apprise.plugins.msg91 import NotifyMSG91

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    (
        "msg91://",
        {
            # No hostname/authkey specified
            "instance": TypeError,
        },
    ),
    (
        "msg91://-",
        {
            # Invalid AuthKey
            "instance": TypeError,
        },
    ),
    (
        "msg91://{}".format("a" * 23),
        {
            # valid AuthKey but no Template ID
            "instance": TypeError,
        },
    ),
    (
        "msg91://{}@{}".format("t" * 20, "a" * 23),
        {
            # Valid entry but no targets
            "instance": NotifyMSG91,
            # Since there are no targets specified we expect a False return on
            # send()
            "notify_response": False,
        },
    ),
    (
        "msg91://{}@{}/abcd".format("t" * 20, "a" * 23),
        {
            # No number to notify
            "instance": NotifyMSG91,
            # Since there are no targets specified we expect a False return on
            # send()
            "notify_response": False,
        },
    ),
    (
        "msg91://{}@{}/15551232000".format("t" * 20, "a" * 23),
        {
            # a valid message
            "instance": NotifyMSG91,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "msg91://t...t@a...a/15551232000",
        },
    ),
    (
        "msg91://{}@{}/?to=15551232000&short_url=no".format(
            "t" * 20, "a" * 23
        ),
        {
            # a valid message
            "instance": NotifyMSG91,
        },
    ),
    (
        "msg91://{}@{}/15551232000?short_url=yes".format("t" * 20, "a" * 23),
        {
            # testing short_url
            "instance": NotifyMSG91,
        },
    ),
    (
        "msg91://{}@{}/15551232000".format("t" * 20, "a" * 23),
        {
            # use get args to acomplish the same thing
            "instance": NotifyMSG91,
        },
    ),
    (
        "msg91://{}@{}/15551232000".format("t" * 20, "a" * 23),
        {
            "instance": NotifyMSG91,
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "msg91://{}@{}/15551232000".format("t" * 20, "a" * 23),
        {
            "instance": NotifyMSG91,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracfully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_msg91_urls():
    """NotifyMSG91() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.post")
def test_plugin_msg91_edge_cases(mock_post):
    """NotifyMSG91() Edge Cases."""

    # Prepare our response
    response = requests.Request()
    response.status_code = requests.codes.ok

    # Prepare Mock
    mock_post.return_value = response

    # Initialize some generic (but valid) tokens
    target = "+1 (555) 123-3456"

    # No authkey specified
    with pytest.raises(TypeError):
        NotifyMSG91(template="1234", authkey=None, targets=target)
    with pytest.raises(TypeError):
        NotifyMSG91(template="1234", authkey="    ", targets=target)
    with pytest.raises(TypeError):
        NotifyMSG91(template="     ", authkey="a" * 23, targets=target)
    with pytest.raises(TypeError):
        NotifyMSG91(template=None, authkey="a" * 23, targets=target)


@mock.patch("requests.post")
def test_plugin_msg91_keywords(mock_post):
    """NotifyMSG91() Templating."""

    response = mock.Mock()
    response.content = ""
    response.status_code = requests.codes.ok

    # Prepare Mock
    mock_post.return_value = response

    target = "+1 (555) 123-3456"
    template = "12345"
    authkey = "{}".format("b" * 32)

    message_contents = "test"

    # Variation of initialization without API key
    obj = Apprise.instantiate(
        f"msg91://{template}@{authkey}/{target}?:key=value&:mobiles=ignored"
    )
    assert isinstance(obj, NotifyMSG91)
    assert isinstance(obj.url(), str)

    # Send Notification
    assert obj.send(body=message_contents) is True

    # Validate expected call parameters
    assert mock_post.call_count == 1
    first_call = mock_post.call_args_list[0]

    # URL and message parameters are the same for both calls
    assert first_call[0][0] == "https://control.msg91.com/api/v5/flow/"
    response = loads(first_call[1]["data"])
    assert response["template_id"] == template
    assert response["short_url"] == 0
    assert len(response["recipients"]) == 1
    # mobiles is not over-ridden as it is a special reserved token
    assert response["recipients"][0]["mobiles"] == "15551233456"

    # Our base tokens
    assert response["recipients"][0]["body"] == message_contents
    assert response["recipients"][0]["type"] == "info"
    assert response["recipients"][0]["key"] == "value"

    mock_post.reset_mock()

    # Play with mapping
    obj = Apprise.instantiate(
        f"msg91://{template}@{authkey}/{target}?:body&:type=cat"
    )
    assert isinstance(obj, NotifyMSG91)
    assert isinstance(obj.url(), str)

    # Send Notification
    assert obj.send(body=message_contents) is True

    # Validate expected call parameters
    assert mock_post.call_count == 1
    first_call = mock_post.call_args_list[0]

    # URL and message parameters are the same for both calls
    assert first_call[0][0] == "https://control.msg91.com/api/v5/flow/"
    response = loads(first_call[1]["data"])
    assert response["template_id"] == template
    assert response["short_url"] == 0
    assert len(response["recipients"]) == 1
    assert response["recipients"][0]["mobiles"] == "15551233456"
    assert "body" not in response["recipients"][0]
    assert "type" not in response["recipients"][0]
    assert response["recipients"][0]["cat"] == "info"
