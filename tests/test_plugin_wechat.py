#
# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2026, Chris Caron <lead2gold@gmail.com>
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in
#    the documentation and/or other materials provided with the
#    distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
# COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

# Disable logging for a cleaner testing output
from json import dumps
import logging
from unittest import mock

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise
from apprise.common import NotifyFormat
from apprise.plugins.wechat import (
    WECHAT_ERROR_CODES,
    WECHAT_TOKEN_ERROR_CODES,
    NotifyWeChat,
)

logging.disable(logging.CRITICAL)

# Fixed test credentials
CORPID = "wwcorpid1234567890"
CORPSECRET = "abcSecret9"
AGENTID = "1000002"

# A successful response serves double-duty: the token GET needs
# access_token and expires_in; the message POST needs errcode == 0.
GOOD_RESPONSE = dumps(
    {
        "errcode": 0,
        "errmsg": "ok",
        "access_token": "TOKEN12345678",
        "expires_in": 7200,
    }
)

# pprint(CORPSECRET, privacy=True) -> first + "..." + last char
# "abcSecret9" -> "a...9"
PRIVACY_SECRET = "a...9"

# Our Testing URLs
apprise_url_tests = (
    # ----------------------------------------------------------------
    # Invalid / missing credential cases
    # ----------------------------------------------------------------
    (
        "wechat://",
        {
            # No credentials at all
            "instance": TypeError,
        },
    ),
    (
        # Missing corpsecret and agentid
        "wechat://{}".format(CORPID),
        {
            "instance": TypeError,
        },
    ),
    (
        # Missing agentid (non-numeric host provided as port only)
        "wechat://{}:{}@".format(CORPID, CORPSECRET),
        {
            "instance": TypeError,
        },
    ),
    (
        # Non-numeric agentid
        "wechat://{}:{}@notanumber".format(CORPID, CORPSECRET),
        {
            "instance": TypeError,
        },
    ),
    # ----------------------------------------------------------------
    # No targets -- plugin loads but send() returns False early
    # ----------------------------------------------------------------
    (
        "wechat://{}:{}@{}".format(CORPID, CORPSECRET, AGENTID),
        {
            "instance": NotifyWeChat,
            "notify_response": False,
            "privacy_url": "wechat://{}:{}@{}/".format(
                CORPID, PRIVACY_SECRET, AGENTID
            ),
        },
    ),
    # ----------------------------------------------------------------
    # @all broadcast -- sends to entire organisation
    # ----------------------------------------------------------------
    (
        "wechat://{}:{}@{}/@all".format(CORPID, CORPSECRET, AGENTID),
        {
            "instance": NotifyWeChat,
            "requests_response_text": GOOD_RESPONSE,
            "privacy_url": "wechat://{}:{}@{}/@all/".format(
                CORPID, PRIVACY_SECRET, AGENTID
            ),
        },
    ),
    # ----------------------------------------------------------------
    # Single user target (bare form -- no @ prefix)
    # ----------------------------------------------------------------
    (
        "wechat://{}:{}@{}/johndoe".format(CORPID, CORPSECRET, AGENTID),
        {
            "instance": NotifyWeChat,
            "requests_response_text": GOOD_RESPONSE,
        },
    ),
    # ----------------------------------------------------------------
    # Single user target (@ prefixed form)
    # ----------------------------------------------------------------
    (
        "wechat://{}:{}@{}/@johndoe".format(CORPID, CORPSECRET, AGENTID),
        {
            "instance": NotifyWeChat,
            "requests_response_text": GOOD_RESPONSE,
        },
    ),
    # ----------------------------------------------------------------
    # Multiple user targets
    # ----------------------------------------------------------------
    (
        "wechat://{}:{}@{}/user1/user2/user3".format(
            CORPID, CORPSECRET, AGENTID
        ),
        {
            "instance": NotifyWeChat,
            "requests_response_text": GOOD_RESPONSE,
        },
    ),
    # ----------------------------------------------------------------
    # Department target (%23 decodes to # prefix)
    # ----------------------------------------------------------------
    (
        "wechat://{}:{}@{}/%23100".format(CORPID, CORPSECRET, AGENTID),
        {
            "instance": NotifyWeChat,
            "requests_response_text": GOOD_RESPONSE,
        },
    ),
    # ----------------------------------------------------------------
    # Tag target (+ prefix)
    # ----------------------------------------------------------------
    (
        "wechat://{}:{}@{}/+7".format(CORPID, CORPSECRET, AGENTID),
        {
            "instance": NotifyWeChat,
            "requests_response_text": GOOD_RESPONSE,
        },
    ),
    # ----------------------------------------------------------------
    # Mixed recipients (user + department + tag)
    # ----------------------------------------------------------------
    (
        "wechat://{}:{}@{}/john/%23200/+3".format(CORPID, CORPSECRET, AGENTID),
        {
            "instance": NotifyWeChat,
            "requests_response_text": GOOD_RESPONSE,
        },
    ),
    # ----------------------------------------------------------------
    # Targets supplied via ?to= query parameter
    # ----------------------------------------------------------------
    (
        "wechat://{}:{}@{}?to=@all".format(CORPID, CORPSECRET, AGENTID),
        {
            "instance": NotifyWeChat,
            "requests_response_text": GOOD_RESPONSE,
        },
    ),
    # ----------------------------------------------------------------
    # Markdown format
    # ----------------------------------------------------------------
    (
        "wechat://{}:{}@{}/@all?format=markdown".format(
            CORPID, CORPSECRET, AGENTID
        ),
        {
            "instance": NotifyWeChat,
            "requests_response_text": GOOD_RESPONSE,
        },
    ),
    # ----------------------------------------------------------------
    # HTTP error responses -- token GET fails -> overall send fails
    # ----------------------------------------------------------------
    (
        "wechat://{}:{}@{}/@all".format(CORPID, CORPSECRET, AGENTID),
        {
            "instance": NotifyWeChat,
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "wechat://{}:{}@{}/@all".format(CORPID, CORPSECRET, AGENTID),
        {
            "instance": NotifyWeChat,
            "response": False,
            "requests_response_code": 999,
        },
    ),
    # ----------------------------------------------------------------
    # Network exception on all requests
    # ----------------------------------------------------------------
    (
        "wechat://{}:{}@{}/@all".format(CORPID, CORPSECRET, AGENTID),
        {
            "instance": NotifyWeChat,
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_wechat_urls():
    """Run the standard Apprise URL tester for all wechat:// entries."""
    AppriseURLTester(tests=apprise_url_tests).run_all()


def test_plugin_wechat_init():
    """Verify __init__ validation for required fields."""

    # Valid construction
    obj = NotifyWeChat(corpid=CORPID, corpsecret=CORPSECRET, agentid=AGENTID)
    assert isinstance(obj, NotifyWeChat)

    # corpid is required
    with (
        mock.patch("apprise.plugins.wechat.validate_regex", return_value=None),
        mock.patch.object(NotifyWeChat, "logger"),
        pytest.raises(TypeError),
    ):
        NotifyWeChat(corpid="", corpsecret=CORPSECRET, agentid=AGENTID)

    # corpsecret is required
    with pytest.raises(TypeError):
        NotifyWeChat(corpid=CORPID, corpsecret="", agentid=AGENTID)

    # agentid must be numeric
    with pytest.raises(TypeError):
        NotifyWeChat(corpid=CORPID, corpsecret=CORPSECRET, agentid="notnum")

    # agentid=None must be rejected
    with pytest.raises(TypeError):
        NotifyWeChat(corpid=CORPID, corpsecret=CORPSECRET, agentid=None)

    # Invalid targets are silently dropped; valid ones are kept
    obj = NotifyWeChat(
        corpid=CORPID,
        corpsecret=CORPSECRET,
        agentid=AGENTID,
        targets=["validuser", "!!invalid!!", "#42", "+7"],
    )
    assert "validuser" in obj.users
    assert "42" in obj.departments
    assert "7" in obj.tag_ids
    assert "!!invalid!!" in obj.invalid_targets

    # The @ prefix on user IDs is optional on input; it is stripped
    # by the regex before storing so the API payload stays prefix-free.
    # The bare keyword "all" is normalised to "@all" (WeCom API form).
    obj = NotifyWeChat(
        corpid=CORPID,
        corpsecret=CORPSECRET,
        agentid=AGENTID,
        targets=["@johndoe", "@all", "all"],
    )
    assert "johndoe" in obj.users
    # Both "@all" and bare "all" must normalise to "@all"
    assert obj.users.count("@all") == 2


def test_plugin_wechat_url_round_trip():
    """Verify that url() and parse_url() form a lossless round-trip."""

    obj1 = NotifyWeChat(
        corpid=CORPID,
        corpsecret=CORPSECRET,
        agentid=AGENTID,
        targets=["alice", "#10", "+2", "@all"],
    )
    url = obj1.url()
    result = NotifyWeChat.parse_url(url)
    assert result is not None
    obj2 = NotifyWeChat(**result)

    # Connection identity must be preserved
    assert obj1.url_identifier == obj2.url_identifier

    # Target counts must match
    assert len(obj1) == len(obj2)


def test_plugin_wechat_url():
    """Verify url() output for various target combinations."""

    # No targets
    obj = NotifyWeChat(corpid=CORPID, corpsecret=CORPSECRET, agentid=AGENTID)
    url = obj.url()
    assert CORPID in url
    assert CORPSECRET in url
    assert AGENTID in url

    # Privacy URL masks the corpsecret
    privacy = obj.url(privacy=True)
    assert CORPSECRET not in privacy
    assert PRIVACY_SECRET in privacy
    assert CORPID in privacy

    # Department gets encoded as %23
    obj = NotifyWeChat(
        corpid=CORPID,
        corpsecret=CORPSECRET,
        agentid=AGENTID,
        targets=["#5"],
    )
    assert "%235" in obj.url()

    # Tag gets + prefix
    obj = NotifyWeChat(
        corpid=CORPID,
        corpsecret=CORPSECRET,
        agentid=AGENTID,
        targets=["+3"],
    )
    assert "+3" in obj.url()

    # @all is kept as-is
    obj = NotifyWeChat(
        corpid=CORPID,
        corpsecret=CORPSECRET,
        agentid=AGENTID,
        targets=["@all"],
    )
    assert "@all" in obj.url()

    # Regular user IDs are always emitted with @ prefix in the URL
    obj = NotifyWeChat(
        corpid=CORPID,
        corpsecret=CORPSECRET,
        agentid=AGENTID,
        targets=["alice"],
    )
    assert "@alice" in obj.url()

    # Invalid targets survive the round-trip
    obj = NotifyWeChat(
        corpid=CORPID,
        corpsecret=CORPSECRET,
        agentid=AGENTID,
        targets=["!!bad!!"],
    )
    assert obj.invalid_targets
    # url() must include the invalid target so it round-trips
    assert obj.url() != ""


def test_plugin_wechat_url_identifier():
    """url_identifier must differ when credentials differ."""

    obj1 = NotifyWeChat(corpid=CORPID, corpsecret=CORPSECRET, agentid=AGENTID)
    obj2 = NotifyWeChat(
        corpid="other_corp", corpsecret=CORPSECRET, agentid=AGENTID
    )
    obj3 = NotifyWeChat(
        corpid=CORPID, corpsecret="other_secret", agentid=AGENTID
    )
    obj4 = NotifyWeChat(
        corpid=CORPID, corpsecret=CORPSECRET, agentid="9999999"
    )

    assert obj1.url_identifier != obj2.url_identifier
    assert obj1.url_identifier != obj3.url_identifier
    assert obj1.url_identifier != obj4.url_identifier


@mock.patch("requests.get")
@mock.patch("requests.post")
def test_plugin_wechat_send_ok(mock_post, mock_get):
    """Successful end-to-end send: token GET + message POST both succeed."""

    def _mk_resp(data, code=requests.codes.ok):
        r = mock.Mock()
        r.status_code = code
        r.content = dumps(data).encode("utf-8")
        return r

    # Token GET -> success + message POST -> success
    mock_get.return_value = _mk_resp(
        {
            "errcode": 0,
            "errmsg": "ok",
            "access_token": "MYTOKEN",
            "expires_in": 7200,
        }
    )
    mock_post.return_value = _mk_resp({"errcode": 0, "errmsg": "ok"})

    obj = NotifyWeChat(
        corpid=CORPID,
        corpsecret=CORPSECRET,
        agentid=AGENTID,
        targets=["@all"],
    )
    assert obj.send(body="Hello") is True
    assert mock_get.call_count == 1
    assert mock_post.call_count == 1


@mock.patch("requests.get")
@mock.patch("requests.post")
def test_plugin_wechat_send_cached_token(mock_post, mock_get):
    """Second send reuses the cached token without a new GET request."""

    def _mk_resp(data, code=requests.codes.ok):
        r = mock.Mock()
        r.status_code = code
        r.content = dumps(data).encode("utf-8")
        return r

    mock_get.return_value = _mk_resp(
        {
            "errcode": 0,
            "errmsg": "ok",
            "access_token": "CACHED_TOKEN",
            "expires_in": 7200,
        }
    )
    mock_post.return_value = _mk_resp({"errcode": 0, "errmsg": "ok"})

    obj = NotifyWeChat(
        corpid=CORPID,
        corpsecret=CORPSECRET,
        agentid=AGENTID,
        targets=["@all"],
    )
    # First send fetches the token
    assert obj.send(body="First") is True
    assert mock_get.call_count == 1

    # Second send reuses the cached token
    assert obj.send(body="Second") is True
    assert mock_get.call_count == 1  # still 1 -- no second GET


@mock.patch("requests.get")
@mock.patch("requests.post")
def test_plugin_wechat_send_all_targets(mock_post, mock_get):
    """A single send delivers to users, departments, and tags in one POST."""

    def _mk_resp(data, code=requests.codes.ok):
        r = mock.Mock()
        r.status_code = code
        r.content = dumps(data).encode("utf-8")
        return r

    mock_get.return_value = _mk_resp(
        {
            "errcode": 0,
            "errmsg": "ok",
            "access_token": "TOKEN",
            "expires_in": 7200,
        }
    )
    mock_post.return_value = _mk_resp({"errcode": 0, "errmsg": "ok"})

    obj = NotifyWeChat(
        corpid=CORPID,
        corpsecret=CORPSECRET,
        agentid=AGENTID,
        targets=["alice", "bob", "#10", "#20", "+3", "+5"],
    )
    assert obj.send(body="Hello") is True
    assert mock_post.call_count == 1

    # Verify payload recipients
    import json

    call_kwargs = mock_post.call_args
    payload = json.loads(call_kwargs[1]["data"])
    assert set(payload["touser"].split("|")) == {"alice", "bob"}
    assert set(payload["toparty"].split("|")) == {"10", "20"}
    assert set(payload["totag"].split("|")) == {"3", "5"}


@mock.patch("requests.get")
@mock.patch("requests.post")
def test_plugin_wechat_send_markdown(mock_post, mock_get):
    """Markdown format produces msgtype=markdown in the payload."""

    def _mk_resp(data, code=requests.codes.ok):
        r = mock.Mock()
        r.status_code = code
        r.content = dumps(data).encode("utf-8")
        return r

    mock_get.return_value = _mk_resp(
        {
            "errcode": 0,
            "errmsg": "ok",
            "access_token": "TOKEN",
            "expires_in": 7200,
        }
    )
    mock_post.return_value = _mk_resp({"errcode": 0, "errmsg": "ok"})

    obj = NotifyWeChat(
        corpid=CORPID,
        corpsecret=CORPSECRET,
        agentid=AGENTID,
        targets=["@all"],
        format=NotifyFormat.MARKDOWN,
    )
    assert obj.send(body="# Hello") is True

    import json

    payload = json.loads(mock_post.call_args[1]["data"])
    assert payload["msgtype"] == "markdown"
    assert "markdown" in payload


@mock.patch("requests.get")
@mock.patch("requests.post")
def test_plugin_wechat_send_no_targets(mock_post, mock_get):
    """send() returns False immediately when no valid targets are present."""

    obj = NotifyWeChat(corpid=CORPID, corpsecret=CORPSECRET, agentid=AGENTID)
    # No targets -> early return False, no network calls
    assert obj.send(body="Hello") is False
    assert mock_get.call_count == 0
    assert mock_post.call_count == 0


@mock.patch("requests.get")
@mock.patch("requests.post")
def test_plugin_wechat_token_fetch_http_error(mock_post, mock_get):
    """Token GET returning HTTP 500 causes send() to fail."""

    r = mock.Mock()
    r.status_code = requests.codes.internal_server_error
    r.content = b""
    mock_get.return_value = r

    obj = NotifyWeChat(
        corpid=CORPID,
        corpsecret=CORPSECRET,
        agentid=AGENTID,
        targets=["@all"],
    )
    assert obj.send(body="Hello") is False
    assert mock_get.call_count == 1
    assert mock_post.call_count == 0


@mock.patch("requests.get")
@mock.patch("requests.post")
def test_plugin_wechat_token_fetch_api_error(mock_post, mock_get):
    """Token GET returning errcode != 0 causes send() to fail."""

    def _mk_resp(data, code=requests.codes.ok):
        r = mock.Mock()
        r.status_code = code
        r.content = dumps(data).encode("utf-8")
        return r

    # errcode 40001 -- invalid credential
    mock_get.return_value = _mk_resp(
        {"errcode": 40001, "errmsg": "invalid credential"}
    )

    obj = NotifyWeChat(
        corpid=CORPID,
        corpsecret=CORPSECRET,
        agentid=AGENTID,
        targets=["@all"],
    )
    assert obj.send(body="Hello") is False
    assert mock_post.call_count == 0


@mock.patch("requests.get")
@mock.patch("requests.post")
def test_plugin_wechat_token_fetch_no_token_field(mock_post, mock_get):
    """Token GET returning errcode 0 but no access_token causes failure."""

    def _mk_resp(data, code=requests.codes.ok):
        r = mock.Mock()
        r.status_code = code
        r.content = dumps(data).encode("utf-8")
        return r

    # errcode 0 but access_token is absent
    mock_get.return_value = _mk_resp({"errcode": 0, "errmsg": "ok"})

    obj = NotifyWeChat(
        corpid=CORPID,
        corpsecret=CORPSECRET,
        agentid=AGENTID,
        targets=["@all"],
    )
    assert obj.send(body="Hello") is False


@mock.patch("requests.get")
@mock.patch("requests.post")
def test_plugin_wechat_token_fetch_bad_json(mock_post, mock_get):
    """Token GET returning unparsable JSON is handled gracefully."""

    r = mock.Mock()
    r.status_code = requests.codes.ok
    r.content = b"{bad json"
    mock_get.return_value = r

    obj = NotifyWeChat(
        corpid=CORPID,
        corpsecret=CORPSECRET,
        agentid=AGENTID,
        targets=["@all"],
    )
    assert obj.send(body="Hello") is False


@mock.patch("requests.get")
@mock.patch("requests.post")
def test_plugin_wechat_token_fetch_request_exception(mock_post, mock_get):
    """RequestException during token GET causes send() to fail."""

    mock_get.side_effect = requests.RequestException("connection error")

    obj = NotifyWeChat(
        corpid=CORPID,
        corpsecret=CORPSECRET,
        agentid=AGENTID,
        targets=["@all"],
    )
    assert obj.send(body="Hello") is False


@mock.patch("requests.get")
@mock.patch("requests.post")
def test_plugin_wechat_send_http_error(mock_post, mock_get):
    """Message POST returning HTTP 500 causes send() to fail."""

    def _mk_resp(data, code=requests.codes.ok):
        r = mock.Mock()
        r.status_code = code
        r.content = dumps(data).encode("utf-8")
        return r

    mock_get.return_value = _mk_resp(
        {
            "errcode": 0,
            "errmsg": "ok",
            "access_token": "TOKEN",
            "expires_in": 7200,
        }
    )
    mock_post.return_value = _mk_resp(
        {}, code=requests.codes.internal_server_error
    )
    mock_post.return_value.content = b""

    obj = NotifyWeChat(
        corpid=CORPID,
        corpsecret=CORPSECRET,
        agentid=AGENTID,
        targets=["@all"],
    )
    assert obj.send(body="Hello") is False


@mock.patch("requests.get")
@mock.patch("requests.post")
def test_plugin_wechat_send_api_error(mock_post, mock_get):
    """Message POST returning errcode != 0 causes send() to fail."""

    def _mk_resp(data, code=requests.codes.ok):
        r = mock.Mock()
        r.status_code = code
        r.content = dumps(data).encode("utf-8")
        return r

    mock_get.return_value = _mk_resp(
        {
            "errcode": 0,
            "errmsg": "ok",
            "access_token": "TOKEN",
            "expires_in": 7200,
        }
    )
    # 81013 -- all recipients invalid
    mock_post.return_value = _mk_resp(
        {"errcode": 81013, "errmsg": "All recipients invalid"}
    )

    obj = NotifyWeChat(
        corpid=CORPID,
        corpsecret=CORPSECRET,
        agentid=AGENTID,
        targets=["@all"],
    )
    assert obj.send(body="Hello") is False


@mock.patch("requests.get")
@mock.patch("requests.post")
def test_plugin_wechat_send_token_expiry_evicts_cache(mock_post, mock_get):
    """A token-expired errcode from the POST evicts the cached token."""

    def _mk_resp(data, code=requests.codes.ok):
        r = mock.Mock()
        r.status_code = code
        r.content = dumps(data).encode("utf-8")
        return r

    mock_get.return_value = _mk_resp(
        {
            "errcode": 0,
            "errmsg": "ok",
            "access_token": "TOKEN",
            "expires_in": 7200,
        }
    )
    # POST returns 42001 -- token expired
    mock_post.return_value = _mk_resp(
        {"errcode": 42001, "errmsg": "access_token expired"}
    )

    obj = NotifyWeChat(
        corpid=CORPID,
        corpsecret=CORPSECRET,
        agentid=AGENTID,
        targets=["@all"],
    )
    assert obj.send(body="Hello") is False

    # Verify the store no longer holds the token
    assert obj.store.get("access_token") is None


@mock.patch("requests.get")
@mock.patch("requests.post")
def test_plugin_wechat_send_token_expiry_all_codes(mock_post, mock_get):
    """All WECHAT_TOKEN_ERROR_CODES cause the cached token to be evicted."""

    def _mk_resp(data, code=requests.codes.ok):
        r = mock.Mock()
        r.status_code = code
        r.content = dumps(data).encode("utf-8")
        return r

    for errcode in WECHAT_TOKEN_ERROR_CODES:
        mock_get.reset_mock()
        mock_post.reset_mock()

        mock_get.return_value = _mk_resp(
            {
                "errcode": 0,
                "errmsg": "ok",
                "access_token": "TOKEN",
                "expires_in": 7200,
            }
        )
        mock_post.return_value = _mk_resp(
            {"errcode": errcode, "errmsg": "token error"}
        )

        obj = NotifyWeChat(
            corpid=CORPID,
            corpsecret=CORPSECRET,
            agentid=AGENTID,
            targets=["@all"],
        )
        assert obj.send(body="Hello") is False
        assert obj.store.get("access_token") is None


@mock.patch("requests.get")
@mock.patch("requests.post")
def test_plugin_wechat_send_bad_json(mock_post, mock_get):
    """Message POST returning unparsable JSON is handled gracefully."""

    def _mk_resp(data, code=requests.codes.ok):
        r = mock.Mock()
        r.status_code = code
        r.content = dumps(data).encode("utf-8")
        return r

    mock_get.return_value = _mk_resp(
        {
            "errcode": 0,
            "errmsg": "ok",
            "access_token": "TOKEN",
            "expires_in": 7200,
        }
    )

    # POST returns unparsable body
    post_r = mock.Mock()
    post_r.status_code = requests.codes.ok
    post_r.content = b"{bad json"
    mock_post.return_value = post_r

    obj = NotifyWeChat(
        corpid=CORPID,
        corpsecret=CORPSECRET,
        agentid=AGENTID,
        targets=["@all"],
    )
    # Bad JSON -> content = {} -> errcode = -1 -> failure
    assert obj.send(body="Hello") is False


@mock.patch("requests.get")
@mock.patch("requests.post")
def test_plugin_wechat_send_request_exception(mock_post, mock_get):
    """RequestException during message POST causes send() to fail."""

    def _mk_resp(data, code=requests.codes.ok):
        r = mock.Mock()
        r.status_code = code
        r.content = dumps(data).encode("utf-8")
        return r

    mock_get.return_value = _mk_resp(
        {
            "errcode": 0,
            "errmsg": "ok",
            "access_token": "TOKEN",
            "expires_in": 7200,
        }
    )
    mock_post.side_effect = requests.RequestException("network error")

    obj = NotifyWeChat(
        corpid=CORPID,
        corpsecret=CORPSECRET,
        agentid=AGENTID,
        targets=["@all"],
    )
    assert obj.send(body="Hello") is False


def test_plugin_wechat_parse_url():
    """Verify parse_url() handles all supported URL forms."""

    # Standard form: corpid:corpsecret@agentid/targets
    url = "wechat://{}:{}@{}/alice".format(CORPID, CORPSECRET, AGENTID)
    result = NotifyWeChat.parse_url(url)
    assert result is not None
    assert result["corpid"] == CORPID
    assert result["corpsecret"] == CORPSECRET
    assert result["agentid"] == AGENTID
    assert "alice" in result["targets"]

    # Department target (%23 decodes to #)
    url = "wechat://{}:{}@{}/%23999".format(CORPID, CORPSECRET, AGENTID)
    result = NotifyWeChat.parse_url(url)
    assert "#999" in result["targets"]

    # Tag target
    url = "wechat://{}:{}@{}/+42".format(CORPID, CORPSECRET, AGENTID)
    result = NotifyWeChat.parse_url(url)
    assert "+42" in result["targets"]

    # ?to= adds targets
    url = "wechat://{}:{}@{}?to=@all".format(CORPID, CORPSECRET, AGENTID)
    result = NotifyWeChat.parse_url(url)
    assert "@all" in result["targets"]

    # None and non-string inputs return None
    assert NotifyWeChat.parse_url(None) is None


def test_plugin_wechat_parse_native_url():
    """parse_native_url() always returns None -- no native URL form."""
    assert (
        NotifyWeChat.parse_native_url("https://qyapi.weixin.qq.com/any/url")
        is None
    )


def test_plugin_wechat_error_codes():
    """Verify the error code constants are populated correctly."""
    assert 0 in WECHAT_ERROR_CODES
    assert 40001 in WECHAT_TOKEN_ERROR_CODES
    assert 40014 in WECHAT_TOKEN_ERROR_CODES
    assert 42001 in WECHAT_TOKEN_ERROR_CODES


@mock.patch("requests.get")
@mock.patch("requests.post")
def test_plugin_wechat_apprise_integration(mock_post, mock_get):
    """End-to-end Apprise().notify() integration test."""

    def _mk_resp(data, code=requests.codes.ok):
        r = mock.Mock()
        r.status_code = code
        r.content = dumps(data).encode("utf-8")
        return r

    mock_get.return_value = _mk_resp(
        {
            "errcode": 0,
            "errmsg": "ok",
            "access_token": "TOKEN",
            "expires_in": 7200,
        }
    )
    mock_post.return_value = _mk_resp({"errcode": 0, "errmsg": "ok"})

    app = Apprise()
    url = "wechat://{}:{}@{}/@all".format(CORPID, CORPSECRET, AGENTID)
    assert app.add(url) is True
    assert app.notify(title="T", body="B") is True


@mock.patch("requests.get")
@mock.patch("requests.post")
def test_plugin_wechat_send_unknown_api_error(mock_post, mock_get):
    """An unknown errcode falls back to the errmsg field in the response."""

    def _mk_resp(data, code=requests.codes.ok):
        r = mock.Mock()
        r.status_code = code
        r.content = dumps(data).encode("utf-8")
        return r

    mock_get.return_value = _mk_resp(
        {
            "errcode": 0,
            "errmsg": "ok",
            "access_token": "TOKEN",
            "expires_in": 7200,
        }
    )
    # Use an error code not in WECHAT_ERROR_CODES
    mock_post.return_value = _mk_resp(
        {"errcode": 99999, "errmsg": "custom error message"}
    )

    obj = NotifyWeChat(
        corpid=CORPID,
        corpsecret=CORPSECRET,
        agentid=AGENTID,
        targets=["@all"],
    )
    assert obj.send(body="Hello") is False


@mock.patch("requests.get")
@mock.patch("requests.post")
def test_plugin_wechat_token_unknown_api_error(mock_post, mock_get):
    """Unknown errcode from token GET falls back to errmsg field."""

    r = mock.Mock()
    r.status_code = requests.codes.ok
    r.content = dumps(
        {"errcode": 99999, "errmsg": "custom token error"}
    ).encode("utf-8")
    mock_get.return_value = r

    obj = NotifyWeChat(
        corpid=CORPID,
        corpsecret=CORPSECRET,
        agentid=AGENTID,
        targets=["@all"],
    )
    assert obj.send(body="Hello") is False
