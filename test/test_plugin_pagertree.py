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

from apprise.plugins.NotifyPagerTree import NotifyPagerTree
from helpers import AppriseURLTester

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# a test UUID we can use
INTEGRATION_ID = 'int_xxxxxxxxxxx'

# Our Testing URLs
apprise_url_tests = (
    ('pagertree://', {
        # Missing Integration ID
        'instance': TypeError,
    }),
    # Invalid Integration ID
    ('pagertree://%s' % ('+' * 24), {
        'instance': TypeError,
    }),
    # Minimum requirements met
    ('pagertree://%s' % INTEGRATION_ID, {
        'instance': NotifyPagerTree,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'pagertree://i...x?',
    }),
    # change the integration id
    ('pagertree://%s?integration_id=int_yyyyyyyyyy' % INTEGRATION_ID, {
        'instance': NotifyPagerTree,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'pagertree://i...y?',
    }),
    # Integration ID + bad url
    ('pagertree://:@/', {
        'instance': TypeError,
    }),
    ('pagertree://%s' % INTEGRATION_ID, {
        'instance': NotifyPagerTree,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('pagertree://%s' % INTEGRATION_ID, {
        'instance': NotifyPagerTree,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('pagertree://%s' % INTEGRATION_ID, {
        'instance': NotifyPagerTree,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
    ('pagertree://%s?urgency=low' % INTEGRATION_ID, {
        # urgency override
        'instance': NotifyPagerTree,
    }),
    ('pagertree://%s?tags=production,web' % INTEGRATION_ID, {
        # tags
        'instance': NotifyPagerTree,
    }),
    ('pagertree://%s?action=resolve&thirdparty_id=123' % INTEGRATION_ID, {
        # urgency override
        'instance': NotifyPagerTree,
    }),
    # Custom values
    ('pagertree://%s?+pagertree-token=123&:env=prod&-m=v' % INTEGRATION_ID, {
        # minimum requirements and support custom key/value pairs
        'instance': NotifyPagerTree,
    }),
)


def test_plugin_pagertree_urls():
    """
    NotifyPagerTree() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()
