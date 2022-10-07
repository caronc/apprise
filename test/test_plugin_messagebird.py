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
    ('msgbird://', {
        # No hostname/apikey specified
        'instance': TypeError,
    }),
    ('msgbird://{}/abcd'.format('a' * 25), {
        # invalid characters in source phone number
        'instance': TypeError,
    }),
    ('msgbird://{}/123'.format('a' * 25), {
        # invalid source phone number
        'instance': TypeError,
    }),
    ('msgbird://{}/15551232000'.format('a' * 25), {
        # target phone number becomes who we text too; all is good
        'instance': plugins.NotifyMessageBird,
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'msgbird://a...a/15551232000',
    }),
    ('msgbird://{}/15551232000/abcd'.format('a' * 25), {
        # valid credentials
        'instance': plugins.NotifyMessageBird,
        # Since there are no targets specified we expect a False return on
        # send()
        'notify_response': False,
    }),
    ('msgbird://{}/15551232000/123'.format('a' * 25), {
        # valid credentials
        'instance': plugins.NotifyMessageBird,
        # Since there are no targets specified we expect a False return on
        # send()
        'notify_response': False,
    }),
    ('msgbird://{}/?from=15551233000&to=15551232000'.format('a' * 25), {
        # reference to to= and from=
        'instance': plugins.NotifyMessageBird,
    }),
    ('msgbird://{}/15551232000'.format('a' * 25), {
        'instance': plugins.NotifyMessageBird,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('msgbird://{}/15551232000'.format('a' * 25), {
        'instance': plugins.NotifyMessageBird,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('msgbird://{}/15551232000'.format('a' * 25), {
        'instance': plugins.NotifyMessageBird,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_messagebird_urls():
    """
    NotifyTemplate() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch('requests.post')
def test_plugin_messagebird_edge_cases(mock_post):
    """
    NotifyMessageBird() Edge Cases

    """
    # Disable Throttling to speed testing
    plugins.NotifyBase.request_rate_per_sec = 0

    # Prepare our response
    response = requests.Request()
    response.status_code = requests.codes.ok

    # Prepare Mock
    mock_post.return_value = response

    # Initialize some generic (but valid) tokens
    # authkey = '{}'.format('a' * 24)
    source = '+1 (555) 123-3456'

    # No apikey specified
    with pytest.raises(TypeError):
        plugins.NotifyMessageBird(apikey=None, source=source)
    with pytest.raises(TypeError):
        plugins.NotifyMessageBird(apikey="     ", source=source)
