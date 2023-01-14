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
from apprise import Apprise
from apprise.plugins.NotifyHomeAssistant import NotifyHomeAssistant
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
        'instance': NotifyHomeAssistant,
    }),
    ('hassio://user:pass@localhost/long-lived-access-token/', {
        'instance': NotifyHomeAssistant,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'hassio://user:****@localhost/l...n',
    }),
    ('hassio://localhost:80/long-lived-access-token', {
        'instance': NotifyHomeAssistant,
    }),
    ('hassio://user@localhost:8123/llat', {
        'instance': NotifyHomeAssistant,
        'privacy_url': 'hassio://user@localhost/l...t',
    }),
    ('hassios://localhost/llat?nid=!%', {
        # Invalid notification_id
        'instance': TypeError,
    }),
    ('hassios://localhost/llat?nid=abcd', {
        # Valid notification_id
        'instance': NotifyHomeAssistant,
    }),
    ('hassios://user:pass@localhost/llat', {
        'instance': NotifyHomeAssistant,
        'privacy_url': 'hassios://user:****@localhost/l...t',
    }),
    ('hassios://localhost:8443/path/llat/', {
        'instance': NotifyHomeAssistant,
        'privacy_url': 'hassios://localhost:8443/path/l...t',
    }),
    ('hassio://localhost:8123/a/path?accesstoken=llat', {
        'instance': NotifyHomeAssistant,
        # Default port; so it's stripped off
        # accesstoken was specified as kwarg
        'privacy_url': 'hassio://localhost/a/path/l...t',
    }),
    ('hassios://user:password@localhost:80/llat/', {
        'instance': NotifyHomeAssistant,

        'privacy_url': 'hassios://user:****@localhost:80',
    }),
    ('hassio://user:pass@localhost:8123/llat', {
        'instance': NotifyHomeAssistant,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('hassio://user:pass@localhost/llat', {
        'instance': NotifyHomeAssistant,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('hassio://user:pass@localhost/llat', {
        'instance': NotifyHomeAssistant,
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

    response = mock.Mock()
    response.content = ''
    response.status_code = requests.codes.ok

    # Prepare Mock
    mock_post.return_value = response

    # Variation Initializations
    obj = Apprise.instantiate('hassio://localhost/accesstoken')
    assert isinstance(obj, NotifyHomeAssistant) is True
    assert isinstance(obj.url(), str) is True

    # Send Notification
    assert obj.send(body="test") is True

    assert mock_post.call_count == 1
    assert mock_post.call_args_list[0][0][0] == \
        'http://localhost:8123/api/services/persistent_notification/create'
