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
import logging
import sys
from unittest import mock

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise
from apprise.plugins.sogs import (
    NotifySessionOGS,
    _build_session_message,
    _encode_varint,
    _ld_field,
)

logging.disable(logging.CRITICAL)

# A valid 64-hex-char Ed25519 seed used as the bot seed.
SEED = "a" * 64

# A valid 64-hex-char server Curve25519 public key (from Session join URL).
PUBLIC_KEY = "b" * 64

# An invalid key: 63 chars (too short).
BAD_KEY = "c" * 63

# A valid room token.
ROOM = "test-room"

# Second room token for multi-room tests.
ROOM2 = "another-room"

# Canonical base URL used throughout the tests.
BASE_URL = f"sessions://{PUBLIC_KEY}:{SEED}@open.getsession.org/{ROOM}"

# Apprise URL tester entries; requires cryptography to run functionally.
apprise_url_tests = (
    # Missing public_key and seed (only hostname + room, no credentials)
    (
        f"sessions://host/{ROOM}",
        {
            "instance": TypeError,
        },
    ),
    # Missing seed (user field present, no password)
    (
        f"sessions://{PUBLIC_KEY}@host/{ROOM}",
        {
            "instance": TypeError,
        },
    ),
    # Missing public_key (bad key in user field, too short)
    (
        f"sessions://{BAD_KEY}:{SEED}@host/{ROOM}",
        {
            "instance": TypeError,
        },
    ),
    # Missing room token (no path segments)
    (
        f"sessions://{PUBLIC_KEY}:{SEED}@host",
        {
            "instance": TypeError,
        },
    ),
    # Invalid seed (too short, in password field)
    (
        f"sessions://{PUBLIC_KEY}:{BAD_KEY}@host/{ROOM}",
        {
            "instance": TypeError,
        },
    ),
    # Valid HTTPS URL - single room
    (
        BASE_URL,
        {
            "instance": NotifySessionOGS,
            "privacy_url": (
                f"sessions://{PUBLIC_KEY}:a...a@open.getsession.org/{ROOM}"
            ),
            "requests_response_code": requests.codes.created,
        },
    ),
    # Valid HTTPS URL via ?to= alias (public_key:seed in authority field)
    (
        f"sessions://{PUBLIC_KEY}:{SEED}@open.getsession.org?to={ROOM}",
        {
            "instance": NotifySessionOGS,
            "requests_response_code": requests.codes.created,
        },
    ),
    # Valid HTTPS URL with custom port
    (
        f"sessions://{PUBLIC_KEY}:{SEED}@open.getsession.org:8443/{ROOM}",
        {
            "instance": NotifySessionOGS,
            "requests_response_code": requests.codes.created,
        },
    ),
    # Valid HTTP (insecure) URL
    (
        f"session://{PUBLIC_KEY}:{SEED}@open.getsession.org/{ROOM}",
        {
            "instance": NotifySessionOGS,
            "requests_response_code": requests.codes.created,
        },
    ),
    # sogs:// alias for sessions:// (HTTPS)
    (
        f"sogs://{PUBLIC_KEY}:{SEED}@open.getsession.org/{ROOM}",
        {
            "instance": NotifySessionOGS,
            "requests_response_code": requests.codes.created,
        },
    ),
    # Multiple rooms as path segments
    (
        f"sessions://{PUBLIC_KEY}:{SEED}@open.getsession.org/{ROOM}/{ROOM2}",
        {
            "instance": NotifySessionOGS,
            "requests_response_code": requests.codes.created,
        },
    ),
    # Query-string form: ?key= and ?seed= instead of authority field
    (
        f"sessions://open.getsession.org/{ROOM}?key={PUBLIC_KEY}&seed={SEED}",
        {
            "instance": NotifySessionOGS,
            "requests_response_code": requests.codes.created,
        },
    ),
    # Query-string form using Session-native ?public_key= alias
    (
        f"sessions://open.getsession.org/{ROOM}"
        f"?public_key={PUBLIC_KEY}&seed={SEED}",
        {
            "instance": NotifySessionOGS,
            "requests_response_code": requests.codes.created,
        },
    ),
    # HTTP 403 Forbidden
    (
        BASE_URL,
        {
            "instance": NotifySessionOGS,
            "response": False,
            "requests_response_code": requests.codes.forbidden,
        },
    ),
    # HTTP 500 Internal Server Error
    (
        BASE_URL,
        {
            "instance": NotifySessionOGS,
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    # Unknown HTTP status code
    (
        BASE_URL,
        {
            "instance": NotifySessionOGS,
            "response": False,
            "requests_response_code": 999,
        },
    ),
    # RequestException
    (
        BASE_URL,
        {
            "instance": NotifySessionOGS,
            "test_requests_exceptions": True,
        },
    ),
)


@pytest.mark.skipif(
    "cryptography" not in sys.modules,
    reason="Requires cryptography",
)
def test_plugin_sogs_urls():
    """Run the Apprise URL test suite against SOGS URLs."""
    helper = AppriseURLTester(tests=apprise_url_tests)
    helper.run_all()


@pytest.mark.skipif(
    "cryptography" in sys.modules,
    reason="Requires that cryptography NOT be installed",
)
def test_plugin_sogs_no_cryptography():
    """Plugin is disabled when cryptography is not installed."""
    # Apprise.instantiate() returns None for disabled plugins.
    obj = Apprise.instantiate(BASE_URL)
    assert obj is None

    # Direct instantiation must raise ImportError with a helpful message,
    # not the confusing AttributeError from None.from_private_bytes().
    with pytest.raises(ImportError, match="cryptography"):
        NotifySessionOGS(public_key=PUBLIC_KEY, seed=SEED, targets=[ROOM])


@pytest.mark.skipif(
    "cryptography" not in sys.modules,
    reason="Requires cryptography",
)
@mock.patch("requests.post")
def test_plugin_sogs_init(mock_post):
    """Test basic initialization and URL round-trip."""

    def _mk_resp(code=requests.codes.created):
        r = mock.Mock()
        r.status_code = code
        r.content = b'{"id": 1}'
        return r

    mock_post.return_value = _mk_resp()

    # Basic construction.
    obj = NotifySessionOGS(
        public_key=PUBLIC_KEY,
        seed=SEED,
        targets=[ROOM],
        host="open.getsession.org",
    )
    assert obj.rooms == [ROOM]
    assert obj.public_key == PUBLIC_KEY
    assert obj.seed == SEED

    # Round-trip invariant.
    url = obj.url()
    parsed = NotifySessionOGS.parse_url(url)
    obj2 = NotifySessionOGS(**parsed)
    assert obj.url_identifier == obj2.url_identifier
    assert len(obj.rooms) == len(obj2.rooms)


@pytest.mark.skipif(
    "cryptography" not in sys.modules,
    reason="Requires cryptography",
)
@mock.patch("requests.post")
def test_plugin_sogs_missing_public_key(mock_post):
    """TypeError is raised when public_key is absent or invalid."""
    with pytest.raises(TypeError):
        NotifySessionOGS(
            public_key=None,
            seed=SEED,
            targets=[ROOM],
            host="host",
        )
    with pytest.raises(TypeError):
        NotifySessionOGS(
            public_key=BAD_KEY,
            seed=SEED,
            targets=[ROOM],
            host="host",
        )


@pytest.mark.skipif(
    "cryptography" not in sys.modules,
    reason="Requires cryptography",
)
@mock.patch("requests.post")
def test_plugin_sogs_missing_seed(mock_post):
    """TypeError is raised when seed is absent or invalid."""
    with pytest.raises(TypeError):
        NotifySessionOGS(
            public_key=PUBLIC_KEY,
            seed=None,
            targets=[ROOM],
            host="host",
        )
    with pytest.raises(TypeError):
        NotifySessionOGS(
            public_key=PUBLIC_KEY,
            seed=BAD_KEY,
            targets=[ROOM],
            host="host",
        )


@pytest.mark.skipif(
    "cryptography" not in sys.modules,
    reason="Requires cryptography",
)
@mock.patch("requests.post")
def test_plugin_sogs_missing_rooms(mock_post):
    """TypeError is raised when no valid room token is provided."""
    with pytest.raises(TypeError):
        NotifySessionOGS(
            public_key=PUBLIC_KEY,
            seed=SEED,
            targets=None,
            host="host",
        )
    with pytest.raises(TypeError):
        NotifySessionOGS(
            public_key=PUBLIC_KEY,
            seed=SEED,
            targets=["!!invalid!!"],
            host="host",
        )


@pytest.mark.skipif(
    "cryptography" not in sys.modules,
    reason="Requires cryptography",
)
@mock.patch("requests.post")
def test_plugin_sogs_send_success(mock_post):
    """A 201 Created response is treated as success."""

    def _mk_resp(code=requests.codes.created):
        r = mock.Mock()
        r.status_code = code
        r.content = b'{"id": 1}'
        return r

    mock_post.return_value = _mk_resp()

    obj = NotifySessionOGS(
        public_key=PUBLIC_KEY,
        seed=SEED,
        targets=[ROOM],
        host="open.getsession.org",
    )
    assert bool(obj.notify(body="Hello SOGS")) is True
    assert mock_post.call_count == 1

    # HTTP 200 (OK) is also treated as success.
    mock_post.return_value = _mk_resp(requests.codes.ok)
    assert bool(obj.notify(body="Hello SOGS")) is True


@pytest.mark.skipif(
    "cryptography" not in sys.modules,
    reason="Requires cryptography",
)
@mock.patch("requests.post")
def test_plugin_sogs_send_multi_room(mock_post):
    """Sending to two rooms makes two POST requests."""

    def _mk_resp(code=requests.codes.created):
        r = mock.Mock()
        r.status_code = code
        r.content = b'{"id": 1}'
        return r

    mock_post.return_value = _mk_resp()

    obj = NotifySessionOGS(
        public_key=PUBLIC_KEY,
        seed=SEED,
        targets=[ROOM, ROOM2],
        host="open.getsession.org",
    )
    assert bool(obj.notify(body="Multi")) is True
    assert mock_post.call_count == 2


@pytest.mark.skipif(
    "cryptography" not in sys.modules,
    reason="Requires cryptography",
)
@mock.patch("requests.post")
def test_plugin_sogs_send_partial_failure(mock_post):
    """Failure on any room causes the overall notify() to return False."""

    def _mk_resp(code):
        r = mock.Mock()
        r.status_code = code
        r.content = b""
        return r

    mock_post.side_effect = [
        _mk_resp(requests.codes.created),
        _mk_resp(requests.codes.forbidden),
    ]

    obj = NotifySessionOGS(
        public_key=PUBLIC_KEY,
        seed=SEED,
        targets=[ROOM, ROOM2],
        host="open.getsession.org",
    )
    assert bool(obj.notify(body="Partial")) is False
    assert mock_post.call_count == 2


@pytest.mark.skipif(
    "cryptography" not in sys.modules,
    reason="Requires cryptography",
)
@mock.patch("requests.post")
def test_plugin_sogs_http_error(mock_post):
    """Non-2xx responses cause send() to return False."""

    def _mk_resp(code):
        r = mock.Mock()
        r.status_code = code
        r.content = b""
        return r

    obj = NotifySessionOGS(
        public_key=PUBLIC_KEY,
        seed=SEED,
        targets=[ROOM],
        host="open.getsession.org",
    )

    for code in (
        requests.codes.bad_request,
        requests.codes.unauthorized,
        requests.codes.forbidden,
        requests.codes.not_found,
        requests.codes.internal_server_error,
        999,
    ):
        mock_post.reset_mock()
        mock_post.return_value = _mk_resp(code)
        assert bool(obj.notify(body="Error")) is False


@pytest.mark.skipif(
    "cryptography" not in sys.modules,
    reason="Requires cryptography",
)
@mock.patch("requests.post")
def test_plugin_sogs_request_exception(mock_post):
    """requests.RequestException causes send() to return False."""
    mock_post.side_effect = requests.RequestException("network error")

    obj = NotifySessionOGS(
        public_key=PUBLIC_KEY,
        seed=SEED,
        targets=[ROOM],
        host="open.getsession.org",
    )
    assert bool(obj.notify(body="Error")) is False


@pytest.mark.skipif(
    "cryptography" not in sys.modules,
    reason="Requires cryptography",
)
@mock.patch("requests.post")
def test_plugin_sogs_http_insecure(mock_post):
    """session:// sends over plain HTTP."""

    def _mk_resp():
        r = mock.Mock()
        r.status_code = requests.codes.created
        r.content = b'{"id": 1}'
        return r

    mock_post.return_value = _mk_resp()

    obj = Apprise()
    assert obj.add(f"session://{PUBLIC_KEY}:{SEED}@open.getsession.org/{ROOM}")
    assert bool(obj.notify(body="Plain HTTP")) is True

    # Confirm the request was sent to http:// not https://.
    url_called = mock_post.call_args[0][0]
    assert url_called.startswith("http://")
    assert "https://" not in url_called


@pytest.mark.skipif(
    "cryptography" not in sys.modules,
    reason="Requires cryptography",
)
@mock.patch("requests.post")
def test_plugin_sogs_url_and_privacy(mock_post):
    """url() round-trips and masks seed in privacy mode."""

    def _mk_resp():
        r = mock.Mock()
        r.status_code = requests.codes.created
        r.content = b'{"id": 1}'
        return r

    mock_post.return_value = _mk_resp()

    obj = NotifySessionOGS(
        public_key=PUBLIC_KEY,
        seed=SEED,
        targets=[ROOM],
        host="open.getsession.org",
    )

    full_url = obj.url(privacy=False)
    assert SEED in full_url
    assert PUBLIC_KEY in full_url

    priv_url = obj.url(privacy=True)
    assert SEED not in priv_url
    assert PUBLIC_KEY in priv_url

    # Round-trip.
    parsed = NotifySessionOGS.parse_url(full_url)
    obj2 = NotifySessionOGS(**parsed)
    assert obj.url_identifier == obj2.url_identifier


@pytest.mark.skipif(
    "cryptography" not in sys.modules,
    reason="Requires cryptography",
)
@mock.patch("requests.post")
def test_plugin_sogs_custom_port(mock_post):
    """Custom port is encoded in the URL and used in requests."""

    def _mk_resp():
        r = mock.Mock()
        r.status_code = requests.codes.created
        r.content = b'{"id": 1}'
        return r

    mock_post.return_value = _mk_resp()

    obj = NotifySessionOGS(
        public_key=PUBLIC_KEY,
        seed=SEED,
        targets=[ROOM],
        host="open.getsession.org",
        port=8443,
    )
    assert ":8443" in obj.url()
    assert bool(obj.notify(body="custom port")) is True

    url_called = mock_post.call_args[0][0]
    assert ":8443" in url_called


def test_plugin_sogs_sogs_alias():
    """sogs:// is accepted as an alias for sessions:// (HTTPS)."""

    # parse_url must recognise the sogs:// schema.
    url = f"sogs://{PUBLIC_KEY}:{SEED}@open.getsession.org/{ROOM}"
    results = NotifySessionOGS.parse_url(url)
    assert results is not None
    assert results["public_key"] == PUBLIC_KEY
    assert results["seed"] == SEED
    assert ROOM in results["targets"]

    # The parsed schema must be "sogs" (the alias used in the input URL).
    assert results["schema"] == "sogs"


def test_plugin_sogs_parse_url():
    """parse_url extracts all expected fields."""

    # Canonical format: public_key:seed in authority, rooms in path.
    url = f"sessions://{PUBLIC_KEY}:{SEED}@open.getsession.org/{ROOM}/{ROOM2}"
    results = NotifySessionOGS.parse_url(url)
    assert results["public_key"] == PUBLIC_KEY
    assert results["seed"] == SEED
    assert ROOM in results["targets"]
    assert ROOM2 in results["targets"]

    # ?key= query param provides the public key (no user in URL).
    url2 = (
        f"sessions://open.getsession.org/{ROOM}?key={PUBLIC_KEY}&seed={SEED}"
    )
    results2 = NotifySessionOGS.parse_url(url2)
    assert results2["public_key"] == PUBLIC_KEY
    assert results2["seed"] == SEED

    # ?public_key= is the Session-native alias and overrides ?key= when both
    # are present.
    url2b = (
        f"sessions://open.getsession.org/{ROOM}"
        f"?public_key={PUBLIC_KEY}&seed={SEED}"
    )
    results2b = NotifySessionOGS.parse_url(url2b)
    assert results2b["public_key"] == PUBLIC_KEY
    assert results2b["seed"] == SEED

    # ?to= alias populates targets (no room in path).
    url3 = f"sessions://{PUBLIC_KEY}:{SEED}@open.getsession.org?to={ROOM}"
    results3 = NotifySessionOGS.parse_url(url3)
    assert ROOM in results3["targets"]

    # No password field -> seed is None.
    url4 = f"sessions://{PUBLIC_KEY}@open.getsession.org/{ROOM}"
    results4 = NotifySessionOGS.parse_url(url4)
    assert results4["seed"] is None

    # Empty URL -> None (host is required; verify_host=True is the default).
    assert NotifySessionOGS.parse_url("sessions://") is None


@pytest.mark.skipif(
    "cryptography" not in sys.modules,
    reason="Requires cryptography",
)
@mock.patch("requests.post")
def test_plugin_sogs_invalid_room_token(mock_post):
    """Invalid room tokens are stored in invalid_rooms and survive url()."""

    def _mk_resp():
        r = mock.Mock()
        r.status_code = requests.codes.created
        r.content = b'{"id": 1}'
        return r

    mock_post.return_value = _mk_resp()

    # One valid + one invalid: must succeed with at least one valid room.
    obj = NotifySessionOGS(
        public_key=PUBLIC_KEY,
        seed=SEED,
        targets=[ROOM, "!!!bad!!!"],
        host="open.getsession.org",
    )
    assert obj.rooms == [ROOM]
    assert len(obj.invalid_rooms) == 1

    # Invalid rooms survive url() round-trip (no silent data loss).
    full_url = obj.url()
    parsed = NotifySessionOGS.parse_url(full_url)
    obj2 = NotifySessionOGS(**parsed)
    assert obj.url_identifier == obj2.url_identifier


@pytest.mark.skipif(
    "cryptography" not in sys.modules,
    reason="Requires cryptography",
)
@mock.patch("requests.post")
def test_plugin_sogs_url_identifier(mock_post):
    """url_identifier distinguishes connections by public_key and host."""

    def _mk_obj(host, public_key=PUBLIC_KEY):
        return NotifySessionOGS(
            public_key=public_key,
            seed=SEED,
            targets=[ROOM],
            host=host,
        )

    obj_a = _mk_obj("server-a.example.com")
    obj_b = _mk_obj("server-b.example.com")
    obj_c = _mk_obj("server-a.example.com", public_key="d" * 64)

    # Same host + same public_key -> same identifier.
    obj_a2 = _mk_obj("server-a.example.com")
    assert obj_a.url_identifier == obj_a2.url_identifier

    # Different host -> different identifier.
    assert obj_a.url_identifier != obj_b.url_identifier

    # Same host, different public_key -> different identifier.
    assert obj_a.url_identifier != obj_c.url_identifier


@pytest.mark.skipif(
    "cryptography" not in sys.modules,
    reason="Requires cryptography",
)
@mock.patch("requests.post")
def test_plugin_sogs_auth_headers(mock_post):
    """X-SOGS-* headers are present and well-formed on every request."""

    def _mk_resp():
        r = mock.Mock()
        r.status_code = requests.codes.created
        r.content = b'{"id": 1}'
        return r

    mock_post.return_value = _mk_resp()

    obj = NotifySessionOGS(
        public_key=PUBLIC_KEY,
        seed=SEED,
        targets=[ROOM],
        host="open.getsession.org",
    )
    assert bool(obj.notify(body="Auth test")) is True

    call_kwargs = mock_post.call_args[1]
    headers = call_kwargs.get("headers", {})

    # All four X-SOGS-* headers must be present.
    assert "X-SOGS-Pubkey" in headers
    assert "X-SOGS-Nonce" in headers
    assert "X-SOGS-Timestamp" in headers
    assert "X-SOGS-Signature" in headers

    # Pubkey starts with "00" (unblinded) then 64 hex chars.
    pk = headers["X-SOGS-Pubkey"]
    assert pk.startswith("00")
    assert len(pk) == 66  # "00" + 32-byte pubkey hex = 2 + 64

    # Timestamp is a digit string.
    assert headers["X-SOGS-Timestamp"].isdigit()

    # Verify the no-body branch of _sogs_auth_headers (body_bytes=None
    # skips the blake2b step; the returned dict must still be well-formed).
    obj2 = NotifySessionOGS(
        public_key=PUBLIC_KEY,
        seed=SEED,
        targets=[ROOM],
        host="open.getsession.org",
    )
    no_body_headers = obj2._sogs_auth_headers("GET", "/room/test")
    assert "X-SOGS-Pubkey" in no_body_headers
    assert "X-SOGS-Nonce" in no_body_headers
    assert "X-SOGS-Timestamp" in no_body_headers
    assert "X-SOGS-Signature" in no_body_headers


@pytest.mark.skipif(
    "cryptography" not in sys.modules,
    reason="Requires cryptography",
)
@mock.patch("requests.post")
def test_plugin_sogs_response_unparseable_json(mock_post):
    """Unparseable response body is handled gracefully."""
    r = mock.Mock()
    r.status_code = requests.codes.created
    r.content = b"not-json"
    mock_post.return_value = r

    obj = NotifySessionOGS(
        public_key=PUBLIC_KEY,
        seed=SEED,
        targets=[ROOM],
        host="open.getsession.org",
    )
    assert bool(obj.notify(body="Hello")) is True


def test_plugin_sogs_build_session_message():
    """_build_session_message produces valid padded protobuf bytes."""
    msg = _build_session_message("hello")

    # Must be bytes and non-empty.
    assert isinstance(msg, bytes)
    assert len(msg) > 0

    # Ends with the Session padding marker 0x80.
    assert msg[-1] == 0x80

    # Starts with protobuf tag 0x0A (field 1, wire type 2).
    assert msg[0] == 0x0A


def test_plugin_sogs_encode_varint():
    """_encode_varint encodes small and multi-byte integers correctly."""
    assert _encode_varint(0) == b"\x00"
    assert _encode_varint(1) == b"\x01"
    assert _encode_varint(127) == b"\x7f"
    assert _encode_varint(128) == b"\x80\x01"
    assert _encode_varint(300) == b"\xac\x02"


def test_plugin_sogs_ld_field():
    """_ld_field encodes a length-delimited protobuf field."""
    encoded = _ld_field(1, b"hi")
    assert encoded == b"\x0a\x02hi"


def test_plugin_sogs_runtime_deps():
    """runtime_deps() returns the cryptography package name."""
    deps = NotifySessionOGS.runtime_deps()
    assert "cryptography" in deps


@pytest.mark.skipif(
    "cryptography" not in sys.modules,
    reason="Requires cryptography",
)
@mock.patch("requests.post")
def test_plugin_sogs_apprise_integration(mock_post):
    """Apprise.add() and Apprise.notify() work end-to-end."""

    def _mk_resp():
        r = mock.Mock()
        r.status_code = requests.codes.created
        r.content = b'{"id": 1}'
        return r

    mock_post.return_value = _mk_resp()

    app = Apprise()
    assert app.add(BASE_URL)
    assert bool(app.notify(title="Title", body="Body")) is True
    assert mock_post.call_count == 1
