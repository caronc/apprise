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

from apprise.plugins.NotifyParsePlatform import NotifyParsePlatform
from helpers import AppriseURLTester

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    ('parsep://', {
        'instance': None,
    }),
    # API Key + bad url
    ('parsep://:@/', {
        'instance': None,
    }),
    # APIkey; no app_id or master_key
    ('parsep://%s' % ('a' * 32), {
        'instance': TypeError,
    }),
    # APIkey; no master_key
    ('parsep://app_id@%s' % ('a' * 32), {
        'instance': TypeError,
    }),
    # APIkey; no app_id
    ('parseps://:master_key@%s' % ('a' * 32), {
        'instance': TypeError,
    }),
    # app_id + master_key (using arguments=)
    ('parseps://localhost?app_id=%s&master_key=%s' % ('a' * 32, 'd' * 32), {
        'instance': NotifyParsePlatform,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'parseps://a...a:d...d@localhost',
    }),
    # Set a device id + custom port
    ('parsep://app_id:master_key@localhost:8080?device=ios', {
        'instance': NotifyParsePlatform,
    }),
    # invalid device id
    ('parsep://app_id:master_key@localhost?device=invalid', {
        'instance': TypeError,
    }),
    # Normal Query
    ('parseps://app_id:master_key@localhost', {
        'instance': NotifyParsePlatform,
    }),
    ('parseps://app_id:master_key@localhost', {
        'instance': NotifyParsePlatform,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('parseps://app_id:master_key@localhost', {
        'instance': NotifyParsePlatform,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('parseps://app_id:master_key@localhost', {
        'instance': NotifyParsePlatform,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_parse_platform_urls():
    """
    NotifyParsePlatform() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()
