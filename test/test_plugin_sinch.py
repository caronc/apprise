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

import pytest
import requests
from json import dumps

from apprise.plugins.NotifySinch import NotifySinch
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
        'instance': NotifySinch,
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
        'instance': NotifySinch,
    }),
    ('sinch://{}:{}@12345/{}'.format('a' * 32, 'b' * 32, '4' * 11), {
        # using short-code (5 characters)
        'instance': NotifySinch,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'sinch://...aaaa:b...b@12345',
    }),
    ('sinch://{}:{}@123456/{}'.format('a' * 32, 'b' * 32, '4' * 11), {
        # using short-code (6 characters)
        'instance': NotifySinch,
    }),
    ('sinch://{}:{}@{}'.format('a' * 32, 'b' * 32, '5' * 11), {
        # using phone no with no target - we text ourselves in
        # this case
        'instance': NotifySinch,
    }),
    ('sinch://{}:{}@{}?region=eu'.format('a' * 32, 'b' * 32, '5' * 11), {
        # Specify a region
        'instance': NotifySinch,
    }),
    ('sinch://{}:{}@{}?region=invalid'.format('a' * 32, 'b' * 32, '5' * 11), {
        # Invalid region
        'instance': TypeError,
    }),
    ('sinch://_?spi={}&token={}&from={}'.format(
        'a' * 32, 'b' * 32, '5' * 11), {
        # use get args to acomplish the same thing
        'instance': NotifySinch,
    }),
    ('sinch://_?spi={}&token={}&source={}'.format(
        'a' * 32, 'b' * 32, '5' * 11), {
        # use get args to acomplish the same thing (use source instead of from)
        'instance': NotifySinch,
    }),
    ('sinch://_?spi={}&token={}&from={}&to={}'.format(
        'a' * 32, 'b' * 32, '5' * 11, '7' * 13), {
        # use to=
        'instance': NotifySinch,
    }),
    ('sinch://{}:{}@{}'.format('a' * 32, 'b' * 32, '6' * 11), {
        'instance': NotifySinch,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('sinch://{}:{}@{}'.format('a' * 32, 'b' * 32, '6' * 11), {
        'instance': NotifySinch,
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
        NotifySinch(
            service_plan_id=None, api_token=api_token, source=source)

    # No api_token specified
    with pytest.raises(TypeError):
        NotifySinch(
            service_plan_id=service_plan_id, api_token=None, source=source)

    # a error response
    response.status_code = 400
    response.content = dumps({
        'code': 21211,
        'message': "The 'To' number +1234567 is not a valid phone number.",
    })
    mock_post.return_value = response

    # Initialize our object
    obj = NotifySinch(
        service_plan_id=service_plan_id, api_token=api_token, source=source)

    # We will fail with the above error code
    assert obj.notify('title', 'body', 'info') is False
