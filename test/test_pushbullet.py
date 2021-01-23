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
import mock
import requests
from json import dumps
from apprise import Apprise
from apprise import AppriseAttachment
from apprise import plugins

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Attachment Directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), 'var')


@mock.patch('requests.post')
def test_pushbullet_attachments(mock_post):
    """
    API: NotifyPushBullet() Attachment Checks

    """
    # Disable Throttling to speed testing
    plugins.NotifyBase.request_rate_per_sec = 0

    # Initialize some generic (but valid) tokens
    access_token = 't' * 32

    # Prepare Mock return object
    response = mock.Mock()
    response.content = dumps({
        "file_name": "cat.jpg",
        "file_type": "image/jpeg",
        "file_url": "https://dl.pushb.com/abc/cat.jpg",
        "upload_url": "https://upload.pushbullet.com/abcd123",
    })
    response.status_code = requests.codes.ok
    mock_post.return_value = response

    # prepare our attachment
    attach = AppriseAttachment(os.path.join(TEST_VAR_DIR, 'apprise-test.gif'))

    # Test our markdown
    obj = Apprise.instantiate(
        'pbul://{}/?format=markdown'.format(access_token))

    # Send a good attachment
    assert obj.notify(body="test", attach=attach) is True

    # Test our call count
    assert mock_post.call_count == 4
    # Image Prep
    assert mock_post.call_args_list[0][0][0] == \
        'https://api.pushbullet.com/v2/upload-request'
    assert mock_post.call_args_list[1][0][0] == \
        'https://upload.pushbullet.com/abcd123'
    # Message
    assert mock_post.call_args_list[2][0][0] == \
        'https://api.pushbullet.com/v2/pushes'
    # Image Send
    assert mock_post.call_args_list[3][0][0] == \
        'https://api.pushbullet.com/v2/pushes'

    # Reset our mock object
    mock_post.reset_mock()

    # Add another attachment so we drop into the area of the PushBullet code
    # that sends remaining attachments (if more detected)
    attach.add(os.path.join(TEST_VAR_DIR, 'apprise-test.gif'))

    # Send our attachments
    assert obj.notify(body="test", attach=attach) is True

    # Test our call count
    assert mock_post.call_count == 7
    # Image Prep
    assert mock_post.call_args_list[0][0][0] == \
        'https://api.pushbullet.com/v2/upload-request'
    assert mock_post.call_args_list[1][0][0] == \
        'https://upload.pushbullet.com/abcd123'
    assert mock_post.call_args_list[2][0][0] == \
        'https://api.pushbullet.com/v2/upload-request'
    assert mock_post.call_args_list[3][0][0] == \
        'https://upload.pushbullet.com/abcd123'
    # Message
    assert mock_post.call_args_list[4][0][0] == \
        'https://api.pushbullet.com/v2/pushes'
    # Image Send
    assert mock_post.call_args_list[5][0][0] == \
        'https://api.pushbullet.com/v2/pushes'
    assert mock_post.call_args_list[6][0][0] == \
        'https://api.pushbullet.com/v2/pushes'

    # Reset our mock object
    mock_post.reset_mock()

    # An invalid attachment will cause a failure
    path = os.path.join(TEST_VAR_DIR, '/invalid/path/to/an/invalid/file.jpg')
    attach = AppriseAttachment(path)
    assert obj.notify(body="test", attach=attach) is False

    # Test our call count
    assert mock_post.call_count == 0

    # prepare our attachment
    attach = AppriseAttachment(os.path.join(TEST_VAR_DIR, 'apprise-test.gif'))

    # Prepare a bad response
    bad_response = mock.Mock()
    bad_response.content = dumps({
        "file_name": "cat.jpg",
        "file_type": "image/jpeg",
        "file_url": "https://dl.pushb.com/abc/cat.jpg",
        "upload_url": "https://upload.pushbullet.com/abcd123",
    })
    bad_response.status_code = requests.codes.internal_server_error

    # Prepare a bad response
    bad_json_response = mock.Mock()
    bad_json_response.content = '}'
    bad_json_response.status_code = requests.codes.ok

    # Throw an exception on the first call to requests.post()
    mock_post.return_value = None
    for side_effect in (requests.RequestException(), OSError(), bad_response):
        mock_post.side_effect = side_effect

        # We'll fail now because of our error handling
        assert obj.send(body="test", attach=attach) is False

    # Throw an exception on the second call to requests.post()
    for side_effect in (requests.RequestException(), OSError(), bad_response):
        mock_post.side_effect = [response, side_effect]

        # We'll fail now because of our error handling
        assert obj.send(body="test", attach=attach) is False

    # Throw an exception on the third call to requests.post()
    for side_effect in (requests.RequestException(), OSError(), bad_response):
        mock_post.side_effect = [response, response, side_effect]

        # We'll fail now because of our error handling
        assert obj.send(body="test", attach=attach) is False

    # Throw an exception on the forth call to requests.post()
    for side_effect in (requests.RequestException(), OSError(), bad_response):
        mock_post.side_effect = [response, response, response, side_effect]

        # We'll fail now because of our error handling
        assert obj.send(body="test", attach=attach) is False

    # Test case where we don't get a valid response back
    mock_post.side_effect = bad_json_response

    # We'll fail because of an invalid json object
    assert obj.send(body="test", attach=attach) is False
