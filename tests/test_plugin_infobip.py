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
from apprise.plugins.infobip import NotifyInfobip

logging.disable(logging.CRITICAL)

# A realistic API Key
APIKEY = "0123456789abcdef0123456789abcdef-01234567-89ab-cdef-0123"


def _status(group: str, description: str = "") -> bytes:
    """Build an Infobip send response carrying one message status."""
    return json.dumps(
        {
            "bulkId": "2034072219640523072",
            "messages": [
                {
                    "messageId": "2250be2d4219-3af1-78856-aabe",
                    "status": {
                        "groupId": 1,
                        "groupName": group,
                        "id": 26,
                        "name": f"{group}_X",
                        "description": description,
                    },
                    "destination": "15551234567",
                }
            ],
        }
    ).encode("utf-8")


# A successful Infobip response
OK_RESPONSE = _status("PENDING", "Message sent to next instance")

# Our Testing URLs
apprise_url_tests = (
    (
        "infobip://",
        {
            # No Base URL specified
            "instance": None,
        },
    ),
    (
        "infobip://xyz123/15551234567",
        {
            # No API Key specified
            "instance": TypeError,
        },
    ),
    (
        f"infobip://{APIKEY}@xyz123",
        {
            # No phone numbers; we load but have nothing to notify
            "instance": NotifyInfobip,
            "notify_response": False,
        },
    ),
    (
        f"infobip://{APIKEY}@xyz123/15551234567",
        {
            "instance": NotifyInfobip,
            "requests_response_text": OK_RESPONSE,
            # Our expected url(privacy=True) startswith() response
            "privacy_url": "infobip://0...3@xyz123.api.infobip.com/"
            "15551234567",
        },
    ),
    (
        f"infobip://{APIKEY}@api.infobip.com/15551234567/15551234568"
        "?from=Alerts",
        {
            # A full Base URL and a sender name
            "instance": NotifyInfobip,
            "privacy_url": "infobip://0...3@api.infobip.com/"
            "15551234567/15551234568?from=Alerts",
        },
    ),
    (
        f"infobip://xyz123/?key={APIKEY}&to=15551234567,15551234568",
        {
            # API Key and phone numbers given as arguments
            "instance": NotifyInfobip,
            "privacy_url": "infobip://0...3@xyz123.api.infobip.com/"
            "15551234567/15551234568",
        },
    ),
    (
        f"infobip://{APIKEY}@xyz123/15551234567/123",
        {
            # One bad phone number is dropped; the good one still works
            "instance": NotifyInfobip,
        },
    ),
    (
        f"infobip://{APIKEY}@xyz123/123",
        {
            # Nothing valid to notify
            "instance": NotifyInfobip,
            "notify_response": False,
        },
    ),
    (
        f"infobip://{APIKEY}@xyz123/15551234567",
        {
            # Infobip refused the message
            "instance": NotifyInfobip,
            "requests_response_text": _status("REJECTED", "Not enough"),
            "response": False,
        },
    ),
    (
        f"infobip://{APIKEY}@xyz123/15551234567",
        {
            "instance": NotifyInfobip,
            # throw a bizarre code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        f"infobip://{APIKEY}@xyz123/15551234567",
        {
            "instance": NotifyInfobip,
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        f"infobip://{APIKEY}@xyz123/15551234567",
        {
            "instance": NotifyInfobip,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracefully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def _mk_resp(content=OK_RESPONSE, code=requests.codes.ok):
    """Build a mock Infobip response."""
    r = mock.Mock()
    r.status_code = code
    r.content = content
    return r


def test_plugin_infobip_urls():
    """NotifyInfobip() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


def test_plugin_infobip_init():
    """NotifyInfobip() validates its API Key, Base URL and targets."""

    # Bad API Keys are refused
    for apikey in (None, "", "  "):
        with pytest.raises(AppriseImproperlyConfigured):
            NotifyInfobip(apikey=apikey, host="xyz123")

    # A Base URL is required
    with pytest.raises(AppriseImproperlyConfigured):
        NotifyInfobip(apikey=APIKEY, targets="15551234567")

    # Good and bad phone numbers are kept apart
    obj = NotifyInfobip(
        apikey=APIKEY,
        host="xyz123",
        targets=["+1 (555) 123-4567", "123"],
        source=" Alerts ",
    )
    assert obj.host == "xyz123.api.infobip.com"
    assert obj.targets == ["15551234567"]
    assert obj.invalid_targets == ["123"]
    assert obj.source == "Alerts"
    assert len(obj) == 1

    # A full Base URL is kept as given
    obj = NotifyInfobip(apikey=APIKEY, host="api.infobip.com")
    assert obj.host == "api.infobip.com"
    assert obj.source is None

    # No targets still counts as one notification
    assert len(obj) == 1


def test_plugin_infobip_round_trip():
    """NotifyInfobip() url() reloads into the same object."""

    obj = NotifyInfobip(
        apikey=APIKEY,
        host="xyz123",
        targets=["15551234567", "123"],
        source="Alerts",
    )
    url = obj.url()
    assert url.startswith(
        f"infobip://{APIKEY}@xyz123.api.infobip.com/15551234567/123?"
    )
    assert "from=Alerts" in url

    result = NotifyInfobip.parse_url(url)
    assert result["apikey"] == APIKEY
    obj2 = NotifyInfobip(**result)
    assert obj2.url_identifier == obj.url_identifier
    assert obj2.targets == obj.targets
    assert obj2.invalid_targets == obj.invalid_targets
    assert obj2.source == obj.source
    assert obj2.url() == url

    # Different targets are still the same account
    assert (
        NotifyInfobip(
            apikey=APIKEY, host="xyz123", targets="15550000000"
        ).url_identifier
        == obj.url_identifier
    )

    # A different Base URL is a different account
    assert (
        NotifyInfobip(apikey=APIKEY, host="abc").url_identifier
        != obj.url_identifier
    )

    # Nothing to parse
    assert NotifyInfobip.parse_url(None) is None


@mock.patch("requests.post")
def test_plugin_infobip_payload(mock_post):
    """NotifyInfobip() posts one message to each phone number."""

    mock_post.return_value = _mk_resp()
    obj = NotifyInfobip(
        apikey=APIKEY,
        host="xyz123",
        targets=["15551234567", "15551234568"],
        source="Alerts",
    )

    assert obj.notify(body="5 * 3 & <b>", title="T & <x>")
    assert mock_post.call_count == 2

    # The request goes to the account's own Base URL
    url = mock_post.call_args_list[0][0][0]
    assert urlparse(url).hostname == "xyz123.api.infobip.com"
    assert urlparse(url).path == "/sms/3/messages"

    # The API Key is sent in the Authorization header
    headers = mock_post.call_args_list[0][1]["headers"]
    assert headers["Authorization"] == f"App {APIKEY}"

    # Each phone number gets its own copy
    first = json.loads(mock_post.call_args_list[0][1]["data"])
    second = json.loads(mock_post.call_args_list[1][1]["data"])
    assert first["messages"][0]["destinations"] == [{"to": "15551234567"}]
    assert second["messages"][0]["destinations"] == [{"to": "15551234568"}]

    # The sender is named and the title is placed in the body as typed
    assert first["messages"][0]["sender"] == "Alerts"
    assert first["messages"][0]["content"]["text"] == (
        "T & <x>\r\n5 * 3 & <b>"
    )

    # Without a sender, Infobip picks one
    mock_post.reset_mock()
    obj = NotifyInfobip(apikey=APIKEY, host="xyz123", targets="15551234567")
    assert obj.notify(body="body")
    payload = json.loads(mock_post.call_args[1]["data"])
    assert "sender" not in payload["messages"][0]


@mock.patch("requests.post")
def test_plugin_infobip_responses(mock_post):
    """NotifyInfobip() reads the message status Infobip sends back."""

    obj = NotifyInfobip(apikey=APIKEY, host="xyz123", targets="15551234567")

    # A failed status without a description still fails
    mock_post.return_value = _mk_resp(_status("UNDELIVERABLE"))
    assert not obj.notify(body="body")

    # An expired message fails too
    mock_post.return_value = _mk_resp(_status("EXPIRED", "Expired"))
    assert not obj.notify(body="body")

    # A delivered message is a success
    mock_post.return_value = _mk_resp(_status("DELIVERED"))
    assert obj.notify(body="body")

    # Responses we can not read fall back to the HTTP status code
    for content in (
        None,
        b"",
        b"not json",
        b"[]",
        b'{"messages": "x"}',
        b'{"messages": ["x", {"status": "x"}, {}]}',
    ):
        mock_post.return_value = _mk_resp(content)
        assert obj.notify(body="body")

    mock_post.return_value = _mk_resp(None, requests.codes.unauthorized)
    assert not obj.notify(body="body")


@mock.patch("requests.post")
def test_plugin_infobip_partial_failure(mock_post):
    """NotifyInfobip() reports a failure when one phone number is refused."""

    mock_post.side_effect = (
        _mk_resp(),
        _mk_resp(_status("REJECTED", "Destination not registered")),
    )
    obj = NotifyInfobip(
        apikey=APIKEY,
        host="xyz123",
        targets=["15551234567", "15551234568"],
    )
    assert not obj.notify(body="body")
    assert mock_post.call_count == 2


@mock.patch("requests.post")
def test_plugin_infobip_apprise_integration(mock_post):
    """Apprise() loads and notifies an infobip:// URL."""

    mock_post.return_value = _mk_resp()
    apobj = Apprise()
    assert apobj.add(f"infobip://{APIKEY}@xyz123/15551234567")
    assert apobj.notify(body="hello")
    assert mock_post.call_count == 1
