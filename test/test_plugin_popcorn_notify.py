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
import requests
from apprise.plugins.NotifyPopcornNotify import NotifyPopcornNotify
from helpers import AppriseURLTester

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    ('popcorn://', {
        # No hostname/apikey specified
        'instance': TypeError,
    }),
    ('popcorn://{}/18001231234'.format('_' * 9), {
        # invalid apikey
        'instance': TypeError,
    }),
    ('popcorn://{}/1232348923489234923489234289-32423'.format('a' * 9), {
        # invalid phone number
        'instance': NotifyPopcornNotify,
        'notify_response': False,
    }),
    ('popcorn://{}/abc'.format('b' * 9), {
        # invalid email
        'instance': NotifyPopcornNotify,
        'notify_response': False,
    }),
    ('popcorn://{}/15551232000/user@example.com'.format('c' * 9), {
        # value phone and email
        'instance': NotifyPopcornNotify,
    }),
    ('popcorn://{}/15551232000/user@example.com?batch=yes'.format('w' * 9), {
        # value phone and email with batch mode set
        'instance': NotifyPopcornNotify,
    }),
    ('popcorn://{}/?to=15551232000'.format('w' * 9), {
        # reference to to=
        'instance': NotifyPopcornNotify,
    }),
    ('popcorn://{}/15551232000'.format('x' * 9), {
        'instance': NotifyPopcornNotify,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('popcorn://{}/15551232000'.format('y' * 9), {
        'instance': NotifyPopcornNotify,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('popcorn://{}/15551232000'.format('z' * 9), {
        'instance': NotifyPopcornNotify,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_popcorn_notify_urls():
    """
    NotifyPopcornNotify() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()
