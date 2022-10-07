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
from unittest import mock

import pytest
import requests
import apprise
from apprise import plugins
from apprise.plugins.NotifyGotify import GotifyPriority
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


@mock.patch('requests.post')
def test_plugin_gotify_config_files(mock_post):
    """
    NotifyGotify() Config File Cases
    """
    content = """
    urls:
      - gotify://hostname/%s:
          - priority: 0
            tag: gotify_int low
          - priority: "0"
            tag: gotify_str_int low
          # We want to make sure our '1' does not match the '10' entry
          - priority: "1"
            tag: gotify_str_int low
          - priority: low
            tag: gotify_str low

          # This will take on moderate (default) priority
          - priority: invalid
            tag: gotify_invalid

      - gotify://hostname/%s:
          - priority: 10
            tag: gotify_int emerg
          - priority: "10"
            tag: gotify_str_int emerg
          - priority: emergency
            tag: gotify_str emerg
    """ % ('a' * 16, 'b' * 16)

    # Disable Throttling to speed testing
    plugins.NotifyGotify.request_rate_per_sec = 0

    # Prepare Mock
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok

    # Create ourselves a config object
    ac = apprise.AppriseConfig()
    assert ac.add_config(content=content) is True

    aobj = apprise.Apprise()

    # Add our configuration
    aobj.add(ac)

    # We should be able to read our 8 servers from that
    # 4x low
    # 3x emerg
    # 1x invalid (so takes on normal priority)
    assert len(ac.servers()) == 8
    assert len(aobj) == 8
    assert len([x for x in aobj.find(tag='low')]) == 4
    for s in aobj.find(tag='low'):
        assert s.priority == GotifyPriority.LOW

    assert len([x for x in aobj.find(tag='emerg')]) == 3
    for s in aobj.find(tag='emerg'):
        assert s.priority == GotifyPriority.EMERGENCY

    assert len([x for x in aobj.find(tag='gotify_str')]) == 2
    assert len([x for x in aobj.find(tag='gotify_str_int')]) == 3
    assert len([x for x in aobj.find(tag='gotify_int')]) == 2

    assert len([x for x in aobj.find(tag='gotify_invalid')]) == 1
    assert next(aobj.find(tag='gotify_invalid')).priority == \
        GotifyPriority.NORMAL
