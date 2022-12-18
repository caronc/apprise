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
from apprise.plugins.NotifyD7Networks import NotifyD7Networks
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
    ('d7sms://token@{}/{}/{}'.format('1' * 9, '2' * 15, 'a' * 13), {
        # No valid targets to notify
        'instance': NotifyD7Networks,
        # Since there are no targets specified we expect a False return on
        # send()
        'notify_response': False,
    }),
    ('d7sms://token1@{}?batch=yes'.format('3' * 14), {
        # valid number
        'instance': NotifyD7Networks,
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'd7sms://t...1@',
    }),
    ('d7sms://token:colon2@{}?batch=yes'.format('3' * 14), {
        # valid number - token containing a colon
        'instance': NotifyD7Networks,
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'd7sms://t...2@',
    }),
    ('d7sms://:token3@{}?batch=yes'.format('3' * 14), {
        # valid number - token starting wit a colon
        'instance': NotifyD7Networks,
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'd7sms://:...3@',
    }),
    ('d7sms://{}?token=token6'.format('3' * 14), {
        # valid number - token starting wit a colon
        'instance': NotifyD7Networks,
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'd7sms://t...6@',
    }),
    ('d7sms://token4@{}?unicode=no'.format('3' * 14), {
        # valid number - test unicode
        'instance': NotifyD7Networks,
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'd7sms://t...4@',
    }),
    ('d7sms://token@{}?batch=yes'.format('7' * 14), {
        # valid number
        'instance': NotifyD7Networks,
        # Test what happens if a batch send fails to return a messageCount
        'requests_response_text': {
            'data': {
                'messageCount': 0,
            },
        },
        # Expected notify() response
        'notify_response': False,
    }),
    ('d7sms://token@{}?batch=yes&to={}'.format('3' * 14, '6' * 14), {
        # valid number
        'instance': NotifyD7Networks,
    }),
    ('d7sms://token@{}?batch=yes&from=apprise'.format('3' * 14), {
        # valid number, utilizing the optional from= variable
        'instance': NotifyD7Networks,
    }),
    ('d7sms://token@{}?batch=yes&source=apprise'.format('3' * 14), {
        # valid number, utilizing the optional source= variable (same as from)
        'instance': NotifyD7Networks,
    }),
    ('d7sms://token@{}?batch=no'.format('3' * 14), {
        # valid number - no batch
        'instance': NotifyD7Networks,
    }),
    ('d7sms://token@{}'.format('3' * 14), {
        'instance': NotifyD7Networks,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('d7sms://token@{}'.format('3' * 14), {
        'instance': NotifyD7Networks,
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
