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
import pytest
import mock
import requests
from json import dumps
from json import loads
from apprise import Apprise
from apprise import AppriseAttachment
from apprise import AppriseAsset
from apprise import NotifyType
from apprise import plugins
from helpers import AppriseURLTester

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Attachment Directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), 'var')

# Our Testing URLs
apprise_url_tests = (
    ##################################
    # NotifyTelegram
    ##################################
    ('tgram://', {
        'instance': None,
    }),
    # Simple Message
    ('tgram://123456789:abcdefg_hijklmnop/lead2gold/', {
        'instance': plugins.NotifyTelegram,
    }),
    # Simple Message (no images)
    ('tgram://123456789:abcdefg_hijklmnop/lead2gold/', {
        'instance': plugins.NotifyTelegram,
        # don't include an image by default
        'include_image': False,
    }),
    # Simple Message with multiple chat names
    ('tgram://123456789:abcdefg_hijklmnop/id1/id2/', {
        'instance': plugins.NotifyTelegram,
    }),
    # Simple Message with multiple chat names
    ('tgram://123456789:abcdefg_hijklmnop/?to=id1,id2', {
        'instance': plugins.NotifyTelegram,
    }),
    # Simple Message with an invalid chat ID
    ('tgram://123456789:abcdefg_hijklmnop/%$/', {
        'instance': plugins.NotifyTelegram,
        # Notify will fail
        'response': False,
    }),
    # Simple Message with multiple chat ids
    ('tgram://123456789:abcdefg_hijklmnop/id1/id2/23423/-30/', {
        'instance': plugins.NotifyTelegram,
    }),
    # Simple Message with multiple chat ids (no images)
    ('tgram://123456789:abcdefg_hijklmnop/id1/id2/23423/-30/', {
        'instance': plugins.NotifyTelegram,
        # don't include an image by default
        'include_image': False,
    }),
    # Support bot keyword prefix
    ('tgram://bottest@123456789:abcdefg_hijklmnop/lead2gold/', {
        'instance': plugins.NotifyTelegram,
    }),
    # Testing image
    ('tgram://123456789:abcdefg_hijklmnop/lead2gold/?image=Yes', {
        'instance': plugins.NotifyTelegram,
    }),
    # Testing invalid format (fall's back to html)
    ('tgram://123456789:abcdefg_hijklmnop/lead2gold/?format=invalid', {
        'instance': plugins.NotifyTelegram,
    }),
    # Testing empty format (falls back to html)
    ('tgram://123456789:abcdefg_hijklmnop/lead2gold/?format=', {
        'instance': plugins.NotifyTelegram,
    }),
    # Testing valid formats
    ('tgram://123456789:abcdefg_hijklmnop/lead2gold/?format=markdown', {
        'instance': plugins.NotifyTelegram,
    }),
    ('tgram://123456789:abcdefg_hijklmnop/lead2gold/?format=html', {
        'instance': plugins.NotifyTelegram,
    }),
    ('tgram://123456789:abcdefg_hijklmnop/lead2gold/?format=text', {
        'instance': plugins.NotifyTelegram,
    }),
    # Test Silent Settings
    ('tgram://123456789:abcdefg_hijklmnop/lead2gold/?silent=yes', {
        'instance': plugins.NotifyTelegram,
    }),
    ('tgram://123456789:abcdefg_hijklmnop/lead2gold/?silent=no', {
        'instance': plugins.NotifyTelegram,
    }),
    # Test Web Page Preview Settings
    ('tgram://123456789:abcdefg_hijklmnop/lead2gold/?preview=yes', {
        'instance': plugins.NotifyTelegram,
    }),
    ('tgram://123456789:abcdefg_hijklmnop/lead2gold/?preview=no', {
        'instance': plugins.NotifyTelegram,
    }),
    # Simple Message without image
    ('tgram://123456789:abcdefg_hijklmnop/lead2gold/', {
        'instance': plugins.NotifyTelegram,
        # don't include an image by default
        'include_image': False,
    }),
    # Invalid Bot Token
    ('tgram://alpha:abcdefg_hijklmnop/lead2gold/', {
        'instance': None,
    }),
    # AuthToken + bad url
    ('tgram://:@/', {
        'instance': None,
    }),
    ('tgram://123456789:abcdefg_hijklmnop/lead2gold/', {
        'instance': plugins.NotifyTelegram,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('tgram://123456789:abcdefg_hijklmnop/lead2gold/?image=Yes', {
        'instance': plugins.NotifyTelegram,
        # force a failure without an image specified
        'include_image': False,
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('tgram://123456789:abcdefg_hijklmnop/id1/id2/', {
        'instance': plugins.NotifyTelegram,
        # force a failure with multiple chat_ids
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('tgram://123456789:abcdefg_hijklmnop/id1/id2/', {
        'instance': plugins.NotifyTelegram,
        # force a failure without an image specified
        'include_image': False,
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('tgram://123456789:abcdefg_hijklmnop/lead2gold/', {
        'instance': plugins.NotifyTelegram,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('tgram://123456789:abcdefg_hijklmnop/lead2gold/', {
        'instance': plugins.NotifyTelegram,
        # throw a bizzare code forcing us to fail to look it up without
        # having an image included
        'include_image': False,
        'response': False,
        'requests_response_code': 999,
    }),
    # Test with image set
    ('tgram://123456789:abcdefg_hijklmnop/lead2gold/?image=Yes', {
        'instance': plugins.NotifyTelegram,
        # throw a bizzare code forcing us to fail to look it up without
        # having an image included
        'include_image': True,
        'response': False,
        'requests_response_code': 999,
    }),
    ('tgram://123456789:abcdefg_hijklmnop/lead2gold/', {
        'instance': plugins.NotifyTelegram,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
    ('tgram://123456789:abcdefg_hijklmnop/lead2gold/?image=Yes', {
        'instance': plugins.NotifyTelegram,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them without images set
        'include_image': True,
        'test_requests_exceptions': True,
    }),
)


def test_plugin_telegram_urls():
    """
    NotifyTelegram() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch('requests.get')
@mock.patch('requests.post')
def test_plugin_telegram_general(mock_post, mock_get):
    """
    NotifyTelegram() General Tests

    """

    # Disable Throttling to speed testing
    plugins.NotifyBase.request_rate_per_sec = 0

    # Bot Token
    bot_token = '123456789:abcdefg_hijklmnop'
    invalid_bot_token = 'abcd:123'

    # Chat ID
    chat_ids = 'l2g, lead2gold'

    # Prepare Mock
    mock_get.return_value = requests.Request()
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok
    mock_get.return_value.status_code = requests.codes.ok
    mock_get.return_value.content = '{}'
    mock_post.return_value.content = '{}'

    # Exception should be thrown about the fact no bot token was specified
    with pytest.raises(TypeError):
        plugins.NotifyTelegram(bot_token=None, targets=chat_ids)

    # Invalid JSON while trying to detect bot owner
    mock_get.return_value.content = '{'
    mock_post.return_value.content = '}'
    obj = plugins.NotifyTelegram(bot_token=bot_token, targets=None)
    obj.notify(title='hello', body='world')

    # Invalid JSON while trying to detect bot owner + 400 error
    mock_get.return_value.status_code = requests.codes.internal_server_error
    mock_post.return_value.status_code = requests.codes.internal_server_error
    obj = plugins.NotifyTelegram(bot_token=bot_token, targets=None)
    obj.notify(title='hello', body='world')

    # Return status back to how they were
    mock_post.return_value.status_code = requests.codes.ok
    mock_get.return_value.status_code = requests.codes.ok

    # Exception should be thrown about the fact an invalid bot token was
    # specifed
    with pytest.raises(TypeError):
        plugins.NotifyTelegram(bot_token=invalid_bot_token, targets=chat_ids)

    obj = plugins.NotifyTelegram(
        bot_token=bot_token, targets=chat_ids, include_image=True)
    assert isinstance(obj, plugins.NotifyTelegram) is True
    assert len(obj.targets) == 2

    # Test Image Sending Exceptions
    mock_post.side_effect = IOError()
    assert not obj.send_media(obj.targets[0], NotifyType.INFO)

    # Test our other objects
    mock_post.side_effect = requests.HTTPError
    assert not obj.send_media(obj.targets[0], NotifyType.INFO)

    # Restore their entries
    mock_get.side_effect = None
    mock_post.side_effect = None
    mock_get.return_value.content = '{}'
    mock_post.return_value.content = '{}'

    # test url call
    assert isinstance(obj.url(), six.string_types) is True

    # test privacy version of url
    assert isinstance(obj.url(privacy=True), six.string_types) is True
    assert obj.url(privacy=True).startswith('tgram://1...p/') is True

    # Test that we can load the string we generate back:
    obj = plugins.NotifyTelegram(**plugins.NotifyTelegram.parse_url(obj.url()))
    assert isinstance(obj, plugins.NotifyTelegram) is True

    # Prepare Mock to fail
    response = mock.Mock()
    response.status_code = requests.codes.internal_server_error

    # a error response
    response.content = dumps({
        'description': 'test',
    })
    mock_get.return_value = response
    mock_post.return_value = response

    # No image asset
    nimg_obj = plugins.NotifyTelegram(bot_token=bot_token, targets=chat_ids)
    nimg_obj.asset = AppriseAsset(image_path_mask=False, image_url_mask=False)

    # Test that our default settings over-ride base settings since they are
    # not the same as the one specified in the base; this check merely
    # ensures our plugin inheritance is working properly
    assert obj.body_maxlen == plugins.NotifyTelegram.body_maxlen

    # We don't override the title maxlen so we should be set to the same
    # as our parent class in this case
    assert obj.title_maxlen == plugins.NotifyBase.title_maxlen

    # This tests erroneous messages involving multiple chat ids
    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO) is False
    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO) is False
    assert nimg_obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO) is False

    # This tests erroneous messages involving a single chat id
    obj = plugins.NotifyTelegram(bot_token=bot_token, targets='l2g')
    nimg_obj = plugins.NotifyTelegram(bot_token=bot_token, targets='l2g')
    nimg_obj.asset = AppriseAsset(image_path_mask=False, image_url_mask=False)

    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO) is False
    assert nimg_obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO) is False

    # Bot Token Detection
    # Just to make it clear to people reading this code and trying to learn
    # what is going on.  Apprise tries to detect the bot owner if you don't
    # specify a user to message.  The idea is to just default to messaging
    # the bot owner himself (it makes it easier for people).  So we're testing
    # the creating of a Telegram Notification without providing a chat ID.
    # We're testing the error handling of this bot detection section of the
    # code
    mock_post.return_value.content = dumps({
        "ok": True,
        "result": [{
            "update_id": 645421321,
            "message": {
                "message_id": 1,
                "from": {
                    "id": 532389719,
                    "is_bot": False,
                    "first_name": "Chris",
                    "language_code": "en-US"
                },
                "chat": {
                    "id": 532389719,
                    "first_name": "Chris",
                    "type": "private"
                },
                "date": 1519694394,
                "text": "/start",
                "entities": [{
                    "offset": 0,
                    "length": 6,
                    "type": "bot_command",
                }],
            }},
        ],
    })
    mock_post.return_value.status_code = requests.codes.ok

    obj = plugins.NotifyTelegram(bot_token=bot_token, targets='12345')
    assert len(obj.targets) == 1
    assert obj.targets[0] == '12345'

    # Test the escaping of characters since Telegram escapes stuff for us to
    # which we need to consider
    mock_post.reset_mock()
    body = "<p>\'\"This can't\t\r\nfail&nbsp;us\"\'</p>"
    assert obj.notify(
        body=body, title='special characters',
        notify_type=NotifyType.INFO) is True
    assert mock_post.call_count == 1
    payload = loads(mock_post.call_args_list[0][1]['data'])

    # Our special characters are escaped properly
    assert payload['text'] == \
        '<b>special characters</b>\r\n&lt;p&gt;'\
        '\'"This can\'t\t\r\nfail us"\'&lt;/p&gt;'

    # Test sending attachments
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

    obj = plugins.NotifyTelegram(bot_token=bot_token, targets=None)
    # No user detected; this happens after our firsst notification
    assert len(obj.targets) == 0

    assert obj.notify(title='hello', body='world') is True
    assert len(obj.targets) == 1
    assert obj.targets[0] == '532389719'

    # Do the test again, but without the expected (parsed response)
    mock_post.return_value.content = dumps({
        "ok": True,
        "result": [],
    })

    # No user will be detected now
    obj = plugins.NotifyTelegram(bot_token=bot_token, targets=None)
    # No user detected; this happens after our firsst notification
    assert len(obj.targets) == 0
    assert obj.notify(title='hello', body='world') is False
    assert len(obj.targets) == 0

    # Detect the bot with a bad response
    mock_post.return_value.content = dumps({})
    obj.detect_bot_owner()

    # Test our bot detection with a internal server error
    mock_post.return_value.status_code = requests.codes.internal_server_error

    # internal server error prevents notification from being sent
    obj = plugins.NotifyTelegram(bot_token=bot_token, targets=None)
    assert len(obj.targets) == 0
    assert obj.notify(title='hello', body='world') is False
    assert len(obj.targets) == 0

    # Test our bot detection with an unmappable html error
    mock_post.return_value.status_code = 999
    plugins.NotifyTelegram(bot_token=bot_token, targets=None)
    assert len(obj.targets) == 0
    assert obj.notify(title='hello', body='world') is False
    assert len(obj.targets) == 0

    # Do it again but this time provide a failure message
    mock_post.return_value.content = dumps({'description': 'Failure Message'})
    plugins.NotifyTelegram(bot_token=bot_token, targets=None)
    assert len(obj.targets) == 0
    assert obj.notify(title='hello', body='world') is False
    assert len(obj.targets) == 0

    # Do it again but this time provide a failure message and perform a
    # notification without a bot detection by providing at least 1 chat id
    obj = plugins.NotifyTelegram(bot_token=bot_token, targets=['@abcd'])
    assert nimg_obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO) is False

    # iterate over our exceptions and test them
    mock_post.side_effect = requests.HTTPError

    # No chat_ids specified
    obj = plugins.NotifyTelegram(bot_token=bot_token, targets=None)
    assert len(obj.targets) == 0
    assert obj.notify(title='hello', body='world') is False
    assert len(obj.targets) == 0

    # Test Telegram Group
    obj = Apprise.instantiate(
        'tgram://123456789:ABCdefghijkl123456789opqyz/-123456789525')
    assert isinstance(obj, plugins.NotifyTelegram)
    assert len(obj.targets) == 1
    assert '-123456789525' in obj.targets
