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
    ('d7sms://', {
        # We failed to identify any valid authentication
        'instance': TypeError,
    }),
    ('d7sms://:@/', {
        # We failed to identify any valid authentication
        'instance': TypeError,
    }),
    ('d7sms://user:pass@{}/{}/{}'.format('1' * 9, '2' * 15, 'a' * 13), {
        # No valid targets to notify
        'instance': plugins.NotifyD7Networks,
        # Since there are no targets specified we expect a False return on
        # send()
        'notify_response': False,
    }),
    ('d7sms://user:pass@{}?batch=yes'.format('3' * 14), {
        # valid number
        'instance': plugins.NotifyD7Networks,
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'd7sms://user:****@',
    }),
    ('d7sms://user:pass@{}?batch=yes'.format('7' * 14), {
        # valid number
        'instance': plugins.NotifyD7Networks,
        # Test what happens if a batch send fails to return a messageCount
        'requests_response_text': {
            'data': {
                'messageCount': 0,
            },
        },
        # Expected notify() response
        'notify_response': False,
    }),
    ('d7sms://user:pass@{}?batch=yes&to={}'.format('3' * 14, '6' * 14), {
        # valid number
        'instance': plugins.NotifyD7Networks,
    }),
    ('d7sms://user:pass@{}?batch=yes&from=apprise'.format('3' * 14), {
        # valid number, utilizing the optional from= variable
        'instance': plugins.NotifyD7Networks,
    }),
    ('d7sms://user:pass@{}?batch=yes&source=apprise'.format('3' * 14), {
        # valid number, utilizing the optional source= variable (same as from)
        'instance': plugins.NotifyD7Networks,
    }),
    ('d7sms://user:pass@{}?priority=invalid'.format('3' * 14), {
        # valid number; invalid priority
        'instance': plugins.NotifyD7Networks,
    }),
    ('d7sms://user:pass@{}?priority=3'.format('3' * 14), {
        # valid number; adjusted priority
        'instance': plugins.NotifyD7Networks,
    }),
    ('d7sms://user:pass@{}?priority=high'.format('3' * 14), {
        # valid number; adjusted priority (string supported)
        'instance': plugins.NotifyD7Networks,
    }),
    ('d7sms://user:pass@{}?batch=no'.format('3' * 14), {
        # valid number - no batch
        'instance': plugins.NotifyD7Networks,
    }),
    ('d7sms://user:pass@{}'.format('3' * 14), {
        'instance': plugins.NotifyD7Networks,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('d7sms://user:pass@{}'.format('3' * 14), {
        'instance': plugins.NotifyD7Networks,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_d7networks_urls():
    """
    NotifyD7Networks() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()
