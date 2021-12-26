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
    ('dapnet://user:pass@{}'.format('DF1ABC'), {
        # valid call sign
        'instance': plugins.NotifyDapnet,
        'response': False,
        'requests_response_code': requests.codes.ok,
    }),
    ('dapnet://user:pass@{}/{}'.format('DF1ABC', 'DF1DEF'), {
        # valid call signs
        'instance': plugins.NotifyDapnet,
        'response': False,
        'requests_response_code': requests.codes.ok,
    }),
    ('dapnet://user:pass@{}?priority=normal'.format('DF1ABC'), {
        # valid call sign with priority
        'instance': plugins.NotifyDapnet,
        'response': False,
        'requests_response_code': requests.codes.ok,
    }),
    ('dapnet://user:pass@{}?transmittergroups=dl-all,all'.format('DF1ABC'), {
        # valid call sign with two transmitter groups
        'instance': plugins.NotifyDapnet,
        'response': False,
        'requests_response_code': requests.codes.ok,
    }),
    ('dapnet://user:pass@{}/{}/{}'.format('abcdefghi', 'a', '0A1DEF'), {
        # invalid call signs
        'instance': plugins.NotifyDapnet,
        'notify_response': False,
    })
)


def test_plugin_dapnet_urls():
    """
    NotifyDapnet() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()
