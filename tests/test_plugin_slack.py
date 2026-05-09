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
from unittest import mock

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise, AppriseAttachment, NotifyType
from apprise.plugins.slack import NotifySlack

logging.disable(logging.CRITICAL)

# Attachment Directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), "var")

# Our Testing URLs
apprise_url_tests = (
    (
        "slack://",
        {
            "instance": TypeError,
        },
    ),
    (
        "slack://:@/",
        {
            "instance": TypeError,
        },
    ),
    (
        "slack://T1JJ3T3L2",
        {
            # Just Token 1 provided
            "instance": TypeError,
        },
    ),
    (
        "slack://T1JJ3T3L2/A1BRTD4JD/",
        {
            # Just 2 tokens provided
            "instance": TypeError,
        },
    ),
    (
        "slack://T1JJ3T3L2/A1BRTD4JD/TIiajkdnlazkcOXrIdevi7FQ/?mode=invalid",
        {
            # invalid Mode provided
            "instance": TypeError,
        },
    ),
    (
        "slack://T1JJ3T3L2/A1BRTD4JD/TIiajkdnlazkcOXrIdevi7FQ/#hmm/#-invalid-",
        {
            # No username specified; this is still okay as we sub in
            # default; The one invalid channel is skipped when sending a
            # message
            "instance": NotifySlack,
            # There is an invalid channel that we will fail to deliver to
            # as a result the response type will be false
            "response": False,
            "requests_response_text": {
                "ok": False,
                "message": "Bad Channel",
            },
        },
    ),
    (
        "slack://T1JJ3T3L2/A1BRTD4JD/TIiajkdnlazkcOXrIdevi7FQ/#channel",
        {
            # No username specified; this is still okay as we sub in
            # default; The one invalid channel is skipped when sending a
            # message
            "instance": NotifySlack,
            # don't include an image by default
            "include_image": False,
            "requests_response_text": "ok",
        },
    ),
    (
        (
            "slack://username@xoxe.xoxb-1234-1234-abc124/#nuxref?footer=no"
            "&timestamp=yes"
        ),
        {
            "instance": NotifySlack,
            "requests_response_text": {
                "ok": True,
                "message": "",
            },
        },
    ),
    (
        (
            "slack://username@xoxe.xoxp-1234-1234-abc124/#nuxref?footer=yes"
            "&timestamp=no"
        ),
        {
            "instance": NotifySlack,
            "requests_response_text": {
                "ok": True,
                "message": "",
            },
        },
    ),
    # Test using a rotating bot-token as argument
    (
        (
            "slack://?token=xoxe.xoxb-1234-1234-abc124&to=#nuxref&footer=no"
            "&user=test"
        ),
        {
            "instance": NotifySlack,
            "requests_response_text": {
                "ok": True,
                "message": "",
            },
            "privacy_url": "slack://test@x...4/nuxref/",
        },
    ),
    (
        "slack://T1JJ3T3L2/A1BRTD4JD/TIiajkdnlazkcOXrIdevi7FQ/+id/@id/",
        {
            # + encoded id,
            # @ userid
            "instance": NotifySlack,
            "requests_response_text": "ok",
        },
    ),
    (
        (
            "slack://username@T1JJ3T3L2/A1BRTD4JD/TIiajkdnlazkcOXrIdevi7FQ/"
            "?to=#nuxref"
        ),
        {
            "instance": NotifySlack,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "slack://username@T...2/A...D/T...Q/",
            "requests_response_text": "ok",
        },
    ),
    (
        (
            "slack://username@T1JJ3T3L2/A1BRTD4JD/"
            "TIiajkdnlazkcOXrIdevi7FQ/#nuxref"
        ),
        {
            "instance": NotifySlack,
            "requests_response_text": "ok",
        },
    ),
    # You can't send to email using webhook
    (
        "slack://T1JJ3T3L2/A1BRTD4JD/TIiajkdnl/user@gmail.com",
        {
            "instance": NotifySlack,
            "requests_response_text": "ok",
            # we'll have a notify response failure in this case
            "notify_response": False,
        },
    ),
    # Specify Token on argument string (with username)
    (
        "slack://bot@_/#nuxref?token=T1JJ3T3L2/A1BRTD4JD/TIiajkdnadfdajkjkfl/",
        {
            "instance": NotifySlack,
            "requests_response_text": "ok",
        },
    ),
    # Specify Token and channels on argument string (no username)
    (
        (
            "slack://?token=T1JJ3T3L2/A1BRTD4JD"
            "/TIiajkdnlazkcOXrIdevi7FQ/&to=#chan"
        ),
        {
            "instance": NotifySlack,
            "requests_response_text": "ok",
        },
    ),
    # Test webhook that doesn't have a proper response
    (
        (
            "slack://username@T1JJ3T3L2/A1BRTD4JD/"
            "TIiajkdnlazkcOXrIdevi7FQ/#nuxref"
        ),
        {
            "instance": NotifySlack,
            "requests_response_text": "fail",
            # we'll have a notify response failure in this case
            "notify_response": False,
        },
    ),
    # Test using a bot-token (also test footer set to no flag)
    (
        (
            "slack://username@xoxb-1234-1234-abc124/#nuxref?footer=no"
            "&timestamp=yes"
        ),
        {
            "instance": NotifySlack,
            "requests_response_text": {
                "ok": True,
                "message": "",
            },
        },
    ),
    (
        (
            "slack://username@xoxb-1234-1234-abc124/#nuxref?footer=yes"
            "&timestamp=yes"
        ),
        {
            "instance": NotifySlack,
            "requests_response_text": {
                "ok": True,
                "message": "",
            },
        },
    ),
    (
        (
            "slack://username@xoxb-1234-1234-abc124/#nuxref?footer=yes"
            "&timestamp=no"
        ),
        {
            "instance": NotifySlack,
            "requests_response_text": {
                "ok": True,
                "message": "",
            },
        },
    ),
    (
        (
            "slack://username@xoxb-1234-1234-abc124/#nuxref?footer=yes"
            "&timestamp=no"
        ),
        {
            "instance": NotifySlack,
            "requests_response_text": {
                "ok": True,
                "message": "",
            },
        },
    ),
    # Testing modes
    (
        (
            "slack://?token=T1JJ3T3L2/A1BRTD4JD/TIiajkdnlazkcOXrIdevi7FQ/"
            "&to=#chan&mode=hook"
        ),
        {"instance": NotifySlack, "requests_response_text": "ok"},
    ),
    # Forced mode on a url that does not have enough details to accommodate
    (
        (
            "slack://?token=T1JJ3T3L2/A1BRTD4JD/TIiajkdnlazkcOXrIdevi7FQ/"
            "&to=#chan&mode=bot"
        ),
        {"instance": TypeError},
    ),
    # Test blocks mode with timestamp variation
    (
        (
            "slack://?token=T1JJ3T3L2/A1BRTD4JD/TIiajkdnlazkcOXrIdevi7FQ/"
            "&to=#chan&blocks=yes&footer=yes&timestamp=no"
        ),
        {"instance": NotifySlack, "requests_response_text": "ok"},
    ),
    # Test blocks mode with another timestamp
    (
        (
            "slack://?token=T1JJ3T3L2/A1BRTD4JD/TIiajkdnlazkcOXrIdevi7FQ/"
            "&to=#chan&blocks=yes&footer=yes&timestamp=yes"
        ),
        {"instance": NotifySlack, "requests_response_text": "ok"},
    ),
    # footer being disabled means timestamp isn't shown
    (
        (
            "slack://?token=T1JJ3T3L2/A1BRTD4JD/TIiajkdnlazkcOXrIdevi7FQ/"
            "&to=#chan&blocks=yes&footer=no&timestamp=yes"
        ),
        {"instance": NotifySlack, "requests_response_text": "ok"},
    ),
    # footer and timestamp disabled
    (
        (
            "slack://?token=T1JJ3T3L2/A1BRTD4JD/TIiajkdnlazkcOXrIdevi7FQ/"
            "&to=#chan&blocks=yes&footer=no&timestamp=no"
        ),
        {"instance": NotifySlack, "requests_response_text": "ok"},
    ),
    (
        (
            "slack://?token=T1JJ3T3L2/A1BRTD4JD/TIiajkdnlazkcOXrIdevi7FQ/"
            "&to=#chan&blocks=yes&footer=yes&image=no"
        ),
        {"instance": NotifySlack, "requests_response_text": "ok"},
    ),
    (
        (
            "slack://?token=T1JJ3T3L2/A1BRTD4JD/TIiajkdnlazkcOXrIdevi7FQ/"
            "&to=#chan&blocks=yes&format=text"
        ),
        {"instance": NotifySlack, "requests_response_text": "ok"},
    ),
    (
        (
            "slack://?token=T1JJ3T3L2/A1BRTD4JD/TIiajkdnlazkcOXrIdevi7FQ/"
            "&to=#chan&blocks=no&format=text"
        ),
        {"instance": NotifySlack, "requests_response_text": "ok"},
    ),
    # Test using a bot-token as argument
    (
        "slack://?token=xoxb-1234-1234-abc124&to=#nuxref&footer=no&user=test",
        {
            "instance": NotifySlack,
            "requests_response_text": {
                "ok": True,
                "message": "",
            },
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "slack://test@x...4/nuxref/",
        },
    ),
    # We contain 1 or more invalid channels, so we'll fail on our notify call
    (
        "slack://?token=xoxb-1234-1234-abc124&to=#nuxref,#$,#-&footer=no",
        {
            "instance": NotifySlack,
            "requests_response_text": {
                "ok": True,
                "message": "",
            },
            # We fail because of the empty channel #$ and #-
            "notify_response": False,
        },
    ),
    (
        "slack://username@xoxb-1234-1234-abc124/#nuxref",
        {
            "instance": NotifySlack,
            "requests_response_text": {
                "ok": True,
                "message": "",
            },
            # we'll fail to send attachments because we had no 'file' response
            # in our object
            "response": False,
        },
    ),
    (
        "slack://username@T1JJ3T3L2/A1BRTD4JD/TIiajkdnlazkcOXrIdevi7FQ",
        {
            # Missing a channel, falls back to webhook channel bindings
            "instance": NotifySlack,
            "requests_response_text": "ok",
        },
    ),
    # Native URL Support, take the slack URL and still build from it
    (
        "https://hooks.slack.com/services/{}/{}/{}".format(
            "A" * 9, "B" * 9, "c" * 24
        ),
        {
            "instance": NotifySlack,
            "requests_response_text": "ok",
            "url_matches": "mode=hook",
        },
    ),
    (
        "https://hooks.slack-gov.com/services/{}/{}/{}".format(
            "A" * 9, "B" * 9, "c" * 24
        ),
        {
            "instance": NotifySlack,
            "requests_response_text": "ok",
            "url_matches": "mode=gov-hook",
        },
    ),
    # Native URL Support with arguments
    (
        "https://hooks.slack.com/services/{}/{}/{}?format=text".format(
            "A" * 9, "B" * 9, "c" * 24
        ),
        {
            "instance": NotifySlack,
            "requests_response_text": "ok",
        },
    ),
    (
        "slack://username@-INVALID-/A1BRTD4JD/TIiajkdnlazkcOXrIdevi7FQ/#cool",
        {
            # invalid 1st Token
            "instance": TypeError,
        },
    ),
    (
        "slack://username@T1JJ3T3L2/-INVALID-/TIiajkdnlazkcOXrIdevi7FQ/#great",
        {
            # invalid 2rd Token
            "instance": TypeError,
        },
    ),
    (
        "slack://username@T1JJ3T3L2/A1BRTD4JD/-INVALID-/#channel",
        {
            # invalid 3rd Token
            "instance": TypeError,
        },
    ),
    (
        "slack://l2g@T1JJ3T3L2/A1BRTD4JD/TIiajkdnlazkcOXrIdevi7FQ/#usenet",
        {
            "instance": NotifySlack,
            # force a failure
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
            "requests_response_text": "ok",
        },
    ),
    (
        "slack://respect@T1JJ3T3L2/A1BRTD4JD/TIiajkdnlazkcOXrIdevi7FQ/#a",
        {
            "instance": NotifySlack,
            # throw a bizarre code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
            "requests_response_text": "ok",
        },
    ),
    (
        "slack://notify@T1JJ3T3L2/A1BRTD4JD/TIiajkdnlazkcOXrIdevi7FQ/#b",
        {
            "instance": NotifySlack,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracefully handle them
            "test_requests_exceptions": True,
            "requests_response_text": "ok",
        },
    ),
    (
        "slack://notify@T1JJ3T3L2/A1BRTD4JD/TIiajkdnlazkcOXrIdevi7FQ/#b:100",
        {
            "instance": NotifySlack,
            "requests_response_text": "ok",
        },
    ),
    (
        "slack://notify@T1JJ3T3L2/A1BRTD4JD/TIiajkdnlazkcOXrIdevi7FQ/+124:100",
        {
            "instance": NotifySlack,
            "requests_response_text": "ok",
        },
    ),
    # test a case where we have a channel defined alone (without a thread_ts)
    # that exists after a definition where a thread_ts does exist.  this
    # tests the branch of code that ensures we do not pass the same thread_ts
    # twice
    (
        (
            "slack://notify@T1JJ3T3L2/A1BRTD4JD/"
            "TIiajkdnlazkcOXrIdevi7FQ/+124:100/@chan"
        ),
        {
            "instance": NotifySlack,
            "requests_response_text": "ok",
        },
    ),
    (
        "slack://notify@T1JJ3T3L2/A1BRTD4JD/TIiajkdnlazkcOXrIdevi7FQ/#b:bad",
        {
            "instance": NotifySlack,
            "requests_response_text": "ok",
            # we'll fail because our thread_ts is bad
            "response": False,
        },
    ),
    # Workflow Builder webhook (4-segment /workflows/ path)
    (
        "slack://T1JJ3T3L2/Ft07XXXX/XXXXXXXX/YYYYYYYY/?mode=workflow",
        {
            "instance": NotifySlack,
        },
    ),
    # Workflow trigger webhook (3-segment /triggers/ path)
    (
        "slack://T1JJ3T3L2/XXXXXXXX/YYYYYYYY/?mode=trigger",
        {
            "instance": NotifySlack,
        },
    ),
    # Workflow native URL (/workflows/)
    (
        (
            "https://hooks.slack.com/workflows/"
            "T1JJ3T3L2/Ft07XXXX/XXXXXXXX/YYYYYYYY"
        ),
        {
            "instance": NotifySlack,
            "privacy_url": "slack://T...2/F...X/X...X/Y...Y/",
        },
    ),
    # Workflow trigger native URL (/triggers/)
    (
        "https://hooks.slack.com/triggers/T1JJ3T3L2/XXXXXXXX/YYYYYYYY",
        {
            "instance": NotifySlack,
            "privacy_url": "slack://T...2/X...X/Y...Y/",
        },
    ),
    # Workflow mode -- too few segments (2 of required 4)
    (
        "slack://T1JJ3T3L2/XXXXXXXX/?mode=workflow",
        {
            "instance": TypeError,
        },
    ),
    # Workflow mode -- wrong count: trigger's 3 segments rejected
    (
        "slack://T1JJ3T3L2/XXXXXXXX/YYYYYYYY/?mode=workflow",
        {
            "instance": TypeError,
        },
    ),
    # Trigger mode -- wrong count: workflow's 4 segments rejected
    (
        "slack://T1JJ3T3L2/Ft07XXXX/XXXXXXXX/YYYYYYYY/?mode=trigger",
        {
            "instance": TypeError,
        },
    ),
)


def test_plugin_slack_urls():
    """NotifySlack() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.request")
def test_plugin_slack_oauth_access_token(mock_request):
    """NotifySlack() OAuth Access Token Tests."""

    # Generate an invalid bot token
    token = "xo-invalid"

    request = mock.Mock()
    request.content = dumps(
        {
            "ok": True,
            "message": "",
            "channel": "C123456",
        }
    )
    request.status_code = requests.codes.ok

    # We'll fail to validate the access_token
    with pytest.raises(TypeError):
        NotifySlack(access_token=token)

    # Generate a (valid) bot token
    token = "xoxb-1234-1234-abc124"

    # Generate a (valid) rotating bot token
    rotating_token = "xoxe.xoxb-1234-1234-abc124"

    # Prepare Mock
    mock_request.return_value = request
    # Variation Initializations
    obj = NotifySlack(access_token=token, targets="#apprise")
    assert isinstance(obj, NotifySlack) is True
    assert isinstance(obj.url(), str) is True

    # apprise room was found
    assert obj.send(body="test") is True

    # Validate rotating token is accepted too
    obj = NotifySlack(access_token=rotating_token, targets="#apprise")
    assert isinstance(obj, NotifySlack) is True
    assert isinstance(obj.url(), str) is True
    assert obj.send(body="test") is True

    # A poorly formatted xoxe prefix should still be rejected
    with pytest.raises(TypeError):
        NotifySlack(access_token="xoxe.xo-invalid", targets="#apprise")

    # Test Valid Attachment
    mock_request.reset_mock()
    mock_request.side_effect = [
        request,
        mock.Mock(
            **{
                "content": dumps(
                    {
                        "ok": True,
                        "upload_url": "https://files.slack.com/upload/v1/ABC123",
                        "file_id": "F123ABC456",
                    }
                ),
                "status_code": requests.codes.ok,
            }
        ),
        mock.Mock(
            **{"content": b"OK - 123", "status_code": requests.codes.ok}
        ),
        mock.Mock(
            **{
                "content": dumps(
                    {
                        "ok": True,
                        "files": [{"id": "F123ABC456", "title": "slack-test"}],
                    }
                ),
                "status_code": requests.codes.ok,
            }
        ),
    ]

    path = os.path.join(TEST_VAR_DIR, "apprise-test.gif")
    attach = AppriseAttachment(path)
    assert (
        obj.notify(
            body="body",
            title="title",
            notify_type=NotifyType.INFO,
            attach=attach,
        )
        is True
    )

    assert mock_request.call_count == 4
    assert mock_request.call_args_list[0][0][0] == "post"
    assert (
        mock_request.call_args_list[0][0][1]
        == "https://slack.com/api/chat.postMessage"
    )
    assert mock_request.call_args_list[1][0][0] == "get"
    assert (
        mock_request.call_args_list[1][0][1]
        == "https://slack.com/api/files.getUploadURLExternal"
    )
    assert mock_request.call_args_list[2][0][0] == "post"
    assert (
        mock_request.call_args_list[2][0][1]
        == "https://files.slack.com/upload/v1/ABC123"
    )
    assert mock_request.call_args_list[3][0][0] == "post"
    assert (
        mock_request.call_args_list[3][0][1]
        == "https://slack.com/api/files.completeUploadExternal"
    )

    # Test a valid attachment that throws an Connection Error
    mock_request.return_value = None
    mock_request.side_effect = (
        request,
        requests.ConnectionError(0, "requests.ConnectionError() not handled"),
    )
    assert (
        obj.notify(
            body="body",
            title="title",
            notify_type=NotifyType.INFO,
            attach=attach,
        )
        is False
    )

    # Test a valid attachment that throws an OSError
    mock_request.return_value = None
    mock_request.side_effect = (request, OSError(0, "OSError"))
    assert (
        obj.notify(
            body="body",
            title="title",
            notify_type=NotifyType.INFO,
            attach=attach,
        )
        is False
    )

    # Reset our mock object back to how it was
    mock_request.return_value = request
    mock_request.side_effect = None

    # Test invalid attachment
    path = os.path.join(TEST_VAR_DIR, "/invalid/path/to/an/invalid/file.jpg")
    assert (
        obj.notify(
            body="body",
            title="title",
            notify_type=NotifyType.INFO,
            attach=path,
        )
        is False
    )

    # Test case where expected return attachment payload is invalid
    mock_request.reset_mock()
    mock_request.side_effect = [
        request,
        mock.Mock(
            **{
                "content": dumps(
                    {
                        "ok": False,
                    }
                ),
                "status_code": requests.codes.internal_server_error,
            }
        ),
    ]
    path = os.path.join(TEST_VAR_DIR, "apprise-test.gif")
    attach = AppriseAttachment(path)
    # We'll fail because of the bad 'file' response
    assert (
        obj.notify(
            body="body",
            title="title",
            notify_type=NotifyType.INFO,
            attach=attach,
        )
        is False
    )

    # Slack requests pay close attention to the response to determine
    # if things go well... this is not a good JSON response:
    request.content = "{"
    mock_request.reset_mock()
    mock_request.return_value = request
    mock_request.side_effect = None

    # As a result, we'll fail to send our notification
    assert obj.send(body="test", attach=attach) is False

    request.content = dumps(
        {
            "ok": False,
            "message": "We failed",
        }
    )

    # A response from Slack (even with a 200 response) still
    # results in a failure:
    assert obj.send(body="test", attach=attach) is False

    # Handle exceptions reading our attachment from disk (should it happen)
    mock_request.side_effect = OSError("Attachment Error")
    mock_request.return_value = None

    # We'll fail now because of an internal exception
    assert obj.send(body="test") is False


@mock.patch("requests.request")
def test_plugin_slack_webhook_mode(mock_request):
    """NotifySlack() Webhook Mode Tests."""

    # Prepare Mock
    mock_request.return_value = requests.Request()
    mock_request.return_value.status_code = requests.codes.ok
    mock_request.return_value.content = b"ok"
    mock_request.return_value.text = "ok"

    # Initialize some generic (but valid) tokens
    token_a = "A" * 9
    token_b = "B" * 9
    token_c = "c" * 24

    # Support strings
    channels = "chan1,#chan2,+BAK4K23G5,@user,,,"

    obj = NotifySlack(
        token_a=token_a, token_b=token_b, token_c=token_c, targets=channels
    )
    assert len(obj.channels) == 4

    # This call includes an image with it's payload:
    assert (
        obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        is True
    )

    # Missing first Token
    with pytest.raises(TypeError):
        NotifySlack(
            token_a=None, token_b=token_b, token_c=token_c, targets=channels
        )

    # Test include_image
    obj = NotifySlack(
        token_a=token_a,
        token_b=token_b,
        token_c=token_c,
        targets=channels,
        include_image=True,
    )

    # This call includes an image with it's payload:
    assert (
        obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        is True
    )


@mock.patch("requests.request")
@mock.patch("requests.get")
def test_plugin_slack_send_by_email(mock_get, mock_request):
    """NotifySlack() Send by Email Tests."""

    # Generate a (valid) bot token
    token = "xoxb-1234-1234-abc124"

    request = mock.Mock()
    request.content = dumps(
        {"ok": True, "message": "", "user": {"id": "ABCD1234"}}
    )
    request.status_code = requests.codes.ok

    # Prepare Mock
    mock_request.return_value = request
    mock_get.return_value = request

    # Variation Initializations
    obj = NotifySlack(access_token=token, targets="user@gmail.com")
    assert isinstance(obj, NotifySlack) is True
    assert isinstance(obj.url(), str) is True

    # No calls made yet
    assert mock_request.call_count == 0
    assert mock_get.call_count == 0

    # Send our notification
    assert (
        obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        is True
    )

    # 2 calls were made, one to perform an email lookup, the second
    # was the notification itself
    assert mock_get.call_count == 1
    assert mock_request.call_count == 1
    assert (
        mock_get.call_args_list[0][0][0]
        == "https://slack.com/api/users.lookupByEmail"
    )
    assert (
        mock_request.call_args_list[0][0][1]
        == "https://slack.com/api/chat.postMessage"
    )

    # Reset our mock object
    mock_request.reset_mock()
    mock_get.reset_mock()

    # Prepare Mock
    mock_request.return_value = request
    mock_get.return_value = request

    # Send our notification again (cached copy of user id associated with
    # email is used)
    assert (
        obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        is True
    )

    assert mock_get.call_count == 0
    assert mock_request.call_count == 1
    assert (
        mock_request.call_args_list[0][0][1]
        == "https://slack.com/api/chat.postMessage"
    )

    #
    # Now test a case where we can't look up the valid email
    #
    request.content = dumps(
        {
            "ok": False,
            "message": "",
        }
    )

    # Reset our mock object
    mock_request.reset_mock()
    mock_get.reset_mock()

    # Prepare Mock
    mock_request.return_value = request
    mock_get.return_value = request

    # Variation Initializations
    obj = NotifySlack(access_token=token, targets="user@gmail.com")
    assert isinstance(obj, NotifySlack) is True
    assert isinstance(obj.url(), str) is True

    # No calls made yet
    assert mock_request.call_count == 0
    assert mock_get.call_count == 0

    # Send our notification; it will fail because we failed to look up
    # the user id
    assert (
        obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        is False
    )

    # We would have failed to look up the email, therefore we wouldn't have
    # even bothered to attempt to send the notification
    assert mock_get.call_count == 1
    assert mock_request.call_count == 0
    assert (
        mock_get.call_args_list[0][0][0]
        == "https://slack.com/api/users.lookupByEmail"
    )

    #
    # Now test a case where we have a poorly formatted JSON response
    #
    request.content = "}"

    # Reset our mock object
    mock_request.reset_mock()
    mock_get.reset_mock()

    # Prepare Mock
    mock_request.return_value = request
    mock_get.return_value = request

    # Variation Initializations
    obj = NotifySlack(access_token=token, targets="user@gmail.com")
    assert isinstance(obj, NotifySlack) is True
    assert isinstance(obj.url(), str) is True

    # No calls made yet
    assert mock_request.call_count == 0
    assert mock_get.call_count == 0

    # Send our notification; it will fail because we failed to look up
    # the user id
    assert (
        obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        is False
    )

    # We would have failed to look up the email, therefore we wouldn't have
    # even bothered to attempt to send the notification
    assert mock_get.call_count == 1
    assert mock_request.call_count == 0
    assert (
        mock_get.call_args_list[0][0][0]
        == "https://slack.com/api/users.lookupByEmail"
    )

    #
    # Now test a case where we have a poorly formatted JSON response
    #
    request.content = "}"

    # Reset our mock object
    mock_request.reset_mock()
    mock_get.reset_mock()

    # Prepare Mock
    mock_request.return_value = request
    mock_get.return_value = request

    # Variation Initializations
    obj = NotifySlack(access_token=token, targets="user@gmail.com")
    assert isinstance(obj, NotifySlack) is True
    assert isinstance(obj.url(), str) is True

    # No calls made yet
    assert mock_request.call_count == 0
    assert mock_get.call_count == 0

    # Send our notification; it will fail because we failed to look up
    # the user id
    assert (
        obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        is False
    )

    # We would have failed to look up the email, therefore we wouldn't have
    # even bothered to attempt to send the notification
    assert mock_get.call_count == 1
    assert mock_request.call_count == 0
    assert (
        mock_get.call_args_list[0][0][0]
        == "https://slack.com/api/users.lookupByEmail"
    )

    #
    # Now test a case where we throw an exception trying to perform the lookup
    #

    request.content = dumps(
        {"ok": True, "message": "", "user": {"id": "ABCD1234"}}
    )
    # Create an unauthorized response
    request.status_code = requests.codes.ok

    # Reset our mock object
    mock_request.reset_mock()
    mock_get.reset_mock()

    # Prepare Mock
    mock_request.return_value = request
    mock_get.side_effect = requests.ConnectionError(
        0, "requests.ConnectionError() not handled"
    )

    # Variation Initializations
    obj = NotifySlack(access_token=token, targets="user@gmail.com")
    assert isinstance(obj, NotifySlack) is True
    assert isinstance(obj.url(), str) is True

    # No calls made yet
    assert mock_request.call_count == 0
    assert mock_get.call_count == 0

    # Send our notification; it will fail because we failed to look up
    # the user id
    assert (
        obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        is False
    )

    # We would have failed to look up the email, therefore we wouldn't have
    # even bothered to attempt to send the notification
    assert mock_get.call_count == 1
    assert mock_request.call_count == 0
    assert (
        mock_get.call_args_list[0][0][0]
        == "https://slack.com/api/users.lookupByEmail"
    )


@mock.patch("requests.request")
@mock.patch("requests.get")
def test_plugin_slack_markdown(mock_get, mock_request):
    """NotifySlack() Markdown tests."""

    request = mock.Mock()
    request.content = b"ok"
    request.status_code = requests.codes.ok

    # Prepare Mock
    mock_request.return_value = request
    mock_get.return_value = request

    # Variation Initializations
    aobj = Apprise()
    assert aobj.add(
        "slack://T1JJ3T3L2/A1BRTD4JD/TIiajkdnlazkcOXrIdevi7FQ/#channel"
    )

    body = cleandoc("""
    Here is a <https://slack.com|Slack Link> we want to support as part of it's
    markdown.

    This one has arguments we want to preserve:
       <https://slack.com?arg=val&arg2=val2|Slack Link>.
    We also want to be able to support <https://slack.com> links without the
    description.

    Channel Testing
    <!channelA>
    <!channelA|Description>

    User ID Testing
    <@U1ZQL9N3Y>
    <@U1ZQL9N3Y|heheh>
    """)

    # Send our notification
    assert aobj.notify(body=body, title="title", notify_type=NotifyType.INFO)

    # We would have failed to look up the email, therefore we wouldn't have
    # even bothered to attempt to send the notification
    assert mock_get.call_count == 0
    assert mock_request.call_count == 1
    assert (
        mock_request.call_args_list[0][0][1]
        == "https://hooks.slack.com/services/T1JJ3T3L2/A1BRTD4JD/"
        "TIiajkdnlazkcOXrIdevi7FQ"
    )

    data = loads(mock_request.call_args_list[0][1]["data"])
    assert (
        data["attachments"][0]["text"]
        == "Here is a <https://slack.com|Slack Link> we want to support as"
        " part "
        "of it's\nmarkdown.\n\nThis one has arguments we want to preserve:"
        "\n   <https://slack.com?arg=val&arg2=val2|Slack Link>.\n"
        "We also want to be able to support <https://slack.com> "
        "links without the\ndescription."
        "\n\nChannel Testing\n<!channelA>\n<!channelA|Description>\n\n"
        "User ID Testing\n<@U1ZQL9N3Y>\n<@U1ZQL9N3Y|heheh>"
    )


@mock.patch("requests.request")
def test_plugin_slack_single_thread_reply(mock_request):
    """NotifySlack() Send Notification as a Reply."""

    # Generate a (valid) bot token
    token = "xoxb-1234-1234-abc124"
    thread_id = 100
    request = mock.Mock()
    request.content = dumps(
        {"ok": True, "message": "", "user": {"id": "ABCD1234"}}
    )
    request.status_code = requests.codes.ok

    # Prepare Mock
    mock_request.return_value = request

    # Variation Initializations
    obj = NotifySlack(access_token=token, targets=[f"#general:{thread_id}"])
    assert isinstance(obj, NotifySlack) is True
    assert isinstance(obj.url(), str) is True

    # No calls made yet
    assert mock_request.call_count == 0

    # Send our notification
    assert (
        obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        is True
    )

    # Post was made
    assert mock_request.call_count == 1
    assert (
        mock_request.call_args_list[0][0][1]
        == "https://slack.com/api/chat.postMessage"
    )
    assert loads(mock_request.call_args_list[0][1]["data"]).get(
        "thread_ts"
    ) == str(thread_id)


@mock.patch("requests.request")
def test_plugin_slack_multiple_thread_reply(mock_request):
    """NotifySlack() Send Notification to multiple channels as Reply."""

    # Generate a (valid) bot token
    token = "xoxb-1234-1234-abc124"
    thread_id_1, thread_id_2 = 100, 200
    request = mock.Mock()
    request.content = dumps(
        {"ok": True, "message": "", "user": {"id": "ABCD1234"}}
    )
    request.status_code = requests.codes.ok

    # Prepare Mock
    mock_request.return_value = request

    # Variation Initializations
    obj = NotifySlack(
        access_token=token,
        targets=[f"#general:{thread_id_1}", f"#other:{thread_id_2}"],
    )
    assert isinstance(obj, NotifySlack) is True
    assert isinstance(obj.url(), str) is True

    # No calls made yet
    assert mock_request.call_count == 0

    # Send our notification
    assert (
        obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        is True
    )

    # Post was made
    assert mock_request.call_count == 2
    assert (
        mock_request.call_args_list[0][0][1]
        == "https://slack.com/api/chat.postMessage"
    )
    assert loads(mock_request.call_args_list[0][1]["data"]).get(
        "thread_ts"
    ) == str(thread_id_1)
    assert loads(mock_request.call_args_list[1][1]["data"]).get(
        "thread_ts"
    ) == str(thread_id_2)


@mock.patch("requests.request")
def test_plugin_slack_file_upload_success(mock_request):
    """Test Slack BOT attachment upload success path."""

    token = "xoxb-1234-1234-abc124"
    path = os.path.join(TEST_VAR_DIR, "apprise-test.gif")
    attach = AppriseAttachment(path)

    # Simulate all successful Slack API responses
    mock_request.side_effect = [
        mock.Mock(
            **{
                "content": dumps(
                    {
                        "ok": True,
                        "channel": "C123456",
                    }
                ),
                "status_code": requests.codes.ok,
            }
        ),
        mock.Mock(
            **{
                "content": dumps(
                    {
                        "ok": True,
                        "upload_url": "https://files.slack.com/upload/v1/ABC123",
                        "file_id": "F123ABC456",
                    }
                ),
                "status_code": requests.codes.ok,
            }
        ),
        mock.Mock(
            **{
                "content": b"OK - 123",
                "status_code": requests.codes.ok,
            }
        ),
        mock.Mock(
            **{
                "content": dumps(
                    {
                        "ok": True,
                        "files": [
                            {"id": "F123ABC456", "title": "apprise-test"}
                        ],
                    }
                ),
                "status_code": requests.codes.ok,
            }
        ),
    ]

    obj = NotifySlack(access_token=token, targets=["#general"])
    assert (
        obj.notify(
            body="Success path test",
            title="Slack Upload OK",
            notify_type=NotifyType.INFO,
            attach=attach,
        )
        is True
    )


@mock.patch("requests.request")
def test_plugin_slack_file_upload_fails_missing_files(mock_request):
    """Test that file upload fails when 'files' is missing or empty."""

    token = "xoxb-1234-1234-abc124"
    path = os.path.join(TEST_VAR_DIR, "apprise-test.gif")
    attach = AppriseAttachment(path)

    # Mock sequence:
    # 1. chat.postMessage returns valid channel
    # 2. files.getUploadURLExternal returns file_id and upload_url
    # 3. Upload returns 'OK'
    # 4. files.completeUploadExternal returns missing/empty 'files'

    mock_request.side_effect = [
        mock.Mock(
            **{
                "content": dumps(
                    {
                        "ok": True,
                        "channel": "C555555",
                    }
                ),
                "status_code": requests.codes.ok,
            }
        ),
        mock.Mock(
            **{
                "content": dumps(
                    {
                        "ok": True,
                        "upload_url": "https://files.slack.com/upload/v1/X99999",
                        "file_id": "F999XYZ888",
                    }
                ),
                "status_code": requests.codes.ok,
            }
        ),
        mock.Mock(
            **{
                "content": b"OK - 2048",
                "status_code": requests.codes.ok,
            }
        ),
        # <== This response will trigger the error condition
        mock.Mock(
            **{
                "content": dumps(
                    {
                        "ok": True,
                        "files": [],
                    }
                ),
                "status_code": requests.codes.ok,
            }
        ),
    ]

    obj = NotifySlack(access_token=token, targets=["#fail-channel"])
    result = obj.notify(
        body="This should trigger a failed file upload",
        title="Trigger failure",
        notify_type=NotifyType.INFO,
        attach=attach,
    )

    assert result is False


@mock.patch("requests.request")
def test_plugin_slack_attach_memory(mock_request):
    """Regression: AttachMemory must be sendable without OSError."""
    from apprise.attachment.memory import AttachMemory

    token = "xoxb-1234-1234-abc124"

    mock_request.side_effect = [
        mock.Mock(
            **{
                "content": dumps({"ok": True, "channel": "C123456"}),
                "status_code": requests.codes.ok,
            }
        ),
        mock.Mock(
            **{
                "content": dumps(
                    {
                        "ok": True,
                        "upload_url": "https://files.slack.com/upload/v1/ABC123",
                        "file_id": "F123ABC456",
                    }
                ),
                "status_code": requests.codes.ok,
            }
        ),
        mock.Mock(
            **{
                "content": b"OK - 100",
                "status_code": requests.codes.ok,
            }
        ),
        mock.Mock(
            **{
                "content": dumps(
                    {
                        "ok": True,
                        "files": [{"id": "F123ABC456", "title": "report"}],
                    }
                ),
                "status_code": requests.codes.ok,
            }
        ),
    ]

    obj = NotifySlack(access_token=token, targets=["#general"])

    mem = AttachMemory(
        content=b"<html><body><h1>Test</h1></body></html>",
        name="report.html",
        mimetype="text/html",
    )

    assert obj.notify(body="Test", attach=mem) is True
    assert mock_request.call_count >= 1


@mock.patch("requests.request")
def test_plugin_slack_template_blocks(mock_request, tmpdir):
    """NotifySlack() - blocks mode with JSON template."""
    # Valid webhook mock response
    mock_request.return_value = mock.Mock(
        **{
            "content": b"ok",
            "status_code": requests.codes.ok,
        }
    )

    # Write a minimal Block Kit JSON template to disk
    template = tmpdir.join("blocks.json")
    template.write(
        cleandoc("""
        {
          "blocks": [
            {
              "type": "header",
              "text": {
                "type": "plain_text",
                "text": "{{app_title}}"
              }
            },
            {
              "type": "section",
              "text": {
                "type": "mrkdwn",
                "text": "{{app_body}}"
              }
            }
          ],
          "color": "{{app_color}}"
        }
        """)
    )

    # Instantiate via URL with blocks=yes and template path
    obj = Apprise.instantiate(
        "slack://T1JJ3T3L2/A1BRTD4JD/TIiajkdnlazkcOXrIdevi7FQ/"
        "?blocks=yes&template={}&:mykey=myval".format(str(template))
    )
    assert isinstance(obj, NotifySlack)

    # Verify tokens and template were parsed correctly
    assert "mykey" in obj.tokens
    assert obj.tokens["mykey"] == "myval"
    assert obj.template

    # Notification should succeed
    assert (
        obj.notify(body="hello", title="world", notify_type=NotifyType.INFO)
        is True
    )
    assert mock_request.called is True

    # Inspect the posted payload
    posted = loads(mock_request.call_args_list[0][1]["data"])
    assert "attachments" in posted
    assert "blocks" in posted["attachments"][0]
    # Header and section blocks should be present
    blocks = posted["attachments"][0]["blocks"]
    assert any(b.get("type") == "header" for b in blocks)
    assert any(b.get("type") == "section" for b in blocks)
    # Title and body substituted correctly
    header = next(b for b in blocks if b.get("type") == "header")
    assert header["text"]["text"] == "world"
    section = next(b for b in blocks if b.get("type") == "section")
    assert section["text"]["text"] == "hello"


@mock.patch("requests.request")
def test_plugin_slack_template_blocks_implied(mock_request, tmpdir):
    """NotifySlack() - template= alone implies blocks=yes."""
    # Valid webhook mock response
    mock_request.return_value = mock.Mock(
        **{
            "content": b"ok",
            "status_code": requests.codes.ok,
        }
    )

    template = tmpdir.join("implied.json")
    template.write(
        cleandoc("""
        {
          "blocks": [
            {
              "type": "section",
              "text": {"type": "mrkdwn", "text": "{{app_body}}"}
            }
          ]
        }
        """)
    )

    # No blocks=yes in the URL -- should still use the template
    obj = Apprise.instantiate(
        "slack://T1JJ3T3L2/A1BRTD4JD/TIiajkdnlazkcOXrIdevi7FQ/"
        "?template={}".format(str(template))
    )
    assert isinstance(obj, NotifySlack)
    # use_blocks must have been forced on by the template
    assert obj.use_blocks is True
    assert (
        obj.notify(body="implied", title="t", notify_type=NotifyType.INFO)
        is True
    )
    assert mock_request.called is True
    posted = loads(mock_request.call_args_list[0][1]["data"])
    blocks = posted["attachments"][0]["blocks"]
    section = next(b for b in blocks if b.get("type") == "section")
    assert section["text"]["text"] == "implied"


@mock.patch("requests.request")
def test_plugin_slack_template_invalid_json(mock_request, tmpdir):
    """NotifySlack() - blocks template with invalid JSON fails gracefully."""
    mock_request.return_value = mock.Mock(
        **{"content": b"ok", "status_code": requests.codes.ok}
    )

    template = tmpdir.join("bad.json")
    template.write("{ not valid json }")

    obj = Apprise.instantiate(
        "slack://T1JJ3T3L2/A1BRTD4JD/TIiajkdnlazkcOXrIdevi7FQ/"
        "?blocks=yes&template={}".format(str(template))
    )
    assert isinstance(obj, NotifySlack)

    # Notification must fail due to bad JSON
    assert (
        obj.notify(body="x", title="y", notify_type=NotifyType.INFO) is False
    )
    # No HTTP call should have been made
    assert mock_request.called is False


@mock.patch("requests.request")
def test_plugin_slack_template_blocks_not_list(mock_request, tmpdir):
    """NotifySlack() - blocks template where 'blocks' is not a list fails."""
    mock_request.return_value = mock.Mock(
        **{"content": b"ok", "status_code": requests.codes.ok}
    )

    # 'blocks' present but not a list
    template = tmpdir.join("bad_blocks.json")
    template.write('{"blocks": "not-a-list"}')

    obj = Apprise.instantiate(
        "slack://T1JJ3T3L2/A1BRTD4JD/TIiajkdnlazkcOXrIdevi7FQ/"
        "?blocks=yes&template={}".format(str(template))
    )
    assert isinstance(obj, NotifySlack)
    assert (
        obj.notify(body="x", title="y", notify_type=NotifyType.INFO) is False
    )
    assert mock_request.called is False

    # Empty list is also rejected
    template.write('{"blocks": []}')
    obj2 = Apprise.instantiate(
        "slack://T1JJ3T3L2/A1BRTD4JD/TIiajkdnlazkcOXrIdevi7FQ/"
        "?blocks=yes&template={}".format(str(template))
    )
    assert isinstance(obj2, NotifySlack)
    assert (
        obj2.notify(body="x", title="y", notify_type=NotifyType.INFO) is False
    )
    assert mock_request.called is False


@mock.patch("requests.request")
def test_plugin_slack_template_block_missing_type(mock_request, tmpdir):
    """NotifySlack() - block missing 'type' string is rejected."""
    mock_request.return_value = mock.Mock(
        **{"content": b"ok", "status_code": requests.codes.ok}
    )

    # Block present but has no 'type' key
    template = tmpdir.join("no_type.json")
    template.write('{"blocks": [{"text": {"type": "mrkdwn", "text": "hi"}}]}')

    obj = Apprise.instantiate(
        "slack://T1JJ3T3L2/A1BRTD4JD/TIiajkdnlazkcOXrIdevi7FQ/"
        "?blocks=yes&template={}".format(str(template))
    )
    assert isinstance(obj, NotifySlack)
    assert (
        obj.notify(body="x", title="y", notify_type=NotifyType.INFO) is False
    )
    assert mock_request.called is False


@mock.patch("requests.request")
def test_plugin_slack_template_load_error(mock_request, tmpdir):
    """NotifySlack() - template OSError during read fails gracefully."""
    mock_request.return_value = mock.Mock(
        **{"content": b"ok", "status_code": requests.codes.ok}
    )

    # Write an empty file so the attachment resolves but open() can be mocked
    template = tmpdir.join("empty.json")
    template.write("")

    obj = Apprise.instantiate(
        "slack://T1JJ3T3L2/A1BRTD4JD/TIiajkdnlazkcOXrIdevi7FQ/"
        "?blocks=yes&template={}".format(str(template))
    )
    assert isinstance(obj, NotifySlack)

    with mock.patch("builtins.open", side_effect=OSError):
        # Notification must fail because the file cannot be read
        assert (
            obj.notify(body="x", title="y", notify_type=NotifyType.INFO)
            is False
        )
    assert mock_request.called is False


def test_plugin_slack_template_bad_tokens():
    """NotifySlack() - invalid tokens type raises TypeError."""
    with pytest.raises(TypeError):
        NotifySlack(
            token_a="T1JJ3T3L2",
            token_b="A1BRTD4JD",
            token_c="TIiajkdnlazkcOXrIdevi7FQ",
            tokens="not-a-dict",
        )


@mock.patch("requests.request")
def test_plugin_slack_template_url_roundtrip(mock_request, tmpdir):
    """NotifySlack() - template + tokens survive url()/parse_url()
    round-trip."""
    mock_request.return_value = mock.Mock(
        **{"content": b"ok", "status_code": requests.codes.ok}
    )

    template = tmpdir.join("rt.json")
    template.write(
        cleandoc("""
        {
          "blocks": [
            {
              "type": "section",
              "text": {"type": "mrkdwn", "text": "{{app_body}}"}
            }
          ]
        }
        """)
    )

    # Build an instance with template and tokens
    obj1 = NotifySlack(
        token_a="T1JJ3T3L2",
        token_b="A1BRTD4JD",
        token_c="TIiajkdnlazkcOXrIdevi7FQ",
        use_blocks=True,
        template=str(template),
        tokens={"key1": "val1", "key2": "val2"},
    )

    # Round-trip through url() -> parse_url()
    url = obj1.url()
    result = NotifySlack.parse_url(url)
    assert result is not None

    obj2 = NotifySlack(**result)
    assert isinstance(obj2, NotifySlack)

    # Connection identity must be preserved
    assert obj1.url_identifier == obj2.url_identifier

    # Tokens must survive the round-trip
    assert obj2.tokens.get("key1") == "val1"
    assert obj2.tokens.get("key2") == "val2"

    # Template must be present after round-trip
    assert obj2.template


@mock.patch("requests.request")
def test_plugin_slack_template_inaccessible(mock_request, tmpdir):
    """NotifySlack() - template attachment that cannot be accessed fails."""
    mock_request.return_value = mock.Mock(
        **{"content": b"ok", "status_code": requests.codes.ok}
    )

    # Point to a template file that does not exist
    missing = str(tmpdir.join("missing.json"))

    obj = Apprise.instantiate(
        "slack://T1JJ3T3L2/A1BRTD4JD/TIiajkdnlazkcOXrIdevi7FQ/"
        "?blocks=yes&template={}".format(missing)
    )
    assert isinstance(obj, NotifySlack)

    # Template attachment resolves to falsy because the file is missing
    assert (
        obj.notify(body="x", title="y", notify_type=NotifyType.INFO) is False
    )
    assert mock_request.called is False


def test_plugin_slack_template_add_failure():
    """NotifySlack() - TypeError when AppriseAttachment.add() drops entry."""
    # Simulate add() silently failing (returns 0 / len stays 0)
    with mock.patch("apprise.plugins.slack.AppriseAttachment") as mock_cls:
        inst = mock.MagicMock()
        inst.__len__ = mock.Mock(return_value=0)
        mock_cls.return_value = inst

        with pytest.raises(TypeError):
            NotifySlack(
                token_a="T1JJ3T3L2",
                token_b="A1BRTD4JD",
                token_c="TIiajkdnlazkcOXrIdevi7FQ",
                template="file:///some/template.json",
            )


@mock.patch("requests.request")
def test_plugin_slack_template_content_not_dict(mock_request, tmpdir):
    """NotifySlack() - template that parses to a JSON array is rejected."""
    mock_request.return_value = mock.Mock(
        **{"content": b"ok", "status_code": requests.codes.ok}
    )

    # Valid JSON but a list rather than an object
    template = tmpdir.join("array.json")
    template.write('[{"type": "section"}]')

    obj = Apprise.instantiate(
        "slack://T1JJ3T3L2/A1BRTD4JD/TIiajkdnlazkcOXrIdevi7FQ/"
        "?template={}".format(str(template))
    )
    assert isinstance(obj, NotifySlack)
    assert (
        obj.notify(body="x", title="y", notify_type=NotifyType.INFO) is False
    )
    assert mock_request.called is False


@mock.patch("requests.request")
def test_plugin_slack_template_block_not_dict(mock_request, tmpdir):
    """NotifySlack() - non-dict entry in blocks list is rejected."""
    mock_request.return_value = mock.Mock(
        **{"content": b"ok", "status_code": requests.codes.ok}
    )

    # blocks list contains a string rather than a dict
    template = tmpdir.join("bad_block.json")
    template.write('{"blocks": ["not-a-dict"]}')

    obj = Apprise.instantiate(
        "slack://T1JJ3T3L2/A1BRTD4JD/TIiajkdnlazkcOXrIdevi7FQ/"
        "?template={}".format(str(template))
    )
    assert isinstance(obj, NotifySlack)
    assert (
        obj.notify(body="x", title="y", notify_type=NotifyType.INFO) is False
    )
    assert mock_request.called is False


@mock.patch("requests.request")
def test_plugin_slack_template_none_token_value(mock_request, tmpdir):
    """NotifySlack() - None token value (e.g. app_image_url) is coerced
    to empty string before JSON-escaping."""
    mock_request.return_value = mock.Mock(
        **{"content": b"ok", "status_code": requests.codes.ok}
    )

    # Template references app_image_url which will be None when
    # include_image=False; old code produced corrupted JSON ("ul")
    template = tmpdir.join("img.json")
    template.write(
        '{"blocks": [{"type": "section",'
        ' "text": {"type": "mrkdwn",'
        ' "text": "{{app_body}} img={{app_image_url}}"}}]}'
    )

    obj = Apprise.instantiate(
        "slack://T1JJ3T3L2/A1BRTD4JD/TIiajkdnlazkcOXrIdevi7FQ/"
        "?image=no&template={}".format(str(template))
    )
    assert isinstance(obj, NotifySlack)
    # Must succeed -- None coerced to "" keeps the JSON valid
    assert (
        obj.notify(body="hello", title="t", notify_type=NotifyType.INFO)
        is True
    )
    assert mock_request.called is True
    payload = loads(mock_request.call_args_list[0][1]["data"])
    block_text = payload["attachments"][0]["blocks"][0]["text"]["text"]
    # app_image_url should expand to empty string, not "ul"
    assert "img=" in block_text
    assert "ul" not in block_text


@mock.patch("requests.request")
def test_plugin_slack_workflow_default_payload(mock_request):
    """NotifySlack() - Workflow Builder mode, default text payload."""
    mock_request.return_value = mock.Mock(
        **{"content": b"", "status_code": requests.codes.ok}
    )

    # 4-segment /workflows/ path via mode=workflow
    obj = Apprise.instantiate(
        "slack://T1JJ3T3L2/Ft07XXXX/XXXXXXXX/YYYYYYYY/?mode=workflow"
    )
    assert isinstance(obj, NotifySlack)
    assert obj.mode == "workflow"
    assert obj.workflow_path == [
        "T1JJ3T3L2",
        "Ft07XXXX",
        "XXXXXXXX",
        "YYYYYYYY",
    ]

    # Notification with title
    assert (
        obj.notify(body="hello", title="Alert", notify_type=NotifyType.INFO)
        is True
    )
    assert mock_request.called is True
    # Verify the POST URL uses the workflow base
    call_url = mock_request.call_args_list[0][0][1]
    assert "hooks.slack.com/workflows/" in call_url
    assert "T1JJ3T3L2/Ft07XXXX/XXXXXXXX/YYYYYYYY" in call_url
    # Verify default payload combines title and body
    posted = loads(mock_request.call_args_list[0][1]["data"])
    assert posted["text"] == "Alert: hello"

    mock_request.reset_mock()

    # Notification without title -- body only
    assert (
        obj.notify(body="body only", title="", notify_type=NotifyType.INFO)
        is True
    )
    posted = loads(mock_request.call_args_list[0][1]["data"])
    assert posted["text"] == "body only"


@mock.patch("requests.request")
def test_plugin_slack_workflow_trigger_mode(mock_request):
    """NotifySlack() - Workflow trigger mode (/triggers/ URL)."""
    mock_request.return_value = mock.Mock(
        **{"content": b"", "status_code": requests.codes.ok}
    )

    # 3-segment /triggers/ path via mode=trigger
    obj = Apprise.instantiate(
        "slack://T1JJ3T3L2/XXXXXXXX/YYYYYYYY/?mode=trigger"
    )
    assert isinstance(obj, NotifySlack)
    assert obj.mode == "trigger"
    assert obj.workflow_path == ["T1JJ3T3L2", "XXXXXXXX", "YYYYYYYY"]

    assert obj.notify(body="hi", title="", notify_type=NotifyType.INFO) is True
    call_url = mock_request.call_args_list[0][0][1]
    assert "hooks.slack.com/triggers/" in call_url
    assert "T1JJ3T3L2/XXXXXXXX/YYYYYYYY" in call_url


@mock.patch("requests.request")
def test_plugin_slack_workflow_native_url(mock_request):
    """NotifySlack() - parse_native_url() handles workflow/trigger URLs."""
    mock_request.return_value = mock.Mock(
        **{"content": b"", "status_code": requests.codes.ok}
    )

    # /workflows/ native URL
    obj = Apprise.instantiate(
        "https://hooks.slack.com/workflows"
        "/T1JJ3T3L2/Ft07XXXX/XXXXXXXX/YYYYYYYY"
    )
    assert isinstance(obj, NotifySlack)
    assert obj.mode == "workflow"
    assert obj.workflow_path == [
        "T1JJ3T3L2",
        "Ft07XXXX",
        "XXXXXXXX",
        "YYYYYYYY",
    ]
    assert (
        obj.notify(body="native", title="", notify_type=NotifyType.INFO)
        is True
    )
    call_url = mock_request.call_args_list[0][0][1]
    assert "hooks.slack.com/workflows/T1JJ3T3L2" in call_url

    mock_request.reset_mock()

    # /triggers/ native URL
    obj2 = Apprise.instantiate(
        "https://hooks.slack.com/triggers/T1JJ3T3L2/XXXXXXXX/YYYYYYYY"
    )
    assert isinstance(obj2, NotifySlack)
    assert obj2.mode == "trigger"
    assert (
        obj2.notify(body="trigger", title="", notify_type=NotifyType.INFO)
        is True
    )
    call_url2 = mock_request.call_args_list[0][0][1]
    assert "hooks.slack.com/triggers/T1JJ3T3L2" in call_url2


@mock.patch("requests.request")
def test_plugin_slack_workflow_url_roundtrip(mock_request):
    """NotifySlack() - workflow url()/parse_url() round-trip."""
    mock_request.return_value = mock.Mock(
        **{"content": b"", "status_code": requests.codes.ok}
    )

    original = "slack://T1JJ3T3L2/Ft07XXXX/XXXXXXXX/YYYYYYYY/?mode=workflow"
    obj = Apprise.instantiate(original)
    assert isinstance(obj, NotifySlack)

    # Reconstruct from url() output and re-instantiate
    rebuilt = Apprise.instantiate(obj.url())
    assert isinstance(rebuilt, NotifySlack)
    assert rebuilt.mode == obj.mode
    assert rebuilt.workflow_path == obj.workflow_path


def test_plugin_slack_workflow_invalid_path():
    """NotifySlack() - invalid path segment counts raise TypeError."""
    from apprise.plugins.slack import NotifySlack as _NS

    # Too few segments for explicit workflow mode (needs 4)
    with pytest.raises(TypeError):
        _NS(workflow_path=["T1JJ3T3L2", "XXXXXXXX"], mode="workflow")

    # Trigger's 3 segments rejected when mode=workflow is explicit
    with pytest.raises(TypeError):
        _NS(
            workflow_path=["T1JJ3T3L2", "XXXXXXXX", "YYYYYYYY"],
            mode="workflow",
        )

    # Workflow's 4 segments rejected when mode=trigger is explicit
    with pytest.raises(TypeError):
        _NS(
            workflow_path=["T1JJ3T3L2", "Ft07XXXX", "XXXXXXXX", "YYYY"],
            mode="trigger",
        )

    # Empty path -- must raise (auto-detect path, 0 segments)
    with pytest.raises(TypeError):
        _NS(workflow_path=[], mode="workflow")

    # Non-string / non-list type (else branch) -- 0 segments, must raise
    with pytest.raises(TypeError):
        _NS(workflow_path=42, mode="workflow")

    # Auto-detect: 4 segments -> WORKFLOW
    obj = _NS(workflow_path=["T1JJ3T3L2", "Ft07XXXX", "XXXXXXXX", "YYY"])
    assert obj.mode == "workflow"
    assert obj.workflow_path == ["T1JJ3T3L2", "Ft07XXXX", "XXXXXXXX", "YYY"]

    # Auto-detect: 3 segments -> WORKFLOW_TRIGGER
    obj = _NS(workflow_path=["T1JJ3T3L2", "XXXXXXXX", "YYYYYYYY"])
    assert obj.mode == "trigger"
    assert obj.workflow_path == ["T1JJ3T3L2", "XXXXXXXX", "YYYYYYYY"]

    # Auto-detect: 2 segments -> TypeError (neither 3 nor 4)
    with pytest.raises(TypeError):
        _NS(workflow_path=["T1JJ3T3L2", "XXXXXXXX"])


@mock.patch("requests.request")
def test_plugin_slack_workflow_template(mock_request, tmpdir):
    """NotifySlack() - Workflow mode with Block Kit JSON template."""
    mock_request.return_value = mock.Mock(
        **{"content": b"", "status_code": requests.codes.ok}
    )

    template = tmpdir.join("wf_blocks.json")
    template.write(
        cleandoc("""
        {
          "blocks": [
            {
              "type": "section",
              "text": {"type": "mrkdwn", "text": "{{app_body}}"}
            }
          ]
        }
        """)
    )

    obj = Apprise.instantiate(
        "slack://T1JJ3T3L2/Ft07XXXX/XXXXXXXX/YYYYYYYY/"
        "?mode=workflow&template={}".format(str(template))
    )
    assert isinstance(obj, NotifySlack)
    assert obj.mode == "workflow"
    assert (
        obj.notify(body="wf-tmpl", title="", notify_type=NotifyType.INFO)
        is True
    )
    assert mock_request.called is True
    call_url = mock_request.call_args_list[0][0][1]
    assert "hooks.slack.com/workflows/" in call_url
    posted = loads(mock_request.call_args_list[0][1]["data"])
    blocks = posted["blocks"]
    section = next(b for b in blocks if b.get("type") == "section")
    assert section["text"]["text"] == "wf-tmpl"

    # Invalid JSON template -- gen_payload() fails, send() returns False
    bad_template = tmpdir.join("bad.json")
    bad_template.write("not-json!")
    obj2 = Apprise.instantiate(
        "slack://T1JJ3T3L2/Ft07XXXX/XXXXXXXX/YYYYYYYY/"
        "?mode=workflow&template={}".format(str(bad_template))
    )
    assert isinstance(obj2, NotifySlack)
    assert (
        obj2.notify(body="x", title="", notify_type=NotifyType.INFO) is False
    )
    assert mock_request.call_count == 1  # no new request made
