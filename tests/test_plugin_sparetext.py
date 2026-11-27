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

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise, NotifyType
from apprise.exception import AppriseImproperlyConfigured
from apprise.plugins.base import _delivery_tracker
from apprise.plugins.sparetext import NotifySparetext

logging.disable(logging.CRITICAL)

# A key in the format Sparetext hands out
APIKEY = "spt_live_" + "a" * 43

# A Device ID in the format Sparetext hands out
DEVICE = "dev_abcdefghjkmn"

# What Sparetext answers when it accepts a send
ACCEPTED = {
    "batchId": "b_abcdefghjkmn",
    "messages": [{"id": "msg_20261125_abcdefgh", "status": "queued"}],
    "estimatedCompletionAt": "2026-11-25T12:00:00.000Z",
}

# Our Testing URLs
apprise_url_tests = (
    (
        "sparetext://",
        {
            # No API Key
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "sparetext://:@/",
        {
            # invalid API Key
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "sparetext://12025550123?key=bad%20key",
        {
            # The API Key may not contain spaces
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        f"sparetext://{APIKEY}",
        {
            # No phone number to notify
            "instance": NotifySparetext,
            # Expected notify() response because we have no one to notify
            "notify_response": False,
        },
    ),
    (
        f"sparetext://{APIKEY}/abcd/123",
        {
            # Nothing that is a phone number; both are kept for url()
            "instance": NotifySparetext,
            "notify_response": False,
            "privacy_url": "sparetext://s...a/abcd/123",
        },
    ),
    (
        f"sparetext://{APIKEY}/+12025550123",
        {
            "instance": NotifySparetext,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "sparetext://s...a/+12025550123",
        },
    ),
    (
        f"sparetext://{APIKEY}/+12025550123/12025550124/abcd/",
        {
            # A garbage string (abcd) is dropped
            "instance": NotifySparetext,
            "privacy_url": "sparetext://s...a/+12025550123/12025550124/abcd",
        },
    ),
    (
        f"sparetext://12025550123?key={APIKEY}&to=+12025550124,12025550125",
        {
            # Use ?key= and ?to=; the host is a phone number then
            "instance": NotifySparetext,
            "privacy_url": (
                "sparetext://s...a/12025550123/+12025550124/12025550125"
            ),
        },
    ),
    (
        f"sparetext://?key={APIKEY}&to=+12025550123",
        {
            # No host at all
            "instance": NotifySparetext,
        },
    ),
    (
        f"sparetext://{APIKEY}/+12025550123?device={DEVICE}",
        {
            # Choose the phone that sends
            "instance": NotifySparetext,
            "privacy_url": (
                f"sparetext://s...a/+12025550123?batch=yes&device={DEVICE}"
            ),
        },
    ),
    (
        f"sparetext://{APIKEY}/+12025550123?device=bad%20id",
        {
            # A Device ID may not contain spaces
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        f"sparetext://{APIKEY}/+12025550123?server=http://127.0.0.1:8787/",
        {
            # Another Sparetext server, such as a local test server
            "instance": NotifySparetext,
            "privacy_url": (
                "sparetext://s...a/+12025550123?batch=yes"
                "&server=http%3A%2F%2F127.0.0.1%3A8787"
            ),
        },
    ),
    (
        f"sparetext://{APIKEY}/+12025550123?server=ftp://example.com",
        {
            # Only http and https servers
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        f"sparetext://{APIKEY}/+12025550123/+12025550124?batch=no",
        {
            # One request per phone number
            "instance": NotifySparetext,
            "privacy_url": (
                "sparetext://s...a/+12025550123/+12025550124?batch=no"
            ),
        },
    ),
    (
        f"sparetext://{APIKEY}/+12025550123",
        {
            "instance": NotifySparetext,
            # What Sparetext answers when it accepts a send
            "requests_response_code": requests.codes.accepted,
            "requests_response_text": ACCEPTED,
        },
    ),
    (
        f"sparetext://{APIKEY}/+12025550123",
        {
            "instance": NotifySparetext,
            # A JSON answer that is not an object is ignored
            "requests_response_code": requests.codes.accepted,
            "requests_response_text": ["unexpected"],
        },
    ),
    (
        f"sparetext://{APIKEY}/+12025550123",
        {
            "instance": NotifySparetext,
            # Sparetext refuses the key
            "response": False,
            "requests_response_code": requests.codes.unauthorized,
            "requests_response_text": {
                "error": {
                    "code": "unauthorized",
                    "message": "Sign in or send an API key.",
                },
            },
        },
    ),
    (
        f"sparetext://{APIKEY}/+12025550123",
        {
            "instance": NotifySparetext,
            # throw a bizarre code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        f"sparetext://{APIKEY}/+12025550123",
        {
            "instance": NotifySparetext,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracefully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_sparetext_urls():
    """NotifySparetext() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.post")
def test_plugin_sparetext_edge_cases(mock_post):
    """NotifySparetext() Edge Cases."""

    # Prepare our response
    response = requests.Request()
    response.status_code = requests.codes.accepted
    response.content = dumps(ACCEPTED)

    # Prepare Mock
    mock_post.return_value = response

    targets = [
        "+1(202) 555-0123",
        "1202 5550124",
        # A garbage entry
        "12",
    ]

    # Instantiate our object
    obj = Apprise.instantiate(
        "sparetext://{}/{}?device={}".format(APIKEY, "/".join(targets), DEVICE)
    )
    assert isinstance(obj, NotifySparetext)

    # Both phone numbers go in one request
    assert len(obj) == 1

    assert (
        bool(
            obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        )
        is True
    )

    # One request carried both phone numbers
    assert mock_post.call_count == 1

    details = mock_post.call_args_list[0]
    assert details[0][0] == "https://sparetext.dev/api/v1/messages"
    assert details[1]["headers"]["x-api-key"] == APIKEY
    assert details[1]["headers"]["Content-Type"] == "application/json"
    payload = loads(details[1]["data"])
    assert payload == {
        # The number written with its + keeps it; the other is left for
        # Sparetext to read in the account's country
        "to": ["+12025550123", "12025550124"],
        "text": "title\r\nbody",
        "deviceId": DEVICE,
    }

    # Verify our URL looks good
    assert obj.url().startswith(
        f"sparetext://{APIKEY}/+12025550123/12025550124/12"
        f"?batch=yes&device={DEVICE}"
    )

    # The phone is only named when one was asked for
    mock_post.reset_mock()
    obj = Apprise.instantiate(f"sparetext://{APIKEY}/+12025550123")
    assert obj.notify(body="body") is True
    assert mock_post.call_count == 1
    payload = loads(mock_post.call_args_list[0][1]["data"])
    assert payload == {"to": ["+12025550123"], "text": "body"}

    # Another server
    mock_post.reset_mock()
    obj = Apprise.instantiate(
        f"sparetext://{APIKEY}/+12025550123"
        "?server=https://staging.example.com/"
    )
    assert obj.server == "https://staging.example.com"
    assert obj.notify(body="body") is True
    assert (
        mock_post.call_args_list[0][0][0]
        == "https://staging.example.com/api/v1/messages"
    )

    # The default server is not written into the URL
    obj = NotifySparetext(
        apikey=APIKEY, targets="+12025550123", server="https://sparetext.dev/"
    )
    assert obj.server == "https://sparetext.dev"
    assert "server=" not in obj.url()


@mock.patch("requests.post")
def test_plugin_sparetext_batches(mock_post):
    """NotifySparetext() Batches of phone numbers."""

    # Prepare our response
    response = requests.Request()
    response.status_code = requests.codes.accepted
    response.content = dumps(ACCEPTED)
    mock_post.return_value = response

    # 150 phone numbers
    targets = [f"+1202555{n:04d}" for n in range(150)]

    # Up to 100 phone numbers go in one request
    obj = NotifySparetext(apikey=APIKEY, targets=targets)
    obj.request_rate_per_sec = 0
    assert len(obj) == 2
    assert obj.notify(body="body") is True
    assert mock_post.call_count == 2
    first = loads(mock_post.call_args_list[0][1]["data"])
    second = loads(mock_post.call_args_list[1][1]["data"])
    assert first["to"] == targets[:100]
    assert second["to"] == targets[100:]

    # One request per phone number
    mock_post.reset_mock()
    obj = NotifySparetext(apikey=APIKEY, targets=targets[:3], batch=False)
    obj.request_rate_per_sec = 0
    assert len(obj) == 3
    assert obj.notify(body="body") is True
    assert mock_post.call_count == 3
    for index, call in enumerate(mock_post.call_args_list):
        assert loads(call[1]["data"])["to"] == [targets[index]]

    # A retry skips the batch that already went out
    mock_post.reset_mock()
    obj = NotifySparetext(apikey=APIKEY, targets=targets)
    obj.request_rate_per_sec = 0
    refused = requests.Request()
    refused.status_code = requests.codes.service_unavailable
    refused.content = b""
    refused.headers = {}
    mock_post.side_effect = [response, refused]

    token = _delivery_tracker.set(set())
    try:
        assert obj.notify(body="body") is False
        assert mock_post.call_count == 2

        mock_post.reset_mock()
        mock_post.side_effect = None
        assert obj.notify(body="body") is True

        # Only the second batch was sent again
        assert mock_post.call_count == 1
        payload = loads(mock_post.call_args_list[0][1]["data"])
        assert payload["to"] == targets[100:]

    finally:
        _delivery_tracker.reset(token)


def test_plugin_sparetext_phone_numbers():
    """NotifySparetext() Phone number handling."""

    # A number written with its + keeps it, and so does one written with
    # 00; Sparetext reads the rest in the account's country
    obj = NotifySparetext(
        apikey=APIKEY,
        targets=["+44 7700 900124", "0044 7700 900125", "(202) 555-0123"],
    )
    assert obj.targets == ["+447700900124", "00447700900125", "2025550123"]
    assert obj.invalid_targets == []

    # Anything that is not a phone number is dropped, but kept for url()
    obj = NotifySparetext(apikey=APIKEY, targets=["12", "abcd"])
    assert obj.targets == []
    assert obj.invalid_targets == ["12", "abcd"]
    assert len(obj) == 1

    # A blank Device ID or server is treated as unset
    obj = NotifySparetext(
        apikey=APIKEY, targets="+12025550123", device="  ", server="  "
    )
    assert obj.device is None
    assert obj.server == "https://sparetext.dev"
    assert obj.batch is True
    assert "device=" not in obj.url()
    assert "server=" not in obj.url()

    # A missing API Key
    with pytest.raises(AppriseImproperlyConfigured):
        NotifySparetext(apikey=None, targets="+12025550123")

    # A bad server
    for server in ("sparetext.dev", "https://", "https://a b", "https://u@x"):
        with pytest.raises(AppriseImproperlyConfigured):
            NotifySparetext(
                apikey=APIKEY, targets="+12025550123", server=server
            )

    # The URL we build loads back into the same targets
    obj = NotifySparetext(
        apikey=APIKEY,
        targets=["+12025550123", "2025550124", "abcd"],
        device=DEVICE,
        batch=False,
        server="http://127.0.0.1:8787",
    )
    clone = Apprise.instantiate(obj.url())
    assert clone.targets == obj.targets == ["+12025550123", "2025550124"]
    assert clone.invalid_targets == obj.invalid_targets == ["abcd"]
    assert clone.device == DEVICE
    assert clone.batch is False
    assert clone.server == "http://127.0.0.1:8787"
    assert clone.url_identifier == obj.url_identifier

    # The phone that sends and the server are part of what identifies us
    one = NotifySparetext(apikey=APIKEY, targets="+12025550123")
    two = NotifySparetext(apikey=APIKEY, targets="+12025550123", device=DEVICE)
    three = NotifySparetext(
        apikey=APIKEY, targets="+12025550123", server="http://127.0.0.1:8787"
    )
    assert one.url_identifier != two.url_identifier
    assert one.url_identifier != three.url_identifier
    assert one.url_id() != two.url_id()


def test_plugin_sparetext_sms_parts():
    """NotifySparetext() SMS parts and their encoding."""

    # The GSM-7 alphabet fits 160 characters in one part
    assert NotifySparetext.sms_parts("a" * 160) == ("GSM-7", 1, [])
    assert NotifySparetext.sms_parts("a" * 161) == ("GSM-7", 2, [])
    assert NotifySparetext.sms_parts("a" * 307) == ("GSM-7", 3, [])

    # Its extension table takes the room of two
    assert NotifySparetext.sms_parts("€" * 80) == ("GSM-7", 1, [])
    assert NotifySparetext.sms_parts("€" * 81) == ("GSM-7", 2, [])

    # A title joins the body with a line break, which is in GSM-7
    assert NotifySparetext.sms_parts("title\r\nbody") == ("GSM-7", 1, [])

    # One emoji makes it UCS-2: 70 in one part, 67 a part once split, and
    # the emoji itself takes two
    assert NotifySparetext.sms_parts("é" * 70) == ("GSM-7", 1, [])
    assert NotifySparetext.sms_parts("ā" * 70) == ("UCS-2", 1, ["ā"] * 70)
    assert NotifySparetext.sms_parts("ā" * 71) == ("UCS-2", 2, ["ā"] * 71)
    assert NotifySparetext.sms_parts("\U0001f534" + "a" * 68) == (
        "UCS-2",
        1,
        ["\U0001f534"],
    )
    assert NotifySparetext.sms_parts("\U0001f534" + "a" * 69) == (
        "UCS-2",
        2,
        ["\U0001f534"],
    )


@mock.patch("requests.post")
def test_plugin_sparetext_logging(mock_post):
    """NotifySparetext() What is logged about a send."""

    response = requests.Request()
    response.status_code = requests.codes.accepted
    response.content = dumps(ACCEPTED)
    mock_post.return_value = response

    obj = NotifySparetext(apikey=APIKEY, targets="+12025550123")

    # The encoding and the number of parts are told
    with mock.patch.object(obj.logger, "debug") as mock_debug:
        assert obj.notify(body="[\U0001f534 Down] example.com") is True

    lines = [call[0][0] % call[0][1:] for call in mock_debug.call_args_list]
    assert "Sparetext text is UCS-2 because of \U0001f534: 1 part(s)." in lines
    assert (
        "Sparetext batch b_abcdefghjkmn; the last text is expected to go out"
        " by 2026-11-25T12:00:00.000Z." in lines
    )

    with mock.patch.object(obj.logger, "debug") as mock_debug:
        assert obj.notify(body="[Down] example.com") is True

    lines = [call[0][0] % call[0][1:] for call in mock_debug.call_args_list]
    assert "Sparetext text is GSM-7: 1 part(s)." in lines

    # Without a batch id, there is nothing to tell about it
    response.content = dumps({"messages": []})
    with mock.patch.object(obj.logger, "debug") as mock_debug:
        assert obj.notify(body="body") is True

    lines = [call[0][0] % call[0][1:] for call in mock_debug.call_args_list]
    assert not [line for line in lines if line.startswith("Sparetext batch")]

    # Nor of when it finishes when Sparetext can not tell (tap to send)
    response.content = dumps({"batchId": "b_abcd", "messages": []})
    with mock.patch.object(obj.logger, "debug") as mock_debug:
        assert obj.notify(body="body") is True

    lines = [call[0][0] % call[0][1:] for call in mock_debug.call_args_list]
    assert (
        "Sparetext batch b_abcd; the last text is expected to go out by"
        " (unknown)." in lines
    )


@mock.patch("requests.post")
def test_plugin_sparetext_skipped(mock_post):
    """NotifySparetext() Phone numbers Sparetext did not text."""

    response = requests.Request()
    response.status_code = requests.codes.accepted
    response.content = dumps(
        {
            **ACCEPTED,
            "skipped": [
                {
                    "to": "+12025550124",
                    "reason": "opted_out",
                    "optedOutAt": "2026-11-01T10:00:00.000Z",
                },
                {"to": "+12025550125", "reason": "something_new"},
                {"to": "+12025550126"},
                # Entries we can not read are ignored
                {"reason": "opted_out"},
                "+12025550127",
            ],
        }
    )
    mock_post.return_value = response

    obj = NotifySparetext(
        apikey=APIKEY,
        targets=["2025550123", "+12025550124", "+12025550125"],
    )

    # The others got the text, so the notification went out
    with mock.patch.object(obj.logger, "warning") as mock_warning:
        assert obj.notify(body="body") is True

    lines = [call[0][0] % call[0][1:] for call in mock_warning.call_args_list]
    assert lines == [
        "Sparetext did not text +12025550124: it is on your opt-out list.",
        "Sparetext did not text +12025550125: something_new.",
        "Sparetext did not text +12025550126: skipped.",
    ]

    # Only the numbers Sparetext queued a text for are named as sent, as
    # Sparetext wrote them, each once
    response.content = dumps(
        {
            **ACCEPTED,
            "messages": [
                {"id": "msg_20261125_aaaaaaaa", "contact": "+12025550123"},
                {"id": "msg_20261125_bbbbbbbb", "contact": "+12025550123"},
                # Entries we can not read are ignored
                {"id": "msg_20261125_cccccccc"},
                "msg_20261125_dddddddd",
            ],
            "skipped": [{"to": "+12025550124", "reason": "opted_out"}],
        }
    )
    with mock.patch.object(obj.logger, "info") as mock_info:
        assert obj.notify(body="body") is True

    lines = [call[0][0] % call[0][1:] for call in mock_info.call_args_list]
    assert "Sent Sparetext notification to +12025550123." in lines

    # Without that list, the numbers we sent are named
    response.content = dumps({**ACCEPTED, "messages": "unexpected"})
    with mock.patch.object(obj.logger, "info") as mock_info:
        assert obj.notify(body="body") is True

    lines = [call[0][0] % call[0][1:] for call in mock_info.call_args_list]
    assert (
        "Sent Sparetext notification to 2025550123, +12025550124,"
        " +12025550125." in lines
    )

    # A list we can not read is ignored too
    response.content = dumps({**ACCEPTED, "skipped": "everyone"})
    with mock.patch.object(obj.logger, "warning") as mock_warning:
        assert obj.notify(body="body") is True

    assert mock_warning.call_count == 0


@mock.patch("requests.post")
def test_plugin_sparetext_errors(mock_post):
    """NotifySparetext() Error reporting."""

    obj = NotifySparetext(
        apikey=APIKEY, targets=["+12025550123", "12025550124"], batch=False
    )

    # No delays between our requests
    obj.request_rate_per_sec = 0

    def answer(status_code, content, headers=None):
        """Prepare the response Sparetext gives."""
        response = requests.Request()
        response.status_code = status_code
        response.content = content
        response.headers = headers or {}
        mock_post.return_value = response

    def warning():
        """Send and return the warning logged about the failure."""
        mock_post.reset_mock()
        with mock.patch.object(obj.logger, "warning") as mock_warning:
            assert obj.notify(body="body") is False

        # Each phone number was tried and reported on its own
        assert mock_post.call_count == 2
        assert mock_warning.call_count == 2
        return mock_warning.call_args_list[0][0]

    # Sparetext explains what went wrong; we keep its words
    answer(
        requests.codes.conflict,
        dumps(
            {
                "error": {
                    "code": "opted_out",
                    "message": "+12025550123 opted out (replied STOP or a "
                    "word like it) on 2026-11-01 UTC, so Sparetext won't "
                    "text them. If they reply START, you can text them "
                    "again.",
                }
            }
        ),
    )
    args = warning()
    assert args[1] == "+12025550123"
    assert args[2].startswith("+12025550123 opted out")
    assert args[4] == 409

    # A bad API Key
    answer(
        requests.codes.unauthorized,
        dumps(
            {
                "error": {
                    "code": "unauthorized",
                    "message": "This API key was revoked.",
                }
            }
        ),
    )
    args = warning()

    # Its closing full stop is left out, as ", error=401" follows it
    assert args[2] == "This API key was revoked"

    # An error without an explanation falls back to the status code
    answer(requests.codes.forbidden, dumps({"error": {"code": "forbidden"}}))
    args = warning()
    assert args[2] == (
        "Forbidden - The API Key is not allowed to send this text."
    )

    answer(requests.codes.bad_request, dumps({"error": "unexpected"}))
    args = warning()
    assert args[2] == "Bad Request - Check the phone numbers and the message."

    # Too many requests, without a JSON body; how long to wait is told
    answer(
        requests.codes.too_many_requests,
        b"Too Many Requests",
        {"Retry-After": "3"},
    )
    with mock.patch.object(obj.logger, "debug") as mock_debug:
        args = warning()

    assert args[2] == "Too many requests were made; try again later."
    assert args[4] == 429
    lines = [call[0][0] % call[0][1:] for call in mock_debug.call_args_list]
    assert "Sparetext asked to retry after 3 second(s)." in lines

    # Sparetext is busy and gave no body at all
    answer(requests.codes.service_unavailable, None)
    args = warning()
    assert args[2] == "Sparetext is busy; try again later."
