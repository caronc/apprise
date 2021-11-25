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
    ('gotify://', {
        'instance': None,
    }),
    # No token specified
    ('gotify://hostname', {
        'instance': TypeError,
    }),
    # Provide a hostname and token
    ('gotify://hostname/%s' % ('t' * 16), {
        'instance': plugins.NotifyGotify,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'gotify://hostname/t...t',
    }),
    # Provide a hostname, path, and token
    ('gotify://hostname/a/path/ending/in/a/slash/%s' % ('u' * 16), {
        'instance': plugins.NotifyGotify,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'gotify://hostname/a/path/ending/in/a/slash/u...u/',
    }),
    # Markdown test
    ('gotify://hostname/%s?format=markdown' % ('t' * 16), {
        'instance': plugins.NotifyGotify,
    }),
    # Provide a hostname, path, and token
    ('gotify://hostname/a/path/not/ending/in/a/slash/%s' % ('v' * 16), {
        'instance': plugins.NotifyGotify,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'gotify://hostname/a/path/not/ending/in/a/slash/v...v/',
    }),
    # Provide a priority
    ('gotify://hostname/%s?priority=high' % ('i' * 16), {
        'instance': plugins.NotifyGotify,
    }),
    # Provide an invalid priority
    ('gotify://hostname:8008/%s?priority=invalid' % ('i' * 16), {
        'instance': plugins.NotifyGotify,
    }),
    # An invalid url
    ('gotify://:@/', {
        'instance': None,
    }),
    ('gotify://hostname/%s/' % ('t' * 16), {
        'instance': plugins.NotifyGotify,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('gotifys://localhost/%s/' % ('t' * 16), {
        'instance': plugins.NotifyGotify,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('gotify://localhost/%s/' % ('t' * 16), {
        'instance': plugins.NotifyGotify,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_gotify_urls():
    """
    NotifyGotify() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


def test_plugin_gotify_edge_cases():
    """
    NotifyGotify() Edge Cases

    """
    # Initializes the plugin with an invalid token
    with pytest.raises(TypeError):
        plugins.NotifyGotify(token=None)
    # Whitespace also acts as an invalid token value
    with pytest.raises(TypeError):
        plugins.NotifyGotify(token="   ")
