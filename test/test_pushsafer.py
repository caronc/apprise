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
import pytest
import mock
import requests
from json import dumps
from apprise import AppriseAttachment
from apprise import NotifyType
from apprise import plugins

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Attachment Directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), 'var')


@mock.patch('requests.post')
def test_notify_pushsafer_plugin(mock_post):
    """
    API: NotifyPushSafer() Tests

    """
    # Disable Throttling to speed testing
    plugins.NotifyBase.request_rate_per_sec = 0

    # Private Key
    privatekey = 'abc123'

    # Prepare Mock
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok
    mock_post.return_value.content = dumps({
        'status': 1,
        'success': "okay",
    })

    # Exception should be thrown about the fact no private key was specified
    with pytest.raises(TypeError):
        plugins.NotifyPushSafer(privatekey=None)

    # Multiple Attachment Support
    path = os.path.join(TEST_VAR_DIR, 'apprise-test.gif')
    attach = AppriseAttachment()
    for _ in range(0, 4):
        attach.add(path)

    obj = plugins.NotifyPushSafer(privatekey=privatekey)
    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO,
        attach=attach) is True

    # Test error reading attachment from disk
    with mock.patch('io.open', side_effect=OSError):
        obj.notify(
            body='body', title='title', notify_type=NotifyType.INFO,
            attach=attach)

    # Test unsupported mime type
    attach = AppriseAttachment(path)

    attach[0]._mimetype = 'application/octet-stream'

    # We gracefully just don't send the attachment in these cases;
    # The notify itself will still be successful
    mock_post.reset_mock()
    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO,
        attach=attach) is True

    # the 'p', 'p2', and 'p3' are the data variables used when including an
    # image.
    assert 'data' in mock_post.call_args[1]
    assert 'p' not in mock_post.call_args[1]['data']
    assert 'p2' not in mock_post.call_args[1]['data']
    assert 'p3' not in mock_post.call_args[1]['data']

    # Invalid file path
    path = os.path.join(TEST_VAR_DIR, '/invalid/path/to/an/invalid/file.jpg')
    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO,
        attach=path) is False
