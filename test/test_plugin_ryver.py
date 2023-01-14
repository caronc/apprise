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

from apprise.plugins.NotifyRyver import NotifyRyver
from helpers import AppriseURLTester

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    ('ryver://', {
        'instance': TypeError,
    }),
    ('ryver://:@/', {
        'instance': TypeError,
    }),
    ('ryver://apprise', {
        # Just org provided (no token)
        'instance': TypeError,
    }),
    ('ryver://apprise/ckhrjW8w672m6HG?mode=invalid', {
        # invalid mode provided
        'instance': TypeError,
    }),
    ('ryver://x/ckhrjW8w672m6HG?mode=slack', {
        # Invalid org
        'instance': TypeError,
    }),
    ('ryver://apprise/ckhrjW8w672m6HG?mode=slack', {
        # No username specified; this is still okay as we use whatever
        # the user told the webhook to use; set our slack mode
        'instance': NotifyRyver,
    }),
    ('ryver://apprise/ckhrjW8w672m6HG?mode=ryver', {
        # No username specified; this is still okay as we use whatever
        # the user told the webhook to use; set our ryver mode
        'instance': NotifyRyver,
    }),
    # Legacy webhook mode setting:
    # Legacy webhook mode setting:
    ('ryver://apprise/ckhrjW8w672m6HG?webhook=slack', {
        # No username specified; this is still okay as we use whatever
        # the user told the webhook to use; set our slack mode
        'instance': NotifyRyver,
    }),
    ('ryver://apprise/ckhrjW8w672m6HG?webhook=ryver', {
        # No username specified; this is still okay as we use whatever
        # the user told the webhook to use; set our ryver mode
        'instance': NotifyRyver,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'ryver://apprise/c...G',
    }),
    # Support Native URLs
    ('https://apprise.ryver.com/application/webhook/ckhrjW8w672m6HG', {
        'instance': NotifyRyver,
    }),
    # Support Native URLs with arguments
    ('https://apprise.ryver.com/application/webhook/ckhrjW8w672m6HG'
     '?webhook=ryver',
        {
            'instance': NotifyRyver,
        }),
    ('ryver://caronc@apprise/ckhrjW8w672m6HG', {
        'instance': NotifyRyver,
        # don't include an image by default
        'include_image': False,
    }),
    ('ryver://apprise/ckhrjW8w672m6HG', {
        'instance': NotifyRyver,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('ryver://apprise/ckhrjW8w672m6HG', {
        'instance': NotifyRyver,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('ryver://apprise/ckhrjW8w672m6HG', {
        'instance': NotifyRyver,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_ryver_urls():
    """
    NotifyRyver() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


def test_plugin_ryver_edge_cases():
    """
    NotifyRyver() Edge Cases

    """

    # No token
    with pytest.raises(TypeError):
        NotifyRyver(organization="abc", token=None)

    with pytest.raises(TypeError):
        NotifyRyver(organization="abc", token="  ")

    # No organization
    with pytest.raises(TypeError):
        NotifyRyver(organization=None, token="abc")

    with pytest.raises(TypeError):
        NotifyRyver(organization="  ", token="abc")
