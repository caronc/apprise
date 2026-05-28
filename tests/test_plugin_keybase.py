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
import logging
import os
import socket as _real_socket
from unittest import mock

import pytest
import requests as _requests

import apprise
from apprise import AppriseAttachment
from apprise.plugins.keybase import (
    KEYBASE_DEFAULT_CHANNEL,
    KEYBASE_DEFAULT_HOST,
    KEYBASE_DEFAULT_PORT,
    KeybaseMode,
    NotifyKeybase,
    keybase_default_socket,
)
from apprise.plugins.keybase.common import keybase_default_socket as _kds
from apprise.utils.saltpack import (
    AppriseSaltpackException,
)

logging.disable(logging.CRITICAL)

# Directory containing test fixture files (GIF, PNG, etc.)
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), "var")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _socket_ok(response=None):
    """Return a mock socket connection that yields a success response."""
    if response is None:
        response = {"result": {"message": "chat send", "id": 1}}
    conn = mock.MagicMock()
    conn.recv.return_value = json.dumps(response).encode("utf-8") + b"\n"
    return conn


def _socket_api_error(message="bad request"):
    """Return a mock socket connection that yields an API-level error."""
    response = {"error": {"code": 400, "message": message}}
    conn = mock.MagicMock()
    conn.recv.return_value = json.dumps(response).encode("utf-8") + b"\n"
    return conn


def _http_ok(response=None):
    """Return a mock requests.Response indicating HTTP 200 + success JSON."""
    if response is None:
        response = {"result": {"message": "chat send", "id": 1}}
    r = mock.MagicMock()
    r.status_code = 200
    r.json.return_value = response
    r.text = json.dumps(response)
    return r


def _http_error(status=500, message="internal error"):
    """Return a mock requests.Response indicating an HTTP error."""
    r = mock.MagicMock()
    r.status_code = status
    r.json.side_effect = ValueError("no json")
    r.text = message
    return r


# ---------------------------------------------------------------------------
# Instantiation and validation
# ---------------------------------------------------------------------------


def test_plugin_keybase_init_user():
    """Valid user DM target."""
    obj = NotifyKeybase(targets=["@alice"])
    assert obj.targets == [("user", "alice")]


def test_plugin_keybase_init_team_default_channel():
    """Valid team target defaults to 'general' channel."""
    obj = NotifyKeybase(targets=["myteam"])
    assert obj.targets == [("team", "myteam", KEYBASE_DEFAULT_CHANNEL)]


def test_plugin_keybase_init_team_explicit_channel():
    """Valid team target with explicit channel."""
    obj = NotifyKeybase(targets=["myteam#dev"])
    assert obj.targets == [("team", "myteam", "dev")]


def test_plugin_keybase_init_mixed_targets():
    """Multiple mixed targets are all parsed."""
    obj = NotifyKeybase(targets=["@alice", "myteam#general", "@bob"])
    assert ("user", "alice") in obj.targets
    assert ("team", "myteam", "general") in obj.targets
    assert ("user", "bob") in obj.targets
    assert len(obj.targets) == 3


def test_plugin_keybase_init_invalid_target_dropped():
    """Invalid targets are dropped and preserved in _invalid_targets."""
    obj = NotifyKeybase(targets=["@alice", "!!bad!!"])
    assert len(obj.targets) == 1
    assert obj.targets[0] == ("user", "alice")
    assert "!!bad!!" in obj._invalid_targets
    # url() preserves invalid targets for round-trip inspection
    url = obj.url()
    assert "alice" in url


def test_plugin_keybase_init_no_targets_raises():
    """No targets at all raises TypeError."""
    with pytest.raises(TypeError):
        NotifyKeybase(targets=[])


def test_plugin_keybase_init_only_invalid_targets_raises():
    """Only invalid targets raises TypeError."""
    with pytest.raises(TypeError):
        NotifyKeybase(targets=["!!!"])


# ---------------------------------------------------------------------------
# Mode detection
# ---------------------------------------------------------------------------


def test_plugin_keybase_default_mode_is_socket():
    """Default connection mode is socket."""
    obj = NotifyKeybase(targets=["@alice"])
    assert obj.mode == KeybaseMode.SOCKET


def test_plugin_keybase_mode_socket_explicit():
    """Explicit mode=socket sets socket mode."""
    obj = NotifyKeybase(targets=["@alice"], mode="socket")
    assert obj.mode == KeybaseMode.SOCKET


def test_plugin_keybase_mode_tcp_explicit():
    """Explicit mode=tcp sets TCP mode."""
    obj = NotifyKeybase(targets=["@alice"], mode="tcp")
    assert obj.mode == KeybaseMode.TCP


def test_plugin_keybase_mode_tcp_from_port():
    """Providing a port auto-selects TCP mode."""
    obj = NotifyKeybase(targets=["@alice"], port=3000)
    assert obj.mode == KeybaseMode.TCP
    assert obj.port == 3000


def test_plugin_keybase_mode_tcp_defaults_host_and_port():
    """TCP mode fills in default host and port when absent."""
    obj = NotifyKeybase(targets=["@alice"], mode="tcp")
    assert obj.host == KEYBASE_DEFAULT_HOST
    assert obj.port == KEYBASE_DEFAULT_PORT


def test_plugin_keybase_mode_socket_path_default():
    """Socket mode uses the platform default socket path."""
    obj = NotifyKeybase(targets=["@alice"])
    assert obj.socket_path == keybase_default_socket()


def test_plugin_keybase_mode_socket_path_custom():
    """A custom socket_path overrides the platform default."""
    obj = NotifyKeybase(targets=["@alice"], socket_path="/tmp/keybase.sock")
    assert obj.socket_path == "/tmp/keybase.sock"


# ---------------------------------------------------------------------------
# Signing-key validation
# ---------------------------------------------------------------------------


def test_plugin_keybase_init_sigkey_valid():
    """A valid 64-char hex signing key is accepted."""
    sigkey = "aa" * 32
    obj = NotifyKeybase(targets=["@alice"], sigkey=sigkey)
    assert obj.sigkey == sigkey.lower()


def test_plugin_keybase_init_sigkey_uppercase_normalised():
    """Uppercase hex in sigkey is normalised to lowercase."""
    sigkey = "AB" * 32
    obj = NotifyKeybase(targets=["@alice"], sigkey=sigkey)
    assert obj.sigkey == sigkey.lower()


def test_plugin_keybase_init_sigkey_too_short_raises():
    """A sigkey that is too short raises TypeError."""
    with pytest.raises(TypeError):
        NotifyKeybase(targets=["@alice"], sigkey="aabb")


def test_plugin_keybase_init_sigkey_invalid_chars_raises():
    """A sigkey with non-hex characters raises TypeError."""
    with pytest.raises(TypeError):
        NotifyKeybase(targets=["@alice"], sigkey="zz" * 32)


def test_plugin_keybase_init_sigkey_none_accepted():
    """No signing key produces a plugin without Saltpack signing."""
    obj = NotifyKeybase(targets=["@alice"])
    assert obj.sigkey is None


# ---------------------------------------------------------------------------
# URL round-trip (socket mode)
# ---------------------------------------------------------------------------


def test_plugin_keybase_url_user():
    """User DM URL round-trips correctly."""
    obj = NotifyKeybase(targets=["@alice"])
    url = obj.url()
    assert "@alice" in url
    r = NotifyKeybase.parse_url(url)
    obj2 = NotifyKeybase(**r)
    assert obj2.targets == obj.targets


def test_plugin_keybase_url_team():
    """Team URL round-trips correctly."""
    obj = NotifyKeybase(targets=["myteam"])
    url = obj.url()
    assert "myteam" in url
    r = NotifyKeybase.parse_url(url)
    obj2 = NotifyKeybase(**r)
    assert obj2.targets == obj.targets


def test_plugin_keybase_url_team_channel():
    """Team+channel URL round-trips correctly."""
    obj = NotifyKeybase(targets=["myteam#dev"])
    url = obj.url()
    # # must be percent-encoded in the generated URL
    assert "%23" in url
    r = NotifyKeybase.parse_url(url)
    obj2 = NotifyKeybase(**r)
    assert obj2.targets == obj.targets


def test_plugin_keybase_url_mixed():
    """Mixed targets round-trip correctly."""
    obj = NotifyKeybase(targets=["@alice", "myteam#dev"])
    url = obj.url()
    r = NotifyKeybase.parse_url(url)
    obj2 = NotifyKeybase(**r)
    assert obj2.targets == obj.targets


def test_plugin_keybase_url_privacy():
    """Privacy URL returns a non-empty string."""
    obj = NotifyKeybase(targets=["@alice"])
    assert isinstance(obj.url(privacy=True), str)
    assert len(obj.url(privacy=True)) > 0


def test_plugin_keybase_url_identifier_is_false():
    """url_id() returns None (url_identifier = False)."""
    obj = NotifyKeybase(targets=["@alice"])
    assert obj.url_id() is None


def test_plugin_keybase_url_socket_mode_contains_mode_param():
    """Socket mode URL always contains mode=socket."""
    obj = NotifyKeybase(targets=["@alice"])
    assert "mode=socket" in obj.url()


def test_plugin_keybase_url_custom_socket_path_included():
    """Custom socket path is included in the URL."""
    obj = NotifyKeybase(
        targets=["@alice"], socket_path="/tmp/custom-keybase.sock"
    )
    url = obj.url()
    assert "socket=" in url
    r = NotifyKeybase.parse_url(url)
    obj2 = NotifyKeybase(**r)
    assert obj2.socket_path == "/tmp/custom-keybase.sock"


def test_plugin_keybase_url_default_socket_path_omitted():
    """Default socket path is omitted from the URL."""
    obj = NotifyKeybase(targets=["@alice"])
    assert "socket=" not in obj.url()


# ---------------------------------------------------------------------------
# URL round-trip (TCP mode)
# ---------------------------------------------------------------------------


def test_plugin_keybase_url_tcp_mode():
    """TCP mode URL contains host, port, and mode=tcp."""
    obj = NotifyKeybase(targets=["@alice"], host="localhost", port=4000)
    url = obj.url()
    assert "localhost" in url
    assert "4000" in url
    assert "mode=tcp" in url


def test_plugin_keybase_url_tcp_roundtrip():
    """TCP mode URL round-trips preserving host, port, mode."""
    obj = NotifyKeybase(targets=["@alice"], host="localhost", port=3000)
    url = obj.url()
    r = NotifyKeybase.parse_url(url)
    obj2 = NotifyKeybase(**r)
    assert obj2.mode == KeybaseMode.TCP
    assert obj2.host == "localhost"
    assert obj2.port == 3000
    assert obj2.targets == obj.targets


# ---------------------------------------------------------------------------
# URL with sigkey
# ---------------------------------------------------------------------------


def test_plugin_keybase_url_with_sigkey():
    """A sigkey appears in the URL and round-trips."""
    sigkey = "ab" * 32
    obj = NotifyKeybase(targets=["@alice"], sigkey=sigkey)
    url = obj.url()
    assert sigkey in url
    r = NotifyKeybase.parse_url(url)
    obj2 = NotifyKeybase(**r)
    assert obj2.sigkey == sigkey


def test_plugin_keybase_url_sigkey_hidden_in_privacy_mode():
    """The sigkey is masked when privacy=True."""
    sigkey = "ab" * 32
    obj = NotifyKeybase(targets=["@alice"], sigkey=sigkey)
    priv_url = obj.url(privacy=True)
    assert sigkey not in priv_url


# ---------------------------------------------------------------------------
# parse_url edge cases
# ---------------------------------------------------------------------------


def test_plugin_keybase_parse_url_at_in_authority():
    """keybase://@alice is parsed as a user DM."""
    r = NotifyKeybase.parse_url("keybase://@alice")
    obj = NotifyKeybase(**r)
    assert obj.targets == [("user", "alice")]


def test_plugin_keybase_parse_url_team_host():
    """keybase://myteam is parsed as a team message."""
    r = NotifyKeybase.parse_url("keybase://myteam")
    obj = NotifyKeybase(**r)
    assert obj.targets == [("team", "myteam", KEYBASE_DEFAULT_CHANNEL)]


def test_plugin_keybase_parse_url_team_channel_host():
    """keybase://myteam%23dev is parsed as team + channel."""
    r = NotifyKeybase.parse_url("keybase://myteam%23dev")
    obj = NotifyKeybase(**r)
    assert obj.targets == [("team", "myteam", "dev")]


def test_plugin_keybase_parse_url_to_param():
    """?to= query param populates targets."""
    r = NotifyKeybase.parse_url("keybase://_/?to=@alice")
    obj = NotifyKeybase(**r)
    assert ("user", "alice") in obj.targets


def test_plugin_keybase_parse_url_sigkey_param():
    """?sigkey= query param is extracted and stored."""
    sigkey = "cd" * 32
    url = "keybase://_/@alice?sigkey={}".format(sigkey)
    r = NotifyKeybase.parse_url(url)
    obj = NotifyKeybase(**r)
    assert obj.sigkey == sigkey


def test_plugin_keybase_parse_url_mode_socket():
    """?mode=socket is parsed correctly."""
    r = NotifyKeybase.parse_url("keybase://_/@alice?mode=socket")
    obj = NotifyKeybase(**r)
    assert obj.mode == KeybaseMode.SOCKET


def test_plugin_keybase_parse_url_mode_tcp():
    """?mode=tcp is parsed correctly and host/port defaults applied."""
    r = NotifyKeybase.parse_url("keybase://_/@alice?mode=tcp")
    obj = NotifyKeybase(**r)
    assert obj.mode == KeybaseMode.TCP
    assert obj.host == KEYBASE_DEFAULT_HOST
    assert obj.port == KEYBASE_DEFAULT_PORT


def test_plugin_keybase_parse_url_tcp_authority():
    """keybase://localhost:3000/@alice sets TCP mode via port."""
    r = NotifyKeybase.parse_url("keybase://localhost:3000/@alice")
    obj = NotifyKeybase(**r)
    assert obj.mode == KeybaseMode.TCP
    assert obj.host == "localhost"
    assert obj.port == 3000
    # "localhost" must NOT be treated as a target
    assert obj.targets == [("user", "alice")]


def test_plugin_keybase_parse_url_custom_socket():
    """?socket= is mapped to socket_path."""
    url = "keybase://_/@alice?socket=/tmp/keybase.sock"
    r = NotifyKeybase.parse_url(url)
    obj = NotifyKeybase(**r)
    assert obj.socket_path == "/tmp/keybase.sock"


def test_plugin_keybase_parse_url_hash_channel_literal():
    """Literal '#' in URL is treated as '%23' -- channel is preserved."""
    r = NotifyKeybase.parse_url("keybase://_/myteam#dev")
    obj = NotifyKeybase(**r)
    assert obj.targets == [("team", "myteam", "dev")]


def test_plugin_keybase_parse_url_hash_channel_multiple_targets():
    """Multiple targets with literal '#' all parse correctly."""
    r = NotifyKeybase.parse_url("keybase://_/@alice/@bob/myteam#general")
    obj = NotifyKeybase(**r)
    assert ("user", "alice") in obj.targets
    assert ("user", "bob") in obj.targets
    assert ("team", "myteam", "general") in obj.targets


def test_plugin_keybase_parse_url_invalid_returns_none():
    """parse_url returns None for unparseable input."""
    result = NotifyKeybase.parse_url("not-a-url")
    assert result is None or isinstance(result, dict)


def test_plugin_keybase_parse_url_no_targets():
    """parse_url with no actual targets yields a TypeError on init."""
    r = NotifyKeybase.parse_url("keybase://_/?")
    with pytest.raises(TypeError):
        NotifyKeybase(**r)


# ---------------------------------------------------------------------------
# send() via socket mode -- success paths
# ---------------------------------------------------------------------------


@mock.patch.object(NotifyKeybase, "_stat_socket_path")
@mock.patch("apprise.plugins.keybase.base._socket.socket")
def test_plugin_keybase_send_user_dm_socket(mock_sock_cls, mock_stat_sp):
    """Successful DM send via Unix socket."""
    mock_sock_cls.return_value = _socket_ok()

    obj = NotifyKeybase(targets=["@alice"])
    assert obj.notify(title="Hi", body="Hello") is True

    # Verify the socket was connected to the expected path
    conn = mock_sock_cls.return_value
    conn.connect.assert_called_once_with(obj.socket_path)

    # Verify the payload structure
    sent_raw = conn.sendall.call_args[0][0]
    payload = json.loads(sent_raw.rstrip(b"\n"))
    assert payload["method"] == "send"
    ch = payload["params"]["options"]["channel"]
    assert ch["name"] == "alice"
    assert "topic_name" not in ch


@mock.patch.object(NotifyKeybase, "_stat_socket_path")
@mock.patch("apprise.plugins.keybase.base._socket.socket")
def test_plugin_keybase_send_team_socket(mock_sock_cls, mock_stat_sp):
    """Successful team channel send via socket."""
    mock_sock_cls.return_value = _socket_ok()

    obj = NotifyKeybase(targets=["myteam"])
    assert obj.notify(body="Hello") is True

    sent_raw = mock_sock_cls.return_value.sendall.call_args[0][0]
    payload = json.loads(sent_raw.rstrip(b"\n"))
    ch = payload["params"]["options"]["channel"]
    assert ch["name"] == "myteam"
    assert ch["topic_name"] == "general"
    assert ch["members_type"] == "team"


@mock.patch.object(NotifyKeybase, "_stat_socket_path")
@mock.patch("apprise.plugins.keybase.base._socket.socket")
def test_plugin_keybase_send_team_channel_socket(mock_sock_cls, mock_stat_sp):
    """Successful team+channel send via socket."""
    mock_sock_cls.return_value = _socket_ok()

    obj = NotifyKeybase(targets=["myteam#dev"])
    assert obj.notify(body="Hello") is True

    sent_raw = mock_sock_cls.return_value.sendall.call_args[0][0]
    payload = json.loads(sent_raw.rstrip(b"\n"))
    ch = payload["params"]["options"]["channel"]
    assert ch["name"] == "myteam"
    assert ch["topic_name"] == "dev"


@mock.patch.object(NotifyKeybase, "_stat_socket_path")
@mock.patch("apprise.plugins.keybase.base._socket.socket")
def test_plugin_keybase_send_multiple_targets_socket(
    mock_sock_cls, mock_stat_sp
):
    """Send to multiple targets via socket; all succeed."""
    mock_sock_cls.return_value = _socket_ok()

    obj = NotifyKeybase(targets=["@alice", "myteam"])
    assert obj.notify(body="Hello") is True

    # One socket.sendall call per target
    assert mock_sock_cls.return_value.sendall.call_count == 2


@mock.patch.object(NotifyKeybase, "_stat_socket_path")
@mock.patch("apprise.plugins.keybase.base._socket.socket")
def test_plugin_keybase_send_partial_failure_socket(
    mock_sock_cls, mock_stat_sp
):
    """If one of two socket sends fails, send() returns False."""
    # First call succeeds; second raises OSError
    first_conn = _socket_ok()
    second_conn = mock.MagicMock()
    second_conn.connect.side_effect = OSError("connection refused")
    mock_sock_cls.side_effect = [first_conn, second_conn]

    obj = NotifyKeybase(targets=["@alice", "myteam"])
    assert obj.notify(body="Hello") is False


# ---------------------------------------------------------------------------
# send() via socket mode -- error paths
# ---------------------------------------------------------------------------


@mock.patch.object(NotifyKeybase, "_stat_socket_path")
@mock.patch("apprise.plugins.keybase.base._socket.socket")
def test_plugin_keybase_send_socket_connection_refused(
    mock_sock_cls, mock_stat_sp
):
    """ConnectionRefusedError from socket is handled gracefully."""
    conn = mock.MagicMock()
    conn.connect.side_effect = OSError("connection refused")
    mock_sock_cls.return_value = conn

    obj = NotifyKeybase(targets=["@alice"])
    assert obj.notify(body="Hello") is False


@mock.patch.object(NotifyKeybase, "_stat_socket_path")
@mock.patch("apprise.plugins.keybase.base._socket.socket")
def test_plugin_keybase_send_socket_file_not_found(
    mock_sock_cls, mock_stat_sp
):
    """FileNotFoundError (missing socket file) is handled gracefully."""
    conn = mock.MagicMock()
    conn.connect.side_effect = FileNotFoundError("no such file")
    mock_sock_cls.return_value = conn

    obj = NotifyKeybase(targets=["@alice"])
    assert obj.notify(body="Hello") is False


@mock.patch.object(NotifyKeybase, "_stat_socket_path")
@mock.patch("apprise.plugins.keybase.base._socket.socket")
def test_plugin_keybase_send_socket_timeout(mock_sock_cls, mock_stat_sp):
    """Socket timeout is handled gracefully."""
    conn = mock.MagicMock()
    conn.recv.side_effect = _real_socket.timeout("timed out")
    mock_sock_cls.return_value = conn

    obj = NotifyKeybase(targets=["@alice"])
    assert obj.notify(body="Hello") is False


@mock.patch.object(NotifyKeybase, "_stat_socket_path")
@mock.patch("apprise.plugins.keybase.base._socket.socket")
def test_plugin_keybase_send_socket_api_error(mock_sock_cls, mock_stat_sp):
    """API-level error in socket response returns False."""
    mock_sock_cls.return_value = _socket_api_error("user not found")

    obj = NotifyKeybase(targets=["@alice"])
    assert obj.notify(body="Hello") is False


@mock.patch.object(NotifyKeybase, "_stat_socket_path")
@mock.patch("apprise.plugins.keybase.base._socket.socket")
def test_plugin_keybase_send_socket_api_error_non_dict(
    mock_sock_cls, mock_stat_sp
):
    """API error when 'error' value is not a dict."""
    conn = mock.MagicMock()
    conn.recv.return_value = (
        json.dumps({"error": "string error"}).encode() + b"\n"
    )
    mock_sock_cls.return_value = conn

    obj = NotifyKeybase(targets=["@alice"])
    assert obj.notify(body="Hello") is False


@mock.patch.object(NotifyKeybase, "_stat_socket_path")
@mock.patch("apprise.plugins.keybase.base._socket.socket")
def test_plugin_keybase_send_socket_bad_json(mock_sock_cls, mock_stat_sp):
    """Non-JSON socket response is treated as success (no error key)."""
    conn = mock.MagicMock()
    conn.recv.return_value = b"not json\n"
    mock_sock_cls.return_value = conn

    obj = NotifyKeybase(targets=["@alice"])
    assert obj.notify(body="Hello") is True


@mock.patch.object(NotifyKeybase, "_stat_socket_path")
@mock.patch("apprise.plugins.keybase.base._socket.socket")
def test_plugin_keybase_send_socket_empty_response(
    mock_sock_cls, mock_stat_sp
):
    """Empty socket response is treated as success."""
    conn = mock.MagicMock()
    # recv returns empty bytes -> connection closed mid-response
    conn.recv.return_value = b""
    mock_sock_cls.return_value = conn

    obj = NotifyKeybase(targets=["@alice"])
    assert obj.notify(body="Hello") is True


@mock.patch("apprise.plugins.keybase.base._socket.socket")
def test_plugin_keybase_send_socket_no_af_unix(mock_sock_cls):
    """OSError raised when AF_UNIX is unavailable (e.g. old Windows)."""
    with mock.patch(
        "apprise.plugins.keybase.base._socket",
        spec=[],  # spec=[] removes all attributes including AF_UNIX
    ):
        obj = NotifyKeybase(targets=["@alice"])
        assert obj.notify(body="Hello") is False


# ---------------------------------------------------------------------------
# send() via TCP mode -- success paths
# ---------------------------------------------------------------------------


@mock.patch("apprise.plugins.keybase.base.requests.post")
def test_plugin_keybase_send_user_dm_tcp(mock_post):
    """Successful DM send via TCP mode."""
    mock_post.return_value = _http_ok()

    obj = NotifyKeybase(targets=["@alice"], host="localhost", port=3000)
    assert obj.notify(body="Hello") is True

    # Verify the HTTP call was made to the correct endpoint
    call_url = mock_post.call_args[0][0]
    assert "localhost:3000" in call_url

    # Verify the payload structure
    payload = mock_post.call_args[1]["json"]
    assert payload["method"] == "send"
    ch = payload["params"]["options"]["channel"]
    assert ch["name"] == "alice"


@mock.patch("apprise.plugins.keybase.base.requests.post")
def test_plugin_keybase_send_team_tcp(mock_post):
    """Successful team channel send via TCP."""
    mock_post.return_value = _http_ok()

    obj = NotifyKeybase(targets=["myteam"], host="localhost", port=3000)
    assert obj.notify(body="Hello") is True

    payload = mock_post.call_args[1]["json"]
    ch = payload["params"]["options"]["channel"]
    assert ch["name"] == "myteam"
    assert ch["topic_name"] == "general"
    assert ch["members_type"] == "team"


@mock.patch("apprise.plugins.keybase.base.requests.post")
def test_plugin_keybase_send_multiple_targets_tcp(mock_post):
    """Send to multiple targets via TCP; all succeed."""
    mock_post.return_value = _http_ok()

    obj = NotifyKeybase(
        targets=["@alice", "myteam"], host="localhost", port=3000
    )
    assert obj.notify(body="Hello") is True

    # One HTTP POST per target
    assert mock_post.call_count == 2


# ---------------------------------------------------------------------------
# send() via TCP mode -- error paths
# ---------------------------------------------------------------------------


@mock.patch("apprise.plugins.keybase.base.requests.post")
def test_plugin_keybase_send_tcp_http_error(mock_post):
    """Non-200 HTTP response returns False."""
    mock_post.return_value = _http_error(status=500)

    obj = NotifyKeybase(targets=["@alice"], host="localhost", port=3000)
    assert obj.notify(body="Hello") is False


@mock.patch("apprise.plugins.keybase.base.requests.post")
def test_plugin_keybase_send_tcp_api_error(mock_post):
    """API-level error in the TCP JSON response returns False."""
    r = mock.MagicMock()
    r.status_code = 200
    r.json.return_value = {"error": {"code": 400, "message": "user not found"}}
    mock_post.return_value = r

    obj = NotifyKeybase(targets=["@alice"], host="localhost", port=3000)
    assert obj.notify(body="Hello") is False


@mock.patch("apprise.plugins.keybase.base.requests.post")
def test_plugin_keybase_send_tcp_request_exception(mock_post):
    """requests.RequestException is handled gracefully."""
    mock_post.side_effect = _requests.RequestException("timeout")

    obj = NotifyKeybase(targets=["@alice"], host="localhost", port=3000)
    assert obj.notify(body="Hello") is False


@mock.patch("apprise.plugins.keybase.base.requests.post")
def test_plugin_keybase_send_tcp_bad_json_response(mock_post):
    """Non-JSON HTTP response body is treated as success (no error key)."""
    r = mock.MagicMock()
    r.status_code = 200
    r.json.side_effect = ValueError("no json")
    mock_post.return_value = r

    obj = NotifyKeybase(targets=["@alice"], host="localhost", port=3000)
    assert obj.notify(body="Hello") is True


@mock.patch("apprise.plugins.keybase.base.requests.post")
def test_plugin_keybase_send_tcp_partial_failure(mock_post):
    """Partial failure across multiple targets returns False."""
    mock_post.side_effect = [
        _http_ok(),
        _requests.RequestException("connection refused"),
    ]

    obj = NotifyKeybase(
        targets=["@alice", "myteam"], host="localhost", port=3000
    )
    assert obj.notify(body="Hello") is False


# ---------------------------------------------------------------------------
# send() -- Saltpack signing paths
# ---------------------------------------------------------------------------


@mock.patch.object(NotifyKeybase, "_stat_socket_path")
@mock.patch("apprise.plugins.keybase.base._socket.socket")
@mock.patch(
    "apprise.plugins.keybase.base.AppriseSaltpackController.sign",
    return_value=(
        ". BEGIN KEYBASE SALTPACK SIGNED MESSAGE.\nabc\n"
        ". END KEYBASE SALTPACK SIGNED MESSAGE."
    ),
)
def test_plugin_keybase_send_with_sigkey_calls_sign(
    mock_sign, mock_sock_cls, mock_stat_sp
):
    """When sigkey is set and NACL is available, sign() is called."""
    mock_sock_cls.return_value = _socket_ok()
    sigkey = "ab" * 32

    with mock.patch("apprise.plugins.keybase.base.NACL_SUPPORT", True):
        obj = NotifyKeybase(targets=["@alice"], sigkey=sigkey)
        assert obj.notify(body="Hello") is True

    # sign() must have been called with the original body and key
    assert mock_sign.called
    assert mock_sign.call_args[0][0] == "Hello"
    assert mock_sign.call_args[0][1] == sigkey

    # The signed message must appear in the socket payload
    sent_raw = mock_sock_cls.return_value.sendall.call_args[0][0]
    payload = json.loads(sent_raw.rstrip(b"\n"))
    body = payload["params"]["options"]["message"]["body"]
    assert "SALTPACK SIGNED MESSAGE" in body


def test_plugin_keybase_send_sigkey_no_nacl():
    """When sigkey is set but NACL_SUPPORT is False, send() fails."""
    sigkey = "ab" * 32
    obj = NotifyKeybase(targets=["@alice"], sigkey=sigkey)
    with mock.patch("apprise.plugins.keybase.base.NACL_SUPPORT", False):
        assert obj.notify(body="Hello") is False


@mock.patch("apprise.plugins.keybase.base._socket.socket")
@mock.patch(
    "apprise.plugins.keybase.base.AppriseSaltpackController.sign",
    side_effect=AppriseSaltpackException("key error"),
)
def test_plugin_keybase_send_sigkey_sign_exception(mock_sign, mock_sock_cls):
    """AppriseSaltpackException from sign() causes send() to return False."""
    mock_sock_cls.return_value = _socket_ok()
    sigkey = "ab" * 32

    with mock.patch("apprise.plugins.keybase.base.NACL_SUPPORT", True):
        obj = NotifyKeybase(targets=["@alice"], sigkey=sigkey)
        assert obj.notify(body="Hello") is False

    # Socket must NOT have been called since signing failed first
    assert not mock_sock_cls.return_value.sendall.called


# ---------------------------------------------------------------------------
# Apprise integration
# ---------------------------------------------------------------------------


@mock.patch.object(NotifyKeybase, "_stat_socket_path")
@mock.patch("apprise.plugins.keybase.base._socket.socket")
def test_plugin_keybase_apprise_integration(mock_sock_cls, mock_stat_sp):
    """Apprise.add() and notify() work end-to-end via socket mode."""
    mock_sock_cls.return_value = _socket_ok()

    a = apprise.Apprise()
    assert a.add("keybase://_/@alice/myteam%23general") is True
    assert a.notify(title="Title", body="Body") is True


# ---------------------------------------------------------------------------
# socket path security validation
# ---------------------------------------------------------------------------


def test_plugin_keybase_socket_path_no_keybase_in_path_raises():
    """socket= without 'keybase' in the path is rejected at init."""
    with pytest.raises(TypeError, match=r"[Kk]eybase"):
        NotifyKeybase(
            targets=["@alice"],
            socket_path="/var/run/docker.sock",
        )


def test_plugin_keybase_socket_path_non_socket_file_raises():
    """socket_path pointing at a regular file raises TypeError at init."""
    with mock.patch("os.stat") as mock_stat:
        # Simulate a regular file (S_IFREG, mode 0o100644)
        mock_stat.return_value.st_mode = 0o100644
        with pytest.raises(TypeError, match=r"not.*socket"):
            NotifyKeybase(
                targets=["@alice"],
                socket_path="/run/keybase/not-a-socket",
            )


def test_plugin_keybase_socket_path_nonexistent_accepted_at_init():
    """Non-existent socket_path is accepted at init (service may be down)."""
    with mock.patch("os.stat", side_effect=OSError("no such file")):
        # Should not raise -- service is just not running yet
        obj = NotifyKeybase(
            targets=["@alice"],
            socket_path="/tmp/not_there-keybase.sock",
        )
    assert obj.socket_path == "/tmp/not_there-keybase.sock"


@mock.patch.object(
    NotifyKeybase,
    "_stat_socket_path",
    side_effect=OSError("Path is not a Unix socket: /fake"),
)
@mock.patch("apprise.plugins.keybase.base._socket.socket")
def test_plugin_keybase_send_socket_path_not_socket_at_send(
    mock_sock_cls, mock_stat_sp
):
    """send() returns False when socket_path exists but is not a socket."""
    obj = NotifyKeybase(targets=["@alice"])
    assert obj.notify(body="Hello") is False

    # socket.socket() must never be called on a non-socket path
    assert not mock_sock_cls.called


@mock.patch.object(
    NotifyKeybase,
    "_stat_socket_path",
    side_effect=OSError("Keybase socket not found: /fake"),
)
@mock.patch("apprise.plugins.keybase.base._socket.socket")
def test_plugin_keybase_send_socket_path_missing_at_send(
    mock_sock_cls, mock_stat_sp
):
    """send() returns False when socket_path is missing at send time."""
    obj = NotifyKeybase(targets=["@alice"])
    assert obj.notify(body="Hello") is False

    assert not mock_sock_cls.called


# ---------------------------------------------------------------------------
# keybase_default_socket() -- platform branches
# ---------------------------------------------------------------------------


def test_keybase_default_socket_windows():
    """Windows path returns the named pipe."""
    with mock.patch("apprise.plugins.keybase.common.sys.platform", "win32"):
        path = _kds()
    assert path == r"\\.\pipe\keybase.service"


def test_keybase_default_socket_macos():
    """macOS path returns a Library/Group Containers path."""
    with mock.patch("apprise.plugins.keybase.common.sys.platform", "darwin"):
        path = _kds()
    assert "Library" in path
    assert "keybased.sock" in path


def test_keybase_default_socket_linux():
    """Linux path uses XDG_RUNTIME_DIR when set."""
    with (
        mock.patch("apprise.plugins.keybase.common.sys.platform", "linux"),
        mock.patch.dict(
            "os.environ",
            {"XDG_RUNTIME_DIR": "/run/user/1234"},
            clear=False,
        ),
    ):
        path = _kds()
    assert path == "/run/user/1234/keybase/keybased.sock"


# ---------------------------------------------------------------------------
# _send_socket() -- multi-chunk response
# ---------------------------------------------------------------------------


@mock.patch.object(NotifyKeybase, "_stat_socket_path")
@mock.patch("apprise.plugins.keybase.base._socket.socket")
def test_plugin_keybase_send_socket_chunked_response(
    mock_sock_cls, mock_stat_sp
):
    """Socket response arriving in two chunks is reassembled correctly."""
    response = json.dumps({"result": {"id": 1}}).encode() + b"\n"
    # Split so the first chunk has no newline; second chunk completes it
    conn = mock.MagicMock()
    conn.recv.side_effect = [response[:10], response[10:]]
    mock_sock_cls.return_value = conn

    obj = NotifyKeybase(targets=["@alice"])
    assert obj.notify(body="Hello") is True


# ---------------------------------------------------------------------------
# _stat_socket_path() -- unit tests
# ---------------------------------------------------------------------------


def test_stat_socket_path_valid_socket():
    """_stat_socket_path does not raise for a genuine socket file."""
    obj = NotifyKeybase(targets=["@alice"])
    with mock.patch("os.stat") as mock_stat:
        # Simulate a Unix socket (S_IFSOCK = 0o140000, mode 0o140777)
        mock_stat.return_value.st_mode = 0o140777
        # Should not raise
        obj._stat_socket_path()


def test_stat_socket_path_regular_file_raises():
    """_stat_socket_path raises OSError when path is a regular file."""
    obj = NotifyKeybase(targets=["@alice"])
    with mock.patch("os.stat") as mock_stat:
        # Simulate a regular file (S_IFREG = 0o100000, mode 0o100644)
        mock_stat.return_value.st_mode = 0o100644
        with pytest.raises(OSError, match="not a Unix socket"):
            obj._stat_socket_path()


def test_stat_socket_path_missing_raises():
    """_stat_socket_path raises OSError when path does not exist."""
    obj = NotifyKeybase(targets=["@alice"])
    with (
        mock.patch("os.stat", side_effect=FileNotFoundError("no such file")),
        pytest.raises(OSError, match="socket not found"),
    ):
        obj._stat_socket_path()


# ---------------------------------------------------------------------------
# send() -- attachment paths
# ---------------------------------------------------------------------------


@mock.patch.object(NotifyKeybase, "_stat_socket_path")
@mock.patch("apprise.plugins.keybase.base._socket.socket")
def test_plugin_keybase_send_attachment_socket_success(
    mock_sock_cls, mock_stat_sp
):
    """Attachment is dispatched after the text message via socket."""
    mock_sock_cls.return_value = _socket_ok()

    path = os.path.join(TEST_VAR_DIR, "apprise-test.gif")
    attach = AppriseAttachment(path)

    obj = NotifyKeybase(targets=["@alice"])
    assert obj.notify(body="Hello", attach=attach) is True

    conn = mock_sock_cls.return_value
    # One send for text, one for the attachment
    assert conn.sendall.call_count == 2

    # Verify the attach payload structure
    raw = conn.sendall.call_args_list[1][0][0]
    payload = json.loads(raw.rstrip(b"\n"))
    assert payload["method"] == "attach"
    opts = payload["params"]["options"]
    assert opts["channel"]["name"] == "alice"
    assert opts["filename"] == path
    assert opts["title"] == "apprise-test.gif"


@mock.patch("apprise.plugins.keybase.base.requests.post")
def test_plugin_keybase_send_attachment_tcp_success(mock_post):
    """Attachment is dispatched after the text message via TCP."""
    mock_post.return_value = _http_ok()

    path = os.path.join(TEST_VAR_DIR, "apprise-test.gif")
    attach = AppriseAttachment(path)

    obj = NotifyKeybase(targets=["@alice"], host="localhost", port=3000)
    assert obj.notify(body="Hello", attach=attach) is True

    # One HTTP POST for text, one for the attachment
    assert mock_post.call_count == 2

    attach_payload = mock_post.call_args_list[1][1]["json"]
    assert attach_payload["method"] == "attach"
    opts = attach_payload["params"]["options"]
    assert opts["channel"]["name"] == "alice"
    assert opts["filename"] == path


@mock.patch.object(NotifyKeybase, "_stat_socket_path")
@mock.patch("apprise.plugins.keybase.base._socket.socket")
def test_plugin_keybase_send_attachment_multiple(mock_sock_cls, mock_stat_sp):
    """Multiple attachments are each dispatched in order."""
    mock_sock_cls.return_value = _socket_ok()

    path = os.path.join(TEST_VAR_DIR, "apprise-test.gif")
    attach = AppriseAttachment((path, path, path))

    obj = NotifyKeybase(targets=["@alice"])
    assert obj.notify(body="Hello", attach=attach) is True

    # 1 text + 3 attachments = 4 total sendall calls
    assert mock_sock_cls.return_value.sendall.call_count == 4


@mock.patch.object(NotifyKeybase, "_stat_socket_path")
@mock.patch("apprise.plugins.keybase.base._socket.socket")
def test_plugin_keybase_send_attachment_inaccessible(
    mock_sock_cls, mock_stat_sp
):
    """Inaccessible attachment is skipped and send() returns False."""
    mock_sock_cls.return_value = _socket_ok()

    # Non-existent file -> attachment is inaccessible
    attach = AppriseAttachment("/path/does/not/exist/apprise-test.gif")

    obj = NotifyKeybase(targets=["@alice"])
    assert obj.notify(body="Hello", attach=attach) is False

    # Text message was still sent; no attachment sendall
    assert mock_sock_cls.return_value.sendall.call_count == 1


@mock.patch.object(NotifyKeybase, "_stat_socket_path")
@mock.patch("apprise.plugins.keybase.base._socket.socket")
def test_plugin_keybase_send_attachment_api_error(mock_sock_cls, mock_stat_sp):
    """API error during attachment dispatch causes send() to return False."""
    # First socket (text) succeeds; second (attach) returns an API error
    mock_sock_cls.side_effect = [
        _socket_ok(),
        _socket_api_error("attachment failed"),
    ]

    path = os.path.join(TEST_VAR_DIR, "apprise-test.gif")
    attach = AppriseAttachment(path)

    obj = NotifyKeybase(targets=["@alice"])
    assert obj.notify(body="Hello", attach=attach) is False


@mock.patch.object(NotifyKeybase, "_stat_socket_path")
@mock.patch("apprise.plugins.keybase.base._socket.socket")
def test_plugin_keybase_send_attachment_connection_error(
    mock_sock_cls, mock_stat_sp
):
    """OSError during attachment socket connect is handled gracefully."""
    err_conn = mock.MagicMock()
    err_conn.connect.side_effect = OSError("connection refused")
    # First socket (text) succeeds; second (attach) raises on connect
    mock_sock_cls.side_effect = [_socket_ok(), err_conn]

    path = os.path.join(TEST_VAR_DIR, "apprise-test.gif")
    attach = AppriseAttachment(path)

    obj = NotifyKeybase(targets=["@alice"])
    assert obj.notify(body="Hello", attach=attach) is False
