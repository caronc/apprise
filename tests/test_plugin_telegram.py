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

from json import dumps, loads

# Disable logging for a cleaner testing output
import logging
import os
import re
from unittest import mock

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
from apprise.plugins.telegram import NotifyTelegram

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
            "instance": TypeError,
        },
    ),
    # content must be 'before' or 'after'
    (
        "tgram://bottest@123456789:abcdefg_hijklmnop/id1/?content=invalid",
        {
            "instance": TypeError,
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
    with pytest.raises(TypeError):
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
    with pytest.raises(TypeError):
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

    # Declared Markdown gets the same MarkdownV2 dialect completion.
    assert (
        payload["text"] == "\\# 🚨 Change detected for _Apprise Test Title_\n"
        "_[Apprise Body Title](http://localhost)_ had "
        "[a change](http://127\\.0\\.0\\.1)"
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

    # v1 (non-strict) recognizes a narrower escape set than v2 does.
    assert (
        payload["text"] == "# 🚨 Change detected for _Apprise Test Title_\n"
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
        payload["text"] == "<b>\r\n<b>🚨 Another Change detected for "
        "<i>Apprise Test Title</i></b>\r\n</b>\r\n<i>"
        '<a href="http://localhost">Apprise Body Title</a>'
        '</i> had <a href="http://127.0.0.2">a change</a>\r\n'
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

    # Generic title merging strips surrounding whitespace before conversion.
    assert payload["text"] == (
        "# #\n"
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

    # v2 (strict) keeps every reserved character escaped, same title
    # doubling as the v1 case above.
    assert payload["text"] == (
        "\\# \\#\n"
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
    # text-to-markdown pass added, since v1 does not require it.
    assert payload["text"] == (
        "# # A Great Title\n"
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
    # title+body, so the literal leading hash is escaped too.
    assert payload["text"] == (
        "\\# \\# A Great Title\n"
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

    # MarkdownV2 escapes the leading hash and URL dots.
    assert payload["text"] == (
        "\\# A Great Title\n"
        "_[Apprise Body Title](http://localhost)_ had "
        "[a change](http://127\\.0\\.0\\.2)"
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

    # v1 keeps "#" and HTML-looking body text unescaped.
    assert payload["text"] == (
        "# Test Message Title\nTest Message Body <br/> ok</br>"
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
        == "<b>Test Message Title</b>\r\nTest Message Body\r\nok\r\n"
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
        == "<b>\r\n<b>'information'</b>\r\n</b>\r\n<i>\"This is in Italic\""
        "</i>\r\n<b>      Headings are dropped and converted to bold</b>\r\n"
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
        == "\r\n<b>Bootstrap 101 Template</b>\r\n<b>My Title</b>\r\n"
        "<b>Heading 1</b>\r\n-Bullet 1\r\n-Bullet 2\r\n-Bullet 3\r\n"
        "-Bullet 1\r\n-Bullet 2\r\n-Bullet 3\r\n<b>Heading 2</b>\r\n"
        "A div entry\r\nA div entry\r\n"
        "<pre><code class=\"language-python\">print('hello')</code></pre>\r\n"
        "<b>Heading 3</b>\r\n<b>Heading 4</b>\r\n<b>Heading 5</b>\r\n"
        "<b>Heading 6</b>\r\nA set of text\r\n"
        "Another line after the set of text\r\nMore text\r\nlabel"
    )


@mock.patch("requests.post")
def test_plugin_telegram_html_heading_padding_requires_declared_source(
    mock_post,
):
    """HTML heading padding requires a declared source format."""

    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok
    mock_post.return_value.content = "{}"

    body = "<h1>Heading</h1>Body text here"

    aobj = Apprise()
    assert aobj.add("tgram://123456789:abcdefg_hijklmnop/12345678")

    # Declared HTML: heading gets padded on both sides.
    assert aobj.notify(body=body, body_format=NotifyFormat.HTML)
    payload = loads(mock_post.call_args_list[-1][1]["data"])
    assert payload["text"] == "\r\n<b>Heading</b>\r\nBody text here"
    mock_post.reset_mock()

    # Undeclared input resolves to HTML but remains unpadded.
    assert aobj.notify(body=body)
    payload = loads(mock_post.call_args_list[-1][1]["data"])
    assert payload["text"] == "<b>Heading</b>Body text here"


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

    # A heading has no MarkdownV2 entity -- its '#' must be escaped (not left
    # bare), or Telegram rejects the entire message outright rather than just.
    aobj = Apprise()
    aobj.add("tgram://123456789:abcdefg_hijklmnop/12345?format=markdown&mdv=2")
    assert len(aobj) == 1

    assert aobj.notify(
        body="<h1>Title</h1><p>body text</p>", body_format=NotifyFormat.HTML
    )

    assert mock_post.call_count == 1
    payload = loads(mock_post.call_args_list[0][1]["data"])

    assert payload["parse_mode"] == "MarkdownV2"
    assert payload["text"] == "\\# Title\n\nbody text"

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

    # Immediately-adjacent nested emphasis (no text between the outer and inner
    # tag's open) must stay correctly nested ("*_x_*"), not cross ("*_x*_").
    assert notify("<b><i>x</i></b>") == "*_x_*"
    assert notify("<i><b>x</b></i>") == "*_x_*"

    # Legacy Markdown (v1) doesn't support nested entities at all.
    assert notify("<b>a <i>b</i> c</b>", mdv="1") == "*a b c*"
    assert notify("<b><i>x</i></b>", mdv="1") == "*x*"

    # <i><b>x</b></i> and <b><i>x</i></b> both flatten to the identical
    # CommonMark "***x***" (html_to_markdown has no separating text to anchor
    assert notify("<i><b>x</b></i>", mdv="1") == "*x*"

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
    assert notify("<b>A</b><b>B</b>") == "*A**B*"

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

    # Escape a dangling "[" during end-of-scan cleanup.
    assert (
        NotifyTelegram._commonmark_to_telegram(
            "text [dangling forever", strict=True
        )
        == "text \\[dangling forever"
    )

    # Preserve plain Markdown links while escaping their destinations.
    assert (
        NotifyTelegram._commonmark_to_telegram(
            "[a link](https://example.com/x.y)", strict=True
        )
        == "[a link](https://example\\.com/x\\.y)"
    )

    # Preserve an escaped parenthesis inside a plain link destination.
    assert (
        NotifyTelegram._commonmark_to_telegram(
            "[label](http://example.com/a\\)b)", strict=True
        )
        == "[label](http://example\\.com/a\\)b)"
    )

    # A plain destination containing a balanced, unescaped pair of
    # parentheses: the real terminator is the ")" that brings nesting
    # back to zero, not the first unescaped ")" encountered -- otherwise
    # the link closes early and the real closing ")" leaks out as
    # ordinary (and here, unescaped-until-fixed) text.
    assert (
        NotifyTelegram._commonmark_to_telegram(
            "[label](https://example.com/a_(b))", strict=True
        )
        == "[label](https://example\\.com/a_\\(b\\))"
    )

    # Same balance check in V1 (non-strict) mode -- the reserved-char
    # escaping differs, but the paren nesting still must not misclose.
    assert (
        NotifyTelegram._commonmark_to_telegram(
            "[label](https://example.com/a_(b))", strict=False
        )
        == "[label](https://example.com/a_\\(b\\))"
    )

    # Empty adjacent entities collapse without affecting following text.
    assert NotifyTelegram._commonmark_to_telegram("****x") == "x"

    # Cascade close that pops an open span whose delimiter was the LAST item
    # in the output buffer (empty entity) -- the delimiter is dropped.
    assert NotifyTelegram._commonmark_to_telegram("******") == ""

    # Unclosed spans at the end of the V1 input are force-closed by the cleanup
    # loop.
    f1 = NotifyTelegram._commonmark_to_telegram
    assert f1("***italic text") == "*italic text*"
    assert f1("**text") == "*text*"
    # An unterminated open with no content at all collapses to nothing.
    assert f1("**") == ""

    # A link destination containing a backslash-escaped '>' in V1 mode:
    # the scan skips escaped characters and still finds the '>)' terminator.
    assert (
        notify('<a href="https://example.com/x>y">click</a>', mdv="1")
        == r"[click](https://example.com/x\\>y)"
    )

    # Merge the title as a heading before Telegram V1 conversion.
    aobj_v1 = Apprise()
    aobj_v1.add(
        "tgram://123456789:abcdefg_hijklmnop/12345?format=markdown&mdv=1"
    )
    assert aobj_v1.notify(
        body="<b>hello</b>", title="My Title", body_format=NotifyFormat.HTML
    )
    payload = loads(mock_post.call_args_list[-1][1]["data"])
    assert payload["text"] == "# My Title\n*hello*"
    mock_post.reset_mock()

    # Title that reduces to an empty string after stripping leading heading and
    # list characters (html_to_markdown converts " - " to "-").
    assert aobj_v1.notify(
        body="<b>hello</b>", title="  - ", body_format=NotifyFormat.HTML
    )
    payload = loads(mock_post.call_args_list[-1][1]["data"])
    assert payload["text"] == "*hello*"
    mock_post.reset_mock()


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
def test_plugin_telegram_overflow_split_repair_declared_markdown(mock_post):
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
