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

from apprise.plugins.NotifyDingTalk import NotifyDingTalk
from helpers import AppriseURLTester

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    ('dingtalk://', {
        # No Access Token specified
        'instance': TypeError,
    }),
    ('dingtalk://a_bd_/', {
        # invalid Access Token
        'instance': TypeError,
    }),
    ('dingtalk://12345678', {
        # access token
        'instance': NotifyDingTalk,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'dingtalk://1...8',
    }),
    ('dingtalk://{}/{}'.format('a' * 8, '1' * 14), {
        # access token + phone number
        'instance': NotifyDingTalk,
    }),
    ('dingtalk://{}/{}/invalid'.format('a' * 8, '1' * 3), {
        # access token + 2 invalid phone numbers
        'instance': NotifyDingTalk,
    }),
    ('dingtalk://{}/?to={}'.format('a' * 8, '1' * 14), {
        # access token + phone number using 'to'
        'instance': NotifyDingTalk,
    }),
    # Test secret via user@
    ('dingtalk://secret@{}/?to={}'.format('a' * 8, '1' * 14), {
        # access token + phone number using 'to'
        'instance': NotifyDingTalk,
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'dingtalk://****@a...a',
    }),
    # Test secret via secret= and token=
    ('dingtalk://?token={}&to={}&secret={}'.format(
        'b' * 8, '1' * 14, 'a' * 15), {
            # access token + phone number using 'to'
            'instance': NotifyDingTalk,
        'privacy_url': 'dingtalk://****@b...b',
    }),
    # Invalid secret
    ('dingtalk://{}/?to={}&secret=_'.format('a' * 8, '1' * 14), {
        'instance': TypeError,
    }),
    ('dingtalk://{}?format=markdown'.format('a' * 8), {
        # access token
        'instance': NotifyDingTalk,
    }),
    ('dingtalk://{}'.format('a' * 8), {
        'instance': NotifyDingTalk,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('dingtalk://{}'.format('a' * 8), {
        'instance': NotifyDingTalk,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_dingtalk_urls():
    """
    NotifyDingTalk() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()
