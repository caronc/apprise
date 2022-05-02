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
from apprise import plugins
import requests
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
        'instance': plugins.NotifyZulip,
        'privacy_url': 'zulip://bot-name@apprise/a...a/',
    }),
    # Valid everything - no target so default is used
    ('zulip://botname@apprise/{}'.format('a' * 32), {
        'instance': plugins.NotifyZulip,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'zulip://botname@apprise/a...a/',
    }),
    # Valid everything - organization as hostname
    ('zulip://botname@apprise.zulipchat.com/{}'.format('a' * 32), {
        'instance': plugins.NotifyZulip,
    }),
    # Valid everything - 2 streams specified
    ('zulip://botname@apprise/{}/channel1/channel2'.format('a' * 32), {
        'instance': plugins.NotifyZulip,
    }),
    # Valid everything - 2 streams specified (using to=)
    ('zulip://botname@apprise/{}/?to=channel1/channel2'.format('a' * 32), {
        'instance': plugins.NotifyZulip,
    }),
    # Valid everything - 2 emails specified
    ('zulip://botname@apprise/{}/user@example.com/user2@example.com'.format(
        'a' * 32), {
        'instance': plugins.NotifyZulip,
    }),
    ('zulip://botname@apprise/{}'.format('a' * 32), {
        'instance': plugins.NotifyZulip,
        # don't include an image by default
        'include_image': False,
    }),
    ('zulip://botname@apprise/{}'.format('a' * 32), {
        'instance': plugins.NotifyZulip,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('zulip://botname@apprise/{}'.format('a' * 32), {
        'instance': plugins.NotifyZulip,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('zulip://botname@apprise/{}'.format('a' * 32), {
        'instance': plugins.NotifyZulip,
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
    # Disable Throttling to speed testing
    plugins.NotifyBase.request_rate_per_sec = 0

    # must be 32 characters long
    token = 'a' * 32

    # Invalid organization
    with pytest.raises(TypeError):
        plugins.NotifyZulip(
            botname='test', organization='#', token=token)
