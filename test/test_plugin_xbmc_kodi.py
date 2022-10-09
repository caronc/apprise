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
