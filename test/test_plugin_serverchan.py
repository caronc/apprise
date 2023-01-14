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
from apprise.plugins.NotifyServerChan import NotifyServerChan
from helpers import AppriseURLTester

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    ('schan://', {
        # No Access Token specified
        'instance': TypeError,
    }),
    ('schan://a_bd_/', {
        # invalid Access Token
        'instance': TypeError,
    }),
    ('schan://12345678', {
        # access token
        'instance': NotifyServerChan,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'schan://1...8',
    }),
    ('schan://{}'.format('a' * 8), {
        'instance': NotifyServerChan,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('schan://{}'.format('a' * 8), {
        'instance': NotifyServerChan,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_serverchan_urls():
    """
    NotifyServerChan() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()
