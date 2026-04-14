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

import json

# Disable logging for a cleaner testing output
import logging
import os
from unittest import mock

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise, AppriseAttachment
from apprise.plugins.mattermost import MattermostMode, NotifyMattermost

# Attachment test fixtures
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), "var")

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
        {
            "instance": NotifyMattermost,
            # Provide valid upload response so the attachment test passes
            "requests_response_text": '{"file_infos": [{"id": "abc"}]}',
        },
    ),
    (
        (
            # sets botname on webhook
            "mmost://localhost/3ccdd113474722377935511fc85d3dd4"
            "?to=general&botname=foobar"
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
    (
        "mmosts://localhost/a/path/3ccdd113474722377935511fc85d3dd4",
        {"instance": NotifyMattermost},
    ),
    (
        "mmosts://localhost/////3ccdd113474722377935511fc85d3dd4///",
        {"instance": NotifyMattermost},
    ),
    # Mode parsing (prefix support)
    ("mmost://localhost/token?mode=w", {"instance": NotifyMattermost}),
    (
        "mmost://localhost/token?mode=b&to=channel-id-1",
        {
            "instance": NotifyMattermost,
            # Provide valid upload response so the attachment test passes
            "requests_response_text": '{"file_infos": [{"id": "abc"}]}',
        },
    ),
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
    request_post_mock, request_get_mock
):
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
        "mmost://team@localhost/token?mode=bot&to=#chan,id1"
    )
    assert isinstance(obj, NotifyMattermost)
    assert obj.mode == MattermostMode.BOT
    assert len(obj) == 2
    # We can look up the team now
    assert obj.notify("test") is True
    assert "mode=bot" in obj.url()
    # Second call to notify() pulls from cache
    assert obj.notify("test") is True

    obj = Apprise.instantiate(
        "mmost://team@localhost/token?mode=bot&to=#chan,id1"
    )
    assert isinstance(obj, NotifyMattermost)
    assert obj.mode == MattermostMode.BOT
    # Invalid response
    request_get_mock.return_value.content = b"}"
    assert obj.notify("test") is False

    obj = Apprise.instantiate(
        "mmost://team@localhost/token?mode=bot&to=#chan,id1"
    )
    assert isinstance(obj, NotifyMattermost)
    assert obj.mode == MattermostMode.BOT
    # empty response
    request_get_mock.return_value.content = b"{}"
    assert obj.notify("test") is False

    obj = Apprise.instantiate(
        "mmost://team@localhost/token?mode=bot&to=#chan,id1"
    )
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
        NotifyMattermost, "image_url", return_value="http://img/ok.png"
    )

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
        "mmost://user@localhost/token?to=test&icon_url=http://x/icon.png"
    )
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
    request_post_mock, mocker
):
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
    request_post_mock,
):
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
    request_post_mock, request_get_mock
):
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
        "mmost://localhost/{bearer}?mode=bot&team={team}&to={chan}".format(
            bearer=bearer, team=team, chan=channel
        )
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
    request_post_mock, request_get_mock
):
    """One lookup fails, one succeeds, overall result is False."""
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
        "mmost://localhost/{bearer}?mode=bot&team={team}&to=#good,#bad".format(
            bearer=bearer, team=team
        )
    )
    assert isinstance(obj, NotifyMattermost)
    request_post_mock.return_value.status_code = requests.codes.created

    assert obj.notify(body="body", title="title") is False
    assert request_post_mock.call_count == 1
    posted_json = json.loads(request_post_mock.call_args_list[0][1]["data"])
    assert posted_json["channel_id"] == "cid-good"


def test_plugin_mattermost_webhook_attachment_warning(request_post_mock):
    """Webhook mode has attachment_support=False; pipeline drops attach."""
    obj = Apprise.instantiate("mmost://localhost/token")
    assert isinstance(obj, NotifyMattermost)
    assert obj.mode == MattermostMode.WEBHOOK
    assert obj.attachment_support is False

    attach = AppriseAttachment(os.path.join(TEST_VAR_DIR, "apprise-test.gif"))

    # Pipeline silently drops the attachment; text message still succeeds
    assert obj.notify(body="body", title="title", attach=attach) is True
    assert request_post_mock.call_count == 1

    # No file upload should have been attempted
    assert "files" not in str(request_post_mock.call_args)


def test_plugin_mattermost_webhook_botname_in_url(request_post_mock):
    """Webhook botname is the {user}@ URL prefix; ?botname= is an alias."""
    # Both input forms resolve to the same object
    obj = Apprise.instantiate("mmost://mybot@localhost/token?to=general")
    obj2 = Apprise.instantiate(
        "mmost://localhost/token?botname=mybot&to=general"
    )
    assert isinstance(obj, NotifyMattermost)
    assert isinstance(obj2, NotifyMattermost)
    assert obj.mode == MattermostMode.WEBHOOK
    assert obj.user == "mybot"
    assert obj2.user == "mybot"

    # url() uses the {user}@ prefix -- consistent with all Apprise plugins
    url = obj.url()
    assert "mybot@" in url
    assert "botname" not in url

    # Round-trip preserves the botname
    obj3 = Apprise.instantiate(url)
    assert isinstance(obj3, NotifyMattermost)
    assert obj3.user == "mybot"
    assert obj3.mode == MattermostMode.WEBHOOK

    # Webhook payload carries username = botname
    request_post_mock.return_value.status_code = requests.codes.ok
    assert obj.notify(body="body", title="title") is True
    posted = json.loads(request_post_mock.call_args_list[0][1]["data"])
    assert posted["username"] == "mybot"


def test_plugin_mattermost_bot_team_in_url(request_post_mock):
    """Bot mode team is the {user}@ URL prefix; ?team= is an alias."""
    obj = Apprise.instantiate("mmost://myteam@localhost/token?mode=bot&to=id1")
    assert isinstance(obj, NotifyMattermost)
    assert obj.mode == MattermostMode.BOT
    assert obj.user == "myteam"

    # url() uses {user}@ prefix for the team too
    url = obj.url()
    assert "myteam@" in url
    assert "mode=bot" in url


def test_plugin_mattermost_bot_attachments(request_post_mock):
    """Bot mode uploads attachments and includes file_ids in the post."""
    bearer = "bearerToken"
    channel_id = "channel-id-123"
    file_id = "uploaded-file-id-abc"

    attach = AppriseAttachment(os.path.join(TEST_VAR_DIR, "apprise-test.gif"))

    def _mk_resp(content, code=requests.codes.ok):
        r = requests.Request()
        r.status_code = code
        r.content = content
        return r

    upload_resp = _mk_resp(
        json.dumps({"file_infos": [{"id": file_id}]}).encode("utf-8")
    )
    post_resp = _mk_resp(b"{}", requests.codes.created)

    request_post_mock.side_effect = [upload_resp, post_resp]

    obj = Apprise.instantiate(
        f"mmost://localhost/{bearer}?mode=bot&to={channel_id}"
    )
    assert isinstance(obj, NotifyMattermost)
    assert obj.mode == MattermostMode.BOT

    assert obj.notify(body="body", title="title", attach=attach) is True
    assert request_post_mock.call_count == 2

    # First call is the file upload
    upload_call = request_post_mock.call_args_list[0]
    assert "/api/v4/files" in upload_call[0][0]
    assert upload_call[1]["data"] == {"channel_id": channel_id}
    assert "files" in upload_call[1]["files"]

    # Second call is the post; it must include file_ids
    post_call = request_post_mock.call_args_list[1]
    assert "/api/v4/posts" in post_call[0][0]
    post_json = json.loads(post_call[1]["data"])
    assert post_json["file_ids"] == [file_id]
    assert post_json["message"] == "title\r\nbody"
    assert post_json["channel_id"] == channel_id


def test_plugin_mattermost_bot_multi_attach_multi_target(request_post_mock):
    """Multiple attachments and multiple targets each get their own uploads."""
    bearer = "bearerToken"
    ch1 = "channel-001"
    ch2 = "channel-002"
    fid1 = "fid-001"
    fid2 = "fid-002"

    attach = AppriseAttachment()
    attach.add(os.path.join(TEST_VAR_DIR, "apprise-test.gif"))
    attach.add(os.path.join(TEST_VAR_DIR, "apprise-test.png"))

    def _mk_upload(fid):
        r = requests.Request()
        r.status_code = requests.codes.ok
        r.content = json.dumps({"file_infos": [{"id": fid}]}).encode("utf-8")
        return r

    def _mk_post():
        r = requests.Request()
        r.status_code = requests.codes.created
        r.content = b"{}"
        return r

    # 2 attachments x 2 targets = 4 upload calls + 2 post calls
    request_post_mock.side_effect = [
        _mk_upload(fid1),
        _mk_upload(fid2),
        _mk_post(),
        _mk_upload(fid1),
        _mk_upload(fid2),
        _mk_post(),
    ]

    obj = Apprise.instantiate(
        "mmost://localhost/{b}?mode=bot&to={c1},{c2}".format(
            b=bearer, c1=ch1, c2=ch2
        )
    )
    assert isinstance(obj, NotifyMattermost)
    assert obj.notify(body="body", title="title", attach=attach) is True
    assert request_post_mock.call_count == 6

    # Verify file_ids for each post
    post1 = json.loads(request_post_mock.call_args_list[2][1]["data"])
    assert post1["file_ids"] == [fid1, fid2]
    assert post1["channel_id"] == ch1

    post2 = json.loads(request_post_mock.call_args_list[5][1]["data"])
    assert post2["file_ids"] == [fid1, fid2]
    assert post2["channel_id"] == ch2


def test_plugin_mattermost_bot_attachment_upload_http_error(
    request_post_mock,
):
    """Upload HTTP error marks the whole target as failed."""
    bearer = "bearerToken"
    channel_id = "channel-id-123"

    attach = AppriseAttachment(os.path.join(TEST_VAR_DIR, "apprise-test.gif"))

    r = requests.Request()
    r.status_code = requests.codes.internal_server_error
    r.content = b""
    request_post_mock.return_value = r

    obj = Apprise.instantiate(
        f"mmost://localhost/{bearer}?mode=bot&to={channel_id}"
    )
    assert isinstance(obj, NotifyMattermost)
    assert obj.notify(body="body", title="title", attach=attach) is False
    # Only the upload was attempted; no post was made
    assert request_post_mock.call_count == 1
    assert "/api/v4/files" in request_post_mock.call_args_list[0][0][0]


def test_plugin_mattermost_bot_attachment_request_exception(
    request_post_mock,
):
    """RequestException during upload marks the target as failed."""
    bearer = "bearerToken"
    channel_id = "channel-id-123"

    attach = AppriseAttachment(os.path.join(TEST_VAR_DIR, "apprise-test.gif"))

    request_post_mock.side_effect = requests.RequestException("boom")

    obj = Apprise.instantiate(
        f"mmost://localhost/{bearer}?mode=bot&to={channel_id}"
    )
    assert isinstance(obj, NotifyMattermost)
    assert obj.notify(body="body", title="title", attach=attach) is False
    assert request_post_mock.call_count == 1


def test_plugin_mattermost_bot_attachment_ioerror(request_post_mock):
    """OSError reading the attachment marks the target as failed."""
    bearer = "bearerToken"
    channel_id = "channel-id-123"

    attach = AppriseAttachment(os.path.join(TEST_VAR_DIR, "apprise-test.gif"))

    with mock.patch(
        "apprise.attachment.file.AttachFile.open",
        side_effect=OSError("disk error"),
    ):
        obj = Apprise.instantiate(
            f"mmost://localhost/{bearer}?mode=bot&to={channel_id}"
        )
        assert isinstance(obj, NotifyMattermost)
        assert obj.notify(body="body", title="title", attach=attach) is False

    # No HTTP request should have been made
    assert request_post_mock.call_count == 0


def test_plugin_mattermost_bot_attachment_valueerror(request_post_mock):
    """ValueError from a closed stream is handled the same as OSError."""
    bearer = "bearerToken"
    channel_id = "channel-id-123"

    attach = AppriseAttachment(os.path.join(TEST_VAR_DIR, "apprise-test.gif"))

    with mock.patch(
        "apprise.attachment.file.AttachFile.open",
        side_effect=ValueError("I/O operation on closed file"),
    ):
        obj = Apprise.instantiate(
            f"mmost://localhost/{bearer}?mode=bot&to={channel_id}"
        )
        assert isinstance(obj, NotifyMattermost)
        assert obj.notify(body="body", title="title", attach=attach) is False

    assert request_post_mock.call_count == 0


def test_plugin_mattermost_bot_attachment_bad_response(request_post_mock):
    """Unparseable upload response marks the target as failed."""
    bearer = "bearerToken"
    channel_id = "channel-id-123"

    attach = AppriseAttachment(os.path.join(TEST_VAR_DIR, "apprise-test.gif"))

    r = requests.Request()
    r.status_code = requests.codes.ok
    r.content = b"not-json{{{"
    request_post_mock.return_value = r

    obj = Apprise.instantiate(
        f"mmost://localhost/{bearer}?mode=bot&to={channel_id}"
    )
    assert isinstance(obj, NotifyMattermost)
    assert obj.notify(body="body", title="title", attach=attach) is False
    assert request_post_mock.call_count == 1


def test_plugin_mattermost_bot_attachment_no_file_id(request_post_mock):
    """Upload response with empty file_id marks the target as failed."""
    bearer = "bearerToken"
    channel_id = "channel-id-123"

    attach = AppriseAttachment(os.path.join(TEST_VAR_DIR, "apprise-test.gif"))

    r = requests.Request()
    r.status_code = requests.codes.ok
    # file_infos present but id is empty
    r.content = json.dumps({"file_infos": [{"id": ""}]}).encode("utf-8")
    request_post_mock.return_value = r

    obj = Apprise.instantiate(
        f"mmost://localhost/{bearer}?mode=bot&to={channel_id}"
    )
    assert isinstance(obj, NotifyMattermost)
    assert obj.notify(body="body", title="title", attach=attach) is False


def test_plugin_mattermost_bot_attachment_invalid(request_post_mock):
    """An inaccessible attachment path marks the target as failed."""
    bearer = "bearerToken"
    channel_id = "channel-id-123"

    attach = AppriseAttachment("/path/does/not/exist.gif")

    obj = Apprise.instantiate(
        f"mmost://localhost/{bearer}?mode=bot&to={channel_id}"
    )
    assert isinstance(obj, NotifyMattermost)
    assert obj.notify(body="body", title="title", attach=attach) is False
    # No upload request should be made for an invalid attachment
    assert request_post_mock.call_count == 0


def test_plugin_mattermost_bot_attachment_partial_target_failure(
    request_post_mock,
):
    """Attachment upload failure on one target does not prevent others."""
    bearer = "bearerToken"
    ch1 = "channel-001"
    ch2 = "channel-002"
    fid = "fid-001"

    attach = AppriseAttachment(os.path.join(TEST_VAR_DIR, "apprise-test.gif"))

    def _mk_upload_ok():
        r = requests.Request()
        r.status_code = requests.codes.ok
        r.content = json.dumps({"file_infos": [{"id": fid}]}).encode("utf-8")
        return r

    def _mk_upload_fail():
        r = requests.Request()
        r.status_code = requests.codes.internal_server_error
        r.content = b""
        return r

    def _mk_post():
        r = requests.Request()
        r.status_code = requests.codes.created
        r.content = b"{}"
        return r

    # ch1: upload ok, post ok; ch2: upload fails
    request_post_mock.side_effect = [
        _mk_upload_ok(),
        _mk_post(),
        _mk_upload_fail(),
    ]

    obj = Apprise.instantiate(
        "mmost://localhost/{b}?mode=bot&to={c1},{c2}".format(
            b=bearer, c1=ch1, c2=ch2
        )
    )
    assert isinstance(obj, NotifyMattermost)
    # One target succeeded, one failed -> overall False
    assert obj.notify(body="body", title="title", attach=attach) is False
    # 1 upload + 1 post (ch1) + 1 upload-fail (ch2) = 3 calls
    assert request_post_mock.call_count == 3


def test_plugin_mattermost_bot_attachment_memory_multi_target(
    request_post_mock,
):
    """Attachment bytes are pre-read once so every target gets a fresh stream.

    Simulates an attachment whose open() raises ValueError on the second
    call (as AttachMemory does when its BytesIO is closed after the first
    read).  Our pre-read approach calls open() exactly once per attachment
    before the target loop, then wraps the bytes in a fresh io.BytesIO for
    each target upload.
    """
    bearer = "bearerToken"
    ch1 = "channel-001"
    ch2 = "channel-002"
    fid = "fid-001"

    attach = AppriseAttachment(os.path.join(TEST_VAR_DIR, "apprise-test.gif"))

    # Simulate a stream that closes after the first read: raise ValueError
    # on any open() call beyond the first.
    _orig_open = attach.attachments[0].open
    open_calls = [0]

    def _open_once(*args, **kwargs):
        open_calls[0] += 1
        if open_calls[0] > 1:
            raise ValueError("stream already closed")
        return _orig_open(*args, **kwargs)

    def _mk_upload():
        r = requests.Request()
        r.status_code = requests.codes.ok
        r.content = json.dumps({"file_infos": [{"id": fid}]}).encode("utf-8")
        return r

    def _mk_post():
        r = requests.Request()
        r.status_code = requests.codes.created
        r.content = b"{}"
        return r

    # 1 attachment x 2 targets = 2 upload + 2 post calls
    request_post_mock.side_effect = [
        _mk_upload(),
        _mk_post(),
        _mk_upload(),
        _mk_post(),
    ]

    obj = Apprise.instantiate(
        "mmost://localhost/{b}?mode=bot&to={c1},{c2}".format(
            b=bearer, c1=ch1, c2=ch2
        )
    )
    assert isinstance(obj, NotifyMattermost)

    with mock.patch.object(attach.attachments[0], "open", _open_once):
        assert obj.notify(body="body", title="title", attach=attach) is True

    # open() was called exactly once (pre-read), not once per target
    assert open_calls[0] == 1
    # Both targets received their uploads
    assert request_post_mock.call_count == 4

    post1 = json.loads(request_post_mock.call_args_list[1][1]["data"])
    assert post1["file_ids"] == [fid]
    assert post1["channel_id"] == ch1

    post2 = json.loads(request_post_mock.call_args_list[3][1]["data"])
    assert post2["file_ids"] == [fid]
    assert post2["channel_id"] == ch2
