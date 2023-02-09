# -*- coding: utf-8 -*-
# BSD 3-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2023, Chris Caron <lead2gold@gmail.com>
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# 3. Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

import requests

from apprise.plugins.NotifySpontit import NotifySpontit
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
        'instance': NotifySpontit,
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'spontit://{}@b...b/'.format('u' * 11),
    }),
    # Provide a valid user and API Key, but provide an invalid channel
    ('spontit://%s@%s/#!!' % ('u' * 11, 'b' * 100), {
        # An instance is still created, but the channel won't be notified
        'instance': NotifySpontit,
    }),
    # Provide a valid user, API Key and a valid channel
    ('spontit://%s@%s/#abcd' % ('u' * 11, 'b' * 100), {
        'instance': NotifySpontit,
    }),
    # Provide a valid user, API Key, and a subtitle
    ('spontit://%s@%s/?subtitle=Test' % ('u' * 11, 'b' * 100), {
        'instance': NotifySpontit,
    }),
    # Provide a valid user, API Key, and a lengthy subtitle
    ('spontit://%s@%s/?subtitle=%s' % ('u' * 11, 'b' * 100, 'c' * 300), {
        'instance': NotifySpontit,
    }),
    # Provide a valid user and API Key, but provide a valid channel (that is
    # not ours).
    # Spontit uses a slash (/) to delimite the user from the channel id when
    # specifying channel entries. For Apprise we need to encode this
    # so we convert the slash (/) into %2F
    ('spontit://{}@{}/#1245%2Fabcd'.format('u' * 11, 'b' * 100), {
        'instance': NotifySpontit,
    }),
    # Provide multipe channels
    ('spontit://{}@{}/#1245%2Fabcd/defg'.format('u' * 11, 'b' * 100), {
        'instance': NotifySpontit,
    }),
    # Provide multipe channels through the use of the to= variable
    ('spontit://{}@{}/?to=#1245/abcd'.format('u' * 11, 'b' * 100), {
        'instance': NotifySpontit,
    }),
    ('spontit://%s@%s' % ('u' * 11, 'b' * 100), {
        'instance': NotifySpontit,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('spontit://%s@%s' % ('u' * 11, 'b' * 100), {
        'instance': NotifySpontit,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('spontit://%s@%s' % ('u' * 11, 'b' * 100), {
        'instance': NotifySpontit,
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
