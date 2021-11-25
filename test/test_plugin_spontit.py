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
    ('spontit://', {
        # invalid url
        'instance': TypeError,
    }),
    # Another bad url
    ('spontit://:@/', {
        'instance': TypeError,
    }),
    # No user specified
    ('spontit://%s' % ('a' * 100), {
        'instance': TypeError,
    }),
    # Invalid API Key specified
    ('spontit://user@%%20_', {
        'instance': TypeError,
    }),
    # Provide a valid user and API Key
    ('spontit://%s@%s' % ('u' * 11, 'b' * 100), {
        'instance': plugins.NotifySpontit,
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'spontit://{}@b...b/'.format('u' * 11),
    }),
    # Provide a valid user and API Key, but provide an invalid channel
    ('spontit://%s@%s/#!!' % ('u' * 11, 'b' * 100), {
        # An instance is still created, but the channel won't be notified
        'instance': plugins.NotifySpontit,
    }),
    # Provide a valid user, API Key and a valid channel
    ('spontit://%s@%s/#abcd' % ('u' * 11, 'b' * 100), {
        'instance': plugins.NotifySpontit,
    }),
    # Provide a valid user, API Key, and a subtitle
    ('spontit://%s@%s/?subtitle=Test' % ('u' * 11, 'b' * 100), {
        'instance': plugins.NotifySpontit,
    }),
    # Provide a valid user, API Key, and a lengthy subtitle
    ('spontit://%s@%s/?subtitle=%s' % ('u' * 11, 'b' * 100, 'c' * 300), {
        'instance': plugins.NotifySpontit,
    }),
    # Provide a valid user and API Key, but provide a valid channel (that is
    # not ours).
    # Spontit uses a slash (/) to delimite the user from the channel id when
    # specifying channel entries. For Apprise we need to encode this
    # so we convert the slash (/) into %2F
    ('spontit://{}@{}/#1245%2Fabcd'.format('u' * 11, 'b' * 100), {
        'instance': plugins.NotifySpontit,
    }),
    # Provide multipe channels
    ('spontit://{}@{}/#1245%2Fabcd/defg'.format('u' * 11, 'b' * 100), {
        'instance': plugins.NotifySpontit,
    }),
    # Provide multipe channels through the use of the to= variable
    ('spontit://{}@{}/?to=#1245/abcd'.format('u' * 11, 'b' * 100), {
        'instance': plugins.NotifySpontit,
    }),
    ('spontit://%s@%s' % ('u' * 11, 'b' * 100), {
        'instance': plugins.NotifySpontit,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('spontit://%s@%s' % ('u' * 11, 'b' * 100), {
        'instance': plugins.NotifySpontit,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('spontit://%s@%s' % ('u' * 11, 'b' * 100), {
        'instance': plugins.NotifySpontit,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_spontit_urls():
    """
    NotifySpontit() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()
