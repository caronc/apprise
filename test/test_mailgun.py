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
def test_notify_mailgun_plugin_attachments(mock_post):
    """
    API: NotifyMailgun() Attachments

    """
    # Disable Throttling to speed testing
    plugins.NotifyBase.request_rate_per_sec = 0

    okay_response = requests.Request()
    okay_response.status_code = requests.codes.ok
    okay_response.content = ""

    # Assign our mock object our return value
    mock_post.return_value = okay_response

    # API Key
    apikey = 'abc123'

    obj = Apprise.instantiate(
        'mailgun://user@localhost.localdomain/{}'.format(apikey))
    assert isinstance(obj, plugins.NotifyMailgun)

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

    mock_post.return_value = None
    mock_post.side_effect = OSError()
    # We can't send the message if we can't read the attachment
    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO,
        attach=attach) is False

    # Return our good configuration
    mock_post.side_effect = None
    mock_post.return_value = okay_response
    with mock.patch('builtins.open', side_effect=OSError()):
        # We can't send the message we can't open the attachment for reading
        assert obj.notify(
            body='body', title='title', notify_type=NotifyType.INFO,
            attach=attach) is False

    with mock.patch('builtins.open') as mock_open:
        mock_fp = mock.Mock()
        mock_fp.seek.side_effect = OSError()
        mock_open.return_value = mock_fp

        # We can't send the message we can't seek through it
        assert obj.notify(
            body='body', title='title', notify_type=NotifyType.INFO,
            attach=attach) is False

    obj = Apprise.instantiate(
        'mailgun://no-reply@example.com/{}/'
        'user1@example.com/user2@example.com?batch=yes'.format(apikey))
    assert isinstance(obj, plugins.NotifyMailgun)

    # Force our batch to break into separate messages
    obj.default_batch_size = 1
    # We'll send 2 messages
    mock_post.reset_mock()

    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO,
        attach=attach) is True
    assert mock_post.call_count == 2

    # single batch
    mock_post.reset_mock()
    # We'll send 1 message
    obj.default_batch_size = 2

    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO,
        attach=attach) is True
    assert mock_post.call_count == 1
