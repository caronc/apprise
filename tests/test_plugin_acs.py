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

import base64
import hashlib
import hmac
from json import loads
import logging
import os
from unittest import mock

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise, AppriseAttachment, NotifyFormat, NotifyType
from apprise.exception import AppriseImproperlyConfigured
from apprise.plugins.acs import NotifyACS

logging.disable(logging.CRITICAL)

# Attachment Directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), "var")

# An 88 character base64 key, like the ones Azure hands out
KEY = "YWJj+/8+" * 11

# A key with "//" in it, written with %2F so the URL keeps it intact
SLASH_KEY = "ab//" * 22
SLASH_KEY_QUOTED = SLASH_KEY.replace("/", "%2F")

EP = "contoso.communication.azure.com"

# Our Testing URLs
apprise_url_tests = (
    (
        "acs://",
        {
            # Nothing at all
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "acs://user@example.com",
        {
            # No access key or endpoint
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        f"acs://user@example.com/{KEY}",
        {
            # No endpoint
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        f"acs://user@example.com/{EP}",
        {
            # No access key
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        f"acs://user@example.com/!invalid!/{EP}",
        {
            # An access key with characters base64 never uses
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        f"acs://user@example.com/YWJjZA=/{EP}",
        {
            # An access key with broken base64 padding
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        f"acs://user@example.com/{KEY}/-invalid.endpoint",
        {
            # An invalid endpoint
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        f"acs://invalid/{KEY}/{EP}",
        {
            # No from email
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        f"acs://user@example.com/{KEY}/{EP}",
        {
            # No targets; we notify ourselves
            "instance": NotifyACS,
            "privacy_url": f"acs://user@example.com/Y...+/{EP}/",
        },
    ),
    (
        f"acs://user@example.com/{KEY}/{EP}/target@example.com",
        {
            "instance": NotifyACS,
            "privacy_url": (
                f"acs://user@example.com/Y...+/{EP}/target@example.com"
            ),
        },
    ),
    (
        (
            f"acs://user@example.com/{KEY}/{EP}/target1@example.com/"
            "target2@example.com?cc=Chris<cc@example.com>"
            "&bcc=bcc@example.com&reply=Support<reply@example.com>"
        ),
        {
            "instance": NotifyACS,
            "url_matches": r"cc=Chris",
        },
    ),
    (
        (
            f"acs://?from=user@example.com&key={SLASH_KEY_QUOTED}"
            f"&endpoint=https://{EP}/&to=target@example.com"
        ),
        {
            # Everything passed as query arguments
            "instance": NotifyACS,
            "privacy_url": (
                f"acs://user@example.com/a...//{EP}/target@example.com"
            ),
        },
    ),
    (
        f"acs://user@example.com/{SLASH_KEY_QUOTED}/{EP}/target@example.com",
        {
            # A key holding "//" written with %2F
            "instance": NotifyACS,
        },
    ),
    (
        f"acs://user@example.com/{EP}/target@example.com?key={KEY}",
        {
            # Endpoint in the path, key as a query argument
            "instance": NotifyACS,
        },
    ),
    (
        f"acs://user@example.com/{KEY}/target@example.com?endpoint={EP}",
        {
            # Key in the path, endpoint as a query argument
            "instance": NotifyACS,
        },
    ),
    (
        f"acs://user@example.com/{KEY}/{EP}/target@example.com?format=text",
        {
            "instance": NotifyACS,
            "force_debug": True,
        },
    ),
    (
        f"acs://user@example.ca/{KEY}/{EP}/target@example.ca",
        {
            "instance": NotifyACS,
            # force a failure
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        f"acs://user@example.uk/{KEY}/{EP}/target@example.uk",
        {
            "instance": NotifyACS,
            # throw a bizarre code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        f"acs://user@example.au/{KEY}/{EP}/target@example.au",
        {
            "instance": NotifyACS,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracefully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_acs_urls():
    """NotifyACS() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


def test_plugin_acs_edge_cases():
    """NotifyACS() Edge Cases."""

    # The endpoint may carry its scheme and a trailing slash
    obj = NotifyACS(
        from_email="user@example.com",
        access_key=KEY,
        endpoint=f"HTTPS://{EP.upper()}/",
    )
    assert obj.endpoint == EP

    with pytest.raises(AppriseImproperlyConfigured):
        NotifyACS(from_email="user@example.com", access_key=KEY, endpoint=None)

    with pytest.raises(AppriseImproperlyConfigured):
        NotifyACS(from_email="user@example.com", access_key=None, endpoint=EP)

    with pytest.raises(AppriseImproperlyConfigured):
        NotifyACS(from_email="!invalid", access_key=KEY, endpoint=EP)

    # Bad cc, bcc and reply-to entries are dropped, good ones are kept
    obj = NotifyACS(
        from_email="user@example.com",
        access_key=KEY,
        endpoint=EP,
        cc=("cc@example.com", "!invalid"),
        bcc=("bcc@example.com", "!invalid"),
        reply_to=("reply@example.com", "!invalid"),
    )
    assert obj.cc == {"cc@example.com"}
    assert obj.bcc == {"bcc@example.com"}
    assert obj.reply_to == {"reply@example.com"}
    assert len(obj) == 1

    # Only invalid targets, so there is nobody to notify
    obj = NotifyACS(
        from_email="user@example.com",
        access_key=KEY,
        endpoint=EP,
        targets="!invalid",
    )
    assert len(obj) == 1
    assert obj.notify(body="body") is False


@mock.patch("requests.post")
def test_plugin_acs_signature_and_payload(mock_post):
    """NotifyACS() signs each request and builds the ACS payload."""

    response = mock.Mock()
    response.status_code = requests.codes.accepted
    response.content = b""
    mock_post.return_value = response

    obj = Apprise.instantiate(
        f"acs://user@example.com/{KEY}/{EP}/"
        "alice@example.com/bob@example.com"
        "?cc=%22Smith%2C%20Chris%22%20%3Ccc%40example.com%3E,"
        "bob@example.com&bcc=bcc@example.com&reply=reply@example.com"
    )
    assert isinstance(obj, NotifyACS)
    assert obj.notify(body="<b>body</b>", title="title") is True

    # One request per target
    assert mock_post.call_count == 2

    for call in mock_post.call_args_list:
        assert call[0][0] == (
            f"https://{EP}/emails:send?api-version=2023-03-31"
        )

        data = call[1]["data"]
        headers = call[1]["headers"]

        # Re-create the signature the same way the Azure SDK does
        content_hash = base64.b64encode(hashlib.sha256(data).digest()).decode()
        assert headers["x-ms-content-sha256"] == content_hash
        string_to_sign = (
            "POST\n/emails:send?api-version=2023-03-31\n"
            f"{headers['x-ms-date']};{EP};{content_hash}"
        )
        signature = base64.b64encode(
            hmac.new(
                base64.b64decode(KEY),
                string_to_sign.encode("utf-8"),
                hashlib.sha256,
            ).digest()
        ).decode()
        assert headers["Authorization"] == (
            "HMAC-SHA256 SignedHeaders=x-ms-date;host;x-ms-content-sha256"
            f"&Signature={signature}"
        )
        assert headers["x-ms-date"].endswith(" GMT")

    first = loads(mock_post.call_args_list[0][1]["data"])
    assert first["senderAddress"] == "user@example.com"
    assert first["content"] == {"subject": "title", "html": "<b>body</b>"}
    assert first["recipients"]["to"] == [{"address": "alice@example.com"}]
    assert first["recipients"]["cc"] == [
        {"address": "bob@example.com"},
        {"address": "cc@example.com", "displayName": "Smith, Chris"},
    ]
    assert first["recipients"]["bcc"] == [{"address": "bcc@example.com"}]
    assert first["replyTo"] == [{"address": "reply@example.com"}]
    assert first["userEngagementTrackingDisabled"] is True

    # A target is never copied on its own email
    second = loads(mock_post.call_args_list[1][1]["data"])
    assert second["recipients"]["to"] == [{"address": "bob@example.com"}]
    assert second["recipients"]["cc"] == [
        {"address": "cc@example.com", "displayName": "Smith, Chris"},
    ]

    # Names survive a round trip through url()
    obj2 = Apprise.instantiate(obj.url())
    assert isinstance(obj2, NotifyACS)
    assert obj2.access_key == KEY
    assert obj2.cc == obj.cc
    assert obj2.names["cc@example.com"] == "Smith, Chris"

    # Plain text goes in plainText, and an empty title gets a subject
    mock_post.reset_mock()
    obj = Apprise.instantiate(f"acs://user@example.com/{KEY}/{EP}?format=text")
    assert obj.notify(body="body") is True
    payload = loads(mock_post.call_args[1]["data"])
    assert payload["content"] == {
        "subject": "<no subject>",
        "plainText": "body",
    }
    assert payload["recipients"] == {"to": [{"address": "user@example.com"}]}
    assert "replyTo" not in payload


@mock.patch("requests.post")
def test_plugin_acs_formats(mock_post):
    """NotifyACS() picks html or plainText from the resolved format."""

    response = mock.Mock()
    response.status_code = requests.codes.accepted
    response.content = b""
    mock_post.return_value = response

    url = f"acs://user@example.com/{KEY}/{EP}/target@example.com"

    def _content(url, body, body_format=None):
        """Send through Apprise and return the posted content block."""
        mock_post.reset_mock()
        a = Apprise()
        assert a.add(url)
        assert a.notify(body=body, title="a & <b>", body_format=body_format)
        return loads(mock_post.call_args[1]["data"])["content"]

    # Text input goes out as plainText, untouched
    assert _content(url, "1 < 2 & *x*", NotifyFormat.TEXT) == {
        "subject": "a & <b>",
        "plainText": "1 < 2 & *x*",
    }

    # HTML input goes out as html, untouched
    assert _content(url, "<b>hi</b>", NotifyFormat.HTML) == {
        "subject": "a & <b>",
        "html": "<b>hi</b>",
    }

    # Markdown is not declared, so it falls back to html
    assert _content(url, "**hi**", NotifyFormat.MARKDOWN) == {
        "subject": "a & <b>",
        "html": "<p><strong>hi</strong></p>",
    }

    # ?format=text beats the input format
    assert _content(f"{url}?format=text", "<b>hi</b>", NotifyFormat.HTML) == {
        "subject": "a & <b>",
        "plainText": "hi",
    }

    # A body with no declared format is relayed as html
    obj = Apprise.instantiate(url)
    mock_post.reset_mock()
    assert obj.notify(body="<i>raw</i>", title="t") is True
    assert loads(mock_post.call_args[1]["data"])["content"] == {
        "subject": "t",
        "html": "<i>raw</i>",
    }


@mock.patch("requests.post")
def test_plugin_acs_attachments(mock_post):
    """NotifyACS() Attachments."""

    response = mock.Mock()
    response.status_code = requests.codes.accepted
    response.content = b""
    mock_post.return_value = response

    path = os.path.join(TEST_VAR_DIR, "apprise-test.gif")
    attach = AppriseAttachment(path)
    obj = Apprise.instantiate(f"acs://user@example.com/{KEY}/{EP}")
    assert isinstance(obj, NotifyACS)
    assert (
        obj.notify(
            body="body",
            title="title",
            notify_type=NotifyType.INFO,
            attach=attach,
        )
        is True
    )

    payload = loads(mock_post.call_args[1]["data"])
    assert len(payload["attachments"]) == 1
    attachment = payload["attachments"][0]
    assert attachment["name"] == "apprise-test.gif"
    assert attachment["contentType"] == "image/gif"
    with open(path, "rb") as f:
        assert base64.b64decode(attachment["contentInBase64"]) == f.read()

    # An attachment without a name gets one
    mock_post.reset_mock()
    with mock.patch(
        "apprise.attachment.file.AttachFile.name",
        new_callable=mock.PropertyMock,
        return_value=None,
    ):
        assert obj.notify(body="body", attach=AppriseAttachment(path)) is True
    payload = loads(mock_post.call_args[1]["data"])
    assert payload["attachments"][0]["name"] == "file001.dat"

    mock_post.reset_mock()

    # We can't access the file
    with mock.patch("os.path.isfile", return_value=False):
        assert obj.notify(body="body", attach=attach) is False

    # We can't read the file
    with mock.patch("builtins.open", side_effect=OSError):
        assert obj.notify(body="body", attach=AppriseAttachment(path)) is False

    assert mock_post.call_count == 0


@mock.patch("requests.post")
def test_plugin_acs_retry_skips_delivered(mock_post):
    """NotifyACS() retries only the targets that failed."""

    def respond(url, data=None, **kwargs):
        response = mock.Mock()
        response.content = b""
        to = loads(data)["recipients"]["to"][0]["address"]
        refused = to == "b@example.com" and mock_post.call_count == 2
        response.status_code = (
            requests.codes.internal_server_error
            if refused
            else requests.codes.accepted
        )
        return response

    mock_post.side_effect = respond

    aobj = Apprise()
    assert aobj.add(
        f"acs://user@example.com/{KEY}/{EP}/a@example.com/b@example.com"
        "?retry=1&wait=0"
    )
    assert aobj.notify(body="body")

    # a@ is sent once, b@ is refused and then sent on the retry
    sent_to = [
        loads(call[1]["data"])["recipients"]["to"][0]["address"]
        for call in mock_post.call_args_list
    ]
    assert sent_to == ["a@example.com", "b@example.com", "b@example.com"]
