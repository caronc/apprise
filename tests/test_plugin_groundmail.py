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
from json import loads
import logging
import os
from unittest import mock

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise, AppriseAttachment, NotifyFormat, NotifyType
from apprise.exception import AppriseImproperlyConfigured
from apprise.plugins.base import _delivery_memo, _delivery_tracker
from apprise.plugins.groundmail import NotifyGroundmail

logging.disable(logging.CRITICAL)

# Attachment Directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), "var")

# A representative Groundmail API key
APIKEY = "gm_live_abc123def456abc123def456abc123"

# Our Testing URLs
apprise_url_tests = (
    (
        "groundmail://",
        {
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "groundmail://:@/",
        {
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "groundmail://abcd",
        {
            # Just an broken email (no api key or email)
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "groundmail://abcd@host",
        {
            # Just an Email specified, no API Key
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "groundmail://invalid-api-key+*-d:user@example.com",
        {
            # An invalid API Key
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "groundmail://abcd:user@example.com",
        {
            # No To/Target Address(es) specified; so we sub in the same From
            # address
            "instance": NotifyGroundmail,
        },
    ),
    (
        f"groundmail://{APIKEY}:user@example.com/newuser1@example.com",
        {
            # A good email
            "instance": NotifyGroundmail,
            "privacy_url": (
                "groundmail://g...3:user@example.com/newuser1@example.com"
            ),
        },
    ),
    (
        "groundmail://abcd:user@example.com/newuser2@example.com?name=Jessica",
        {
            # A good email
            "instance": NotifyGroundmail,
            "privacy_url": (
                "groundmail://a...d:user@example.com/newuser2@example.com"
            ),
            "url_matches": r"name=Jessica",
        },
    ),
    (
        (
            "groundmail://abcd@newuser4%40example.com?name=Ralph"
            "&from=user2@example.ca"
        ),
        {
            # A good email
            "instance": NotifyGroundmail,
            "privacy_url": "groundmail://a...d:user2@example.ca/",
            "url_matches": r"name=Ralph",
            "force_debug": True,
        },
    ),
    (
        (
            "groundmail://?apikey=abcd&from=Joe<user@example.com>"
            "&to=newuser5@example.com"
        ),
        {
            # A good email
            "instance": NotifyGroundmail,
            "privacy_url": (
                "groundmail://a...d:user@example.com/newuser5@example.com"
            ),
            "url_matches": r"name=Joe",
        },
    ),
    (
        (
            "groundmail://?apikey=abcd&from=Joe<user@example.com>"
            "&reply=John<newuser6@example.com>"
        ),
        {
            # A good email
            "instance": NotifyGroundmail,
            "privacy_url": "groundmail://a...d:user@example.com",
            "url_matches": r"reply=John",
        },
    ),
    (
        (
            "groundmail://?apikey=abcd&from=Joe<user@example.com>"
            "&reply=garbage%"
        ),
        {
            # A good email but has a garbage reply-to value
            "instance": NotifyGroundmail,
        },
    ),
    (
        (
            "groundmail://abcd:user@example.com/newuser7@example.com"
            "?bcc=l2g@nuxref.com"
        ),
        {
            # A good email with Blind Carbon Copy
            "instance": NotifyGroundmail,
        },
    ),
    (
        (
            "groundmail://abcd:user@example.com/newuser8@example.com"
            "?cc=l2g@nuxref.com"
        ),
        {
            # A good email with Carbon Copy
            "instance": NotifyGroundmail,
        },
    ),
    (
        (
            "groundmail://abcd:user@example.com/newuser8@example.com?"
            "cc=Chris<l2g@nuxref.com>"
        ),
        {
            # A good email with Carbon Copy + Name
            "instance": NotifyGroundmail,
        },
    ),
    (
        (
            "groundmail://abcd:user@example.com/newuser9@example.com"
            "?to=l2g@nuxref.com"
        ),
        {
            # A good email with an additional To
            "instance": NotifyGroundmail,
        },
    ),
    (
        "groundmail://abcd:user@example.com?format=text",
        {
            # plain-text format
            "instance": NotifyGroundmail,
        },
    ),
    (
        "groundmail://abcd:user@example.com/newuser@example.com",
        {
            # Groundmail may answer with a 201
            "instance": NotifyGroundmail,
            "requests_response_code": requests.codes.created,
        },
    ),
    (
        "groundmail://abcd:user@example.ca/newuser0@example.ca",
        {
            "instance": NotifyGroundmail,
            # force a failure
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "groundmail://abcd:user@example.uk/newuser01@example.uk",
        {
            "instance": NotifyGroundmail,
            # throw a bizarre code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "groundmail://abcd:user@example.au/newuser02@example.au",
        {
            "instance": NotifyGroundmail,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracefully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_groundmail_urls():
    """NotifyGroundmail() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.get")
@mock.patch("requests.post")
def test_plugin_groundmail_edge_cases(mock_post, mock_get):
    """NotifyGroundmail() Edge Cases."""

    # no apikey
    with pytest.raises(AppriseImproperlyConfigured):
        NotifyGroundmail(apikey=None, from_addr="user@example.com")

    # invalid from email
    with pytest.raises(AppriseImproperlyConfigured):
        NotifyGroundmail(apikey="abcd", from_addr="!invalid")

    # no email
    with pytest.raises(AppriseImproperlyConfigured):
        NotifyGroundmail(apikey="abcd", from_addr=None)

    # Invalid To email address
    obj = NotifyGroundmail(
        apikey="abcd", from_addr="user@example.com", targets="!invalid"
    )

    # Every target was dropped; nothing is sent
    assert len(obj.targets) == 0
    assert len(obj) == 1
    assert obj.notify(body="body") is False
    assert mock_post.call_count == 0

    # Test invalid bcc/cc entries mixed with good ones
    assert isinstance(
        NotifyGroundmail(
            apikey="abcd",
            from_addr="l2g@example.com",
            bcc=("abc@def.com", "!invalid"),
            cc=("abc@test.org", "!invalid"),
        ),
        NotifyGroundmail,
    )


@mock.patch("requests.post")
def test_plugin_groundmail_payload(mock_post):
    """NotifyGroundmail() Payload."""

    request = mock.Mock()
    request.status_code = requests.codes.ok
    request.content = b'{"id":"msg_794399cdfb1bfc21","status":"sent"}'
    mock_post.return_value = request

    obj = Apprise.instantiate(
        f"groundmail://{APIKEY}:user@example.com/to@example.com"
        "?name=Apprise%20Bot&cc=Chris<cc@example.com>,to@example.com"
        "&bcc=bcc@example.com,to@example.com"
        "&reply=Help<reply@example.com>"
    )
    assert isinstance(obj, NotifyGroundmail)
    assert obj.notify(body="<p>body</p>", title="title") is True
    assert mock_post.call_count == 1

    url, kwargs = mock_post.call_args[0][0], mock_post.call_args[1]
    assert url == "https://api.groundmail.dev/emails"

    headers = kwargs["headers"]
    assert headers["Authorization"] == f"Bearer {APIKEY}"
    assert headers["Content-Type"] == "application/json"
    assert headers["Idempotency-Key"]

    payload = loads(kwargs["data"])
    assert payload["from"] == "Apprise Bot <user@example.com>"
    assert payload["to"] == "to@example.com"
    assert payload["subject"] == "title"
    assert payload["html"] == "<p>body</p>"
    assert "body" in payload["text"]
    assert "<p>" not in payload["text"]

    # The target is never copied into its own cc or bcc
    assert payload["cc"] == ["Chris <cc@example.com>"]
    assert payload["bcc"] == ["bcc@example.com"]
    assert payload["reply_to"] == ["Help <reply@example.com>"]
    assert "attachments" not in payload

    mock_post.reset_mock()

    # Plain text input; html is generated from it
    obj = Apprise.instantiate(
        "groundmail://abcd:user@example.com/to@example.com?format=text"
    )
    assert obj.notify(body="line1\nline2") is True
    payload = loads(mock_post.call_args[1]["data"])
    assert payload["text"] == "line1\nline2"
    assert "line1" in payload["html"]
    assert payload["html"] != payload["text"]

    # No title uses the default subject
    assert payload["subject"] == NotifyGroundmail.default_empty_subject

    # A per-call body format overrides the URL default
    mock_post.reset_mock()
    obj = Apprise.instantiate("groundmail://abcd:user@example.com")
    assert obj.notify(body="plain", body_format=NotifyFormat.TEXT) is True
    payload = loads(mock_post.call_args[1]["data"])

    # Without targets the email goes to the From address
    assert payload["to"] == "user@example.com"
    assert "cc" not in payload
    assert "bcc" not in payload
    assert "reply_to" not in payload

    # Each target is sent separately with its own Idempotency-Key
    mock_post.reset_mock()
    obj = NotifyGroundmail(
        apikey="abcd",
        from_addr="user@example.com",
        targets=["t1@example.com", "t2@example.com"],
    )
    assert obj.notify(body="body") is True
    assert mock_post.call_count == 2
    first, second = mock_post.call_args_list
    assert loads(first[1]["data"])["to"] == "t1@example.com"
    assert loads(second[1]["data"])["to"] == "t2@example.com"
    assert (
        first[1]["headers"]["Idempotency-Key"]
        != second[1]["headers"]["Idempotency-Key"]
    )


@mock.patch("requests.post")
def test_plugin_groundmail_retry_keeps_idempotency_key(mock_post):
    """NotifyGroundmail() reuses its Idempotency-Key on a retry."""

    ok = mock.Mock()
    ok.status_code = requests.codes.ok
    ok.content = b""

    bad = mock.Mock()
    bad.status_code = requests.codes.service_unavailable
    bad.content = b""

    obj = NotifyGroundmail(
        apikey="abcd",
        from_addr="user@example.com",
        targets=["t1@example.com", "t2@example.com"],
    )

    # Retries turn on delivery marks and remembered values together
    token = _delivery_tracker.set(set())
    memo_token = _delivery_memo.set({})
    try:
        # The first target is accepted, the second is not
        mock_post.side_effect = [ok, bad]
        assert obj.send(body="body") is False
        assert mock_post.call_count == 2
        first_t2 = mock_post.call_args_list[1][1]["headers"]["Idempotency-Key"]

        # The retry only contacts the second target, with the same key
        mock_post.reset_mock()
        mock_post.side_effect = [ok]
        assert obj.send(body="body") is True
        assert mock_post.call_count == 1
        retry = mock_post.call_args_list[0][1]
        assert loads(retry["data"])["to"] == "t2@example.com"
        assert retry["headers"]["Idempotency-Key"] == first_t2

    finally:
        _delivery_tracker.reset(token)
        _delivery_memo.reset(memo_token)


@mock.patch("requests.get")
@mock.patch("requests.post")
def test_plugin_groundmail_attachments(mock_post, mock_get):
    """NotifyGroundmail() Attachments."""

    request = mock.Mock()
    request.status_code = requests.codes.ok
    request.content = b""

    # Prepare Mock
    mock_post.return_value = request
    mock_get.return_value = request

    path = os.path.join(TEST_VAR_DIR, "apprise-test.gif")
    attach = AppriseAttachment(path)
    obj = Apprise.instantiate("groundmail://abcd:user@example.com")
    assert isinstance(obj, NotifyGroundmail)
    assert (
        bool(
            obj.notify(
                body="body",
                title="title",
                notify_type=NotifyType.INFO,
                attach=attach,
            )
        )
        is True
    )

    payload = loads(mock_post.call_args[1]["data"])
    assert len(payload["attachments"]) == 1
    attachment = payload["attachments"][0]
    assert attachment["name"] == "apprise-test.gif"
    assert attachment["content_type"] == "image/gif"
    assert attachment["data"]

    mock_post.reset_mock()
    mock_get.reset_mock()

    # Multiple attachments
    attach = AppriseAttachment(
        [
            os.path.join(TEST_VAR_DIR, "apprise-test.gif"),
            os.path.join(TEST_VAR_DIR, "apprise-test.png"),
        ]
    )
    assert (
        bool(
            obj.notify(
                body="body",
                title="title",
                notify_type=NotifyType.INFO,
                attach=attach,
            )
        )
        is True
    )
    payload = loads(mock_post.call_args[1]["data"])
    assert [a["name"] for a in payload["attachments"]] == [
        "apprise-test.gif",
        "apprise-test.png",
    ]

    mock_post.reset_mock()

    # An attachment without a name is given one
    with mock.patch(
        "apprise.attachment.file.AttachFile.name",
        new_callable=mock.PropertyMock,
        return_value=None,
    ):
        assert (
            bool(
                obj.notify(
                    body="body",
                    title="title",
                    notify_type=NotifyType.INFO,
                    attach=AppriseAttachment(path),
                )
            )
            is True
        )
    payload = loads(mock_post.call_args[1]["data"])
    assert payload["attachments"][0]["name"] == "file001.dat"

    mock_post.reset_mock()

    # Try again in a use case where we can't access the file
    with mock.patch("os.path.isfile", return_value=False):
        assert (
            bool(
                obj.notify(
                    body="body",
                    title="title",
                    notify_type=NotifyType.INFO,
                    attach=attach,
                )
            )
            is False
        )

    # Try again in a use case where we can't access the file
    with mock.patch("builtins.open", side_effect=OSError):
        assert (
            bool(
                obj.notify(
                    body="body",
                    title="title",
                    notify_type=NotifyType.INFO,
                    attach=attach,
                )
            )
            is False
        )

    # Nothing was sent when an attachment could not be read
    assert mock_post.call_count == 0


def test_plugin_groundmail_url_parsing():
    """NotifyGroundmail() URL parsing."""

    # Valid round-trip
    obj = NotifyGroundmail(
        apikey=APIKEY,
        from_addr="Ops <sender@example.com>",
        targets=["to@example.com"],
        cc=["cc@example.com"],
        bcc=["bcc@example.com"],
        reply_to="reply@example.com",
    )
    url = obj.url()
    assert "cc=" in url
    assert "bcc=" in url
    assert "reply=" in url
    assert "name=Ops" in url

    result = NotifyGroundmail.parse_url(url)
    assert result is not None
    obj2 = NotifyGroundmail(**result)
    assert obj.url_identifier == obj2.url_identifier
    assert obj2.targets == ["to@example.com"]
    assert obj2.cc == {"cc@example.com"}
    assert obj2.bcc == {"bcc@example.com"}
    assert obj2.reply_to == {"reply@example.com"}

    # url() with privacy=True masks the API key
    assert APIKEY not in obj.url(privacy=True)

    # ?to= alias
    result = NotifyGroundmail.parse_url(
        "groundmail://abcd:user@example.com?to=extra@example.com"
    )
    assert result is not None
    assert "extra@example.com" in result["targets"]
