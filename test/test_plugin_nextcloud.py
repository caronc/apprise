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

from unittest import mock

import requests
from apprise.plugins.NotifyNextcloud import NotifyNextcloud
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
        'instance': NotifyNextcloud,
    }),
    ('ncloud://user@localhost/admin', {
        'instance': NotifyNextcloud,
    }),
    ('ncloud://user@localhost?to=user1,user2', {
        'instance': NotifyNextcloud,
    }),
    ('ncloud://user@localhost?to=user1,user2&version=20', {
        'instance': NotifyNextcloud,
    }),
    ('ncloud://user@localhost?to=user1,user2&version=21', {
        'instance': NotifyNextcloud,
    }),
    ('ncloud://user:pass@localhost/user1/user2', {
        'instance': NotifyNextcloud,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'ncloud://user:****@localhost/user1/user2',
    }),
    ('ncloud://user:pass@localhost:8080/admin', {
        'instance': NotifyNextcloud,
    }),
    ('nclouds://user:pass@localhost/admin', {
        'instance': NotifyNextcloud,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'nclouds://user:****@localhost/admin',
    }),
    ('nclouds://user:pass@localhost:8080/admin/', {
        'instance': NotifyNextcloud,
    }),
    ('ncloud://localhost:8080/admin?+HeaderKey=HeaderValue', {
        'instance': NotifyNextcloud,
    }),
    ('ncloud://user:pass@localhost:8081/admin', {
        'instance': NotifyNextcloud,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('ncloud://user:pass@localhost:8082/admin', {
        'instance': NotifyNextcloud,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('ncloud://user:pass@localhost:8083/user1/user2/user3', {
        'instance': NotifyNextcloud,
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

    # A response
    robj = mock.Mock()
    robj.content = ''
    robj.status_code = requests.codes.ok

    # Prepare Mock
    mock_post.return_value = robj

    # Variation Initializations
    obj = NotifyNextcloud(
        host="localhost", user="admin", password="pass", targets="user")
    assert isinstance(obj, NotifyNextcloud) is True
    assert isinstance(obj.url(), str) is True

    # An empty body
    assert obj.send(body="") is True
    assert 'data' in mock_post.call_args_list[0][1]
    assert 'shortMessage' in mock_post.call_args_list[0][1]['data']
    # The longMessage argument is not set
    assert 'longMessage' not in mock_post.call_args_list[0][1]['data']
