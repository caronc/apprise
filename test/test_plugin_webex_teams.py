# -*- coding: utf-8 -*-
#
# Copyright (C) 2021 Chris Caron <lead2gold@gmail.com>
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
import requests
from apprise import plugins
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
        'instance': plugins.NotifyWebexTeams,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'wxteams://a...a/',
    }),
    # Support Native URLs
    ('https://api.ciscospark.com/v1/webhooks/incoming/{}'.format('a' * 80), {
        # token provided - we're good
        'instance': plugins.NotifyWebexTeams,
    }),
    # Support Native URLs with arguments
    ('https://api.ciscospark.com/v1/webhooks/incoming/{}?format=text'.format(
        'a' * 80), {
        # token provided - we're good
        'instance': plugins.NotifyWebexTeams,
    }),
    ('wxteams://{}'.format('a' * 80), {
        'instance': plugins.NotifyWebexTeams,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('wxteams://{}'.format('a' * 80), {
        'instance': plugins.NotifyWebexTeams,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('wxteams://{}'.format('a' * 80), {
        'instance': plugins.NotifyWebexTeams,
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
