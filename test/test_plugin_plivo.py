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
from apprise.plugins.NotifyPlivo import NotifyPlivo
from helpers import AppriseURLTester

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    ('plivo://', {
        # No hostname/apikey specified
        'instance': None,
    }),
    ('plivo://{}@{}/15551232000'.format('a' * 10, 'a' * 25), {
        # invalid auth id
        'instance': TypeError,
    }),
    ('plivo://{}@{}/15551232000'.format('a' * 25, 'a' * 10), {
        # invalid token
        'instance': TypeError,
    }),
    ('plivo://{}@{}/123'.format('a' * 25, 'a' * 25), {
        # invalid phone number
        'instance': TypeError,
    }),
    ('plivo://{}@{}/abc'.format('a' * 25, 'a' * 25), {
        # invalid phone number
        'instance': TypeError,
    }),
    ('plivo://{}@{}/15551232000'.format('a' * 25, 'a' * 25), {
        # target phone number becomes who we text too; all is good
        'instance': NotifyPlivo,
    }),
    ('plivo://{}@{}/15551232000/abcd'.format('a' * 25, 'a' * 25), {
        # invalid target phone number; we fall back to texting ourselves
        'instance': NotifyPlivo,
    }),
    ('plivo://{}@{}/15551232000/123'.format('a' * 25, 'a' * 25), {
        # invalid target phone number; we fall back to texting ourselves
        'instance': NotifyPlivo,
    }),
    ('plivo://{}@{}/?from=15551233000&to=15551232000'.format(
        'a' * 25, 'a' * 25), {
            # reference to to= and frome=
            'instance': NotifyPlivo,
    }),
    ('plivo://{}@{}/15551232000'.format('a' * 25, 'a' * 25), {
        'instance': NotifyPlivo,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('plivo://{}@{}/15551232000'.format('a' * 25, 'a' * 25), {
        'instance': NotifyPlivo,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_plivo_urls():
    """
    NotifyPlivo() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()
