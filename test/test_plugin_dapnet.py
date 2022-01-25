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
# Disable logging for a cleaner testing output
import logging
import requests

from apprise import plugins
from helpers import AppriseURLTester

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    ('dapnet://', {
        # We failed to identify any valid authentication
        'instance': TypeError,
    }),
    ('dapnet://:@/', {
        # We failed to identify any valid authentication
        'instance': TypeError,
    }),
    ('dapnet://user:pass', {
        # No call-sign specified
        'instance': TypeError,
    }),
    ('dapnet://user@host', {
        # No password specified
        'instance': TypeError,
    }),
    ('dapnet://user:pass@{}'.format('DF1ABC'), {
        # valid call sign
        'instance': plugins.NotifyDapnet,
        'requests_response_code': requests.codes.created,
    }),
    ('dapnet://user:pass@{}/{}'.format('DF1ABC', 'DF1DEF'), {
        # valid call signs
        'instance': plugins.NotifyDapnet,
        'requests_response_code': requests.codes.created,
    }),
    ('dapnet://user:pass@DF1ABC-1/DF1ABC/DF1ABC-15', {
        # valid call signs; but a few are duplicates;
        # at the end there will only be 1 entry
        'instance': plugins.NotifyDapnet,
        'requests_response_code': requests.codes.created,
        # Our expected url(privacy=True) startswith() response:
        # Note that only 1 entry is saved (as other 2 are duplicates)
        'privacy_url': 'dapnet://user:****@D...C?',
    }),
    ('dapnet://user:pass@?to={},{}'.format('DF1ABC', 'DF1DEF'), {
        # support the to= argument
        'instance': plugins.NotifyDapnet,
        'requests_response_code': requests.codes.created,
    }),
    ('dapnet://user:pass@{}?priority=normal'.format('DF1ABC'), {
        # valid call sign with priority
        'instance': plugins.NotifyDapnet,
        'requests_response_code': requests.codes.created,
    }),
    ('dapnet://user:pass@{}?priority=em&batch=false'.format(
        '/'.join(['DF1ABC', '0A1DEF'])), {
            # valid call sign with priority (emergency) + no batch
            # transmissions
            'instance': plugins.NotifyDapnet,
            'requests_response_code': requests.codes.created,
    }),
    ('dapnet://user:pass@{}?priority=invalid'.format('DF1ABC'), {
        # invalid priority
        'instance': plugins.NotifyDapnet,
        'requests_response_code': requests.codes.created,
    }),
    ('dapnet://user:pass@{}?txgroups=dl-all,all'.format('DF1ABC'), {
        # valid call sign with two transmitter groups
        'instance': plugins.NotifyDapnet,
        'requests_response_code': requests.codes.created,
    }),
    ('dapnet://user:pass@{}?txgroups=invalid'.format('DF1ABC'), {
        # valid call sign with invalid transmitter group
        'instance': plugins.NotifyDapnet,
        'requests_response_code': requests.codes.created,
    }),
    ('dapnet://user:pass@{}/{}'.format('abcdefghi', 'a'), {
        # invalid call signs
        'instance': plugins.NotifyDapnet,
        'notify_response': False,
    }),
    # Edge cases
    ('dapnet://user:pass@{}'.format('DF1ABC'), {
        'instance': plugins.NotifyDapnet,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('dapnet://user:pass@{}'.format('DF1ABC'), {
        'instance': plugins.NotifyDapnet,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_dapnet_urls():
    """
    NotifyDapnet() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()
