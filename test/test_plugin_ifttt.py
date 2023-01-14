# -*- coding: utf-8 -*-
#
# Apprise - Push Notification Library.
# Copyright (C) 2023  Chris Caron <lead2gold@gmail.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor,
# Boston, MA  02110-1301, USA.
import pytest
from unittest import mock

import requests
from apprise import NotifyType
from apprise.plugins.NotifyIFTTT import NotifyIFTTT
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
        'instance': NotifyIFTTT,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'ifttt://W...D',
    }),
    # Test to= in which case we set the host to the webhook id
    ('ifttt://WebHookID?to=EventID,EventID2', {
        'instance': NotifyIFTTT,
    }),
    # Removing certain keys:
    ('ifttt://WebHookID@EventID/?-Value1=&-Value2', {
        'instance': NotifyIFTTT,
    }),
    # A nicely formed ifttt url with 2 events defined:
    ('ifttt://WebHookID@EventID/EventID2/', {
        'instance': NotifyIFTTT,
    }),
    # Support Native URL references
    ('https://maker.ifttt.com/use/WebHookID/', {
        # No EventID specified
        'instance': TypeError,
    }),
    ('https://maker.ifttt.com/use/WebHookID/EventID/', {
        'instance': NotifyIFTTT,
    }),
    #  Native URL with arguments
    ('https://maker.ifttt.com/use/WebHookID/EventID/?-Value1=', {
        'instance': NotifyIFTTT,
    }),
    # Test website connection failures
    ('ifttt://WebHookID@EventID', {
        'instance': NotifyIFTTT,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('ifttt://WebHookID@EventID', {
        'instance': NotifyIFTTT,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('ifttt://WebHookID@EventID', {
        'instance': NotifyIFTTT,
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
        NotifyIFTTT(webhook_id=None, events=None)

    # Initializes the plugin with an invalid webhook id
    with pytest.raises(TypeError):
        NotifyIFTTT(webhook_id=None, events=events)

    # Whitespace also acts as an invalid webhook id
    with pytest.raises(TypeError):
        NotifyIFTTT(webhook_id="   ", events=events)

    # No events specified
    with pytest.raises(TypeError):
        NotifyIFTTT(webhook_id=webhook_id, events=None)

    obj = NotifyIFTTT(webhook_id=webhook_id, events=events)
    assert isinstance(obj, NotifyIFTTT) is True

    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO) is True

    # Test the addition of tokens
    obj = NotifyIFTTT(
        webhook_id=webhook_id, events=events,
        add_tokens={'Test': 'ValueA', 'Test2': 'ValueB'})

    assert isinstance(obj, NotifyIFTTT) is True

    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO) is True

    # Invalid del_tokens entry
    with pytest.raises(TypeError):
        NotifyIFTTT(
            webhook_id=webhook_id, events=events,
            del_tokens=NotifyIFTTT.ifttt_default_title_key)

    assert isinstance(obj, NotifyIFTTT) is True

    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO) is True

    # Test removal of tokens by a list
    obj = NotifyIFTTT(
        webhook_id=webhook_id, events=events,
        add_tokens={
            'MyKey': 'MyValue'
        },
        del_tokens=(
            NotifyIFTTT.ifttt_default_title_key,
            NotifyIFTTT.ifttt_default_body_key,
            NotifyIFTTT.ifttt_default_type_key))

    assert isinstance(obj, NotifyIFTTT) is True

    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO) is True

    # Test removal of tokens as dict
    obj = NotifyIFTTT(
        webhook_id=webhook_id, events=events,
        add_tokens={
            'MyKey': 'MyValue'
        },
        del_tokens={
            NotifyIFTTT.ifttt_default_title_key: None,
            NotifyIFTTT.ifttt_default_body_key: None,
            NotifyIFTTT.ifttt_default_type_key: None})

    assert isinstance(obj, NotifyIFTTT) is True
