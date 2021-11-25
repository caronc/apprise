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

# a test UUID we can use
UUID4 = '8b799edf-6f98-4d3a-9be7-2862fb4e5752'

# Our Testing URLs
apprise_url_tests = (
    ('kumulos://', {
        # No API or Server Key specified
        'instance': TypeError,
    }),
    ('kumulos://:@/', {
        # No API or Server Key specified
        # We don't have strict host checking on for kumulos, so this URL
        # actually becomes parseable and :@ becomes a hostname.
        # The below errors because a second token wasn't found
        'instance': TypeError,
    }),
    ('kumulos://{}/'.format(UUID4), {
        # No server key was specified
        'instance': TypeError,
    }),
    ('kumulos://{}/{}/'.format(UUID4, 'w' * 36), {
        # Everything is okay
        'instance': plugins.NotifyKumulos,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'kumulos://8...2/w...w/',
    }),
    ('kumulos://{}/{}/'.format(UUID4, 'x' * 36), {
        'instance': plugins.NotifyKumulos,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'kumulos://8...2/x...x/',
    }),
    ('kumulos://{}/{}/'.format(UUID4, 'y' * 36), {
        'instance': plugins.NotifyKumulos,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'kumulos://8...2/y...y/',
    }),
    ('kumulos://{}/{}/'.format(UUID4, 'z' * 36), {
        'instance': plugins.NotifyKumulos,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_kumulos_urls():
    """
    NotifyKumulos() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


def test_plugin_kumulos_edge_cases():
    """
    NotifyKumulos() Edge Cases

    """
    # Disable Throttling to speed testing
    plugins.NotifyBase.request_rate_per_sec = 0

    # Invalid API Key
    with pytest.raises(TypeError):
        plugins.NotifyKumulos(None, None)
    with pytest.raises(TypeError):
        plugins.NotifyKumulos("     ", None)

    # Invalid Server Key
    with pytest.raises(TypeError):
        plugins.NotifyKumulos("abcd", None)
    with pytest.raises(TypeError):
        plugins.NotifyKumulos("abcd", "       ")
