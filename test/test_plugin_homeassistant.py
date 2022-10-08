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

from unittest import mock

import requests
from apprise import plugins
from apprise import Apprise
from helpers import AppriseURLTester

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    ('hassio://:@/', {
        'instance': TypeError,
    }),
    ('hassio://', {
        'instance': TypeError,
    }),
    ('hassios://', {
        'instance': TypeError,
    }),
    # No Long Lived Access Token specified
    ('hassio://user@localhost', {
        'instance': TypeError,
    }),
    ('hassio://localhost/long-lived-access-token', {
        'instance': plugins.NotifyHomeAssistant,
    }),
    ('hassio://user:pass@localhost/long-lived-access-token/', {
        'instance': plugins.NotifyHomeAssistant,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'hassio://user:****@localhost/l...n',
    }),
    ('hassio://localhost:80/long-lived-access-token', {
        'instance': plugins.NotifyHomeAssistant,
    }),
    ('hassio://user@localhost:8123/llat', {
        'instance': plugins.NotifyHomeAssistant,
        'privacy_url': 'hassio://user@localhost/l...t',
    }),
    ('hassios://localhost/llat?nid=!%', {
        # Invalid notification_id
        'instance': TypeError,
    }),
    ('hassios://localhost/llat?nid=abcd', {
        # Valid notification_id
        'instance': plugins.NotifyHomeAssistant,
    }),
    ('hassios://user:pass@localhost/llat', {
        'instance': plugins.NotifyHomeAssistant,
        'privacy_url': 'hassios://user:****@localhost/l...t',
    }),
    ('hassios://localhost:8443/path/llat/', {
        'instance': plugins.NotifyHomeAssistant,
        'privacy_url': 'hassios://localhost:8443/path/l...t',
    }),
    ('hassio://localhost:8123/a/path?accesstoken=llat', {
        'instance': plugins.NotifyHomeAssistant,
        # Default port; so it's stripped off
        # accesstoken was specified as kwarg
        'privacy_url': 'hassio://localhost/a/path/l...t',
    }),
    ('hassios://user:password@localhost:80/llat/', {
        'instance': plugins.NotifyHomeAssistant,

        'privacy_url': 'hassios://user:****@localhost:80',
    }),
    ('hassio://user:pass@localhost:8123/llat', {
        'instance': plugins.NotifyHomeAssistant,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('hassio://user:pass@localhost/llat', {
        'instance': plugins.NotifyHomeAssistant,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('hassio://user:pass@localhost/llat', {
        'instance': plugins.NotifyHomeAssistant,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_homeassistant_urls():
    """
    NotifyHomeAssistant() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch('requests.post')
def test_plugin_homeassistant_general(mock_post):
    """
    NotifyHomeAssistant() General Checks

    """
    # Disable Throttling to speed testing
    plugins.NotifyBase.request_rate_per_sec = 0

    response = mock.Mock()
    response.content = ''
    response.status_code = requests.codes.ok

    # Prepare Mock
    mock_post.return_value = response

    # Variation Initializations
    obj = Apprise.instantiate('hassio://localhost/accesstoken')
    assert isinstance(obj, plugins.NotifyHomeAssistant) is True
    assert isinstance(obj.url(), str) is True

    # Send Notification
    assert obj.send(body="test") is True

    assert mock_post.call_count == 1
    assert mock_post.call_args_list[0][0][0] == \
        'http://localhost:8123/api/services/persistent_notification/create'
