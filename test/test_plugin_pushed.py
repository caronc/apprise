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

from apprise.plugins.NotifyPushed import NotifyPushed
from helpers import AppriseURLTester

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    ('pushed://', {
        'instance': TypeError,
    }),
    # Application Key Only
    ('pushed://%s' % ('a' * 32), {
        'instance': TypeError,
    }),
    # Invalid URL
    ('pushed://:@/', {
        'instance': TypeError,
    }),
    # Application Key+Secret
    ('pushed://%s/%s' % ('a' * 32, 'a' * 64), {
        'instance': NotifyPushed,
    }),
    # Application Key+Secret + channel
    ('pushed://%s/%s/#channel/' % ('a' * 32, 'a' * 64), {
        'instance': NotifyPushed,
    }),
    # Application Key+Secret + channel (via to=)
    ('pushed://%s/%s?to=channel' % ('a' * 32, 'a' * 64), {
        'instance': NotifyPushed,
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'pushed://a...a/****/',
    }),
    # Application Key+Secret + dropped entry
    ('pushed://%s/%s/dropped_value/' % ('a' * 32, 'a' * 64), {
        # No entries validated is a fail
        'instance': TypeError,
    }),
    # Application Key+Secret + 2 channels
    ('pushed://%s/%s/#channel1/#channel2' % ('a' * 32, 'a' * 64), {
        'instance': NotifyPushed,
    }),
    # Application Key+Secret + User Pushed ID
    ('pushed://%s/%s/@ABCD/' % ('a' * 32, 'a' * 64), {
        'instance': NotifyPushed,
    }),
    # Application Key+Secret + 2 devices
    ('pushed://%s/%s/@ABCD/@DEFG/' % ('a' * 32, 'a' * 64), {
        'instance': NotifyPushed,
    }),
    # Application Key+Secret + Combo
    ('pushed://%s/%s/@ABCD/#channel' % ('a' * 32, 'a' * 64), {
        'instance': NotifyPushed,
    }),
    # ,
    ('pushed://%s/%s' % ('a' * 32, 'a' * 64), {
        'instance': NotifyPushed,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('pushed://%s/%s' % ('a' * 32, 'a' * 64), {
        'instance': NotifyPushed,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('pushed://%s/%s' % ('a' * 32, 'a' * 64), {
        'instance': NotifyPushed,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
    ('pushed://%s/%s' % ('a' * 32, 'a' * 64), {
        'instance': NotifyPushed,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('pushed://%s/%s' % ('a' * 32, 'a' * 64), {
        'instance': NotifyPushed,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('pushed://%s/%s/#channel' % ('a' * 32, 'a' * 64), {
        'instance': NotifyPushed,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('pushed://%s/%s/@user' % ('a' * 32, 'a' * 64), {
        'instance': NotifyPushed,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('pushed://%s/%s' % ('a' * 32, 'a' * 64), {
        'instance': NotifyPushed,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_pushed_urls():
    """
    NotifyPushed() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch('requests.get')
@mock.patch('requests.post')
def test_plugin_pushed_edge_cases(mock_post, mock_get):
    """
    NotifyPushed() Edge Cases

    """

    # Chat ID
    recipients = '@ABCDEFG, @DEFGHIJ, #channel, #channel2'

    # Some required input
    app_key = 'ABCDEFG'
    app_secret = 'ABCDEFG'

    # Prepare Mock
    mock_get.return_value = requests.Request()
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok
    mock_get.return_value.status_code = requests.codes.ok

    # No application Key specified
    with pytest.raises(TypeError):
        NotifyPushed(
            app_key=None,
            app_secret=app_secret,
            recipients=None,
        )

    with pytest.raises(TypeError):
        NotifyPushed(
            app_key="  ",
            app_secret=app_secret,
            recipients=None,
        )
    # No application Secret specified
    with pytest.raises(TypeError):
        NotifyPushed(
            app_key=app_key,
            app_secret=None,
            recipients=None,
        )

    with pytest.raises(TypeError):
        NotifyPushed(
            app_key=app_key,
            app_secret="   ",
        )

    # recipients list set to (None) is perfectly fine; in this case it will
    # notify the App
    obj = NotifyPushed(
        app_key=app_key,
        app_secret=app_secret,
        recipients=None,
    )
    assert isinstance(obj, NotifyPushed) is True
    assert len(obj.channels) == 0
    assert len(obj.users) == 0

    obj = NotifyPushed(
        app_key=app_key,
        app_secret=app_secret,
        targets=recipients,
    )
    assert isinstance(obj, NotifyPushed) is True
    assert len(obj.channels) == 2
    assert len(obj.users) == 2

    # Prepare Mock to fail
    mock_post.return_value.status_code = requests.codes.internal_server_error
    mock_get.return_value.status_code = requests.codes.internal_server_error
