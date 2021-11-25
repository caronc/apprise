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
import pytest
import requests
from apprise import plugins
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
        'instance': plugins.NotifyRyver,
    }),
    ('ryver://apprise/ckhrjW8w672m6HG?mode=ryver', {
        # No username specified; this is still okay as we use whatever
        # the user told the webhook to use; set our ryver mode
        'instance': plugins.NotifyRyver,
    }),
    # Legacy webhook mode setting:
    # Legacy webhook mode setting:
    ('ryver://apprise/ckhrjW8w672m6HG?webhook=slack', {
        # No username specified; this is still okay as we use whatever
        # the user told the webhook to use; set our slack mode
        'instance': plugins.NotifyRyver,
    }),
    ('ryver://apprise/ckhrjW8w672m6HG?webhook=ryver', {
        # No username specified; this is still okay as we use whatever
        # the user told the webhook to use; set our ryver mode
        'instance': plugins.NotifyRyver,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'ryver://apprise/c...G',
    }),
    # Support Native URLs
    ('https://apprise.ryver.com/application/webhook/ckhrjW8w672m6HG', {
        'instance': plugins.NotifyRyver,
    }),
    # Support Native URLs with arguments
    ('https://apprise.ryver.com/application/webhook/ckhrjW8w672m6HG'
     '?webhook=ryver',
        {
            'instance': plugins.NotifyRyver,
        }),
    ('ryver://caronc@apprise/ckhrjW8w672m6HG', {
        'instance': plugins.NotifyRyver,
        # don't include an image by default
        'include_image': False,
    }),
    ('ryver://apprise/ckhrjW8w672m6HG', {
        'instance': plugins.NotifyRyver,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('ryver://apprise/ckhrjW8w672m6HG', {
        'instance': plugins.NotifyRyver,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('ryver://apprise/ckhrjW8w672m6HG', {
        'instance': plugins.NotifyRyver,
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
    # Disable Throttling to speed testing
    plugins.NotifyBase.request_rate_per_sec = 0

    # No token
    with pytest.raises(TypeError):
        plugins.NotifyRyver(organization="abc", token=None)

    with pytest.raises(TypeError):
        plugins.NotifyRyver(organization="abc", token="  ")

    # No organization
    with pytest.raises(TypeError):
        plugins.NotifyRyver(organization=None, token="abc")

    with pytest.raises(TypeError):
        plugins.NotifyRyver(organization="  ", token="abc")
