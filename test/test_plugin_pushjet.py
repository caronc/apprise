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
    ('pjet://', {
        'instance': None,
    }),
    ('pjets://', {
        'instance': None,
    }),
    ('pjet://:@/', {
        'instance': None,
    }),
    #  You must specify a secret key
    ('pjet://%s' % ('a' * 32), {
        'instance': TypeError,
    }),
    # The proper way to log in
    ('pjet://user:pass@localhost/%s' % ('a' * 32), {
        'instance': plugins.NotifyPushjet,
    }),
    # The proper way to log in
    ('pjets://localhost/%s' % ('a' * 32), {
        'instance': plugins.NotifyPushjet,
    }),
    # Specify your own server with login (secret= MUST be provided)
    ('pjet://user:pass@localhost?secret=%s' % ('a' * 32), {
        'instance': plugins.NotifyPushjet,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'pjet://user:****@localhost',
    }),
    # Specify your own server with port
    ('pjets://localhost:8080/%s' % ('a' * 32), {
        'instance': plugins.NotifyPushjet,
    }),
    ('pjets://localhost:8080/%s' % ('a' * 32), {
        'instance': plugins.NotifyPushjet,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('pjets://localhost:4343/%s' % ('a' * 32), {
        'instance': plugins.NotifyPushjet,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('pjet://localhost:8081/%s' % ('a' * 32), {
        'instance': plugins.NotifyPushjet,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_pushjet_urls():
    """
    NotifyPushjet() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


def test_plugin_pushjet_edge_cases():
    """
    NotifyPushjet() Edge Cases

    """
    # Disable Throttling to speed testing
    plugins.NotifyBase.request_rate_per_sec = 0

    # No application Key specified
    with pytest.raises(TypeError):
        plugins.NotifyPushjet(secret_key=None)

    with pytest.raises(TypeError):
        plugins.NotifyPushjet(secret_key="  ")
