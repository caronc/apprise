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
from unittest import mock
from urllib.parse import urlparse

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise, NotifyType
from apprise.plugins.mobilemessage import NotifyMobileMessage

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    (
        "mobilemessage://",
        {
            # No credentials at all
            "instance": TypeError,
        },
    ),
    (
        "mobilemessage://:@/",
        {
            # No credentials at all
            "instance": TypeError,
        },
    ),
    (
        "mobilemessage://user@ALERTS/0412345678",
        {
            # No API password provided
            "instance": TypeError,
        },
    ),
    (
        "mobilemessage://user:pass@/0412345678",
        {
            # No Sender ID provided
            "instance": TypeError,
        },
    ),
    (
        "mobilemessage://user:pass@%20/0412345678",
        {
            # A Sender ID of nothing but whitespace
            "instance": TypeError,
        },
    ),
    (
        "mobilemessage://user:pass@ALERTS/",
        {
            # No targets to notify
            "instance": NotifyMobileMessage,
            "notify_response": False,
        },
    ),
    (
        "mobilemessage://user:pass@ALERTS/0412345678",
        {
            "instance": NotifyMobileMessage,
            "privacy_url": "mobilemessage://user:****@ALERTS/61412345678",
        },
    ),
    (
        "mobilemsg://user:pass@ALERTS/0412345678",
        {
            # The shorthand schema normalises back to the full one
            "instance": NotifyMobileMessage,
            "privacy_url": "mobilemessage://user:****@ALERTS/61412345678",
        },
    ),
    (
        "mobilemessage://user:pass@+61 400 000 000/61412345678",
        {
            # A phone number Sender ID is reduced to digits
            "instance": NotifyMobileMessage,
            "privacy_url": (
                "mobilemessage://user:****@61400000000/61412345678"
            ),
        },
    ),
    (
        "mobilemessage://user:pass@ALERTS/0412345678/412345679/61412345680",
        {
            # Every accepted way of writing an Australian mobile
            "instance": NotifyMobileMessage,
            "privacy_url": (
                "mobilemessage://user:****@ALERTS/61412345678/61412345679"
            ),
        },
    ),
    (
        "mobilemessage://user:pass@ALERTS/0412345678/abcd/15551231234",
        {
            # Garbage and a non-Australian number are both dropped
            "instance": NotifyMobileMessage,
            "privacy_url": "mobilemessage://user:****@ALERTS/61412345678",
        },
    ),
    (
        "mobilemessage://user:pass@ALERTS/15551231234",
        {
            # Nothing is left to notify once the US number is dropped
            "instance": NotifyMobileMessage,
            "notify_response": False,
        },
    ),
    (
        "mobilemessage://user:pass@ALERTS/0412345678?max_parts=invalid",
        {
            # max_parts must be a number
            "instance": TypeError,
        },
    ),
    (
        "mobilemessage://user:pass@ALERTS/0412345678?max_parts=0",
        {
            # max_parts is below the accepted range
            "instance": TypeError,
        },
    ),
    (
        "mobilemessage://user:pass@ALERTS/0412345678?max_parts=100",
        {
            # max_parts is above the accepted range
            "instance": TypeError,
        },
    ),
    (
        "mobilemessage://user:pass@ALERTS/0412345678"
        "?unicode=yes&batch=no&max_parts=2&ref=nightly",
        {
            # Every option at once
            "instance": NotifyMobileMessage,
            "privacy_url": "mobilemessage://user:****@ALERTS/61412345678",
        },
    ),
    (
        "mobilemessage://user:pass@0412345678/?from=ALERTS",
        {
            # With from=, the hostname becomes a target
            "instance": NotifyMobileMessage,
            "privacy_url": "mobilemessage://user:****@ALERTS/61412345678",
        },
    ),
    (
        "mobilemessage://user:pass@ALERTS/?to=0412345678,0498765432",
        {
            "instance": NotifyMobileMessage,
            "privacy_url": (
                "mobilemessage://user:****@ALERTS/61412345678/61498765432"
            ),
        },
    ),
    (
        "mobilemessage://user:pass@ALERTS/0412345678",
        {
            "instance": NotifyMobileMessage,
            # A failure from the upstream server
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "mobilemessage://user:pass@ALERTS/0412345678",
        {
            "instance": NotifyMobileMessage,
            # An unknown status code has no mapped description
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "mobilemessage://user:pass@ALERTS/0412345678",
        {
            "instance": NotifyMobileMessage,
            # Exercise request exception handling
            "test_requests_exceptions": True,
        },
    ),
)


def _mk_resp(payload, code=requests.codes.ok):
    """Build a mocked requests response carrying the given payload."""
    response = mock.Mock()
    response.status_code = code
    response.content = dumps(payload).encode("utf-8")
    return response


def test_plugin_mobilemessage_urls():
    """NotifyMobileMessage() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


def test_plugin_mobilemessage_init():
    """NotifyMobileMessage() initialisation."""

    # An API username and password are both mandatory
    with pytest.raises(TypeError):
        NotifyMobileMessage(source="ALERTS", targets="0412345678")

    with pytest.raises(TypeError):
        NotifyMobileMessage(user="user", source="ALERTS", targets="0412345678")

    # A Sender ID is mandatory
    with pytest.raises(TypeError):
        NotifyMobileMessage(user="user", password="pass", targets="0412345678")

    # A valid object
    obj = NotifyMobileMessage(
        user="user",
        password="pass",
        source="ALERTS",
        targets="0412345678",
    )
    assert obj.targets == ["61412345678"]
    assert obj.unicode is False
    assert obj.batch is True
    assert obj.max_parts == 10
    assert obj.ref is None
    assert len(obj) == 1

    # An object with no targets still counts as one notification
    obj = NotifyMobileMessage(user="user", password="pass", source="ALERTS")
    assert obj.targets == []
    assert len(obj) == 1

    # Batch mode turned off counts every target separately
    obj = NotifyMobileMessage(
        user="user",
        password="pass",
        source="ALERTS",
        targets=["0412345678", "0498765432"],
        batch=False,
    )
    assert len(obj) == 2

    # Our identity does not change when the targets do
    other = NotifyMobileMessage(
        user="user",
        password="pass",
        source="ALERTS",
        targets="0411111111",
    )
    assert obj.url_identifier == other.url_identifier


def test_plugin_mobilemessage_max_parts():
    """NotifyMobileMessage() max_parts handling."""

    # A value that is not a number at all
    with pytest.raises(TypeError):
        NotifyMobileMessage(
            user="user",
            password="pass",
            source="ALERTS",
            targets="0412345678",
            max_parts="invalid",
        )

    # Below and above the accepted range
    for value in (0, 100):
        with pytest.raises(TypeError):
            NotifyMobileMessage(
                user="user",
                password="pass",
                source="ALERTS",
                targets="0412345678",
                max_parts=value,
            )

    # The body limit follows the part count and the encoding
    obj = NotifyMobileMessage(
        user="user",
        password="pass",
        source="ALERTS",
        targets="0412345678",
    )
    assert obj.body_maxlen == 1530

    obj = NotifyMobileMessage(
        user="user",
        password="pass",
        source="ALERTS",
        targets="0412345678",
        unicode=True,
    )
    assert obj.body_maxlen == 670

    obj = NotifyMobileMessage(
        user="user",
        password="pass",
        source="ALERTS",
        targets="0412345678",
        unicode=True,
        max_parts=3,
    )
    assert obj.body_maxlen == 201


def test_plugin_mobilemessage_targets():
    """NotifyMobileMessage() target handling."""

    obj = NotifyMobileMessage(
        user="user",
        password="pass",
        source="ALERTS",
        targets=[
            # Local format
            "0412345678",
            # Leading zero left off
            "412345679",
            # International format
            "61412345680",
            # Nicely formatted international
            "+61 412 345 681",
            # Not a phone number at all
            "abcd",
            # Too short to be anything
            "123",
            # A United States number
            "15551231234",
            # An Australian landline, not a mobile
            "0298765432",
        ],
    )

    assert obj.targets == [
        "61412345678",
        "61412345679",
        "61412345680",
        "61412345681",
    ]


@mock.patch("requests.post")
def test_plugin_mobilemessage_send(mock_post):
    """NotifyMobileMessage() send handling."""

    # Every recipient was accepted
    mock_post.return_value = _mk_resp(
        {
            "status": "complete",
            "results": [{"to": "61412345678", "status": "success"}],
        }
    )

    obj = Apprise.instantiate(
        "mobilemessage://user:pass@ALERTS/0412345678?ref=nightly"
    )
    assert obj.notify(body="body", notify_type=NotifyType.INFO) is True

    assert mock_post.call_count == 1
    call = mock_post.call_args_list[0]

    # We reached the documented endpoint
    assert urlparse(call[0][0]).hostname == "api.mobilemessage.com.au"

    # Basic authentication carries our API key pair
    assert call[1]["auth"] == ("user", "pass")

    # Our payload holds one entry per recipient
    payload = loads(call[1]["data"])
    assert payload["messages"] == [
        {
            "to": "61412345678",
            "message": "body",
            "sender": "ALERTS",
            "custom_ref": "nightly",
        }
    ]
    assert payload["enable_unicode"] is False
    assert payload["max_parts"] == 10

    # Every request carries its own idempotency key
    assert len(call[1]["headers"]["Idempotency-Key"]) > 0


@mock.patch("requests.post")
def test_plugin_mobilemessage_batch(mock_post):
    """NotifyMobileMessage() batch handling."""

    mock_post.return_value = _mk_resp({"status": "complete"})

    # Batch mode is on by default, so both recipients share one request
    obj = Apprise.instantiate(
        "mobilemessage://user:pass@ALERTS/0412345678/0498765432"
    )
    assert obj.notify(body="body") is True
    assert mock_post.call_count == 1

    payload = loads(mock_post.call_args_list[0][1]["data"])
    assert len(payload["messages"]) == 2

    # Turning batch mode off gives each recipient its own request
    mock_post.reset_mock()
    obj = Apprise.instantiate(
        "mobilemessage://user:pass@ALERTS/0412345678/0498765432?batch=no"
    )
    assert obj.notify(body="body") is True
    assert mock_post.call_count == 2

    # Each request gets a key of its own
    keys = {
        call[1]["headers"]["Idempotency-Key"]
        for call in mock_post.call_args_list
    }
    assert len(keys) == 2


@mock.patch("requests.post")
def test_plugin_mobilemessage_results(mock_post):
    """NotifyMobileMessage() per recipient result handling."""

    obj = Apprise.instantiate(
        "mobilemessage://user:pass@ALERTS/0412345678/0498765432"
    )

    # A recipient the service refused fails the notification
    mock_post.return_value = _mk_resp(
        {
            "results": [
                {"to": "61412345678", "status": "success"},
                {
                    "to": "61498765432",
                    "status": "blocked",
                    "error": "Recipient has unsubscribed",
                },
            ],
        }
    )
    assert obj.notify(body="body") is False

    # An entry with nothing useful in it still fails
    mock_post.return_value = _mk_resp(
        {
            "results": [{"status": "error"}],
        }
    )
    assert obj.notify(body="body") is False

    # Entries that are not objects are ignored
    mock_post.return_value = _mk_resp({"results": ["unexpected"]})
    assert obj.notify(body="body") is True

    # A results field of the wrong shape is ignored
    mock_post.return_value = _mk_resp({"results": "unexpected"})
    assert obj.notify(body="body") is True

    # An unreadable body falls back to the HTTP status
    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = b"<html>not json</html>"
    mock_post.return_value = response
    assert obj.notify(body="body") is True


@mock.patch("requests.post")
def test_plugin_mobilemessage_errors(mock_post):
    """NotifyMobileMessage() error handling."""

    obj = Apprise.instantiate(
        "mobilemessage://user:pass@ALERTS/0412345678/0498765432?batch=no"
    )

    # A documented error code
    mock_post.return_value = _mk_resp(
        {"error": "Unauthorized"}, code=requests.codes.unauthorized
    )
    assert obj.notify(body="body") is False

    # A code we have no message for
    mock_post.return_value = _mk_resp({}, code=999)
    assert obj.notify(body="body") is False

    # The connection never got anywhere
    mock_post.side_effect = requests.ConnectionError(
        0, "requests.ConnectionError() not handled"
    )
    assert obj.notify(body="body") is False


def test_plugin_mobilemessage_url_parsing():
    """NotifyMobileMessage() URL parsing."""

    # Every supported query argument
    results = NotifyMobileMessage.parse_url(
        "mobilemessage://user:pass@ALERTS/0412345678"
        "?unicode=yes&batch=no&max_parts=4&ref=nightly&to=0498765432"
    )
    assert results["source"] == "ALERTS"
    assert results["targets"] == ["0412345678", "0498765432"]
    assert results["unicode"] is True
    assert results["batch"] is False
    assert results["max_parts"] == "4"
    assert results["ref"] == "nightly"

    # With from=, the hostname becomes a target
    results = NotifyMobileMessage.parse_url(
        "mobilemessage://user:pass@0412345678/0498765432?from=ALERTS"
    )
    assert results["source"] == "ALERTS"
    assert results["targets"] == ["0412345678", "0498765432"]

    # A URL we cannot make sense of at all
    assert NotifyMobileMessage.parse_url("mobilemessage://") is not None
    assert NotifyMobileMessage.parse_url(None) is None


@mock.patch("requests.post")
def test_plugin_mobilemessage_apprise_integration(mock_post):
    """NotifyMobileMessage() Apprise integration."""

    mock_post.return_value = _mk_resp({"status": "complete"})

    aobj = Apprise()
    assert aobj.add("mobilemessage://user:pass@ALERTS/0412345678")
    assert aobj.add("mobilemsg://user:pass@61400000000/0498765432")
    assert len(aobj) == 2
    assert aobj.notify(title="title", body="body") is True
    assert mock_post.call_count == 2

    # The title is folded into the body because SMS has no title field
    payload = loads(mock_post.call_args_list[0][1]["data"])
    assert payload["messages"][0]["message"] == "title\r\nbody"
