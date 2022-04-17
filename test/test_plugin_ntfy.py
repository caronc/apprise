# -*- coding: utf-8 -*-
#
# Copyright (C) 2022 Chris Caron <lead2gold@gmail.com>
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
import json
import mock
import requests
from apprise import Apprise
from apprise import plugins
from apprise import NotifyType
from helpers import AppriseURLTester
from apprise import AppriseAttachment

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Attachment Directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), 'var')

# For testing our return response
GOOD_RESPONSE_TEXT = {
    'code': '0',
    'error': 'success',
}

# Our Testing URLs
apprise_url_tests = (
    ('ntfy://', {
        # Initializes okay (as cloud mode) but has no topics to notify
        'instance': plugins.NotifyNtfy,
        # invalid topics specified (nothing to notify)
        # as a result the response type will be false
        'requests_response_text': GOOD_RESPONSE_TEXT,
        'response': False,
    }),
    ('ntfys://', {
        # Initializes okay (as cloud mode) but has no topics to notify
        'instance': plugins.NotifyNtfy,
        # invalid topics specified (nothing to notify)
        # as a result the response type will be false
        'requests_response_text': GOOD_RESPONSE_TEXT,
        'response': False,
    }),
    ('ntfy://:@/', {
        # Initializes okay (as cloud mode) but has no topics to notify
        'instance': plugins.NotifyNtfy,
        # invalid topics specified (nothing to notify)
        # as a result the response type will be false
        'requests_response_text': GOOD_RESPONSE_TEXT,
        'response': False,
    }),
    # No topics
    ('ntfy://user:pass@localhost?mode=private', {
        'instance': plugins.NotifyNtfy,
        # invalid topics specified (nothing to notify)
        # as a result the response type will be false
        'requests_response_text': GOOD_RESPONSE_TEXT,
        'response': False,
    }),
    # No valid topics
    ('ntfy://user:pass@localhost/#/!/@', {
        'instance': plugins.NotifyNtfy,
        # invalid topics specified (nothing to notify)
        # as a result the response type will be false
        'requests_response_text': GOOD_RESPONSE_TEXT,
        'response': False,
    }),
    # user/pass combos
    ('ntfy://user@localhost/topic/', {
        'instance': plugins.NotifyNtfy,
        'requests_response_text': GOOD_RESPONSE_TEXT,
    }),
    # Ntfy cloud mode (enforced)
    ('ntfy://ntfy.sh/topic1/topic2/', {
        'instance': plugins.NotifyNtfy,
        'requests_response_text': GOOD_RESPONSE_TEXT,
    }),
    # No user/pass combo
    ('ntfy://localhost/topic1/topic2/', {
        'instance': plugins.NotifyNtfy,
        'requests_response_text': GOOD_RESPONSE_TEXT,
    }),
    # A Email Testing
    ('ntfy://localhost/topic1/?email=user@gmail.com', {
        'instance': plugins.NotifyNtfy,
        'requests_response_text': GOOD_RESPONSE_TEXT,
    }),
    # Tags
    ('ntfy://localhost/topic1/?tags=tag1,tag2,tag3', {
        'instance': plugins.NotifyNtfy,
        'requests_response_text': GOOD_RESPONSE_TEXT,
    }),
    # Delay
    ('ntfy://localhost/topic1/?delay=3600', {
        'instance': plugins.NotifyNtfy,
        'requests_response_text': GOOD_RESPONSE_TEXT,
    }),
    # Title
    ('ntfy://localhost/topic1/?title=A%20Great%20Title', {
        'instance': plugins.NotifyNtfy,
        'requests_response_text': GOOD_RESPONSE_TEXT,
    }),
    # Click
    ('ntfy://localhost/topic1/?click=yes', {
        'instance': plugins.NotifyNtfy,
        'requests_response_text': GOOD_RESPONSE_TEXT,
    }),
    # Email
    ('ntfy://localhost/topic1/?email=user@example.com', {
        'instance': plugins.NotifyNtfy,
        'requests_response_text': GOOD_RESPONSE_TEXT,
    }),
    # Attach
    ('ntfy://localhost/topic1/?attach=http://example.com/file.jpg', {
        'instance': plugins.NotifyNtfy,
        'requests_response_text': GOOD_RESPONSE_TEXT,
    }),
    # Attach with filename over-ride
    ('ntfy://localhost/topic1/'
     '?attach=http://example.com/file.jpg&filename=smoke.jpg', {
         'instance': plugins.NotifyNtfy,
         'requests_response_text': GOOD_RESPONSE_TEXT}),
    # Attach with bad url
    ('ntfy://localhost/topic1/?attach=http://-%20', {
        'instance': plugins.NotifyNtfy,
        'requests_response_text': GOOD_RESPONSE_TEXT,
    }),
    # Priority
    ('ntfy://localhost/topic1/?priority=default', {
        'instance': plugins.NotifyNtfy,
        'requests_response_text': GOOD_RESPONSE_TEXT,
    }),
    # Priority higher
    ('ntfy://localhost/topic1/?priority=high', {
        'instance': plugins.NotifyNtfy,
        'requests_response_text': GOOD_RESPONSE_TEXT,
    }),
    # Invalid Priority
    ('ntfy://localhost/topic1/?priority=invalid', {
        'instance': TypeError,
    }),
    # A topic and port identifier
    ('ntfy://user:pass@localhost:8080/topic/', {
        'instance': plugins.NotifyNtfy,
        # The response text is expected to be the following on a success
        'requests_response_text': GOOD_RESPONSE_TEXT,
    }),
    # A topic (using the to=)
    ('ntfys://user:pass@localhost?to=topic', {
        'instance': plugins.NotifyNtfy,
        # The response text is expected to be the following on a success
        'requests_response_text': GOOD_RESPONSE_TEXT,
    }),
    ('https://just/a/random/host/that/means/nothing', {
        # Nothing transpires from this
        'instance': None
    }),
    # reference the ntfy.sh url
    ('https://ntfy.sh?to=topic', {
        'instance': plugins.NotifyNtfy,
        # The response text is expected to be the following on a success
        'requests_response_text': GOOD_RESPONSE_TEXT,
    }),
    # Several topics
    ('ntfy://user:pass@topic1/topic2/topic3/?mode=cloud', {
        'instance': plugins.NotifyNtfy,
        # The response text is expected to be the following on a success
        'requests_response_text': GOOD_RESPONSE_TEXT,
    }),
    # Several topics (but do not add ntfy.sh)
    ('ntfy://user:pass@ntfy.sh/topic1/topic2/?mode=cloud', {
        'instance': plugins.NotifyNtfy,
        # The response text is expected to be the following on a success
        'requests_response_text': GOOD_RESPONSE_TEXT,
    }),
    ('ntfys://user:web/token@localhost/topic/?mode=invalid', {
        # Invalid mode
        'instance': TypeError,
    }),
    # Invalid hostname on localhost/private mode
    ('ntfys://user:web@-_/topic1/topic2/?mode=private', {
        'instance': None,
    }),
    ('ntfy://user:pass@localhost:8089/topic/topic2', {
        'instance': plugins.NotifyNtfy,
        # force a failure using basic mode
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('ntfy://user:pass@localhost:8082/topic', {
        'instance': plugins.NotifyNtfy,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
        'requests_response_text': GOOD_RESPONSE_TEXT,
    }),
    ('ntfy://user:pass@localhost:8083/topic1/topic2/', {
        'instance': plugins.NotifyNtfy,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
        'requests_response_text': GOOD_RESPONSE_TEXT,
    }),
)


def test_plugin_ntfy_chat_urls():
    """
    NotifyNtfy() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch('requests.post')
def test_plugin_ntfy_attachments(mock_post):
    """
    NotifyNtfy() Attachment Checks

    """
    # Disable Throttling to speed testing
    plugins.NotifyNtfy.request_rate_per_sec = 0

    # Prepare Mock return object
    response = mock.Mock()
    response.content = GOOD_RESPONSE_TEXT
    response.status_code = requests.codes.ok
    mock_post.return_value = response

    # prepare our attachment
    attach = AppriseAttachment(os.path.join(TEST_VAR_DIR, 'apprise-test.gif'))

    # Prepare our object
    obj = Apprise.instantiate(
        'ntfy://user:pass@localhost:8084/topic')

    # Send a good attachment
    assert obj.notify(body="test", attach=attach) is True

    # Test our call count (one for the message, and two for the attachment)
    assert mock_post.call_count == 2

    # Image Send
    assert mock_post.call_args_list[1][0][0] == \
        'http://localhost:8084/topic'
    # Message
    assert mock_post.call_args_list[0][0][0] == \
        'http://localhost:8084/topic'

    # Reset our mock object
    mock_post.reset_mock()

    # Add another attachment so we drop into the area of the PushBullet code
    # that sends remaining attachments (if more detected)
    attach.add(os.path.join(TEST_VAR_DIR, 'apprise-test.gif'))

    # Send our attachments
    assert obj.notify(body="test", attach=attach) is True

    # Test our call count
    assert mock_post.call_count == 3
    # Image Send
    assert mock_post.call_args_list[0][0][0] == \
        'http://localhost:8084/topic'
    assert mock_post.call_args_list[0][0][0] == \
        'http://localhost:8084/topic'
    # Message
    assert mock_post.call_args_list[1][0][0] == \
        'http://localhost:8084/topic'

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

    # Throw an exception on the first call to requests.post()
    mock_post.return_value = None
    for side_effect in (requests.RequestException(), OSError()):
        mock_post.side_effect = side_effect

        # We'll fail now because of our error handling
        assert obj.send(body="test", attach=attach) is False


@mock.patch('requests.post')
def test_plugin_custom_ntfy_edge_cases(mock_post):
    """
    NotifyNtfy() Edge Cases

    """
    # Disable Throttling to speed testing
    plugins.NotifyBase.request_rate_per_sec = 0

    # Prepare our response
    response = requests.Request()
    response.status_code = requests.codes.ok
    response.content = json.dumps(GOOD_RESPONSE_TEXT)

    # Prepare Mock
    mock_post.return_value = response

    results = plugins.NotifyNtfy.parse_url(
        'ntfys://abc---,topic2,~~,,?priority=max&tags=smile,de')

    assert isinstance(results, dict)
    assert results['user'] is None
    assert results['password'] is None
    assert results['port'] is None
    assert results['host'] == 'abc---,topic2,~~,,'
    assert results['fullpath'] is None
    assert results['path'] is None
    assert results['query'] is None
    assert results['schema'] == 'ntfys'
    assert results['url'] == 'ntfys://abc---,topic2,~~,,'
    assert isinstance(results['qsd:'], dict) is True
    assert results['qsd']['priority'] == 'max'
    assert results['qsd']['tags'] == 'smile,de'

    instance = plugins.NotifyNtfy(**results)
    assert isinstance(instance, plugins.NotifyNtfy)
    assert len(instance.topics) == 2
    assert 'abc---' in instance.topics
    assert 'topic2' in instance.topics

    results = plugins.NotifyNtfy.parse_url(
        'ntfy://localhost/topic1/'
        '?attach=http://example.com/file.jpg&filename=smoke.jpg')

    assert isinstance(results, dict)
    assert results['user'] is None
    assert results['password'] is None
    assert results['port'] is None
    assert results['host'] == 'localhost'
    assert results['fullpath'] == '/topic1'
    assert results['path'] == '/'
    assert results['query'] == 'topic1'
    assert results['schema'] == 'ntfy'
    assert results['url'] == 'ntfy://localhost/topic1'
    assert results['attach'] == 'http://example.com/file.jpg'
    assert results['filename'] == 'smoke.jpg'

    instance = plugins.NotifyNtfy(**results)
    assert isinstance(instance, plugins.NotifyNtfy)
    assert len(instance.topics) == 1
    assert 'topic1' in instance.topics

    assert instance.notify(
        body='body', title='title', notify_type=NotifyType.INFO) is True

    # Test our call count
    assert mock_post.call_count == 1
    assert mock_post.call_args_list[0][0][0] == \
        'http://localhost/topic1'
    assert mock_post.call_args_list[0][1]['headers'].get('X-Attach') == \
        'http://example.com/file.jpg'
    assert mock_post.call_args_list[0][1]['headers'].get('X-Filename') == \
        'smoke.jpg'
