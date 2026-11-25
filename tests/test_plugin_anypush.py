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
from json import dumps, loads
import logging
from unittest import mock
from uuid import UUID

from helpers import AppriseURLTester
import pytest
import requests

import apprise
from apprise import Apprise, NotifyType
from apprise.exception import AppriseImproperlyConfigured
from apprise.plugins.anypush import AnypushPriority, NotifyAnypush

logging.disable(logging.CRITICAL)

# A made up channel token (base32, 24 characters); never a real one
TOKEN = "abcdefghijklmnopqrstuvwx"

# The longest token anypush hands out (52 characters)
LONG_TOKEN = "abcdefghijklmnopqrstuvwxyz234567abcdefghijklmnopqrst"

# Our Testing URLs
apprise_url_tests = (
    (
        "anypush://",
        {
            # No token specified
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "anypush://:@/",
        {
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        # One character too short
        "anypush://{}".format(TOKEN[:-1]),
        {
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        # One character too long
        "anypush://{}a".format(LONG_TOKEN),
        {
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        # 0, 1, 8 and 9 are not base32 characters
        "anypush://{}0189".format(TOKEN[:-4]),
        {
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "anypush://{}".format(TOKEN),
        {
            "instance": NotifyAnypush,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "anypush://a...x/",
        },
    ),
    (
        # The longest token
        "anypush://{}".format(LONG_TOKEN),
        {
            "instance": NotifyAnypush,
            "privacy_url": "anypush://a...t/",
        },
    ),
    (
        # A token typed in uppercase is accepted
        "anypush://{}".format(TOKEN.upper()),
        {
            "instance": NotifyAnypush,
            "privacy_url": "anypush://a...x/",
        },
    ),
    (
        # Our token provided as a query argument
        "anypush://?token={}".format(TOKEN),
        {
            "instance": NotifyAnypush,
            "privacy_url": "anypush://a...x/",
        },
    ),
    (
        # Our options
        "anypush://{}?priority=high&url=https://example.com/logs/42".format(
            TOKEN
        ),
        {
            "instance": NotifyAnypush,
        },
    ),
    (
        # An unknown priority
        "anypush://{}?priority=invalid".format(TOKEN),
        {
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        # The tap address must be http or https
        "anypush://{}?url=ftp://example.com/".format(TOKEN),
        {
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        # Native URL
        "https://anypush.app/h/{}".format(TOKEN),
        {
            "instance": NotifyAnypush,
            "privacy_url": "anypush://a...x/",
        },
    ),
    (
        # Native URL with a trailing slash and our options
        "https://anypush.app/h/{}/?priority=low".format(TOKEN),
        {
            "instance": NotifyAnypush,
        },
    ),
    (
        "anypush://{}".format(TOKEN),
        {
            "instance": NotifyAnypush,
            # anypush answers 202 when it kept the message
            "requests_response_code": requests.codes.accepted,
        },
    ),
    (
        "anypush://{}".format(TOKEN),
        {
            "instance": NotifyAnypush,
            # Throw a bizarre code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "anypush://{}".format(TOKEN),
        {
            "instance": NotifyAnypush,
            # No channel at this address
            "response": False,
            "requests_response_code": requests.codes.not_found,
        },
    ),
    (
        "anypush://{}".format(TOKEN),
        {
            "instance": NotifyAnypush,
            # Too many messages
            "response": False,
            "requests_response_code": requests.codes.too_many_requests,
        },
    ),
    (
        "anypush://{}".format(TOKEN),
        {
            "instance": NotifyAnypush,
            # Briefly unavailable
            "response": False,
            "requests_response_code": requests.codes.service_unavailable,
        },
    ),
    (
        "anypush://{}".format(TOKEN),
        {
            "instance": NotifyAnypush,
            # Throws a series of i/o exceptions with this flag set and tests
            # that we gracefully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_anypush_urls():
    """NotifyAnypush() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@pytest.mark.parametrize(
    "word, expected",
    (
        ("low", AnypushPriority.LOW),
        ("min", AnypushPriority.LOW),
        ("l", AnypushPriority.LOW),
        ("m", AnypushPriority.LOW),
        ("normal", AnypushPriority.NORMAL),
        ("default", AnypushPriority.NORMAL),
        ("moderate", AnypushPriority.NORMAL),
        ("mo", AnypushPriority.NORMAL),
        ("n", AnypushPriority.NORMAL),
        ("high", AnypushPriority.HIGH),
        ("max", AnypushPriority.HIGH),
        ("ma", AnypushPriority.HIGH),
        ("urgent", AnypushPriority.HIGH),
        ("emergency", AnypushPriority.HIGH),
        ("e", AnypushPriority.HIGH),
        (" HIGH ", AnypushPriority.HIGH),
    ),
)
def test_plugin_anypush_priority(word, expected):
    """NotifyAnypush() maps priority words onto low, normal and high."""

    obj = NotifyAnypush(token=TOKEN, priority=word)
    assert obj.priority == expected

    # The priority survives a round trip as one of the three words
    obj2 = Apprise.instantiate(obj.url())
    assert obj2.priority == expected
    assert f"priority={expected}" in obj.url()


def test_plugin_anypush_init():
    """NotifyAnypush() defaults and rejected values."""

    # Our defaults
    obj = NotifyAnypush(token=TOKEN.upper())
    assert obj.token == TOKEN
    assert obj.priority == AnypushPriority.NORMAL
    assert obj.click is None
    assert len(obj) == 1

    # An empty priority is the default one
    assert NotifyAnypush(token=TOKEN, priority="").priority == "normal"

    # A priority that is not a word
    with pytest.raises(AppriseImproperlyConfigured):
        NotifyAnypush(token=TOKEN, priority=5)

    # A tap address that is not a web address
    with pytest.raises(AppriseImproperlyConfigured):
        NotifyAnypush(token=TOKEN, click="example.com")

    # A token of the wrong type
    with pytest.raises(AppriseImproperlyConfigured):
        NotifyAnypush(token=None)


def test_plugin_anypush_native_url():
    """NotifyAnypush() reads a channel address and nothing else."""

    for url in (
        "https://anypush.app/h/{}".format(TOKEN),
        "https://anypush.app/h/{}/".format(TOKEN),
        "https://ANYPUSH.app/h/{}".format(TOKEN.upper()),
        "https://anypush.app/h/{}#fragment".format(TOKEN),
    ):
        result = NotifyAnypush.parse_native_url(url)
        assert result is not None, url
        obj = Apprise.instantiate(result)
        assert isinstance(obj, NotifyAnypush)
        assert obj.token == TOKEN

    # Options carried on the address are read too
    result = NotifyAnypush.parse_native_url(
        "https://anypush.app/h/{}?priority=urgent".format(TOKEN)
    )
    assert NotifyAnypush(**result).priority == AnypushPriority.HIGH

    for url in (
        # A job's exit status is a different request
        "https://anypush.app/h/{}/0".format(TOKEN),
        # The status of a message is not a channel
        "https://anypush.app/h/{}/messages/1042".format(TOKEN),
        # Another host
        "https://example.com/h/{}".format(TOKEN),
        # Too short to be a token
        "https://anypush.app/h/{}".format(TOKEN[:-1]),
    ):
        assert NotifyAnypush.parse_native_url(url) is None, url

    # The address loads through Apprise as is
    obj = Apprise.instantiate("https://anypush.app/h/{}".format(TOKEN))
    assert isinstance(obj, NotifyAnypush)
    assert obj.url_identifier == ("anypush", TOKEN)


@mock.patch("requests.post")
def test_plugin_anypush_payload(mock_post):
    """NotifyAnypush() builds the expected request."""

    # Prepare our response
    response = mock.Mock()
    response.status_code = requests.codes.accepted
    response.content = dumps(
        {
            "id": 1042,
            "duplicate": False,
            "status_url": "https://anypush.app/h/{}/messages/1042".format(
                TOKEN
            ),
        }
    ).encode("utf-8")
    mock_post.return_value = response

    obj = Apprise.instantiate(
        "anypush://{}?priority=high&url={}".format(
            TOKEN,
            NotifyAnypush.quote("https://example.com/logs/42?a=1&b=%20"),
        )
    )
    assert isinstance(obj, NotifyAnypush)

    # Plain text arrives as typed
    assert obj.notify(
        title="nightly-backup",
        body="Backup failed on *nas* <1> & done",
        notify_type=NotifyType.FAILURE,
    )

    assert mock_post.call_count == 1
    assert mock_post.call_args[0][0] == "https://anypush.app/h/{}".format(
        TOKEN
    )

    headers = mock_post.call_args[1]["headers"]
    assert headers["User-Agent"] == "anypush-apprise/{}".format(
        apprise.__version__
    )
    assert headers["Content-Type"] == "application/json"
    # A key is set for each message
    assert UUID(headers["Idempotency-Key"])

    payload = loads(mock_post.call_args[1]["data"])
    assert payload == {
        "message": "Backup failed on *nas* <1> & done",
        "title": "nightly-backup",
        "priority": "high",
        "url": "https://example.com/logs/42?a=1&b=%20",
    }

    # Our settings survive a round trip
    obj2 = Apprise.instantiate(obj.url())
    assert obj2.url_identifier == obj.url_identifier
    assert obj2.priority == "high"
    assert obj2.click == "https://example.com/logs/42?a=1&b=%20"

    mock_post.reset_mock()

    # Now with our defaults and no title
    obj = Apprise.instantiate("anypush://{}".format(TOKEN))
    assert obj.notify(body="body")

    payload = loads(mock_post.call_args[1]["data"])
    assert payload == {"message": "body", "priority": "normal"}

    # Every message gets a key of its own
    first = mock_post.call_args[1]["headers"]["Idempotency-Key"]
    assert obj.notify(body="body")
    second = mock_post.call_args[1]["headers"]["Idempotency-Key"]
    assert first != second

    # A plain 200 is a success too
    response.status_code = requests.codes.ok
    response.content = b""
    assert obj.notify(body="body")


@mock.patch("requests.post")
def test_plugin_anypush_retry_key(mock_post):
    """NotifyAnypush() keeps its Idempotency-Key across retries."""

    busy = mock.Mock()
    busy.status_code = requests.codes.service_unavailable
    busy.content = b""
    kept = mock.Mock()
    kept.status_code = requests.codes.accepted
    kept.content = b'{"id": 1, "duplicate": false}'
    mock_post.side_effect = [busy, kept]

    aobj = Apprise()
    assert aobj.add("anypush://{}?retry=1&wait=0".format(TOKEN))
    with mock.patch("apprise.apprise.time.sleep"):
        assert aobj.notify(body="Backup failed on nas")

    # The retry reused the key, so anypush shows the message once
    assert mock_post.call_count == 2
    first = mock_post.call_args_list[0][1]["headers"]["Idempotency-Key"]
    second = mock_post.call_args_list[1][1]["headers"]["Idempotency-Key"]
    assert first == second


@mock.patch("requests.post")
def test_plugin_anypush_token_never_logged(mock_post):
    """NotifyAnypush() keeps the channel token out of its logs."""

    with mock.patch.object(NotifyAnypush, "logger") as mock_logger:
        # A mistyped token is still most of a secret
        with pytest.raises(AppriseImproperlyConfigured):
            NotifyAnypush(token=TOKEN + "1")

        obj = NotifyAnypush(token=TOKEN)

        # anypush quotes the channel address in its answers
        response = mock.Mock()
        response.status_code = requests.codes.accepted
        response.content = dumps(
            {
                "id": 1042,
                "status_url": "https://anypush.app/h/{}/messages/1".format(
                    TOKEN
                ),
            }
        ).encode("utf-8")
        mock_post.return_value = response
        assert obj.notify(body="body")

        # An error page could do the same
        response.status_code = requests.codes.not_found
        response.content = "No channel at /h/{}".format(TOKEN).encode("utf-8")
        assert not obj.notify(body="body")

        # So does a connection error
        mock_post.side_effect = requests.ConnectionError(
            "HTTPSConnectionPool(host='anypush.app', port=443): Max retries"
            " exceeded with url: /h/{}".format(TOKEN)
        )
        assert not obj.notify(body="body")

    # Our logger was used, and the token appears in none of its calls
    assert mock_logger.mock_calls
    for call in mock_logger.mock_calls:
        assert TOKEN not in str(call)

    # Text is masked as well as bytes
    assert obj._redact("/h/{}".format(TOKEN)) == "/h/a...x"
