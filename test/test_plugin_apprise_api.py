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
from helpers import AppriseURLTester
from apprise import plugins
import requests

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    ('apprise://', {
        # invalid url (not complete)
        'instance': None,
    }),
    # A a bad url
    ('apprise://:@/', {
        'instance': None,
    }),
    # No token specified
    ('apprise://localhost', {
        'instance': TypeError,
    }),
    # invalid token
    ('apprise://localhost/!', {
        'instance': TypeError,
    }),
    # No token specified (whitespace is trimmed)
    ('apprise://localhost/%%20', {
        'instance': TypeError,
    }),
    # A valid URL with Token
    ('apprise://localhost/%s' % ('a' * 32), {
        'instance': plugins.NotifyAppriseAPI,
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'apprise://localhost/a...a/',
    }),
    # A valid URL with Token (using port)
    ('apprise://localhost:8080/%s' % ('b' * 32), {
        'instance': plugins.NotifyAppriseAPI,
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'apprise://localhost:8080/b...b/',
    }),
    # A secure (https://) reference
    ('apprises://localhost/%s' % ('c' * 32), {
        'instance': plugins.NotifyAppriseAPI,
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'apprises://localhost/c...c/',
    }),
    # Native URL suport (https)
    ('https://example.com/path/notify/%s' % ('d' * 32), {
        'instance': plugins.NotifyAppriseAPI,
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'apprises://example.com/path/d...d/',
    }),
    # Native URL suport (http)
    ('http://example.com/notify/%s' % ('d' * 32), {
        'instance': plugins.NotifyAppriseAPI,
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'apprise://example.com/d...d/',
    }),
    # support to= keyword
    ('apprises://localhost/?to=%s' % ('e' * 32), {
        'instance': plugins.NotifyAppriseAPI,
        'privacy_url': 'apprises://localhost/e...e/',
    }),
    # support token= keyword (even when passed with to=, token over-rides)
    ('apprise://localhost/?token=%s&to=%s' % ('f' * 32, 'abcd'), {
        'instance': plugins.NotifyAppriseAPI,
        'privacy_url': 'apprise://localhost/f...f/',
    }),
    # Test tags
    ('apprise://localhost/?token=%s&tags=admin,team' % ('abcd'), {
        'instance': plugins.NotifyAppriseAPI,
        'privacy_url': 'apprise://localhost/a...d/',
    }),
    # Test Format string
    ('apprise://user@localhost/mytoken0/?format=markdown', {
        'instance': plugins.NotifyAppriseAPI,
        'privacy_url': 'apprise://user@localhost/m...0/',
    }),
    ('apprise://user@localhost/mytoken1/', {
        'instance': plugins.NotifyAppriseAPI,
        'privacy_url': 'apprise://user@localhost/m...1/',
    }),
    ('apprise://localhost:8080/mytoken/', {
        'instance': plugins.NotifyAppriseAPI,
    }),
    ('apprise://user:pass@localhost:8080/mytoken2/', {
        'instance': plugins.NotifyAppriseAPI,
        'privacy_url': 'apprise://user:****@localhost:8080/m...2/',
    }),
    ('apprises://localhost/mytoken/', {
        'instance': plugins.NotifyAppriseAPI,
    }),
    ('apprises://user:pass@localhost/mytoken3/', {
        'instance': plugins.NotifyAppriseAPI,
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'apprises://user:****@localhost/m...3/',
    }),
    ('apprises://localhost:8080/mytoken4/', {
        'instance': plugins.NotifyAppriseAPI,
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'apprises://localhost:8080/m...4/',
    }),
    ('apprises://user:password@localhost:8080/mytoken5/', {
        'instance': plugins.NotifyAppriseAPI,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'apprises://user:****@localhost:8080/m...5/',
    }),
    ('apprises://localhost:8080/path?+HeaderKey=HeaderValue', {
        'instance': plugins.NotifyAppriseAPI,
    }),
    ('apprise://localhost/%s' % ('a' * 32), {
        'instance': plugins.NotifyAppriseAPI,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('apprise://localhost/%s' % ('a' * 32), {
        'instance': plugins.NotifyAppriseAPI,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('apprise://localhost/%s' % ('a' * 32), {
        'instance': plugins.NotifyAppriseAPI,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_apprise_urls():
    """
    NotifyAppriseAPI() General Checks

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()
