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

# a test UUID we can use
UUID4 = '8b799edf-6f98-4d3a-9be7-2862fb4e5752'

# Our Testing URLs
apprise_url_tests = (
    ('push://', {
        # Missing API Key
        'instance': TypeError,
    }),
    # Invalid API Key
    ('push://%s' % ('+' * 24), {
        'instance': TypeError,
    }),
    # APIkey
    ('push://%s' % UUID4, {
        'instance': plugins.NotifyTechulusPush,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'push://8...2/',
    }),
    # API Key + bad url
    ('push://:@/', {
        'instance': TypeError,
    }),
    ('push://%s' % UUID4, {
        'instance': plugins.NotifyTechulusPush,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('push://%s' % UUID4, {
        'instance': plugins.NotifyTechulusPush,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('push://%s' % UUID4, {
        'instance': plugins.NotifyTechulusPush,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_techulus_push_urls():
    """
    NotifyTechulusPush() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()
