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
from urllib.parse import parse_qs, urlparse

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise
from apprise.exception import AppriseImproperlyConfigured
from apprise.plugins.kakaotalk import NotifyKakaoTalk

logging.disable(logging.CRITICAL)

# A realistic Client ID (REST API Key), Client Secret and Refresh Token
CLIENT_ID = "0123456789abcdef0123456789abcdef"
SECRET = "Sx9QeT1aYp7Lr3Kd"
REFRESH = "tGb4hhaFbYxNRexWXy6TQuKGx-pxt4QxAAAAAgo9cxgAAAGB_1a2b3c4"

# Friend UUIDs as Kakao hands them out
UUID1 = "-Jqzh7SBuYq4kKCRo5WvhrCJsJS9gbm7kQ"
UUID2 = "aBcDeFgHiJkLmNoPqRsTuVwXyZ_0123456"

# A response that satisfies the token call and both message calls
OK_RESPONSE = json.dumps(
    {
        "token_type": "bearer",
        "access_token": "abcd1234",
        "expires_in": 43199,
        "result_code": 0,
        "successful_receiver_uuids": [UUID1],
    }
).encode("utf-8")

# Our Testing URLs
apprise_url_tests = (
    (
        "kakaotalk://",
        {
            # Nothing specified
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        f"kakaotalk://{CLIENT_ID}",
        {
            # No refresh token specified
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        f"kakaotalk://invalid!id/{REFRESH}",
        {
            # An invalid Client ID
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        f"kakaotalk://{CLIENT_ID}/{REFRESH}?secret=bad!secret",
        {
            # An invalid Client Secret
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        f"kakaotalk://{CLIENT_ID}/{REFRESH}",
        {
            # Send to ourselves
            "instance": NotifyKakaoTalk,
            "requests_response_text": OK_RESPONSE,
            # Our expected url(privacy=True) startswith() response
            "privacy_url": "kakaotalk://0...f/t...4/",
        },
    ),
    (
        f"kakao://{SECRET}@{CLIENT_ID}/{REFRESH}/{UUID1}/me",
        {
            # Our alias schema, a Client Secret, a friend and ourselves
            "instance": NotifyKakaoTalk,
            "requests_response_text": OK_RESPONSE,
            "privacy_url": f"kakaotalk://S...d@0...f/t...4/{UUID1}/me",
        },
    ),
    (
        f"kakaotalk://{CLIENT_ID}/{REFRESH}?to={UUID1},{UUID2}"
        "&link=https://example.com/status",
        {
            # Targets given with ?to= and a custom link
            "instance": NotifyKakaoTalk,
            "requests_response_text": OK_RESPONSE,
            "privacy_url": "kakaotalk://0...f/t...4/",
        },
    ),
    (
        f"kakaotalk://{CLIENT_ID}/{REFRESH}/{UUID1}/bad.uuid",
        {
            # An invalid UUID is dropped; the good one still works
            "instance": NotifyKakaoTalk,
            "requests_response_text": OK_RESPONSE,
            "privacy_url": f"kakaotalk://0...f/t...4/{UUID1}/bad.uuid",
        },
    ),
    (
        f"kakaotalk://{CLIENT_ID}/{REFRESH}",
        {
            # No access token was handed back
            "instance": NotifyKakaoTalk,
            "requests_response_text": "{}",
            "notify_response": False,
        },
    ),
    (
        f"kakaotalk://{CLIENT_ID}/{REFRESH}",
        {
            "instance": NotifyKakaoTalk,
            "requests_response_text": OK_RESPONSE,
            # Throws a series of i/o exceptions with this flag set and
            # tests that we gracefully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_kakaotalk_urls():
    """NotifyKakaoTalk() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


def _mk_resp(content, code=requests.codes.ok):
    """Build one mocked response."""
    response = mock.Mock()
    response.status_code = code
    response.content = (
        json.dumps(content).encode("utf-8")
        if isinstance(content, (dict, list))
        else content
    )
    return response


def _token(**extra):
    """Build a token response."""
    content = {"access_token": "abcd1234", "expires_in": 43199}
    content.update(extra)
    return _mk_resp(content)


@mock.patch("requests.post")
def test_plugin_kakaotalk_send_me(mock_post):
    """A message to ourselves uses the memo API and our access token."""

    mock_post.side_effect = [_token(), _mk_resp({"result_code": 0})]

    obj = Apprise.instantiate(
        f"kakaotalk://{SECRET}@{CLIENT_ID}/{REFRESH}"
        "?link=https://example.com/status"
    )
    assert isinstance(obj, NotifyKakaoTalk)
    assert len(obj) == 1
    assert obj.notify(title="Title & <b>", body="Body _.!*#<") is True
    assert mock_post.call_count == 2

    # Our token request
    url, kwargs = (
        mock_post.call_args_list[0][0][0],
        (mock_post.call_args_list[0][1]),
    )
    assert urlparse(url).hostname == "kauth.kakao.com"
    assert kwargs["data"] == {
        "grant_type": "refresh_token",
        "client_id": CLIENT_ID,
        "refresh_token": REFRESH,
        "client_secret": SECRET,
    }

    # Our message
    url, kwargs = (
        mock_post.call_args_list[1][0][0],
        (mock_post.call_args_list[1][1]),
    )
    assert urlparse(url).hostname == "kapi.kakao.com"
    assert urlparse(url).path == "/v2/api/talk/memo/default/send"
    assert kwargs["headers"]["Authorization"] == "Bearer abcd1234"
    assert "receiver_uuids" not in kwargs["data"]
    template = json.loads(kwargs["data"]["template_object"])
    assert template == {
        "object_type": "text",
        # The title is merged into the body untouched
        "text": "Title & <b>\r\nBody _.!*#<",
        "link": {
            "web_url": "https://example.com/status",
            "mobile_web_url": "https://example.com/status",
        },
    }

    # The cached access token is reused on our next send
    mock_post.reset_mock()
    mock_post.side_effect = [_mk_resp({"result_code": 0})]
    assert obj.notify(body="again") is True
    assert mock_post.call_count == 1


@mock.patch("requests.post")
def test_plugin_kakaotalk_send_friends(mock_post):
    """Each friend gets their own message; a failure is reported."""

    mock_post.side_effect = [
        _token(),
        _mk_resp({"successful_receiver_uuids": [UUID1]}),
        _mk_resp(
            {"msg": "daily message limit exceeded", "code": -532},
            requests.codes.bad_request,
        ),
    ]

    obj = NotifyKakaoTalk(
        client_id=CLIENT_ID, refresh_token=REFRESH, targets=[UUID1, UUID2]
    )
    assert len(obj) == 2
    assert obj.notify(body="hello") is False
    assert mock_post.call_count == 3

    for index, uuid in ((1, UUID1), (2, UUID2)):
        url, kwargs = (
            mock_post.call_args_list[index][0][0],
            (mock_post.call_args_list[index][1]),
        )
        assert urlparse(url).path == (
            "/v1/api/talk/friends/message/default/send"
        )
        assert json.loads(kwargs["data"]["receiver_uuids"]) == [uuid]
        template = json.loads(kwargs["data"]["template_object"])

        # Without ?link= Kakao's own example link is used
        assert template["link"]["web_url"] == NotifyKakaoTalk.default_link
        assert template["text"] == "hello"


@mock.patch("requests.post")
def test_plugin_kakaotalk_token_handling(mock_post):
    """Token lifetimes, a rotated refresh token and an expired token."""

    obj = NotifyKakaoTalk(client_id=CLIENT_ID, refresh_token=REFRESH)

    # A new refresh token is kept and used for the next login
    mock_post.side_effect = [
        _token(
            expires_in="invalid",
            refresh_token="newRefresh_1",
            refresh_token_expires_in=5184000,
        ),
    ]
    assert obj.login() == "abcd1234"
    assert obj.store.get("refresh_token") == "newRefresh_1"

    mock_post.side_effect = [
        _token(refresh_token="newRefresh_2", refresh_token_expires_in=None),
    ]
    assert obj.login() == "abcd1234"
    assert mock_post.call_args[1]["data"]["refresh_token"] == "newRefresh_1"
    assert obj.store.get("refresh_token") == "newRefresh_2"

    # A 401 forgets our access token so the next send logs in again
    mock_post.reset_mock()
    mock_post.side_effect = [
        _mk_resp(
            {"msg": "this access token does not exist", "code": -401},
            requests.codes.unauthorized,
        ),
    ]
    assert obj.send(body="hello") is False
    assert obj.store.get("access_token") is None
    assert mock_post.call_count == 1

    # A failed login stops the send early
    mock_post.reset_mock()
    mock_post.side_effect = [
        _mk_resp(
            {"error": "invalid_grant", "error_description": "bad token"},
            requests.codes.bad_request,
        ),
    ]
    assert obj.send(body="hello") is False
    assert mock_post.call_count == 1

    # A response that is not JSON, or not a dict, is survived
    for content in (b"not json", b"[]"):
        mock_post.reset_mock()
        mock_post.side_effect = [_mk_resp(content, 500)]
        assert obj.send(body="hello") is False


def test_plugin_kakaotalk_url_parsing():
    """Round trips keep the connection, targets and options."""

    obj = Apprise.instantiate(
        f"kakao://{CLIENT_ID}/{REFRESH}/{UUID1}/ME/bad.uuid"
        f"?secret={SECRET}&link=https://example.com/a"
    )
    assert isinstance(obj, NotifyKakaoTalk)
    assert obj.client_secret == SECRET
    assert obj.link == "https://example.com/a"
    assert obj.targets == [UUID1, "me"]
    assert obj.invalid_targets == ["bad.uuid"]

    # Everything survives a round trip
    obj2 = Apprise.instantiate(obj.url())
    assert obj2.url_identifier == obj.url_identifier
    assert obj2.targets == obj.targets
    assert obj2.invalid_targets == obj.invalid_targets
    assert obj2.link == obj.link
    assert obj2.url().startswith("kakaotalk://")
    assert parse_qs(urlparse(obj2.url()).query)["link"] == [
        "https://example.com/a"
    ]

    # The Client Secret makes it a different connection
    obj3 = NotifyKakaoTalk(client_id=CLIENT_ID, refresh_token=REFRESH)
    assert obj3.url_identifier != obj.url_identifier

    # A missing refresh token is refused
    with pytest.raises(AppriseImproperlyConfigured):
        NotifyKakaoTalk(client_id=CLIENT_ID, refresh_token=None)

    with pytest.raises(AppriseImproperlyConfigured):
        NotifyKakaoTalk(client_id=CLIENT_ID, refresh_token="bad token")
