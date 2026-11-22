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

from helpers import AppriseURLTester
import requests

import apprise
from apprise import NotifyFormat, NotifyType
from apprise.exception import AppriseImproperlyConfigured
from apprise.plugins.nextmsg import NotifyNextMsg, nextmsg_unescape

logging.disable(logging.CRITICAL)

# Keys as the NextMsg app hands them out
SEND_KEY = "nextmsg_live_" + "0123456789abcdef" * 3
AGENT_KEY = "nextmsg_agent_" + "fedcba9876543210" * 3

# Our Testing URLs
apprise_url_tests = (
    (
        "nextmsg://",
        {
            # No key specified
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "nextmsg://:@/",
        {
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "nextmsg://invalid_key",
        {
            # A key that is not a NextMsg key
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "nextmsg://nextmsg_live_0123",
        {
            # A key that is too short
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "nextmsg://{}".format(SEND_KEY),
        {
            "instance": NotifyNextMsg,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "nextmsg://n...f/",
        },
    ),
    (
        # An agent key and a channel
        "nextmsg://{}/deploys".format(AGENT_KEY),
        {
            "instance": NotifyNextMsg,
            "privacy_url": "nextmsg://n...0/deploys",
        },
    ),
    (
        # An invalid channel
        "nextmsg://{}/not a channel!".format(SEND_KEY),
        {
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        # Our key and channel provided as query arguments
        "nextmsg://?key={}&channel=ci".format(SEND_KEY),
        {
            "instance": NotifyNextMsg,
            "privacy_url": "nextmsg://n...f/ci",
        },
    ),
    (
        # Native URL
        "https://api.nextmsg.app/p/{}".format(SEND_KEY),
        {
            "instance": NotifyNextMsg,
        },
    ),
    (
        # Native URL with a channel
        "https://api.nextmsg.app/p/{}/?channel=backups".format(SEND_KEY),
        {
            "instance": NotifyNextMsg,
        },
    ),
    (
        "nextmsg://{}".format(SEND_KEY),
        {
            "instance": NotifyNextMsg,
            # Throw a bizarre code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "nextmsg://{}".format(SEND_KEY),
        {
            "instance": NotifyNextMsg,
            # A revoked key
            "response": False,
            "requests_response_code": requests.codes.unauthorized,
        },
    ),
    (
        "nextmsg://{}".format(SEND_KEY),
        {
            "instance": NotifyNextMsg,
            # Throws a series of i/o exceptions with this flag set and tests
            # that we gracefully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_nextmsg_urls():
    """NotifyNextMsg() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


def test_plugin_nextmsg_init():
    """NotifyNextMsg() rejects a bad key or channel."""

    # A missing key
    result = NotifyNextMsg.parse_url(f"nextmsg://{SEND_KEY}")
    result["apikey"] = None
    assert apprise.Apprise.instantiate(result) is None

    # A channel that is too long
    result = NotifyNextMsg.parse_url(f"nextmsg://{SEND_KEY}/{'a' * 33}")
    assert apprise.Apprise.instantiate(result) is None

    # A key typed in uppercase still works and is sent in lowercase
    obj = apprise.Apprise.instantiate(f"nextmsg://{SEND_KEY.upper()}/CI")
    assert isinstance(obj, NotifyNextMsg)
    assert obj.apikey == SEND_KEY
    assert obj.channel == "ci"


@mock.patch("requests.post")
def test_plugin_nextmsg_payload(mock_post):
    """NotifyNextMsg() builds the expected request."""

    # Prepare our response
    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = dumps(
        {"success": True, "id": "0196...", "status": "queued"}
    ).encode("utf-8")
    mock_post.return_value = response

    obj = apprise.Apprise.instantiate(f"nextmsg://{AGENT_KEY}/deploys")
    assert isinstance(obj, NotifyNextMsg)

    # The title is sent in bold on the first line
    assert obj.notify(
        title="Deploy",
        body="Version 2.4 is *live*",
        notify_type=NotifyType.SUCCESS,
    )

    assert mock_post.call_count == 1
    assert mock_post.call_args[0][0] == "https://api.nextmsg.app/v1/send"
    headers = mock_post.call_args[1]["headers"]
    assert headers["Authorization"] == f"Bearer {AGENT_KEY}"
    assert headers["Content-Type"] == "application/json"

    payload = loads(mock_post.call_args[1]["data"])
    assert payload == {
        "message": "**Deploy**\nVersion 2.4 is *live*",
        "channel": "deploys",
    }

    # Our settings survive a round trip
    obj2 = apprise.Apprise.instantiate(obj.url())
    assert obj2.url_identifier == obj.url_identifier
    assert obj2.channel == "deploys"

    mock_post.reset_mock()

    # Without a title or a channel, only the message is sent
    obj = apprise.Apprise.instantiate(f"nextmsg://{SEND_KEY}")
    assert obj.notify(body="body")

    payload = loads(mock_post.call_args[1]["data"])
    assert payload == {"message": "body"}

    # Our settings survive a round trip
    obj2 = apprise.Apprise.instantiate(obj.url())
    assert obj2.channel is None
    assert obj2.apikey == SEND_KEY


@mock.patch("requests.post")
def test_plugin_nextmsg_formats(mock_post):
    """NotifyNextMsg() sends Markdown as is and converts HTML."""

    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = b"{}"
    mock_post.return_value = response

    obj = apprise.Apprise.instantiate(f"nextmsg://{SEND_KEY}")
    assert obj.notify_format == NotifyFormat.MARKDOWN

    # Markdown arrives as typed
    assert obj.notify(
        body="**bold** and `code`", body_format=NotifyFormat.MARKDOWN
    )
    payload = loads(mock_post.call_args[1]["data"])
    assert payload["message"] == "**bold** and `code`"

    # Plain text keeps its asterisks: they are escaped, not made bold
    assert obj.notify(body="2 * 3 = **6**", body_format=NotifyFormat.TEXT)
    payload = loads(mock_post.call_args[1]["data"])
    assert payload["message"] == "2 \\* 3 = \\*\\*6\\*\\*"

    # Other punctuation arrives without the backslashes CommonMark adds
    assert obj.notify(
        body="v1.2-beta done! (see #42) a_b", body_format=NotifyFormat.TEXT
    )
    payload = loads(mock_post.call_args[1]["data"])
    assert payload["message"] == "v1.2-beta done! (see #42) a_b"

    # A backslash in plain text stays one backslash on the phone
    assert obj.notify(body="C:\\temp", body_format=NotifyFormat.TEXT)
    payload = loads(mock_post.call_args[1]["data"])
    assert payload["message"] == "C:\\\\temp"

    # Markers in the title are shown as typed, inside the bold
    assert obj.notify(
        title="2*3", body="ok", body_format=NotifyFormat.MARKDOWN
    )
    payload = loads(mock_post.call_args[1]["data"])
    assert payload["message"] == "**2\\*3**\nok"

    # HTML is converted, so no tags reach the phone
    assert obj.notify(body="<b>bold</b>", body_format=NotifyFormat.HTML)
    payload = loads(mock_post.call_args[1]["data"])
    assert "<b>" not in payload["message"]
    assert "bold" in payload["message"]


@mock.patch("requests.post")
def test_plugin_nextmsg_errors(mock_post):
    """NotifyNextMsg() fails on every NextMsg error."""

    obj = apprise.Apprise.instantiate(f"nextmsg://{SEND_KEY}")

    for code in (400, 401, 402, 413, 429, 500, 503):
        response = mock.Mock()
        response.status_code = code
        response.content = dumps({"error": "nope"}).encode("utf-8")
        mock_post.return_value = response
        assert not obj.notify(body="body")


def test_plugin_nextmsg_native_url():
    """NotifyNextMsg() reads the quick URL from the app."""

    result = NotifyNextMsg.parse_native_url(
        f"https://api.nextmsg.app/p/{SEND_KEY}?channel=ci#fragment"
    )
    assert result["apikey"] == SEND_KEY
    assert result["channel"] == "ci"

    # Agent keys never work in a URL, so they are not native URLs
    assert (
        NotifyNextMsg.parse_native_url(
            f"https://api.nextmsg.app/p/{AGENT_KEY}"
        )
        is None
    )

    # Another host is not ours
    assert (
        NotifyNextMsg.parse_native_url(f"https://example.com/p/{SEND_KEY}")
        is None
    )


def test_plugin_nextmsg_unescape():
    """nextmsg_unescape() keeps only the escapes NextMsg understands."""

    # Escapes NextMsg doesn't know are removed
    assert nextmsg_unescape(r"v1\.2\-beta \_x\_ \[a\](b) \#1 \!") == (
        "v1.2-beta _x_ [a](b) #1 !"
    )

    # Escapes NextMsg understands stay
    assert nextmsg_unescape(r"\*a\* \~\~b\~\~ \`c\` \\") == (
        r"\*a\* \~\~b\~\~ \`c\` \\"
    )

    # An escaped backslash followed by an escaped dot
    assert nextmsg_unescape(r"a \\\. b") == r"a \\. b"

    # A backslash before a letter is not an escape
    assert nextmsg_unescape(r"C:\temp") == r"C:\temp"
