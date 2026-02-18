# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2025, Chris Caron <lead2gold@gmail.com>
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

import json

# Disable logging for a cleaner testing output
import logging

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise
from apprise.plugins.mattermost import MattermostMode, NotifyMattermost

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    ("mmost://", {"instance": None}),
    ("mmosts://", {"instance": None}),
    ("mmost://:@/", {"instance": None}),
    (
        "mmosts://localhost",
        {
            # Thrown because there was no webhook id specified
            "instance": TypeError,
        },
    ),
    (
        "mmost://localhost/3ccdd113474722377935511fc85d3dd4",
        {
            "instance": NotifyMattermost,
        },
    ),
    (
        (
            "mmost://localhost/3ccdd113474722377935511fc85d3dd4"
            "?icon_url=http://localhost/test.png"
        ),
        {
            "instance": NotifyMattermost,
        },
    ),
    (
        "mmost://user@localhost/3ccdd113474722377935511fc85d3dd4?channel=test",
        {
            "instance": NotifyMattermost,
        },
    ),
    (
        (
            "mmost://user@localhost/3ccdd113474722377935511fc85d3dd4"
            "?channels=test"
        ),
        {
            "instance": NotifyMattermost,
        },
    ),
    (
        "mmost://user@localhost/3ccdd113474722377935511fc85d3dd4?to=test",
        {
            "instance": NotifyMattermost,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "mmost://user@localhost/3...4/",
        },
    ),
    (
        (
            "mmost://localhost/3ccdd113474722377935511fc85d3dd4"
            "?to=test&image=True"
        ),
        {"instance": NotifyMattermost},
    ),
    (
        (
            # Team defined implies bot mode
            "mmost://localhost/3ccdd113474722377935511fc85d3dd4"
            "?to=test&team=chester"
        ),
        {"instance": NotifyMattermost},
    ),
    (
        (
            "mmost://team@localhost/3ccdd113474722377935511fc85d3dd4"
            "?channel=$!garbag3^&mode=bot"
        ),
        {
            "instance": NotifyMattermost,
            # We will fail to notify anyone due to the bad entry
            "notify_response": False,
        },
    ),
    (
        (
            "mmost://localhost/3ccdd113474722377935511fc85d3dd4"
            "?to=test&image=False"
        ),
        {"instance": NotifyMattermost},
    ),
    (
        (
            "mmost://localhost/3ccdd113474722377935511fc85d3dd4"
            "?to=test&image=True"
        ),
        {
            "instance": NotifyMattermost,
            # don't include an image by default
            "include_image": False,
        },
    ),
    (
        "mmost://localhost:8080/3ccdd113474722377935511fc85d3dd4",
        {
            "instance": NotifyMattermost,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "mmost://localhost:8080/3...4/",
        },
    ),
    (
        "mmost://localhost:8080/3ccdd113474722377935511fc85d3dd4",
        {
            "instance": NotifyMattermost,
        },
    ),
    (
        "mmost://localhost:invalid-port/3ccdd113474722377935511fc85d3dd4",
        {
            "instance": None,
        },
    ),
    (
        "mmosts://localhost/3ccdd113474722377935511fc85d3dd4",
        {
            "instance": NotifyMattermost,
        },
    ),
    (
        (
            "https://mattermost.example.com/hooks/"
            "3ccdd113474722377935511fc85d3dd4"
        ),
        {
            "instance": NotifyMattermost,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "mmosts://mattermost.example.com/3...4/",
        },
    ),
    # Test our paths
    ("mmosts://localhost/a/path/3ccdd113474722377935511fc85d3dd4", {
        "instance": NotifyMattermost}),
    ("mmosts://localhost/////3ccdd113474722377935511fc85d3dd4///", {
        "instance": NotifyMattermost}),

    # Mode parsing (prefix support)
    ("mmost://localhost/token?mode=w", {"instance": NotifyMattermost}),
    ("mmost://localhost/token?mode=b&to=channel-id-1", {
        "instance": NotifyMattermost}),
    (
        "mmost://localhost/token?mode=invalid",
        {
            # invalid mode is detected in __init__
            "instance": TypeError,
        },
    ),
    (
        "mmosts://localhost/a/path/3ccdd113474722377935511fc85d3dd4",
        {
            "instance": NotifyMattermost,
        },
    ),
    (
        "mmosts://localhost/////3ccdd113474722377935511fc85d3dd4///",
        {
            "instance": NotifyMattermost,
        },
    ),
    (
        "mmost://localhost/3ccdd113474722377935511fc85d3dd4",
        {
            "instance": NotifyMattermost,
            # force a failure
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "mmost://localhost/3ccdd113474722377935511fc85d3dd4",
        {
            "instance": NotifyMattermost,
            # throw a bizarre code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "mmost://localhost/3ccdd113474722377935511fc85d3dd4",
        {
            "instance": NotifyMattermost,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracefully handle them
            "test_requests_exceptions": True,
        },
    ),
)


@pytest.fixture
def request_get_mock(mocker):
    """Prepare requests.get mock."""
    mock_get = mocker.patch("requests.get")
    mock_get.return_value = requests.Request()
    mock_get.return_value.status_code = requests.codes.ok
    mock_get.return_value.content = b'{"id":"abc123"}'
    return mock_get


@pytest.fixture
def request_post_mock(mocker):
    """Prepare requests mock."""
    mock_post = mocker.patch("requests.post")
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok
    mock_post.return_value.content = b""
    return mock_post


def test_plugin_mattermost_urls():
    """NotifyMattermost() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


def test_plugin_mattermost_edge_cases():
    """NotifyMattermost() Edge Cases."""

    # Invalid Authorization Token
    with pytest.raises(TypeError):
        NotifyMattermost(None)
    with pytest.raises(TypeError):
        NotifyMattermost("     ")


def test_plugin_mattermost_len_webhook_and_bot(
        request_post_mock, request_get_mock):
    """NotifyMattermost() __len__() behaviour."""
    # webhook: no channels -> 1
    obj = Apprise.instantiate("mmost://localhost/token")
    assert isinstance(obj, NotifyMattermost)
    assert obj.mode == MattermostMode.WEBHOOK
    assert len(obj) == 1

    # webhook: channels -> count
    obj = Apprise.instantiate("mmost://localhost/token?channels=a,b,c")
    assert isinstance(obj, NotifyMattermost)
    assert obj.mode == MattermostMode.WEBHOOK
    assert len(obj) == 3

    # bot: channels are channel_id values -> count
    obj = Apprise.instantiate("mmost://localhost/token?mode=bot&to=id1,id2")
    assert isinstance(obj, NotifyMattermost)
    assert obj.mode == MattermostMode.BOT
    assert len(obj) == 2
    assert obj.notify("test") is True
    assert "mode=bot" in obj.url()

    # bot: channels are channel_id values -> count
    obj = Apprise.instantiate("mmost://localhost/token?mode=bot&to=#chan,id1")
    assert isinstance(obj, NotifyMattermost)
    assert obj.mode == MattermostMode.BOT
    # our #chan isn't added to the list because no team was provided
    assert len(obj) == 1
    assert obj.notify("test") is True
    assert "mode=bot" in obj.url()

    obj = Apprise.instantiate("mmost://localhost/token?mode=bot&to=#chan")
    assert isinstance(obj, NotifyMattermost)
    assert obj.mode == MattermostMode.BOT
    # No one to notify (but we always return a minimum of 1)
    assert len(obj) == 1
    assert obj.notify("test") is False
    assert "mode=bot" in obj.url()

    obj = Apprise.instantiate(
        "mmost://team@localhost/token?mode=bot&to=#chan,id1")
    assert isinstance(obj, NotifyMattermost)
    assert obj.mode == MattermostMode.BOT
    assert len(obj) == 2
    # We can look up the team now
    assert obj.notify("test") is True
    assert "mode=bot" in obj.url()
    # Second call to notify() pulls from cache
    assert obj.notify("test") is True

    obj = Apprise.instantiate(
        "mmost://team@localhost/token?mode=bot&to=#chan,id1")
    assert isinstance(obj, NotifyMattermost)
    assert obj.mode == MattermostMode.BOT
    # Invalid response
    request_get_mock.return_value.content = b"}"
    assert obj.notify("test") is False

    obj = Apprise.instantiate(
        "mmost://team@localhost/token?mode=bot&to=#chan,id1")
    assert isinstance(obj, NotifyMattermost)
    assert obj.mode == MattermostMode.BOT
    # empty response
    request_get_mock.return_value.content = b"{}"
    assert obj.notify("test") is False

    obj = Apprise.instantiate(
        "mmost://team@localhost/token?mode=bot&to=#chan,id1")
    assert isinstance(obj, NotifyMattermost)
    assert obj.mode == MattermostMode.BOT
    # upstream inquiry failure
    request_get_mock.side_effect = requests.RequestException
    assert obj.notify("test") is False


def test_plugin_mattermost_channels(request_post_mock):
    """NotifyMattermost() Channel Testing."""

    # Test channels with/without hashtag (#)
    user = "user1"
    token = "token"
    channels = ["#one", "two"]

    # Instantiate our URL
    obj = Apprise.instantiate(
        "mmost://{user}@localhost:8065/{token}?channels={channels}".format(
            user=user, token=token, channels=",".join(channels)
        )
    )

    assert isinstance(obj, NotifyMattermost)
    assert obj.notify(body="body", title="title") is True

    assert request_post_mock.called is True
    assert request_post_mock.call_count == 2
    assert request_post_mock.call_args_list[0][0][0].startswith(
        "http://localhost:8065/hooks/token"
    )

    # Our Posted JSON Object
    posted_json = json.loads(request_post_mock.call_args_list[0][1]["data"])
    assert "username" in posted_json
    assert "channel" in posted_json
    assert "text" in posted_json
    assert posted_json["username"] == "user1"
    assert posted_json["channel"] == "one"
    assert posted_json["text"] == "title\r\nbody"

    # Our second Posted JSON Object
    posted_json = json.loads(request_post_mock.call_args_list[1][1]["data"])
    assert posted_json["username"] == "user1"
    assert posted_json["channel"] == "two"
    assert posted_json["text"] == "title\r\nbody"


def test_mattermost_post_default_port(request_post_mock):
    # Test token
    token = "token"

    # Instantiate our URL
    obj = Apprise.instantiate(f"mmosts://mattermost.example.com/{token}")

    assert isinstance(obj, NotifyMattermost)
    assert obj.notify(body="body", title="title") is True

    # Make sure we don't use port if not provided
    assert request_post_mock.called is True
    assert request_post_mock.call_count == 1
    assert request_post_mock.call_args_list[0][0][0].startswith(
        "https://mattermost.example.com/hooks/token"
    )

    # Our Posted JSON Object
    posted_json = json.loads(request_post_mock.call_args_list[0][1]["data"])
    assert "text" in posted_json
    assert posted_json["text"] == "title\r\nbody"


def test_mattermost_icon_override(request_post_mock):
    # Test token
    token = "token"
    icon_url = "http://localhost/test.png"

    # Instantiate our URL with an icon override
    obj = Apprise.instantiate(
        "mmost://mattermost.example.com/{token}?icon_url={icon_url}".format(
            token=token,
            icon_url=icon_url,
        )
    )

    assert isinstance(obj, NotifyMattermost)
    assert obj.notify(body="body", title="title") is True

    assert request_post_mock.called is True
    assert request_post_mock.call_count == 1

    # Our Posted JSON Object
    posted_json = json.loads(request_post_mock.call_args_list[0][1]["data"])
    assert posted_json["icon_url"] == icon_url


def test_plugin_mattermost_webhook_payload_variants(request_post_mock, mocker):
    """Webhook mode covers icon_url vs include_image branches, and optional
    channel."""
    # Force image_url() to be deterministic for coverage
    mocker.patch.object(
        NotifyMattermost, "image_url", return_value="http://img/ok.png")

    # Case 1: include_image=True (default) and no icon_url -> icon_url from
    obj = Apprise.instantiate("mmost://user@localhost/token?to=test")
    assert isinstance(obj, NotifyMattermost)
    assert obj.mode == MattermostMode.WEBHOOK
    assert obj.notify(body="body", title="title") is True

    posted_json = json.loads(request_post_mock.call_args_list[-1][1]["data"])
    assert posted_json["username"] == "user"
    assert posted_json["channel"] == "test"
    assert posted_json["text"] == "title\r\nbody"
    assert posted_json["icon_url"] == "http://img/ok.png"

    # Case 2: icon_url overrides include_image
    request_post_mock.reset_mock()
    obj = Apprise.instantiate(
        "mmost://user@localhost/token?to=test&icon_url=http://x/icon.png")
    assert isinstance(obj, NotifyMattermost)
    assert obj.notify(body="body", title="title") is True

    posted_json = json.loads(request_post_mock.call_args_list[0][1]["data"])
    assert posted_json["icon_url"] == "http://x/icon.png"

    # Case 3: no channels specified -> payload has no channel key
    request_post_mock.reset_mock()
    obj = Apprise.instantiate("mmost://user@localhost/token")
    assert isinstance(obj, NotifyMattermost)
    assert obj.notify(body="body", title="title") is True

    posted_json = json.loads(request_post_mock.call_args_list[0][1]["data"])
    assert "channel" not in posted_json


def test_plugin_mattermost_webhook_http_error_and_exception(
        request_post_mock, mocker):
    """Webhook mode error paths."""
    obj = Apprise.instantiate("mmost://localhost/token?to=test")
    assert isinstance(obj, NotifyMattermost)
    assert obj.mode == MattermostMode.WEBHOOK

    # HTTP error
    request_post_mock.return_value.status_code = requests.codes.bad_request
    assert obj.notify(body="body", title="title") is False

    # Request exception
    request_post_mock.reset_mock()
    request_post_mock.side_effect = requests.RequestException("boom")
    assert obj.notify(body="body", title="title") is False


def test_plugin_mattermost_bot_mode_success_and_payload(request_post_mock):
    """Bot mode success path, headers and payload."""
    bearer = "bearerToken"
    channel_id = "channel-id-123"

    obj = Apprise.instantiate(
        f"mmosts://mattermost.example.com/{bearer}?mode=bot&to={channel_id}"
    )
    assert isinstance(obj, NotifyMattermost)
    assert obj.mode == MattermostMode.BOT

    # Mattermost returns 201 Created for /api/v4/posts
    request_post_mock.return_value.status_code = requests.codes.created

    assert obj.notify(body="body", title="title") is True
    assert request_post_mock.called is True
    assert request_post_mock.call_count == 1

    url = request_post_mock.call_args_list[0][0][0]
    assert url.startswith("https://mattermost.example.com/api/v4/posts")

    headers = request_post_mock.call_args_list[0][1]["headers"]
    assert headers.get("Authorization") == f"Bearer {bearer}"

    posted_json = json.loads(request_post_mock.call_args_list[0][1]["data"])
    assert posted_json["channel_id"] == channel_id
    assert posted_json["message"] == "title\r\nbody"
    assert "text" not in posted_json


def test_plugin_mattermost_bot_mode_requires_channel_id(request_post_mock):
    """Bot mode requires at least one channel_id target."""
    bearer = "bearerToken"
    obj = Apprise.instantiate(f"mmost://localhost/{bearer}?mode=bot")
    assert isinstance(obj, NotifyMattermost)
    assert obj.mode == MattermostMode.BOT

    request_post_mock.return_value.status_code = requests.codes.created
    assert obj.notify(body="body", title="title") is False
    assert request_post_mock.called is False


def test_plugin_mattermost_bot_mode_http_error_and_exception(
        request_post_mock):
    """Bot mode error paths."""
    bearer = "bearerToken"
    obj = Apprise.instantiate(f"mmost://localhost/{bearer}?mode=bot&to=id1")
    assert isinstance(obj, NotifyMattermost)
    assert obj.mode == MattermostMode.BOT

    # HTTP error (not 201)
    request_post_mock.return_value.status_code = requests.codes.unauthorized
    assert obj.notify(body="body", title="title") is False

    # Request exception
    request_post_mock.reset_mock()
    request_post_mock.side_effect = requests.RequestException("boom")
    assert obj.notify(body="body", title="title") is False


def test_plugin_mattermost_bot_channel_lookup_success(
        request_post_mock, request_get_mock):
    """Bot mode resolves #channel via team lookup."""
    bearer = "bearerToken"
    team = "myteam"
    channel = "#general"
    channel_id = "cid123"

    # Mock channel lookup response
    request_get_mock.return_value.content = json.dumps(
        {"id": channel_id}
    ).encode("utf-8")

    obj = Apprise.instantiate(
        "mmost://localhost/{bearer}?mode=bot&team={team}&to={chan}"
        .format(bearer=bearer, team=team, chan=channel)
    )
    assert isinstance(obj, NotifyMattermost)
    assert obj.mode == MattermostMode.BOT

    request_post_mock.return_value.status_code = requests.codes.created
    assert obj.notify(body="body", title="title") is True

    assert request_get_mock.called is True
    get_url = request_get_mock.call_args_list[0][0][0]
    assert "/api/v4/teams/name/" in get_url
    assert "/channels/name/" in get_url

    posted_json = json.loads(request_post_mock.call_args_list[0][1]["data"])
    assert posted_json["channel_id"] == channel_id
    assert posted_json["message"] == "title\r\nbody"


def test_plugin_mattermost_bot_channel_lookup_partial_success(
        request_post_mock, request_get_mock):
    """One lookup fails, one succeeds, overall result is True."""
    bearer = "bearerToken"
    team = "myteam"

    def side_effect(*args, **kwargs):
        r = requests.Request()
        url = args[0]
        if url.endswith("/channels/name/good"):
            r.status_code = requests.codes.ok
            r.content = b'{"id":"cid-good"}'
        else:
            r.status_code = requests.codes.not_found
            r.content = b""
        return r

    request_get_mock.side_effect = side_effect

    obj = Apprise.instantiate(
        "mmost://localhost/{bearer}?mode=bot&team={team}&to=#good,#bad"
        .format(bearer=bearer, team=team)
    )
    assert isinstance(obj, NotifyMattermost)
    request_post_mock.return_value.status_code = requests.codes.created

    assert obj.notify(body="body", title="title") is False
    assert request_post_mock.call_count == 1
    posted_json = json.loads(request_post_mock.call_args_list[0][1]["data"])
    assert posted_json["channel_id"] == "cid-good"
