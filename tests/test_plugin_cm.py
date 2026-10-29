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
import json
import logging
from unittest import mock
from urllib.parse import urlparse

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise
from apprise.exception import AppriseImproperlyConfigured
from apprise.plugins.cm import NotifyCM

logging.disable(logging.CRITICAL)

# A realistic Product Token
TOKEN = "0123abcd-4567-89ef-abcd-0123456789ab"


def _result(*rejected: str) -> bytes:
    """Build a CM.com response where only ``rejected`` numbers failed."""
    return json.dumps(
        {
            "details": "Created 1 message(s)",
            "errorCode": 201,
            "messages": [
                {
                    "to": "0015551234567",
                    "status": "Rejected" if rejected else "Accepted",
                    "messageDetails": rejected[0] if rejected else None,
                    "messageErrorCode": 303 if rejected else 0,
                },
                {
                    "to": "0015551234568",
                    "status": "Accepted",
                    "messageDetails": None,
                    "messageErrorCode": 0,
                },
            ],
        }
    ).encode("utf-8")


# A successful CM.com response
OK_RESPONSE = json.dumps(
    {"details": "Created 1 message(s)", "errorCode": 0, "messages": []}
).encode("utf-8")

# Our Testing URLs
apprise_url_tests = (
    (
        "cm://",
        {
            # No Product Token specified
            "instance": TypeError,
        },
    ),
    (
        "cm://abcd/15551234567",
        {
            # An invalid Product Token
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        f"cm://{TOKEN}",
        {
            # No phone numbers; we load but have nothing to notify
            "instance": NotifyCM,
            "notify_response": False,
        },
    ),
    (
        f"cm://{TOKEN}/15551234567",
        {
            "instance": NotifyCM,
            "requests_response_text": OK_RESPONSE,
            # Our expected url(privacy=True) startswith() response
            "privacy_url": "cm://0...b/15551234567",
        },
    ),
    (
        f"cm://Alerts@{TOKEN}/15551234567/15551234568",
        {
            # A sender name
            "instance": NotifyCM,
            "privacy_url": "cm://Alerts@0...b/15551234567/15551234568",
        },
    ),
    (
        f"cm://_/?token={TOKEN}&from=Alerts&to=15551234567,15551234568",
        {
            # Everything given as arguments
            "instance": NotifyCM,
            "privacy_url": "cm://Alerts@0...b/15551234567/15551234568",
        },
    ),
    (
        f"cm://{TOKEN}/15551234567?channels=WhatsApp,sms&batch=yes",
        {
            # Other channels and batch mode
            "instance": NotifyCM,
            "privacy_url": "cm://0...b/15551234567"
            "?channels=whatsapp%2Csms&batch=yes",
        },
    ),
    (
        f"cm://{TOKEN}/15551234567?channels=pigeon",
        {
            # An unknown channel
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        f"cm://{TOKEN}/15551234567/123",
        {
            # One bad phone number is dropped; the good one still works
            "instance": NotifyCM,
        },
    ),
    (
        f"cm://{TOKEN}/123",
        {
            # Nothing valid to notify
            "instance": NotifyCM,
            "notify_response": False,
        },
    ),
    (
        f"cm://{TOKEN}/15551234567",
        {
            "instance": NotifyCM,
            # throw a bizarre code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        f"cm://{TOKEN}/15551234567",
        {
            "instance": NotifyCM,
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        f"cm://{TOKEN}/15551234567",
        {
            "instance": NotifyCM,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracefully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def _mk_resp(content=OK_RESPONSE, code=requests.codes.ok):
    """Build a mock CM.com response."""
    r = mock.Mock()
    r.status_code = code
    r.content = content
    return r


def test_plugin_cm_urls():
    """NotifyCM() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


def test_plugin_cm_init():
    """NotifyCM() validates its token, sender, channels and targets."""

    # Bad Product Tokens are refused
    for token in (None, "", "  ", "abcd", TOKEN + "0"):
        with pytest.raises(AppriseImproperlyConfigured):
            NotifyCM(token=token)

    # Good and bad phone numbers are kept apart
    obj = NotifyCM(
        token=TOKEN,
        targets=["+1 (555) 123-4567", "123"],
        source=" Alerts ",
        channels="VIBER, sms, viber",
    )
    assert obj.targets == ["15551234567"]
    assert obj.invalid_targets == ["123"]
    assert obj.source == "Alerts"
    assert sorted(obj.channels) == ["sms", "viber"]
    assert obj.batch is False
    assert len(obj) == 1

    # A blank sender is the same as none, and SMS is the default channel
    obj = NotifyCM(token=TOKEN, source="  ")
    assert obj.source is None
    assert obj.channels == ["sms"]

    # No targets still counts as one notification
    assert len(obj) == 1

    # Batch mode counts requests rather than recipients
    obj = NotifyCM(token=TOKEN, targets=["15551234567"] * 1001, batch=True)
    assert len(obj) == 2


def test_plugin_cm_round_trip():
    """NotifyCM() url() reloads into the same object."""

    obj = NotifyCM(
        token=TOKEN,
        targets=["15551234567", "123"],
        source="Alerts",
        channels=["rcs"],
        batch=True,
    )
    url = obj.url()
    assert url.startswith(f"cm://Alerts@{TOKEN}/15551234567/123?")

    result = NotifyCM.parse_url(url)
    assert result["token"] == TOKEN
    obj2 = NotifyCM(**result)
    assert obj2.url_identifier == obj.url_identifier
    assert obj2.targets == obj.targets
    assert obj2.invalid_targets == obj.invalid_targets
    assert obj2.source == obj.source
    assert obj2.channels == obj.channels
    assert obj2.batch is True
    assert obj2.url() == url

    # Different targets and senders are still the same account
    assert (
        NotifyCM(token=TOKEN, targets="15550000000").url_identifier
        == obj.url_identifier
    )

    # A different token is a different account
    assert (
        NotifyCM(token=TOKEN.replace("0", "1")).url_identifier
        != obj.url_identifier
    )

    # Nothing to parse
    assert NotifyCM.parse_url(None) is None


@mock.patch("requests.post")
def test_plugin_cm_payload(mock_post):
    """NotifyCM() posts one message to each phone number."""

    mock_post.return_value = _mk_resp()
    obj = NotifyCM(
        token=TOKEN,
        targets=["15551234567", "15551234568"],
        channels="whatsapp,sms",
    )

    assert obj.notify(body="5 * 3 & <b>", title="T & <x>")
    assert mock_post.call_count == 2

    # The request goes to the global gateway
    url = mock_post.call_args_list[0][0][0]
    assert urlparse(url).hostname == "gw.messaging.cm.com"
    assert urlparse(url).path == "/v1.0/message"

    # The Product Token is sent in its own header
    headers = mock_post.call_args_list[0][1]["headers"]
    assert headers["X-CM-PRODUCTTOKEN"] == TOKEN

    # Each phone number gets its own copy, written as 00 + number
    first = json.loads(mock_post.call_args_list[0][1]["data"])
    second = json.loads(mock_post.call_args_list[1][1]["data"])
    msg = first["messages"]["msg"][0]
    assert msg["to"] == [{"number": "0015551234567"}]
    assert second["messages"]["msg"][0]["to"] == [{"number": "0015551234568"}]

    # Without a sender, Apprise names itself
    assert msg["from"] == "Apprise"

    # Channels use the API's own spelling
    assert sorted(msg["allowedChannels"]) == ["SMS", "WhatsApp"]

    # The title is placed in the body as typed
    assert msg["body"] == {
        "type": "auto",
        "content": "T & <x>\r\n5 * 3 & <b>",
    }
    assert msg["maximumNumberOfMessageParts"] == 8

    # A named sender is passed along
    mock_post.reset_mock()
    obj = NotifyCM(token=TOKEN, targets="15551234567", source="Alerts")
    assert obj.notify(body="body")
    payload = json.loads(mock_post.call_args[1]["data"])
    assert payload["messages"]["msg"][0]["from"] == "Alerts"


@mock.patch("requests.post")
def test_plugin_cm_batch(mock_post):
    """NotifyCM() groups recipients into batches when asked to."""

    mock_post.return_value = _mk_resp()
    obj = NotifyCM(
        token=TOKEN,
        targets=["15551234567", "15551234568", "15551234569"],
        batch=True,
    )

    with mock.patch.object(NotifyCM, "default_batch_size", 2):
        assert obj.notify(body="body")

    # Two numbers in the first request, one in the second
    assert mock_post.call_count == 2
    first = json.loads(mock_post.call_args_list[0][1]["data"])
    second = json.loads(mock_post.call_args_list[1][1]["data"])
    assert first["messages"]["msg"][0]["to"] == [
        {"number": "0015551234567"},
        {"number": "0015551234568"},
    ]
    assert second["messages"]["msg"][0]["to"] == [{"number": "0015551234569"}]


@mock.patch("requests.post")
def test_plugin_cm_responses(mock_post):
    """NotifyCM() reads the per-recipient results CM.com sends back."""

    obj = NotifyCM(
        token=TOKEN, targets=["15551234567", "15551234568"], batch=True
    )

    # Every recipient taken, reported one by one
    mock_post.return_value = _mk_resp(_result())
    assert obj.notify(body="body")

    # One recipient refused fails the notification
    mock_post.return_value = _mk_resp(_result("Gsm is not a number."))
    assert not obj.notify(body="body")

    # A partial result we can not read fails every recipient
    for content in (
        b'{"errorCode": 201}',
        b'{"errorCode": 201, "details": "x", "messages": "x"}',
        b'{"errorCode": 201, "messages": ["x"]}',
    ):
        mock_post.return_value = _mk_resp(content)
        assert not obj.notify(body="body")

    # Responses we can not read fall back to the HTTP status code
    for content in (None, b"", b"not json", b"[]"):
        mock_post.return_value = _mk_resp(content)
        assert obj.notify(body="body")

    # A refused request reports CM.com's reason when given one
    for content in (
        b'{"details": "No account found", "errorCode": 101}',
        None,
    ):
        mock_post.return_value = _mk_resp(content, requests.codes.bad_request)
        assert not obj.notify(body="body")


@mock.patch("requests.post")
def test_plugin_cm_retry(mock_post):
    """NotifyCM() only resends to the recipients CM.com refused."""

    mock_post.side_effect = (
        _mk_resp(_result("Gsm is not a number.")),
        _mk_resp(),
    )

    apobj = Apprise()
    assert apobj.add(f"cm://{TOKEN}/15551234567/15551234568?batch=yes&retry=1")
    with mock.patch("apprise.plugins.base.time.sleep"):
        assert apobj.notify(body="hello")

    # The retry carries only the refused number
    assert mock_post.call_count == 2
    retry = json.loads(mock_post.call_args_list[1][1]["data"])
    assert retry["messages"]["msg"][0]["to"] == [{"number": "0015551234567"}]

    # Sending one number at a time, the retry skips the one taken
    mock_post.reset_mock()
    mock_post.side_effect = (
        _mk_resp(),
        _mk_resp(None, requests.codes.bad_request),
        _mk_resp(),
    )

    apobj = Apprise()
    assert apobj.add(f"cm://{TOKEN}/15551234567/15551234568?retry=1")
    with mock.patch("apprise.plugins.base.time.sleep"):
        assert apobj.notify(body="hello")

    assert mock_post.call_count == 3
    retry = json.loads(mock_post.call_args_list[2][1]["data"])
    assert retry["messages"]["msg"][0]["to"] == [{"number": "0015551234568"}]


@mock.patch("requests.post")
def test_plugin_cm_apprise_integration(mock_post):
    """Apprise() loads and notifies a cm:// URL."""

    mock_post.return_value = _mk_resp()
    apobj = Apprise()
    assert apobj.add(f"cm://{TOKEN}/15551234567")
    assert apobj.notify(body="hello")
    assert mock_post.call_count == 1
