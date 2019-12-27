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
def test_pushover_attachments(mock_post, tmpdir):
    """
    API: NotifyPushover() Attachment Checks

    """
    # Disable Throttling to speed testing
    plugins.NotifyBase.request_rate_per_sec = 0

    # Initialize some generic (but valid) tokens
    user_key = 'u' * 30
    api_token = 'a' * 30

    # Prepare Mock return object
    response = mock.Mock()
    response.content = dumps(
        {"status": 1, "request": "647d2300-702c-4b38-8b2f-d56326ae460b"})
    response.status_code = requests.codes.ok
    mock_post.return_value = response

    # prepare our attachment
    attach = AppriseAttachment(os.path.join(TEST_VAR_DIR, 'apprise-test.gif'))

    # Instantiate our object
    obj = Apprise.instantiate(
        'pover://{}@{}/'.format(user_key, api_token))
    assert isinstance(obj, plugins.NotifyPushover)

    # Test our attachment
    assert obj.notify(body="test", attach=attach) is True

    # Test multiple attachments
    assert attach.add(os.path.join(TEST_VAR_DIR, 'apprise-test.gif'))
    assert obj.notify(body="test", attach=attach) is True

    image = tmpdir.mkdir("pover_image").join("test.jpg")
    image.write('a' * plugins.NotifyPushover.attach_max_size_bytes)

    attach = AppriseAttachment.instantiate(str(image))
    assert obj.notify(body="test", attach=attach) is True

    # Add 1 more byte to the file (putting it over the limit)
    image.write('a' * (plugins.NotifyPushover.attach_max_size_bytes + 1))

    attach = AppriseAttachment.instantiate(str(image))
    assert obj.notify(body="test", attach=attach) is False

    # Test case when file is missing
    attach = AppriseAttachment.instantiate(
        'file://{}?cache=False'.format(str(image)))
    os.unlink(str(image))
    assert obj.notify(
        body='body', title='title', attach=attach) is False

    # Test unsuported files:
    image = tmpdir.mkdir("pover_unsupported").join("test.doc")
    image.write('a' * 256)
    attach = AppriseAttachment.instantiate(str(image))

    # Content is silently ignored
    assert obj.notify(body="test", attach=attach) is True

    # Throw an exception on the second call to requests.post()
    mock_post.side_effect = OSError()
    # prepare our attachment
    attach = AppriseAttachment(os.path.join(TEST_VAR_DIR, 'apprise-test.gif'))
    assert obj.notify(body="test", attach=attach) is False
