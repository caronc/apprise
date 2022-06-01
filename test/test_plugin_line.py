# -*- coding: utf-8 -*-
#
# Copyright (C) 2022 Chris Caron <lead2gold@gmail.com>
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
from apprise import plugins
from helpers import AppriseURLTester

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    ('line://', {
        # No Access Token
        'instance': TypeError,
    }),
    ('line://%20/', {
        # invalid Access Token; no Integration/Routing Key
        'instance': TypeError,
    }),
    ('line://token', {
        # no target specified
        'instance': plugins.NotifyLine,
        # Expected notify() response
        'notify_response': False,

    }),
    ('line://token=/target', {
        # minimum requirements met
        'instance': plugins.NotifyLine,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'line://****/t...t?',
    }),
    ('line://token/target?image=no', {
        # minimum requirements met; no icon display
        'instance': plugins.NotifyLine,
    }),
    ('line://a/very/long/token=/target?image=no', {
        # minimum requirements met; no icon display
        'instance': plugins.NotifyLine,
    }),
    ('line://?token=token&to=target1', {
        # minimum requirements met
        'instance': plugins.NotifyLine,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'line://****/t...1?',
    }),
    ('line://token/target', {
        'instance': plugins.NotifyLine,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('line://token/target', {
        'instance': plugins.NotifyLine,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_line_urls():
    """
    NotifyLine() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()
