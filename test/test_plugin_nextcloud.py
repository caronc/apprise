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
