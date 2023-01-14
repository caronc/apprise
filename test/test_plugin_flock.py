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

from apprise.plugins.NotifyFlock import NotifyFlock
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
        'instance': NotifyFlock,
    }),
    # Image handling
    ('flock://%s?image=True' % ('t' * 24), {
        'instance': NotifyFlock,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'flock://t...t',
    }),
    ('flock://%s?image=False' % ('t' * 24), {
        'instance': NotifyFlock,
    }),
    ('flock://%s?image=True' % ('t' * 24), {
        'instance': NotifyFlock,
        # Run test when image is set to True, but one couldn't actually be
        # loaded from the Asset Object.
        'include_image': False,
    }),
    # Test to=
    ('flock://%s?to=u:%s&format=markdown' % ('i' * 24, 'u' * 12), {
        'instance': NotifyFlock,
    }),
    # Provide markdown format
    ('flock://%s?format=markdown' % ('i' * 24), {
        'instance': NotifyFlock,
    }),
    # Provide text format
    ('flock://%s?format=text' % ('i' * 24), {
        'instance': NotifyFlock,
    }),
    # Native URL Support, take the slack URL and still build from it
    ('https://api.flock.com/hooks/sendMessage/{}/'.format('i' * 24), {
        'instance': NotifyFlock,
    }),
    # Native URL Support with arguments
    ('https://api.flock.com/hooks/sendMessage/{}/?format=markdown'.format(
        'i' * 24), {
        'instance': NotifyFlock,
    }),
    # Bot API presumed if one or more targets are specified
    # Provide markdown format
    ('flock://%s/u:%s?format=markdown' % ('i' * 24, 'u' * 12), {
        'instance': NotifyFlock,
    }),
    # Bot API presumed if one or more targets are specified
    # Provide text format
    ('flock://%s/u:%s?format=html' % ('i' * 24, 'u' * 12), {
        'instance': NotifyFlock,
    }),
    # Bot API presumed if one or more targets are specified
    # u: is optional
    ('flock://%s/%s?format=text' % ('i' * 24, 'u' * 12), {
        'instance': NotifyFlock,
    }),
    # Bot API presumed if one or more targets are specified
    # Multi-entries
    ('flock://%s/g:%s/u:%s?format=text' % ('i' * 24, 'g' * 12, 'u' * 12), {
        'instance': NotifyFlock,
    }),
    # Bot API presumed if one or more targets are specified
    # Multi-entries using @ for user and # for channel
    ('flock://%s/#%s/@%s?format=text' % ('i' * 24, 'g' * 12, 'u' * 12), {
        'instance': NotifyFlock,
    }),
    # Bot API presumed if one or more targets are specified
    # has bad entry
    ('flock://%s/g:%s/u:%s?format=text' % ('i' * 24, 'g' * 12, 'u' * 10), {
        'instance': NotifyFlock,
    }),
    # Invalid user/group defined
    ('flock://%s/g:/u:?format=text' % ('i' * 24), {
        'instance': TypeError,
    }),
    # we don't focus on the invalid length of the user/group fields.
    # As a result, the following will load and pass the data upstream
    ('flock://%s/g:%s/u:%s?format=text' % ('i' * 24, 'g' * 14, 'u' * 10), {
        # We will still instantiate the object
        'instance': NotifyFlock,
    }),
    # Error Testing
    ('flock://%s/g:%s/u:%s?format=text' % ('i' * 24, 'g' * 12, 'u' * 10), {
        'instance': NotifyFlock,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('flock://%s/' % ('t' * 24), {
        'instance': NotifyFlock,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('flock://%s/' % ('t' * 24), {
        'instance': NotifyFlock,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('flock://%s/' % ('t' * 24), {
        'instance': NotifyFlock,
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

    # Initializes the plugin with an invalid token
    with pytest.raises(TypeError):
        NotifyFlock(token=None)
    # Whitespace also acts as an invalid token value
    with pytest.raises(TypeError):
        NotifyFlock(token="   ")
