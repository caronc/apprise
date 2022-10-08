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
from json import dumps
from apprise import plugins
from helpers import AppriseURLTester

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    ('sinch://', {
        # No Account SID specified
        'instance': TypeError,
    }),
    ('sinch://:@/', {
        # invalid Auth token
        'instance': TypeError,
    }),
    ('sinch://{}@12345678'.format('a' * 32), {
        # Just spi provided
        'instance': TypeError,
    }),
    ('sinch://{}:{}@_'.format('a' * 32, 'b' * 32), {
        # spi and token provided but invalid from
        'instance': TypeError,
    }),
    ('sinch://{}:{}@{}'.format('a' * 32, 'b' * 32, '3' * 5), {
        # using short-code (5 characters) without a target
        # We can still instantiate ourselves with a valid short code
        'instance': plugins.NotifySinch,
        # Expected notify() response because we have no one to notify
        'notify_response': False,
    }),
    ('sinch://{}:{}@{}'.format('a' * 32, 'b' * 32, '3' * 9), {
        # spi and token provided and from but invalid from no
        'instance': TypeError,
    }),
    ('sinch://{}:{}@{}/123/{}/abcd/'.format(
        'a' * 32, 'b' * 32, '3' * 11, '9' * 15), {
        # valid everything but target numbers
        'instance': plugins.NotifySinch,
    }),
    ('sinch://{}:{}@12345/{}'.format('a' * 32, 'b' * 32, '4' * 11), {
        # using short-code (5 characters)
        'instance': plugins.NotifySinch,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'sinch://...aaaa:b...b@12345',
    }),
    ('sinch://{}:{}@123456/{}'.format('a' * 32, 'b' * 32, '4' * 11), {
        # using short-code (6 characters)
        'instance': plugins.NotifySinch,
    }),
    ('sinch://{}:{}@{}'.format('a' * 32, 'b' * 32, '5' * 11), {
        # using phone no with no target - we text ourselves in
        # this case
        'instance': plugins.NotifySinch,
    }),
    ('sinch://{}:{}@{}?region=eu'.format('a' * 32, 'b' * 32, '5' * 11), {
        # Specify a region
        'instance': plugins.NotifySinch,
    }),
    ('sinch://{}:{}@{}?region=invalid'.format('a' * 32, 'b' * 32, '5' * 11), {
        # Invalid region
        'instance': TypeError,
    }),
    ('sinch://_?spi={}&token={}&from={}'.format(
        'a' * 32, 'b' * 32, '5' * 11), {
        # use get args to acomplish the same thing
        'instance': plugins.NotifySinch,
    }),
    ('sinch://_?spi={}&token={}&source={}'.format(
        'a' * 32, 'b' * 32, '5' * 11), {
        # use get args to acomplish the same thing (use source instead of from)
        'instance': plugins.NotifySinch,
    }),
    ('sinch://_?spi={}&token={}&from={}&to={}'.format(
        'a' * 32, 'b' * 32, '5' * 11, '7' * 13), {
        # use to=
        'instance': plugins.NotifySinch,
    }),
    ('sinch://{}:{}@{}'.format('a' * 32, 'b' * 32, '6' * 11), {
        'instance': plugins.NotifySinch,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('sinch://{}:{}@{}'.format('a' * 32, 'b' * 32, '6' * 11), {
        'instance': plugins.NotifySinch,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_sinch_urls():
    """
    NotifyTemplate() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch('requests.post')
def test_plugin_sinch_edge_cases(mock_post):
    """
    NotifySinch() Edge Cases

    """
    # Disable Throttling to speed testing
    plugins.NotifyBase.request_rate_per_sec = 0

    # Prepare our response
    response = requests.Request()
    response.status_code = requests.codes.ok

    # Prepare Mock
    mock_post.return_value = response

    # Initialize some generic (but valid) tokens
    service_plan_id = '{}'.format('b' * 32)
    api_token = '{}'.format('b' * 32)
    source = '+1 (555) 123-3456'

    # No service_plan_id specified
    with pytest.raises(TypeError):
        plugins.NotifySinch(
            service_plan_id=None, api_token=api_token, source=source)

    # No api_token specified
    with pytest.raises(TypeError):
        plugins.NotifySinch(
            service_plan_id=service_plan_id, api_token=None, source=source)

    # a error response
    response.status_code = 400
    response.content = dumps({
        'code': 21211,
        'message': "The 'To' number +1234567 is not a valid phone number.",
    })
    mock_post.return_value = response

    # Initialize our object
    obj = plugins.NotifySinch(
        service_plan_id=service_plan_id, api_token=api_token, source=source)

    # We will fail with the above error code
    assert obj.notify('title', 'body', 'info') is False
