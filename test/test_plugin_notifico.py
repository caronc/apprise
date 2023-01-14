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

from apprise.plugins.NotifyNotifico import NotifyNotifico
from helpers import AppriseURLTester

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    ('notifico://', {
        'instance': TypeError,
    }),
    ('notifico://:@/', {
        'instance': TypeError,
    }),
    ('notifico://1234', {
        # Just a project id provided (no message token)
        'instance': TypeError,
    }),
    ('notifico://abcd/ckhrjW8w672m6HG', {
        # an invalid project id provided
        'instance': TypeError,
    }),
    ('notifico://1234/ckhrjW8w672m6HG', {
        # A project id and message hook provided
        'instance': NotifyNotifico,
    }),
    ('notifico://1234/ckhrjW8w672m6HG?prefix=no', {
        # Disable our prefix
        'instance': NotifyNotifico,
    }),
    ('notifico://1234/ckhrjW8w672m6HG?color=yes', {
        'instance': NotifyNotifico,
        'notify_type': 'info',
    }),
    ('notifico://1234/ckhrjW8w672m6HG?color=yes', {
        'instance': NotifyNotifico,
        'notify_type': 'success',
    }),
    ('notifico://1234/ckhrjW8w672m6HG?color=yes', {
        'instance': NotifyNotifico,
        'notify_type': 'warning',
    }),
    ('notifico://1234/ckhrjW8w672m6HG?color=yes', {
        'instance': NotifyNotifico,
        'notify_type': 'failure',
    }),
    ('notifico://1234/ckhrjW8w672m6HG?color=yes', {
        'instance': NotifyNotifico,
        'notify_type': 'invalid',
    }),
    ('notifico://1234/ckhrjW8w672m6HG?color=no', {
        # Test our color flag by having it set to off
        'instance': NotifyNotifico,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'notifico://1...4/c...G',
    }),
    # Support Native URLs
    ('https://n.tkte.ch/h/2144/uJmKaBW9WFk42miB146ci3Kj', {
        'instance': NotifyNotifico,
    }),
    ('notifico://1234/ckhrjW8w672m6HG', {
        'instance': NotifyNotifico,
        # don't include an image by default
        'include_image': False,
    }),
    ('notifico://1234/ckhrjW8w672m6HG', {
        'instance': NotifyNotifico,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('notifico://1234/ckhrjW8w672m6HG', {
        'instance': NotifyNotifico,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('notifico://1234/ckhrjW8w672m6HG', {
        'instance': NotifyNotifico,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_notifico_urls():
    """
    NotifyNotifico() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()
