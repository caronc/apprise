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
from hashlib import sha256
import hmac
import json
import logging
from unittest import mock
from urllib.parse import parse_qs, urlparse

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise, NotifyType
from apprise.exception import AppriseImproperlyConfigured
from apprise.plugins.nextcloudtalk import NotifyNextcloudTalk

logging.disable(logging.CRITICAL)

apprise_url_tests = (
    ##################################
    # NotifyNextcloudTalk
    ##################################
    (
        "nctalk://:@/",
        {
            "instance": None,
        },
    ),
    (
        "nctalk://",
        {
            "instance": None,
        },
    ),
    (
        "nctalks://",
        {
            # No hostname
            "instance": None,
        },
    ),
    (
        "nctalk://localhost",
        {
            # No user and password and roomid specified
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "nctalk://localhost/roomid",
        {
            # No user and password specified
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "nctalk://user@localhost/roomid",
        {
            # No password specified
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "nctalk://user:pass@localhost",
        {
            # No roomid specified
            "instance": NotifyNextcloudTalk,
            # Since there are no targets specified we expect a False return on
            # send()
            "notify_response": False,
        },
    ),
    (
        "nctalk://user:pass@localhost/roomid1/roomid2",
        {
            "instance": NotifyNextcloudTalk,
            "requests_response_code": requests.codes.created,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "nctalk://user:****@localhost/roomid1/roomid2",
        },
    ),
    (
        "nctalk://user:pass@localhost:8080/roomid",
        {
            "instance": NotifyNextcloudTalk,
            "requests_response_code": requests.codes.created,
        },
    ),
    (
        "nctalk://user:pass@localhost:8080/roomid?url_prefix=/prefix",
        {
            "instance": NotifyNextcloudTalk,
            "requests_response_code": requests.codes.created,
        },
    ),
    (
        "nctalks://user:pass@localhost/roomid",
        {
            "instance": NotifyNextcloudTalk,
            "requests_response_code": requests.codes.created,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "nctalks://user:****@localhost/roomid",
        },
    ),
    (
        "nctalks://user:pass@localhost:8080/roomid/",
        {
            "instance": NotifyNextcloudTalk,
            "requests_response_code": requests.codes.created,
        },
    ),
    (
        "nctalk://user:pass@localhost:8080/roomid?+HeaderKey=HeaderValue",
        {
            "instance": NotifyNextcloudTalk,
            "requests_response_code": requests.codes.created,
        },
    ),
    (
        "nctalk://user:pass@localhost:8081/roomid",
        {
            "instance": NotifyNextcloudTalk,
            # force a failure
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "nctalk://user:pass@localhost:8082/roomid",
        {
            "instance": NotifyNextcloudTalk,
            # throw a bizarre code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "nctalk://user:pass@localhost:8083/roomid1/roomid2/roomid3",
        {
            "instance": NotifyNextcloudTalk,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracefully handle them
            "test_requests_exceptions": True,
        },
    ),
    (
        "nctalk://localhost/roomid?secret=",
        {
            # An empty secret with no user and password
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "nctalk://localhost?secret=abcd",
        {
            # Bot mode with no roomid specified
            "instance": NotifyNextcloudTalk,
            "notify_response": False,
        },
    ),
    (
        "nctalks://localhost/roomid1/roomid2?secret=abcd",
        {
            "instance": NotifyNextcloudTalk,
            "requests_response_code": requests.codes.created,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "nctalks://localhost/roomid1/roomid2",
        },
    ),
    (
        "nctalk://localhost:8081/roomid?secret=abcd",
        {
            "instance": NotifyNextcloudTalk,
            # force a failure
            "response": False,
            "requests_response_code": requests.codes.unauthorized,
        },
    ),
    (
        "nctalk://localhost:8082/roomid?secret=abcd",
        {
            "instance": NotifyNextcloudTalk,
            # throw a bizarre code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "nctalk://localhost:8083/roomid1/roomid2?secret=abcd",
        {
            "instance": NotifyNextcloudTalk,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracefully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_nextcloudtalk_urls():
    """NotifyNextcloudTalk() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.post")
def test_plugin_nextcloudtalk_edge_cases(mock_post):
    """NotifyNextcloudTalk() Edge Cases."""

    # A response
    robj = mock.Mock()
    robj.content = ""
    robj.status_code = requests.codes.created

    # Prepare Mock
    mock_post.return_value = robj

    # Variation Initializations
    obj = NotifyNextcloudTalk(
        host="localhost", user="admin", password="pass", targets="roomid"
    )
    assert isinstance(obj, NotifyNextcloudTalk) is True
    assert isinstance(obj.url(), str) is True

    # An empty body
    assert obj.send(body="") is True
    assert "data" in mock_post.call_args_list[0][1]
    assert "message" in mock_post.call_args_list[0][1]["data"]


@mock.patch("requests.post")
def test_plugin_nextcloud_talk_url_prefix(mock_post):
    """NotifyNextcloudTalk() URL Prefix Testing."""

    response = mock.Mock()
    response.content = ""
    response.status_code = requests.codes.created

    # Prepare our mock object
    mock_post.return_value = response

    # instantiate our object (without a batch mode)
    obj = Apprise.instantiate(
        "nctalk://user:pass@localhost/admin/?url_prefix=/abcd"
    )

    assert (
        bool(
            obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        )
        is True
    )

    # Not set to batch, so we send 2 different messages
    assert mock_post.call_count == 1
    assert (
        mock_post.call_args_list[0][0][0]
        == "http://localhost/abcd/ocs/v2.php/apps/spreed/api/v1/chat/admin"
    )

    mock_post.reset_mock()

    # instantiate our object (without a batch mode)
    obj = Apprise.instantiate(
        "nctalk://user:pass@localhost/admin/?url_prefix=a/longer/path/abcd/"
    )

    assert (
        bool(
            obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        )
        is True
    )

    # Not set to batch, so we send 2 different messages
    assert mock_post.call_count == 1
    assert (
        mock_post.call_args_list[0][0][0]
        == "http://localhost/a/longer/path/abcd/"
        "ocs/v2.php/apps/spreed/api/v1/chat/admin"
    )


@pytest.mark.parametrize(
    "body,title", [("Hello \u4e16\u754c", "Task"), ("", "Done"), ("", "")]
)
@mock.patch("requests.post")
def test_plugin_nextcloud_talk_bot_signature(mock_post, body, title):
    """Bot authentication signs the message, not its JSON serialization."""
    mock_post.return_value.status_code = requests.codes.created
    secret = "test-bot-secret"
    obj = NotifyNextcloudTalk(
        host="localhost",
        secret=secret,
        targets="room1",
        url_prefix="nextcloud",
    )
    assert obj.send(body=body, title=title)
    args, kwargs = mock_post.call_args
    assert args[0].endswith(
        "/nextcloud/ocs/v2.php/apps/spreed/api/v1/bot/room1/message"
    )
    assert kwargs["auth"] is None
    message = json.loads(kwargs["data"])["message"]
    headers = kwargs["headers"]
    random = headers["X-Nextcloud-Talk-Bot-Random"]
    assert len(random) == 64
    expected = hmac.new(
        secret.encode(), (random + message).encode(), sha256
    ).hexdigest()
    assert headers["X-Nextcloud-Talk-Bot-Signature"] == expected
    assert headers["OCS-APIRequest"] == "true"


def test_plugin_nextcloud_talk_bot_url():
    """Bot secrets survive URL encoding and are hidden in privacy output."""
    obj = NotifyNextcloudTalk(
        host="localhost", secret="a+b&c/%2Ftest", targets="room1"
    )
    restored = Apprise.instantiate(obj.url())
    assert restored.secret == obj.secret
    assert restored.targets == obj.targets
    assert restored.url_identifier == obj.url_identifier
    assert parse_qs(urlparse(obj.url(privacy=True)).query)["secret"] == [
        "****"
    ]
    assert obj.secret not in obj.url(privacy=True)
    assert Apprise.instantiate("nctalk://localhost/room1?secret=") is None


@mock.patch("requests.post")
def test_plugin_nextcloud_talk_bot_retry(mock_post):
    """Accepted rooms are not sent a second copy during a retry."""
    accepted = mock.Mock(status_code=201)
    rejected = mock.Mock(status_code=401, content=b"unauthorized")
    mock_post.side_effect = [accepted, rejected, accepted]
    obj = NotifyNextcloudTalk(
        host="localhost",
        secret="secret",
        targets="room1,room2",
        retry=1,
        wait=0,
    )
    app = Apprise()
    app.add(obj)
    assert bool(app.notify(body="hello"))
    assert mock_post.call_count == 3
    assert [c.args[0].split("/")[-2] for c in mock_post.call_args_list] == [
        "room1",
        "room2",
        "room2",
    ]


@mock.patch("requests.post")
def test_plugin_nextcloud_talk_user_auth(mock_post):
    """Password URLs still use the chat API and Basic authentication."""
    mock_post.return_value.status_code = requests.codes.created
    obj = Apprise.instantiate("nctalk://user:password@localhost/room1")
    assert obj.send(body="hello")
    assert mock_post.call_args.args[0].endswith("/chat/room1")
    assert mock_post.call_args.kwargs["auth"] == ("user", "password")
    assert (
        "X-Nextcloud-Talk-Bot-Signature"
        not in mock_post.call_args.kwargs["headers"]
    )


def test_plugin_nextcloud_talk_bot_identity():
    """A bot URL with a user and password keeps its identity on reload."""
    obj = Apprise.instantiate("nctalks://user:pass@localhost/room?secret=abc")
    restored = Apprise.instantiate(obj.url())
    assert restored.url_identifier == obj.url_identifier


@mock.patch("requests.post")
def test_plugin_nextcloud_talk_no_prefix(mock_post):
    """Without a url_prefix the API path has no double slash."""
    mock_post.return_value.status_code = requests.codes.created
    obj = Apprise.instantiate("nctalk://user:pass@localhost/room1")
    assert obj.send(body="hello")
    assert (
        mock_post.call_args.args[0]
        == "http://localhost/ocs/v2.php/apps/spreed/api/v1/chat/room1"
    )


@mock.patch("requests.post")
def test_plugin_nextcloud_talk_silent(mock_post):
    """The silent flag is sent only when requested and survives a reload."""
    mock_post.return_value.status_code = requests.codes.created

    # Silent messages carry the flag
    obj = Apprise.instantiate(
        "nctalks://localhost/room1?secret=abc&silent=yes"
    )
    assert obj.silent is True
    assert obj.send(body="hello")
    assert json.loads(mock_post.call_args.kwargs["data"])["silent"] is True
    assert Apprise.instantiate(obj.url()).silent is True

    # Regular messages leave the payload unchanged
    obj = Apprise.instantiate("nctalk://user:pass@localhost/room1")
    assert obj.silent is False
    assert obj.send(body="hello")
    assert "silent" not in json.loads(mock_post.call_args.kwargs["data"])


def test_plugin_nextcloud_talk_body_maxlen():
    """The title shares the 32000 character message limit with the body."""
    obj = NotifyNextcloudTalk(host="localhost", secret="abc", targets="room")
    assert obj.body_maxlen == 32000
    assert obj.overflow_amalgamate_title is True
