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
from apprise.plugins.NotifyNextcloudTalk import NotifyNextcloudTalk
from helpers import AppriseURLTester

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

apprise_url_tests = (
    ##################################
    # NotifyNextcloud
    ##################################
    ('nctalk://:@/', {
        'instance': None,
    }),
    ('nctalk://', {
        'instance': None,
    }),
    ('nctalks://', {
        # No hostname
        'instance': None,
    }),
    ('nctalk://localhost', {
        # No user and password and roomid specified
        'instance': TypeError,
    }),
    ('nctalk://localhost/roomid', {
        # No user and password specified
        'instance': TypeError,
    }),
    ('nctalk://user@localhost/roomid', {
        # No password specified
        'instance': TypeError,
    }),
    ('nctalk://user:pass@localhost', {
        # No roomid specified
        'instance': TypeError,
    }),
    ('nctalk://user:pass@localhost/roomid1/roomid2', {
        'instance': NotifyNextcloudTalk,
        'requests_response_code': requests.codes.created,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'nctalk://user:****@localhost/roomid1/roomid2',
    }),
    ('nctalk://user:pass@localhost:8080/roomid', {
        'instance': NotifyNextcloudTalk,
        'requests_response_code': requests.codes.created,
    }),
    ('nctalks://user:pass@localhost/roomid', {
        'instance': NotifyNextcloudTalk,
        'requests_response_code': requests.codes.created,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'nctalks://user:****@localhost/roomid',
    }),
    ('nctalks://user:pass@localhost:8080/roomid/', {
        'instance': NotifyNextcloudTalk,
        'requests_response_code': requests.codes.created,
    }),
    ('nctalk://user:pass@localhost:8080/roomid?+HeaderKey=HeaderValue', {
        'instance': NotifyNextcloudTalk,
        'requests_response_code': requests.codes.created,
    }),
    ('nctalk://user:pass@localhost:8081/roomid', {
        'instance': NotifyNextcloudTalk,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('nctalk://user:pass@localhost:8082/roomid', {
        'instance': NotifyNextcloudTalk,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('nctalk://user:pass@localhost:8083/roomid1/roomid2/roomid3', {
        'instance': NotifyNextcloudTalk,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_nextcloudtalk_urls():
    """
    NotifyNextcloud() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch('requests.post')
def test_plugin_nextcloudtalk_edge_cases(mock_post):
    """
    NotifyNextcloud() Edge Cases

    """

    # A response
    robj = mock.Mock()
    robj.content = ''
    robj.status_code = requests.codes.created

    # Prepare Mock
    mock_post.return_value = robj

    # Variation Initializations
    obj = NotifyNextcloudTalk(
        host="localhost", user="admin", password="pass", targets="roomid")
    assert isinstance(obj, NotifyNextcloudTalk) is True
    assert isinstance(obj.url(), str) is True

    # An empty body
    assert obj.send(body="") is True
    assert 'data' in mock_post.call_args_list[0][1]
    assert 'message' in mock_post.call_args_list[0][1]['data']
