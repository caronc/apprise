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
from apprise.plugins.kaleyra import NotifyKaleyra

logging.disable(logging.CRITICAL)

# A realistic Account SID, API Key and Sender ID
SID = "HXAP16XXXXXX97IN"
APIKEY = "Ac4b0123456789abcdef0123456789a21f"
SENDER = "KLRHXA"

# A successful Kaleyra response
OK_RESPONSE = json.dumps(
    {
        "id": "ee8a0000-0000-0000-0000-9b7170000030d",
        "sender": SENDER,
        "type": "DEFAULT",
        "body": "test",
        "createdDateTime": "2019-11-04 10:42:23+00:00",
        "totalCount": 1,
        "data": [
            {
                "message_id": "ee8a0000-0000-0000-0000-9b7170000030d:1",
                "recipient": "15551234567",
            }
        ],
        "dlrurl": None,
        "error": {},
    }
).encode("utf-8")

# Our Testing URLs
apprise_url_tests = (
    (
        "kaleyra://",
        {
            # Nothing specified
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        f"kaleyra://{SENDER}/15551234567",
        {
            # No Account SID or API Key specified
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        f"kaleyra://{SID}@{SENDER}/15551234567",
        {
            # No API Key specified
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        f"kaleyra://{SID}:{APIKEY}@/15551234567",
        {
            # No Sender ID specified
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        f"kaleyra://{SID}:{APIKEY}@{SENDER}/15551234567?region=us",
        {
            # An unknown region
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        f"kaleyra://{SID}:{APIKEY}@{SENDER}/15551234567?type=invalid",
        {
            # An unknown message type
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        f"kaleyra://{SID}:{APIKEY}@{SENDER}",
        {
            # No phone numbers; we load but have nothing to notify
            "instance": NotifyKaleyra,
            "notify_response": False,
        },
    ),
    (
        f"kaleyra://{SID}:{APIKEY}@{SENDER}/15551234567",
        {
            "instance": NotifyKaleyra,
            "requests_response_text": OK_RESPONSE,
            # Our expected url(privacy=True) startswith() response
            "privacy_url": f"kaleyra://{SID}:A...f@{SENDER}/15551234567",
        },
    ),
    (
        f"kaleyra://{SID}:{APIKEY}@{SENDER}/15551234567/915551234568"
        "?region=in&type=txn&template=1012345678901&flash=yes&batch=yes",
        {
            # Every option in use
            "instance": NotifyKaleyra,
            "privacy_url": f"kaleyra://{SID}:A...f@{SENDER}/15551234567/"
            "915551234568?flash=yes&batch=yes&region=in&type=txn"
            "&template=1012345678901",
        },
    ),
    (
        f"kaleyra://?sid={SID}&key={APIKEY}&from={SENDER}"
        "&to=15551234567,15551234568",
        {
            # Everything given as arguments
            "instance": NotifyKaleyra,
            "privacy_url": f"kaleyra://{SID}:A...f@{SENDER}/15551234567/"
            "15551234568",
        },
    ),
    (
        f"kaleyra://{SID}:{APIKEY}@/15551234567?sender={SENDER}",
        {
            # The Sender ID given as an argument
            "instance": NotifyKaleyra,
            "privacy_url": f"kaleyra://{SID}:A...f@{SENDER}/15551234567",
        },
    ),
    (
        f"klr://{SID}:{APIKEY}@{SENDER}/15551234567",
        {
            # The short alias is written back as kaleyra://
            "instance": NotifyKaleyra,
            "privacy_url": f"kaleyra://{SID}:A...f@{SENDER}/15551234567",
        },
    ),
    (
        f"kaleyra://{SID}:{APIKEY}@{SENDER}/15551234567/123",
        {
            # One bad phone number is dropped; the good one still works
            "instance": NotifyKaleyra,
        },
    ),
    (
        f"kaleyra://{SID}:{APIKEY}@{SENDER}/123",
        {
            # Nothing valid to notify
            "instance": NotifyKaleyra,
            "notify_response": False,
        },
    ),
    (
        f"kaleyra://{SID}:{APIKEY}@{SENDER}/15551234567",
        {
            "instance": NotifyKaleyra,
            # An internal server error
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        f"kaleyra://{SID}:{APIKEY}@{SENDER}/15551234567",
        {
            "instance": NotifyKaleyra,
            # throw a bizarre code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        f"kaleyra://{SID}:{APIKEY}@{SENDER}/15551234567",
        {
            "instance": NotifyKaleyra,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracefully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def _mk_resp(content=OK_RESPONSE, code=requests.codes.ok):
    """Build a mock Kaleyra response."""
    r = mock.Mock()
    r.status_code = code
    r.content = content
    return r


def test_plugin_kaleyra_urls():
    """Kaleyra URLs load and behave as expected."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


def test_plugin_kaleyra_init():
    """Kaleyra settings are validated and normalised."""

    # The defaults
    obj = NotifyKaleyra(
        sid=SID, apikey=APIKEY, sender=SENDER, targets="+1 555 123 4567"
    )
    assert obj.region == "sg"
    assert obj.message_type is None
    assert obj.template is None
    assert obj.flash is False
    assert obj.batch is False
    assert obj.targets == ["15551234567"]
    assert len(obj) == 1

    # The region and message type are cleaned up
    obj = NotifyKaleyra(
        sid=SID,
        apikey=APIKEY,
        sender=SENDER,
        region=" EU ",
        message_type=" otp ",
        template="1012345678901",
        flash=True,
        targets=["15551234567", "15551234568"],
    )
    assert obj.region == "eu"
    assert obj.message_type == "OTP"
    assert obj.template == "1012345678901"
    assert obj.flash is True
    assert len(obj) == 2

    # No phone numbers still counts as one notification
    obj = NotifyKaleyra(sid=SID, apikey=APIKEY, sender=SENDER)
    assert len(obj) == 1

    # A missing SID, API Key or Sender ID is refused
    with pytest.raises(AppriseImproperlyConfigured):
        NotifyKaleyra(apikey=APIKEY, sender=SENDER)

    with pytest.raises(AppriseImproperlyConfigured):
        NotifyKaleyra(sid=SID, sender=SENDER)

    with pytest.raises(AppriseImproperlyConfigured):
        NotifyKaleyra(sid=SID, apikey=APIKEY)

    # A blank template is refused
    with pytest.raises(AppriseImproperlyConfigured):
        NotifyKaleyra(sid=SID, apikey=APIKEY, sender=SENDER, template=" ")


def test_plugin_kaleyra_batch_count():
    """Batching groups up to 100 phone numbers per request."""

    targets = [f"1555{n:07d}" for n in range(101)]

    # One request per phone number without batching
    obj = NotifyKaleyra(sid=SID, apikey=APIKEY, sender=SENDER, targets=targets)
    assert len(obj) == 101

    # Two requests are needed for 101 phone numbers when batching
    obj = NotifyKaleyra(
        sid=SID, apikey=APIKEY, sender=SENDER, targets=targets, batch=True
    )
    assert len(obj) == 2


def test_plugin_kaleyra_round_trip():
    """A Kaleyra URL survives url() and parse_url() unchanged."""

    obj = NotifyKaleyra(
        sid=SID,
        apikey=APIKEY,
        sender="+17005551234",
        region="in",
        message_type="mkt",
        template="1012345678901",
        flash=True,
        batch=True,
        targets=["15551234567", "15551234568", "bad"],
    )

    # Rebuild it from its own URL
    result = NotifyKaleyra.parse_url(obj.url())
    obj2 = NotifyKaleyra(**result)

    assert obj.url_identifier == obj2.url_identifier
    assert obj2.sender == "+17005551234"
    assert obj2.targets == obj.targets
    assert obj2.invalid_targets == obj.invalid_targets
    assert obj2.region == "in"
    assert obj2.message_type == "MKT"
    assert obj2.template == "1012345678901"
    assert obj2.flash is True
    assert obj2.batch is True

    # The default region and an unset type are not written to the URL
    obj = NotifyKaleyra(
        sid=SID, apikey=APIKEY, sender=SENDER, targets="15551234567"
    )
    assert "region=" not in obj.url()
    assert "type=" not in obj.url()

    # The API Key is hidden in a private URL
    assert APIKEY not in obj.url(privacy=True)

    # Another region is a different connection
    obj3 = NotifyKaleyra(
        sid=SID,
        apikey=APIKEY,
        sender=SENDER,
        region="eu",
        targets="15551234567",
    )
    assert obj.url_identifier != obj3.url_identifier

    # The short alias is the same connection as the full schema
    obj4 = Apprise.instantiate(f"klr://{SID}:{APIKEY}@{SENDER}/15551234567")
    assert obj4.url().startswith("kaleyra://")
    assert obj.url_identifier == obj4.url_identifier


@mock.patch("requests.post")
def test_plugin_kaleyra_payload(mock_post):
    """Kaleyra receives the expected request."""

    mock_post.return_value = _mk_resp()

    obj = Apprise.instantiate(f"kaleyra://{SID}:{APIKEY}@{SENDER}/15551234567")
    assert isinstance(obj, NotifyKaleyra)
    assert obj.notify(title="Title & <b>", body="Body _ . ! * # <")

    assert mock_post.call_count == 1
    args, kwargs = mock_post.call_args

    # The default region is Singapore
    assert urlparse(args[0]).hostname == "api.kaleyra.io"
    assert urlparse(args[0]).path == f"/v1/{SID}/messages"

    # Our API Key is sent as a header
    assert kwargs["headers"]["api-key"] == APIKEY
    assert kwargs["headers"]["Content-Type"] == "application/json"

    # The title is placed in the body untouched
    assert json.loads(kwargs["data"]) == {
        "to": "15551234567",
        "sender": SENDER,
        "body": "Title & <b>\r\nBody _ . ! * # <",
        "unicode": "AUTO",
    }

    # Every option is passed along
    mock_post.reset_mock()
    obj = Apprise.instantiate(
        f"kaleyra://{SID}:{APIKEY}@{SENDER}/15551234567/15551234568"
        "?region=in&type=txn&template=1012345678901&flash=yes&batch=yes"
    )
    assert obj.notify(body="test")

    # Both phone numbers go out in one request
    assert mock_post.call_count == 1
    args, kwargs = mock_post.call_args
    assert urlparse(args[0]).hostname == "api.in.kaleyra.io"
    assert json.loads(kwargs["data"]) == {
        "to": "15551234567,15551234568",
        "sender": SENDER,
        "body": "test",
        "unicode": "AUTO",
        "type": "TXN",
        "template_id": "1012345678901",
        "flash": "1",
    }

    # The Europe region has its own host
    mock_post.reset_mock()
    obj = Apprise.instantiate(
        f"kaleyra://{SID}:{APIKEY}@{SENDER}/15551234567?region=eu"
    )
    assert obj.notify(body="test")
    assert urlparse(mock_post.call_args[0][0]).hostname == (
        "api.eu.kaleyra.io"
    )


@mock.patch("requests.post")
def test_plugin_kaleyra_responses(mock_post):
    """Kaleyra error responses are reported as failures."""

    obj = Apprise.instantiate(f"kaleyra://{SID}:{APIKEY}@{SENDER}/15551234567")

    # Kaleyra explains the error
    mock_post.return_value = _mk_resp(
        json.dumps(
            {
                "code": "E418",
                "message": "Invalid or incorrect sender ID.",
                "data": [],
                "error": {"sender": "Invalid or incorrect sender ID."},
            }
        ).encode("utf-8"),
        code=requests.codes.bad_request,
    )
    assert obj.notify(body="test") is False

    # An error reported alongside a successful status code
    mock_post.return_value = _mk_resp(
        b'{"error": {"body": "Body parameter is mandatory."}}'
    )
    assert obj.notify(body="test") is False

    # A known HTTP error with no usable body
    mock_post.return_value = _mk_resp(
        b"not json", code=requests.codes.unauthorized
    )
    assert obj.notify(body="test") is False

    # A JSON body that is not an object
    mock_post.return_value = _mk_resp(
        b"[]", code=requests.codes.too_many_requests
    )
    assert obj.notify(body="test") is False

    # No content at all
    mock_post.return_value = _mk_resp(None, code=requests.codes.forbidden)
    assert obj.notify(body="test") is False

    # Accepted for later delivery is a success
    mock_post.return_value = _mk_resp(code=requests.codes.accepted)
    assert obj.notify(body="test") is True


@mock.patch("requests.post")
def test_plugin_kaleyra_partial_failure(mock_post):
    """One refused phone number fails the send but not the others."""

    mock_post.side_effect = [
        _mk_resp(),
        _mk_resp(b"{}", code=requests.codes.bad_request),
    ]

    obj = Apprise.instantiate(
        f"kaleyra://{SID}:{APIKEY}@{SENDER}/15551234567/15551234568"
    )
    assert obj.notify(body="test") is False
    assert mock_post.call_count == 2


@mock.patch("requests.post")
def test_plugin_kaleyra_apprise_integration(mock_post):
    """Kaleyra works through the Apprise object."""

    mock_post.return_value = _mk_resp()

    aobj = Apprise()
    assert aobj.add(f"kaleyra://{SID}:{APIKEY}@{SENDER}/15551234567")
    assert aobj.notify(title="Title", body="Body")
    assert mock_post.call_count == 1
