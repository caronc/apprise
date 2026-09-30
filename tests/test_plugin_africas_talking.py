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

# Disable logging for a cleaner testing output
from json import dumps
import logging
from unittest import mock

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise, NotifyType
from apprise.exception import AppriseImproperlyConfigured
from apprise.plugins.africas_talking import NotifyAfricasTalking

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    (
        "atalk://",
        {
            # Instantiated but no auth, so no notification can happen
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "atalk://:@/",
        {
            # invalid auth
            "instance": AppriseImproperlyConfigured
        },
    ),
    (
        "atalk://user@^/",
        {
            # invalid apikey
            "instance": AppriseImproperlyConfigured
        },
    ),
    (
        "atalk://user@apikey/{}".format("3" * 5),
        {
            # invalid nubmer provided
            "instance": NotifyAfricasTalking,
            # Expected notify() response because we have no one to notify
            "notify_response": False,
        },
    ),
    (
        "atalk://user@apikey/123/{}/abcd/+{}".format("3" * 11, "4" * 11),
        {
            # includes a few invalid bits of info
            "instance": NotifyAfricasTalking,
            "privacy_url": "atalk://user@a...y/33333333333/+44444444444",
        },
    ),
    (
        "atalk://user@apikey/+{}?batch=y".format("4" * 11),
        {
            "instance": NotifyAfricasTalking,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "atalk://user@a...y/+44444444444",
        },
    ),
    (
        "atalk://user@apikey/+{}?mode=invalid".format("4" * 11),
        {"instance": AppriseImproperlyConfigured},
    ),
    (
        "atalk://user@apikey/+{}?mode=s".format("4" * 11),
        {
            # S will match the sandbox
            "instance": NotifyAfricasTalking,
        },
    ),
    (
        "atalk://user@apikey/+{}?mode=PREM".format("4" * 11),
        {
            # PREM will match premium (not case sensitive)
            "instance": NotifyAfricasTalking,
        },
    ),
    (
        "atalk://{}?apikey=key&user=user&from=FROMUSER".format("1" * 11),
        {
            # use get args to acomplish the same thing
            "instance": NotifyAfricasTalking,
        },
    ),
    (
        "atalk://_?user=user&to={},{}&key={}&from={}".format(
            "1" * 11, "2" * 11, "b" * 10, "5" * 13
        ),
        {
            # use get args to acomplish the same thing
            "instance": NotifyAfricasTalking,
        },
    ),
    (
        "atalk://user@apikey/{}/".format("1" * 11),
        {
            "instance": NotifyAfricasTalking,
            # throw a bizarre code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "atalk://user@apikey/{}/".format("1" * 11),
        {
            "instance": NotifyAfricasTalking,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracefully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_atalk_urls():
    """NotifyTemplate() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.post")
def test_plugin_atalk_edge_cases(mock_post):
    """NotifyAfricasTalking() Edge Cases."""

    # Initialize some generic (but valid) tokens
    apikey = "my-api-key"
    appuser = "my-app-user"
    targets = [
        "+1(555) 123-1234",
        "1555 5555555",
        # A garbage entry
        "12",
    ]

    # Prepare our response
    response = requests.Response()
    response.status_code = requests.codes.ok

    # Prepare Mock
    mock_post.return_value = response

    # Instantiate our object
    obj = Apprise.instantiate(
        "atalk://{}@{}/{}?batch=n".format(appuser, apikey, "/".join(targets))
    )

    assert (
        bool(
            obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        )
        is True
    )

    # We know there are 2 (valid) targets
    assert len(obj) == 2

    # Test our call count
    assert mock_post.call_count == 2

    # Test
    details = mock_post.call_args_list[0]
    headers = details[1]["headers"]
    assert headers["apiKey"] == apikey
    payload = details[1]["data"]
    assert payload["username"] == appuser
    assert payload["from"] == "AFRICASTKNG"
    assert payload["to"] == "+15551231234"
    assert payload["message"] == "title\r\nbody"

    details = mock_post.call_args_list[1]
    headers = details[1]["headers"]
    assert headers["apiKey"] == apikey
    payload = details[1]["data"]
    assert payload["username"] == appuser
    assert payload["from"] == "AFRICASTKNG"
    assert payload["to"] == "15555555555"
    assert payload["message"] == "title\r\nbody"

    # Verify our URL looks good
    assert obj.url().startswith(
        "atalk://{}@{}/{}".format(
            appuser, apikey, "/".join(["+15551231234", "15555555555"])
        )
    )

    assert "batch=no" in obj.url()

    # Reset our mock object
    mock_post.reset_mock()

    # With our batch in place, our calculations are different
    # Testing URL restructuring here as well where phone # is found
    # in host
    obj = Apprise.instantiate(
        "atalk://{}?user={}&apikey={}&batch=y&from=TEST".format(
            "/".join(targets), appuser, apikey
        )
    )

    # 2 phones were loaded but counted as 1 due to batch flag
    assert len(obj) == 1

    assert (
        bool(
            obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        )
        is True
    )

    # Test our call count (batched into 1)
    assert mock_post.call_count == 1

    details = mock_post.call_args_list[0]
    headers = details[1]["headers"]
    assert headers["apiKey"] == apikey
    payload = details[1]["data"]
    assert payload["username"] == appuser
    assert payload["from"] == "TEST"
    assert payload["to"] == "+15551231234,15555555555"
    assert payload["message"] == "title\r\nbody"


def _at_response(content, status=requests.codes.created):
    """Build a mocked Africas Talking reply."""
    response = mock.Mock()
    response.status_code = status
    response.content = (
        content if isinstance(content, bytes) else dumps(content)
    )
    return response


@mock.patch("requests.post")
def test_plugin_atalk_created_is_success(mock_post):
    """A 201 reply whose recipients were all queued is a success."""

    mock_post.return_value = _at_response(
        {
            "SMSMessageData": {
                "Message": "Sent to 2/2 Total Cost: KES 1.6000",
                "Recipients": [
                    {"number": "+15551231234", "statusCode": 101},
                    # Some replies carry the code as a string
                    {"number": "+15555555555", "statusCode": "102"},
                ],
            }
        }
    )

    aobj = Apprise()
    assert aobj.add("atalk://user@apikey/+15551231234/+15555555555?batch=yes")
    assert aobj.notify(body="body")
    assert mock_post.call_count == 1


@mock.patch("requests.post")
def test_plugin_atalk_recipient_failure(mock_post):
    """A rejected recipient fails the notification and is retried alone."""

    def respond(url, data=None, **kwargs):
        # The second number is always refused (InvalidPhoneNumber)
        recipients = [
            {"number": n, "statusCode": 403 if n == "+15555555555" else 101}
            for n in data["to"].split(",")
        ]
        return _at_response({"SMSMessageData": {"Recipients": recipients}})

    mock_post.side_effect = respond

    aobj = Apprise()
    assert aobj.add(
        "atalk://user@apikey/+15551231234/+15555555555"
        "?batch=yes&retry=1&wait=0"
    )
    assert not aobj.notify(body="body")

    # The retry only contacts the number that was refused
    assert mock_post.call_count == 2
    assert (
        mock_post.call_args_list[0][1]["data"]["to"]
        == "+15551231234,+15555555555"
    )
    assert mock_post.call_args_list[1][1]["data"]["to"] == "+15555555555"


@mock.patch("requests.post")
def test_plugin_atalk_empty_recipients_is_failure(mock_post):
    """A reply listing no recipients means nothing was sent."""

    mock_post.return_value = _at_response(
        {"SMSMessageData": {"Message": "InvalidSenderId", "Recipients": []}}
    )

    aobj = Apprise()
    assert aobj.add("atalk://user@apikey/+15551231234")
    assert not aobj.notify(body="body")


@mock.patch("requests.post")
def test_plugin_atalk_local_number_matches(mock_post):
    """A local number matches its international form in the reply."""

    mock_post.return_value = _at_response(
        {
            "SMSMessageData": {
                "Recipients": [
                    # Garbage entries are ignored
                    "garbage",
                    {"statusCode": None},
                    {"number": "+254711000111", "statusCode": "abc"},
                    {"number": "+254711000111", "statusCode": 100},
                ]
            }
        }
    )

    aobj = Apprise()
    assert aobj.add("atalk://user@apikey/0711000111")
    assert aobj.notify(body="body")


@mock.patch("requests.post")
def test_plugin_atalk_foreign_number_not_matched(mock_post):
    """A number from another country never marks a local one delivered."""

    # The Kenyan number is refused; the Tanzanian one is queued
    replies = {
        "0711222333": {"number": "+254711222333", "statusCode": 403},
        "+255711222333": {"number": "+255711222333", "statusCode": 101},
    }

    def respond(url, data=None, **kwargs):
        # Only the numbers sent in this request are reported back
        recipients = [replies[n] for n in data["to"].split(",")]
        return _at_response({"SMSMessageData": {"Recipients": recipients}})

    mock_post.side_effect = respond

    aobj = Apprise()
    assert aobj.add(
        "atalk://user@apikey/0711222333/+255711222333?batch=yes&retry=1&wait=0"
    )
    assert not aobj.notify(body="body")

    # Only the refused local number is tried again
    assert mock_post.call_count == 2
    assert mock_post.call_args_list[1][1]["data"]["to"] == "0711222333"


@mock.patch("requests.post")
def test_plugin_atalk_ambiguous_number_not_matched(mock_post):
    """An accepted number that could mean two targets marks neither."""

    mock_post.return_value = _at_response(
        {
            "SMSMessageData": {
                "Recipients": [
                    {"number": "+254711222333", "statusCode": 101},
                ]
            }
        }
    )

    obj = Apprise.instantiate(
        "atalk://user@apikey/0711222333/00711222333?batch=yes"
    )

    # Both local forms end the same way, so neither can be trusted
    assert (
        obj._accepted(mock_post.return_value, ["0711222333", "00711222333"])
        == []
    )


@pytest.mark.parametrize(
    "content",
    [
        b"not json",
        b"[]",
        b'{"SMSMessageData": []}',
        b'{"SMSMessageData": {"Recipients": {}}}',
    ],
)
@mock.patch("requests.post")
def test_plugin_atalk_unreadable_reply_trusts_http(mock_post, content):
    """A 2xx reply without a readable recipient list is a success."""

    mock_post.return_value = _at_response(content)

    aobj = Apprise()
    assert aobj.add("atalk://user@apikey/+15551231234")
    assert aobj.notify(body="body")
