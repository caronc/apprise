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
import pytest
import requests

from apprise.plugins.NotifyZulip import NotifyZulip
from helpers import AppriseURLTester

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    ('zulip://', {
        'instance': TypeError,
    }),
    ('zulip://:@/', {
        'instance': TypeError,
    }),
    ('zulip://apprise', {
        # Just org provided (no token or botname)
        'instance': TypeError,
    }),
    ('zulip://botname@apprise', {
        # Just org and botname provided (no token)
        'instance': TypeError,
    }),
    # invalid token
    ('zulip://botname@apprise/{}'.format('a' * 24), {
        'instance': TypeError,
    }),
    # invalid botname
    ('zulip://....@apprise/{}'.format('a' * 32), {
        'instance': TypeError,
    }),
    # Valid everything - botname with a dash
    ('zulip://bot-name@apprise/{}'.format('a' * 32), {
        'instance': NotifyZulip,
        'privacy_url': 'zulip://bot-name@apprise/a...a/',
    }),
    # Valid everything - no target so default is used
    ('zulip://botname@apprise/{}'.format('a' * 32), {
        'instance': NotifyZulip,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'zulip://botname@apprise/a...a/',
    }),
    # Valid everything - organization as hostname
    ('zulip://botname@apprise.zulipchat.com/{}'.format('a' * 32), {
        'instance': NotifyZulip,
    }),
    # Valid everything - 2 streams specified
    ('zulip://botname@apprise/{}/channel1/channel2'.format('a' * 32), {
        'instance': NotifyZulip,
    }),
    # Valid everything - 2 streams specified (using to=)
    ('zulip://botname@apprise/{}/?to=channel1/channel2'.format('a' * 32), {
        'instance': NotifyZulip,
    }),
    # Valid everything - 2 emails specified
    ('zulip://botname@apprise/{}/user@example.com/user2@example.com'.format(
        'a' * 32), {
        'instance': NotifyZulip,
    }),
    ('zulip://botname@apprise/{}'.format('a' * 32), {
        'instance': NotifyZulip,
        # don't include an image by default
        'include_image': False,
    }),
    ('zulip://botname@apprise/{}'.format('a' * 32), {
        'instance': NotifyZulip,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('zulip://botname@apprise/{}'.format('a' * 32), {
        'instance': NotifyZulip,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('zulip://botname@apprise/{}'.format('a' * 32), {
        'instance': NotifyZulip,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_zulip_urls():
    """
    NotifyZulip() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


def test_plugin_zulip_edge_cases():
    """
    NotifyZulip() Edge Cases

    """

    # must be 32 characters long
    token = 'a' * 32

    # Invalid organization
    with pytest.raises(TypeError):
        NotifyZulip(
            botname='test', organization='#', token=token)
