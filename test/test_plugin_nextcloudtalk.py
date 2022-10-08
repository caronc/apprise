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
        'instance': plugins.NotifyNextcloudTalk,
        'requests_response_code': requests.codes.created,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'nctalk://user:****@localhost/roomid1/roomid2',
    }),
    ('nctalk://user:pass@localhost:8080/roomid', {
        'instance': plugins.NotifyNextcloudTalk,
        'requests_response_code': requests.codes.created,
    }),
    ('nctalks://user:pass@localhost/roomid', {
        'instance': plugins.NotifyNextcloudTalk,
        'requests_response_code': requests.codes.created,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'nctalks://user:****@localhost/roomid',
    }),
    ('nctalks://user:pass@localhost:8080/roomid/', {
        'instance': plugins.NotifyNextcloudTalk,
        'requests_response_code': requests.codes.created,
    }),
    ('nctalk://user:pass@localhost:8080/roomid?+HeaderKey=HeaderValue', {
        'instance': plugins.NotifyNextcloudTalk,
        'requests_response_code': requests.codes.created,
    }),
    ('nctalk://user:pass@localhost:8081/roomid', {
        'instance': plugins.NotifyNextcloudTalk,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('nctalk://user:pass@localhost:8082/roomid', {
        'instance': plugins.NotifyNextcloudTalk,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('nctalk://user:pass@localhost:8083/roomid1/roomid2/roomid3', {
        'instance': plugins.NotifyNextcloudTalk,
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
    # Disable Throttling to speed testing
    plugins.NotifyBase.request_rate_per_sec = 0

    # A response
    robj = mock.Mock()
    robj.content = ''
    robj.status_code = requests.codes.created

    # Prepare Mock
    mock_post.return_value = robj

    # Variation Initializations
    obj = plugins.NotifyNextcloudTalk(
        host="localhost", user="admin", password="pass", targets="roomid")
    assert isinstance(obj, plugins.NotifyNextcloudTalk) is True
    assert isinstance(obj.url(), str) is True

    # An empty body
    assert obj.send(body="") is True
    assert 'data' in mock_post.call_args_list[0][1]
    assert 'message' in mock_post.call_args_list[0][1]['data']
