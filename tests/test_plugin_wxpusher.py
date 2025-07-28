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

from json import dumps, loads

# Disable logging for a cleaner testing output
import logging
import os
from unittest import mock

from helpers import AppriseURLTester
import requests

from apprise import Apprise
from apprise.plugins.wxpusher import NotifyWxPusher

logging.disable(logging.CRITICAL)

WXPUSHER_GOOD_RESPONSE = dumps({"code": 1000})
WXPUSHER_BAD_RESPONSE = dumps({"code": 99})


# Attachment Directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), "var")

# Our Testing URLs
apprise_url_tests = (
    (
        "wxpusher://",
        {
            # No token specified
            "instance": TypeError,
        },
    ),
    (
        "wxpusher://:@/",
        {
            # invalid url
            "instance": TypeError,
        },
    ),
    (
        "wxpusher://invalid",
        {
            # invalid app token
            "instance": TypeError,
        },
    ),
    (
        "wxpusher://AT_appid/123/",
        {
            # invalid 'to' phone number
            "instance": NotifyWxPusher,
            # Notify will fail because it couldn't send to anyone
            "response": False,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "wxpusher://****/123/",
            # Our response expected server response
            "requests_response_text": WXPUSHER_GOOD_RESPONSE,
        },
    ),
    (
        "wxpusher://AT_appid/%20/%20/",
        {
            # invalid 'to' phone number
            "instance": NotifyWxPusher,
            # Notify will fail because it couldn't send to anyone
            "response": False,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "wxpusher://****/",
            # Our response expected server response
            "requests_response_text": WXPUSHER_GOOD_RESPONSE,
        },
    ),
    (
        "wxpusher://AT_appid/123/",
        {
            # one phone number will notify ourselves
            "instance": NotifyWxPusher,
            # Our response expected server response
            "requests_response_text": WXPUSHER_GOOD_RESPONSE,
        },
    ),
    (
        "wxpusher://123?token=AT_abc1234",
        {
            # pass our token in as an argument and our host actually becomes a
            # target
            "instance": NotifyWxPusher,
            # Our response expected server response
            "requests_response_text": WXPUSHER_GOOD_RESPONSE,
        },
    ),
    (
        "wxpusher://?token=AT_abc1234",
        {
            # slightly different then test above; a token is defined, but
            # there are no targets
            "instance": NotifyWxPusher,
            # Notify will fail because it couldn't send to anyone
            "response": False,
            # Our response expected server response
            "requests_response_text": WXPUSHER_GOOD_RESPONSE,
        },
    ),
    (
        "wxpusher://?token=AT_abc1234&to=UID_abc",
        {
            # all kwargs to load url with
            "instance": NotifyWxPusher,
            # Our response expected server response
            "requests_response_text": WXPUSHER_GOOD_RESPONSE,
        },
    ),
    (
        "wxpusher://AT_appid/UID_abcd/",
        {
            # a valid contact
            "instance": NotifyWxPusher,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "wxpusher://****/UID_abcd",
            # Our response expected server response
            "requests_response_text": WXPUSHER_GOOD_RESPONSE,
        },
    ),
    (
        "wxpusher://AT_appid/@/#/,/",
        {
            # Test case where we provide bad data
            "instance": NotifyWxPusher,
            # Our failed response
            "requests_response_text": WXPUSHER_GOOD_RESPONSE,
            # as a result, we expect a failed notification
            "response": False,
        },
    ),
    (
        "wxpusher://AT_appid/123/",
        {
            # Test case where we get a bad response
            "instance": NotifyWxPusher,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "wxpusher://****/123",
            # Our failed response
            "requests_response_text": WXPUSHER_BAD_RESPONSE,
            # as a result, we expect a failed notification
            "response": False,
        },
    ),
    (
        "wxpusher://AT_appid/UID_345/",
        {
            # Test case where we get a bad response
            "instance": NotifyWxPusher,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "wxpusher://****/UID_345",
            # Our failed response
            "requests_response_text": None,
            # as a result, we expect a failed notification
            "response": False,
        },
    ),
    (
        "wxpusher://AT_appid/UID_345/",
        {
            # Test case where we get a bad response
            "instance": NotifyWxPusher,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "wxpusher://****/UID_345",
            # Our failed response (bad json)
            "requests_response_text": "{",
            # as a result, we expect a failed notification
            "response": False,
        },
    ),
    (
        "wxpusher://AT_appid/?to={},{}".format("2" * 11, "3" * 11),
        {
            # use get args to acomplish the same thing
            "instance": NotifyWxPusher,
            # Our response expected server response
            "requests_response_text": WXPUSHER_GOOD_RESPONSE,
        },
    ),
    (
        "wxpusher://AT_appid/?to={},{},{}".format("2" * 11, "3" * 11, "5" * 3),
        {
            # 2 good targets and one invalid one
            "instance": NotifyWxPusher,
            # Our response expected server response
            "requests_response_text": WXPUSHER_GOOD_RESPONSE,
        },
    ),
    (
        "wxpusher://AT_appid/{}/{}/".format("2" * 11, "3" * 11),
        {
            # If we have from= specified, then all elements take on the
            # to= value
            "instance": NotifyWxPusher,
            # Our response expected server response
            "requests_response_text": WXPUSHER_GOOD_RESPONSE,
        },
    ),
    (
        "wxpusher://AT_appid/{}".format("3" * 11),
        {
            # use get args to acomplish the same thing (use source instead
            # of from)
            "instance": NotifyWxPusher,
            # Our response expected server response
            "requests_response_text": WXPUSHER_GOOD_RESPONSE,
        },
    ),
    (
        "wxpusher://AT_appid/{}".format("4" * 11),
        {
            "instance": NotifyWxPusher,
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
            # Our response expected server response
            "requests_response_text": WXPUSHER_GOOD_RESPONSE,
        },
    ),
    (
        "wxpusher://AT_appid/{}".format("4" * 11),
        {
            "instance": NotifyWxPusher,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracfully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_wxpusher_urls():
    """NotifyWxPusher() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.post")
def test_plugin_wxpusher_edge_cases(mock_post):
    """NotifyWxPusher() Edge Cases."""

    # Prepare our response
    response = requests.Request()
    response.status_code = requests.codes.ok
    response.content = WXPUSHER_GOOD_RESPONSE

    # Prepare Mock
    mock_post.return_value = response

    # Initialize some generic (but valid) tokens
    target = "UID_abcd"
    body = "test body"
    title = "My Title"

    aobj = Apprise()
    assert aobj.add(f"wxpusher://AT_appid/{target}")
    assert len(aobj) == 1
    assert aobj.notify(title=title, body=body)
    assert mock_post.call_count == 1

    details = mock_post.call_args_list[0]
    assert details[0][0] == "https://wxpusher.zjiecode.com/api/send/message"
    payload = loads(details[1]["data"])
    assert payload == {
        "appToken": "AT_appid",
        "content": "test body",
        "summary": "My Title",
        "contentType": 1,
        "topicIds": [],
        "uids": ["UID_abcd"],
        "url": None,
    }

    # Reset our mock object
    mock_post.reset_mock()


@mock.patch("requests.post")
def test_plugin_wxpusher_result_set(mock_post):
    """NotifyWxPusher() Result Sets."""

    # Prepare our response
    response = requests.Request()
    response.status_code = requests.codes.ok
    response.content = WXPUSHER_GOOD_RESPONSE

    # Prepare Mock
    mock_post.return_value = response

    body = "test body"
    title = "My Title"

    aobj = Apprise()
    aobj.add("wxpusher://AT_appid/123/abc/UID_456")
    # One bad entry and 2 good
    assert len(aobj[0]) == 1

    assert aobj.notify(title=title, body=body)

    # 2 posts made
    assert mock_post.call_count == 1

    details = mock_post.call_args_list[0]
    assert details[0][0] == "https://wxpusher.zjiecode.com/api/send/message"
    payload = loads(details[1]["data"])
    assert payload == {
        "appToken": "AT_appid",
        "content": "test body",
        "summary": "My Title",
        "contentType": 1,
        "topicIds": [123],
        "uids": ["UID_456"],
        "url": None,
    }

    # Validate our information is also placed back into the assembled URL
    assert "/123" in aobj[0].url()
    assert "/UID_456" in aobj[0].url()
    assert "/abc" in aobj[0].url()

    mock_post.reset_mock()

    aobj = Apprise()
    aobj.add("wxpusher://AT_appid//UID_123/UID_abc/123456789")
    assert len(aobj[0]) == 1

    assert aobj.notify(title=title, body=body)

    # If batch is off then there is a post per entry
    assert mock_post.call_count == 1

    details = mock_post.call_args_list[0]
    assert details[0][0] == "https://wxpusher.zjiecode.com/api/send/message"
    payload = loads(details[1]["data"])

    assert payload == {
        "appToken": "AT_appid",
        "content": "test body",
        "summary": "My Title",
        "contentType": 1,
        "topicIds": [123456789],
        "uids": ["UID_123", "UID_abc"],
        "url": None,
    }

    assert "/123456789" in aobj[0].url()
    assert "/UID_123" in aobj[0].url()
    assert "/UID_abc" in aobj[0].url()


@mock.patch("requests.post")
def test_notify_wxpusher_plugin_result_list(mock_post):
    """NotifyWxPusher() Result List Response."""

    okay_response = requests.Request()
    okay_response.status_code = requests.codes.ok
    # We want to test the case where the `result` set returned is a list

    # Invalid JSON response
    okay_response.content = "{"

    # Assign our mock object our return value
    mock_post.return_value = okay_response

    obj = Apprise.instantiate("wxpusher://AT_apptoken/UID_abcd/")
    assert isinstance(obj, NotifyWxPusher)

    # We should now fail
    assert obj.notify("test") is False
