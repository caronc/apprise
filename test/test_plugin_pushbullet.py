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

import os
from unittest import mock

import pytest
import requests
from json import dumps
from apprise import Apprise
from apprise import AppriseAttachment
from apprise.plugins.NotifyPushBullet import NotifyPushBullet
from helpers import AppriseURLTester

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Attachment Directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), 'var')

# Our Testing URLs
apprise_url_tests = (
    ('pbul://', {
        'instance': TypeError,
    }),
    ('pbul://:@/', {
        'instance': TypeError,
    }),
    # APIkey
    ('pbul://%s' % ('a' * 32), {
        'instance': NotifyPushBullet,
        'check_attachments': False,
    }),
    # APIkey; but support attachment response
    ('pbul://%s' % ('a' * 32), {
        'instance': NotifyPushBullet,

        # Test what happens if a batch send fails to return a messageCount
        'requests_response_text': {
            'file_name': 'cat.jpeg',
            'file_type': 'image/jpeg',
            'file_url': 'http://file_url',
            'upload_url': 'http://upload_url',
        },
    }),
    # APIkey; attachment testing that isn't an image type
    ('pbul://%s' % ('a' * 32), {
        'instance': NotifyPushBullet,

        # Test what happens if a batch send fails to return a messageCount
        'requests_response_text': {
            'file_name': 'test.pdf',
            'file_type': 'application/pdf',
            'file_url': 'http://file_url',
            'upload_url': 'http://upload_url',
        },
    }),
    # APIkey; attachment testing were expected entry in payload is missing
    ('pbul://%s' % ('a' * 32), {
        'instance': NotifyPushBullet,

        # Test what happens if a batch send fails to return a messageCount
        'requests_response_text': {
            'file_name': 'test.pdf',
            'file_type': 'application/pdf',
            'file_url': 'http://file_url',
            # upload_url missing
        },
        # Our Notification calls associated with attachments will fail:
        'attach_response': False,
    }),
    # API Key + channel
    ('pbul://%s/#channel/' % ('a' * 32), {
        'instance': NotifyPushBullet,
        'check_attachments': False,
    }),
    # API Key + channel (via to=
    ('pbul://%s/?to=#channel' % ('a' * 32), {
        'instance': NotifyPushBullet,
        'check_attachments': False,
    }),
    # API Key + 2 channels
    ('pbul://%s/#channel1/#channel2' % ('a' * 32), {
        'instance': NotifyPushBullet,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'pbul://a...a/',
        'check_attachments': False,
    }),
    # API Key + device
    ('pbul://%s/device/' % ('a' * 32), {
        'instance': NotifyPushBullet,
        'check_attachments': False,
    }),
    # API Key + 2 devices
    ('pbul://%s/device1/device2/' % ('a' * 32), {
        'instance': NotifyPushBullet,
        'check_attachments': False,
    }),
    # API Key + email
    ('pbul://%s/user@example.com/' % ('a' * 32), {
        'instance': NotifyPushBullet,
        'check_attachments': False,
    }),
    # API Key + 2 emails
    ('pbul://%s/user@example.com/abc@def.com/' % ('a' * 32), {
        'instance': NotifyPushBullet,
        'check_attachments': False,
    }),
    # API Key + Combo
    ('pbul://%s/device/#channel/user@example.com/' % ('a' * 32), {
        'instance': NotifyPushBullet,
        'check_attachments': False,
    }),
    # ,
    ('pbul://%s' % ('a' * 32), {
        'instance': NotifyPushBullet,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
        'check_attachments': False,
    }),
    ('pbul://%s' % ('a' * 32), {
        'instance': NotifyPushBullet,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
        'check_attachments': False,
    }),
    ('pbul://%s' % ('a' * 32), {
        'instance': NotifyPushBullet,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
        'check_attachments': False,
    }),
    ('pbul://%s' % ('a' * 32), {
        'instance': NotifyPushBullet,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
        'check_attachments': False,
    }),
    ('pbul://%s' % ('a' * 32), {
        'instance': NotifyPushBullet,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
        'check_attachments': False,
    }),
    ('pbul://%s' % ('a' * 32), {
        'instance': NotifyPushBullet,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
        'check_attachments': False,
    }),
)


def test_plugin_pushbullet_urls():
    """
    NotifyPushBullet() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch('requests.post')
def test_plugin_pushbullet_attachments(mock_post):
    """
    NotifyPushBullet() Attachment Checks

    """

    # Initialize some generic (but valid) tokens
    access_token = 't' * 32

    # Prepare Mock return object
    response = mock.Mock()
    response.content = dumps({
        "file_name": "cat.jpg",
        "file_type": "image/jpeg",
        "file_url": "https://dl.pushb.com/abc/cat.jpg",
        "upload_url": "https://upload.pushbullet.com/abcd123",
    })
    response.status_code = requests.codes.ok
    mock_post.return_value = response

    # prepare our attachment
    attach = AppriseAttachment(os.path.join(TEST_VAR_DIR, 'apprise-test.gif'))

    # Test our markdown
    obj = Apprise.instantiate(
        'pbul://{}/?format=markdown'.format(access_token))

    # Send a good attachment
    assert obj.notify(body="test", attach=attach) is True

    # Test our call count
    assert mock_post.call_count == 4
    # Image Prep
    assert mock_post.call_args_list[0][0][0] == \
        'https://api.pushbullet.com/v2/upload-request'
    assert mock_post.call_args_list[1][0][0] == \
        'https://upload.pushbullet.com/abcd123'
    # Message
    assert mock_post.call_args_list[2][0][0] == \
        'https://api.pushbullet.com/v2/pushes'
    # Image Send
    assert mock_post.call_args_list[3][0][0] == \
        'https://api.pushbullet.com/v2/pushes'

    # Reset our mock object
    mock_post.reset_mock()

    # Add another attachment so we drop into the area of the PushBullet code
    # that sends remaining attachments (if more detected)
    attach.add(os.path.join(TEST_VAR_DIR, 'apprise-test.gif'))

    # Send our attachments
    assert obj.notify(body="test", attach=attach) is True

    # Test our call count
    assert mock_post.call_count == 7
    # Image Prep
    assert mock_post.call_args_list[0][0][0] == \
        'https://api.pushbullet.com/v2/upload-request'
    assert mock_post.call_args_list[1][0][0] == \
        'https://upload.pushbullet.com/abcd123'
    assert mock_post.call_args_list[2][0][0] == \
        'https://api.pushbullet.com/v2/upload-request'
    assert mock_post.call_args_list[3][0][0] == \
        'https://upload.pushbullet.com/abcd123'
    # Message
    assert mock_post.call_args_list[4][0][0] == \
        'https://api.pushbullet.com/v2/pushes'
    # Image Send
    assert mock_post.call_args_list[5][0][0] == \
        'https://api.pushbullet.com/v2/pushes'
    assert mock_post.call_args_list[6][0][0] == \
        'https://api.pushbullet.com/v2/pushes'

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

    # Prepare a bad response
    bad_response = mock.Mock()
    bad_response.content = dumps({
        "file_name": "cat.jpg",
        "file_type": "image/jpeg",
        "file_url": "https://dl.pushb.com/abc/cat.jpg",
        "upload_url": "https://upload.pushbullet.com/abcd123",
    })
    bad_response.status_code = requests.codes.internal_server_error

    # Prepare a bad response
    bad_json_response = mock.Mock()
    bad_json_response.content = '}'
    bad_json_response.status_code = requests.codes.ok

    # Throw an exception on the first call to requests.post()
    mock_post.return_value = None
    for side_effect in (requests.RequestException(), OSError(), bad_response):
        mock_post.side_effect = side_effect

        # We'll fail now because of our error handling
        assert obj.send(body="test", attach=attach) is False

    # Throw an exception on the second call to requests.post()
    for side_effect in (requests.RequestException(), OSError(), bad_response):
        mock_post.side_effect = [response, side_effect]

        # We'll fail now because of our error handling
        assert obj.send(body="test", attach=attach) is False

    # Throw an exception on the third call to requests.post()
    for side_effect in (requests.RequestException(), OSError(), bad_response):
        mock_post.side_effect = [response, response, side_effect]

        # We'll fail now because of our error handling
        assert obj.send(body="test", attach=attach) is False

    # Throw an exception on the forth call to requests.post()
    for side_effect in (requests.RequestException(), OSError(), bad_response):
        mock_post.side_effect = [response, response, response, side_effect]

        # We'll fail now because of our error handling
        assert obj.send(body="test", attach=attach) is False

    # Test case where we don't get a valid response back
    mock_post.side_effect = bad_json_response

    # We'll fail because of an invalid json object
    assert obj.send(body="test", attach=attach) is False


@mock.patch('requests.get')
@mock.patch('requests.post')
def test_plugin_pushbullet_edge_cases(mock_post, mock_get):
    """
    NotifyPushBullet() Edge Cases

    """

    # Initialize some generic (but valid) tokens
    accesstoken = 'a' * 32

    # Support strings
    recipients = '#chan1,#chan2,device,user@example.com,,,'

    # Prepare Mock
    mock_get.return_value = requests.Request()
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok
    mock_get.return_value.status_code = requests.codes.ok

    # Invalid Access Token
    with pytest.raises(TypeError):
        NotifyPushBullet(accesstoken=None)
    with pytest.raises(TypeError):
        NotifyPushBullet(accesstoken="     ")

    obj = NotifyPushBullet(
        accesstoken=accesstoken, targets=recipients)
    assert isinstance(obj, NotifyPushBullet) is True
    assert len(obj.targets) == 4

    obj = NotifyPushBullet(accesstoken=accesstoken)
    assert isinstance(obj, NotifyPushBullet) is True
    # Default is to send to all devices, so there will be a
    # recipient here
    assert len(obj.targets) == 1

    obj = NotifyPushBullet(accesstoken=accesstoken, targets=set())
    assert isinstance(obj, NotifyPushBullet) is True
    # Default is to send to all devices, so there will be a
    # recipient here
    assert len(obj.targets) == 1
