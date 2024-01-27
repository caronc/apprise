# -*- coding: utf-8 -*-
# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2024, Chris Caron <lead2gold@gmail.com>
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
