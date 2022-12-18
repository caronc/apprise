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

from apprise.plugins.NotifyExotel import NotifyExotel
from helpers import AppriseURLTester

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    ('exotel://', {
        # No Account SID specified
        'instance': TypeError,
    }),
    ('exotel://:@/', {
        # invalid Auth token
        'instance': TypeError,
    }),
    ('exotel://{}@12345678'.format('a' * 32), {
        # Just sid provided
        'instance': TypeError,
    }),
    ('exotel://{}:{}@_'.format('a' * 32, 'b' * 32), {
        # sid and token provided but invalid from
        'instance': TypeError,
    }),
    ('exotel://{}:{}@{}'.format('a' * 32, 'b' * 32, '3' * 8), {
        # sid and token provided and from but invalid from no
        'instance': TypeError,
    }),
    ('exotel://{}:{}@{}'.format('a' * 32, 'b' * 32, '3' * 9), {
        # sid and token provided and from
        'instance': NotifyExotel,
    }),
    ('exotel://{}:{}@{}/123/{}/abcd/'.format(
        'a' * 32, 'b' * 32, '3' * 11, '9' * 15), {
        # valid everything but target numbers
        'instance': NotifyExotel,
        # Since the targets are invalid, we'll fail to send()
        'notify_response': False,
    }),
    ('exotel://{}:{}@12345/{}'.format('a' * 32, 'b' * 32, '4' * 11), {
        # using short-code (5 characters) is not supported
        'instance': TypeError,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'exotel://...aaaa:b...b@12345',
    }),
    ('exotel://{}:{}@{}'.format('a' * 32, 'b' * 32, '5' * 11), {
        # using phone no with no target - we text ourselves in
        # this case
        'instance': NotifyExotel,
    }),
    ('exotel://_?sid={}&token={}&from={}'.format(
        'a' * 32, 'b' * 32, '5' * 11), {
        # use get args to acomplish the same thing
        'instance': NotifyExotel,
    }),
    ('exotel://_?sid={}&token={}&from={}&unicode=Yes'.format(
        'a' * 32, 'b' * 32, '5' * 11), {
        # Test unicode flag
        'instance': NotifyExotel,
    }),
    ('exotel://_?sid={}&token={}&from={}&unicode=no'.format(
        'a' * 32, 'b' * 32, '5' * 11), {
        # Test unicode flag
        'instance': NotifyExotel,
    }),
    ('exotel://_?sid={}&token={}&from={}&region=us'.format(
        'a' * 32, 'b' * 32, '5' * 11), {
        # Test region flag (Us)
        'instance': NotifyExotel,
    }),
    ('exotel://_?sid={}&token={}&from={}&region=in'.format(
        'a' * 32, 'b' * 32, '5' * 11), {
        # Test region flag (India)
        'instance': NotifyExotel,
    }),
    ('exotel://_?sid={}&token={}&from={}&region=invalid'.format(
        'a' * 32, 'b' * 32, '5' * 11), {
        # Test region flag Invalid
        'instance': TypeError,
    }),
    ('exotel://_?sid={}&token={}&from={}&priority=normal'.format(
        'a' * 32, 'b' * 32, '5' * 11), {
        # Test region flag (Us)
        'instance': NotifyExotel,
    }),
    ('exotel://_?sid={}&token={}&from={}&priority=high'.format(
        'a' * 32, 'b' * 32, '5' * 11), {
        # Test region flag (India)
        'instance': NotifyExotel,
    }),
    ('exotel://_?sid={}&token={}&from={}&priority=invalid'.format(
        'a' * 32, 'b' * 32, '5' * 11), {
        # Test region flag Invalid
        'instance': TypeError,
    }),
    ('exotel://_?sid={}&token={}&source={}'.format(
        'a' * 32, 'b' * 32, '5' * 11), {
        # use get args to acomplish the same thing (use source instead of from)
        'instance': NotifyExotel,
    }),
    ('exotel://_?sid={}&token={}&from={}&to={}'.format(
        'a' * 32, 'b' * 32, '5' * 11, '7' * 13), {
        # use to=
        'instance': NotifyExotel,
    }),
    ('exotel://{}:{}@{}'.format('a' * 32, 'b' * 32, '6' * 11), {
        'instance': NotifyExotel,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('exotel://{}:{}@{}'.format('a' * 32, 'b' * 32, '6' * 11), {
        'instance': NotifyExotel,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_exotel_urls():
    """
    NotifyExotel() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()
