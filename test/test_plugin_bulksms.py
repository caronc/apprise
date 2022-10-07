# -*- coding: utf-8 -*-
#
# Copyright (C) 2022 Chris Caron <lead2gold@gmail.com>
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
try:
    # Python 3.x
    from unittest import mock

except ImportError:
    # Python 2.7
    import mock

import requests
from json import loads
from apprise import Apprise
from apprise import plugins
from helpers import AppriseURLTester
from apprise import NotifyType

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    ('bulksms://', {
        # Instantiated but no auth, so no otification can happen
        'instance': plugins.NotifyBulkSMS,
        # Expected notify() response because we have no one to notify
        'notify_response': False,
    }),
    ('bulksms://:@/', {
        # invalid auth
        'instance': plugins.NotifyBulkSMS,
        # Expected notify() response because we have no one to notify
        'notify_response': False,
    }),
    ('bulksms://{}@12345678'.format('a' * 10), {
        # Just user provided (no password)
        'instance': plugins.NotifyBulkSMS,
        # Expected notify() response because we have no one to notify
        'notify_response': False,
    }),
    ('bulksms://{}:{}@{}'.format('a' * 10, 'b' * 10, '3' * 5), {
        # invalid nubmer provided
        'instance': plugins.NotifyBulkSMS,
        # Expected notify() response because we have no one to notify
        'notify_response': False,
    }),
    ('bulksms://{}:{}@123/{}/abcd/'.format(
        'a' * 5, 'b' * 10, '3' * 11), {
        # included group and phone, short number (123) dropped
        'instance': plugins.NotifyBulkSMS,
        'privacy_url': 'bulksms://a...a:****@+33333333333/@abcd'
    }),
    ('bulksms://{}:{}@{}?batch=y&unicode=n'.format(
        'b' * 5, 'c' * 10, '4' * 11), {
            'instance': plugins.NotifyBulkSMS,

            # Our expected url(privacy=True) startswith() response:
            'privacy_url': 'bulksms://b...b:****@+4444444444',
    }),
    ('bulksms://{}:{}@123456/{}'.format('a' * 10, 'b' * 10, '4' * 11), {
        # using short-code (6 characters)
        'instance': plugins.NotifyBulkSMS,
    }),
    ('bulksms://{}:{}@{}'.format('a' * 10, 'b' * 10, '5' * 11), {
        # using phone no with no target - we text ourselves in
        # this case
        'instance': plugins.NotifyBulkSMS,
    }),
    # Test route group
    ('bulksms://{}:{}@admin?route=premium'.format('a' * 10, 'b' * 10), {
        'instance': plugins.NotifyBulkSMS,
    }),
    ('bulksms://{}:{}@admin?route=invalid'.format('a' * 10, 'b' * 10), {
        # invalid route
        'instance': TypeError,
    }),
    ('bulksms://_?user={}&password={}&from={}'.format(
        'a' * 10, 'b' * 10, '5' * 11), {
        # use get args to acomplish the same thing
        'instance': plugins.NotifyBulkSMS,
    }),
    ('bulksms://_?user={}&password={}&from={}'.format(
        'a' * 10, 'b' * 10, '5' * 3), {
        # use get args to acomplish the same thing
        'instance': TypeError,
    }),
    ('bulksms://_?user={}&password={}&from={}&to={}'.format(
        'a' * 10, 'b' * 10, '5' * 11, '7' * 13), {
        # use to=
        'instance': plugins.NotifyBulkSMS,
    }),
    ('bulksms://{}:{}@{}'.format('a' * 10, 'b' * 10, 'a' * 3), {
        'instance': plugins.NotifyBulkSMS,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('bulksms://{}:{}@{}'.format('a' * 10, 'b' * 10, '6' * 11), {
        'instance': plugins.NotifyBulkSMS,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_bulksms_urls():
    """
    NotifyTemplate() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch('requests.post')
def test_plugin_bulksms_edge_cases(mock_post):
    """
    NotifyBulkSMS() Edge Cases

    """
    # Disable Throttling to speed testing
    plugins.NotifyBase.request_rate_per_sec = 0

    # Initialize some generic (but valid) tokens
    user = 'abcd'
    pwd = 'mypass123'
    targets = [
        '+1(555) 123-1234',
        '1555 5555555',
        'group',
        # A garbage entry
        '12',
        # NOw a valid one because a group was implicit
        '@12',
    ]

    # Prepare our response
    response = requests.Request()
    response.status_code = requests.codes.ok

    # Prepare Mock
    mock_post.return_value = response

    # Test our markdown
    obj = Apprise.instantiate(
        'bulksms://{}:{}@{}?batch=n'.format(user, pwd, '/'.join(targets)))

    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO) is True

    # Test our call count
    assert mock_post.call_count == 4

    # Test
    details = mock_post.call_args_list[0]
    payload = loads(details[1]['data'])
    assert payload['to'] == '+15551231234'
    assert payload['body'] == 'title\r\nbody'

    details = mock_post.call_args_list[1]
    payload = loads(details[1]['data'])
    assert payload['to'] == '+15555555555'
    assert payload['body'] == 'title\r\nbody'

    details = mock_post.call_args_list[2]
    payload = loads(details[1]['data'])
    assert isinstance(payload['to'], dict)
    assert payload['to']['name'] == 'group'
    assert payload['body'] == 'title\r\nbody'

    details = mock_post.call_args_list[3]
    payload = loads(details[1]['data'])
    assert isinstance(payload['to'], dict)
    assert payload['to']['name'] == '12'
    assert payload['body'] == 'title\r\nbody'

    # Verify our URL looks good
    assert obj.url().startswith(
        'bulksms://{}:{}@{}'.format(user, pwd, '/'.join(
            ['+15551231234', '+15555555555', '@group', '@12'])))

    assert 'batch=no' in obj.url()
