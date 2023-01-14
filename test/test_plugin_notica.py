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

from apprise.plugins.NotifyNotica import NotifyNotica
from helpers import AppriseURLTester

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    ('notica://', {
        'instance': TypeError,
    }),
    ('notica://:@/', {
        'instance': TypeError,
    }),
    # Native URL
    ('https://notica.us/?%s' % ('z' * 6), {
        'instance': NotifyNotica,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'notica://z...z/',
    }),
    # Native URL with additional arguments
    ('https://notica.us/?%s&overflow=upstream' % ('z' * 6), {
        'instance': NotifyNotica,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'notica://z...z/',
    }),
    # Token specified
    ('notica://%s' % ('a' * 6), {
        'instance': NotifyNotica,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'notica://a...a/',
    }),
    # Self-Hosted configuration
    ('notica://localhost/%s' % ('b' * 6), {
        'instance': NotifyNotica,
    }),
    ('notica://user@localhost/%s' % ('c' * 6), {
        'instance': NotifyNotica,
    }),
    ('notica://user:pass@localhost/%s/' % ('d' * 6), {
        'instance': NotifyNotica,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'notica://user:****@localhost/d...d',
    }),
    ('notica://user:pass@localhost/a/path/%s/' % ('r' * 6), {
        'instance': NotifyNotica,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'notica://user:****@localhost/a/path/r...r',
    }),
    ('notica://localhost:8080/%s' % ('a' * 6), {
        'instance': NotifyNotica,
    }),
    ('notica://user:pass@localhost:8080/%s' % ('b' * 6), {
        'instance': NotifyNotica,
    }),
    ('noticas://localhost/%s' % ('j' * 6), {
        'instance': NotifyNotica,
        'privacy_url': 'noticas://localhost/j...j',
    }),
    ('noticas://user:pass@localhost/%s' % ('e' * 6), {
        'instance': NotifyNotica,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'noticas://user:****@localhost/e...e',
    }),
    ('noticas://localhost:8080/path/%s' % ('5' * 6), {
        'instance': NotifyNotica,
        'privacy_url': 'noticas://localhost:8080/path/5...5',
    }),
    ('noticas://user:pass@localhost:8080/%s' % ('6' * 6), {
        'instance': NotifyNotica,
    }),
    ('notica://%s' % ('b' * 6), {
        'instance': NotifyNotica,
        # don't include an image by default
        'include_image': False,
    }),
    # Test Header overrides
    ('notica://localhost:8080//%s/?+HeaderKey=HeaderValue' % ('7' * 6), {
        'instance': NotifyNotica,
    }),
    ('notica://%s' % ('c' * 6), {
        'instance': NotifyNotica,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('notica://%s' % ('d' * 7), {
        'instance': NotifyNotica,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('notica://%s' % ('e' * 8), {
        'instance': NotifyNotica,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_notica_urls():
    """
    NotifyNotica() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()
