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
    ('parsep://', {
        'instance': None,
    }),
    # API Key + bad url
    ('parsep://:@/', {
        'instance': None,
    }),
    # APIkey; no app_id or master_key
    ('parsep://%s' % ('a' * 32), {
        'instance': TypeError,
    }),
    # APIkey; no master_key
    ('parsep://app_id@%s' % ('a' * 32), {
        'instance': TypeError,
    }),
    # APIkey; no app_id
    ('parseps://:master_key@%s' % ('a' * 32), {
        'instance': TypeError,
    }),
    # app_id + master_key (using arguments=)
    ('parseps://localhost?app_id=%s&master_key=%s' % ('a' * 32, 'd' * 32), {
        'instance': plugins.NotifyParsePlatform,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'parseps://a...a:d...d@localhost',
    }),
    # Set a device id + custom port
    ('parsep://app_id:master_key@localhost:8080?device=ios', {
        'instance': plugins.NotifyParsePlatform,
    }),
    # invalid device id
    ('parsep://app_id:master_key@localhost?device=invalid', {
        'instance': TypeError,
    }),
    # Normal Query
    ('parseps://app_id:master_key@localhost', {
        'instance': plugins.NotifyParsePlatform,
    }),
    ('parseps://app_id:master_key@localhost', {
        'instance': plugins.NotifyParsePlatform,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('parseps://app_id:master_key@localhost', {
        'instance': plugins.NotifyParsePlatform,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('parseps://app_id:master_key@localhost', {
        'instance': plugins.NotifyParsePlatform,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_parse_platform_urls():
    """
    NotifyParsePlatform() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()
