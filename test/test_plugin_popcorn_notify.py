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

# Our Testing URLs
apprise_url_tests = (
    ('popcorn://', {
        # No hostname/apikey specified
        'instance': TypeError,
    }),
    ('popcorn://{}/18001231234'.format('_' * 9), {
        # invalid apikey
        'instance': TypeError,
    }),
    ('popcorn://{}/1232348923489234923489234289-32423'.format('a' * 9), {
        # invalid phone number
        'instance': plugins.NotifyPopcornNotify,
        'notify_response': False,
    }),
    ('popcorn://{}/abc'.format('b' * 9), {
        # invalid email
        'instance': plugins.NotifyPopcornNotify,
        'notify_response': False,
    }),
    ('popcorn://{}/15551232000/user@example.com'.format('c' * 9), {
        # value phone and email
        'instance': plugins.NotifyPopcornNotify,
    }),
    ('popcorn://{}/15551232000/user@example.com?batch=yes'.format('w' * 9), {
        # value phone and email with batch mode set
        'instance': plugins.NotifyPopcornNotify,
    }),
    ('popcorn://{}/?to=15551232000'.format('w' * 9), {
        # reference to to=
        'instance': plugins.NotifyPopcornNotify,
    }),
    ('popcorn://{}/15551232000'.format('x' * 9), {
        'instance': plugins.NotifyPopcornNotify,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('popcorn://{}/15551232000'.format('y' * 9), {
        'instance': plugins.NotifyPopcornNotify,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('popcorn://{}/15551232000'.format('z' * 9), {
        'instance': plugins.NotifyPopcornNotify,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_popcorn_notify_urls():
    """
    NotifyPopcornNotify() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()
