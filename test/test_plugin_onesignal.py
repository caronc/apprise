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
from apprise.plugins.NotifyOneSignal import NotifyOneSignal
from helpers import AppriseURLTester

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    ('onesignal://', {
        # We failed to identify any valid authentication
        'instance': TypeError,
    }),
    ('onesignal://:@/', {
        # We failed to identify any valid authentication
        'instance': TypeError,
    }),
    ('onesignal://apikey/', {
        # no app id specified
        'instance': TypeError,
    }),
    ('onesignal://appid@%20%20/', {
        # invalid apikey
        'instance': TypeError,
    }),
    ('onesignal://appid@apikey/playerid/?lang=X', {
        # invalid language id (must be 2 characters)
        'instance': TypeError,
    }),
    ('onesignal://appid@apikey/', {
        # No targets specified; we will initialize but not notify anything
        'instance': NotifyOneSignal,
        'notify_response': False,
    }),
    ('onesignal://appid@apikey/playerid', {
        # Valid playerid
        'instance': NotifyOneSignal,
        'privacy_url': 'onesignal://a...d@a...y/playerid',
    }),
    ('onesignal://appid@apikey/player', {
        # Valid player id
        'instance': NotifyOneSignal,
        # don't include an image by default
        'include_image': False,
    }),
    ('onesignal://appid@apikey/@user?image=no', {
        # Valid userid, no image
        'instance': NotifyOneSignal,
    }),
    ('onesignal://appid@apikey/user@email.com/#seg/player/@user/%20/a', {
        # Valid email, valid playerid, valid user, invalid entry (%20),
        # and too short of an entry (a)
        'instance': NotifyOneSignal,
    }),
    ('onesignal://appid@apikey?to=#segment,playerid', {
        # Test to=
        'instance': NotifyOneSignal,
    }),
    ('onesignal://appid@apikey/#segment/@user/?batch=yes', {
        # Test batch=
        'instance': NotifyOneSignal,
    }),
    ('onesignal://appid@apikey/#segment/@user/?batch=no', {
        # Test batch=
        'instance': NotifyOneSignal,
    }),
    ('onesignal://templateid:appid@apikey/playerid', {
        # Test Template ID
        'instance': NotifyOneSignal,
    }),
    ('onesignal://appid@apikey/playerid/?lang=es&subtitle=Sub', {
        # Test Language and Subtitle Over-ride
        'instance': NotifyOneSignal,
    }),
    ('onesignal://?apikey=abc&template=tp&app=123&to=playerid', {
        # Test Kwargs
        'instance': NotifyOneSignal,
    }),
    ('onesignal://appid@apikey/#segment/playerid/', {
        'instance': NotifyOneSignal,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('onesignal://appid@apikey/#segment/playerid/', {
        'instance': NotifyOneSignal,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_onesignal_urls():
    """
    NotifyOneSignal() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()
