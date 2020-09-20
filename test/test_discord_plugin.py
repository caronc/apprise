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
import six
import mock
import pytest
import requests
from apprise import Apprise
from apprise import AppriseAttachment
from apprise import plugins
from apprise import NotifyType
from apprise import NotifyFormat

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Attachment Directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), 'var')


@mock.patch('requests.post')
def test_discord_plugin(mock_post):
    """
    API: NotifyDiscord() General Checks

    """
    # Disable Throttling to speed testing
    plugins.NotifyBase.request_rate_per_sec = 0

    # Initialize some generic (but valid) tokens
    webhook_id = 'A' * 24
    webhook_token = 'B' * 64

    # Prepare Mock
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok

    # Invalid webhook id
    with pytest.raises(TypeError):
        plugins.NotifyDiscord(webhook_id=None, webhook_token=webhook_token)
    # Invalid webhook id (whitespace)
    with pytest.raises(TypeError):
        plugins.NotifyDiscord(webhook_id="  ", webhook_token=webhook_token)

    # Invalid webhook token
    with pytest.raises(TypeError):
        plugins.NotifyDiscord(webhook_id=webhook_id, webhook_token=None)
    # Invalid webhook token (whitespace)
    with pytest.raises(TypeError):
        plugins.NotifyDiscord(webhook_id=webhook_id, webhook_token="   ")

    obj = plugins.NotifyDiscord(
        webhook_id=webhook_id,
        webhook_token=webhook_token,
        footer=True, thumbnail=False)

    # Test that we get a string response
    assert isinstance(obj.url(), six.string_types) is True

    # This call includes an image with it's payload:
    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO) is True

    # Simple Markdown Single line of text
    test_markdown = "body"
    desc, results = obj.extract_markdown_sections(test_markdown)
    assert isinstance(results, list) is True
    assert len(results) == 0

    # Test our header parsing when not lead with a header
    test_markdown = """
    A section of text that has no header at the top.
    It also has a hash tag # <- in the middle of a
    string.

    ## Heading 1
    body

    # Heading 2

    more content
    on multi-lines
    """

    desc, results = obj.extract_markdown_sections(test_markdown)
    # we have a description
    assert isinstance(desc, six.string_types) is True
    assert desc.startswith('A section of text that has no header at the top.')
    assert desc.endswith('string.')

    assert isinstance(results, list) is True
    assert len(results) == 2
    assert results[0]['name'] == 'Heading 1'
    assert results[0]['value'] == '```md\nbody\n```'
    assert results[1]['name'] == 'Heading 2'
    assert results[1]['value'] == \
        '```md\nmore content\n    on multi-lines\n```'

    # Test our header parsing
    test_markdown = "## Heading one\nbody body\n\n" + \
        "# Heading 2 ##\n\nTest\n\n" + \
        "more content\n" + \
        "even more content  \t\r\n\n\n" + \
        "# Heading 3 ##\n\n\n" + \
        "normal content\n" + \
        "# heading 4\n" + \
        "#### Heading 5"

    desc, results = obj.extract_markdown_sections(test_markdown)
    assert isinstance(results, list) is True
    # No desc details filled out
    assert isinstance(desc, six.string_types) is True
    assert not desc

    # We should have 5 sections (since there are 5 headers identified above)
    assert len(results) == 5
    assert results[0]['name'] == 'Heading one'
    assert results[0]['value'] == '```md\nbody body\n```'
    assert results[1]['name'] == 'Heading 2'
    assert results[1]['value'] == \
        '```md\nTest\n\nmore content\neven more content\n```'
    assert results[2]['name'] == 'Heading 3'
    assert results[2]['value'] == \
        '```md\nnormal content\n```'
    assert results[3]['name'] == 'heading 4'
    assert results[3]['value'] == '```\n```'
    assert results[4]['name'] == 'Heading 5'
    assert results[4]['value'] == '```\n```'

    # Create an apprise instance
    a = Apprise()

    # Our processing is slightly different when we aren't using markdown
    # as we do not pre-parse content during our notifications
    assert a.add(
        'discord://{webhook_id}/{webhook_token}/'
        '?format=markdown&footer=Yes'.format(
            webhook_id=webhook_id,
            webhook_token=webhook_token)) is True

    # This call includes an image with it's payload:
    plugins.NotifyDiscord.discord_max_fields = 1

    assert a.notify(body=test_markdown, title='title',
                    notify_type=NotifyType.INFO,
                    body_format=NotifyFormat.TEXT) is True

    # Throw an exception on the forth call to requests.post()
    # This allows to test our batch field processing
    response = mock.Mock()
    response.content = ''
    response.status_code = requests.codes.ok
    mock_post.return_value = response
    mock_post.side_effect = [
        response, response, response, requests.RequestException()]

    # Test our markdown
    obj = Apprise.instantiate(
        'discord://{}/{}/?format=markdown'.format(webhook_id, webhook_token))
    assert isinstance(obj, plugins.NotifyDiscord)
    assert obj.notify(
        body=test_markdown, title='title',
        notify_type=NotifyType.INFO) is False
    mock_post.side_effect = None

    # Empty String
    desc, results = obj.extract_markdown_sections("")
    assert isinstance(results, list) is True
    assert len(results) == 0

    # No desc details filled out
    assert isinstance(desc, six.string_types) is True
    assert not desc

    # String without Heading
    test_markdown = "Just a string without any header entries.\n" + \
        "A second line"
    desc, results = obj.extract_markdown_sections(test_markdown)
    assert isinstance(results, list) is True
    assert len(results) == 0

    # No desc details filled out
    assert isinstance(desc, six.string_types) is True
    assert desc == 'Just a string without any header entries.\n' + \
        'A second line'

    # Use our test markdown string during a notification
    assert obj.notify(
        body=test_markdown, title='title', notify_type=NotifyType.INFO) is True

    # Create an apprise instance
    a = Apprise()

    # Our processing is slightly different when we aren't using markdown
    # as we do not pre-parse content during our notifications
    assert a.add(
        'discord://{webhook_id}/{webhook_token}/'
        '?format=markdown&footer=Yes'.format(
            webhook_id=webhook_id,
            webhook_token=webhook_token)) is True

    # This call includes an image with it's payload:
    assert a.notify(body=test_markdown, title='title',
                    notify_type=NotifyType.INFO,
                    body_format=NotifyFormat.TEXT) is True

    assert a.notify(body=test_markdown, title='title',
                    notify_type=NotifyType.INFO,
                    body_format=NotifyFormat.MARKDOWN) is True

    # Toggle our logo availability
    a.asset.image_url_logo = None
    assert a.notify(
        body='body', title='title', notify_type=NotifyType.INFO) is True


@mock.patch('requests.post')
def test_discord_attachments(mock_post):
    """
    API: NotifyDiscord() Attachment Checks

    """
    # Disable Throttling to speed testing
    plugins.NotifyBase.request_rate_per_sec = 0

    # Initialize some generic (but valid) tokens
    webhook_id = 'C' * 24
    webhook_token = 'D' * 64

    # Prepare Mock return object
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok

    # Test our markdown
    obj = Apprise.instantiate(
        'discord://{}/{}/?format=markdown'.format(webhook_id, webhook_token))

    # attach our content
    attach = AppriseAttachment(os.path.join(TEST_VAR_DIR, 'apprise-test.gif'))

    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO,
        attach=attach) is True

    # An invalid attachment will cause a failure
    path = os.path.join(TEST_VAR_DIR, '/invalid/path/to/an/invalid/file.jpg')
    attach = AppriseAttachment(path)
    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO,
        attach=path) is False

    # Throw an exception on the second call to requests.post()
    mock_post.return_value = None
    response = mock.Mock()
    response.status_code = requests.codes.ok
    mock_post.side_effect = [response, OSError()]

    # update our attachment to be valid
    attach = AppriseAttachment(os.path.join(TEST_VAR_DIR, 'apprise-test.gif'))
    # Test our markdown

    # We'll fail now because of an internal exception
    assert obj.send(body="test", attach=attach) is False
