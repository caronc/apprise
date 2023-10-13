# -*- coding: utf-8 -*-
# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2023, Chris Caron <lead2gold@gmail.com>
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

import os
from unittest import mock
from datetime import datetime, timedelta
from datetime import timezone
import pytest
import requests

from apprise.plugins.NotifyDiscord import NotifyDiscord
from helpers import AppriseURLTester
from apprise import Apprise
from apprise import AppriseAttachment
from apprise import NotifyType
from apprise import NotifyFormat

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Attachment Directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), 'var')

# Our Testing URLs
apprise_url_tests = (
    ('discord://', {
        'instance': TypeError,
    }),
    # An invalid url
    ('discord://:@/', {
        'instance': TypeError,
    }),
    # No webhook_token specified
    ('discord://%s' % ('i' * 24), {
        'instance': TypeError,
    }),
    # Provide both an webhook id and a webhook token
    ('discord://%s/%s' % ('i' * 24, 't' * 64), {
        'instance': NotifyDiscord,
        'requests_response_code': requests.codes.no_content,
    }),
    # Provide a temporary username
    ('discord://l2g@%s/%s' % ('i' * 24, 't' * 64), {
        'instance': NotifyDiscord,
        'requests_response_code': requests.codes.no_content,
    }),
    # test image= field
    ('discord://%s/%s?format=markdown&footer=Yes&image=Yes' % (
        'i' * 24, 't' * 64), {
            'instance': NotifyDiscord,
            'requests_response_code': requests.codes.no_content,
            # don't include an image by default
            'include_image': False,
    }),
    ('discord://%s/%s?format=markdown&footer=Yes&image=No&fields=no' % (
        'i' * 24, 't' * 64), {
            'instance': NotifyDiscord,
            'requests_response_code': requests.codes.no_content,
    }),
    ('discord://%s/%s?format=markdown&footer=Yes&image=Yes' % (
        'i' * 24, 't' * 64), {
            'instance': NotifyDiscord,
            'requests_response_code': requests.codes.no_content,
    }),
    ('https://discord.com/api/webhooks/{}/{}'.format(
        '0' * 10, 'B' * 40), {
            # Native URL Support, support the provided discord URL from their
            # webpage.
            'instance': NotifyDiscord,
            'requests_response_code': requests.codes.no_content,
    }),
    ('https://discordapp.com/api/webhooks/{}/{}'.format(
        '0' * 10, 'B' * 40), {
            # Legacy Native URL Support, support the older URL (to be
            # decomissioned on Nov 7th 2020)
            'instance': NotifyDiscord,
            'requests_response_code': requests.codes.no_content,
    }),
    ('https://discordapp.com/api/webhooks/{}/{}?footer=yes'.format(
        '0' * 10, 'B' * 40), {
            # Native URL Support with arguments
            'instance': NotifyDiscord,
            'requests_response_code': requests.codes.no_content,
    }),
    ('discord://%s/%s?format=markdown&avatar=No&footer=No' % (
        'i' * 24, 't' * 64), {
            'instance': NotifyDiscord,
            'requests_response_code': requests.codes.no_content,
    }),
    # different format support
    ('discord://%s/%s?format=markdown' % ('i' * 24, 't' * 64), {
        'instance': NotifyDiscord,
        'requests_response_code': requests.codes.no_content,
    }),
    # Thread ID
    ('discord://%s/%s?format=markdown&thread=abc123' % (
        'i' * 24, 't' * 64), {
            'instance': NotifyDiscord,
            'requests_response_code': requests.codes.no_content,
    }),
    ('discord://%s/%s?format=text' % ('i' * 24, 't' * 64), {
        'instance': NotifyDiscord,
        'requests_response_code': requests.codes.no_content,
    }),
    # Test with href (title link)
    ('discord://%s/%s?hmarkdown=true&ref=http://localhost' % (
        'i' * 24, 't' * 64), {
            'instance': NotifyDiscord,
            'requests_response_code': requests.codes.no_content,
    }),
    # Test with url (title link) - Alias of href
    ('discord://%s/%s?markdown=true&url=http://localhost' % (
        'i' * 24, 't' * 64), {
            'instance': NotifyDiscord,
            'requests_response_code': requests.codes.no_content,
    }),
    # Test with avatar URL
    ('discord://%s/%s?avatar_url=http://localhost/test.jpg' % (
        'i' * 24, 't' * 64), {
            'instance': NotifyDiscord,
            'requests_response_code': requests.codes.no_content,
    }),
    # Test without image set
    ('discord://%s/%s' % ('i' * 24, 't' * 64), {
        'instance': NotifyDiscord,
        'requests_response_code': requests.codes.no_content,
        # don't include an image by default
        'include_image': False,
    }),
    ('discord://%s/%s/' % ('a' * 24, 'b' * 64), {
        'instance': NotifyDiscord,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('discord://%s/%s/' % ('a' * 24, 'b' * 64), {
        'instance': NotifyDiscord,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('discord://%s/%s/' % ('a' * 24, 'b' * 64), {
        'instance': NotifyDiscord,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_discord_urls():
    """
    NotifyDiscord() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch('requests.post')
def test_plugin_discord_general(mock_post):
    """
    NotifyDiscord() General Checks

    """

    # Turn off clock skew for local testing
    NotifyDiscord.clock_skew = timedelta(seconds=0)
    # Epoch time:
    epoch = datetime.fromtimestamp(0, timezone.utc)

    # Initialize some generic (but valid) tokens
    webhook_id = 'A' * 24
    webhook_token = 'B' * 64

    # Prepare Mock
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok
    mock_post.return_value.content = ''
    mock_post.return_value.headers = {
        'X-RateLimit-Reset': (
            datetime.now(timezone.utc) - epoch).total_seconds(),
        'X-RateLimit-Remaining': 1,
    }

    # Invalid webhook id
    with pytest.raises(TypeError):
        NotifyDiscord(webhook_id=None, webhook_token=webhook_token)
    # Invalid webhook id (whitespace)
    with pytest.raises(TypeError):
        NotifyDiscord(webhook_id="  ", webhook_token=webhook_token)

    # Invalid webhook token
    with pytest.raises(TypeError):
        NotifyDiscord(webhook_id=webhook_id, webhook_token=None)
    # Invalid webhook token (whitespace)
    with pytest.raises(TypeError):
        NotifyDiscord(webhook_id=webhook_id, webhook_token="   ")

    obj = NotifyDiscord(
        webhook_id=webhook_id,
        webhook_token=webhook_token,
        footer=True, thumbnail=False)
    assert obj.ratelimit_remaining == 1

    # Test that we get a string response
    assert isinstance(obj.url(), str) is True

    # This call includes an image with it's payload:
    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO) is True

    # Force a case where there are no more remaining posts allowed
    mock_post.return_value.headers = {
        'X-RateLimit-Reset': (
            datetime.now(timezone.utc) - epoch).total_seconds(),
        'X-RateLimit-Remaining': 0,
    }

    # This call includes an image with it's payload:
    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO) is True

    # behind the scenes, it should cause us to update our rate limit
    assert obj.send(body="test") is True
    assert obj.ratelimit_remaining == 0

    # This should cause us to block
    mock_post.return_value.headers = {
        'X-RateLimit-Reset': (
            datetime.now(timezone.utc) - epoch).total_seconds(),
        'X-RateLimit-Remaining': 10,
    }
    assert obj.send(body="test") is True
    assert obj.ratelimit_remaining == 10

    # Reset our variable back to 1
    mock_post.return_value.headers = {
        'X-RateLimit-Reset': (
            datetime.now(timezone.utc) - epoch).total_seconds(),
        'X-RateLimit-Remaining': 1,
    }
    # Handle cases where our epoch time is wrong
    del mock_post.return_value.headers['X-RateLimit-Reset']
    assert obj.send(body="test") is True

    # Return our object, but place it in the future forcing us to block
    mock_post.return_value.headers = {
        'X-RateLimit-Reset': (
            datetime.now(timezone.utc) - epoch).total_seconds() + 1,
        'X-RateLimit-Remaining': 0,
    }

    obj.ratelimit_remaining = 0
    assert obj.send(body="test") is True

    # Test 429 error response
    mock_post.return_value.status_code = requests.codes.too_many_requests

    # The below will attempt a second transmission and fail (because we didn't
    # set up a second post request to pass) :)
    assert obj.send(body="test") is False

    # Return our object, but place it in the future forcing us to block
    mock_post.return_value.status_code = requests.codes.ok
    mock_post.return_value.headers = {
        'X-RateLimit-Reset': (
            datetime.now(timezone.utc) - epoch).total_seconds() - 1,
        'X-RateLimit-Remaining': 0,
    }
    assert obj.send(body="test") is True

    # Return our limits to always work
    obj.ratelimit_remaining = 1

    # Return our headers to normal
    mock_post.return_value.headers = {
        'X-RateLimit-Reset': (
            datetime.now(timezone.utc) - epoch).total_seconds(),
        'X-RateLimit-Remaining': 1,
    }

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
    assert isinstance(desc, str) is True
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
    assert isinstance(desc, str) is True
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
    NotifyDiscord.discord_max_fields = 1

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
    assert isinstance(obj, NotifyDiscord)
    assert obj.notify(
        body=test_markdown, title='title',
        notify_type=NotifyType.INFO) is False
    mock_post.side_effect = None

    # Empty String
    desc, results = obj.extract_markdown_sections("")
    assert isinstance(results, list) is True
    assert len(results) == 0

    # No desc details filled out
    assert isinstance(desc, str) is True
    assert not desc

    # String without Heading
    test_markdown = "Just a string without any header entries.\n" + \
        "A second line"
    desc, results = obj.extract_markdown_sections(test_markdown)
    assert isinstance(results, list) is True
    assert len(results) == 0

    # No desc details filled out
    assert isinstance(desc, str) is True
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

    # Create an apprise instance
    a = Apprise()

    # Reset our object
    mock_post.reset_mock()

    # Test our threading
    assert a.add(
        'discord://{webhook_id}/{webhook_token}/'
        '?thread=12345'.format(
            webhook_id=webhook_id,
            webhook_token=webhook_token)) is True

    # This call includes an image with it's payload:
    assert a.notify(body='test', title='title') is True

    assert mock_post.call_count == 1
    response = mock_post.call_args_list[0][1]
    assert 'params' in response
    assert response['params'].get('thread_id') == '12345'


@mock.patch('requests.post')
def test_plugin_discord_markdown_extra(mock_post):
    """
    NotifyDiscord() Markdown Extra Checks

    """

    # Initialize some generic (but valid) tokens
    webhook_id = 'A' * 24
    webhook_token = 'B' * 64

    # Prepare Mock
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok

    # Reset our apprise object
    a = Apprise()

    # We want to further test our markdown support to accomodate bug rased on
    # 2022.10.25; see https://github.com/caronc/apprise/issues/717
    assert a.add(
        'discord://{webhook_id}/{webhook_token}/'
        '?format=markdown&footer=Yes'.format(
            webhook_id=webhook_id,
            webhook_token=webhook_token)) is True

    test_markdown = "[green-blue](https://google.com)"

    # This call includes an image with it's payload:
    assert a.notify(body=test_markdown, title='title',
                    notify_type=NotifyType.INFO,
                    body_format=NotifyFormat.TEXT) is True

    assert a.notify(
        body='body', title='title', notify_type=NotifyType.INFO) is True


@mock.patch('requests.post')
def test_plugin_discord_attachments(mock_post):
    """
    NotifyDiscord() Attachment Checks

    """

    # Initialize some generic (but valid) tokens
    webhook_id = 'C' * 24
    webhook_token = 'D' * 64

    # Prepare a good response
    response = mock.Mock()
    response.status_code = requests.codes.ok

    # Prepare a bad response
    bad_response = mock.Mock()
    bad_response.status_code = requests.codes.internal_server_error

    # Prepare Mock return object
    mock_post.return_value = response

    # Test our markdown
    obj = Apprise.instantiate(
        'discord://{}/{}/?format=markdown'.format(webhook_id, webhook_token))

    # attach our content
    attach = AppriseAttachment(os.path.join(TEST_VAR_DIR, 'apprise-test.gif'))

    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO,
        attach=attach) is True

    # Test our call count
    assert mock_post.call_count == 2
    assert mock_post.call_args_list[0][0][0] == \
        'https://discord.com/api/webhooks/{}/{}'.format(
            webhook_id, webhook_token)
    assert mock_post.call_args_list[1][0][0] == \
        'https://discord.com/api/webhooks/{}/{}'.format(
            webhook_id, webhook_token)

    # An invalid attachment will cause a failure
    path = os.path.join(TEST_VAR_DIR, '/invalid/path/to/an/invalid/file.jpg')
    attach = AppriseAttachment(path)
    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO,
        attach=path) is False

    # update our attachment to be valid
    attach = AppriseAttachment(os.path.join(TEST_VAR_DIR, 'apprise-test.gif'))

    mock_post.return_value = None
    # Throw an exception on the first call to requests.post()
    for side_effect in (requests.RequestException(), OSError(), bad_response):
        mock_post.side_effect = [side_effect]

        # We'll fail now because of our error handling
        assert obj.send(body="test", attach=attach) is False

    # Throw an exception on the second call to requests.post()
    for side_effect in (requests.RequestException(), OSError(), bad_response):
        mock_post.side_effect = [response, side_effect]

        # We'll fail now because of our error handling
        assert obj.send(body="test", attach=attach) is False

    # handle a bad response
    bad_response = mock.Mock()
    bad_response.status_code = requests.codes.internal_server_error
    mock_post.side_effect = [response, bad_response]

    # We'll fail now because of an internal exception
    assert obj.send(body="test", attach=attach) is False
