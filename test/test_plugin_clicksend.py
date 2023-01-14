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

from apprise.plugins.NotifyClickSend import NotifyClickSend
from helpers import AppriseURLTester

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    ('clicksend://', {
        # We failed to identify any valid authentication
        'instance': TypeError,
    }),
    ('clicksend://:@/', {
        # We failed to identify any valid authentication
        'instance': TypeError,
    }),
    ('clicksend://user:pass@{}/{}/{}'.format('1' * 9, '2' * 15, 'a' * 13), {
        # invalid target numbers; we'll fail to notify anyone
        'instance': NotifyClickSend,
        'notify_response': False,
    }),
    ('clicksend://user:pass@{}?batch=yes'.format('3' * 14), {
        # valid number
        'instance': NotifyClickSend,
    }),
    ('clicksend://user:pass@{}?batch=yes&to={}'.format('3' * 14, '6' * 14), {
        # valid number but using the to= variable
        'instance': NotifyClickSend,
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'clicksend://user:****',
    }),
    ('clicksend://user:pass@{}?batch=no'.format('3' * 14), {
        # valid number - no batch
        'instance': NotifyClickSend,
    }),
    ('clicksend://user:pass@{}'.format('3' * 14), {
        'instance': NotifyClickSend,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('clicksend://user:pass@{}'.format('3' * 14), {
        'instance': NotifyClickSend,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_clicksend_urls():
    """
    NotifyClickSend() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()
