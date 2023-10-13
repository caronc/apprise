# -*- coding: utf-8 -*-
# BSD 2-Clause License
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

from apprise.plugins.NotifyPushMe import NotifyPushMe
from helpers import AppriseURLTester

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    ('pushme://', {
        'instance': TypeError,
    }),
    ('pushme://:@/', {
        'instance': TypeError,
    }),
    # Token specified
    ('pushme://%s' % ('a' * 6), {
        'instance': NotifyPushMe,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'pushme://a...a/',
    }),
    # Token specified
    ('pushme://?token=%s&status=yes' % ('b' * 6), {
        'instance': NotifyPushMe,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'pushme://b...b/',
    }),
    # Status setting
    ('pushme://?token=%s&status=no' % ('b' * 6), {
        'instance': NotifyPushMe,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'pushme://b...b/',
    }),
    # Status setting
    ('pushme://?token=%s&status=True' % ('b' * 6), {
        'instance': NotifyPushMe,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'pushme://b...b/',
    }),
    # Token specified
    ('pushme://?push_key=%s&status=no' % ('p' * 6), {
        'instance': NotifyPushMe,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'pushme://p...p/',
    }),
    ('pushme://%s' % ('c' * 6), {
        'instance': NotifyPushMe,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('pushme://%s' % ('d' * 7), {
        'instance': NotifyPushMe,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('pushme://%s' % ('e' * 8), {
        'instance': NotifyPushMe,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_pushme_urls():
    """
    NotifyPushMe() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()
