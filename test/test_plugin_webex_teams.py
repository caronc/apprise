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
from apprise.plugins.NotifyWebexTeams import NotifyWebexTeams
from helpers import AppriseURLTester

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    ('wxteams://', {
        # Teams Token missing
        'instance': TypeError,
    }),
    ('wxteams://:@/', {
        # We don't have strict host checking on for wxteams, so this URL
        # actually becomes parseable and :@ becomes a hostname.
        # The below errors because a second token wasn't found
        'instance': TypeError,
    }),
    ('wxteams://{}'.format('a' * 80), {
        # token provided - we're good
        'instance': NotifyWebexTeams,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'wxteams://a...a/',
    }),
    # Support Native URLs
    ('https://api.ciscospark.com/v1/webhooks/incoming/{}'.format('a' * 80), {
        # token provided - we're good
        'instance': NotifyWebexTeams,
    }),
    # Support Native URLs with arguments
    ('https://api.ciscospark.com/v1/webhooks/incoming/{}?format=text'.format(
        'a' * 80), {
        # token provided - we're good
        'instance': NotifyWebexTeams,
    }),
    ('wxteams://{}'.format('a' * 80), {
        'instance': NotifyWebexTeams,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('wxteams://{}'.format('a' * 80), {
        'instance': NotifyWebexTeams,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('wxteams://{}'.format('a' * 80), {
        'instance': NotifyWebexTeams,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_webex_teams_urls():
    """
    NotifyWebexTeams() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()
