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
from apprise.plugins.NotifyKavenegar import NotifyKavenegar
from helpers import AppriseURLTester

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    ('kavenegar://', {
        # We failed to identify any valid authentication
        'instance': TypeError,
    }),
    ('kavenegar://:@/', {
        # We failed to identify any valid authentication
        'instance': TypeError,
    }),
    ('kavenegar://{}/{}/{}'.format('1' * 10, '2' * 15, 'a' * 13), {
        # valid api key and valid authentication
        'instance': NotifyKavenegar,
        # Since there are no targets specified we expect a False return on
        # send()
        'notify_response': False,
    }),
    ('kavenegar://{}/{}'.format('a' * 24, '3' * 14), {
        # valid api key and valid number
        'instance': NotifyKavenegar,
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'kavenegar://a...a/',
    }),
    ('kavenegar://{}?to={}'.format('a' * 24, '3' * 14), {
        # valid api key and valid number
        'instance': NotifyKavenegar,
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'kavenegar://a...a/',
    }),
    ('kavenegar://{}@{}/{}'.format('1' * 14, 'b' * 24, '3' * 14), {
        # valid api key and valid number
        'instance': NotifyKavenegar,
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'kavenegar://{}@b...b/'.format('1' * 14),
    }),
    ('kavenegar://{}@{}/{}'.format('a' * 14, 'b' * 24, '3' * 14), {
        # invalid from number
        'instance': TypeError,
    }),
    ('kavenegar://{}@{}/{}'.format('3' * 4, 'b' * 24, '3' * 14), {
        # invalid from number
        'instance': TypeError,
    }),
    ('kavenegar://{}/{}?from={}'.format('b' * 24, '3' * 14, '1' * 14), {
        # valid api key and valid number
        'instance': NotifyKavenegar,
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'kavenegar://{}@b...b/'.format('1' * 14),
    }),
    ('kavenegar://{}/{}'.format('b' * 24, '4' * 14), {
        'instance': NotifyKavenegar,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('kavenegar://{}/{}'.format('c' * 24, '5' * 14), {
        'instance': NotifyKavenegar,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_kavenegar_urls():
    """
    NotifyKavenegar() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()
