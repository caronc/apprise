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
import threading
from unittest import mock
from urllib.parse import urlparse

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise, NotifyType
from apprise.exception import AppriseImproperlyConfigured
from apprise.plugins.mobilemessage import NotifyMobileMessage

logging.disable(logging.CRITICAL)


def _ok(count=1):
    """Build the all-accepted report returned for `count` recipients."""
    return {
        "status": "complete",
        "results": [
            {"to": f"614000000{index:02d}", "status": "success"}
            for index in range(count)
        ],
    }


# Our Testing URLs
apprise_url_tests = (
    (
        "mobilemessage://",
        {
            # No credentials at all
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "mobilemessage://:@/",
        {
            # No credentials at all
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "mobilemessage://user@ALERTS/0412345678",
        {
            # No API password provided
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "mobilemessage://user:pass@/0412345678",
        {
            # No Sender ID provided
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "mobilemessage://user:pass@%20/0412345678",
        {
            # A Sender ID of nothing but whitespace
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "mobilemessage://user:pass@ALERTS/",
        {
            # No targets to notify
            "instance": NotifyMobileMessage,
            "requests_response_text": _ok(),
            "notify_response": False,
        },
    ),
    (
        "mobilemessage://user:pass@ALERTS/0412345678",
        {
            "instance": NotifyMobileMessage,
            "requests_response_text": _ok(),
            "privacy_url": "mobilemessage://user:****@ALERTS/61412345678",
        },
    ),
    (
        "mobilemsg://user:pass@ALERTS/0412345678",
        {
            # The shorthand schema normalises back to the full one
            "instance": NotifyMobileMessage,
            "requests_response_text": _ok(),
            "privacy_url": "mobilemessage://user:****@ALERTS/61412345678",
        },
    ),
    (
        "mobilemessage://user:pass@+61 400 000 000/61412345678",
        {
            # A phone number Sender ID is reduced to digits
            "instance": NotifyMobileMessage,
            "requests_response_text": _ok(),
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
            "requests_response_text": _ok(3),
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
            "requests_response_text": _ok(),
            "privacy_url": "mobilemessage://user:****@ALERTS/61412345678",
        },
    ),
    (
        "mobilemessage://user:pass@ALERTS/15551231234",
        {
            # Nothing is left to notify once the US number is dropped
            "instance": NotifyMobileMessage,
            "requests_response_text": _ok(),
            "notify_response": False,
        },
    ),
    (
        "mobilemessage://user:pass@ALERTS/0412345678?max_parts=invalid",
        {
            # max_parts must be a number
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "mobilemessage://user:pass@ALERTS/0412345678?max_parts=0",
        {
            # max_parts is below the accepted range
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "mobilemessage://user:pass@ALERTS/0412345678?max_parts=100",
        {
            # max_parts is above the accepted range
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "mobilemessage://user:pass@ALERTS/0412345678"
        "?unicode=yes&batch=no&max_parts=2&ref=nightly",
        {
            # Every option at once
            "instance": NotifyMobileMessage,
            "requests_response_text": _ok(),
            "privacy_url": "mobilemessage://user:****@ALERTS/61412345678",
        },
    ),
    (
        "mobilemessage://user:pass@0412345678/?from=ALERTS",
        {
            # With from=, the hostname becomes a target
            "instance": NotifyMobileMessage,
            "requests_response_text": _ok(),
            "privacy_url": "mobilemessage://user:****@ALERTS/61412345678",
        },
    ),
    (
        "mobilemessage://user:pass@ALERTS/?to=0412345678,0498765432",
        {
            "instance": NotifyMobileMessage,
            "requests_response_text": _ok(2),
            "privacy_url": (
                "mobilemessage://user:****@ALERTS/61412345678/61498765432"
            ),
        },
    ),
    (
        "mobilemessage://user:pass@ALERTS/0412345678",
        {
            "instance": NotifyMobileMessage,
            "requests_response_text": _ok(),
            # A failure from the upstream server
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "mobilemessage://user:pass@ALERTS/0412345678",
        {
            "instance": NotifyMobileMessage,
            "requests_response_text": _ok(),
            # An unknown status code has no mapped description
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "mobilemessage://user:pass@ALERTS/0412345678",
        {
            "instance": NotifyMobileMessage,
            "requests_response_text": _ok(),
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
    with pytest.raises(AppriseImproperlyConfigured):
        NotifyMobileMessage(source="ALERTS", targets="0412345678")

    with pytest.raises(AppriseImproperlyConfigured):
        NotifyMobileMessage(user="user", source="ALERTS", targets="0412345678")

    # A Sender ID is mandatory
    with pytest.raises(AppriseImproperlyConfigured):
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
    with pytest.raises(AppriseImproperlyConfigured):
        NotifyMobileMessage(
            user="user",
            password="pass",
            source="ALERTS",
            targets="0412345678",
            max_parts="invalid",
        )

    # Below and above the accepted range
    for value in (0, 100):
        with pytest.raises(AppriseImproperlyConfigured):
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

    mock_post.return_value = _mk_resp(_ok(2))

    # Batch mode is on by default, so both recipients share one request
    obj = Apprise.instantiate(
        "mobilemessage://user:pass@ALERTS/0412345678/0498765432"
    )
    assert obj.notify(body="body") is True
    assert mock_post.call_count == 1

    payload = loads(mock_post.call_args_list[0][1]["data"])
    assert len(payload["messages"]) == 2

    # Turning batch mode off gives each recipient its own request, so each
    # response reports on just the one it carried
    mock_post.reset_mock()
    mock_post.return_value = _mk_resp(_ok(1))
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
            "status": "complete",
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
            "status": "complete",
            "results": [
                {"to": "61412345678", "status": "success"},
                {"status": "error"},
            ],
        }
    )
    assert obj.notify(body="body") is False

    # An entry we can not read confirms nothing, so it counts as refused
    mock_post.return_value = _mk_resp(
        {
            "status": "complete",
            "results": [
                {"to": "61412345678", "status": "success"},
                "unexpected",
            ],
        }
    )
    assert obj.notify(body="body") is False

    # Every recipient accepted
    mock_post.return_value = _mk_resp(_ok(2))
    assert obj.notify(body="body") is True


@mock.patch("apprise.plugins.base.time.sleep")
@mock.patch("requests.post")
def test_plugin_mobilemessage_timeout_reuses_key(mock_post, mock_sleep):
    """A resend after a timeout carries the key of the attempt that hung."""

    # Nothing comes back from the first attempt, so there is no way to know
    # whether the service took the batch or not
    mock_post.side_effect = [
        requests.ConnectionError("timed out"),
        _mk_resp(_ok(2)),
    ]

    aobj = Apprise()
    assert aobj.add(
        "mobilemessage://user:pass@ALERTS/0412345678/0498765432?retry=1&wait=0"
    )
    assert bool(aobj.notify(body="body")) is True
    assert mock_post.call_count == 2

    keys = [
        call[1]["headers"]["Idempotency-Key"]
        for call in mock_post.call_args_list
    ]

    # Same key, so the service recognises the resend and only charges once
    assert keys[0] == keys[1]

    # The same content in a fresh notification still needs a fresh key.
    mock_post.reset_mock()
    mock_post.side_effect = None
    mock_post.return_value = _mk_resp(_ok(2))
    assert bool(aobj.notify(body="body")) is True
    assert (
        mock_post.call_args_list[0][1]["headers"]["Idempotency-Key"]
        not in keys
    )


@mock.patch("apprise.plugins.base.time.sleep")
@mock.patch("requests.post")
def test_plugin_mobilemessage_server_error_key(mock_post, mock_sleep):
    """A retry after a server error carries the key that produced it."""

    # A 5xx leaves it unclear whether the batch was processed at all
    mock_post.side_effect = [
        _mk_resp({}, code=requests.codes.internal_server_error),
        _mk_resp(_ok(2)),
    ]

    aobj = Apprise()
    assert aobj.add(
        "mobilemessage://user:pass@ALERTS/0412345678/0498765432?retry=1&wait=0"
    )
    assert bool(aobj.notify(body="body")) is True
    assert mock_post.call_count == 2

    keys = [
        call[1]["headers"]["Idempotency-Key"]
        for call in mock_post.call_args_list
    ]
    assert keys[0] == keys[1]


@mock.patch("requests.post")
def test_plugin_mobilemessage_key_not_inherited(mock_post):
    """A later notification never picks up a key left by an earlier one."""

    # Retries are off, so the first send has no second attempt to hand its
    # key to.  Leaving it behind would have the service answer the next
    # alert from its cache instead of sending it.
    mock_post.side_effect = [
        requests.ConnectionError("timed out"),
        _mk_resp(_ok()),
    ]

    aobj = Apprise()
    assert aobj.add("mobilemessage://user:pass@ALERTS/0412345678")
    assert bool(aobj.notify(body="Disk full")) is False
    assert bool(aobj.notify(body="Disk full")) is True

    keys = [
        call[1]["headers"]["Idempotency-Key"]
        for call in mock_post.call_args_list
    ]
    assert keys[0] != keys[1]


@mock.patch("apprise.plugins.base.time.sleep")
@mock.patch("requests.post")
def test_plugin_mobilemessage_key_expires(mock_post, mock_sleep):
    """A used up retry chain does not lend its key to the next alert."""

    # Both attempts hang, then a separate notification sends the same text
    mock_post.side_effect = [
        requests.ConnectionError("timed out"),
        requests.ConnectionError("timed out"),
        _mk_resp(_ok()),
    ]

    aobj = Apprise()
    assert aobj.add(
        "mobilemessage://user:pass@ALERTS/0412345678?retry=1&wait=0"
    )
    assert bool(aobj.notify(body="Disk full")) is False
    assert bool(aobj.notify(body="Disk full")) is True

    keys = [
        call[1]["headers"]["Idempotency-Key"]
        for call in mock_post.call_args_list
    ]

    # Shared by the two attempts of the first notification ...
    assert keys[0] == keys[1]

    # ... and not by the notification that followed it
    assert keys[2] != keys[0]


@mock.patch("requests.post")
def test_plugin_mobilemessage_overlapping_keys(mock_post):
    """Two notifications in flight at once each get their own key."""

    aobj = Apprise()
    assert aobj.add("mobilemessage://user:pass@ALERTS/0412345678")

    # Send the same text again from inside the first send's own request,
    # so the two notifications genuinely overlap on one plugin instance
    def handler(*args, **kwargs):
        if mock_post.call_count == 1:
            aobj.notify(body="Disk full")

        return _mk_resp(_ok())

    mock_post.side_effect = handler
    assert bool(aobj.notify(body="Disk full")) is True
    assert mock_post.call_count == 2

    keys = [
        call[1]["headers"]["Idempotency-Key"]
        for call in mock_post.call_args_list
    ]
    assert keys[0] != keys[1]


@mock.patch("apprise.plugins.base.time.sleep")
@mock.patch("requests.post")
def test_plugin_mobilemessage_identical_pieces(mock_post, mock_sleep):
    """Two pieces of one message never share a key, alike or not.

    A long body splits into pieces that can come out byte for byte the
    same. Each is still its own request, so handing the second the
    first's key would have the service replay it and never deliver.
    """

    def handler(*args, **kwargs):
        sent = loads(kwargs["data"])["messages"]
        return _mk_resp(
            {
                "status": "complete",
                "results": [{"status": "success"}] * len(sent),
            }
        )

    mock_post.side_effect = handler

    aobj = Apprise()
    assert aobj.add(
        "mobilemessage://user:pass@ALERTS/0412345678"
        "?overflow=split&retry=1&wait=0"
    )

    # Splits into two pieces holding exactly the same text
    assert bool(aobj.notify(body="A" * 3060)) is True
    assert mock_post.call_count == 2

    pieces = [
        loads(call[1]["data"])["messages"][0]["message"]
        for call in mock_post.call_args_list
    ]
    assert pieces[0] == pieces[1]

    keys = [
        call[1]["headers"]["Idempotency-Key"]
        for call in mock_post.call_args_list
    ]
    assert keys[0] != keys[1]


@mock.patch("apprise.dispatch.time.sleep")
@mock.patch("apprise.plugins.base.time.sleep")
@mock.patch("requests.post")
def test_plugin_mobilemessage_piece_retry_key(
    mock_post, mock_sleep, mock_wait
):
    """A piece that has to be resent still carries its own first key."""

    calls = []

    def handler(*args, **kwargs):
        # The two pieces are told apart by the character they end on
        message = loads(kwargs["data"])["messages"][0]["message"]
        calls.append((message[-1], kwargs["headers"]["Idempotency-Key"]))

        if len(calls) == 1:
            # The opening piece hangs and has to be sent again
            raise requests.ConnectionError("timed out")

        return _mk_resp(
            {
                "status": "complete",
                "results": [{"status": "success"}],
            }
        )

    mock_post.side_effect = handler

    aobj = Apprise()
    assert aobj.add(
        "mobilemessage://user:pass@ALERTS/0412345678"
        "?overflow=split&retry=1&wait=0"
    )
    aobj.notify(body="A" * 2000 + "B" * 1060)

    # The first piece, the second piece, then the first one again
    assert [tail for tail, _ in calls] == ["A", "B", "A"]

    # The resent piece carries the key it opened with
    assert calls[0][1] == calls[2][1]

    # The piece that got through has its own
    assert calls[1][1] != calls[0][1]


@mock.patch("apprise.plugins.base.time.sleep")
@mock.patch("requests.post")
def test_plugin_mobilemessage_concurrent_keys(mock_post, mock_sleep):
    """Parallel notifications keep separate keys across their retries."""

    aobj = Apprise()
    assert aobj.add(
        "mobilemessage://user:pass@ALERTS/0412345678?retry=1&wait=0"
    )

    seen = set()
    guard = threading.Lock()
    keys = []

    def handler(*args, **kwargs):
        key = kwargs["headers"]["Idempotency-Key"]
        with guard:
            keys.append(key)
            opening = key not in seen
            seen.add(key)

        if opening:
            # Every chain's first attempt hangs, whichever order they
            # happen to run in
            raise requests.ConnectionError("first attempt hangs")

        return _mk_resp(_ok())

    mock_post.side_effect = handler

    threads = [
        threading.Thread(target=aobj.notify, kwargs={"body": "Disk full"})
        for _ in range(2)
    ]
    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join(timeout=30)
        assert not thread.is_alive()

    # Two chains, each of which retried once
    assert len(keys) == 4

    # A key of their own, and each one used by both of its attempts.
    # Order is left alone; the threads may interleave any way they like.
    assert len(set(keys)) == 2
    assert all(keys.count(key) == 2 for key in set(keys))


@mock.patch("apprise.plugins.base.time.sleep")
@mock.patch("requests.post")
def test_plugin_mobilemessage_overlapping_chains(mock_post, mock_sleep):
    """An overlapping notification cannot take another's key away."""

    aobj = Apprise()
    assert aobj.add(
        "mobilemessage://user:pass@ALERTS/0412345678?retry=1&wait=0"
    )

    # While the first request is open, an identical notification runs to
    # completion on the same instance.  Its key is its own, and clearing it
    # must not disturb the one the first notification is still relying on.
    def handler(*args, **kwargs):
        if mock_post.call_count == 1:
            aobj.notify(body="Disk full")
            raise requests.ConnectionError("first request hangs")

        return _mk_resp(_ok())

    mock_post.side_effect = handler
    aobj.notify(body="Disk full")

    keys = [
        call[1]["headers"]["Idempotency-Key"]
        for call in mock_post.call_args_list
    ]

    # First attempt, the overlapping notification, then the first's retry
    assert len(keys) == 3
    assert keys[0] != keys[1]
    assert keys[2] == keys[0]


@mock.patch("apprise.plugins.base.time.sleep")
@mock.patch("requests.post")
def test_plugin_mobilemessage_batch_boundaries(mock_post, mock_sleep):
    """A batch whose outcome is unknown is resent exactly as it was."""

    # Two batches of one.  The first is answered and taken, the second
    # never comes back, so only the second should go out again -- and it
    # has to look identical, key included, or the resend is charged twice.
    mock_post.side_effect = [
        _mk_resp(
            {
                "status": "complete",
                "results": [{"to": "61412345678", "status": "success"}],
            }
        ),
        requests.ConnectionError("timed out"),
        _mk_resp(
            {
                "status": "complete",
                "results": [{"to": "61498765432", "status": "success"}],
            }
        ),
    ]

    aobj = Apprise()
    assert aobj.add(
        "mobilemessage://user:pass@ALERTS/0412345678/0498765432"
        "?batch=no&retry=1&wait=0"
    )
    assert bool(aobj.notify(body="body")) is True

    # The recipient that was taken is not contacted again
    assert mock_post.call_count == 3
    sent = [
        [entry["to"] for entry in loads(call[1]["data"])["messages"]]
        for call in mock_post.call_args_list
    ]
    assert sent == [["61412345678"], ["61498765432"], ["61498765432"]]

    # The resend of the unanswered batch carries its original key
    keys = [
        call[1]["headers"]["Idempotency-Key"]
        for call in mock_post.call_args_list
    ]
    assert keys[1] == keys[2]
    assert keys[0] != keys[1]


@mock.patch("apprise.plugins.base.time.sleep")
@mock.patch("requests.post")
def test_plugin_mobilemessage_unreadable_ok_key(mock_post, mock_sleep):
    """A 200 we cannot read keeps its key, because nothing is settled."""

    # A valid answer accounts for every message; this one accounts for
    # none, so there is no telling what the service did with the batch
    unreadable = mock.Mock()
    unreadable.status_code = requests.codes.ok
    unreadable.content = b"<html>not json</html>"

    mock_post.side_effect = [unreadable, _mk_resp(_ok(2))]

    aobj = Apprise()
    assert aobj.add(
        "mobilemessage://user:pass@ALERTS/0412345678/0498765432?retry=1&wait=0"
    )
    assert bool(aobj.notify(body="body")) is True
    assert mock_post.call_count == 2

    keys = [
        call[1]["headers"]["Idempotency-Key"]
        for call in mock_post.call_args_list
    ]
    assert keys[0] == keys[1]


@mock.patch("requests.post")
def test_plugin_mobilemessage_key_per_notification(mock_post):
    """Each notification sends under a key of its very own."""

    obj = Apprise.instantiate("mobilemessage://user:pass@ALERTS/0412345678")

    # The outcome of the first send makes no difference here
    mock_post.return_value = _mk_resp(
        {"error": "Unauthorized"}, code=requests.codes.unauthorized
    )
    assert obj.notify(body="body") is False

    # The same text going out again is a new message, not a repeat
    mock_post.return_value = _mk_resp(_ok())
    assert obj.notify(body="body") is True

    keys = [
        call[1]["headers"]["Idempotency-Key"]
        for call in mock_post.call_args_list
    ]
    assert keys[0] != keys[1]


@mock.patch("apprise.plugins.base.time.sleep")
@mock.patch("requests.post")
def test_plugin_mobilemessage_retry_skips_accepted(mock_post, mock_sleep):
    """A retry carries only the recipients the service has not taken."""

    # The first attempt gets one recipient through and has the other
    # refused; the retry should then be left with just the refused one.
    mock_post.side_effect = [
        _mk_resp(
            {
                "status": "complete",
                "results": [
                    {"to": "61412345678", "status": "success"},
                    {
                        "to": "61498765432",
                        "status": "blocked",
                        "error": "Recipient has unsubscribed",
                    },
                ],
            }
        ),
        _mk_resp(
            {
                "status": "complete",
                "results": [{"to": "61498765432", "status": "blocked"}],
            }
        ),
    ]

    aobj = Apprise()
    assert aobj.add(
        "mobilemessage://user:pass@ALERTS/0412345678/0498765432?retry=1&wait=0"
    )
    assert bool(aobj.notify(body="body")) is False

    # Both attempts were made
    assert mock_post.call_count == 2

    def recipients(call):
        return [entry["to"] for entry in loads(call[1]["data"])["messages"]]

    # Everyone on the way out, then only the one still outstanding
    assert recipients(mock_post.call_args_list[0]) == [
        "61412345678",
        "61498765432",
    ]
    assert recipients(mock_post.call_args_list[1]) == ["61498765432"]


@mock.patch("requests.post")
def test_plugin_mobilemessage_unconfirmed(mock_post):
    """NotifyMobileMessage() responses that confirm nothing."""

    obj = Apprise.instantiate(
        "mobilemessage://user:pass@ALERTS/0412345678/0498765432"
    )

    # The service always reports on every message it processed, so a
    # response without that list leaves the send unconfirmed
    for payload in (
        # No results field at all
        {"status": "complete"},
        # Present but the wrong shape
        {"status": "complete", "results": "unexpected"},
        # Present but empty
        {"status": "complete", "results": []},
        # One report short of the two recipients we sent to
        {
            "status": "complete",
            "results": [{"to": "61412345678", "status": "success"}],
        },
        # More reports than we sent messages
        {
            "status": "complete",
            "results": [{"status": "success"}] * 3,
        },
        # The envelope never said the batch finished
        {"results": [{"status": "success"}] * 2},
        # An envelope status we do not recognise
        {"status": "queued", "results": [{"status": "success"}] * 2},
        # Not an object at the top level
        None,
    ):
        mock_post.return_value = _mk_resp(payload)
        assert obj.notify(body="body") is False

    # A body that is not JSON at all
    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = b"<html>not json</html>"
    mock_post.return_value = response
    assert obj.notify(body="body") is False


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

    mock_post.return_value = _mk_resp(_ok())

    aobj = Apprise()
    assert aobj.add("mobilemessage://user:pass@ALERTS/0412345678")
    assert aobj.add("mobilemsg://user:pass@61400000000/0498765432")
    assert len(aobj) == 2
    assert bool(aobj.notify(title="title", body="body")) is True
    assert mock_post.call_count == 2

    # The title is folded into the body because SMS has no title field
    payload = loads(mock_post.call_args_list[0][1]["data"])
    assert payload["messages"][0]["message"] == "title\r\nbody"
