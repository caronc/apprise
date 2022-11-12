# -*- coding: utf-8 -*-
#
# Copyright (C) 2021 Chris Caron <lead2gold@gmail.com>
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
import requests
import pytest
from apprise import Apprise
from apprise.plugins.NotifyGoogleChat import NotifyGoogleChat
from helpers import AppriseURLTester
from unittest import mock
from apprise import NotifyType
from json import loads

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    ('gchat://', {
        'instance': TypeError,
    }),
    ('gchat://:@/', {
        'instance': TypeError,
    }),
    # Workspace, but not Key or Token
    ('gchat://workspace', {
        'instance': TypeError,
    }),
    # Workspace and key, but no Token
    ('gchat://workspace/key/', {
        'instance': TypeError,
    }),
    # Credentials are good
    ('gchat://workspace/key/token', {
        'instance': NotifyGoogleChat,
        'privacy_url': 'gchat://w...e/k...y/t...n',
    }),
    # Test arguments
    ('gchat://?workspace=ws&key=mykey&token=mytoken', {
        'instance': NotifyGoogleChat,
        'privacy_url': 'gchat://w...s/m...y/m...n',
    }),
    ('gchat://?workspace=ws&key=mykey&token=mytoken&thread=abc123', {
        # Test our thread key
        'instance': NotifyGoogleChat,
        'privacy_url': 'gchat://w...s/m...y/m...n/a...3',
    }),
    ('gchat://?workspace=ws&key=mykey&token=mytoken&threadKey=abc345', {
        # Test our thread key
        'instance': NotifyGoogleChat,
        'privacy_url': 'gchat://w...s/m...y/m...n/a...5',
    }),
    # Google Native Webhook URL
    ('https://chat.googleapis.com/v1/spaces/myworkspace/messages'
     '?key=mykey&token=mytoken', {
         'instance': NotifyGoogleChat,
         'privacy_url': 'gchat://m...e/m...y/m...n'}),
    ('https://chat.googleapis.com/v1/spaces/myworkspace/messages'
     '?key=mykey&token=mytoken&threadKey=mythreadkey', {
         'instance': NotifyGoogleChat,
         'privacy_url': 'gchat://m...e/m...y/m...n/m...y'}),
    ('gchat://workspace/key/token', {
        'instance': NotifyGoogleChat,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('gchat://workspace/key/token', {
        'instance': NotifyGoogleChat,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('gchat://workspace/key/token', {
        'instance': NotifyGoogleChat,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_google_chat_urls():
    """
    NotifyGoogleChat() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch('requests.post')
def test_plugin_google_chat_general(mock_post):
    """
    NotifyGoogleChat() General Checks

    """

    # Initialize some generic (but valid) tokens
    workspace = 'ws'
    key = 'key'
    threadkey = 'threadkey'
    token = 'token'

    # Prepare Mock
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok

    # Test our messaging
    obj = Apprise.instantiate(
        'gchat://{}/{}/{}'.format(workspace, key, token))
    assert isinstance(obj, NotifyGoogleChat)
    assert obj.notify(
        body="test body", title='title',
        notify_type=NotifyType.INFO) is True

    # Test our call count
    assert mock_post.call_count == 1
    assert mock_post.call_args_list[0][0][0] == \
        'https://chat.googleapis.com/v1/spaces/ws/messages'
    params = mock_post.call_args_list[0][1]['params']
    assert params.get('token') == token
    assert params.get('key') == key
    assert 'threadKey' not in params
    payload = loads(mock_post.call_args_list[0][1]['data'])
    assert payload['text'] == "title\r\ntest body"

    mock_post.reset_mock()

    # Test our messaging with the threadKey
    obj = Apprise.instantiate(
        'gchat://{}/{}/{}/{}'.format(workspace, key, token, threadkey))
    assert isinstance(obj, NotifyGoogleChat)
    assert obj.notify(
        body="test body", title='title',
        notify_type=NotifyType.INFO) is True

    # Test our call count
    assert mock_post.call_count == 1
    assert mock_post.call_args_list[0][0][0] == \
        'https://chat.googleapis.com/v1/spaces/ws/messages'
    params = mock_post.call_args_list[0][1]['params']
    assert params.get('token') == token
    assert params.get('key') == key
    assert params.get('threadKey') == threadkey
    payload = loads(mock_post.call_args_list[0][1]['data'])
    assert payload['text'] == "title\r\ntest body"


def test_plugin_google_chat_edge_case():
    """
    NotifyGoogleChat() Edge Cases

    """
    with pytest.raises(TypeError):
        NotifyGoogleChat('workspace', 'webhook', 'token', thread_key=object())
