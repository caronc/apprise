# -*- coding: utf-8 -*-
# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2024, Chris Caron <lead2gold@gmail.com>
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

from apprise.plugins.NotifyOneSignal import NotifyOneSignal
from helpers import AppriseURLTester
from apprise import Apprise

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


def test_plugin_onesignal_edge_cases():
    """
    NotifyOneSignal() Batch Validation

    """
    obj = Apprise.instantiate(
        'onesignal://appid@apikey/#segment/@user/playerid/user@email.com'
        '/?batch=yes')
    # Validate that it loaded okay
    assert isinstance(obj, NotifyOneSignal)

    # all 4 types defined; but even in a batch mode, they can not be
    # sent in one submission
    assert len(obj) == 4

    #
    # Users
    #
    obj = Apprise.instantiate(
        'onesignal://appid@apikey/@user1/@user2/@user3/@user4/?batch=yes')
    assert isinstance(obj, NotifyOneSignal)

    # We can lump these together - no problem
    assert len(obj) == 1

    # Same query, but no batch mode set
    obj = Apprise.instantiate(
        'onesignal://appid@apikey/@user1/@user2/@user3/@user4/?batch=no')
    assert isinstance(obj, NotifyOneSignal)

    # Individual queries
    assert len(obj) == 4

    #
    # Segments
    #
    obj = Apprise.instantiate(
        'onesignal://appid@apikey/#segment1/#seg2/#seg3/#seg4/?batch=yes')
    assert isinstance(obj, NotifyOneSignal)

    # We can lump these together - no problem
    assert len(obj) == 1

    # Same query, but no batch mode set
    obj = Apprise.instantiate(
        'onesignal://appid@apikey/#segment1/#seg2/#seg3/#seg4/?batch=no')
    assert isinstance(obj, NotifyOneSignal)

    # Individual queries
    assert len(obj) == 4

    #
    # Player ID's
    #
    obj = Apprise.instantiate(
        'onesignal://appid@apikey/pid1/pid2/pid3/pid4/?batch=yes')
    assert isinstance(obj, NotifyOneSignal)

    # We can lump these together - no problem
    assert len(obj) == 1

    # Same query, but no batch mode set
    obj = Apprise.instantiate(
        'onesignal://appid@apikey/pid1/pid2/pid3/pid4/?batch=no')
    assert isinstance(obj, NotifyOneSignal)

    # Individual queries
    assert len(obj) == 4

    #
    # Emails
    #
    emails = ('abc@yahoo.ca', 'def@yahoo.ca', 'ghi@yahoo.ca', 'jkl@yahoo.ca')
    obj = Apprise.instantiate(
        'onesignal://appid@apikey/{}/?batch=yes'.format('/'.join(emails)))
    assert isinstance(obj, NotifyOneSignal)

    # We can lump these together - no problem
    assert len(obj) == 1

    # Same query, but no batch mode set
    obj = Apprise.instantiate(
        'onesignal://appid@apikey/{}/?batch=no'.format('/'.join(emails)))
    assert isinstance(obj, NotifyOneSignal)

    # Individual queries
    assert len(obj) == 4

    #
    # Mixed
    #
    emails = ('abc@yahoo.ca', 'def@yahoo.ca', 'ghi@yahoo.ca', 'jkl@yahoo.ca')
    users = ('@user1', '@user2', '@user3', '@user4')
    players = ('player1', 'player2', 'player3', 'player4')
    segments = ('#seg1', '#seg2', '#seg3', '#seg4')

    path = '{}/{}/{}/{}'.format(
        '/'.join(emails), '/'.join(users),
        '/'.join(players), '/'.join(segments))

    obj = Apprise.instantiate(
        'onesignal://appid@apikey/{}/?batch=yes'.format(path))
    assert isinstance(obj, NotifyOneSignal)

    # We can lump these together - no problem
    assert len(obj) == 4

    # Same query, but no batch mode set
    obj = Apprise.instantiate(
        'onesignal://appid@apikey/{}/?batch=no'.format(path))
    assert isinstance(obj, NotifyOneSignal)

    # Individual queries
    assert len(obj) == 16
