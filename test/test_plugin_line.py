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
from apprise.plugins.NotifyLine import NotifyLine
from helpers import AppriseURLTester

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    ('line://', {
        # No Access Token
        'instance': TypeError,
    }),
    ('line://%20/', {
        # invalid Access Token; no Integration/Routing Key
        'instance': TypeError,
    }),
    ('line://token', {
        # no target specified
        'instance': NotifyLine,
        # Expected notify() response
        'notify_response': False,

    }),
    ('line://token=/target', {
        # minimum requirements met
        'instance': NotifyLine,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'line://****/t...t?',
    }),
    ('line://token/target?image=no', {
        # minimum requirements met; no icon display
        'instance': NotifyLine,
    }),
    ('line://a/very/long/token=/target?image=no', {
        # minimum requirements met; no icon display
        'instance': NotifyLine,
    }),
    ('line://?token=token&to=target1', {
        # minimum requirements met
        'instance': NotifyLine,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'line://****/t...1?',
    }),
    ('line://token/target', {
        'instance': NotifyLine,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('line://token/target', {
        'instance': NotifyLine,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_line_urls():
    """
    NotifyLine() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()
