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
import six
import mock
import pytest
import requests
from apprise import plugins
from apprise import NotifyType
from apprise import AppriseAttachment

from json import dumps

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Attachment Directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), 'var')


@mock.patch('requests.post')
def test_slack_oauth_access_token(mock_post):
    """
    API: NotifySlack() OAuth Access Token Tests

    """
    # Disable Throttling to speed testing
    plugins.NotifyBase.request_rate_per_sec = 0

    # Generate an invalid bot token
    token = 'xo-invalid'

    request = mock.Mock()
    request.content = dumps({
        'ok': True,
        'message': '',

        # Attachment support
        'file': {
            'url_private': 'http://localhost',
        }
    })
    request.status_code = requests.codes.ok

    # We'll fail to validate the access_token
    with pytest.raises(TypeError):
        plugins.NotifySlack(access_token=token)

    # Generate a (valid) bot token
    token = 'xoxb-1234-1234-abc124'

    # Prepare Mock
    mock_post.return_value = request

    # Variation Initializations
    obj = plugins.NotifySlack(access_token=token, targets='#apprise')
    assert isinstance(obj, plugins.NotifySlack) is True
    assert isinstance(obj.url(), six.string_types) is True

    # apprise room was found
    assert obj.send(body="test") is True

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

    # Test case where expected return attachment payload is invalid
    request.content = dumps({
        'ok': True,
        'message': '',

        # Attachment support
        'file': None
    })
    path = os.path.join(TEST_VAR_DIR, 'apprise-test.gif')
    attach = AppriseAttachment(path)
    # We'll fail because of the bad 'file' response
    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO,
        attach=attach) is False

    # Slack requests pay close attention to the response to determine
    # if things go well... this is not a good JSON response:
    request.content = '{'

    # As a result, we'll fail to send our notification
    assert obj.send(body="test", attach=attach) is False

    request.content = dumps({
        'ok': False,
        'message': 'We failed',
    })

    # A response from Slack (even with a 200 response) still
    # results in a failure:
    assert obj.send(body="test", attach=attach) is False

    # Handle exceptions reading our attachment from disk (should it happen)
    mock_post.side_effect = OSError("Attachment Error")
    mock_post.return_value = None

    # We'll fail now because of an internal exception
    assert obj.send(body="test") is False


@mock.patch('requests.post')
def test_slack_webhook(mock_post):
    """
    API: NotifySlack() Webhook Tests

    """
    # Disable Throttling to speed testing
    plugins.NotifyBase.request_rate_per_sec = 0

    # Prepare Mock
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok
    mock_post.return_value.content = dumps({
        'ok': True,
    })

    # Initialize some generic (but valid) tokens
    token_a = 'A' * 9
    token_b = 'B' * 9
    token_c = 'c' * 24

    # Support strings
    channels = 'chan1,#chan2,+BAK4K23G5,@user,,,'

    obj = plugins.NotifySlack(
        token_a=token_a, token_b=token_b, token_c=token_c, targets=channels)
    assert len(obj.channels) == 4

    # This call includes an image with it's payload:
    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO) is True

    # Missing first Token
    with pytest.raises(TypeError):
        plugins.NotifySlack(
            token_a=None, token_b=token_b, token_c=token_c,
            targets=channels)

    # Test include_image
    obj = plugins.NotifySlack(
        token_a=token_a, token_b=token_b, token_c=token_c, targets=channels,
        include_image=True)

    # This call includes an image with it's payload:
    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO) is True
