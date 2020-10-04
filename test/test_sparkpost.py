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

import os
import pytest
import mock
import requests
from json import dumps
from apprise import plugins
from apprise import Apprise
from apprise import AppriseAttachment
from apprise import NotifyType

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Attachment Directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), 'var')


@mock.patch('requests.post')
def test_notify_sparkpost_plugin_throttling(mock_post):
    """
    API: NotifySpark() Throttling

    """

    # Disable Throttling to speed testing
    plugins.NotifyBase.request_rate_per_sec = 0
    plugins.NotifySparkPost.sparkpost_retry_wait_sec = 0.1
    plugins.NotifySparkPost.sparkpost_retry_attempts = 3

    # API Key
    apikey = 'abc123'
    user = 'user'
    host = 'example.com'
    targets = '{}@{}'.format(user, host)

    # Exception should be thrown about the fact no user was specified
    with pytest.raises(TypeError):
        plugins.NotifySparkPost(
            apikey=apikey, targets=targets, host=host)

    # Exception should be thrown about the fact no private key was specified
    with pytest.raises(TypeError):
        plugins.NotifySparkPost(
            apikey=None, targets=targets, user=user, host=host)

    okay_response = requests.Request()
    okay_response.status_code = requests.codes.ok
    okay_response.content = dumps({
        "results": {
            "total_rejected_recipients": 0,
            "total_accepted_recipients": 1,
            "id": "11668787484950529"
        }
    })

    retry_response = requests.Request()
    retry_response.status_code = requests.codes.too_many_requests
    retry_response.content = dumps({
        "errors": [
            {
                "description":
                    "Unconfigured or unverified sending domain.",
                "code": "7001",
                "message": "Invalid domain"
            }
        ]
    })

    # Prepare Mock (force 2 retry responses and then one okay)
    mock_post.side_effect = \
        (retry_response, retry_response, okay_response)

    obj = Apprise.instantiate(
        'sparkpost://user@localhost.localdomain/{}'.format(apikey))
    assert isinstance(obj, plugins.NotifySparkPost)

    # We'll successfully perform the notification as we're within
    # our retry limit
    assert obj.notify('test') is True

    mock_post.reset_mock()
    mock_post.side_effect = \
        (retry_response, retry_response, retry_response)

    # Now we are less than our expected limit check so we will fail
    assert obj.notify('test') is False


@mock.patch('requests.post')
def test_notify_sparkpost_plugin_attachments(mock_post):
    """
    API: NotifySpark() Attachments

    """
    # Disable Throttling to speed testing
    plugins.NotifyBase.request_rate_per_sec = 0
    plugins.NotifySparkPost.sparkpost_retry_wait_sec = 0.1
    plugins.NotifySparkPost.sparkpost_retry_attempts = 3

    okay_response = requests.Request()
    okay_response.status_code = requests.codes.ok
    okay_response.content = dumps({
        "results": {
            "total_rejected_recipients": 0,
            "total_accepted_recipients": 1,
            "id": "11668787484950529"
        }
    })

    # Assign our mock object our return value
    mock_post.return_value = okay_response

    # API Key
    apikey = 'abc123'

    obj = Apprise.instantiate(
        'sparkpost://user@localhost.localdomain/{}'.format(apikey))
    assert isinstance(obj, plugins.NotifySparkPost)

    # Test Valid Attachment
    path = os.path.join(TEST_VAR_DIR, 'apprise-test.gif')
    attach = AppriseAttachment(path)
    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO,
        attach=attach) is True

    # Test invalid attachment
    path = os.path.join(TEST_VAR_DIR, '/invalid/path/to/an/invalid/file.jpg')
    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO,
        attach=path) is False

    with mock.patch('base64.b64encode', side_effect=OSError()):
        # We can't send the message if we fail to parse the data
        assert obj.notify(
            body='body', title='title', notify_type=NotifyType.INFO,
            attach=attach) is False
