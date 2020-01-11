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

    # Add another attachment so we drop into the area of the PushBullet code
    # that sends remaining attachments (if more detected)
    attach.add(os.path.join(TEST_VAR_DIR, 'apprise-test.gif'))

    # Send our attachments
    assert obj.notify(body="test", attach=attach) is True

    # An invalid attachment will cause a failure
    path = os.path.join(TEST_VAR_DIR, '/invalid/path/to/an/invalid/file.jpg')
    attach = AppriseAttachment(path)
    assert obj.notify(body="test", attach=attach) is False

    # Throw an exception on the first call to requests.post()
    mock_post.return_value = None
    mock_post.side_effect = requests.RequestException()

    # We'll fail now because of an internal exception
    assert obj.send(body="test", attach=attach) is False

    # Throw an exception on the second call to requests.post()
    mock_post.side_effect = [response, OSError()]

    # We'll fail now because of an internal exception
    assert obj.send(body="test", attach=attach) is False

    # Throw an exception on the third call to requests.post()
    mock_post.side_effect = [
        response, response, requests.RequestException()]

    # We'll fail now because of an internal exception
    assert obj.send(body="test", attach=attach) is False

    # Throw an exception on the forth call to requests.post()
    mock_post.side_effect = [
        response, response, response, requests.RequestException()]

    # We'll fail now because of an internal exception
    assert obj.send(body="test", attach=attach) is False

    # Test case where we don't get a valid response back
    response.content = '}'
    mock_post.side_effect = response

    # We'll fail because of an invalid json object
    assert obj.send(body="test", attach=attach) is False

    #
    # Test bad responses
    #

    # Prepare a bad response
    response.content = dumps({
        "file_name": "cat.jpg",
        "file_type": "image/jpeg",
        "file_url": "https://dl.pushb.com/abc/cat.jpg",
        "upload_url": "https://upload.pushbullet.com/abcd123",
    })
    bad_response = mock.Mock()
    bad_response.content = response.content
    bad_response.status_code = 400

    # Throw an exception on the third call to requests.post()
    mock_post.return_value = bad_response

    # prepare our attachment
    attach = AppriseAttachment(os.path.join(TEST_VAR_DIR, 'apprise-test.gif'))

    # We'll fail now because we were unable to send the attachment
    assert obj.send(body="test", attach=attach) is False

    # Throw an exception on the second call
    mock_post.side_effect = [response, bad_response, response]
    assert obj.send(body="test", attach=attach) is False

    # Throw an OSError
    mock_post.side_effect = [response, OSError()]
    assert obj.send(body="test", attach=attach) is False

    # Throw an exception on the third call
    mock_post.side_effect = [response, response, bad_response]
    assert obj.send(body="test", attach=attach) is False

    # Throw an exception on the fourth call
    mock_post.side_effect = [response, response, response, bad_response]
    assert obj.send(body="test", attach=attach) is False

    # A good message
    mock_post.side_effect = [response, response, response, response]
    assert obj.send(body="test", attach=attach) is True
