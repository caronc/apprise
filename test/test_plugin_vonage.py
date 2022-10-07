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
    ('vonage://', {
        # No API Key specified
        'instance': TypeError,
    }),
    ('vonage://:@/', {
        # invalid Auth key
        'instance': TypeError,
    }),
    ('vonage://AC{}@12345678'.format('a' * 8), {
        # Just a key provided
        'instance': TypeError,
    }),
    ('vonage://AC{}:{}@{}'.format('a' * 8, 'b' * 16, '3' * 9), {
        # key and secret provided and from but invalid from no
        'instance': TypeError,
    }),
    ('vonage://AC{}:{}@{}/?ttl=0'.format('b' * 8, 'c' * 16, '3' * 11), {
        # Invalid ttl defined
        'instance': TypeError,
    }),
    ('vonage://AC{}:{}@{}'.format('d' * 8, 'e' * 16, 'a' * 11), {
        # Invalid source number
        'instance': TypeError,
    }),
    ('vonage://AC{}:{}@{}/123/{}/abcd/'.format(
        'f' * 8, 'g' * 16, '3' * 11, '9' * 15), {
        # valid everything but target numbers
        'instance': plugins.NotifyVonage,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'vonage://A...f:****@',
    }),
    ('vonage://AC{}:{}@{}'.format('h' * 8, 'i' * 16, '5' * 11), {
        # using phone no with no target - we text ourselves in
        # this case
        'instance': plugins.NotifyVonage,
    }),
    ('vonage://_?key=AC{}&secret={}&from={}'.format(
        'a' * 8, 'b' * 16, '5' * 11), {
        # use get args to acomplish the same thing
        'instance': plugins.NotifyVonage,
    }),
    ('vonage://_?key=AC{}&secret={}&source={}'.format(
        'a' * 8, 'b' * 16, '5' * 11), {
        # use get args to acomplish the same thing (use source instead of from)
        'instance': plugins.NotifyVonage,
    }),
    ('vonage://_?key=AC{}&secret={}&from={}&to={}'.format(
        'a' * 8, 'b' * 16, '5' * 11, '7' * 13), {
        # use to=
        'instance': plugins.NotifyVonage,
    }),
    ('vonage://AC{}:{}@{}'.format('a' * 8, 'b' * 16, '6' * 11), {
        'instance': plugins.NotifyVonage,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('vonage://AC{}:{}@{}'.format('a' * 8, 'b' * 16, '6' * 11), {
        'instance': plugins.NotifyVonage,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),

    # Nexmo Backwards Support
    ('nexmo://', {
        # No API Key specified
        'instance': TypeError,
    }),
    ('nexmo://:@/', {
        # invalid Auth key
        'instance': TypeError,
    }),
    ('nexmo://AC{}@12345678'.format('a' * 8), {
        # Just a key provided
        'instance': TypeError,
    }),
    ('nexmo://AC{}:{}@{}'.format('a' * 8, 'b' * 16, '3' * 9), {
        # key and secret provided and from but invalid from no
        'instance': TypeError,
    }),
    ('nexmo://AC{}:{}@{}/?ttl=0'.format('b' * 8, 'c' * 16, '3' * 11), {
        # Invalid ttl defined
        'instance': TypeError,
    }),
    ('nexmo://AC{}:{}@{}'.format('d' * 8, 'e' * 16, 'a' * 11), {
        # Invalid source number
        'instance': TypeError,
    }),
    ('nexmo://AC{}:{}@{}/123/{}/abcd/'.format(
        'f' * 8, 'g' * 16, '3' * 11, '9' * 15), {
        # valid everything but target numbers
        'instance': plugins.NotifyVonage,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'vonage://A...f:****@',
    }),
    ('nexmo://AC{}:{}@{}'.format('h' * 8, 'i' * 16, '5' * 11), {
        # using phone no with no target - we text ourselves in
        # this case
        'instance': plugins.NotifyVonage,
    }),
    ('nexmo://_?key=AC{}&secret={}&from={}'.format(
        'a' * 8, 'b' * 16, '5' * 11), {
        # use get args to acomplish the same thing
        'instance': plugins.NotifyVonage,
    }),
    ('nexmo://_?key=AC{}&secret={}&source={}'.format(
        'a' * 8, 'b' * 16, '5' * 11), {
        # use get args to acomplish the same thing (use source instead of from)
        'instance': plugins.NotifyVonage,
    }),
    ('nexmo://_?key=AC{}&secret={}&from={}&to={}'.format(
        'a' * 8, 'b' * 16, '5' * 11, '7' * 13), {
        # use to=
        'instance': plugins.NotifyVonage,
    }),
    ('nexmo://AC{}:{}@{}'.format('a' * 8, 'b' * 16, '6' * 11), {
        'instance': plugins.NotifyVonage,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('nexmo://AC{}:{}@{}'.format('a' * 8, 'b' * 16, '6' * 11), {
        'instance': plugins.NotifyVonage,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_vonage_urls():
    """
    NotifyVonage() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch('requests.post')
def test_plugin_vonage_edge_cases(mock_post):
    """
    NotifyVonage() Edge Cases

    """
    # Disable Throttling to speed testing
    plugins.NotifyBase.request_rate_per_sec = 0

    # Prepare our response
    response = requests.Request()
    response.status_code = requests.codes.ok

    # Prepare Mock
    mock_post.return_value = response

    # Initialize some generic (but valid) tokens
    apikey = 'AC{}'.format('b' * 8)
    secret = '{}'.format('b' * 16)
    source = '+1 (555) 123-3456'

    # No apikey specified
    with pytest.raises(TypeError):
        plugins.NotifyVonage(apikey=None, secret=secret, source=source)

    with pytest.raises(TypeError):
        plugins.NotifyVonage(apikey="  ", secret=secret, source=source)

    # No secret specified
    with pytest.raises(TypeError):
        plugins.NotifyVonage(apikey=apikey, secret=None, source=source)

    with pytest.raises(TypeError):
        plugins.NotifyVonage(apikey=apikey, secret="  ", source=source)

    # a error response
    response.status_code = 400
    response.content = dumps({
        'code': 21211,
        'message': "The 'To' number +1234567 is not a valid phone number.",
    })
    mock_post.return_value = response

    # Initialize our object
    obj = plugins.NotifyVonage(
        apikey=apikey, secret=secret, source=source)

    # We will fail with the above error code
    assert obj.notify('title', 'body', 'info') is False
