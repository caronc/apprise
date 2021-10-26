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

import six
import mock
import requests
from apprise import plugins
from apprise import Apprise

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)


@mock.patch('requests.post')
def test_twilio_auth(mock_post):
    """
    API: NotifyTwilio() Tests using:
        - account-wide auth token
        - API key and its own auth token

    """
    # Disable Throttling to speed testing
    plugins.NotifyBase.request_rate_per_sec = 0

    response = mock.Mock()
    response.content = ''
    response.status_code = requests.codes.ok

    # Prepare Mock
    mock_post.return_value = response

    # Initialize some generic (but valid) tokens
    account_sid = 'AC{}'.format('b' * 32)
    apikey = 'SK{}'.format('b' * 32)
    auth_token = '{}'.format('b' * 32)
    source = '+1 (555) 123-3456'
    dest = '+1 (555) 987-6543'
    message_contents = "test"

    # Variation of initialization without API key
    obj = Apprise.instantiate(
        'twilio://{}:{}@{}/{}'
        .format(account_sid, auth_token, source, dest))
    assert isinstance(obj, plugins.NotifyTwilio) is True
    assert isinstance(obj.url(), six.string_types) is True

    # Send Notification
    assert obj.send(body=message_contents) is True

    # Variation of initialization with API key
    obj = Apprise.instantiate(
        'twilio://{}:{}@{}/{}?apikey={}'
        .format(account_sid, auth_token, source, dest, apikey))
    assert isinstance(obj, plugins.NotifyTwilio) is True
    assert isinstance(obj.url(), six.string_types) is True

    # Send Notification
    assert obj.send(body=message_contents) is True

    # Validate expected call parameters
    assert mock_post.call_count == 2
    first_call = mock_post.call_args_list[0]
    second_call = mock_post.call_args_list[1]

    # URL and message parameters are the same for both calls
    assert first_call[0][0] == \
        second_call[0][0] == \
        'https://api.twilio.com/2010-04-01/Accounts/{}/Messages.json'.format(
            account_sid)
    assert first_call[1]['data']['Body'] == \
        second_call[1]['data']['Body'] == \
        message_contents
    assert first_call[1]['data']['From'] == \
        second_call[1]['data']['From'] == \
        '+15551233456'
    assert first_call[1]['data']['To'] == \
        second_call[1]['data']['To'] == \
        '+15559876543'

    # Auth differs depending on if API Key is used
    assert first_call[1]['auth'] == (account_sid, auth_token)
    assert second_call[1]['auth'] == (apikey, auth_token)
