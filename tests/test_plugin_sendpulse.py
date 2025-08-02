# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2025, Chris Caron <lead2gold@gmail.com>
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
from unittest import mock

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise, AppriseAttachment, NotifyType
from apprise.plugins.sendpulse import NotifySendPulse

logging.disable(logging.CRITICAL)

SENDPULSE_GOOD_RESPONSE = dumps({
    "access_token": "abc123",
    "expires_in": 3600,
})

SENDPULSE_BAD_RESPONSE = "{"

# Attachment Directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), "var")

# Our Testing URLs
apprise_url_tests = (
    ("sendpulse://", {
        "instance": TypeError,
    }),
    ("sendpulse://:@/", {
        "instance": TypeError,
    }),
    ("sendpulse://abcd", {
        # invalid from email
        "instance": TypeError,
    }),
    ("sendpulse://abcd@host.com", {
        # Just an Email specified, no client_id or client_secret
        "instance": TypeError,
    }),
    ("sendpulse://user@example.com/client_id/cs/?template=invalid", {
        # Invalid template
        "instance": TypeError,
    }),
    ("sendpulse://user@example.com/client_id/cs1/?template=123", {
        "instance": NotifySendPulse,
        "requests_response_text": SENDPULSE_GOOD_RESPONSE,
    }),
    ("sendpulse://user@example.com/client_id/cs1/", {
        "instance": NotifySendPulse,
        "requests_response_text": SENDPULSE_GOOD_RESPONSE,
    }),
    ("sendpulse://user@example.com/client_id/cs1/?format=text", {
        "instance": NotifySendPulse,
        "requests_response_text": SENDPULSE_GOOD_RESPONSE,
    }),
    ("sendpulse://user@example.com/client_id/cs1/?format=html", {
        "instance": NotifySendPulse,
        "requests_response_text": SENDPULSE_GOOD_RESPONSE,
    }),
    ("sendpulse://chris@example.com/client_id/cs1/?from=Chris", {
        # Set name only
        "instance": NotifySendPulse,
        "requests_response_text": SENDPULSE_GOOD_RESPONSE,
    }),
    ("sendpulse://?id=ci&secret=cs&user=chris@example.com", {
        # Set login through user= only
        "instance": NotifySendPulse,
        "requests_response_text": SENDPULSE_GOOD_RESPONSE,
    }),
    ("sendpulse://?id=ci&secret=cs&user=Chris<chris@example.com>", {
        # Set login through user= only
        "instance": NotifySendPulse,
        "requests_response_text": SENDPULSE_GOOD_RESPONSE,
    }),
    ("sendpulse://?id=ci&secret=cs&user=chris", {
        # Set login through user= only - invaild email
        "instance": TypeError,
    }),
    ("sendpulse://example.com/client_id/cs1/?user=chris", {
        # Set user as a name only
        "instance": NotifySendPulse,
        "requests_response_text": SENDPULSE_GOOD_RESPONSE,
    }),
    ("sendpulse://client_id/cs1/?user=chris@example.ca", {
        # Set user as email
        "instance": NotifySendPulse,
        "requests_response_text": SENDPULSE_GOOD_RESPONSE,
    }),
    ("sendpulse://client_id/cs1/?from=Chris<chris@example.com>", {
        # set full email with name
        "instance": NotifySendPulse,
        "requests_response_text": SENDPULSE_GOOD_RESPONSE,
    }),
    ("sendpulse://?from=Chris<chris@example.com>&id=ci&secret=cs", {
        # leverage all get params from URL
        "instance": NotifySendPulse,
        "requests_response_text": SENDPULSE_GOOD_RESPONSE,
    }),
    ("sendpulse://user@example.com/client_id/cs1a/", {
        "instance": NotifySendPulse,
        "requests_response_text": SENDPULSE_BAD_RESPONSE,
        # Notify will fail because auth failed
        "response": False,
    }),
    ("sendpulse://user@example.com/client_id/cs2/"
     "?bcc=l2g@nuxref.com", {
         # A good email with Blind Carbon Copy
         "instance": NotifySendPulse,
         "requests_response_text": SENDPULSE_GOOD_RESPONSE,
     }),
    ("sendpulse://user@example.com/client_id/cs2/"
     "?bcc=invalid", {
         # A good email with Blind Carbon Copy
         "instance": NotifySendPulse,
         "requests_response_text": SENDPULSE_GOOD_RESPONSE,
     }),
    ("sendpulse://user@example.com/client_id/cs3/"
     "?cc=l2g@nuxref.com", {
         # A good email with Carbon Copy
         "instance": NotifySendPulse,
         "requests_response_text": SENDPULSE_GOOD_RESPONSE,
     }),
    ("sendpulse://user@example.com/client_id/cs4/"
     "?cc=Chris<l2g@nuxref.com>", {
         # A good email with Carbon Copy
         "instance": NotifySendPulse,
         "requests_response_text": SENDPULSE_GOOD_RESPONSE,
     }),
    ("sendpulse://user@example.com/client_id/cs5/"
     "?cc=invalid", {
         # A good email with Carbon Copy
         "instance": NotifySendPulse,
         "requests_response_text": SENDPULSE_GOOD_RESPONSE,
     }),
    ("sendpulse://user@example.com/client_id/cs6/"
     "?to=invalid", {
         # an invalid to email
         "instance": NotifySendPulse,
         "requests_response_text": SENDPULSE_GOOD_RESPONSE,
     }),
    ("sendpulse://user@example.com/client_id/cs7/chris@example.com", {
        # An email with a designated to email
        "instance": NotifySendPulse,
        "requests_response_text": SENDPULSE_GOOD_RESPONSE,
    }),
    ("sendpulse://user@example.com/client_id/cs8/"
     "?to=Chris<chris@example.com>", {
         # An email with a full name in in To field
         "instance": NotifySendPulse,
         "requests_response_text": SENDPULSE_GOOD_RESPONSE,
     }),
    ("sendpulse://user@example.com/client_id/cs9/"
     "chris@example.com/chris2@example.com/Test<test@test.com>", {
         # Several emails to notify
         "instance": NotifySendPulse,
         "requests_response_text": SENDPULSE_GOOD_RESPONSE,
     }),
    ("sendpulse://user@example.com/client_id/cs10/"
     "?cc=Chris<chris@example.com>", {
         # An email with a full name in cc
         "instance": NotifySendPulse,
         "requests_response_text": SENDPULSE_GOOD_RESPONSE,
     }),
    ("sendpulse://user@example.com/client_id/cs11/"
     "?cc=chris@example.com", {
         # An email with a full name in cc
         "instance": NotifySendPulse,
         "requests_response_text": SENDPULSE_GOOD_RESPONSE,
     }),
    ("sendpulse://user@example.com/client_id/cs12/"
     "?bcc=Chris<chris@example.com>", {
         # An email with a full name in bcc
         "instance": NotifySendPulse,
         "requests_response_text": SENDPULSE_GOOD_RESPONSE,
     }),
    ("sendpulse://user@example.com/client_id/cs13/"
     "?bcc=chris@example.com", {
         # An email with a full name in bcc
         "instance": NotifySendPulse,
         "requests_response_text": SENDPULSE_GOOD_RESPONSE,
     }),
    ("sendpulse://user@example.com/client_id/cs14/"
     "?to=Chris<chris@example.com>", {
         # An email with a full name in bcc
         "instance": NotifySendPulse,
         "requests_response_text": SENDPULSE_GOOD_RESPONSE,
     }),
    ("sendpulse://user@example.com/client_id/cs15/"
     "?to=chris@example.com", {
         # An email with a full name in bcc
         "instance": NotifySendPulse,
         "requests_response_text": SENDPULSE_GOOD_RESPONSE,
     }),
    ("sendpulse://user@example.com/client_id/cs16/"
     "?template=1234&+sub=value&+sub2=value2", {
         # A good email with a template + substitutions
         "instance": NotifySendPulse,
         "requests_response_text": SENDPULSE_GOOD_RESPONSE,

         # Our expected url(privacy=True) startswith() response:
         "privacy_url": "sendpulse://user@example.com/c...d/c...6/",
     }),
    ("sendpulse://user@example.com/client_id/cs17/", {
        "instance": NotifySendPulse,
        # force a failure
        "response": False,
        "requests_response_code": requests.codes.internal_server_error,
        "requests_response_text": SENDPULSE_GOOD_RESPONSE,
    }),
    ("sendpulse://user@example.com/client_id/cs18/", {
        "instance": NotifySendPulse,
        # throw a bizzare code forcing us to fail to look it up
        "response": False,
        "requests_response_code": 999,
        "requests_response_text": SENDPULSE_GOOD_RESPONSE,
    }),
    ("sendpulse://user@example.com/client_id/cs19/", {
        "instance": NotifySendPulse,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        "test_requests_exceptions": True,
        "requests_response_text": SENDPULSE_GOOD_RESPONSE,
    }),
)


def test_plugin_sendpulse_urls():
    """
    NotifySendPulse() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.post")
def test_plugin_sendpulse_edge_cases(mock_post):
    """
    NotifySendPulse() Edge Cases
    """
    request = mock.Mock()
    request.status_code = requests.codes.ok
    request.content = SENDPULSE_GOOD_RESPONSE

    # Prepare Mock
    mock_post.return_value = request

    obj = Apprise.instantiate(
        "sendpulse://user@example.com/ci/cs/Test<test@example.com>")

    assert obj.notify(
        body="body", title="title", notify_type=NotifyType.INFO) is True

    # Test our call count
    assert mock_post.call_count == 2

    # Authentication
    assert mock_post.call_args_list[0][0][0] == \
        "https://api.sendpulse.com/oauth/access_token"

    payload = loads(mock_post.call_args_list[0][1]["data"])
    assert payload == {
        "grant_type": "client_credentials",
        "client_id": "ci",
        "client_secret": "cs",
    }

    assert mock_post.call_args_list[1][0][0] == \
        "https://api.sendpulse.com/smtp/emails"
    payload = loads(mock_post.call_args_list[1][1]["data"])

    assert payload == {
        "email": {
            "from": {
                "email": "user@example.com", "name": "Apprise"
            },
            "to": [{"email": "test@example.com", "name": "Test"}],
            "subject": "title", "text": "body", "html": "Ym9keQ=="}}

    mock_post.reset_mock()

    obj = Apprise.instantiate("sendpulse://user@example.com/ci/cs/?from=John")

    assert obj.notify(
        body="body", title="title", notify_type=NotifyType.INFO) is True

    # Test our call count
    assert mock_post.call_count == 2

    # Authentication
    assert mock_post.call_args_list[0][0][0] == \
        "https://api.sendpulse.com/oauth/access_token"

    payload = loads(mock_post.call_args_list[0][1]["data"])
    assert payload == {
        "grant_type": "client_credentials",
        "client_id": "ci",
        "client_secret": "cs",
    }

    assert mock_post.call_args_list[1][0][0] == \
        "https://api.sendpulse.com/smtp/emails"
    payload = loads(mock_post.call_args_list[1][1]["data"])

    assert payload == {
        "email": {
            "from": {
                "email": "user@example.com", "name": "John"
            },
            "to": [{"email": "user@example.com", "name": "John"}],
            "subject": "title", "text": "body", "html": "Ym9keQ=="}}

    mock_post.reset_mock()

    # Second call no longer needs to authenticate
    assert obj.notify(
        body="body", title="title", notify_type=NotifyType.INFO) is True

    assert mock_post.call_count == 1

    assert mock_post.call_args_list[0][0][0] == \
        "https://api.sendpulse.com/smtp/emails"

    # force an exception
    mock_post.side_effect = requests.RequestException
    assert obj.notify(
        body="body", title="title", notify_type=NotifyType.INFO) is False

    # Set an invalid return code
    mock_post.side_effect = None
    request.status_code = 403
    assert obj.notify(
        body="body", title="title", notify_type=NotifyType.INFO) is False

    # Test re-authentication
    mock_post.reset_mock()
    request = mock.Mock()
    obj = Apprise.instantiate("sendpulse://usr2@example.com/ci/cs/?from=Retry")

    class sendpulse:
        def __init__(self):
            # 200 login okay
            # 401 on retrival
            # recursive re-attempt to login returns 200
            # fetch after works
            self._side_effect = iter([
                requests.codes.ok, requests.codes.unauthorized,
                requests.codes.ok, requests.codes.ok,
            ])

        @property
        def status_code(self):
            return next(self._side_effect)

        @property
        def content(self):
            return SENDPULSE_GOOD_RESPONSE

    mock_post.return_value = sendpulse()

    assert obj.notify(
        body="body", title="title", notify_type=NotifyType.INFO) is True

    assert mock_post.call_count == 4
    # Authentication
    assert mock_post.call_args_list[0][0][0] == \
        "https://api.sendpulse.com/oauth/access_token"
    # 401 received
    assert mock_post.call_args_list[1][0][0] == \
        "https://api.sendpulse.com/smtp/emails"
    # Re-authenticate
    assert mock_post.call_args_list[2][0][0] == \
        "https://api.sendpulse.com/oauth/access_token"
    # Try again
    assert mock_post.call_args_list[3][0][0] == \
        "https://api.sendpulse.com/smtp/emails"

    # Test re-authentication  (no recursive loops)
    mock_post.reset_mock()
    request = mock.Mock()
    obj = Apprise.instantiate("sendpulse://usr2@example.com/ci/cs/?from=Retry")

    class sendpulse:
        def __init__(self):
            # oauth always returns okay but notify returns 401
            # recursive re-attempt only once
            self._side_effect = iter([
                requests.codes.ok, requests.codes.unauthorized,
                requests.codes.ok, requests.codes.unauthorized,
                requests.codes.ok, requests.codes.unauthorized,
                requests.codes.ok, requests.codes.unauthorized,
                requests.codes.ok, requests.codes.unauthorized,
                requests.codes.ok, requests.codes.unauthorized,
                requests.codes.ok, requests.codes.unauthorized,
                requests.codes.ok, requests.codes.unauthorized,
            ])

        @property
        def status_code(self):
            return next(self._side_effect)

        @property
        def content(self):
            return SENDPULSE_GOOD_RESPONSE

    mock_post.return_value = sendpulse()

    assert obj.notify(
        body="body", title="title", notify_type=NotifyType.INFO) is False

    assert mock_post.call_count == 4
    # Authentication
    assert mock_post.call_args_list[0][0][0] == \
        "https://api.sendpulse.com/oauth/access_token"
    # 401 received
    assert mock_post.call_args_list[1][0][0] == \
        "https://api.sendpulse.com/smtp/emails"
    # Re-authenticate
    assert mock_post.call_args_list[2][0][0] == \
        "https://api.sendpulse.com/oauth/access_token"
    # Last failed attempt
    assert mock_post.call_args_list[3][0][0] == \
        "https://api.sendpulse.com/smtp/emails"

    mock_post.side_effect = None
    request = mock.Mock()
    request.status_code = requests.codes.ok
    request.content = SENDPULSE_GOOD_RESPONSE
    mock_post.return_value = request
    for expires_in in (None, -1, "garbage", 3600, 300000):
        request.content = dumps({
            "access_token": "abc123",
            "expires_in": expires_in,
        })

        # Instantiate our object
        obj = Apprise.instantiate("sendpulse://user@example.com/ci/cs/")

        # Test variations of responses
        obj.notify(
            body="body", title="title", notify_type=NotifyType.INFO)

        # expires_in is missing
        request.content = dumps({
            "access_token": "abc123",
        })

        # Instantiate our object
        obj = Apprise.instantiate("sendpulse://user@example.com/ci/cs/")
        assert obj.notify(
            body="body", title="title", notify_type=NotifyType.INFO) is True


def test_plugin_sendpulse_fail_cases():
    """
    NotifySendPulse() Fail Cases

    """

    # no client_id
    with pytest.raises(TypeError):
        NotifySendPulse(
            client_id="abcd", client_secret=None,
            from_addr="user@example.com")

    with pytest.raises(TypeError):
        NotifySendPulse(
            client_id=None, client_secret="abcd123",
            from_addr="user@example.com")

    # invalid from email
    with pytest.raises(TypeError):
        NotifySendPulse(
            client_id="abcd", client_secret="abcd456", from_addr="!invalid")

    # no email
    with pytest.raises(TypeError):
        NotifySendPulse(
            client_id="abcd", client_secret="abcd789", from_addr=None)

    # Invalid To email address
    NotifySendPulse(
        client_id="abcd", client_secret="abcd321",
        from_addr="user@example.com", targets="!invalid")

    # Test invalid bcc/cc entries mixed with good ones
    assert isinstance(NotifySendPulse(
        client_id="abcd", client_secret="abcd654",
        from_addr="l2g@example.com",
        bcc=("abc@def.com", "!invalid"),
        cc=("abc@test.org", "!invalid")), NotifySendPulse)


@mock.patch("requests.post")
def test_plugin_sendpulse_attachments(mock_post):
    """
    NotifySendPulse() Attachments

    """

    request = mock.Mock()
    request.status_code = requests.codes.ok
    request.content = SENDPULSE_GOOD_RESPONSE

    # Prepare Mock
    mock_post.return_value = request

    path = os.path.join(TEST_VAR_DIR, "apprise-test.gif")
    attach = AppriseAttachment(path)
    obj = Apprise.instantiate("sendpulse://user@example.com/aaaa/bbbb")
    assert isinstance(obj, NotifySendPulse)
    assert obj.notify(
        body="body", title="title", notify_type=NotifyType.INFO,
        attach=attach) is True

    mock_post.reset_mock()

    # Try again in a use case where we can't access the file
    with mock.patch("os.path.isfile", return_value=False):
        assert obj.notify(
            body="body", title="title", notify_type=NotifyType.INFO,
            attach=attach) is False

    # Try again in a use case where we can't access the file
    with mock.patch("builtins.open", side_effect=OSError):
        assert obj.notify(
            body="body", title="title", notify_type=NotifyType.INFO,
            attach=attach) is False
