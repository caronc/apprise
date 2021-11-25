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
from apprise import plugins
from helpers import AppriseURLTester

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    ('dingtalk://', {
        # No Access Token specified
        'instance': TypeError,
    }),
    ('dingtalk://a_bd_/', {
        # invalid Access Token
        'instance': TypeError,
    }),
    ('dingtalk://12345678', {
        # access token
        'instance': plugins.NotifyDingTalk,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'dingtalk://1...8',
    }),
    ('dingtalk://{}/{}'.format('a' * 8, '1' * 14), {
        # access token + phone number
        'instance': plugins.NotifyDingTalk,
    }),
    ('dingtalk://{}/{}/invalid'.format('a' * 8, '1' * 3), {
        # access token + 2 invalid phone numbers
        'instance': plugins.NotifyDingTalk,
    }),
    ('dingtalk://{}/?to={}'.format('a' * 8, '1' * 14), {
        # access token + phone number using 'to'
        'instance': plugins.NotifyDingTalk,
    }),
    # Test secret via user@
    ('dingtalk://secret@{}/?to={}'.format('a' * 8, '1' * 14), {
        # access token + phone number using 'to'
        'instance': plugins.NotifyDingTalk,
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'dingtalk://****@a...a',
    }),
    # Test secret via secret= and token=
    ('dingtalk://?token={}&to={}&secret={}'.format(
        'b' * 8, '1' * 14, 'a' * 15), {
            # access token + phone number using 'to'
            'instance': plugins.NotifyDingTalk,
        'privacy_url': 'dingtalk://****@b...b',
    }),
    # Invalid secret
    ('dingtalk://{}/?to={}&secret=_'.format('a' * 8, '1' * 14), {
        'instance': TypeError,
    }),
    ('dingtalk://{}?format=markdown'.format('a' * 8), {
        # access token
        'instance': plugins.NotifyDingTalk,
    }),
    ('dingtalk://{}'.format('a' * 8), {
        'instance': plugins.NotifyDingTalk,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('dingtalk://{}'.format('a' * 8), {
        'instance': plugins.NotifyDingTalk,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_dingtalk_urls():
    """
    NotifyDingTalk() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()
