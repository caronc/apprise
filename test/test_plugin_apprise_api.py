# -*- coding: utf-8 -*-
#
# Apprise - Push Notification Library.
# Copyright (C) 2023  Chris Caron <lead2gold@gmail.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor,
# Boston, MA  02110-1301, USA.
from apprise.plugins.NotifyAppriseAPI import NotifyAppriseAPI
from helpers import AppriseURLTester
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
        'instance': NotifyAppriseAPI,
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'apprise://localhost/a...a/',
    }),
    # A valid URL with Token (using port)
    ('apprise://localhost:8080/%s' % ('b' * 32), {
        'instance': NotifyAppriseAPI,
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'apprise://localhost:8080/b...b/',
    }),
    # A secure (https://) reference
    ('apprises://localhost/%s' % ('c' * 32), {
        'instance': NotifyAppriseAPI,
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'apprises://localhost/c...c/',
    }),
    # Native URL suport (https)
    ('https://example.com/path/notify/%s' % ('d' * 32), {
        'instance': NotifyAppriseAPI,
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'apprises://example.com/path/d...d/',
    }),
    # Native URL suport (http)
    ('http://example.com/notify/%s' % ('d' * 32), {
        'instance': NotifyAppriseAPI,
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'apprise://example.com/d...d/',
    }),
    # support to= keyword
    ('apprises://localhost/?to=%s' % ('e' * 32), {
        'instance': NotifyAppriseAPI,
        'privacy_url': 'apprises://localhost/e...e/',
    }),
    # support token= keyword (even when passed with to=, token over-rides)
    ('apprise://localhost/?token=%s&to=%s' % ('f' * 32, 'abcd'), {
        'instance': NotifyAppriseAPI,
        'privacy_url': 'apprise://localhost/f...f/',
    }),
    # Test tags
    ('apprise://localhost/?token=%s&tags=admin,team' % ('abcd'), {
        'instance': NotifyAppriseAPI,
        'privacy_url': 'apprise://localhost/a...d/',
    }),
    # Test Format string
    ('apprise://user@localhost/mytoken0/?format=markdown', {
        'instance': NotifyAppriseAPI,
        'privacy_url': 'apprise://user@localhost/m...0/',
    }),
    ('apprise://user@localhost/mytoken1/', {
        'instance': NotifyAppriseAPI,
        'privacy_url': 'apprise://user@localhost/m...1/',
    }),
    ('apprise://localhost:8080/mytoken/', {
        'instance': NotifyAppriseAPI,
    }),
    ('apprise://user:pass@localhost:8080/mytoken2/', {
        'instance': NotifyAppriseAPI,
        'privacy_url': 'apprise://user:****@localhost:8080/m...2/',
    }),
    ('apprises://localhost/mytoken/', {
        'instance': NotifyAppriseAPI,
    }),
    ('apprises://user:pass@localhost/mytoken3/', {
        'instance': NotifyAppriseAPI,
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'apprises://user:****@localhost/m...3/',
    }),
    ('apprises://localhost:8080/mytoken4/', {
        'instance': NotifyAppriseAPI,
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'apprises://localhost:8080/m...4/',
    }),
    ('apprises://user:password@localhost:8080/mytoken5/', {
        'instance': NotifyAppriseAPI,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'apprises://user:****@localhost:8080/m...5/',
    }),
    ('apprises://localhost:8080/path?+HeaderKey=HeaderValue', {
        'instance': NotifyAppriseAPI,
    }),
    ('apprise://localhost/%s' % ('a' * 32), {
        'instance': NotifyAppriseAPI,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('apprise://localhost/%s' % ('a' * 32), {
        'instance': NotifyAppriseAPI,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('apprise://localhost/%s' % ('a' * 32), {
        'instance': NotifyAppriseAPI,
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
