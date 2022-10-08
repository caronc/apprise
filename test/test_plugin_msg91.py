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
    ('msg91://', {
        # No hostname/authkey specified
        'instance': TypeError,
    }),
    ('msg91://-', {
        # Invalid AuthKey
        'instance': TypeError,
    }),
    ('msg91://{}'.format('a' * 23), {
        # valid AuthKey
        'instance': plugins.NotifyMSG91,
        # Since there are no targets specified we expect a False return on
        # send()
        'notify_response': False,
    }),
    ('msg91://{}/123'.format('a' * 23), {
        # invalid phone number
        'instance': plugins.NotifyMSG91,
        # Since there are no targets specified we expect a False return on
        # send()
        'notify_response': False,
    }),
    ('msg91://{}/abcd'.format('a' * 23), {
        # No number to notify
        'instance': plugins.NotifyMSG91,
        # Since there are no targets specified we expect a False return on
        # send()
        'notify_response': False,
    }),
    ('msg91://{}/15551232000/?country=invalid'.format('a' * 23), {
        # invalid country
        'instance': TypeError,
    }),
    ('msg91://{}/15551232000/?country=99'.format('a' * 23), {
        # invalid country
        'instance': TypeError,
    }),
    ('msg91://{}/15551232000/?route=invalid'.format('a' * 23), {
        # invalid route
        'instance': TypeError,
    }),
    ('msg91://{}/15551232000/?route=99'.format('a' * 23), {
        # invalid route
        'instance': TypeError,
    }),
    ('msg91://{}/15551232000'.format('a' * 23), {
        # a valid message
        'instance': plugins.NotifyMSG91,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'msg91://a...a/15551232000',
    }),
    ('msg91://{}/?to=15551232000'.format('a' * 23), {
        # a valid message
        'instance': plugins.NotifyMSG91,
    }),
    ('msg91://{}/15551232000?country=91&route=1'.format('a' * 23), {
        # using phone no with no target - we text ourselves in
        # this case
        'instance': plugins.NotifyMSG91,
    }),
    ('msg91://{}/15551232000'.format('a' * 23), {
        # use get args to acomplish the same thing
        'instance': plugins.NotifyMSG91,
    }),
    ('msg91://{}/15551232000'.format('a' * 23), {
        'instance': plugins.NotifyMSG91,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('msg91://{}/15551232000'.format('a' * 23), {
        'instance': plugins.NotifyMSG91,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_msg91_urls():
    """
    NotifyMSG91() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch('requests.post')
def test_plugin_msg91_edge_cases(mock_post):
    """
    NotifyMSG91() Edge Cases

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
    target = '+1 (555) 123-3456'

    # No authkey specified
    with pytest.raises(TypeError):
        plugins.NotifyMSG91(authkey=None, targets=target)
    with pytest.raises(TypeError):
        plugins.NotifyMSG91(authkey="    ", targets=target)
