# -*- coding: utf-8 -*-
#
# Copyright (C) 2021 Chris Caron <lead2gold@gmail.com>
# All rights reserved.
#
# This code is licensed under the MIT License.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files(the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and / or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions :
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
from unittest import mock

import pytest
import requests
from apprise import plugins
from helpers import AppriseURLTester

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    ('flock://', {
        'instance': TypeError,
    }),
    # An invalid url
    ('flock://:@/', {
        'instance': TypeError,
    }),
    # Provide a token
    ('flock://%s' % ('t' * 24), {
        'instance': plugins.NotifyFlock,
    }),
    # Image handling
    ('flock://%s?image=True' % ('t' * 24), {
        'instance': plugins.NotifyFlock,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'flock://t...t',
    }),
    ('flock://%s?image=False' % ('t' * 24), {
        'instance': plugins.NotifyFlock,
    }),
    ('flock://%s?image=True' % ('t' * 24), {
        'instance': plugins.NotifyFlock,
        # Run test when image is set to True, but one couldn't actually be
        # loaded from the Asset Object.
        'include_image': False,
    }),
    # Test to=
    ('flock://%s?to=u:%s&format=markdown' % ('i' * 24, 'u' * 12), {
        'instance': plugins.NotifyFlock,
    }),
    # Provide markdown format
    ('flock://%s?format=markdown' % ('i' * 24), {
        'instance': plugins.NotifyFlock,
    }),
    # Provide text format
    ('flock://%s?format=text' % ('i' * 24), {
        'instance': plugins.NotifyFlock,
    }),
    # Native URL Support, take the slack URL and still build from it
    ('https://api.flock.com/hooks/sendMessage/{}/'.format('i' * 24), {
        'instance': plugins.NotifyFlock,
    }),
    # Native URL Support with arguments
    ('https://api.flock.com/hooks/sendMessage/{}/?format=markdown'.format(
        'i' * 24), {
        'instance': plugins.NotifyFlock,
    }),
    # Bot API presumed if one or more targets are specified
    # Provide markdown format
    ('flock://%s/u:%s?format=markdown' % ('i' * 24, 'u' * 12), {
        'instance': plugins.NotifyFlock,
    }),
    # Bot API presumed if one or more targets are specified
    # Provide text format
    ('flock://%s/u:%s?format=html' % ('i' * 24, 'u' * 12), {
        'instance': plugins.NotifyFlock,
    }),
    # Bot API presumed if one or more targets are specified
    # u: is optional
    ('flock://%s/%s?format=text' % ('i' * 24, 'u' * 12), {
        'instance': plugins.NotifyFlock,
    }),
    # Bot API presumed if one or more targets are specified
    # Multi-entries
    ('flock://%s/g:%s/u:%s?format=text' % ('i' * 24, 'g' * 12, 'u' * 12), {
        'instance': plugins.NotifyFlock,
    }),
    # Bot API presumed if one or more targets are specified
    # Multi-entries using @ for user and # for channel
    ('flock://%s/#%s/@%s?format=text' % ('i' * 24, 'g' * 12, 'u' * 12), {
        'instance': plugins.NotifyFlock,
    }),
    # Bot API presumed if one or more targets are specified
    # has bad entry
    ('flock://%s/g:%s/u:%s?format=text' % ('i' * 24, 'g' * 12, 'u' * 10), {
        'instance': plugins.NotifyFlock,
    }),
    # Invalid user/group defined
    ('flock://%s/g:/u:?format=text' % ('i' * 24), {
        'instance': TypeError,
    }),
    # we don't focus on the invalid length of the user/group fields.
    # As a result, the following will load and pass the data upstream
    ('flock://%s/g:%s/u:%s?format=text' % ('i' * 24, 'g' * 14, 'u' * 10), {
        # We will still instantiate the object
        'instance': plugins.NotifyFlock,
    }),
    # Error Testing
    ('flock://%s/g:%s/u:%s?format=text' % ('i' * 24, 'g' * 12, 'u' * 10), {
        'instance': plugins.NotifyFlock,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('flock://%s/' % ('t' * 24), {
        'instance': plugins.NotifyFlock,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('flock://%s/' % ('t' * 24), {
        'instance': plugins.NotifyFlock,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('flock://%s/' % ('t' * 24), {
        'instance': plugins.NotifyFlock,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_flock_urls():
    """
    NotifyFlock() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch('requests.get')
@mock.patch('requests.post')
def test_plugin_flock_edge_cases(mock_post, mock_get):
    """
    NotifyFlock() Edge Cases

    """
    # Disable Throttling to speed testing
    plugins.NotifyBase.request_rate_per_sec = 0

    # Initializes the plugin with an invalid token
    with pytest.raises(TypeError):
        plugins.NotifyFlock(token=None)
    # Whitespace also acts as an invalid token value
    with pytest.raises(TypeError):
        plugins.NotifyFlock(token="   ")
