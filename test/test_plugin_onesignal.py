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
from apprise import plugins
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
        'instance': plugins.NotifyOneSignal,
        'notify_response': False,
    }),
    ('onesignal://appid@apikey/playerid', {
        # Valid playerid
        'instance': plugins.NotifyOneSignal,
        'privacy_url': 'onesignal://a...d@a...y/playerid',
    }),
    ('onesignal://appid@apikey/player', {
        # Valid player id
        'instance': plugins.NotifyOneSignal,
        # don't include an image by default
        'include_image': False,
    }),
    ('onesignal://appid@apikey/@user?image=no', {
        # Valid userid, no image
        'instance': plugins.NotifyOneSignal,
    }),
    ('onesignal://appid@apikey/user@email.com/#seg/player/@user/%20/a', {
        # Valid email, valid playerid, valid user, invalid entry (%20),
        # and too short of an entry (a)
        'instance': plugins.NotifyOneSignal,
    }),
    ('onesignal://appid@apikey?to=#segment,playerid', {
        # Test to=
        'instance': plugins.NotifyOneSignal,
    }),
    ('onesignal://appid@apikey/#segment/@user/?batch=yes', {
        # Test batch=
        'instance': plugins.NotifyOneSignal,
    }),
    ('onesignal://appid@apikey/#segment/@user/?batch=no', {
        # Test batch=
        'instance': plugins.NotifyOneSignal,
    }),
    ('onesignal://templateid:appid@apikey/playerid', {
        # Test Template ID
        'instance': plugins.NotifyOneSignal,
    }),
    ('onesignal://appid@apikey/playerid/?lang=es&subtitle=Sub', {
        # Test Language and Subtitle Over-ride
        'instance': plugins.NotifyOneSignal,
    }),
    ('onesignal://?apikey=abc&template=tp&app=123&to=playerid', {
        # Test Kwargs
        'instance': plugins.NotifyOneSignal,
    }),
    ('onesignal://appid@apikey/#segment/playerid/', {
        'instance': plugins.NotifyOneSignal,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('onesignal://appid@apikey/#segment/playerid/', {
        'instance': plugins.NotifyOneSignal,
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
