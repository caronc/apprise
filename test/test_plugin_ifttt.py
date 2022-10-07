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
import pytest
from unittest import mock

import requests
from apprise import plugins
from apprise import NotifyType
from helpers import AppriseURLTester

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    ('ifttt://', {
        'instance': TypeError,
    }),
    ('ifttt://:@/', {
        'instance': TypeError,
    }),
    # No User
    ('ifttt://EventID/', {
        'instance': TypeError,
    }),
    # A nicely formed ifttt url with 1 event and a new key/value store
    ('ifttt://WebHookID@EventID/?+TemplateKey=TemplateVal', {
        'instance': plugins.NotifyIFTTT,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'ifttt://W...D',
    }),
    # Test to= in which case we set the host to the webhook id
    ('ifttt://WebHookID?to=EventID,EventID2', {
        'instance': plugins.NotifyIFTTT,
    }),
    # Removing certain keys:
    ('ifttt://WebHookID@EventID/?-Value1=&-Value2', {
        'instance': plugins.NotifyIFTTT,
    }),
    # A nicely formed ifttt url with 2 events defined:
    ('ifttt://WebHookID@EventID/EventID2/', {
        'instance': plugins.NotifyIFTTT,
    }),
    # Support Native URL references
    ('https://maker.ifttt.com/use/WebHookID/', {
        # No EventID specified
        'instance': TypeError,
    }),
    ('https://maker.ifttt.com/use/WebHookID/EventID/', {
        'instance': plugins.NotifyIFTTT,
    }),
    #  Native URL with arguments
    ('https://maker.ifttt.com/use/WebHookID/EventID/?-Value1=', {
        'instance': plugins.NotifyIFTTT,
    }),
    # Test website connection failures
    ('ifttt://WebHookID@EventID', {
        'instance': plugins.NotifyIFTTT,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('ifttt://WebHookID@EventID', {
        'instance': plugins.NotifyIFTTT,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('ifttt://WebHookID@EventID', {
        'instance': plugins.NotifyIFTTT,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_ifttt_urls():
    """
    NotifyIFTTT() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch('requests.get')
@mock.patch('requests.post')
def test_plugin_ifttt_edge_cases(mock_post, mock_get):
    """
    NotifyIFTTT() Edge Cases

    """
    # Disable Throttling to speed testing
    plugins.NotifyBase.request_rate_per_sec = 0

    # Initialize some generic (but valid) tokens
    webhook_id = 'webhook_id'
    events = ['event1', 'event2']

    # Prepare Mock
    mock_get.return_value = requests.Request()
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok
    mock_get.return_value.status_code = requests.codes.ok
    mock_get.return_value.content = '{}'
    mock_post.return_value.content = '{}'

    # No webhook_id specified
    with pytest.raises(TypeError):
        plugins.NotifyIFTTT(webhook_id=None, events=None)

    # Disable Throttling to speed testing
    plugins.NotifyBase.request_rate_per_sec = 0

    # Initializes the plugin with an invalid webhook id
    with pytest.raises(TypeError):
        plugins.NotifyIFTTT(webhook_id=None, events=events)

    # Whitespace also acts as an invalid webhook id
    with pytest.raises(TypeError):
        plugins.NotifyIFTTT(webhook_id="   ", events=events)

    # No events specified
    with pytest.raises(TypeError):
        plugins.NotifyIFTTT(webhook_id=webhook_id, events=None)

    obj = plugins.NotifyIFTTT(webhook_id=webhook_id, events=events)
    assert isinstance(obj, plugins.NotifyIFTTT) is True

    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO) is True

    # Test the addition of tokens
    obj = plugins.NotifyIFTTT(
        webhook_id=webhook_id, events=events,
        add_tokens={'Test': 'ValueA', 'Test2': 'ValueB'})

    assert isinstance(obj, plugins.NotifyIFTTT) is True

    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO) is True

    # Invalid del_tokens entry
    with pytest.raises(TypeError):
        plugins.NotifyIFTTT(
            webhook_id=webhook_id, events=events,
            del_tokens=plugins.NotifyIFTTT.ifttt_default_title_key)

    assert isinstance(obj, plugins.NotifyIFTTT) is True

    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO) is True

    # Test removal of tokens by a list
    obj = plugins.NotifyIFTTT(
        webhook_id=webhook_id, events=events,
        add_tokens={
            'MyKey': 'MyValue'
        },
        del_tokens=(
            plugins.NotifyIFTTT.ifttt_default_title_key,
            plugins.NotifyIFTTT.ifttt_default_body_key,
            plugins.NotifyIFTTT.ifttt_default_type_key))

    assert isinstance(obj, plugins.NotifyIFTTT) is True

    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO) is True

    # Test removal of tokens as dict
    obj = plugins.NotifyIFTTT(
        webhook_id=webhook_id, events=events,
        add_tokens={
            'MyKey': 'MyValue'
        },
        del_tokens={
            plugins.NotifyIFTTT.ifttt_default_title_key: None,
            plugins.NotifyIFTTT.ifttt_default_body_key: None,
            plugins.NotifyIFTTT.ifttt_default_type_key: None})

    assert isinstance(obj, plugins.NotifyIFTTT) is True
