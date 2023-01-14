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
import pytest
import requests

from apprise.plugins.NotifyKumulos import NotifyKumulos
from helpers import AppriseURLTester

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# a test UUID we can use
UUID4 = '8b799edf-6f98-4d3a-9be7-2862fb4e5752'

# Our Testing URLs
apprise_url_tests = (
    ('kumulos://', {
        # No API or Server Key specified
        'instance': TypeError,
    }),
    ('kumulos://:@/', {
        # No API or Server Key specified
        # We don't have strict host checking on for kumulos, so this URL
        # actually becomes parseable and :@ becomes a hostname.
        # The below errors because a second token wasn't found
        'instance': TypeError,
    }),
    ('kumulos://{}/'.format(UUID4), {
        # No server key was specified
        'instance': TypeError,
    }),
    ('kumulos://{}/{}/'.format(UUID4, 'w' * 36), {
        # Everything is okay
        'instance': NotifyKumulos,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'kumulos://8...2/w...w/',
    }),
    ('kumulos://{}/{}/'.format(UUID4, 'x' * 36), {
        'instance': NotifyKumulos,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'kumulos://8...2/x...x/',
    }),
    ('kumulos://{}/{}/'.format(UUID4, 'y' * 36), {
        'instance': NotifyKumulos,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'kumulos://8...2/y...y/',
    }),
    ('kumulos://{}/{}/'.format(UUID4, 'z' * 36), {
        'instance': NotifyKumulos,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_kumulos_urls():
    """
    NotifyKumulos() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


def test_plugin_kumulos_edge_cases():
    """
    NotifyKumulos() Edge Cases

    """

    # Invalid API Key
    with pytest.raises(TypeError):
        NotifyKumulos(None, None)
    with pytest.raises(TypeError):
        NotifyKumulos("     ", None)

    # Invalid Server Key
    with pytest.raises(TypeError):
        NotifyKumulos("abcd", None)
    with pytest.raises(TypeError):
        NotifyKumulos("abcd", "       ")
