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
    ('octopush://', {
        # No API Login or API Key specified
        'instance': TypeError,
    }),
    ('octopush://:@/', {
        # invalid API Login
        'instance': TypeError,
    }),
    ('octopush://user@myaccount.com', {
        # Valid API Login, but no API Key provided
        'instance': TypeError,
    }),
    ('octopush://_/apikey?login=invalid', {
        # Invalid login
        'instance': TypeError,
    }),
    ('octopush://user@myaccount.com/%20', {
        # Valid API Login, but invalid API Key provided
        'instance': TypeError,
    }),
    ('octopush://%20:user@myaccount.com/apikey', {
        # All valid entries, but invalid sender
        'instance': TypeError,
    }),
    ('octopush://user@myaccount.com/apikey', {
        # All valid entries, but no target phone numbers defined
        'instance': plugins.NotifyOctopush.NotifyOctopush,
        'response': False,
    }),
    ('octopush://user@myaccount.com/apikey/+0987654321', {
        # A valid url
        'instance': plugins.NotifyOctopush.NotifyOctopush,
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'octopush://u...m/****/+0987654321',
    }),
    ('octopush://sender:user@myaccount.com/apikey/+1111111111', {
        # A valid url with sender
        'instance': plugins.NotifyOctopush.NotifyOctopush,
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'octopush://sender:u...m/****/+1111111111',
    }),
    ('octopush://?login=user@myaccount.com&key=key&to=9999999999'
        '&purpose=wholesale', {
            # Testing valid purpose change
            'instance': plugins.NotifyOctopush.NotifyOctopush}),
    ('octopush://?login=user@myaccount.com&key=key&to=9999999999'
        '&purpose=invalid', {
            # Testing invalid purpose change
            'instance': TypeError}),
    ('octopush://?login=user@myaccount.com&key=key&to=9999999999'
        '&type=premium', {
            # Testing valid type change
            'instance': plugins.NotifyOctopush.NotifyOctopush}),
    ('octopush://?login=user@myaccount.com&key=key&to=9999999999'
        '&type=invalid', {
            # Testing invalid type change
            'instance': TypeError}),
    ('octopush://user@myaccount.com/apikey/+3333333333?replies=yes', {
        # Test replies
        'instance': plugins.NotifyOctopush.NotifyOctopush,
    }),
    ('octopush://sender:user@myaccount.com/apikey/{}/{}/{}/?batch=yes'.format(
        '1' * 10, '2' * 3, '3' * 11), {
            # batch mode, 2 valid targets (1 is invalid and skipped)
            'instance': plugins.NotifyOctopush.NotifyOctopush}),
    ('octopush://_?key=abc123&login=user@myaccount&sender=abc&to=2222222222', {
        # use get args to acomplish the same thing
        'instance': plugins.NotifyOctopush.NotifyOctopush,
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'octopush://abc:u...t/****/+2222222222',
    }),
    ('octopush://user@myaccount.com/apikey/1234567890', {
        'instance': plugins.NotifyOctopush.NotifyOctopush,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('octopush://user@myaccount.com/apikey/1234567890', {
        'instance': plugins.NotifyOctopush.NotifyOctopush,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_octopush_urls():
    """
    NotifyOctopush() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()
