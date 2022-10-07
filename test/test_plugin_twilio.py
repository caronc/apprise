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

import requests
import pytest
from json import dumps
from apprise import plugins
from apprise import Apprise
from helpers import AppriseURLTester

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    ('twilio://', {
        # No Account SID specified
        'instance': TypeError,
    }),
    ('twilio://:@/', {
        # invalid Auth token
        'instance': TypeError,
    }),
    ('twilio://AC{}@12345678'.format('a' * 32), {
        # Just sid provided
        'instance': TypeError,
    }),
    ('twilio://AC{}:{}@_'.format('a' * 32, 'b' * 32), {
        # sid and token provided but invalid from
        'instance': TypeError,
    }),
    ('twilio://AC{}:{}@{}'.format('a' * 32, 'b' * 32, '3' * 5), {
        # using short-code (5 characters) without a target
        # We can still instantiate ourselves with a valid short code
        'instance': plugins.NotifyTwilio,
        # Since there are no targets specified we expect a False return on
        # send()
        'notify_response': False,
    }),
    ('twilio://AC{}:{}@{}'.format('a' * 32, 'b' * 32, '3' * 9), {
        # sid and token provided and from but invalid from no
        'instance': TypeError,
    }),
    ('twilio://AC{}:{}@{}/123/{}/abcd/'.format(
        'a' * 32, 'b' * 32, '3' * 11, '9' * 15), {
        # valid everything but target numbers
        'instance': plugins.NotifyTwilio,
    }),
    ('twilio://AC{}:{}@12345/{}'.format('a' * 32, 'b' * 32, '4' * 11), {
        # using short-code (5 characters)
        'instance': plugins.NotifyTwilio,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'twilio://...aaaa:b...b@12345',
    }),
    ('twilio://AC{}:{}@123456/{}'.format('a' * 32, 'b' * 32, '4' * 11), {
        # using short-code (6 characters)
        'instance': plugins.NotifyTwilio,
    }),
    ('twilio://AC{}:{}@{}'.format('a' * 32, 'b' * 32, '5' * 11), {
        # using phone no with no target - we text ourselves in
        # this case
        'instance': plugins.NotifyTwilio,
    }),
    ('twilio://_?sid=AC{}&token={}&from={}'.format(
        'a' * 32, 'b' * 32, '5' * 11), {
        # use get args to acomplish the same thing
        'instance': plugins.NotifyTwilio,
    }),
    ('twilio://_?sid=AC{}&token={}&source={}'.format(
        'a' * 32, 'b' * 32, '5' * 11), {
        # use get args to acomplish the same thing (use source instead of from)
        'instance': plugins.NotifyTwilio,
    }),
    ('twilio://_?sid=AC{}&token={}&from={}&to={}'.format(
        'a' * 32, 'b' * 32, '5' * 11, '7' * 13), {
        # use to=
        'instance': plugins.NotifyTwilio,
    }),
    ('twilio://AC{}:{}@{}'.format('a' * 32, 'b' * 32, '6' * 11), {
        'instance': plugins.NotifyTwilio,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('twilio://AC{}:{}@{}'.format('a' * 32, 'b' * 32, '6' * 11), {
        'instance': plugins.NotifyTwilio,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_twilio_urls():
    """
    NotifyTwilio() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch('requests.post')
def test_plugin_twilio_auth(mock_post):
    """
    NotifyTwilio() Auth
      - account-wide auth token
      - API key and its own auth token

    """
    # Disable Throttling to speed testing
    plugins.NotifyBase.request_rate_per_sec = 0

    response = mock.Mock()
    response.content = ''
    response.status_code = requests.codes.ok

    # Prepare Mock
    mock_post.return_value = response

    # Initialize some generic (but valid) tokens
    account_sid = 'AC{}'.format('b' * 32)
    apikey = 'SK{}'.format('b' * 32)
    auth_token = '{}'.format('b' * 32)
    source = '+1 (555) 123-3456'
    dest = '+1 (555) 987-6543'
    message_contents = "test"

    # Variation of initialization without API key
    obj = Apprise.instantiate(
        'twilio://{}:{}@{}/{}'
        .format(account_sid, auth_token, source, dest))
    assert isinstance(obj, plugins.NotifyTwilio) is True
    assert isinstance(obj.url(), str) is True

    # Send Notification
    assert obj.send(body=message_contents) is True

    # Variation of initialization with API key
    obj = Apprise.instantiate(
        'twilio://{}:{}@{}/{}?apikey={}'
        .format(account_sid, auth_token, source, dest, apikey))
    assert isinstance(obj, plugins.NotifyTwilio) is True
    assert isinstance(obj.url(), str) is True

    # Send Notification
    assert obj.send(body=message_contents) is True

    # Validate expected call parameters
    assert mock_post.call_count == 2
    first_call = mock_post.call_args_list[0]
    second_call = mock_post.call_args_list[1]

    # URL and message parameters are the same for both calls
    assert first_call[0][0] == \
        second_call[0][0] == \
        'https://api.twilio.com/2010-04-01/Accounts/{}/Messages.json'.format(
            account_sid)
    assert first_call[1]['data']['Body'] == \
        second_call[1]['data']['Body'] == \
        message_contents
    assert first_call[1]['data']['From'] == \
        second_call[1]['data']['From'] == \
        '+15551233456'
    assert first_call[1]['data']['To'] == \
        second_call[1]['data']['To'] == \
        '+15559876543'

    # Auth differs depending on if API Key is used
    assert first_call[1]['auth'] == (account_sid, auth_token)
    assert second_call[1]['auth'] == (apikey, auth_token)


@mock.patch('requests.post')
def test_plugin_twilio_edge_cases(mock_post):
    """
    NotifyTwilio() Edge Cases

    """
    # Disable Throttling to speed testing
    plugins.NotifyBase.request_rate_per_sec = 0

    # Prepare our response
    response = requests.Request()
    response.status_code = requests.codes.ok

    # Prepare Mock
    mock_post.return_value = response

    # Initialize some generic (but valid) tokens
    account_sid = 'AC{}'.format('b' * 32)
    auth_token = '{}'.format('b' * 32)
    source = '+1 (555) 123-3456'

    # No account_sid specified
    with pytest.raises(TypeError):
        plugins.NotifyTwilio(
            account_sid=None, auth_token=auth_token, source=source)

    # No auth_token specified
    with pytest.raises(TypeError):
        plugins.NotifyTwilio(
            account_sid=account_sid, auth_token=None, source=source)

    # a error response
    response.status_code = 400
    response.content = dumps({
        'code': 21211,
        'message': "The 'To' number +1234567 is not a valid phone number.",
    })
    mock_post.return_value = response

    # Initialize our object
    obj = plugins.NotifyTwilio(
        account_sid=account_sid, auth_token=auth_token, source=source)

    # We will fail with the above error code
    assert obj.notify('title', 'body', 'info') is False
