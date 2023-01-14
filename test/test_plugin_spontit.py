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
import requests

from apprise.plugins.NotifySpontit import NotifySpontit
from helpers import AppriseURLTester

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    ('spontit://', {
        # invalid url
        'instance': TypeError,
    }),
    # Another bad url
    ('spontit://:@/', {
        'instance': TypeError,
    }),
    # No user specified
    ('spontit://%s' % ('a' * 100), {
        'instance': TypeError,
    }),
    # Invalid API Key specified
    ('spontit://user@%%20_', {
        'instance': TypeError,
    }),
    # Provide a valid user and API Key
    ('spontit://%s@%s' % ('u' * 11, 'b' * 100), {
        'instance': NotifySpontit,
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'spontit://{}@b...b/'.format('u' * 11),
    }),
    # Provide a valid user and API Key, but provide an invalid channel
    ('spontit://%s@%s/#!!' % ('u' * 11, 'b' * 100), {
        # An instance is still created, but the channel won't be notified
        'instance': NotifySpontit,
    }),
    # Provide a valid user, API Key and a valid channel
    ('spontit://%s@%s/#abcd' % ('u' * 11, 'b' * 100), {
        'instance': NotifySpontit,
    }),
    # Provide a valid user, API Key, and a subtitle
    ('spontit://%s@%s/?subtitle=Test' % ('u' * 11, 'b' * 100), {
        'instance': NotifySpontit,
    }),
    # Provide a valid user, API Key, and a lengthy subtitle
    ('spontit://%s@%s/?subtitle=%s' % ('u' * 11, 'b' * 100, 'c' * 300), {
        'instance': NotifySpontit,
    }),
    # Provide a valid user and API Key, but provide a valid channel (that is
    # not ours).
    # Spontit uses a slash (/) to delimite the user from the channel id when
    # specifying channel entries. For Apprise we need to encode this
    # so we convert the slash (/) into %2F
    ('spontit://{}@{}/#1245%2Fabcd'.format('u' * 11, 'b' * 100), {
        'instance': NotifySpontit,
    }),
    # Provide multipe channels
    ('spontit://{}@{}/#1245%2Fabcd/defg'.format('u' * 11, 'b' * 100), {
        'instance': NotifySpontit,
    }),
    # Provide multipe channels through the use of the to= variable
    ('spontit://{}@{}/?to=#1245/abcd'.format('u' * 11, 'b' * 100), {
        'instance': NotifySpontit,
    }),
    ('spontit://%s@%s' % ('u' * 11, 'b' * 100), {
        'instance': NotifySpontit,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('spontit://%s@%s' % ('u' * 11, 'b' * 100), {
        'instance': NotifySpontit,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('spontit://%s@%s' % ('u' * 11, 'b' * 100), {
        'instance': NotifySpontit,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_spontit_urls():
    """
    NotifySpontit() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()
