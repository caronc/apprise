# -*- coding: utf-8 -*-
#
# Apprise - Push Notification Library.
# Copyright (C) 2023  Chris Caron <lead2gold@gmail.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor,
# Boston, MA  02110-1301, USA.
from unittest import mock

import requests
from json import loads
from apprise import Apprise
from apprise.plugins.NotifyBulkSMS import NotifyBulkSMS
from helpers import AppriseURLTester
from apprise import NotifyType

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    ('bulksms://', {
        # Instantiated but no auth, so no otification can happen
        'instance': NotifyBulkSMS,
        # Expected notify() response because we have no one to notify
        'notify_response': False,
    }),
    ('bulksms://:@/', {
        # invalid auth
        'instance': NotifyBulkSMS,
        # Expected notify() response because we have no one to notify
        'notify_response': False,
    }),
    ('bulksms://{}@12345678'.format('a' * 10), {
        # Just user provided (no password)
        'instance': NotifyBulkSMS,
        # Expected notify() response because we have no one to notify
        'notify_response': False,
    }),
    ('bulksms://{}:{}@{}'.format('a' * 10, 'b' * 10, '3' * 5), {
        # invalid nubmer provided
        'instance': NotifyBulkSMS,
        # Expected notify() response because we have no one to notify
        'notify_response': False,
    }),
    ('bulksms://{}:{}@123/{}/abcd/'.format(
        'a' * 5, 'b' * 10, '3' * 11), {
        # included group and phone, short number (123) dropped
        'instance': NotifyBulkSMS,
        'privacy_url': 'bulksms://a...a:****@+33333333333/@abcd'
    }),
    ('bulksms://{}:{}@{}?batch=y&unicode=n'.format(
        'b' * 5, 'c' * 10, '4' * 11), {
            'instance': NotifyBulkSMS,

            # Our expected url(privacy=True) startswith() response:
            'privacy_url': 'bulksms://b...b:****@+4444444444',
    }),
    ('bulksms://{}:{}@123456/{}'.format('a' * 10, 'b' * 10, '4' * 11), {
        # using short-code (6 characters)
        'instance': NotifyBulkSMS,
    }),
    ('bulksms://{}:{}@{}'.format('a' * 10, 'b' * 10, '5' * 11), {
        # using phone no with no target - we text ourselves in
        # this case
        'instance': NotifyBulkSMS,
    }),
    # Test route group
    ('bulksms://{}:{}@admin?route=premium'.format('a' * 10, 'b' * 10), {
        'instance': NotifyBulkSMS,
    }),
    ('bulksms://{}:{}@admin?route=invalid'.format('a' * 10, 'b' * 10), {
        # invalid route
        'instance': TypeError,
    }),
    ('bulksms://_?user={}&password={}&from={}'.format(
        'a' * 10, 'b' * 10, '5' * 11), {
        # use get args to acomplish the same thing
        'instance': NotifyBulkSMS,
    }),
    ('bulksms://_?user={}&password={}&from={}'.format(
        'a' * 10, 'b' * 10, '5' * 3), {
        # use get args to acomplish the same thing
        'instance': TypeError,
    }),
    ('bulksms://_?user={}&password={}&from={}&to={}'.format(
        'a' * 10, 'b' * 10, '5' * 11, '7' * 13), {
        # use to=
        'instance': NotifyBulkSMS,
    }),
    ('bulksms://{}:{}@{}'.format('a' * 10, 'b' * 10, 'a' * 3), {
        'instance': NotifyBulkSMS,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('bulksms://{}:{}@{}'.format('a' * 10, 'b' * 10, '6' * 11), {
        'instance': NotifyBulkSMS,
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
