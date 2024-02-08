# -*- coding: utf-8 -*-
# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2024, Chris Caron <lead2gold@gmail.com>
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

import os
from unittest import mock
from datetime import datetime, timedelta
from datetime import timezone
import pytest
import requests

from apprise.plugins.NotifyRevolt import NotifyRevolt
from helpers import AppriseURLTester
from apprise import Apprise
from apprise import NotifyType
from apprise import NotifyFormat
from apprise.common import OverflowMode

from random import choice
from string import ascii_uppercase as str_alpha
from string import digits as str_num

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Attachment Directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), 'var')

# Our Testing URLs
apprise_url_tests = (
    ('revolt://', {
        'instance': TypeError,
    }),
    # An invalid url
    ('revolt://:@/', {
        'instance': TypeError,
    }),
    # No channel_id specified
    ('revolt://%s' % ('i' * 24), {
        'instance': TypeError,
    }),
    # channel_id specified on url
    ('revolt://?channel_id=%s' % ('i' * 24), {
        'instance': TypeError,
    }),
    # Provide both a bot token and a channel id
    ('revolt://%s/%s' % ('i' * 24, 't' * 64), {
        'instance': NotifyRevolt,
        'requests_response_code': requests.codes.no_content,
    }),
    # Provide a temporary username
    ('revolt://l2g@%s/%s' % ('i' * 24, 't' * 64), {
        'instance': NotifyRevolt,
        'requests_response_code': requests.codes.no_content,
    }),
    ('revolt://l2g@_?bot_token=%s&channel_id=%s' % ('i' * 24, 't' * 64), {
        'instance': NotifyRevolt,
        'requests_response_code': requests.codes.no_content,
    }),
    # test custom_img= field
    ('revolt://%s/%s?format=markdown&custom_img=Yes' % (
        'i' * 24, 't' * 64), {
            'instance': NotifyRevolt,
            'requests_response_code': requests.codes.no_content,
    }),
    ('revolt://%s/%s?format=markdown&custom_img=No' % (
        'i' * 24, 't' * 64), {
            'instance': NotifyRevolt,
            'requests_response_code': requests.codes.no_content,
    }),
    # different format support
    ('revolt://%s/%s?format=markdown' % ('i' * 24, 't' * 64), {
        'instance': NotifyRevolt,
        'requests_response_code': requests.codes.no_content,
    }),
    ('revolt://%s/%s?format=text' % ('i' * 24, 't' * 64), {
        'instance': NotifyRevolt,
        'requests_response_code': requests.codes.no_content,
    }),
    # Test with embed_url (title link)
    ('revolt://%s/%s?hmarkdown=true&embed_url=http://localhost' % (
        'i' * 24, 't' * 64), {
            'instance': NotifyRevolt,
            'requests_response_code': requests.codes.no_content,
    }),
    # Test with avatar URL
    ('revolt://%s/%s?embed_img=http://localhost/test.jpg' % (
        'i' * 24, 't' * 64), {
            'instance': NotifyRevolt,
            'requests_response_code': requests.codes.no_content,
    }),
    # Test without image set
    ('revolt://%s/%s' % ('i' * 24, 't' * 64), {
        'instance': NotifyRevolt,
        'requests_response_code': requests.codes.no_content,
        # don't include an image by default
        'embed_img': False,
    }),
    ('revolt://%s/%s/' % ('a' * 24, 'b' * 64), {
        'instance': NotifyRevolt,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('revolt://%s/%s/' % ('a' * 24, 'b' * 64), {
        'instance': NotifyRevolt,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('revolt://%s/%s/' % ('a' * 24, 'b' * 64), {
        'instance': NotifyRevolt,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_revolt_urls():
    """
    NotifyRevolt() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch('requests.post')
def test_plugin_revolt_notifications(mock_post):
    """
    NotifyRevolt() Notifications/Ping Support

    """

    # Initialize some generic (but valid) tokens
    bot_token = 'A' * 24
    channel_id = 'B' * 64

    # Prepare Mock
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok

    # Test our header parsing when not lead with a header
    body = """
    # Heading
    @everyone and @admin, wake and meet our new user <@123>; <@&456>"
    """

    results = NotifyRevolt.parse_url(
        f'revolt://{bot_token}/{channel_id}/?format=markdown')

    assert isinstance(results, dict)
    assert results['user'] is None
    assert results['bot_token'] == bot_token
    assert results['channel_id'] == channel_id
    assert results['password'] is None
    assert results['port'] is None
    assert results['host'] == bot_token
    assert results['fullpath'] == f'/{channel_id}/'
    assert results['path'] == f'/{channel_id}/'
    assert results['query'] is None
    assert results['schema'] == 'revolt'
    assert results['url'] == f'revolt://{bot_token}/{channel_id}/'

    instance = NotifyRevolt(**results)
    assert isinstance(instance, NotifyRevolt)

    response = instance.send(body=body)
    assert response is True
    assert mock_post.call_count == 1

    # Reset our object
    mock_post.reset_mock()

    results = NotifyRevolt.parse_url(
        f'revolt://{bot_token}/{channel_id}/?format=text')

    assert isinstance(results, dict)
    assert results['user'] is None
    assert results['bot_token'] == bot_token
    assert results['channel_id'] == channel_id
    assert results['password'] is None
    assert results['port'] is None
    assert results['host'] == bot_token
    assert results['fullpath'] == f'/{channel_id}/'
    assert results['path'] == f'/{channel_id}/'
    assert results['query'] is None
    assert results['schema'] == 'revolt'
    assert results['url'] == f'revolt://{bot_token}/{channel_id}/'

    instance = NotifyRevolt(**results)
    assert isinstance(instance, NotifyRevolt)

    response = instance.send(body=body)
    assert response is True
    assert mock_post.call_count == 1


@mock.patch('requests.post')
def test_plugin_revolt_general(mock_post):
    """
    NotifyRevolt() General Checks

    """

    # Turn off clock skew for local testing
    NotifyRevolt.clock_skew = timedelta(seconds=0)
    # Epoch time:
    epoch = datetime.fromtimestamp(0, timezone.utc)

    # Initialize some generic (but valid) tokens
    bot_token = 'A' * 24
    channel_id = 'B' * 64

    # Prepare Mock
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok
    mock_post.return_value.content = ''
    mock_post.return_value.headers = {
        'X-RateLimit-Reset': (
            datetime.now(timezone.utc) - epoch).total_seconds(),
        'X-RateLimit-Remaining': 1,
    }

    # Invalid bot_token
    with pytest.raises(TypeError):
        NotifyRevolt(bot_token=None, channel_id=channel_id)
    # Invalid bot_token (whitespace)
    with pytest.raises(TypeError):
        NotifyRevolt(bot_token="  ", channel_id=channel_id)

    # Invalid channel_id
    with pytest.raises(TypeError):
        NotifyRevolt(bot_token=bot_token, channel_id=None)
    # Invalid channel_id (whitespace)
    with pytest.raises(TypeError):
        NotifyRevolt(bot_token=bot_token, channel_id="   ")

    obj = NotifyRevolt(
        bot_token=bot_token,
        channel_id=channel_id)
    assert obj.ratelimit_remaining == 1

    # Test that we get a string response
    assert isinstance(obj.url(), str) is True

    # This call includes an image with it's payload:
    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO) is True

    # Force a case where there are no more remaining posts allowed
    mock_post.return_value.headers = {
        'X-RateLimit-Reset': (
            datetime.now(timezone.utc) - epoch).total_seconds(),
        'X-RateLimit-Remaining': 0,
    }

    # This call includes an image with it's payload:
    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO) is True

    # behind the scenes, it should cause us to update our rate limit
    assert obj.send(body="test") is True
    assert obj.ratelimit_remaining == 0

    # This should cause us to block
    mock_post.return_value.headers = {
        'X-RateLimit-Reset': (
            datetime.now(timezone.utc) - epoch).total_seconds(),
        'X-RateLimit-Remaining': 10,
    }
    assert obj.send(body="test") is True
    assert obj.ratelimit_remaining == 10

    # Reset our variable back to 1
    mock_post.return_value.headers = {
        'X-RateLimit-Reset': (
            datetime.now(timezone.utc) - epoch).total_seconds(),
        'X-RateLimit-Remaining': 1,
    }
    # Handle cases where our epoch time is wrong
    del mock_post.return_value.headers['X-RateLimit-Reset']
    assert obj.send(body="test") is True

    # Return our object, but place it in the future forcing us to block
    mock_post.return_value.headers = {
        'X-RateLimit-Reset': (
            datetime.now(timezone.utc) - epoch).total_seconds() + 1,
        'X-RateLimit-Remaining': 0,
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
        'X-RateLimit-Reset': (
            datetime.now(timezone.utc) - epoch).total_seconds() - 1,
        'X-RateLimit-Remaining': 0,
    }
    assert obj.send(body="test") is True

    # Return our limits to always work
    obj.ratelimit_remaining = 1

    # Return our headers to normal
    mock_post.return_value.headers = {
        'X-RateLimit-Reset': (
            datetime.now(timezone.utc) - epoch).total_seconds(),
        'X-RateLimit-Remaining': 1,
    }

    # This call includes an image with it's payload:
    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO) is True

    # Create an apprise instance
    a = Apprise()

    # Our processing is slightly different when we aren't using markdown
    # as we do not pre-parse content during our notifications
    assert a.add(
        'revolt://{bot_token}/{channel_id}/'
        '?format=markdown'.format(
            bot_token=bot_token,
            channel_id=channel_id)) is True

    # Toggle our logo availability
    a.asset.image_url_logo = None
    assert a.notify(
        body='body', title='title', notify_type=NotifyType.INFO) is True


@mock.patch('requests.post')
def test_plugin_revolt_overflow(mock_post):
    """
    NotifyRevolt() Overflow Checks

    """

    # Initialize some generic (but valid) tokens
    bot_token = 'A' * 24
    channel_id = 'B' * 64

    # Prepare Mock
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok

    # Some variables we use to control the data we work with
    body_len = 2000
    title_len = 100

    # Number of characters per line
    row = 24

    # Create a large body and title with random data
    body = ''.join(choice(str_alpha + str_num + ' ') for _ in range(body_len))
    body = '\r\n'.join([body[i: i + row] for i in range(0, len(body), row)])

    # Create our title using random data
    title = ''.join(choice(str_alpha + str_num) for _ in range(title_len))

    results = NotifyRevolt.parse_url(
        f'revolt://{bot_token}/{channel_id}/?overflow=split')

    assert isinstance(results, dict)
    assert results['user'] is None
    assert results['bot_token'] == bot_token
    assert results['channel_id'] == channel_id
    assert results['password'] is None
    assert results['port'] is None
    assert results['host'] == bot_token
    assert results['fullpath'] == f'/{channel_id}/'
    assert results['path'] == f'/{channel_id}/'
    assert results['query'] is None
    assert results['schema'] == 'revolt'
    assert results['url'] == f'revolt://{bot_token}/{channel_id}/'

    instance = NotifyRevolt(**results)
    assert isinstance(instance, NotifyRevolt)

    results = instance._apply_overflow(
        body, title=title, overflow=OverflowMode.SPLIT)

    # Ensure we never exceed 2000 characters
    for entry in results:
        assert len(entry['title']) <= instance.title_maxlen
        assert len(entry['title']) + len(entry['body']) <= instance.body_maxlen


@mock.patch('requests.post')
def test_plugin_revolt_markdown_extra(mock_post):
    """
    NotifyRevolt() Markdown Extra Checks

    """

    # Initialize some generic (but valid) tokens
    bot_token = 'A' * 24
    channel_id = 'B' * 64

    # Prepare Mock
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok

    # Reset our apprise object
    a = Apprise()

    # We want to further test our markdown support to accomodate bug rased on
    # 2022.10.25; see https://github.com/caronc/apprise/issues/717
    assert a.add(
        'revolt://{bot_token}/{channel_id}/'
        '?format=markdown'.format(
            bot_token=bot_token,
            channel_id=channel_id)) is True

    test_markdown = "[green-blue](https://google.com)"

    # This call includes an image with it's payload:
    assert a.notify(body=test_markdown, title='title',
                    notify_type=NotifyType.INFO,
                    body_format=NotifyFormat.TEXT) is True

    assert a.notify(
        body='body', title='title', notify_type=NotifyType.INFO) is True
