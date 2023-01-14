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
from apprise.plugins.NotifyBark import NotifyBark
from helpers import AppriseURLTester

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    ('bark://', {
        # No no host
        'instance': None,
    }),
    ('bark://:@/', {
        # just invalid all around
        'instance': None,
    }),
    ('bark://localhost', {
        # No Device Key specified
        'instance': NotifyBark,
        # Expected notify() response False (because we won't be able
        # to actually notify anything if no device_key was specified
        'notify_response': False,

    }),
    ('bark://192.168.0.6:8081/device_key', {
        # Everything is okay
        'instance': NotifyBark,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'bark://192.168.0.6:8081/',
    }),
    ('bark://user@192.168.0.6:8081/device_key', {
        # Everything is okay (test with user)
        'instance': NotifyBark,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'bark://user@192.168.0.6:8081/',
    }),
    ('bark://192.168.0.6:8081/device_key/?sound=invalid', {
        # bad sound, but we go ahead anyway
        'instance': NotifyBark,
    }),
    ('bark://192.168.0.6:8081/device_key/?sound=alarm', {
        # alarm.caf sound loaded
        'instance': NotifyBark,
    }),
    ('bark://192.168.0.6:8081/device_key/?sound=NOiR.cAf', {
        # noir.caf sound loaded
        'instance': NotifyBark,
    }),
    ('bark://192.168.0.6:8081/device_key/?badge=100', {
        # set badge
        'instance': NotifyBark,
    }),
    ('barks://192.168.0.6:8081/device_key/?badge=invalid', {
        # set invalid badge
        'instance': NotifyBark,
    }),
    ('barks://192.168.0.6:8081/device_key/?badge=-12', {
        # set invalid badge
        'instance': NotifyBark,
    }),
    ('bark://192.168.0.6:8081/device_key/?category=apprise', {
        # set category
        'instance': NotifyBark,
    }),
    ('bark://192.168.0.6:8081/device_key/?image=no', {
        # do not display image
        'instance': NotifyBark,
    }),
    ('bark://192.168.0.6:8081/device_key/?group=apprise', {
        # set group
        'instance': NotifyBark,
    }),
    ('bark://192.168.0.6:8081/device_key/?level=invalid', {
        # bad level, but we go ahead anyway
        'instance': NotifyBark,
    }),
    ('bark://192.168.0.6:8081/?to=device_key', {
        # test use of to= argument
        'instance': NotifyBark,
    }),
    ('bark://192.168.0.6:8081/device_key/?click=http://localhost', {
        # Our click link
        'instance': NotifyBark,
    }),
    ('bark://192.168.0.6:8081/device_key/?level=active', {
        # active level
        'instance': NotifyBark,
    }),
    ('bark://user:pass@192.168.0.5:8086/device_key/device_key2/', {
        # Everything is okay
        'instance': NotifyBark,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'bark://user:****@192.168.0.5:8086/',
    }),
    ('barks://192.168.0.7/device_key/', {
        'instance': NotifyBark,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'barks://192.168.0.7/device_key',
    }),
    ('bark://192.168.0.7/device_key', {
        'instance': NotifyBark,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_bark_urls():
    """
    NotifyBark() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()
