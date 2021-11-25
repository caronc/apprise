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
    ('kavenegar://', {
        # We failed to identify any valid authentication
        'instance': TypeError,
    }),
    ('kavenegar://:@/', {
        # We failed to identify any valid authentication
        'instance': TypeError,
    }),
    ('kavenegar://{}/{}/{}'.format('1' * 10, '2' * 15, 'a' * 13), {
        # valid api key and valid authentication
        'instance': plugins.NotifyKavenegar,
        # Since there are no targets specified we expect a False return on
        # send()
        'notify_response': False,
    }),
    ('kavenegar://{}/{}'.format('a' * 24, '3' * 14), {
        # valid api key and valid number
        'instance': plugins.NotifyKavenegar,
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'kavenegar://a...a/',
    }),
    ('kavenegar://{}?to={}'.format('a' * 24, '3' * 14), {
        # valid api key and valid number
        'instance': plugins.NotifyKavenegar,
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'kavenegar://a...a/',
    }),
    ('kavenegar://{}@{}/{}'.format('1' * 14, 'b' * 24, '3' * 14), {
        # valid api key and valid number
        'instance': plugins.NotifyKavenegar,
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'kavenegar://{}@b...b/'.format('1' * 14),
    }),
    ('kavenegar://{}@{}/{}'.format('a' * 14, 'b' * 24, '3' * 14), {
        # invalid from number
        'instance': TypeError,
    }),
    ('kavenegar://{}@{}/{}'.format('3' * 4, 'b' * 24, '3' * 14), {
        # invalid from number
        'instance': TypeError,
    }),
    ('kavenegar://{}/{}?from={}'.format('b' * 24, '3' * 14, '1' * 14), {
        # valid api key and valid number
        'instance': plugins.NotifyKavenegar,
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'kavenegar://{}@b...b/'.format('1' * 14),
    }),
    ('kavenegar://{}/{}'.format('b' * 24, '4' * 14), {
        'instance': plugins.NotifyKavenegar,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('kavenegar://{}/{}'.format('c' * 24, '5' * 14), {
        'instance': plugins.NotifyKavenegar,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_kavenegar_urls():
    """
    NotifyKavenegar() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()
