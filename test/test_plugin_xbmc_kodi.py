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
from apprise import NotifyType
from apprise.plugins.NotifyXBMC import NotifyXBMC
from helpers import AppriseURLTester

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    ('kodi://', {
        'instance': None,
    }),
    ('kodis://', {
        'instance': None,
    }),
    ('kodi://localhost', {
        'instance': NotifyXBMC,
    }),
    ('kodi://192.168.4.1', {
        # Support IPv4 Addresses
        'instance': NotifyXBMC,
    }),
    ('kodi://[2001:db8:002a:3256:adfe:05c0:0003:0006]', {
        # Support IPv6 Addresses
        'instance': NotifyXBMC,
        # Privacy URL
        'privacy_url': 'kodi://[2001:db8:002a:3256:adfe:05c0:0003:0006]',
    }),
    ('kodi://[2001:db8:002a:3256:adfe:05c0:0003:0006]:8282', {
        # Support IPv6 Addresses with port
        'instance': NotifyXBMC,
        # Privacy URL
        'privacy_url': 'kodi://[2001:db8:002a:3256:adfe:05c0:0003:0006]:8282',
    }),
    ('kodi://user:pass@localhost', {
        'instance': NotifyXBMC,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'kodi://user:****@localhost',
    }),
    ('kodi://localhost:8080', {
        'instance': NotifyXBMC,
    }),
    ('kodi://user:pass@localhost:8080', {
        'instance': NotifyXBMC,
    }),
    ('kodis://localhost', {
        'instance': NotifyXBMC,
    }),
    ('kodis://user:pass@localhost', {
        'instance': NotifyXBMC,
    }),
    ('kodis://localhost:8080/path/', {
        'instance': NotifyXBMC,
    }),
    ('kodis://user:password@localhost:8080', {
        'instance': NotifyXBMC,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'kodis://user:****@localhost:8080',
    }),
    ('kodi://localhost', {
        'instance': NotifyXBMC,
        # Experement with different notification types
        'notify_type': NotifyType.WARNING,
    }),
    ('kodi://localhost', {
        'instance': NotifyXBMC,
        # Experement with different notification types
        'notify_type': NotifyType.FAILURE,
    }),
    ('kodis://localhost:443', {
        'instance': NotifyXBMC,
        # don't include an image by default
        'include_image': False,
    }),
    ('kodi://:@/', {
        'instance': None,
    }),
    ('kodi://user:pass@localhost:8081', {
        'instance': NotifyXBMC,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('kodi://user:pass@localhost:8082', {
        'instance': NotifyXBMC,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('kodi://user:pass@localhost:8083', {
        'instance': NotifyXBMC,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),

    #
    # XMBC (Legacy Platform) Shares this same KODI Plugin
    #

    ('xbmc://', {
        'instance': None,
    }),
    ('xbmc://localhost', {
        'instance': NotifyXBMC,
    }),
    ('xbmc://localhost?duration=14', {
        'instance': NotifyXBMC,
    }),
    ('xbmc://localhost?duration=invalid', {
        'instance': NotifyXBMC,
    }),
    ('xbmc://localhost?duration=-1', {
        'instance': NotifyXBMC,
    }),
    ('xbmc://user:pass@localhost', {
        'instance': NotifyXBMC,
    }),
    ('xbmc://localhost:8080', {
        'instance': NotifyXBMC,
    }),
    ('xbmc://user:pass@localhost:8080', {
        'instance': NotifyXBMC,
    }),
    ('xbmc://user@localhost', {
        'instance': NotifyXBMC,
        # don't include an image by default
        'include_image': False,
    }),
    ('xbmc://localhost', {
        'instance': NotifyXBMC,
        # Experement with different notification types
        'notify_type': NotifyType.WARNING,
    }),
    ('xbmc://localhost', {
        'instance': NotifyXBMC,
        # Experement with different notification types
        'notify_type': NotifyType.FAILURE,
    }),
    ('xbmc://:@/', {
        'instance': None,
    }),
    ('xbmc://user:pass@localhost:8081', {
        'instance': NotifyXBMC,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('xbmc://user:pass@localhost:8082', {
        'instance': NotifyXBMC,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('xbmc://user:pass@localhost:8083', {
        'instance': NotifyXBMC,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_xbmc_kodi_urls():
    """
    NotifyXBMC() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()
