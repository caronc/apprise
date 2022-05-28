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
from apprise import plugins
from helpers import AppriseURLTester

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    ('notica://', {
        'instance': TypeError,
    }),
    ('notica://:@/', {
        'instance': TypeError,
    }),
    # Native URL
    ('https://notica.us/?%s' % ('z' * 6), {
        'instance': plugins.NotifyNotica,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'notica://z...z/',
    }),
    # Native URL with additional arguments
    ('https://notica.us/?%s&overflow=upstream' % ('z' * 6), {
        'instance': plugins.NotifyNotica,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'notica://z...z/',
    }),
    # Token specified
    ('notica://%s' % ('a' * 6), {
        'instance': plugins.NotifyNotica,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'notica://a...a/',
    }),
    # Self-Hosted configuration
    ('notica://localhost/%s' % ('b' * 6), {
        'instance': plugins.NotifyNotica,
    }),
    ('notica://user@localhost/%s' % ('c' * 6), {
        'instance': plugins.NotifyNotica,
    }),
    ('notica://user:pass@localhost/%s/' % ('d' * 6), {
        'instance': plugins.NotifyNotica,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'notica://user:****@localhost/d...d',
    }),
    ('notica://user:pass@localhost/a/path/%s/' % ('r' * 6), {
        'instance': plugins.NotifyNotica,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'notica://user:****@localhost/a/path/r...r',
    }),
    ('notica://localhost:8080/%s' % ('a' * 6), {
        'instance': plugins.NotifyNotica,
    }),
    ('notica://user:pass@localhost:8080/%s' % ('b' * 6), {
        'instance': plugins.NotifyNotica,
    }),
    ('noticas://localhost/%s' % ('j' * 6), {
        'instance': plugins.NotifyNotica,
        'privacy_url': 'noticas://localhost/j...j',
    }),
    ('noticas://user:pass@localhost/%s' % ('e' * 6), {
        'instance': plugins.NotifyNotica,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'noticas://user:****@localhost/e...e',
    }),
    ('noticas://localhost:8080/path/%s' % ('5' * 6), {
        'instance': plugins.NotifyNotica,
        'privacy_url': 'noticas://localhost:8080/path/5...5',
    }),
    ('noticas://user:pass@localhost:8080/%s' % ('6' * 6), {
        'instance': plugins.NotifyNotica,
    }),
    ('notica://%s' % ('b' * 6), {
        'instance': plugins.NotifyNotica,
        # don't include an image by default
        'include_image': False,
    }),
    # Test Header overrides
    ('notica://localhost:8080//%s/?+HeaderKey=HeaderValue' % ('7' * 6), {
        'instance': plugins.NotifyNotica,
    }),
    ('notica://%s' % ('c' * 6), {
        'instance': plugins.NotifyNotica,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('notica://%s' % ('d' * 7), {
        'instance': plugins.NotifyNotica,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('notica://%s' % ('e' * 8), {
        'instance': plugins.NotifyNotica,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_notica_urls():
    """
    NotifyNotica() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()
