# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2026, Chris Caron <lead2gold@gmail.com>
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

from inspect import cleandoc
from json import dumps, loads

# Disable logging for a cleaner testing output
import logging
import os
import re
from timeit import default_timer
from unittest import mock
from urllib.parse import urlparse

from helpers import AppriseURLTester
import pytest
import requests

from apprise import (
    Apprise,
    AppriseAsset,
    AppriseAttachment,
    NotifyFormat,
    NotifyType,
)
from apprise.exception import AppriseImproperlyConfigured
from apprise.plugins.base import _delivery_tracker
from apprise.plugins.telegram import (
    NotifyTelegram,
    TelegramGroupResult,
    TelegramHTMLReducer,
    TelegramMediaKind,
)

logging.disable(logging.CRITICAL)

# Attachment Directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), "var")

# Our Testing URLs
apprise_url_tests = (
    ##################################
    # NotifyTelegram
    ##################################
    (
        "tgram://",
        {
            "instance": None,
        },
    ),
    # Simple Message
    (
        "tgram://123456789:abcdefg_hijklmnop/lead2gold/",
        {
            "instance": NotifyTelegram,
        },
    ),
    # Simple Message (no images)
    (
        "tgram://123456789:abcdefg_hijklmnop/lead2gold/",
        {
            "instance": NotifyTelegram,
            # don't include an image by default
            "include_image": False,
        },
    ),
    # Simple Message with multiple chat names
    (
        "tgram://123456789:abcdefg_hijklmnop/id1/id2/",
        {
            "instance": NotifyTelegram,
        },
    ),
    # Simple Message with multiple chat names
    (
        "tgram://123456789:abcdefg_hijklmnop/?to=id1,id2",
        {
            "instance": NotifyTelegram,
        },
    ),
    # Simple Message with an invalid chat ID
    (
        "tgram://123456789:abcdefg_hijklmnop/%$/",
        {
            "instance": NotifyTelegram,
            # Notify will fail
            "response": False,
        },
    ),
    # Simple Message with multiple chat ids
    (
        "tgram://123456789:abcdefg_hijklmnop/id1/id2/23423/-30/",
        {
            "instance": NotifyTelegram,
        },
    ),
    # Simple Message with multiple chat ids (no images)
    (
        "tgram://123456789:abcdefg_hijklmnop/id1/id2/23423/-30/",
        {
            "instance": NotifyTelegram,
            # don't include an image by default
            "include_image": False,
        },
    ),
    # Support bot keyword prefix
    (
        "tgram://bottest@123456789:abcdefg_hijklmnop/lead2gold/",
        {
            "instance": NotifyTelegram,
        },
    ),
    # Support Thread Topics
    (
        "tgram://bottest@123456789:abcdefg_hijklmnop/id1/?topic=12345",
        {
            "instance": NotifyTelegram,
        },
    ),
    # Thread is just an alias of topic
    (
        "tgram://bottest@123456789:abcdefg_hijklmnop/id1/?thread=12345",
        {
            "instance": NotifyTelegram,
        },
    ),
    # Threads must be numeric
    (
        "tgram://bottest@123456789:abcdefg_hijklmnop/id1/?topic=invalid",
        {
            "instance": AppriseImproperlyConfigured,
        },
    ),
    # content must be 'before' or 'after'
    (
        "tgram://bottest@123456789:abcdefg_hijklmnop/id1/?content=invalid",
        {
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "tgram://bottest@123456789:abcdefg_hijklmnop/id1:invalid/?thread=12345",
        {
            "instance": NotifyTelegram,
            # Notify will fail (bad target)
            "response": False,
        },
    ),
    # Testing image
    (
        "tgram://123456789:abcdefg_hijklmnop/lead2gold/?image=Yes",
        {
            "instance": NotifyTelegram,
        },
    ),
    # Testing invalid format (fall's back to html)
    (
        "tgram://123456789:abcdefg_hijklmnop/lead2gold/?format=invalid",
        {
            "instance": NotifyTelegram,
        },
    ),
    # Testing empty format (falls back to html)
    (
        "tgram://123456789:abcdefg_hijklmnop/lead2gold/?format=",
        {
            "instance": NotifyTelegram,
        },
    ),
    # Testing valid formats
    (
        "tgram://123456789:abcdefg_hijklmnop/lead2gold/?format=markdown",
        {
            "instance": NotifyTelegram,
        },
    ),
    (
        "tgram://123456789:abcdefg_hijklmnop/lead2gold/?format=markdown&mdv=v1",
        {
            "instance": NotifyTelegram,
        },
    ),
    (
        "tgram://123456789:abcdefg_hijklmnop/lead2gold/?format=markdown&mdv=v2",
        {
            "instance": NotifyTelegram,
        },
    ),
    (
        "tgram://123456789:abcdefg_hijklmnop/l2g/?format=markdown&mdv=bad",
        {
            # Defaults to v2
            "instance": NotifyTelegram,
        },
    ),
    (
        "tgram://123456789:abcdefg_hijklmnop/lead2gold/?format=html",
        {
            "instance": NotifyTelegram,
        },
    ),
    (
        "tgram://123456789:abcdefg_hijklmnop/lead2gold/?format=text",
        {
            "instance": NotifyTelegram,
        },
    ),
    # Test Silent Settings
    (
        "tgram://123456789:abcdefg_hijklmnop/lead2gold/?silent=yes",
        {
            "instance": NotifyTelegram,
        },
    ),
    (
        "tgram://123456789:abcdefg_hijklmnop/lead2gold/?silent=no",
        {
            "instance": NotifyTelegram,
        },
    ),
    # Test Web Page Preview Settings
    (
        "tgram://123456789:abcdefg_hijklmnop/lead2gold/?preview=yes",
        {
            "instance": NotifyTelegram,
        },
    ),
    (
        "tgram://123456789:abcdefg_hijklmnop/lead2gold/?preview=no",
        {
            "instance": NotifyTelegram,
        },
    ),
    # Simple Message without image
    (
        "tgram://123456789:abcdefg_hijklmnop/lead2gold/",
        {
            "instance": NotifyTelegram,
            # don't include an image by default
            "include_image": False,
        },
    ),
    # Invalid Bot Token
    (
        "tgram://alpha:abcdefg_hijklmnop/lead2gold/",
        {
            "instance": None,
        },
    ),
    # AuthToken + bad url
    (
        "tgram://:@/",
        {
            "instance": None,
        },
    ),
    (
        "tgram://123456789:abcdefg_hijklmnop/lead2gold/",
        {
            "instance": NotifyTelegram,
            # force a failure
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "tgram://123456789:abcdefg_hijklmnop/lead2gold/?image=Yes",
        {
            "instance": NotifyTelegram,
            # force a failure without an image specified
            "include_image": False,
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "tgram://123456789:abcdefg_hijklmnop/id1/id2/",
        {
            "instance": NotifyTelegram,
            # force a failure with multiple chat_ids
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "tgram://123456789:abcdefg_hijklmnop/id1/id2/",
        {
            "instance": NotifyTelegram,
            # force a failure without an image specified
            "include_image": False,
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "tgram://123456789:abcdefg_hijklmnop/lead2gold/",
        {
            "instance": NotifyTelegram,
            # throw a bizarre code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "tgram://123456789:abcdefg_hijklmnop/lead2gold/",
        {
            "instance": NotifyTelegram,
            # throw a bizarre code forcing us to fail to look it up without
            # having an image included
            "include_image": False,
            "response": False,
            "requests_response_code": 999,
        },
    ),
    # Test with image set
    (
        "tgram://123456789:abcdefg_hijklmnop/lead2gold/?image=Yes",
        {
            "instance": NotifyTelegram,
            # throw a bizarre code forcing us to fail to look it up without
            # having an image included
            "include_image": True,
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "tgram://123456789:abcdefg_hijklmnop/lead2gold/",
        {
            "instance": NotifyTelegram,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracefully handle them
            "test_requests_exceptions": True,
        },
    ),
    (
        "tgram://123456789:abcdefg_hijklmnop/lead2gold/?image=Yes",
        {
            "instance": NotifyTelegram,
            # Throws a series of i/o exceptions with this flag is set and
            # tests that we gracefully handle them without images set
            "include_image": True,
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_telegram_urls():
    """NotifyTelegram() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.post")
def test_plugin_telegram_general(mock_post):
    """NotifyTelegram() General Tests."""

    # Bot Token
    bot_token = "123456789:abcdefg_hijklmnop"
    invalid_bot_token = "abcd:123"

    # Chat ID
    chat_ids = "l2g:1234, lead2gold"

    # Prepare Mock
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok
    mock_post.return_value.content = "{}"

    # Exception should be thrown about the fact no bot token was specified
    with pytest.raises(AppriseImproperlyConfigured):
        NotifyTelegram(bot_token=None, targets=chat_ids)

    # Invalid JSON while trying to detect bot owner
    mock_post.return_value.content = "}"
    obj = NotifyTelegram(bot_token=bot_token, targets=None)
    obj.notify(title="hello", body="world")

    # Invalid JSON while trying to detect bot owner + 400 error
    mock_post.return_value.status_code = requests.codes.internal_server_error
    obj = NotifyTelegram(bot_token=bot_token, targets=None)
    obj.notify(title="hello", body="world")

    # Return status back to how they were
    mock_post.return_value.status_code = requests.codes.ok

    # Exception should be thrown about the fact an invalid bot token was
    # specifed
    with pytest.raises(AppriseImproperlyConfigured):
        NotifyTelegram(bot_token=invalid_bot_token, targets=chat_ids)

    obj = NotifyTelegram(
        bot_token=bot_token, targets=chat_ids, include_image=True
    )
    assert isinstance(obj, NotifyTelegram) is True
    assert len(obj.targets) == 2

    # Test Image Sending Exceptions
    mock_post.side_effect = OSError()
    assert not obj.send_media(obj.targets[0], NotifyType.INFO)

    # Test our other objects
    mock_post.side_effect = requests.HTTPError
    assert not obj.send_media(obj.targets[0], NotifyType.INFO)

    # Restore their entries
    mock_post.side_effect = None
    mock_post.return_value.content = "{}"

    # test url call
    assert isinstance(obj.url(), str) is True

    # test privacy version of url
    assert isinstance(obj.url(privacy=True), str) is True
    assert obj.url(privacy=True).startswith("tgram://1...p/") is True

    # Test that we can load the string we generate back:
    obj = NotifyTelegram(**NotifyTelegram.parse_url(obj.url()))
    assert isinstance(obj, NotifyTelegram) is True

    # Prepare Mock to fail
    response = mock.Mock()
    response.status_code = requests.codes.internal_server_error

    # a error response
    response.content = dumps(
        {
            "description": "test",
        }
    )
    mock_post.return_value = response

    # No image asset
    nimg_obj = NotifyTelegram(bot_token=bot_token, targets=chat_ids)
    nimg_obj.asset = AppriseAsset(image_path_mask=False, image_url_mask=False)

    # Test that our default settings over-ride base settings since they are
    # not the same as the one specified in the base; this check merely
    # ensures our plugin inheritance is working properly
    assert obj.body_maxlen == NotifyTelegram.body_maxlen

    # This tests erroneous messages involving multiple chat ids
    assert (
        bool(
            obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        )
        is False
    )
    assert (
        bool(
            obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        )
        is False
    )
    assert (
        bool(
            nimg_obj.notify(
                body="body", title="title", notify_type=NotifyType.INFO
            )
        )
        is False
    )

    # This tests erroneous messages involving a single chat id
    obj = NotifyTelegram(bot_token=bot_token, targets="l2g")
    nimg_obj = NotifyTelegram(bot_token=bot_token, targets="l2g")
    nimg_obj.asset = AppriseAsset(image_path_mask=False, image_url_mask=False)

    assert (
        bool(
            obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        )
        is False
    )
    assert (
        bool(
            nimg_obj.notify(
                body="body", title="title", notify_type=NotifyType.INFO
            )
        )
        is False
    )

    # Bot Token Detection
    # Just to make it clear to people reading this code and trying to learn
    # what is going on.  Apprise tries to detect the bot owner if you don't
    # specify a user to message.  The idea is to just default to messaging
    # the bot owner himself (it makes it easier for people).  So we're testing
    # the creating of a Telegram Notification without providing a chat ID.
    # We're testing the error handling of this bot detection section of the
    # code
    mock_post.return_value.content = dumps(
        {
            "ok": True,
            "result": [
                {
                    "update_id": 645421319,
                    # Entry without `message` in it
                },
                {
                    # Entry without `from` in `message`
                    "update_id": 645421320,
                    "message": {
                        "message_id": 2,
                        "chat": {
                            "id": 532389719,
                            "first_name": "Chris",
                            "type": "private",
                        },
                        "date": 1519694394,
                        "text": "/start",
                        "entities": [
                            {
                                "offset": 0,
                                "length": 6,
                                "type": "bot_command",
                            }
                        ],
                    },
                },
                {
                    "update_id": 645421321,
                    "message": {
                        "message_id": 2,
                        "from": {
                            "id": 532389719,
                            "is_bot": False,
                            "first_name": "Chris",
                            "language_code": "en-US",
                        },
                        "chat": {
                            "id": 532389719,
                            "first_name": "Chris",
                            "type": "private",
                        },
                        "date": 1519694394,
                        "text": "/start",
                        "entities": [
                            {
                                "offset": 0,
                                "length": 6,
                                "type": "bot_command",
                            }
                        ],
                    },
                },
            ],
        }
    )
    mock_post.return_value.status_code = requests.codes.ok

    obj = NotifyTelegram(bot_token=bot_token, targets="12345")
    assert len(obj.targets) == 1
    assert obj.targets[0] == (12345, None)

    # Test the escaping of characters since Telegram escapes stuff for us to
    # which we need to consider
    mock_post.reset_mock()
    body = "<p>'\"This can't\t\r\nfail&nbsp;us\"'</p>"
    assert (
        bool(
            obj.notify(
                body=body,
                title="special characters",
                notify_type=NotifyType.INFO,
            )
        )
        is True
    )
    assert mock_post.call_count == 1
    payload = loads(mock_post.call_args_list[0][1]["data"])

    # Test our payload
    assert (
        payload["text"]
        == "<b>special characters</b>\r\n'\"This can't\t\r\nfail us\"'\r\n"
    )

    for content in ("before", "after"):
        # Test our content settings
        obj = NotifyTelegram(
            bot_token=bot_token, targets="12345", content=content
        )
        # Reset our mock
        mock_post.reset_mock()
        # Test sending attachments
        attach = AppriseAttachment(
            os.path.join(TEST_VAR_DIR, "apprise-test.gif")
        )
        assert (
            bool(
                obj.notify(
                    body="body",
                    title="title",
                    notify_type=NotifyType.INFO,
                    attach=attach,
                )
            )
            is True
        )

        # Test large messages
        assert (
            bool(
                obj.notify(
                    body="a" * (obj.telegram_caption_maxlen + 1),
                    title="title",
                    notify_type=NotifyType.INFO,
                    attach=attach,
                )
            )
            is True
        )

        # An invalid attachment will cause a failure
        path = os.path.join(
            TEST_VAR_DIR, "/invalid/path/to/an/invalid/file.jpg"
        )
        attach = AppriseAttachment(path)
        assert (
            bool(
                obj.notify(
                    body="body",
                    title="title",
                    notify_type=NotifyType.INFO,
                    attach=path,
                )
            )
            is False
        )

        # Test large messages
        assert (
            bool(
                obj.notify(
                    body="a" * (obj.telegram_caption_maxlen + 1),
                    title="title",
                    notify_type=NotifyType.INFO,
                    attach=path,
                )
            )
            is False
        )

    obj = NotifyTelegram(bot_token=bot_token, targets=None)
    # No user detected; this happens after our firsst notification
    assert len(obj.targets) == 0

    assert bool(obj.notify(title="hello", body="world")) is True
    assert len(obj.targets) == 1
    assert obj.targets[0] == ("532389719", None)

    # Do the test again, but without the expected (parsed response)
    mock_post.return_value.content = dumps(
        {
            "ok": True,
            "result": [],
        }
    )

    # No user will be detected now
    obj = NotifyTelegram(bot_token=bot_token, targets=None)
    # No user detected; this happens after our firsst notification
    assert len(obj.targets) == 0
    assert bool(obj.notify(title="hello", body="world")) is False
    assert len(obj.targets) == 0

    # Do the test again, but with ok not set to True
    mock_post.return_value.content = dumps(
        {
            "ok": False,
            "result": [
                {
                    "update_id": 645421321,
                    "message": {
                        "message_id": 2,
                        "from": {
                            "id": 532389719,
                            "is_bot": False,
                            "first_name": "Chris",
                            "language_code": "en-US",
                        },
                        "chat": {
                            "id": 532389719,
                            "first_name": "Chris",
                            "type": "private",
                        },
                        "date": 1519694394,
                        "text": "/start",
                        "entities": [
                            {
                                "offset": 0,
                                "length": 6,
                                "type": "bot_command",
                            }
                        ],
                    },
                },
            ],
        }
    )

    # No user will be detected now
    obj = NotifyTelegram(bot_token=bot_token, targets=None)
    # No user detected; this happens after our firsst notification
    assert len(obj.targets) == 0
    assert bool(obj.notify(title="hello", body="world")) is False
    assert len(obj.targets) == 0

    # An edge case where no results were provided; this will probably never
    # happen, but it helps with test coverage completeness
    mock_post.return_value.content = dumps(
        {
            "ok": True,
        }
    )

    # No user will be detected now
    obj = NotifyTelegram(bot_token=bot_token, targets=None)
    # No user detected; this happens after our firsst notification
    assert len(obj.targets) == 0
    assert bool(obj.notify(title="hello", body="world")) is False
    assert len(obj.targets) == 0
    # Detect the bot with a bad response
    mock_post.return_value.content = dumps({})
    obj.detect_bot_owner()

    # Test our bot detection with a internal server error
    mock_post.return_value.status_code = requests.codes.internal_server_error

    # internal server error prevents notification from being sent
    obj = NotifyTelegram(bot_token=bot_token, targets=None)
    assert len(obj.targets) == 0
    assert bool(obj.notify(title="hello", body="world")) is False
    assert len(obj.targets) == 0

    # Test our bot detection with an unmappable html error
    mock_post.return_value.status_code = 999
    NotifyTelegram(bot_token=bot_token, targets=None)
    assert len(obj.targets) == 0
    assert bool(obj.notify(title="hello", body="world")) is False
    assert len(obj.targets) == 0

    # Do it again but this time provide a failure message
    mock_post.return_value.content = dumps({"description": "Failure Message"})
    NotifyTelegram(bot_token=bot_token, targets=None)
    assert len(obj.targets) == 0
    assert bool(obj.notify(title="hello", body="world")) is False
    assert len(obj.targets) == 0

    # Do it again but this time provide a failure message and perform a
    # notification without a bot detection by providing at least 1 chat id
    obj = NotifyTelegram(bot_token=bot_token, targets=["@abcd"])
    assert (
        bool(
            nimg_obj.notify(
                body="body", title="title", notify_type=NotifyType.INFO
            )
        )
        is False
    )

    # iterate over our exceptions and test them
    mock_post.side_effect = requests.HTTPError

    # No chat_ids specified
    obj = NotifyTelegram(bot_token=bot_token, targets=None)
    assert len(obj.targets) == 0
    assert bool(obj.notify(title="hello", body="world")) is False
    assert len(obj.targets) == 0

    # Test Telegram Group
    obj = Apprise.instantiate(
        "tgram://123456789:ABCdefghijkl123456789opqyz/-123456789525"
    )
    assert isinstance(obj, NotifyTelegram)
    assert len(obj.targets) == 1
    assert (-123456789525, None) in obj.targets


@mock.patch("requests.post")
def test_plugin_telegram_formatting(mock_post):
    """NotifyTelegram() formatting tests."""

    # Prepare Mock
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok
    mock_post.return_value.content = "{}"

    # Simple success response
    mock_post.return_value.content = dumps(
        {
            "ok": True,
            "result": [
                {
                    "update_id": 645421321,
                    "message": {
                        "message_id": 2,
                        "from": {
                            "id": 532389719,
                            "is_bot": False,
                            "first_name": "Chris",
                            "language_code": "en-US",
                        },
                        "chat": {
                            "id": 532389719,
                            "first_name": "Chris",
                            "type": "private",
                        },
                        "date": 1519694394,
                        "text": "/start",
                        "entities": [
                            {
                                "offset": 0,
                                "length": 6,
                                "type": "bot_command",
                            }
                        ],
                    },
                },
            ],
        }
    )
    mock_post.return_value.status_code = requests.codes.ok

    results = NotifyTelegram.parse_url("tgram://123456789:abcdefg_hijklmnop/")

    instance = NotifyTelegram(**results)
    assert isinstance(instance, NotifyTelegram)

    response = instance.send(title="title", body="body")
    assert response is True
    # 1 call to look up bot owner, and second for notification
    assert mock_post.call_count == 2

    assert (
        mock_post.call_args_list[0][0][0]
        == "https://api.telegram.org/bot123456789:abcdefg_hijklmnop/getUpdates"
    )
    assert (
        mock_post.call_args_list[1][0][0]
        == "https://api.telegram.org/bot123456789:abcdefg_hijklmnop/sendMessage"
    )

    # Reset our values
    mock_post.reset_mock()

    # Now test our HTML Conversion as TEXT)
    aobj = Apprise()
    aobj.add("tgram://123456789:abcdefg_hijklmnop/")
    assert len(aobj) == 1

    title = "🚨 Change detected for <i>Apprise Test Title</i>"
    body = (
        '<a href="http://localhost"><i>Apprise Body Title</i></a>'
        ' had <a href="http://127.0.0.1">a change</a>'
    )

    assert aobj.notify(title=title, body=body, body_format=NotifyFormat.TEXT)

    # Test our calls
    assert mock_post.call_count == 2

    assert (
        mock_post.call_args_list[0][0][0]
        == "https://api.telegram.org/bot123456789:abcdefg_hijklmnop/getUpdates"
    )
    assert (
        mock_post.call_args_list[1][0][0]
        == "https://api.telegram.org/bot123456789:abcdefg_hijklmnop/sendMessage"
    )

    payload = loads(mock_post.call_args_list[1][1]["data"])

    # Test that everything is escaped properly in a TEXT mode
    assert (
        payload["text"]
        == "<b>🚨 Change detected for &lt;i&gt;Apprise Test Title&lt;/i&gt;"
        '</b>\r\n&lt;a href="http://localhost"&gt;&lt;i&gt;'
        "Apprise Body Title&lt;/i&gt;&lt;/a&gt; had &lt;"
        'a href="http://127.0.0.1"&gt;a change&lt;/a&gt;'
    )

    # Reset our values
    mock_post.reset_mock()

    # Now test our HTML Conversion as TEXT)
    aobj = Apprise()
    aobj.add("tgram://123456789:abcdefg_hijklmnop/?format=html")
    assert len(aobj) == 1

    assert aobj.notify(title=title, body=body, body_format=NotifyFormat.HTML)

    # Test our calls
    assert mock_post.call_count == 2

    assert (
        mock_post.call_args_list[0][0][0]
        == "https://api.telegram.org/bot123456789:abcdefg_hijklmnop/getUpdates"
    )
    assert (
        mock_post.call_args_list[1][0][0]
        == "https://api.telegram.org/bot123456789:abcdefg_hijklmnop/sendMessage"
    )

    payload = loads(mock_post.call_args_list[1][1]["data"])

    # Test that everything is escaped properly in a HTML mode
    assert (
        payload["text"]
        == "<b>🚨 Change detected for <i>Apprise Test Title</i></b>\r\n"
        '<a href="http://localhost"><i>Apprise Body Title</i></a> had '
        '<a href="http://127.0.0.1">a change</a>'
    )

    # Reset our values
    mock_post.reset_mock()

    # Now test our MARKDOWN Handling
    title = "# 🚨 Change detected for _Apprise Test Title_"
    body = (
        "_[Apprise Body Title](http://localhost)_"
        " had [a change](http://127.0.0.1)"
    )

    aobj = Apprise()
    aobj.add("tgram://123456789:abcdefg_hijklmnop/?format=markdown&mdv=2")
    assert len(aobj) == 1

    assert aobj.notify(
        title=title, body=body, body_format=NotifyFormat.MARKDOWN
    )

    # Test our calls
    assert mock_post.call_count == 2

    assert (
        mock_post.call_args_list[0][0][0]
        == "https://api.telegram.org/bot123456789:abcdefg_hijklmnop/getUpdates"
    )
    assert (
        mock_post.call_args_list[1][0][0]
        == "https://api.telegram.org/bot123456789:abcdefg_hijklmnop/sendMessage"
    )

    payload = loads(mock_post.call_args_list[1][1]["data"])

    # MarkdownV2 renders the merged title heading as bold.
    assert (
        payload["text"] == "*🚨 Change detected for _Apprise Test Title_*\n"
        "_[Apprise Body Title](http://localhost)_ had "
        "[a change](http://127.0.0.1)"
    )

    # Reset our values
    mock_post.reset_mock()

    # Now test our MARKDOWN Handling
    title = "# 🚨 Change detected for _Apprise Test Title_"
    body = (
        "_[Apprise Body Title](http://localhost)_"
        " had [a change](http://127.0.0.1)"
    )

    aobj = Apprise()
    aobj.add("tgram://123456789:abcdefg_hijklmnop/?format=markdown&mdv=1")
    assert len(aobj) == 1

    assert aobj.notify(
        title=title, body=body, body_format=NotifyFormat.MARKDOWN
    )

    # Test our calls
    assert mock_post.call_count == 2

    assert (
        mock_post.call_args_list[0][0][0]
        == "https://api.telegram.org/bot123456789:abcdefg_hijklmnop/getUpdates"
    )
    assert (
        mock_post.call_args_list[1][0][0]
        == "https://api.telegram.org/bot123456789:abcdefg_hijklmnop/sendMessage"
    )

    payload = loads(mock_post.call_args_list[1][1]["data"])

    # Telegram v1 renders the heading as bold and drops nested italic markers.
    assert (
        payload["text"] == "*🚨 Change detected for Apprise Test Title*\n"
        "_[Apprise Body Title](http://localhost)_ had "
        "[a change](http://127.0.0.1)"
    )

    # Reset our values
    mock_post.reset_mock()

    # Upstream to use HTML but input specified as Markdown
    aobj = Apprise()
    aobj.add("tgram://987654321:abcdefg_hijklmnop/?format=html")
    assert len(aobj) == 1

    # Now test our MARKDOWN Handling
    title = "# 🚨 Another Change detected for _Apprise Test Title_"
    body = (
        "_[Apprise Body Title](http://localhost)_"
        " had [a change](http://127.0.0.2)"
    )

    # HTML forced by the command line, but MARKDOWN specified as
    # upstream mode
    assert aobj.notify(
        title=title, body=body, body_format=NotifyFormat.MARKDOWN
    )

    # Test our calls
    assert mock_post.call_count == 2

    assert (
        mock_post.call_args_list[0][0][0]
        == "https://api.telegram.org/bot987654321:abcdefg_hijklmnop/getUpdates"
    )
    assert (
        mock_post.call_args_list[1][0][0]
        == "https://api.telegram.org/bot987654321:abcdefg_hijklmnop/sendMessage"
    )

    payload = loads(mock_post.call_args_list[1][1]["data"])

    # Test that everything is escaped properly in a HTML mode
    assert (
        payload["text"] == "<b><b>🚨 Another Change detected for "
        "<i>Apprise Test Title</i></b>\r\n</b>\r\n<i>"
        '<a href="http://localhost">Apprise Body Title</a>'
        '</i> had <a href="http://127.0.0.2">a change</a>'
    )

    # Now we'll test an edge case where a title was defined, but after
    # processing it, it was determiend there really wasn't anything there
    # at all at the end of the day.

    # Reset our values
    mock_post.reset_mock()

    # Upstream to use HTML but input specified as Markdown v1
    aobj = Apprise()
    aobj.add("tgram://987654321:abcdefg_hijklmnop/?format=markdown&mdv=1")
    assert len(aobj) == 1

    # Now test our MARKDOWN Handling (no title defined... not really anyway)
    title = "# "
    body = (
        "_[Apprise Body Title](http://localhost)_"
        " had [a change](http://127.0.0.2)"
    )

    # MARKDOWN forced by the command line, but TEXT specified as
    # upstream mode
    assert aobj.notify(title=title, body=body, body_format=NotifyFormat.TEXT)

    # Test our calls
    assert mock_post.call_count == 2

    assert (
        mock_post.call_args_list[0][0][0]
        == "https://api.telegram.org/bot987654321:abcdefg_hijklmnop/getUpdates"
    )
    assert (
        mock_post.call_args_list[1][0][0]
        == "https://api.telegram.org/bot987654321:abcdefg_hijklmnop/sendMessage"
    )

    payload = loads(mock_post.call_args_list[1][1]["data"])

    # The merged ``# #`` heading renders its literal hash as bold.
    assert payload["text"] == (
        "*#*\n"
        r"\_\[Apprise Body Title\](http://localhost)\_"
        r" had \[a change\](http://127.0.0.2)"
    )

    # Reset our values
    mock_post.reset_mock()

    # Upstream to use HTML but input specified as Markdown v2
    aobj = Apprise()
    aobj.add("tgram://987654321:abcdefg_hijklmnop/?format=markdown&mdv=2")
    assert len(aobj) == 1

    # MARKDOWN forced by the command line, but TEXT specified as
    # upstream mode
    assert aobj.notify(title=title, body=body, body_format=NotifyFormat.TEXT)

    # Test our calls
    assert mock_post.call_count == 2

    assert (
        mock_post.call_args_list[0][0][0]
        == "https://api.telegram.org/bot987654321:abcdefg_hijklmnop/getUpdates"
    )
    assert (
        mock_post.call_args_list[1][0][0]
        == "https://api.telegram.org/bot987654321:abcdefg_hijklmnop/sendMessage"
    )

    payload = loads(mock_post.call_args_list[1][1]["data"])

    # MarkdownV2 also escapes the literal hash inside the bold heading.
    assert payload["text"] == (
        "*\\#*\n"
        r"\_\[Apprise Body Title\]\(http://localhost\)\_"
        r" had \[a change\]\(http://127\.0\.0\.2\)"
    )

    # Reset our values
    mock_post.reset_mock()

    # Upstream to use HTML but input specified as Markdown v1
    aobj = Apprise()
    aobj.add("tgram://987654321:abcdefg_hijklmnop/?format=markdown&mdv=1")
    assert len(aobj) == 1

    # Set an actual title this time
    title = "# A Great Title"
    body = (
        "_[Apprise Body Title](http://localhost)_"
        " had [a change](http://127.0.0.2)"
    )

    # TEXT forced by the command line, but MARKDOWN specified as
    # upstream mode
    assert aobj.notify(title=title, body=body, body_format=NotifyFormat.TEXT)

    # Test our calls
    assert mock_post.call_count == 2

    assert (
        mock_post.call_args_list[0][0][0]
        == "https://api.telegram.org/bot987654321:abcdefg_hijklmnop/getUpdates"
    )
    assert (
        mock_post.call_args_list[1][0][0]
        == "https://api.telegram.org/bot987654321:abcdefg_hijklmnop/sendMessage"
    )

    payload = loads(mock_post.call_args_list[1][1]["data"])

    # v1's narrower escape set un-escapes what the framework's baseline
    # text-to-markdown pass added, since v1 does not require it. The merged
    # "# # A Great Title" line is itself a heading, so it renders as bold.
    assert payload["text"] == (
        "*# A Great Title*\n"
        r"\_\[Apprise Body Title\](http://localhost)\_"
        r" had \[a change\](http://127.0.0.2)"
    )

    # Reset our values
    mock_post.reset_mock()

    # Upstream to use HTML but input specified as Markdown v2
    aobj = Apprise()
    aobj.add("tgram://987654321:abcdefg_hijklmnop/?format=markdown&mdv=2")
    assert len(aobj) == 1

    # TEXT forced by the command line, but MARKDOWN specified as
    # upstream mode
    assert aobj.notify(title=title, body=body, body_format=NotifyFormat.TEXT)

    # Test our calls
    assert mock_post.call_count == 2

    assert (
        mock_post.call_args_list[0][0][0]
        == "https://api.telegram.org/bot987654321:abcdefg_hijklmnop/getUpdates"
    )
    assert (
        mock_post.call_args_list[1][0][0]
        == "https://api.telegram.org/bot987654321:abcdefg_hijklmnop/sendMessage"
    )

    payload = loads(mock_post.call_args_list[1][1]["data"])

    # MarkdownV2 runs its completion pass over the already-amalgamated
    # title+body; the merged heading line renders as bold, and its
    # literal leading hash still needs its own reserved-character escape.
    assert payload["text"] == (
        "*\\# A Great Title*\n"
        r"\_\[Apprise Body Title\]\(http://localhost\)\_"
        r" had \[a change\]\(http://127\.0\.0\.2\)"
    )

    # Reset our values
    mock_post.reset_mock()

    # Declared Markdown gets MarkdownV2 dialect completion.
    assert aobj.notify(
        title=title, body=body, body_format=NotifyFormat.MARKDOWN
    )

    # Test our calls
    assert mock_post.call_count == 1

    assert (
        mock_post.call_args_list[0][0][0]
        == "https://api.telegram.org/bot987654321:abcdefg_hijklmnop/sendMessage"
    )

    payload = loads(mock_post.call_args_list[0][1]["data"])

    # The declared heading renders as bold. Link destinations only need
    # "(" and ")" escaped, not the full reserved-character set.
    assert payload["text"] == (
        "*A Great Title*\n"
        "_[Apprise Body Title](http://localhost)_ had "
        "[a change](http://127.0.0.2)"
    )

    # Reset our values
    mock_post.reset_mock()

    # No body format specified at all... user definitely must know what
    # they are doing... still no escaping in this circumstance
    assert aobj.notify(title=title, body=body)

    # Test our calls
    assert mock_post.call_count == 1

    assert (
        mock_post.call_args_list[0][0][0]
        == "https://api.telegram.org/bot987654321:abcdefg_hijklmnop/sendMessage"
    )

    payload = loads(mock_post.call_args_list[0][1]["data"])

    # No escaping in this circumstance
    assert (
        payload["text"] == "# A Great Title\r\n"
        "_[Apprise Body Title](http://localhost)_ had "
        "[a change](http://127.0.0.2)"
    )

    # Reset our values
    mock_post.reset_mock()

    #
    # Markdown input aligns directly, then gets title merging and v1
    # dialect completion without an HTML round trip.
    #
    title = "Test Message Title"
    body = "Test Message Body <br/> ok</br>"

    aobj = Apprise()
    aobj.add("tgram://1234:aaaaaaaaa/-1123456245134")
    assert len(aobj) == 1

    assert aobj.notify(
        title=title, body=body, body_format=NotifyFormat.MARKDOWN
    )

    # Test our calls
    assert mock_post.call_count == 1

    assert (
        mock_post.call_args_list[0][0][0]
        == "https://api.telegram.org/bot1234:aaaaaaaaa/sendMessage"
    )

    payload = loads(mock_post.call_args_list[0][1]["data"])

    # The merged heading renders as bold; v1 keeps HTML-looking body text
    # unescaped.
    assert payload["text"] == (
        "*Test Message Title*\nTest Message Body <br/> ok</br>"
    )

    # Reset our values
    mock_post.reset_mock()

    #
    # Now test that <br/> is correctly escaped as it would have been via the
    # CLI mode where the body_format is TEXT
    #

    aobj = Apprise()
    aobj.add("tgram://1234:aaaaaaaaa/-1123456245134")
    assert len(aobj) == 1

    assert aobj.notify(title=title, body=body, body_format=NotifyFormat.TEXT)

    # Test our calls
    assert mock_post.call_count == 1

    assert (
        mock_post.call_args_list[0][0][0]
        == "https://api.telegram.org/bot1234:aaaaaaaaa/sendMessage"
    )

    payload = loads(mock_post.call_args_list[0][1]["data"])

    # Test that everything is escaped properly in a HTML mode
    assert (
        payload["text"] == "<b>Test Message Title</b>\r\n"
        "Test Message Body &lt;br/&gt; ok&lt;/br&gt;"
    )

    # Reset our values
    mock_post.reset_mock()

    #
    # Now test that <br/> is correctly escaped if fed as HTML
    #

    aobj = Apprise()
    aobj.add("tgram://1234:aaaaaaaaa/-1123456245134")
    assert len(aobj) == 1

    assert aobj.notify(title=title, body=body, body_format=NotifyFormat.HTML)

    # Test our calls
    assert mock_post.call_count == 1

    assert (
        mock_post.call_args_list[0][0][0]
        == "https://api.telegram.org/bot1234:aaaaaaaaa/sendMessage"
    )

    payload = loads(mock_post.call_args_list[0][1]["data"])

    # Test that everything is escaped properly in a HTML mode
    assert (
        payload["text"]
        == "<b>Test Message Title</b>\r\nTest Message Body\r\nok"
    )


@mock.patch("requests.post")
def test_plugin_telegram_html_formatting(mock_post):
    """NotifyTelegram() HTML Formatting."""
    # Prepare Mock
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok

    # Simple success response
    mock_post.return_value.content = dumps(
        {
            "ok": True,
            "result": [
                {
                    "update_id": 645421321,
                    "message": {
                        "message_id": 2,
                        "from": {
                            "id": 532389719,
                            "is_bot": False,
                            "first_name": "Chris",
                            "language_code": "en-US",
                        },
                        "chat": {
                            "id": 532389719,
                            "first_name": "Chris",
                            "type": "private",
                        },
                        "date": 1519694394,
                        "text": "/start",
                        "entities": [
                            {
                                "offset": 0,
                                "length": 6,
                                "type": "bot_command",
                            }
                        ],
                    },
                },
            ],
        }
    )

    aobj = Apprise()
    aobj.add("tgram://123456789:abcdefg_hijklmnop/")

    assert len(aobj) == 1

    assert isinstance(aobj[0], NotifyTelegram)

    # Test our HTML Conversion
    title = "<title>&apos;information&apos</title>"
    body = (
        "<em>&quot;This is in Italic&quot</em><br/>"
        "<h5>&emsp;&emspHeadings&nbsp;are dropped and"
        "&nbspconverted to bold</h5>"
    )

    assert aobj.notify(title=title, body=body, body_format=NotifyFormat.HTML)

    # 1 call to look up bot owner, and second for notification
    assert mock_post.call_count == 2

    payload = loads(mock_post.call_args_list[1][1]["data"])

    # Test that everything is escaped properly in a HTML mode
    assert (
        payload["text"]
        == "<b><b>'information'</b>\r\n</b>\r\n<i>\"This is in Italic\""
        "</i>\r\n<b>      Headings are dropped and converted to bold</b>"
    )

    mock_post.reset_mock()

    assert aobj.notify(title=title, body=body, body_format=NotifyFormat.TEXT)

    # owner has already been looked up, so only one call is made
    assert mock_post.call_count == 1

    payload = loads(mock_post.call_args_list[0][1]["data"])

    assert (
        payload["text"]
        == "<b>&lt;title&gt;&amp;apos;information&amp;apos&lt;/title&gt;</b>"
        "\r\n&lt;em&gt;&amp;quot;This is in Italic&amp;quot&lt;/em&gt;&lt;"
        "br/&gt;&lt;h5&gt;&amp;emsp;&amp;emspHeadings&amp;nbsp;are "
        "dropped and&amp;nbspconverted to bold&lt;/h5&gt;"
    )

    # Lest test more complex HTML examples now
    mock_post.reset_mock()

    test_file_01 = os.path.join(TEST_VAR_DIR, "01_test_example.html")
    with open(test_file_01) as html_file:
        assert aobj.notify(
            body=html_file.read(), body_format=NotifyFormat.HTML
        )

    # owner has already been looked up, so only one call is made
    assert mock_post.call_count == 1

    payload = loads(mock_post.call_args_list[0][1]["data"])
    assert (
        payload["text"]
        == "<b>Bootstrap 101 Template</b>\r\n<b>My Title</b>\r\n"
        "<b>Heading 1</b>\r\n- Bullet 1\r\n- Bullet 2\r\n- Bullet 3\r\n"
        "1. Bullet 1\r\n2. Bullet 2\r\n3. Bullet 3\r\n<b>Heading 2</b>\r\n"
        "A div entry\r\nA div entry\r\n"
        "<pre><code class=\"language-python\">print('hello')</code></pre>\r\n"
        "<b>Heading 3</b>\r\n<b>Heading 4</b>\r\n<b>Heading 5</b>\r\n"
        "<b>Heading 6</b>\r\nA set of text\r\n"
        "Another line after the set of text\r\nMore text\r\nlabel"
    )


@mock.patch("requests.post")
def test_plugin_telegram_html_heading_padding_needs_source(
    mock_post,
):
    """HTML heading padding requires a declared source format."""

    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok
    mock_post.return_value.content = "{}"

    body = "<h1>Heading</h1>Body text here"

    aobj = Apprise()
    assert aobj.add("tgram://123456789:abcdefg_hijklmnop/12345678")

    # Declared HTML: the heading sits on its own line.
    assert aobj.notify(body=body, body_format=NotifyFormat.HTML)
    payload = loads(mock_post.call_args_list[-1][1]["data"])
    assert payload["text"] == "<b>Heading</b>\r\nBody text here"
    mock_post.reset_mock()

    # Undeclared input resolves to HTML but remains unpadded.
    assert aobj.notify(body=body)
    payload = loads(mock_post.call_args_list[-1][1]["data"])
    assert payload["text"] == "<b>Heading</b>Body text here"


def test_plugin_telegram_html_reduced_to_supported_tags():
    """HTML is rewritten to the tags Telegram accepts."""

    def reduce(html):
        return TelegramHTMLReducer().reduce(html)

    # Supported tags are kept; their aliases are mapped
    assert (
        reduce(
            "<strong>a</strong><em>b</em><ins>c</ins><strike>d</strike>"
            "<del>e</del><s>f</s><tg-spoiler>g</tg-spoiler>"
        )
        == "<b>a</b><i>b</i><u>c</u><s>d</s><s>e</s><s>f</s>"
        "<tg-spoiler>g</tg-spoiler>"
    )

    # Spoiler spans are kept; other spans only keep their text
    assert (
        reduce('<span class="x tg-spoiler">a</span> <span class="y">b</span>')
        == "<tg-spoiler>a</tg-spoiler> b"
    )

    # Links and custom emoji keep only the attribute Telegram needs
    assert (
        reduce('<a href="http://e.com?a=1&amp;b=2" rel="x">l</a> <a>n</a>')
        == '<a href="http://e.com?a=1&amp;b=2">l</a> n'
    )
    assert (
        reduce('<tg-emoji emoji-id="5368">x</tg-emoji><tg-emoji>y</tg-emoji>')
        == '<tg-emoji emoji-id="5368">x</tg-emoji>y'
    )

    # Links are never nested
    assert (
        reduce('<a href="http://a">x <a href="http://b">y</a></a>')
        == '<a href="http://a">x y</a>'
    )

    # Code blocks keep their language, but no formatting inside them
    assert (
        reduce(
            '<pre><code class="language-py">a <b>&lt;</b>\n b</code></pre>'
            '<code class="language-py">c</code>'
        )
        == '<pre><code class="language-py">a &lt;\n b</code></pre>\r\n'
        "<code>c</code>"
    )

    # A character reference that decodes to nothing adds nothing to code
    assert reduce("<pre>&#1;</pre>x") == "<pre></pre>x"

    # Quotes are never nested and can be expandable
    assert (
        reduce(
            "<blockquote expandable>a<blockquote>b</blockquote></blockquote>"
        )
        == "<blockquote expandable>a\r\nb</blockquote>"
    )

    # Hidden content, images, tables, dividers and unknown tags
    assert (
        reduce(
            '<script>bad()</script><style>x</style><img alt="pic" src="a">'
            '<img src="b"><hr/><table><tr><th>a</th><th>b</th></tr>'
            "<tr><td>1</td><td>2</td></tr></table><font>c</font>"
        )
        == "pic\r\na | b\r\n1 | 2\r\nc"
    )

    # Nested and numbered lists
    assert (
        reduce(
            "<ul><li>a<ul><li>b</li></ul></li></ul>"
            "<ol><li>one</li><li>two</li></ol>"
        )
        == "- a\r\n  - b\r\n1. one\r\n2. two"
    )
    assert reduce("<li>orphan</li>") == "- orphan"

    # Unsupported spaces become plain ones
    assert reduce("a&nbsp;b&emsp;c&nbspd") == "a b   c d"

    # Stray, crossed and unclosed tags still give balanced output
    assert reduce("</b>stray <b>open <i>both") == (
        "stray <b>open <i>both</i></b>"
    )
    assert reduce("<b>x <i>y</b> z</i>") == "<b>x <i>y</i></b> z"

    # Self-closed tags other than br, hr and img are ignored
    assert reduce("a<b/>c") == "ac"

    # A list closed without being opened only ends the line
    assert reduce("a</ul>b") == "a\r\nb"

    # Blank input stays blank
    assert reduce("   \n  ") == ""


def test_plugin_telegram_dialect_leaves_text_alone():
    """Formats Telegram does not render pass through unchanged."""

    obj = NotifyTelegram(bot_token="123456789:abcdefg_hijklmnop", targets=1)
    assert obj.dialect_convert("<b>&</b>", NotifyFormat.TEXT) == "<b>&</b>"


@mock.patch("requests.post")
def test_plugin_telegram_balances_split_html(mock_post):
    """Split HTML pieces only hold balanced, supported tags."""

    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok
    mock_post.return_value.content = "{}"

    aobj = Apprise()
    assert aobj.add(
        "tgram://123456789:abcdefg_hijklmnop/12345678?overflow=split"
    )

    body = (
        "<h1>Title</h1>" + "<p><strong>bold</strong> <em>word</em></p>" * 300
    )
    assert aobj.notify(body=body, body_format=NotifyFormat.HTML)

    texts = [
        loads(call[1]["data"])["text"] for call in mock_post.call_args_list
    ]
    assert len(texts) > 1
    for text in texts:
        assert len(text) <= NotifyTelegram.body_maxlen

        # Only Telegram's own tags remain, and each one is closed
        tags = re.findall(r"</?([a-z-]+)", text)
        assert set(tags) <= {"b", "i"}
        assert text.count("<b>") == text.count("</b>")
        assert text.count("<i>") == text.count("</i>")


@mock.patch("requests.post")
def test_plugin_telegram_html_to_markdown_format(mock_post):
    """Test HTML delivery to Telegram Markdown targets."""

    # Prepare Mock
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok
    mock_post.return_value.content = dumps({"ok": True, "result": True})

    # Simple HTML that our html_to_markdown converter handles
    body = "<b>hello</b> <i>world</i>"

    # Markdown v1 gets the converted body in Telegram's own Markdown dialect
    # (single-asterisk bold, single-underscore italic).
    aobj = Apprise()
    aobj.add("tgram://123456789:abcdefg_hijklmnop/12345?format=markdown&mdv=1")
    assert len(aobj) == 1

    assert aobj.notify(body=body, body_format=NotifyFormat.HTML)

    assert mock_post.call_count == 1
    payload = loads(mock_post.call_args_list[0][1]["data"])

    assert payload["parse_mode"] == "MARKDOWN"
    assert payload["text"] == "*hello* _world_"

    mock_post.reset_mock()

    # Markdown v2 gets the same dialect-correct delimiters, left unescaped so
    # Telegram still parses them as real formatting.
    aobj = Apprise()
    aobj.add("tgram://123456789:abcdefg_hijklmnop/12345?format=markdown&mdv=2")
    assert len(aobj) == 1

    assert aobj.notify(body=body, body_format=NotifyFormat.HTML)

    assert mock_post.call_count == 1
    payload = loads(mock_post.call_args_list[0][1]["data"])

    assert payload["parse_mode"] == "MarkdownV2"
    assert payload["text"] == "*hello* _world_"

    mock_post.reset_mock()

    # Telegram escapes v2-only punctuation not covered by generic Markdown.
    aobj = Apprise()
    aobj.add("tgram://123456789:abcdefg_hijklmnop/12345?format=markdown&mdv=2")
    assert len(aobj) == 1

    assert aobj.notify(
        body="<p>3:00 p.m. (sharp)! Don't be late - see you there.</p>",
        body_format=NotifyFormat.HTML,
    )

    assert mock_post.call_count == 1
    payload = loads(mock_post.call_args_list[0][1]["data"])

    assert payload["parse_mode"] == "MarkdownV2"
    assert payload["text"] == (
        r"3:00 p\.m\. \(sharp\)\! Don't be late \- see you there\."
    )

    mock_post.reset_mock()

    # Markdown v2 target, plain TEXT body
    aobj = Apprise()
    aobj.add("tgram://123456789:abcdefg_hijklmnop/12345?format=markdown&mdv=2")
    assert len(aobj) == 1

    assert aobj.notify(
        body="Tag #1 and *not* bold", body_format=NotifyFormat.TEXT
    )

    assert mock_post.call_count == 1
    payload = loads(mock_post.call_args_list[0][1]["data"])

    assert payload["parse_mode"] == "MarkdownV2"
    assert payload["text"] == r"Tag \#1 and \*not\* bold"

    mock_post.reset_mock()

    # Markdown v2 target, no body_format specified
    aobj = Apprise()
    aobj.add("tgram://123456789:abcdefg_hijklmnop/12345?format=markdown&mdv=2")
    assert len(aobj) == 1

    assert aobj.notify(body="**already** markdown #tag")

    assert mock_post.call_count == 1
    payload = loads(mock_post.call_args_list[0][1]["data"])

    assert payload["parse_mode"] == "MarkdownV2"
    assert payload["text"] == "**already** markdown #tag"

    mock_post.reset_mock()

    # A heading has no MarkdownV2 entity, so it renders as bold instead of
    # a literal, escaped "#" -- either way Telegram never sees a bare '#'
    # that would make it reject the whole message.
    aobj = Apprise()
    aobj.add("tgram://123456789:abcdefg_hijklmnop/12345?format=markdown&mdv=2")
    assert len(aobj) == 1

    assert aobj.notify(
        body="<h1>Title</h1><p>body text</p>", body_format=NotifyFormat.HTML
    )

    assert mock_post.call_count == 1
    payload = loads(mock_post.call_args_list[0][1]["data"])

    assert payload["parse_mode"] == "MarkdownV2"
    assert payload["text"] == "*Title*\n\nbody text"

    mock_post.reset_mock()

    # Convert CommonMark links to Telegram's bare-destination syntax.
    aobj = Apprise()
    aobj.add("tgram://123456789:abcdefg_hijklmnop/12345?format=markdown&mdv=2")
    assert len(aobj) == 1

    assert aobj.notify(
        body='<a href="https://example.com/x">click</a>',
        body_format=NotifyFormat.HTML,
    )

    assert mock_post.call_count == 1
    payload = loads(mock_post.call_args_list[0][1]["data"])

    assert payload["parse_mode"] == "MarkdownV2"
    assert payload["text"] == "[click](https://example.com/x)"

    mock_post.reset_mock()

    # Lists and tables have no MarkdownV2 entity either -- their markers
    # need the same escaping as a heading's, for the same reason.
    aobj = Apprise()
    aobj.add("tgram://123456789:abcdefg_hijklmnop/12345?format=markdown&mdv=2")
    assert len(aobj) == 1

    assert aobj.notify(
        body="<ul><li>one</li><li>two</li></ul>",
        body_format=NotifyFormat.HTML,
    )

    assert mock_post.call_count == 1
    payload = loads(mock_post.call_args_list[0][1]["data"])

    assert payload["parse_mode"] == "MarkdownV2"
    assert payload["text"] == "\\- one\n\\- two"

    mock_post.reset_mock()

    aobj = Apprise()
    aobj.add("tgram://123456789:abcdefg_hijklmnop/12345?format=markdown&mdv=2")
    assert len(aobj) == 1

    assert aobj.notify(
        body="<table><tr><td>A</td><td>B</td></tr></table>",
        body_format=NotifyFormat.HTML,
    )

    assert mock_post.call_count == 1
    payload = loads(mock_post.call_args_list[0][1]["data"])

    assert payload["parse_mode"] == "MarkdownV2"
    assert payload["text"] == (
        "\\| A \\| B \\|\n\\| \\-\\-\\- \\| \\-\\-\\- \\|"
    )

    mock_post.reset_mock()

    # A code span's content is just as literal to Telegram as it is to
    # CommonMark -- the strict escape pass must not touch it.
    aobj = Apprise()
    aobj.add("tgram://123456789:abcdefg_hijklmnop/12345?format=markdown&mdv=2")
    assert len(aobj) == 1

    assert aobj.notify(
        body="<code>a.b-c|d</code>", body_format=NotifyFormat.HTML
    )

    assert mock_post.call_count == 1
    payload = loads(mock_post.call_args_list[0][1]["data"])

    assert payload["parse_mode"] == "MarkdownV2"
    assert payload["text"] == "`a.b-c|d`"


@mock.patch("requests.post")
def test_plugin_telegram_html_to_markdown_hardening(mock_post):
    """Test edge cases in the CommonMark-to-Telegram dialect adaptation."""

    # Prepare Mock
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok
    mock_post.return_value.content = dumps({"ok": True, "result": True})

    def notify(body, mdv="2"):
        aobj = Apprise()
        aobj.add(
            "tgram://123456789:abcdefg_hijklmnop/12345"
            f"?format=markdown&mdv={mdv}"
        )
        assert len(aobj) == 1
        assert aobj.notify(body=body, body_format=NotifyFormat.HTML)
        payload = loads(mock_post.call_args_list[-1][1]["data"])
        mock_post.reset_mock()
        return payload["text"]

    # A link destination containing a literal ')' or '\' must have those
    # escaped.
    assert notify('<a href="https://example.com/a(b)c">x</a>') == (
        "[x](https://example.com/a(b\\)c)"
    )

    # A code span's content needs every '`'/'\' inside it escaped.
    assert notify("<code>a\\b</code>") == "`a\\\\b`"
    assert notify("<code>a`b</code>") == "`a\\`b`"

    # Either adjacent nesting order flattens to italic around bold.
    assert notify("<b><i>x</i></b>") == "_*x*_"
    assert notify("<i><b>x</b></i>") == "_*x*_"

    # Legacy Markdown (v1) doesn't support nested entities at all.
    assert notify("<b>a <i>b</i> c</b>", mdv="1") == "*a b c*"

    # Telegram v1 keeps only the outer span from nested CommonMark.
    assert notify("<b><i>x</i></b>", mdv="1") == "_x_"
    assert notify("<i><b>x</b></i>", mdv="1") == "_x_"

    # Legacy Markdown only recognizes a backslash escape in front of
    # '`'/'*'/'_'/'['.
    assert (
        notify("<p>#tag (test)! &lt;x&gt; ~wave~</p>", mdv="1")
        == "#tag (test)! <x> ~wave~"
    )
    assert (
        notify("<p>a[b]c *lit* _lit_ `lit`</p>", mdv="1")
        == "a\\[b\\]c \\*lit\\* \\_lit\\_ \\`lit\\`"
    )

    # Non-adjacent nesting and sibling spans are unaffected.
    assert notify("<b>bold <i>italic</i> still bold</b>") == (
        "*bold _italic_ still bold*"
    )
    # Adjacent bold tags retain and escape ambiguous middle markers.
    assert notify("<b>A</b><b>B</b>") == "*A\\*\\*\\*\\*B*"

    # A nested bold opening *while italic is already open, with real text in
    # between* (so the two opening delimiters aren't touching) is a completely.
    assert notify("<i>a <b>b</b> c</i>") == "_a *b* c_"
    assert notify("<i>a <b>b</b> c</i>", mdv="1") == "_a b c_"

    # The reverse nesting (bold containing italic, separated by text) was
    # already correct, and must stay that way.
    assert notify("<b>a <i>b</i> c</b>") == "*a _b_ c*"

    # A literal "\x01<digits>\x01"-shaped sequence in ordinary text must pass
    # through completely unaltered.
    assert notify("literal \x010\x01 text, no code or links at all") == (
        "literal \x010\x01 text, no code or links at all"
    )

    # overflow=split can hand this method just one chunk of a longer body, with
    # a span that doesn't open or close until a different chunk entirely.
    aobj = Apprise()
    aobj.add(
        "tgram://123456789:abcdefg_hijklmnop/12345"
        "?format=markdown&mdv=2&overflow=split"
    )
    assert len(aobj) == 1
    assert aobj.notify(
        body="<b>" + ("x" * 4990) + "</b>", body_format=NotifyFormat.HTML
    )
    assert mock_post.call_count == 2
    texts = [loads(c[1]["data"])["text"] for c in mock_post.call_args_list]

    # Each half is independently balanced -- an odd number of un-escaped
    # '*'/'_' in either one would mean Telegram still rejects it.
    for text in texts:
        assert text.count("*") % 2 == 0
        assert text.count("_") % 2 == 0

    # A split at a bold close must not leave an empty entity.
    assert texts[1] == "x" * (len(texts[1]))

    # The same overflow split can also land mid-code-span or mid-link.
    assert (
        NotifyTelegram._commonmark_to_telegram(
            "text ``unterminated", strict=True
        )
        == "text \\`\\`unterminated"
    )
    # "](<" with no preceding "[" (so not a real link) and no closing ">)"
    # either: every reserved bracket/paren is escaped as stray punctuation.
    assert (
        NotifyTelegram._commonmark_to_telegram(
            "a](<https://incomplete no close", strict=True
        )
        == "a\\]\\(\\<https://incomplete no close"
    )

    # Always escape stray MarkdownV2 brackets and parentheses.
    assert (
        NotifyTelegram._commonmark_to_telegram(
            "literal (value) and [bracket] text", strict=True
        )
        == "literal \\(value\\) and \\[bracket\\] text"
    )

    # Prevent an orphaned "[" from matching a later unrelated link.
    assert (
        NotifyTelegram._commonmark_to_telegram("[a] b (c) ](d)", strict=True)
        == "\\[a\\] b \\(c\\) \\]\\(d\\)"
    )

    # An invalid inner angle link must not reuse or consume its outer label.
    # Telegram returns the unresolved structure as escaped literal text.
    body = "[OUTER [INNER](<badstuff)](https://example.com)"
    assert NotifyTelegram._commonmark_to_telegram(body, strict=True) == (
        "\\[OUTER \\[INNER\\]\\(\\<badstuff\\)\\]\\(https://example\\.com\\)"
    )

    # A "]" with no "(" must retire its "[" in both Markdown modes,
    # instead of leaving it pending for a later, unrelated link to reuse.
    stray_body = "[label] and ](http://x.com/a(b)c) end"
    assert (
        NotifyTelegram._commonmark_to_telegram(stray_body, strict=False)
        == r"\[label] and ](http://x.com/a(b)c) end"
    )
    assert NotifyTelegram._commonmark_to_telegram(stray_body, strict=True) == (
        "\\[label\\] and \\]\\(http://x\\.com/a\\(b\\)c\\) end"
    )

    # An invalid destination becomes fully escaped literal text in v2.
    assert (
        NotifyTelegram._commonmark_to_telegram(
            "[label](has space)", strict=True
        )
        == "\\[label\\]\\(has space\\)"
    )

    # An unfinished destination follows the same literal-text path.
    assert (
        NotifyTelegram._commonmark_to_telegram(
            "[label](unterminated", strict=True
        )
        == "\\[label\\]\\(unterminated"
    )

    # Telegram v1 keeps the rejected destination as literal text.
    assert (
        NotifyTelegram._commonmark_to_telegram(
            "[label](has space)", strict=False
        )
        == r"\[label](has space)"
    )

    # An unfinished angle destination follows the same v2 fallback.
    assert (
        NotifyTelegram._commonmark_to_telegram(
            "[label](<https://unterminated", strict=True
        )
        == "\\[label\\]\\(\\<https://unterminated"
    )

    # Telegram v1 also keeps the unfinished angle destination literal.
    assert (
        NotifyTelegram._commonmark_to_telegram(
            "[label](<https://unterminated", strict=False
        )
        == r"\[label](<https://unterminated"
    )

    # Escape a dangling "[" during end-of-scan cleanup.
    assert (
        NotifyTelegram._commonmark_to_telegram(
            "text [dangling forever", strict=True
        )
        == "text \\[dangling forever"
    )

    # Preserve plain Markdown links; only "(" and ")" need escaping inside
    # a destination, not the full MarkdownV2 reserved-character set.
    assert (
        NotifyTelegram._commonmark_to_telegram(
            "[a link](https://example.com/x.y)", strict=True
        )
        == "[a link](https://example.com/x.y)"
    )

    # Preserve an escaped parenthesis inside a plain link destination.
    assert (
        NotifyTelegram._commonmark_to_telegram(
            "[label](http://example.com/a\\)b)", strict=True
        )
        == "[label](http://example.com/a\\)b)"
    )

    # Preserve balanced parentheses inside a plain link destination.
    assert (
        NotifyTelegram._commonmark_to_telegram(
            "[label](https://example.com/a_(b))", strict=True
        )
        == "[label](https://example.com/a_\\(b\\))"
    )

    # Apply the same parenthesis balancing in Telegram V1.
    assert (
        NotifyTelegram._commonmark_to_telegram(
            "[label](https://example.com/a_(b))", strict=False
        )
        == "[label](https://example.com/a_\\(b\\))"
    )

    # Keep an opener with no closer as literal (escaped) text.
    assert NotifyTelegram._commonmark_to_telegram("****x") == r"\*\*\*\*x"

    # Keep a run that is neither left- nor right-flanking as literal text.
    assert NotifyTelegram._commonmark_to_telegram("******") == r"\*" * 6

    # Keep unmatched markers in a complete body as literal text.
    f1 = NotifyTelegram._commonmark_to_telegram
    assert f1("***italic text") == r"\*\*\*italic text"
    assert f1("**text") == r"\*\*text"
    assert f1("**") == r"\*\*"

    # User-provided Private Use text must not collide in either Markdown mode.
    marker = chr(0xE000)
    attack = f"before {marker}0{marker} after"
    assert f1(attack, strict=False) == attack
    assert f1(attack, strict=True) == attack
    assert f1(f"*italic* {attack}", strict=False) == f"_italic_ {attack}"

    # Strict MarkdownV2 escapes literal emphasis markers.
    assert (
        NotifyTelegram._commonmark_to_telegram("a" * 9 + "_", strict=True)
        == "a" * 9 + "\\_"
    )
    assert (
        NotifyTelegram._commonmark_to_telegram("a" * 9 + "*", strict=True)
        == "a" * 9 + "\\*"
    )
    # Legacy v1 also escapes a literal marker outside a span, or Telegram
    # rejects it as an entity that never ends.
    assert (
        NotifyTelegram._commonmark_to_telegram("a" * 9 + "_", strict=False)
        == "a" * 9 + "\\_"
    )

    # Preserve genuine underscore-based italics.
    assert (
        NotifyTelegram._commonmark_to_telegram("_italic_", strict=True)
        == "_italic_"
    )
    assert (
        NotifyTelegram._commonmark_to_telegram(
            "**bold** _italic_", strict=True
        )
        == "*bold* _italic_"
    )
    # Escape intraword underscores instead of treating them as emphasis.
    assert (
        NotifyTelegram._commonmark_to_telegram("foo_bar_baz", strict=True)
        == "foo\\_bar\\_baz"
    )
    # Keep intraword double underscores literal, not underlined.
    assert (
        NotifyTelegram._commonmark_to_telegram("a__b__c", strict=True)
        == "a\\_\\_b\\_\\_c"
    )
    # Render valid double-underscore CommonMark as Telegram bold.
    assert (
        NotifyTelegram._commonmark_to_telegram("__bold__", strict=True)
        == "*bold*"
    )
    assert (
        NotifyTelegram._commonmark_to_telegram(
            "before __bold__ after", strict=True
        )
        == "before *bold* after"
    )

    # Keep adjacent asterisk and underscore families independent.
    assert NotifyTelegram._commonmark_to_telegram("*_", strict=True) == (
        "\\*\\_"
    )

    # Keep unrelated unmatched delimiter families as literal text.
    assert (
        NotifyTelegram._commonmark_to_telegram("**_a", strict=False)
        == r"\*\*\_a"
    )

    # Do not close asterisk emphasis with an underscore.
    assert (
        NotifyTelegram._commonmark_to_telegram("***_", strict=True)
        == "\\*\\*\\*\\_"
    )

    # Match underscores across an unrelated literal asterisk run.
    assert (
        NotifyTelegram._commonmark_to_telegram("_***_", strict=True)
        == "_\\*\\*\\*_"
    )

    # Leave unmatched width literal beside a valid italic span.
    assert (
        NotifyTelegram._commonmark_to_telegram("__a_", strict=True) == "\\__a_"
    )

    # Preserve an unmatched underscore opener.
    assert (
        NotifyTelegram._commonmark_to_telegram("____a", strict=True)
        == "\\_\\_\\_\\_a"
    )

    # Preserve leftover width after closing bold.
    assert (
        NotifyTelegram._commonmark_to_telegram("__a___", strict=True)
        == "*a*\\_"
    )

    # Keep unmatched mixed delimiter families as literal text.
    assert (
        NotifyTelegram._commonmark_to_telegram("*__a", strict=False)
        == r"\*\_\_a"
    )

    # A run wide enough to supply both kinds of emphasis nests regular
    # emphasis outermost and bold innermost, the same as for asterisks.
    assert (
        NotifyTelegram._commonmark_to_telegram("___a___", strict=True)
        == "_*a*_"
    )

    # Opening requires content, so empty trailing bold is unreachable.

    # A link destination containing a backslash-escaped '>' in V1 mode:
    # the scan skips escaped characters and still finds the '>)' terminator.
    assert (
        notify('<a href="https://example.com/x>y">click</a>', mdv="1")
        == r"[click](https://example.com/x\\>y)"
    )

    # Telegram v1 renders the merged title heading as bold.
    aobj_v1 = Apprise()
    aobj_v1.add(
        "tgram://123456789:abcdefg_hijklmnop/12345?format=markdown&mdv=1"
    )
    assert aobj_v1.notify(
        body="<b>hello</b>", title="My Title", body_format=NotifyFormat.HTML
    )
    payload = loads(mock_post.call_args_list[-1][1]["data"])
    assert payload["text"] == "*My Title*\n*hello*"
    mock_post.reset_mock()

    # Title that reduces to an empty string after stripping leading heading and
    # list characters (html_to_markdown converts " - " to "-").
    assert aobj_v1.notify(
        body="<b>hello</b>", title="  - ", body_format=NotifyFormat.HTML
    )
    payload = loads(mock_post.call_args_list[-1][1]["data"])
    assert payload["text"] == "*hello*"
    mock_post.reset_mock()


def test_plugin_telegram_v1_unmatched_markers_escaped():
    """Legacy Markdown rejects an entity marker that never closes.

    Telegram answers "can't parse entities" for a lone "_", "*", "`" or "["
    outside an entity, and reads text inside an entity literally.
    """
    f1 = NotifyTelegram._commonmark_to_telegram

    # CommonMark literals outside a span are escaped.
    assert f1("Backup of app_data failed") == r"Backup of app\_data failed"
    assert f1("snake_case_name") == r"snake\_case\_name"
    assert f1("5 * 3 = 15") == r"5 \* 3 = 15"
    assert f1("a lone ` tick") == r"a lone \` tick"
    assert f1("x ``` y") == r"x \`\`\` y"

    # Text inside a visible span is left as is.
    assert f1("**disk a_b** on c_d") == r"*disk a_b* on c\_d"
    assert f1("_it a*b_ x*y") == r"_it a*b_ x\*y"
    assert f1("**a ` b** c") == "*a ` b* c"
    assert f1("**[a** b") == "*[a* b"

    # A "[" that opens no link is escaped too.
    assert f1("[ERROR] disk full") == r"\[ERROR] disk full"
    assert f1("a [b") == r"a \[b"

    # Real markup and code spans are unchanged.
    assert f1("**bold** and _it_") == "*bold* and _it_"
    assert f1("`code_x` y_z") == r"`code_x` y\_z"

    # MarkdownV2 output is unchanged.
    assert f1("app_data", strict=True) == r"app\_data"
    assert f1("a ` b", strict=True) == r"a \` b"


@mock.patch("requests.post")
def test_plugin_telegram_v1_markdown_body_with_underscore(mock_post):
    """A Markdown body is sent in legacy Markdown with its literals escaped."""
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok
    mock_post.return_value.content = dumps({"ok": True, "result": True})

    aobj = Apprise()
    aobj.add("tgram://123456789:abcdefg_hijklmnop/12345")
    assert aobj.notify(
        title="Backup",
        body="Backup of app_data failed",
        body_format=NotifyFormat.MARKDOWN,
    )
    payload = loads(mock_post.call_args_list[-1][1]["data"])
    assert payload["parse_mode"] == "MARKDOWN"
    assert payload["text"] == "*Backup*\n" r"Backup of app\_data failed"


@mock.patch("requests.post")
def test_plugin_telegram_overflow_split_repair(mock_post):
    """Test generic split repair before Telegram dialect conversion."""

    # Prepare Mock
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok
    mock_post.return_value.content = dumps({"ok": True, "result": True})

    def notify_split(body):
        aobj = Apprise()
        aobj.add(
            "tgram://123456789:abcdefg_hijklmnop/12345"
            "?format=markdown&mdv=2&overflow=split"
        )
        assert len(aobj) == 1
        assert aobj.notify(body=body, body_format=NotifyFormat.HTML)
        texts = [loads(c[1]["data"])["text"] for c in mock_post.call_args_list]
        mock_post.reset_mock()
        return texts

    # A bold span long enough to force a split, immediately followed by plain
    # text that was never part of it.
    texts = notify_split(
        "<b>" + ("x" * 4990) + "</b>" + "TAIL_SHOULD_NOT_BE_BOLD"
    )
    assert len(texts) == 2
    # The part that fit keeps its formatting...
    assert texts[0].startswith("*x")
    assert texts[0].endswith("x*")
    # ...but the unrelated trailing text does not become bold.
    assert "TAIL" in texts[1]
    assert not texts[1].startswith("*")
    for text in texts:
        assert text.count("*") % 2 == 0
        assert text.count("_") % 2 == 0

    # A link long enough that its URL alone forces a split.
    url = "https://example.com/" + ("a" * 4990)
    texts = notify_split(f'<a href="{url}">click here</a>')
    assert len(texts) >= 2
    for text in texts:
        # Every chunk must be valid MarkdownV2: no unescaped reserved chars.
        assert not re.search(r"(?<!\\)[_*\[\]()~`>#+=|{}.!<-]", text)

    # A <pre> block long enough to force a split.
    content = "line.with.dots-and-dashes_under " * 200
    texts = notify_split(f"<pre>{content}</pre>")
    assert len(texts) >= 2
    for text in texts:
        assert not re.search(r"(?<!\\)[_*\[\]()~`>#+=|{}.!<-]", text)

    # A short message that never triggers a split at all is unaffected.
    texts = notify_split("<b>short</b> <i>text</i>")
    assert texts == ["*short* _text_"]

    # Conversion tests cover the repair primitive used indirectly here.


@mock.patch("requests.post")
def test_plugin_telegram_declared_markdown_split_repair(mock_post):
    """Declared Markdown uses the same split repair as converted HTML."""

    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok
    mock_post.return_value.content = dumps({"ok": True, "result": True})

    def notify_split(body, body_format):
        aobj = Apprise()
        aobj.add(
            "tgram://123456789:abcdefg_hijklmnop/12345"
            "?format=markdown&mdv=2&overflow=split"
        )
        assert len(aobj) == 1
        assert aobj.notify(body=body, body_format=body_format)
        texts = [loads(c[1]["data"])["text"] for c in mock_post.call_args_list]
        mock_post.reset_mock()
        return texts

    # Force a split after a long bold span.
    body = "**" + ("x" * 4990) + "**" + "TAIL SHOULD NOT BE BOLD"
    texts_html = notify_split(
        "<b>" + ("x" * 4990) + "</b>" + "TAIL SHOULD NOT BE BOLD",
        NotifyFormat.HTML,
    )
    texts_md = notify_split(body, NotifyFormat.MARKDOWN)

    # Declared Markdown matches HTML-derived Markdown chunk repair.
    assert texts_md == texts_html

    # Short declared Markdown still gets dialect completion.
    texts = notify_split("**short** _text_", NotifyFormat.MARKDOWN)
    assert texts == ["*short* _text_"]

    # Undeclared input skips dialect completion and repair.
    texts = notify_split("**short** _text_", None)
    assert texts == ["**short** _text_"]


@mock.patch("requests.post")
def test_plugin_telegram_dialect_overflow(mock_post):
    """Apply the selected overflow mode after MarkdownV2 escaping
    grows text."""

    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok
    mock_post.return_value.content = dumps({"ok": True, "result": True})

    def notify(overflow):
        aobj = Apprise()
        aobj.add(
            "tgram://123456789:abcdefg_hijklmnop/12345"
            f"?format=markdown&mdv=2&overflow={overflow}"
        )
        assert len(aobj) == 1
        # Escaping periods makes this body exceed the converted limit.
        assert aobj.notify(body="." * 5000, body_format=NotifyFormat.MARKDOWN)
        texts = [loads(c[1]["data"])["text"] for c in mock_post.call_args_list]
        mock_post.reset_mock()
        return texts

    # UPSTREAM: exactly one message, sent oversized rather than split.
    texts = notify("upstream")
    assert len(texts) == 1
    assert len(texts[0]) > NotifyTelegram.body_maxlen

    # TRUNCATE: exactly one message, clipped to fit.
    texts = notify("truncate")
    assert len(texts) == 1
    assert len(texts[0]) <= NotifyTelegram.body_maxlen

    # SPLIT: as many messages as needed, each one within the limit.
    texts = notify("split")
    assert len(texts) > 1
    for text in texts:
        assert len(text) <= NotifyTelegram.body_maxlen


@mock.patch("requests.post")
def test_plugin_telegram_dialect_attachment_order(mock_post):
    """Place one attachment before or after dialect-split text pieces."""
    from apprise.attachment.memory import AttachMemory

    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = dumps({"ok": True, "result": True})
    mock_post.return_value = response

    mem = AttachMemory(
        content=b"hello world", name="test.txt", mimetype="text/plain"
    )

    def notify(content_mode):
        aobj = Apprise()
        aobj.add(
            "tgram://123456789:abcdefg_hijklmnop/12345"
            f"?format=markdown&mdv=2&overflow=split&content={content_mode}"
        )
        assert len(aobj) == 1
        # Escaping doubles this initially valid body and forces dialect
        # splitting.
        assert aobj.notify(
            body="." * 3000, attach=mem, body_format=NotifyFormat.MARKDOWN
        )
        # Classify each call as a text message or an attachment upload.
        kinds = [
            "text" if "sendMessage" in c[0][0] else "attach"
            for c in mock_post.call_args_list
        ]
        mock_post.reset_mock()
        return kinds

    # content=before: every text piece goes out, then the attachment.
    kinds = notify("before")
    assert kinds.count("text") > 1
    assert kinds.count("attach") == 1
    assert kinds == ["text"] * kinds.count("text") + ["attach"]

    # content=after: the attachment goes out first, then every piece.
    kinds = notify("after")
    assert kinds.count("text") > 1
    assert kinds.count("attach") == 1
    assert kinds == ["attach"] + ["text"] * (len(kinds) - 1)


@mock.patch("requests.post")
def test_plugin_telegram_overflow_no_invented_emphasis(mock_post):
    """Do not invent emphasis for an unmatched literal delimiter."""

    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok
    mock_post.return_value.content = dumps({"ok": True, "result": True})

    def notify(overflow):
        aobj = Apprise()
        aobj.add(
            "tgram://123456789:abcdefg_hijklmnop/12345"
            f"?format=markdown&mdv=2&overflow={overflow}"
        )
        assert len(aobj) == 1
        # Keep spacing after valid emphasis so its closer is not intraword.
        body = "*_a_ test " + ("x" * 5000)
        assert aobj.notify(body=body, body_format=NotifyFormat.MARKDOWN)
        texts = [loads(c[1]["data"])["text"] for c in mock_post.call_args_list]
        mock_post.reset_mock()
        return texts

    # SPLIT preserves both the escaped literal and valid emphasis.
    texts = notify("split")
    assert texts[0].startswith("\\*_a_")

    # TRUNCATE preserves the same prefix in one message.
    texts = notify("truncate")
    assert len(texts) == 1
    assert texts[0].startswith("\\*_a_")


@mock.patch("requests.post")
def test_plugin_telegram_threads(mock_post):
    """NotifyTelegram() Threads/Topics."""
    # Prepare Mock
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok

    # Simple success response
    mock_post.return_value.content = dumps(
        {
            "ok": True,
            "result": [
                {
                    "update_id": 645421321,
                    "message": {
                        "message_id": 2,
                        "from": {
                            "id": 532389719,
                            "is_bot": False,
                            "first_name": "Chris",
                            "language_code": "en-US",
                        },
                        "chat": {
                            "id": 532389719,
                            "first_name": "Chris",
                            "type": "private",
                        },
                        "date": 1519694394,
                        "text": "/start",
                        "entities": [
                            {
                                "offset": 0,
                                "length": 6,
                                "type": "bot_command",
                            }
                        ],
                    },
                },
            ],
        }
    )

    aobj = Apprise()
    aobj.add("tgram://123456789:abcdefg_hijklmnop/?thread=1234")

    assert len(aobj) == 1

    assert isinstance(aobj[0], NotifyTelegram)

    body = "my threaded message"

    assert aobj.notify(body=body)

    # 1 call to look up bot owner, and second for notification
    assert mock_post.call_count == 2

    payload = loads(mock_post.call_args_list[1][1]["data"])

    assert "message_thread_id" in payload
    assert payload["message_thread_id"] == 1234

    mock_post.reset_mock()

    aobj = Apprise()
    aobj.add("tgram://123456789:abcdefg_hijklmnop/?topic=1234")

    assert len(aobj) == 1

    assert isinstance(aobj[0], NotifyTelegram)

    body = "my message"

    assert aobj.notify(body=body)

    # 1 call to look up bot owner, and second for notification
    assert mock_post.call_count == 2

    payload = loads(mock_post.call_args_list[1][1]["data"])

    assert "message_thread_id" in payload
    assert payload["message_thread_id"] == 1234

    mock_post.reset_mock()

    aobj = Apprise()
    aobj.add("tgram://123456789:abcdefg_hijklmnop/9876:1234/9876:1111")

    assert len(aobj) == 1

    assert isinstance(aobj[0], NotifyTelegram)

    body = "my message"

    assert aobj.notify(body=body)

    # 1 call to look up bot owner, and second for notification
    assert mock_post.call_count == 2

    payload = loads(mock_post.call_args_list[0][1]["data"])

    assert "message_thread_id" in payload
    assert payload["message_thread_id"] == 1111

    payload = loads(mock_post.call_args_list[1][1]["data"])

    assert "message_thread_id" in payload
    assert payload["message_thread_id"] == 1234

    mock_post.reset_mock()


@mock.patch("requests.post")
def test_plugin_telegram_markdown_v2(mock_post):
    """NotifyTelegram() MarkdownV2."""
    # Prepare Mock
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok

    # Simple success response
    mock_post.return_value.content = dumps(
        {
            "ok": True,
            "result": [
                {
                    "update_id": 645421321,
                    "message": {
                        "message_id": 2,
                        "from": {
                            "id": 532389719,
                            "is_bot": False,
                            "first_name": "Chris",
                            "language_code": "en-US",
                        },
                        "chat": {
                            "id": 532389719,
                            "first_name": "Chris",
                            "type": "private",
                        },
                        "date": 1519694394,
                        "text": "/start",
                        "entities": [
                            {
                                "offset": 0,
                                "length": 6,
                                "type": "bot_command",
                            }
                        ],
                    },
                },
            ],
        }
    )

    aobj = Apprise()
    aobj.add("tgram://123456789:abcdefg_hijklmnop/?mdv=2&format=markdown")
    assert len(aobj) == 1
    assert isinstance(aobj[0], NotifyTelegram)

    body = "# my message\r\n## more content\r\n\\# already escaped hashtag"

    # Test with body format set to markdown
    assert aobj.notify(body=body, body_format=NotifyFormat.TEXT)

    # 1 call to look up bot owner, and second for notification
    assert mock_post.call_count == 2
    payload = loads(mock_post.call_args_list[1][1]["data"])

    # Literal backslashes are escaped along with MarkdownV2 syntax.
    assert (
        payload["text"] == "\\# my message\r\n"
        "\\#\\# more content\r\n\\\\\\# already escaped hashtag"
    )

    mock_post.reset_mock()

    # We'll iterate over all of the bad unsupported characters
    mdv2_unsupported = (
        "_",
        "*",
        "[",
        "]",
        "(",
        ")",
        "~",
        "`",
        ">",
        "#",
        "+",
        "=",
        "|",
        "{",
        "}",
        ".",
        "!",
        "-",
    )

    for c in mdv2_unsupported:
        body = f"bad character: {c}, and already escapped \\{c}"

        # Test with body format set to markdown
        assert aobj.notify(body=body, body_format=NotifyFormat.TEXT)
        assert mock_post.call_count == 1
        payload = loads(mock_post.call_args_list[0][1]["data"])

        # The literal backslash before the second occurrence is escaped too.
        assert (
            payload["text"]
            == f"bad character: \\{c}, and already escapped \\\\\\{c}"
        )

        mock_post.reset_mock()


def test_plugin_telegram_standalone_autolink_dialect():
    """A complete standalone autolink converts safely in both modes."""

    # Telegram auto-links the URL after its brackets are removed.
    assert (
        NotifyTelegram._commonmark_to_telegram(
            "see <https://a*b> now", strict=False
        )
        == "see https://a*b now"
    )

    # Escape reserved markup characters inside a MarkdownV2 autolink.
    assert (
        NotifyTelegram._commonmark_to_telegram(
            "see <https://a*b-c> now", strict=True
        )
        == "see https://a\\*b\\-c now"
    )

    # Strict mode also escapes every other reserved autolink character.
    assert (
        NotifyTelegram._commonmark_to_telegram(
            "see <https://x.example/*a*_b_[c](d)`e`> now", strict=True
        )
        == "see https://x\\.example/\\*a\\*\\_b\\_\\[c\\]\\(d\\)\\`e\\` now"
    )


@mock.patch("requests.post")
def test_plugin_telegram_attach_memory(mock_post):
    """Regression: AttachMemory must be sendable without OSError."""
    from apprise.attachment.memory import AttachMemory

    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = dumps({"ok": True, "result": True})
    mock_post.return_value = response

    obj = NotifyTelegram(
        bot_token="123456789:abcdefg_hijklmnop", targets="12345"
    )

    mem = AttachMemory(
        content=b"<html><body><h1>Test</h1></body></html>",
        name="test.html",
        mimetype="text/html",
    )

    assert bool(obj.notify(body="Test", attach=mem)) is True
    assert mock_post.call_count >= 1


@mock.patch("requests.post")
def test_plugin_telegram_template_blocks(mock_post, tmpdir):
    """NotifyTelegram() - Rich Message template mode."""
    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = dumps({"ok": True})
    mock_post.return_value = response

    # Write a minimal Rich Message JSON template to disk
    template = tmpdir.join("blocks.json")
    template.write(
        cleandoc("""
        {
          "blocks": [
            {
              "type": "section_heading",
              "text": "{{app_title}}"
            },
            {
              "type": "paragraph",
              "text": "{{app_body}}"
            }
          ]
        }
        """)
    )

    obj = Apprise.instantiate(
        "tgram://123456789:abcdefg_hijklmnop/lead2gold/"
        "?template={}&:mykey=myval".format(str(template))
    )
    assert isinstance(obj, NotifyTelegram)

    # Verify tokens and template were parsed correctly
    assert "mykey" in obj.tokens
    assert obj.tokens["mykey"] == "myval"
    assert obj.template

    assert (
        obj.notify(body="hello", title="world", notify_type=NotifyType.INFO)
        is True
    )
    assert mock_post.called is True

    # Inspect the posted URL and payload
    posted_url = mock_post.call_args_list[0][0][0]
    assert posted_url.endswith("/sendRichMessage")

    posted = loads(mock_post.call_args_list[0][1]["data"])
    assert posted["chat_id"] == "@lead2gold"
    assert "rich_message" in posted
    blocks = posted["rich_message"]["blocks"]
    assert any(b.get("type") == "section_heading" for b in blocks)
    assert any(b.get("type") == "paragraph" for b in blocks)

    heading = next(b for b in blocks if b.get("type") == "section_heading")
    assert heading["text"] == "world"
    paragraph = next(b for b in blocks if b.get("type") == "paragraph")
    assert paragraph["text"] == "hello"


@mock.patch("requests.post")
def test_plugin_telegram_template_invalid_json(mock_post, tmpdir):
    """NotifyTelegram() - Rich Message template with invalid JSON fails."""
    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = dumps({"ok": True})
    mock_post.return_value = response

    template = tmpdir.join("bad.json")
    template.write("{ not valid json }")

    obj = Apprise.instantiate(
        "tgram://123456789:abcdefg_hijklmnop/lead2gold/?template={}".format(
            str(template)
        )
    )
    assert isinstance(obj, NotifyTelegram)

    assert (
        obj.notify(body="x", title="y", notify_type=NotifyType.INFO) is False
    )
    assert mock_post.called is False


@mock.patch("requests.post")
def test_plugin_telegram_template_blocks_not_list(mock_post, tmpdir):
    """NotifyTelegram() - 'blocks' missing/not-a-list/empty is rejected."""
    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = dumps({"ok": True})
    mock_post.return_value = response

    # 'blocks' key entirely missing
    template = tmpdir.join("missing_blocks.json")
    template.write('{"text": "no blocks here"}')

    obj = Apprise.instantiate(
        "tgram://123456789:abcdefg_hijklmnop/lead2gold/?template={}".format(
            str(template)
        )
    )
    assert isinstance(obj, NotifyTelegram)
    assert (
        obj.notify(body="x", title="y", notify_type=NotifyType.INFO) is False
    )
    assert mock_post.called is False

    # 'blocks' present but not a list
    template.write('{"blocks": "not-a-list"}')
    obj2 = Apprise.instantiate(
        "tgram://123456789:abcdefg_hijklmnop/lead2gold/?template={}".format(
            str(template)
        )
    )
    assert isinstance(obj2, NotifyTelegram)
    assert (
        obj2.notify(body="x", title="y", notify_type=NotifyType.INFO) is False
    )
    assert mock_post.called is False

    # Empty list is also rejected
    template.write('{"blocks": []}')
    obj3 = Apprise.instantiate(
        "tgram://123456789:abcdefg_hijklmnop/lead2gold/?template={}".format(
            str(template)
        )
    )
    assert isinstance(obj3, NotifyTelegram)
    assert (
        obj3.notify(body="x", title="y", notify_type=NotifyType.INFO) is False
    )
    assert mock_post.called is False


@mock.patch("requests.post")
def test_plugin_telegram_template_block_missing_type(mock_post, tmpdir):
    """NotifyTelegram() - a block dict without 'type' is rejected."""
    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = dumps({"ok": True})
    mock_post.return_value = response

    template = tmpdir.join("no_type.json")
    template.write('{"blocks": [{"text": "hi"}]}')

    obj = Apprise.instantiate(
        "tgram://123456789:abcdefg_hijklmnop/lead2gold/?template={}".format(
            str(template)
        )
    )
    assert isinstance(obj, NotifyTelegram)
    assert (
        obj.notify(body="x", title="y", notify_type=NotifyType.INFO) is False
    )
    assert mock_post.called is False


@mock.patch("requests.post")
def test_plugin_telegram_template_content_not_dict(mock_post, tmpdir):
    """NotifyTelegram() - template that parses to a JSON array is
    rejected."""
    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = dumps({"ok": True})
    mock_post.return_value = response

    template = tmpdir.join("array.json")
    template.write('[{"type": "paragraph"}]')

    obj = Apprise.instantiate(
        "tgram://123456789:abcdefg_hijklmnop/lead2gold/?template={}".format(
            str(template)
        )
    )
    assert isinstance(obj, NotifyTelegram)
    assert (
        obj.notify(body="x", title="y", notify_type=NotifyType.INFO) is False
    )
    assert mock_post.called is False


@mock.patch("requests.post")
def test_plugin_telegram_template_block_not_dict(mock_post, tmpdir):
    """NotifyTelegram() - non-dict entry in blocks list is rejected."""
    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = dumps({"ok": True})
    mock_post.return_value = response

    template = tmpdir.join("bad_block.json")
    template.write('{"blocks": ["not-a-dict"]}')

    obj = Apprise.instantiate(
        "tgram://123456789:abcdefg_hijklmnop/lead2gold/?template={}".format(
            str(template)
        )
    )
    assert isinstance(obj, NotifyTelegram)
    assert (
        obj.notify(body="x", title="y", notify_type=NotifyType.INFO) is False
    )
    assert mock_post.called is False


@mock.patch("requests.post")
def test_plugin_telegram_template_load_error(mock_post, tmpdir):
    """NotifyTelegram() - template OSError during read fails gracefully."""
    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = dumps({"ok": True})
    mock_post.return_value = response

    # Write an empty file so the attachment resolves but open() can be
    # mocked to fail
    template = tmpdir.join("empty.json")
    template.write("")

    obj = Apprise.instantiate(
        "tgram://123456789:abcdefg_hijklmnop/lead2gold/?template={}".format(
            str(template)
        )
    )
    assert isinstance(obj, NotifyTelegram)

    with mock.patch("builtins.open", side_effect=OSError):
        assert (
            obj.notify(body="x", title="y", notify_type=NotifyType.INFO)
            is False
        )
    assert mock_post.called is False


def test_plugin_telegram_template_bad_tokens():
    """NotifyTelegram() rejects an invalid template token type."""
    with pytest.raises(AppriseImproperlyConfigured):
        NotifyTelegram(
            bot_token="123456789:abcdefg_hijklmnop",
            targets="lead2gold",
            tokens="not-a-dict",
        )


def test_plugin_telegram_template_add_failure():
    """NotifyTelegram() rejects a template attachment it cannot add."""
    with mock.patch("apprise.plugins.telegram.AppriseAttachment") as mock_cls:
        inst = mock.MagicMock()
        inst.__len__ = mock.Mock(return_value=0)
        mock_cls.return_value = inst

        with pytest.raises(AppriseImproperlyConfigured):
            NotifyTelegram(
                bot_token="123456789:abcdefg_hijklmnop",
                targets="lead2gold",
                template="file:///some/template.json",
            )


@mock.patch("requests.post")
def test_plugin_telegram_template_inaccessible(mock_post, tmpdir):
    """NotifyTelegram() - template attachment that cannot be accessed
    fails."""
    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = dumps({"ok": True})
    mock_post.return_value = response

    # Point to a template file that does not exist
    missing = str(tmpdir.join("missing.json"))

    obj = Apprise.instantiate(
        "tgram://123456789:abcdefg_hijklmnop/lead2gold/?template={}".format(
            missing
        )
    )
    assert isinstance(obj, NotifyTelegram)
    assert (
        obj.notify(body="x", title="y", notify_type=NotifyType.INFO) is False
    )
    assert mock_post.called is False


@mock.patch("requests.post")
def test_plugin_telegram_template_none_token_value(mock_post, tmpdir):
    """NotifyTelegram() - a None token value (e.g. app_image_url) is
    coerced to an empty string before JSON-escaping."""
    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = dumps({"ok": True})
    mock_post.return_value = response

    # Template references app_image_url which will be None when
    # include_image=False
    template = tmpdir.join("img.json")
    template.write(
        '{"blocks": [{"type": "paragraph",'
        ' "text": "{{app_body}} img={{app_image_url}}"}]}'
    )

    obj = Apprise.instantiate(
        "tgram://123456789:abcdefg_hijklmnop/lead2gold/"
        "?image=no&template={}".format(str(template))
    )
    assert isinstance(obj, NotifyTelegram)
    assert (
        obj.notify(body="hi", title="y", notify_type=NotifyType.INFO) is True
    )
    posted = loads(mock_post.call_args_list[0][1]["data"])
    paragraph = posted["rich_message"]["blocks"][0]
    assert paragraph["text"] == "hi img="


@mock.patch("requests.post")
def test_plugin_telegram_template_url_roundtrip(mock_post, tmpdir):
    """NotifyTelegram() - template + tokens survive url()/parse_url()
    round-trip."""
    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = dumps({"ok": True})
    mock_post.return_value = response

    template = tmpdir.join("rt.json")
    template.write(
        cleandoc("""
        {
          "blocks": [
            {"type": "paragraph", "text": "{{app_body}}"}
          ]
        }
        """)
    )

    obj1 = NotifyTelegram(
        bot_token="123456789:abcdefg_hijklmnop",
        targets="lead2gold",
        template=str(template),
        tokens={"key1": "val1", "key2": "val2"},
    )

    url = obj1.url()
    result = NotifyTelegram.parse_url(url)
    assert result is not None

    obj2 = NotifyTelegram(**result)
    assert isinstance(obj2, NotifyTelegram)

    # Connection identity must be preserved
    assert obj1.url_identifier == obj2.url_identifier

    # Tokens must survive the round-trip
    assert obj2.tokens.get("key1") == "val1"
    assert obj2.tokens.get("key2") == "val2"

    # Template must be present after round-trip
    assert obj2.template


@mock.patch("requests.post")
def test_plugin_telegram_template_multi_target(mock_post, tmpdir):
    """NotifyTelegram() - Rich Message is POSTed once per target."""
    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = dumps({"ok": True})
    mock_post.return_value = response

    template = tmpdir.join("multi.json")
    template.write('{"blocks": [{"type": "paragraph", "text": "hi"}]}')

    obj = Apprise.instantiate(
        "tgram://123456789:abcdefg_hijklmnop/12345/67890:55/"
        "?template={}".format(str(template))
    )
    assert isinstance(obj, NotifyTelegram)
    assert len(obj.targets) == 2

    assert obj.notify(body="x", title="y", notify_type=NotifyType.INFO) is True
    assert mock_post.call_count == 2

    posted_1 = loads(mock_post.call_args_list[0][1]["data"])
    posted_2 = loads(mock_post.call_args_list[1][1]["data"])
    assert posted_1["chat_id"] == 12345
    assert "message_thread_id" not in posted_1
    assert posted_2["chat_id"] == 67890
    assert posted_2["message_thread_id"] == 55


@mock.patch("requests.post")
def test_plugin_telegram_template_with_attachment(mock_post, tmpdir):
    """NotifyTelegram() - attachments remain untouched in template mode,
    sent separately after the Rich Message."""
    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = dumps({"ok": True})
    mock_post.return_value = response

    template = tmpdir.join("attach.json")
    template.write('{"blocks": [{"type": "paragraph", "text": "hi"}]}')

    obj = Apprise.instantiate(
        "tgram://123456789:abcdefg_hijklmnop/lead2gold/?template={}".format(
            str(template)
        )
    )
    assert isinstance(obj, NotifyTelegram)

    # Pass a raw (not pre-wrapped) attachment path; template mode must
    # still normalize it into an AppriseAttachment internally.
    path = os.path.join(TEST_VAR_DIR, "apprise-test.gif")

    assert obj.notify(body="hi", title="y", attach=path) is True

    # First call is the Rich Message itself
    first_url = mock_post.call_args_list[0][0][0]
    assert first_url.endswith("/sendRichMessage")

    # Second call is the attachment, sent via the normal send_media() path
    second_url = mock_post.call_args_list[1][0][0]
    assert not second_url.endswith("/sendRichMessage")


@mock.patch("requests.post")
def test_plugin_telegram_template_attachment_failure(mock_post, tmpdir):
    """NotifyTelegram() - a failed attachment send flags an overall
    failure in Rich Message mode."""
    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = dumps({"ok": True})
    mock_post.return_value = response

    template = tmpdir.join("attach_fail.json")
    template.write('{"blocks": [{"type": "paragraph", "text": "hi"}]}')

    obj = Apprise.instantiate(
        "tgram://123456789:abcdefg_hijklmnop/lead2gold/?template={}".format(
            str(template)
        )
    )
    assert isinstance(obj, NotifyTelegram)

    # Point to an attachment that cannot be accessed
    attach = AppriseAttachment("file:///path/does/not/exist.gif")

    assert obj.notify(body="hi", title="y", attach=attach) is False


@mock.patch("requests.post")
def test_plugin_telegram_template_preview_enabled(mock_post, tmpdir):
    """NotifyTelegram() - preview=yes omits link_preview_options."""
    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = dumps({"ok": True})
    mock_post.return_value = response

    template = tmpdir.join("preview.json")
    template.write('{"blocks": [{"type": "paragraph", "text": "hi"}]}')

    obj = Apprise.instantiate(
        "tgram://123456789:abcdefg_hijklmnop/lead2gold/"
        "?preview=yes&template={}".format(str(template))
    )
    assert isinstance(obj, NotifyTelegram)
    assert obj.notify(body="x", title="y", notify_type=NotifyType.INFO) is True
    posted = loads(mock_post.call_args_list[0][1]["data"])
    assert "link_preview_options" not in posted


@mock.patch("requests.post")
def test_plugin_telegram_template_http_error(mock_post, tmpdir):
    """NotifyTelegram() - Rich Message HTTP error is handled gracefully."""
    response = mock.Mock()
    response.status_code = requests.codes.internal_server_error
    response.content = dumps({"description": "failure"})
    mock_post.return_value = response

    template = tmpdir.join("err.json")
    template.write('{"blocks": [{"type": "paragraph", "text": "hi"}]}')

    obj = Apprise.instantiate(
        "tgram://123456789:abcdefg_hijklmnop/lead2gold/?template={}".format(
            str(template)
        )
    )
    assert isinstance(obj, NotifyTelegram)
    assert (
        obj.notify(body="x", title="y", notify_type=NotifyType.INFO) is False
    )

    # Also cover the case where the error response body itself is not
    # parsable JSON (falls back to the generic HTTP status string)
    response.content = b"not-json"
    assert (
        obj.notify(body="x", title="y", notify_type=NotifyType.INFO) is False
    )


@mock.patch("requests.post")
def test_plugin_telegram_template_request_exception(mock_post, tmpdir):
    """NotifyTelegram() - Rich Message RequestException is handled
    gracefully."""
    mock_post.side_effect = requests.RequestException()

    template = tmpdir.join("exc.json")
    template.write('{"blocks": [{"type": "paragraph", "text": "hi"}]}')

    obj = Apprise.instantiate(
        "tgram://123456789:abcdefg_hijklmnop/lead2gold/?template={}".format(
            str(template)
        )
    )
    assert isinstance(obj, NotifyTelegram)
    assert (
        obj.notify(body="x", title="y", notify_type=NotifyType.INFO) is False
    )


def test_plugin_telegram_html_reducer_many_open_tags_is_fast():
    """Thousands of open tags or empty lines are reduced quickly."""

    # Every open tag is still closed at the end
    start = default_timer()
    result = TelegramHTMLReducer().reduce("<b>" * 33333)
    elapsed = default_timer() - start
    assert result == "<b>" * 33333 + "</b>" * 33333
    assert elapsed < 5.0

    # Empty tags followed by many blocks add no blank lines
    start = default_timer()
    result = TelegramHTMLReducer().reduce("<b></b>" * 20000 + "<p>" * 20000)
    elapsed = default_timer() - start
    assert result == "<b></b>" * 20000
    assert elapsed < 5.0


def telegram_album_obj(targets=None):
    """Build an album-enabled Telegram object without throttling."""
    obj = NotifyTelegram(
        bot_token="123456789:abcdefg_hijklmnop",
        targets=targets if targets else ["12345"],
        album=True,
    )
    obj.throttle = mock.Mock()
    return obj


def telegram_album_calls(mock_post):
    """Return the Telegram endpoint used by each recorded POST."""
    return [
        urlparse(call[0][0]).path.rsplit("/", 1)[-1]
        for call in mock_post.call_args_list
    ]


def test_plugin_telegram_album_url():
    """Verify album= parsing and URL round trips."""

    obj = Apprise.instantiate(
        "tgram://123456789:abcdefg_hijklmnop/12345/?album=yes"
    )
    assert isinstance(obj, NotifyTelegram)
    assert obj.album is True
    assert "album=yes" in obj.url()

    # Our default is off
    obj = Apprise.instantiate("tgram://123456789:abcdefg_hijklmnop/12345/")
    assert obj.album is False
    assert "album=no" in obj.url()

    # The flag survives a full round trip
    obj = Apprise.instantiate(
        Apprise.instantiate(
            "tgram://123456789:abcdefg_hijklmnop/12345/?album=yes"
        ).url()
    )
    assert obj.album is True


def test_plugin_telegram_album_kind():
    """Verify MIME types select album or separate delivery."""

    obj = telegram_album_obj()

    photo = AppriseAttachment(os.path.join(TEST_VAR_DIR, "apprise-test.jpeg"))
    video = AppriseAttachment(os.path.join(TEST_VAR_DIR, "apprise-test.mp4"))
    animation = AppriseAttachment(
        os.path.join(TEST_VAR_DIR, "apprise-test.gif")
    )
    archive = AppriseAttachment(
        os.path.join(TEST_VAR_DIR, "apprise-archive.zip")
    )

    assert obj._album_kind(photo[0]) == TelegramMediaKind.PHOTO
    assert obj._album_kind(video[0]) == TelegramMediaKind.VIDEO

    # Animations go out on their own; sendAnimation has no album form
    assert obj._album_kind(animation[0]) == TelegramMediaKind.SINGLE
    assert obj._album_kind(archive[0]) == TelegramMediaKind.SINGLE

    # An attachment we can't reach has no mime type to go on
    missing = AppriseAttachment("file:///path/does/not/exist.png")
    assert obj._album_kind(missing[0]) == TelegramMediaKind.SINGLE

    # Anything that isn't an attachment object is left alone
    assert obj._album_kind(None) == TelegramMediaKind.SINGLE


def test_plugin_telegram_album_kind_size():
    """Verify files over Telegram's size limits leave the album."""

    obj = telegram_album_obj()

    photo = AppriseAttachment(os.path.join(TEST_VAR_DIR, "apprise-test.jpeg"))
    video = AppriseAttachment(os.path.join(TEST_VAR_DIR, "apprise-test.mp4"))

    # Telegram's limits are 10 MB for photos and 50 MB for videos
    with mock.patch("os.path.getsize", return_value=10000000):
        assert obj._album_kind(photo[0]) == TelegramMediaKind.PHOTO

    with mock.patch("os.path.getsize", return_value=10000001):
        assert obj._album_kind(photo[0]) == TelegramMediaKind.SINGLE

    with mock.patch("os.path.getsize", return_value=50000000):
        assert obj._album_kind(video[0]) == TelegramMediaKind.VIDEO

    with mock.patch("os.path.getsize", return_value=50000001):
        assert obj._album_kind(video[0]) == TelegramMediaKind.SINGLE


@mock.patch("requests.post")
def test_plugin_telegram_album_groups_media(mock_post):
    """Verify eligible attachments are posted as one album."""

    mock_post.return_value = mock.Mock()
    mock_post.return_value.status_code = requests.codes.ok
    mock_post.return_value.content = b'{"ok":true}'

    obj = telegram_album_obj()
    attach = AppriseAttachment(
        [
            os.path.join(TEST_VAR_DIR, "apprise-test.jpeg"),
            os.path.join(TEST_VAR_DIR, "apprise-test.png"),
            os.path.join(TEST_VAR_DIR, "apprise-test.mp4"),
        ]
    )

    assert obj.notify(body="hello", attach=attach) is True

    # One album, not three separate messages
    assert telegram_album_calls(mock_post) == ["sendMediaGroup"]

    details = mock_post.call_args_list[0]
    assert urlparse(details[0][0]).hostname == "api.telegram.org"

    media = loads(details[1]["data"]["media"])
    assert [entry["type"] for entry in media] == ["photo", "photo", "video"]
    assert [entry["media"] for entry in media] == [
        "attach://file0",
        "attach://file1",
        "attach://file2",
    ]
    assert sorted(details[1]["files"]) == ["file0", "file1", "file2"]

    # The caption rides on the first album entry only
    assert media[0]["caption"] == "hello"
    assert "caption" not in media[1]
    assert "caption" not in media[2]


@mock.patch("requests.post")
def test_plugin_telegram_album_preserves_order(mock_post):
    """Verify separate attachments keep their original position."""

    mock_post.return_value = mock.Mock()
    mock_post.return_value.status_code = requests.codes.ok
    mock_post.return_value.content = b'{"ok":true}'

    obj = telegram_album_obj()
    attach = AppriseAttachment(
        [
            os.path.join(TEST_VAR_DIR, "apprise-test.jpeg"),
            os.path.join(TEST_VAR_DIR, "apprise-archive.zip"),
            os.path.join(TEST_VAR_DIR, "apprise-test.png"),
            os.path.join(TEST_VAR_DIR, "apprise-test.jpeg"),
        ]
    )

    assert obj.notify(body="hello", attach=attach) is True

    # A lone photo can't form an album, the zip never could, and the
    # trailing pair does
    assert telegram_album_calls(mock_post) == [
        "sendPhoto",
        "sendDocument",
        "sendMediaGroup",
    ]

    # Only the very first message carries the caption
    assert mock_post.call_args_list[0][1]["data"].get("caption") == "hello"
    assert "caption" not in mock_post.call_args_list[1][1]["data"]
    media = loads(mock_post.call_args_list[2][1]["data"]["media"])
    assert "caption" not in media[0]


@mock.patch("requests.post")
def test_plugin_telegram_album_batches(mock_post):
    """Verify more than ten media are split across albums."""

    mock_post.return_value = mock.Mock()
    mock_post.return_value.status_code = requests.codes.ok
    mock_post.return_value.content = b'{"ok":true}'

    obj = telegram_album_obj()
    path = os.path.join(TEST_VAR_DIR, "apprise-test.jpeg")

    # Eleven photos: a full album of ten, then a single leftover
    assert obj.notify(body="hello", attach=AppriseAttachment([path] * 11))
    assert telegram_album_calls(mock_post) == ["sendMediaGroup", "sendPhoto"]
    assert len(loads(mock_post.call_args_list[0][1]["data"]["media"])) == 10

    # Twelve photos: two albums, since two is enough to form one
    mock_post.reset_mock()
    assert obj.notify(body="hello", attach=AppriseAttachment([path] * 12))
    assert telegram_album_calls(mock_post) == [
        "sendMediaGroup",
        "sendMediaGroup",
    ]
    assert len(loads(mock_post.call_args_list[1][1]["data"]["media"])) == 2


@mock.patch("requests.post")
def test_plugin_telegram_album_topic(mock_post):
    """Verify album requests include the topic thread."""

    mock_post.return_value = mock.Mock()
    mock_post.return_value.status_code = requests.codes.ok
    mock_post.return_value.content = b'{"ok":true}'

    obj = telegram_album_obj(targets=["12345:9"])
    attach = AppriseAttachment(
        [
            os.path.join(TEST_VAR_DIR, "apprise-test.jpeg"),
            os.path.join(TEST_VAR_DIR, "apprise-test.png"),
        ]
    )

    assert obj.notify(body="hello", attach=attach) is True
    assert mock_post.call_args_list[0][1]["data"]["message_thread_id"] == 9


@mock.patch("requests.post")
def test_plugin_telegram_album_unnamed_attachment(mock_post):
    """Verify unnamed attachments receive a filename."""

    mock_post.return_value = mock.Mock()
    mock_post.return_value.status_code = requests.codes.ok
    mock_post.return_value.content = b'{"ok":true}'

    obj = telegram_album_obj()
    attach = AppriseAttachment(
        [
            os.path.join(TEST_VAR_DIR, "apprise-test.jpeg"),
            os.path.join(TEST_VAR_DIR, "apprise-test.png"),
        ]
    )

    # Use the instance's class because other tests may reload Apprise.
    with mock.patch.object(
        type(attach[0]),
        "name",
        new_callable=mock.PropertyMock,
        return_value=None,
    ):
        assert (
            obj._send_media_group(
                (12345, None),
                list(attach),
                [TelegramMediaKind.PHOTO] * 2,
            )
            == TelegramGroupResult.OK
        )

    files = mock_post.call_args_list[0][1]["files"]
    assert files["file0"][0] == "file000.dat"
    assert files["file1"][0] == "file001.dat"


@mock.patch("requests.post")
def test_plugin_telegram_album_retry(mock_post):
    """Verify a refused album is retried as separate messages."""

    refused = mock.Mock()
    refused.status_code = requests.codes.bad_request
    refused.content = b'{"ok":false,"description":"group is invalid"}'

    accepted = mock.Mock()
    accepted.status_code = requests.codes.ok
    accepted.content = b'{"ok":true}'

    mock_post.side_effect = [refused, accepted, accepted]

    obj = telegram_album_obj()
    attach = AppriseAttachment(
        [
            os.path.join(TEST_VAR_DIR, "apprise-test.jpeg"),
            os.path.join(TEST_VAR_DIR, "apprise-test.png"),
        ]
    )

    assert obj.notify(body="hello", attach=attach) is True
    assert telegram_album_calls(mock_post) == [
        "sendMediaGroup",
        "sendPhoto",
        "sendPhoto",
    ]

    # The caption moves to the first of the retried messages
    assert mock_post.call_args_list[1][1]["data"].get("caption") == "hello"
    assert "caption" not in mock_post.call_args_list[2][1]["data"]


@mock.patch("requests.post")
def test_plugin_telegram_album_retry_failure(mock_post):
    """Verify delivery stops when an album retry fails."""

    refused = mock.Mock()
    refused.status_code = requests.codes.bad_request
    refused.content = b'{"ok":false}'

    rejected = mock.Mock()
    rejected.status_code = requests.codes.internal_server_error
    rejected.content = b'{"ok":false}'

    # The photo endpoint fails and so does the document fallback
    mock_post.side_effect = [refused, rejected, rejected]

    obj = telegram_album_obj()
    attach = AppriseAttachment(
        [
            os.path.join(TEST_VAR_DIR, "apprise-test.jpeg"),
            os.path.join(TEST_VAR_DIR, "apprise-test.png"),
        ]
    )

    assert obj.notify(body="hello", attach=attach) is False


@mock.patch("requests.post")
def test_plugin_telegram_album_document_fallback(mock_post):
    """Verify refused media is resent as a document."""

    refused = mock.Mock()
    refused.status_code = requests.codes.bad_request
    refused.content = b'{"ok":false,"description":"bad photo"}'

    accepted = mock.Mock()
    accepted.status_code = requests.codes.ok
    accepted.content = b'{"ok":true}'

    # The album and the first photo are refused, the rest go through
    mock_post.side_effect = [refused, refused, accepted, accepted]

    obj = telegram_album_obj()
    attach = AppriseAttachment(
        [
            os.path.join(TEST_VAR_DIR, "apprise-test.jpeg"),
            os.path.join(TEST_VAR_DIR, "apprise-test.png"),
        ]
    )

    assert obj.notify(body="hello", attach=attach) is True
    assert telegram_album_calls(mock_post) == [
        "sendMediaGroup",
        "sendPhoto",
        "sendDocument",
        "sendPhoto",
    ]

    # The document keeps the caption the refused photo would have had
    assert mock_post.call_args_list[2][1]["data"].get("caption") == "hello"
    assert "document" in mock_post.call_args_list[2][1]["files"]


@mock.patch("requests.post")
def test_plugin_telegram_album_oversized_photo(mock_post):
    """Verify oversized photos are sent straight as documents."""

    mock_post.return_value = mock.Mock()
    mock_post.return_value.status_code = requests.codes.ok
    mock_post.return_value.content = b'{"ok":true}'

    obj = telegram_album_obj()
    attach = AppriseAttachment(
        [
            os.path.join(TEST_VAR_DIR, "apprise-test.jpeg"),
            os.path.join(TEST_VAR_DIR, "apprise-test.png"),
        ]
    )

    with mock.patch("os.path.getsize", return_value=10000001):
        assert obj.notify(body="hello", attach=attach) is True

    assert telegram_album_calls(mock_post) == ["sendDocument", "sendDocument"]


@mock.patch("requests.post")
def test_plugin_telegram_album_size_budget(mock_post):
    """Verify an album is split before it grows past 50 MB."""

    mock_post.return_value = mock.Mock()
    mock_post.return_value.status_code = requests.codes.ok
    mock_post.return_value.content = b'{"ok":true}'

    obj = telegram_album_obj()
    attach = AppriseAttachment(
        [os.path.join(TEST_VAR_DIR, "apprise-test.mp4")] * 3
    )

    # Two 20 MB videos fit in one album; the third does not
    with mock.patch("os.path.getsize", return_value=20000000):
        assert obj.notify(body="hello", attach=attach) is True

    assert telegram_album_calls(mock_post) == ["sendMediaGroup", "sendVideo"]


@mock.patch("requests.post")
def test_plugin_telegram_attach_size_limits(mock_post):
    """Verify Telegram's upload limits are enforced before sending."""

    mock_post.return_value = mock.Mock()
    mock_post.return_value.status_code = requests.codes.ok
    mock_post.return_value.content = b'{"ok":true}'

    obj = NotifyTelegram(
        bot_token="123456789:abcdefg_hijklmnop", targets=["12345"]
    )
    obj.throttle = mock.Mock()

    photo = AppriseAttachment(os.path.join(TEST_VAR_DIR, "apprise-test.jpeg"))
    video = AppriseAttachment(os.path.join(TEST_VAR_DIR, "apprise-test.mp4"))

    # A photo over 10 MB is sent as a document instead
    with mock.patch("os.path.getsize", return_value=10000001):
        assert obj.notify(body="hello", attach=photo) is True

    assert telegram_album_calls(mock_post) == ["sendDocument"]

    # Anything over 50 MB is never uploaded
    mock_post.reset_mock()
    with mock.patch("os.path.getsize", return_value=50000001):
        assert obj.notify(body="hello", attach=video) is False

    assert not mock_post.called


@mock.patch("requests.post")
def test_plugin_telegram_album_single_failure(mock_post):
    """Verify a failed separate attachment stops delivery."""

    mock_post.return_value = mock.Mock()
    mock_post.return_value.status_code = requests.codes.internal_server_error
    mock_post.return_value.content = b'{"ok":false}'

    obj = telegram_album_obj()
    attach = AppriseAttachment(
        os.path.join(TEST_VAR_DIR, "apprise-archive.zip")
    )

    assert obj.notify(body="hello", attach=attach) is False


@mock.patch("requests.post")
def test_plugin_telegram_album_server_error(mock_post):
    """Verify only HTTP 400 responses retry an album."""

    mock_post.return_value = mock.Mock()
    mock_post.return_value.status_code = requests.codes.internal_server_error
    mock_post.return_value.content = b'{"ok":false}'

    obj = telegram_album_obj()
    attach = AppriseAttachment(
        [
            os.path.join(TEST_VAR_DIR, "apprise-test.jpeg"),
            os.path.join(TEST_VAR_DIR, "apprise-test.png"),
        ]
    )

    assert obj.notify(body="hello", attach=attach) is False
    assert telegram_album_calls(mock_post) == ["sendMediaGroup"]


@mock.patch("requests.post")
def test_plugin_telegram_album_inaccessible(mock_post):
    """Verify unreadable attachments stop before upload."""

    obj = telegram_album_obj()
    attach = AppriseAttachment(
        [
            os.path.join(TEST_VAR_DIR, "apprise-test.jpeg"),
            os.path.join(TEST_VAR_DIR, "apprise-test.png"),
        ]
    )

    with mock.patch("os.path.isfile", return_value=False):
        assert (
            obj._send_media_group(
                (12345, None),
                list(attach),
                [TelegramMediaKind.PHOTO] * 2,
            )
            == TelegramGroupResult.FAIL
        )

    # Reporting a missing attachment must not raise
    assert (
        obj._send_media_group(
            (12345, None), [None, None], [TelegramMediaKind.PHOTO] * 2
        )
        == TelegramGroupResult.FAIL
    )

    assert not mock_post.called


@mock.patch("requests.post")
def test_plugin_telegram_album_open_error(mock_post):
    """Verify file read errors are handled."""

    obj = telegram_album_obj()
    attach = AppriseAttachment(
        [
            os.path.join(TEST_VAR_DIR, "apprise-test.jpeg"),
            os.path.join(TEST_VAR_DIR, "apprise-test.png"),
        ]
    )

    with mock.patch("builtins.open", side_effect=OSError):
        assert (
            obj._send_media_group(
                (12345, None),
                list(attach),
                [TelegramMediaKind.PHOTO] * 2,
            )
            == TelegramGroupResult.FAIL
        )

    assert not mock_post.called


@mock.patch("requests.post")
def test_plugin_telegram_album_request_exception(mock_post):
    """Verify album connection errors are handled."""

    mock_post.side_effect = requests.ConnectionError(
        0, "requests.ConnectionError() not handled"
    )

    obj = telegram_album_obj()
    attach = AppriseAttachment(
        [
            os.path.join(TEST_VAR_DIR, "apprise-test.jpeg"),
            os.path.join(TEST_VAR_DIR, "apprise-test.png"),
        ]
    )

    assert obj.notify(body="hello", attach=attach) is False


@mock.patch("requests.post")
def test_plugin_telegram_album_disabled(mock_post):
    """Verify attachments remain separate by default."""

    mock_post.return_value = mock.Mock()
    mock_post.return_value.status_code = requests.codes.ok
    mock_post.return_value.content = b'{"ok":true}'

    obj = NotifyTelegram(
        bot_token="123456789:abcdefg_hijklmnop", targets=["12345"]
    )
    obj.throttle = mock.Mock()
    attach = AppriseAttachment(
        [
            os.path.join(TEST_VAR_DIR, "apprise-test.jpeg"),
            os.path.join(TEST_VAR_DIR, "apprise-test.png"),
        ]
    )

    assert obj.notify(body="hello", attach=attach) is True
    assert telegram_album_calls(mock_post) == ["sendPhoto", "sendPhoto"]


@mock.patch("requests.post")
def test_plugin_telegram_album_delivery_tracking(mock_post):
    """Verify a retry only resends album items that never arrived."""

    refused = mock.Mock()
    refused.status_code = requests.codes.bad_request
    refused.content = b'{"ok":false}'

    rejected = mock.Mock()
    rejected.status_code = requests.codes.internal_server_error
    rejected.content = b'{"ok":false}'

    accepted = mock.Mock()
    accepted.status_code = requests.codes.ok
    accepted.content = b'{"ok":true}'

    obj = telegram_album_obj()
    attach = AppriseAttachment(
        [
            os.path.join(TEST_VAR_DIR, "apprise-test.jpeg"),
            os.path.join(TEST_VAR_DIR, "apprise-test.png"),
            os.path.join(TEST_VAR_DIR, "apprise-test.jpeg"),
        ]
    )

    token = _delivery_tracker.set(set())
    try:
        # The album is refused, the first photo arrives on its own, and
        # the second photo fails along with its document fallback
        mock_post.side_effect = [refused, accepted, rejected, rejected]
        assert (
            obj._send_attachments(
                (12345, None),
                NotifyType.INFO,
                attach,
                payload={"caption": "hello"},
            )
            is False
        )

        # The retry skips the delivered photo and its caption, and the
        # two remaining photos still form an album
        mock_post.reset_mock()
        mock_post.side_effect = [accepted]
        assert (
            obj._send_attachments(
                (12345, None),
                NotifyType.INFO,
                attach,
                payload={"caption": "hello"},
            )
            is True
        )
        assert telegram_album_calls(mock_post) == ["sendMediaGroup"]
        media = loads(mock_post.call_args_list[0][1]["data"]["media"])
        assert len(media) == 2
        assert "caption" not in media[0]

        # Nothing is left to send on a further retry
        mock_post.reset_mock()
        assert (
            obj._send_attachments((12345, None), NotifyType.INFO, attach)
            is True
        )
        assert not mock_post.called

    finally:
        _delivery_tracker.reset(token)
