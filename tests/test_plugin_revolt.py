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

from datetime import datetime, timedelta
from json import dumps

# Disable logging for a cleaner testing output
import logging
import os
from random import choice
from string import ascii_uppercase as str_alpha, digits as str_num
from unittest import mock

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise, NotifyFormat, NotifyType
from apprise.common import OverflowMode
from apprise.plugins.revolt import NotifyRevolt

logging.disable(logging.CRITICAL)

# Attachment Directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), "var")

# Prepare a Valid Response
REVOLT_GOOD_RESPONSE = dumps({
    "_id": "AAAPWPMMQA2JJB59BR2EASWWWW",
    "nonce": "01HPWPPMDJABC2FTDG54CBKKKS",
    "channel": "00000000000000000000000000",
    "author": "011244Q9S8NCS67KMM9543W7JJ",
    "content": "test",
})

# Our Testing URLs
apprise_url_tests = (
    (
        "revolt://",
        {
            "instance": TypeError,
        },
    ),
    # An invalid url
    (
        "revolt://:@/",
        {
            "instance": TypeError,
        },
    ),
    # No channel_id specified
    (
        "revolt://%s" % ("i" * 24),
        {
            "instance": NotifyRevolt,
            # Notify will fail
            "response": False,
            # Our response expected server response
            "requests_response_text": REVOLT_GOOD_RESPONSE,
        },
    ),
    # channel_id specified on url, but no Bot Token
    (
        "revolt://?channel=%s" % ("i" * 24),
        {
            "instance": TypeError,
        },
    ),
    # channel_id specified on url
    (
        "revolt://{}/?channel={}".format("i" * 24, "i" * 24),
        {
            "instance": NotifyRevolt,
            # Our response expected server response
            "requests_response_text": REVOLT_GOOD_RESPONSE,
        },
    ),
    (
        "revolt://{}/?to={}".format("i" * 24, "i" * 24),
        {
            "instance": NotifyRevolt,
            # Our response expected server response
            "requests_response_text": REVOLT_GOOD_RESPONSE,
        },
    ),
    (
        "revolt://{}/?to={}".format("i" * 24, "i" * 24),
        {
            "instance": NotifyRevolt,
            # an invalid JSON Response
            "requests_response_text": "{",
        },
    ),
    # channel_id specified on url
    (
        "revolt://{}/?channel={},%20".format("i" * 24, "i" * 24),
        {
            "instance": NotifyRevolt,
            # Our response expected server response
            "requests_response_text": REVOLT_GOOD_RESPONSE,
        },
    ),
    # Provide both a bot token and a channel id
    (
        "revolt://{}/{}".format("i" * 24, "t" * 64),
        {
            "instance": NotifyRevolt,
            "requests_response_code": requests.codes.ok,
            # Our response expected server response
            "requests_response_text": REVOLT_GOOD_RESPONSE,
        },
    ),
    (
        "revolt://_?bot_token={}&channel={}".format("i" * 24, "t" * 64),
        {
            "instance": NotifyRevolt,
            "requests_response_code": requests.codes.ok,
            # Our response expected server response
            "requests_response_text": REVOLT_GOOD_RESPONSE,
        },
    ),
    # different format support
    (
        "revolt://{}/{}?format=markdown".format("i" * 24, "t" * 64),
        {
            "instance": NotifyRevolt,
            "requests_response_code": requests.codes.ok,
            # Our response expected server response
            "requests_response_text": REVOLT_GOOD_RESPONSE,
        },
    ),
    (
        "revolt://{}/{}?format=text".format("i" * 24, "t" * 64),
        {
            "instance": NotifyRevolt,
            "requests_response_code": requests.codes.ok,
            # Our response expected server response
            "requests_response_text": REVOLT_GOOD_RESPONSE,
        },
    ),
    # Test with url
    (
        "revolt://{}/{}?url=http://localhost".format("i" * 24, "t" * 64),
        {
            "instance": NotifyRevolt,
            "requests_response_code": requests.codes.ok,
            # Our response expected server response
            "requests_response_text": REVOLT_GOOD_RESPONSE,
        },
    ),
    # URL implies markdown unless explicitly set otherwise
    (
        "revolt://{}/{}?format=text&url=http://localhost".format(
            "i" * 24, "t" * 64
        ),
        {
            "instance": NotifyRevolt,
            "requests_response_code": requests.codes.ok,
            # Our response expected server response
            "requests_response_text": REVOLT_GOOD_RESPONSE,
        },
    ),
    # Test with Icon URL
    (
        "revolt://{}/{}?icon_url=http://localhost/test.jpg".format(
            "i" * 24, "t" * 64
        ),
        {
            "instance": NotifyRevolt,
            "requests_response_code": requests.codes.ok,
            # Our response expected server response
            "requests_response_text": REVOLT_GOOD_RESPONSE,
        },
    ),
    # Icon URL implies markdown unless explicitly set otherwise
    (
        "revolt://{}/{}?format=text&icon_url=http://localhost/test.jpg".format(
            "i" * 24, "t" * 64
        ),
        {
            "instance": NotifyRevolt,
            "requests_response_code": requests.codes.ok,
            # Our response expected server response
            "requests_response_text": REVOLT_GOOD_RESPONSE,
        },
    ),
    # Test without any image set
    (
        "revolt://{}/{}".format("i" * 24, "t" * 64),
        {
            "instance": NotifyRevolt,
            "requests_response_code": requests.codes.ok,
            # don't include an image by default
            "include_image": False,
            # Our response expected server response
            "requests_response_text": REVOLT_GOOD_RESPONSE,
        },
    ),
    (
        "revolt://{}/{}/".format("a" * 24, "b" * 64),
        {
            "instance": NotifyRevolt,
            # force a failure
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
            # Our response expected server response
            "requests_response_text": REVOLT_GOOD_RESPONSE,
        },
    ),
    (
        "revolt://{}/{}/".format("a" * 24, "b" * 64),
        {
            "instance": NotifyRevolt,
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
            # Our response expected server response
            "requests_response_text": REVOLT_GOOD_RESPONSE,
        },
    ),
    (
        "revolt://{}/{}/".format("a" * 24, "b" * 64),
        {
            "instance": NotifyRevolt,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracfully handle them
            "test_requests_exceptions": True,
            # Our response expected server response
            "requests_response_text": REVOLT_GOOD_RESPONSE,
        },
    ),
)


def test_plugin_revolt_urls():
    """NotifyRevolt() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.post")
def test_plugin_revolt_notifications(mock_post):
    """NotifyRevolt() Notifications."""

    # Initialize some generic (but valid) tokens
    bot_token = "A" * 24
    channel_id = "B" * 64

    # Prepare Mock
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok
    mock_post.return_value.content = REVOLT_GOOD_RESPONSE

    # Test our header parsing when not lead with a header
    body = """
    # Heading
    @everyone and @admin, wake and meet our new user <@123>; <@&456>"
    """

    results = NotifyRevolt.parse_url(
        f"revolt://{bot_token}/{channel_id}/?format=markdown"
    )

    assert isinstance(results, dict)
    assert results["user"] is None
    assert results["bot_token"] == bot_token
    assert results["targets"] == [
        channel_id,
    ]
    assert results["password"] is None
    assert results["port"] is None
    assert results["host"] == bot_token
    assert results["fullpath"] == f"/{channel_id}/"
    assert results["path"] == f"/{channel_id}/"
    assert results["query"] is None
    assert results["schema"] == "revolt"
    assert results["url"] == f"revolt://{bot_token}/{channel_id}/"

    instance = NotifyRevolt(**results)
    assert isinstance(instance, NotifyRevolt)

    response = instance.send(body=body)
    assert response is True
    assert mock_post.call_count == 1

    # Reset our object
    mock_post.reset_mock()

    results = NotifyRevolt.parse_url(
        f"revolt://{bot_token}/{channel_id}/?format=text"
    )

    assert isinstance(results, dict)
    assert results["user"] is None
    assert results["bot_token"] == bot_token
    assert results["targets"] == [
        channel_id,
    ]
    assert results["password"] is None
    assert results["port"] is None
    assert results["host"] == bot_token
    assert results["fullpath"] == f"/{channel_id}/"
    assert results["path"] == f"/{channel_id}/"
    assert results["query"] is None
    assert results["schema"] == "revolt"
    assert results["url"] == f"revolt://{bot_token}/{channel_id}/"

    instance = NotifyRevolt(**results)
    assert isinstance(instance, NotifyRevolt)

    response = instance.send(body=body)
    assert response is True
    assert mock_post.call_count == 1


@mock.patch("requests.post")
@mock.patch("time.sleep")
def test_plugin_revolt_general(mock_sleep, mock_post):
    """NotifyRevolt() General Checks."""

    # Prevent throttling
    mock_sleep.return_value = True

    # Turn off clock skew for local testing
    NotifyRevolt.clock_skew = timedelta(seconds=0)

    # Initialize some generic (but valid) tokens
    bot_token = "A" * 24
    channel_id = ",".join(["B" * 32, "C" * 32]) + ", ,%%"

    # Prepare Mock
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok
    mock_post.return_value.content = REVOLT_GOOD_RESPONSE
    mock_post.return_value.headers = {
        "X-RateLimit-Remaining": 0,
        "X-RateLimit-Reset-After": 1,
    }

    # Invalid bot_token
    with pytest.raises(TypeError):
        NotifyRevolt(bot_token=None, targets=channel_id)
    # Invalid bot_token (whitespace)
    with pytest.raises(TypeError):
        NotifyRevolt(bot_token="  ", targets=channel_id)

    obj = NotifyRevolt(bot_token=bot_token, targets=channel_id)
    assert obj.ratelimit_remaining == 1

    # Test that we get a string response
    assert isinstance(obj.url(), str)

    # This call includes an image with it's payload:
    assert (
        obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        is True
    )

    # Force a case where there are no more remaining posts allowed
    mock_post.return_value.headers = {
        "X-RateLimit-Remaining": 0,
        "X-RateLimit-Reset-After": 0,
    }

    # This call includes an image with it's payload:
    assert (
        obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        is True
    )

    # behind the scenes, it should cause us to update our rate limit
    assert obj.send(body="test") is True
    assert obj.ratelimit_remaining == 0
    assert isinstance(obj.ratelimit_reset, datetime)

    # This should cause us to block
    mock_post.return_value.headers = {
        "X-RateLimit-Remaining": 0,
        "X-RateLimit-Reset-After": 3000,
    }
    assert obj.send(body="test") is True
    assert obj.ratelimit_remaining == 0
    assert isinstance(obj.ratelimit_reset, datetime)

    # Reset our variable back to 1
    mock_post.return_value.headers = {
        "X-RateLimit-Remaining": 0,
        "X-RateLimit-Reset-After": 10000,
    }
    del mock_post.return_value.headers["X-RateLimit-Remaining"]
    assert obj.send(body="test") is True
    assert obj.ratelimit_remaining == 0
    assert isinstance(obj.ratelimit_reset, datetime)

    # Return our object, but place it in the future forcing us to block
    mock_post.return_value.headers = {
        "X-RateLimit-Remaining": 0,
        "X-RateLimit-Reset-After": 0,
    }

    obj.ratelimit_remaining = 0
    assert obj.send(body="test") is True

    # Test 429 error response
    mock_post.return_value.status_code = requests.codes.too_many_requests

    # The below will attempt a second transmission and fail (because we didn't
    # set up a second post request to pass) :)
    assert obj.send(body="test") is False

    # Return our object, but place it in the future forcing us to block
    mock_post.return_value.status_code = requests.codes.ok
    mock_post.return_value.headers = {
        "X-RateLimit-Remaining": 0,
        "X-RateLimit-Reset-After": 0,
    }
    assert obj.send(body="test") is True

    # Return our limits to always work
    obj.ratelimit_remaining = 1

    # Return our headers to normal
    mock_post.return_value.headers = {
        "X-RateLimit-Remaining": 0,
        "X-RateLimit-Reset-After": 1,
    }

    # This call includes an image with it's payload:
    assert (
        obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        is True
    )

    # Create an apprise instance
    a = Apprise()

    # Our processing is slightly different when we aren't using markdown
    # as we do not pre-parse content during our notifications
    assert a.add(f"revolt://{bot_token}/{channel_id}/?format=markdown") is True

    # Toggle our logo availability
    a.asset.image_url_logo = None
    assert (
        a.notify(body="body", title="title", notify_type=NotifyType.INFO)
        is True
    )


@mock.patch("requests.post")
def test_plugin_revolt_overflow(mock_post):
    """NotifyRevolt() Overflow Checks."""

    # Initialize some generic (but valid) tokens
    bot_token = "A" * 24
    channel_id = "B" * 64

    # Prepare Mock
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok
    mock_post.return_value.content = REVOLT_GOOD_RESPONSE

    # Some variables we use to control the data we work with
    body_len = 2005
    title_len = 110

    # Number of characters per line
    row = 24

    # Create a large body and title with random data
    body = "".join(choice(str_alpha + str_num + " ") for _ in range(body_len))
    body = "\r\n".join([body[i : i + row] for i in range(0, len(body), row)])

    # Create our title using random data
    title = "".join(choice(str_alpha + str_num) for _ in range(title_len))

    results = NotifyRevolt.parse_url(
        f"revolt://{bot_token}/{channel_id}/?overflow=split"
    )

    assert isinstance(results, dict)
    assert results["user"] is None
    assert results["bot_token"] == bot_token
    assert results["targets"] == [
        channel_id,
    ]
    assert results["password"] is None
    assert results["port"] is None
    assert results["host"] == bot_token
    assert results["fullpath"] == f"/{channel_id}/"
    assert results["path"] == f"/{channel_id}/"
    assert results["query"] is None
    assert results["schema"] == "revolt"
    assert results["url"] == f"revolt://{bot_token}/{channel_id}/"

    instance = NotifyRevolt(**results)
    assert isinstance(instance, NotifyRevolt)

    results = instance._apply_overflow(
        body, title=title, overflow=OverflowMode.SPLIT
    )
    # Split into 2
    assert len(results) == 2
    assert len(results[0]["title"]) <= instance.title_maxlen
    assert len(results[0]["body"]) <= instance.body_maxlen


@mock.patch("requests.post")
def test_plugin_revolt_markdown_extra(mock_post):
    """NotifyRevolt() Markdown Extra Checks."""

    # Initialize some generic (but valid) tokens
    bot_token = "A" * 24
    channel_id = "B" * 64

    # Prepare Mock
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok
    mock_post.return_value.content = REVOLT_GOOD_RESPONSE

    # Reset our apprise object
    a = Apprise()

    # We want to further test our markdown support to accomodate bug rased on
    # 2022.10.25; see https://github.com/caronc/apprise/issues/717
    assert a.add(f"revolt://{bot_token}/{channel_id}/?format=markdown") is True

    test_markdown = "[green-blue](https://google.com)"

    # This call includes an image with it's payload:
    assert (
        a.notify(
            body=test_markdown,
            title="title",
            notify_type=NotifyType.INFO,
            body_format=NotifyFormat.TEXT,
        )
        is True
    )

    assert (
        a.notify(body="body", title="title", notify_type=NotifyType.INFO)
        is True
    )
