# -*- coding: utf-8 -*-
#
# Copyright (C) 2020 Chris Caron <lead2gold@gmail.com>
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

from unittest import mock

import requests
from apprise import plugins
from helpers import AppriseURLTester

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

apprise_url_tests = (
    ##################################
    # NotifyNextcloud
    ##################################
    ('ncloud://:@/', {
        'instance': None,
    }),
    ('ncloud://', {
        'instance': None,
    }),
    ('nclouds://', {
        # No hostname
        'instance': None,
    }),
    ('ncloud://localhost', {
        # No user specified
        'instance': TypeError,
    }),
    ('ncloud://user@localhost?to=user1,user2&version=invalid', {
        # An invalid version was specified
        'instance': TypeError,
    }),
    ('ncloud://user@localhost?to=user1,user2&version=0', {
        # An invalid version was specified
        'instance': TypeError,
    }),
    ('ncloud://user@localhost?to=user1,user2&version=-23', {
        # An invalid version was specified
        'instance': TypeError,
    }),
    ('ncloud://localhost/admin', {
        'instance': plugins.NotifyNextcloud,
    }),
    ('ncloud://user@localhost/admin', {
        'instance': plugins.NotifyNextcloud,
    }),
    ('ncloud://user@localhost?to=user1,user2', {
        'instance': plugins.NotifyNextcloud,
    }),
    ('ncloud://user@localhost?to=user1,user2&version=20', {
        'instance': plugins.NotifyNextcloud,
    }),
    ('ncloud://user@localhost?to=user1,user2&version=21', {
        'instance': plugins.NotifyNextcloud,
    }),
    ('ncloud://user:pass@localhost/user1/user2', {
        'instance': plugins.NotifyNextcloud,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'ncloud://user:****@localhost/user1/user2',
    }),
    ('ncloud://user:pass@localhost:8080/admin', {
        'instance': plugins.NotifyNextcloud,
    }),
    ('nclouds://user:pass@localhost/admin', {
        'instance': plugins.NotifyNextcloud,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'nclouds://user:****@localhost/admin',
    }),
    ('nclouds://user:pass@localhost:8080/admin/', {
        'instance': plugins.NotifyNextcloud,
    }),
    ('ncloud://localhost:8080/admin?+HeaderKey=HeaderValue', {
        'instance': plugins.NotifyNextcloud,
    }),
    ('ncloud://user:pass@localhost:8081/admin', {
        'instance': plugins.NotifyNextcloud,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('ncloud://user:pass@localhost:8082/admin', {
        'instance': plugins.NotifyNextcloud,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('ncloud://user:pass@localhost:8083/user1/user2/user3', {
        'instance': plugins.NotifyNextcloud,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_nextcloud_urls():
    """
    NotifyNextcloud() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch('requests.post')
def test_plugin_nextcloud_edge_cases(mock_post):
    """
    NotifyNextcloud() Edge Cases

    """
    # Disable Throttling to speed testing
    plugins.NotifyBase.request_rate_per_sec = 0

    # A response
    robj = mock.Mock()
    robj.content = ''
    robj.status_code = requests.codes.ok

    # Prepare Mock
    mock_post.return_value = robj

    # Variation Initializations
    obj = plugins.NotifyNextcloud(
        host="localhost", user="admin", password="pass", targets="user")
    assert isinstance(obj, plugins.NotifyNextcloud) is True
    assert isinstance(obj.url(), str) is True

    # An empty body
    assert obj.send(body="") is True
    assert 'data' in mock_post.call_args_list[0][1]
    assert 'shortMessage' in mock_post.call_args_list[0][1]['data']
    # The longMessage argument is not set
    assert 'longMessage' not in mock_post.call_args_list[0][1]['data']
