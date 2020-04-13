# -*- coding: utf-8 -*-
#
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

import os
import mock
import requests
from datetime import datetime
from json import dumps
from apprise import Apprise
from apprise import plugins

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Attachment Directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), 'var')


@mock.patch('requests.post')
def test_office365_general(mock_post):
    """
    API: NotifyOffice365 Testing

    """
    # Disable Throttling to speed testing
    plugins.NotifyBase.request_rate_per_sec = 0

    # Initialize some generic (but valid) tokens
    tenant = 'tenant.domain'
    client_id = 'aa-bb-cc-dd-ee'
    secret = 'abcd/1234/abcd@ajd@/test'
    targets = 'target@example.com'

    # Prepare Mock return object
    authentication = {
        "token_type": "Bearer",
        "expires_in": 6000,
        "access_token": "abcd1234"
    }
    response = mock.Mock()
    response.content = dumps(authentication)
    response.status_code = requests.codes.ok
    mock_post.return_value = response

    # Instantiate our object
    obj = Apprise.instantiate(
        'o365://{tenant}:{client_id}@{secret}/{targets}'.format(
            client_id=client_id,
            tenant=tenant,
            secret=secret,
            targets=targets))

    assert isinstance(obj, plugins.NotifyOffice365)

    # Test our notification
    assert obj.notify(title='title', body='test') is True


@mock.patch('requests.post')
def test_office365_authentication(mock_post):
    """
    API: NotifyOffice365 Authentication Testing

    """
    # Disable Throttling to speed testing
    plugins.NotifyBase.request_rate_per_sec = 0

    # Initialize some generic (but valid) tokens
    tenant = 'tenant.domain'
    client_id = 'aa-bb-cc-dd-ee'
    secret = 'abcd/1234/abcd@ajd@/test'
    targets = 'target@example.com'

    # Prepare Mock return object
    authentication_okay = {
        "token_type": "Bearer",
        "expires_in": 6000,
        "access_token": "abcd1234"
    }
    authentication_failure = {
        "error": "invalid_scope",
        "error_description": "AADSTS70011: Blah... Blah Blah... Blah",
        "error_codes": [70011],
        "timestamp": "2020-01-09 02:02:12Z",
        "trace_id": "255d1aef-8c98-452f-ac51-23d051240864",
        "correlation_id": "fb3d2015-bc17-4bb9-bb85-30c5cf1aaaa7",
    }
    response = mock.Mock()
    response.content = dumps(authentication_okay)
    response.status_code = requests.codes.ok
    mock_post.return_value = response

    # Instantiate our object
    obj = Apprise.instantiate(
        'o365://{tenant}:{client_id}@{secret}/{targets}'.format(
            client_id=client_id,
            tenant=tenant,
            secret=secret,
            targets=targets))

    # Authenticate
    assert obj.authenticate() is True

    # We're already authenticated
    assert obj.authenticate() is True

    # Expire our token
    obj.token_expiry = datetime.now()

    # Re-authentiate
    assert obj.authenticate() is True

    # Expire our token
    obj.token_expiry = datetime.now()

    # Set a failure response
    response.content = dumps(authentication_failure)
    response.status_code = 400

    # We will fail to authenticate at this point
    assert obj.authenticate() is False

    # Notifications will also fail in this case
    assert obj.notify(title='title', body='test') is False

    # We will fail to authenticate with invalid data

    invalid_auth_entries = authentication_okay.copy()
    invalid_auth_entries['expires_in'] = 'garbage'
    response.content = dumps(invalid_auth_entries)
    response.status_code = requests.codes.ok
    assert obj.authenticate() is False

    invalid_auth_entries['expires_in'] = None
    response.content = dumps(invalid_auth_entries)
    assert obj.authenticate() is False

    invalid_auth_entries['expires_in'] = ''
    response.content = dumps(invalid_auth_entries)
    assert obj.authenticate() is False

    del invalid_auth_entries['expires_in']
    response.content = dumps(invalid_auth_entries)
    assert obj.authenticate() is False
