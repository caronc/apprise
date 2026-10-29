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

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise, NotifyType
from apprise.exception import AppriseImproperlyConfigured
from apprise.plugins.gupshup import NotifyGupshup

logging.disable(logging.CRITICAL)

# A realistic App Name, API Key and sandbox sending number
APP = "DemoAPI"
APIKEY = "abcdef0123456789abcdef0123456789"
SOURCE = "917834811114"

# An approved template ID
TEMPLATE = "c6aecef6-bcb0-4fb1-8100-28c094e3bc6b"

# The start of every URL below
BASE = f"gupshup://{APP}:{APIKEY}@{SOURCE}"

# A successful Gupshup response
OK_RESPONSE = json.dumps(
    {
        "status": "submitted",
        "messageId": "ee4a68a0-1203-4c85-8dc3-49d0b3226a35",
    }
).encode("utf-8")

# Our Testing URLs
apprise_url_tests = (
    (
        "gupshup://",
        {
            # Nothing specified
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        f"gupshup://{SOURCE}/15551234567",
        {
            # No App Name or API Key specified
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        f"gupshup://{APP}@{SOURCE}/15551234567",
        {
            # No API Key specified
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        f"gupshup://{APP}:{APIKEY}@abcd/15551234567",
        {
            # An invalid source phone number
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        f"{BASE}/15551234567?template={TEMPLATE}&:abc=1",
        {
            # An unknown template placeholder
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        f"{BASE}/",
        {
            # No phone numbers; we load but have nothing to notify
            "instance": NotifyGupshup,
            "notify_response": False,
        },
    ),
    (
        f"{BASE}/15551234567",
        {
            "instance": NotifyGupshup,
            "requests_response_text": OK_RESPONSE,
            # Our expected url(privacy=True) startswith() response
            "privacy_url": f"gupshup://{APP}:a...9@{SOURCE}/15551234567",
        },
    ),
    (
        f"{BASE}/15551234567/15551234568?template={TEMPLATE}&:body=1",
        {
            # A template with the body as its first placeholder
            "instance": NotifyGupshup,
            "requests_response_text": OK_RESPONSE,
            "privacy_url": f"gupshup://{APP}:a...9@{SOURCE}/15551234567/"
            f"15551234568?template={TEMPLATE}",
        },
    ),
    (
        f"gupshup://?app={APP}&key={APIKEY}&from={SOURCE}"
        "&to=15551234567,15551234568",
        {
            # Everything given as arguments
            "instance": NotifyGupshup,
            "privacy_url": f"gupshup://{APP}:a...9@{SOURCE}/15551234567/"
            "15551234568",
        },
    ),
    (
        f"gupshup://{APP}:{APIKEY}@/15551234567?source={SOURCE}",
        {
            # The sending number given with ?source=
            "instance": NotifyGupshup,
        },
    ),
    (
        f"{BASE}/15551234567/123",
        {
            # One bad phone number is dropped; the good one still works
            "instance": NotifyGupshup,
        },
    ),
    (
        f"{BASE}/123",
        {
            # Nothing valid to notify
            "instance": NotifyGupshup,
            "notify_response": False,
        },
    ),
    (
        f"{BASE}/15551234567",
        {
            "instance": NotifyGupshup,
            # throw a bizarre code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        f"{BASE}/15551234567",
        {
            "instance": NotifyGupshup,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracefully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def _mk_resp(content=OK_RESPONSE, code=requests.codes.ok):
    """Build a mock Gupshup response."""
    r = mock.Mock()
    r.status_code = code
    r.content = content
    return r


def test_plugin_gupshup_urls():
    """Gupshup URLs load and behave as expected."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


def test_plugin_gupshup_init():
    """Gupshup settings are validated and normalised."""

    # The source and targets are reduced to digits
    obj = NotifyGupshup(
        app=APP,
        apikey=APIKEY,
        source="+91 78348 11114",
        targets="+1 555 123 4567",
    )
    assert obj.source == SOURCE
    assert obj.targets == ["15551234567"]
    assert obj.template is None
    assert len(obj) == 1

    # No phone numbers still counts as one notification
    obj = NotifyGupshup(app=APP, apikey=APIKEY, source=SOURCE)
    assert len(obj) == 1

    # Several phone numbers
    obj = NotifyGupshup(
        app=APP,
        apikey=APIKEY,
        source=SOURCE,
        targets=["15551234567", "15551234568"],
    )
    assert len(obj) == 2

    # A missing App Name, API Key or source is refused
    with pytest.raises(AppriseImproperlyConfigured):
        NotifyGupshup(apikey=APIKEY, source=SOURCE)

    with pytest.raises(AppriseImproperlyConfigured):
        NotifyGupshup(app=APP, source=SOURCE)

    with pytest.raises(AppriseImproperlyConfigured):
        NotifyGupshup(app=APP, apikey=APIKEY)

    # A template ID made of nothing but spaces is refused
    with pytest.raises(AppriseImproperlyConfigured):
        NotifyGupshup(app=APP, apikey=APIKEY, source=SOURCE, template="  ")


def test_plugin_gupshup_template_mapping():
    """Gupshup template placeholders are validated."""

    # Fixed values, the body and the type in any order
    obj = NotifyGupshup(
        app=APP,
        apikey=APIKEY,
        source=SOURCE,
        template=TEMPLATE,
        template_mapping={"3": "fixed", "body": "2", "type": "1"},
    )
    assert obj.template_params == {
        1: ("type", None),
        2: ("body", None),
        3: ("text", "fixed"),
    }

    # An unknown placeholder key
    with pytest.raises(AppriseImproperlyConfigured):
        NotifyGupshup(
            app=APP,
            apikey=APIKEY,
            source=SOURCE,
            template=TEMPLATE,
            template_mapping={"title": "1"},
        )

    # The body must be given a position
    with pytest.raises(AppriseImproperlyConfigured):
        NotifyGupshup(
            app=APP,
            apikey=APIKEY,
            source=SOURCE,
            template=TEMPLATE,
            template_mapping={"body": "type"},
        )

    # The same position can not be filled twice
    with pytest.raises(AppriseImproperlyConfigured):
        NotifyGupshup(
            app=APP,
            apikey=APIKEY,
            source=SOURCE,
            template=TEMPLATE,
            template_mapping={"1": "fixed", "body": "1"},
        )


def test_plugin_gupshup_round_trip():
    """A Gupshup URL survives url() and parse_url() unchanged."""

    obj = NotifyGupshup(
        app=APP,
        apikey=APIKEY,
        source=SOURCE,
        template=TEMPLATE,
        template_mapping={"body": "1", "2": "a & b"},
        targets=["15551234567", "15551234568", "bad"],
    )

    # Rebuild it from its own URL
    result = NotifyGupshup.parse_url(obj.url())
    obj2 = NotifyGupshup(**result)

    assert obj.url_identifier == obj2.url_identifier
    assert obj2.apikey == APIKEY
    assert obj2.targets == obj.targets
    assert obj2.invalid_targets == obj.invalid_targets
    assert obj2.template == TEMPLATE
    assert obj2.template_mapping == obj.template_mapping
    assert obj2.template_params == obj.template_params

    # Without a template, none is written to the URL
    obj = NotifyGupshup(
        app=APP, apikey=APIKEY, source=SOURCE, targets="15551234567"
    )
    assert "template=" not in obj.url()

    # The API Key is hidden in a private URL
    assert APIKEY not in obj.url(privacy=True)

    # A different app or sending number is a different connection
    obj3 = NotifyGupshup(app="Other", apikey=APIKEY, source=SOURCE)
    assert obj.url_identifier != obj3.url_identifier
    obj3 = NotifyGupshup(app=APP, apikey=APIKEY, source="15550000000")
    assert obj.url_identifier != obj3.url_identifier


@mock.patch("requests.post")
def test_plugin_gupshup_text_payload(mock_post):
    """Gupshup receives the expected free-form text request."""

    mock_post.return_value = _mk_resp()

    obj = Apprise.instantiate(f"{BASE}/15551234567")
    assert isinstance(obj, NotifyGupshup)
    assert obj.notify(title="Title & <b>", body="Body _ . ! * # <")

    assert mock_post.call_count == 1
    args, kwargs = mock_post.call_args
    assert args[0] == "https://api.gupshup.io/wa/api/v1/msg"

    # Our API Key is sent as a header
    assert kwargs["headers"]["apikey"] == APIKEY

    # The title is placed in the body untouched
    data = kwargs["data"]
    assert data["channel"] == "whatsapp"
    assert data["source"] == SOURCE
    assert data["src.name"] == APP
    assert data["destination"] == "15551234567"
    assert "template" not in data
    assert json.loads(data["message"]) == {
        "type": "text",
        "text": "Title & <b>\r\nBody _ . ! * # <",
    }


@mock.patch("requests.post")
def test_plugin_gupshup_template_payload(mock_post):
    """Gupshup receives the expected template request."""

    mock_post.return_value = _mk_resp()

    obj = Apprise.instantiate(
        f"{BASE}/15551234567?template={TEMPLATE}&:body=2&:type=3&:1=Server%20A"
    )
    assert isinstance(obj, NotifyGupshup)
    assert obj.notify(body="Disk is full", notify_type=NotifyType.WARNING)

    assert mock_post.call_count == 1
    args, kwargs = mock_post.call_args
    assert args[0] == "https://api.gupshup.io/wa/api/v1/template/msg"

    # The placeholders are filled in position order
    data = kwargs["data"]
    assert data["source"] == SOURCE
    assert data["src.name"] == APP
    assert data["destination"] == "15551234567"
    assert "message" not in data
    assert "channel" not in data
    assert json.loads(data["template"]) == {
        "id": TEMPLATE,
        "params": ["Server A", "Disk is full", "warning"],
    }

    # A template without placeholders sends no values
    mock_post.reset_mock()
    obj = Apprise.instantiate(f"{BASE}/15551234567?template={TEMPLATE}")
    assert obj.notify(body="ignored")
    data = mock_post.call_args[1]["data"]
    assert json.loads(data["template"]) == {"id": TEMPLATE, "params": []}


@mock.patch("requests.post")
def test_plugin_gupshup_responses(mock_post):
    """Gupshup error responses are reported as failures."""

    obj = Apprise.instantiate(f"{BASE}/15551234567")

    # A 202 response is a success too
    mock_post.return_value = _mk_resp(code=requests.codes.accepted)
    assert obj.notify(body="test") is True

    # Gupshup explains the error
    mock_post.return_value = _mk_resp(
        b'{"status": "error", "message": "Authentication Failed"}',
        code=requests.codes.unauthorized,
    )
    assert obj.notify(body="test") is False

    # An error reported with a successful status code
    mock_post.return_value = _mk_resp(
        b'{"status": "error", "message": "Invalid Destination"}'
    )
    assert obj.notify(body="test") is False

    # A known HTTP error with no usable body
    mock_post.return_value = _mk_resp(
        b"not json", code=requests.codes.bad_request
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


@mock.patch("requests.post")
def test_plugin_gupshup_partial_failure(mock_post):
    """One refused phone number fails the send but not the others."""

    mock_post.side_effect = [
        _mk_resp(),
        _mk_resp(b"{}", code=requests.codes.bad_request),
    ]

    obj = Apprise.instantiate(f"{BASE}/15551234567/15551234568")
    assert obj.notify(body="test") is False
    assert mock_post.call_count == 2


@mock.patch("requests.post")
def test_plugin_gupshup_apprise_integration(mock_post):
    """Gupshup works through the Apprise object."""

    mock_post.return_value = _mk_resp()

    aobj = Apprise()
    assert aobj.add(f"{BASE}/15551234567")
    assert aobj.notify(title="Title", body="Body")
    assert mock_post.call_count == 1
