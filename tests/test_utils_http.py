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

"""Tests for opt-in HTTP destination policy.

The socket option tests below describe each option shape by hand rather
than installing urllib3-future to produce one. That keeps the whole file
passing on RHEL and Rocky Linux, which ship the urllib3 1.26 series, and it
means the compatibility branch is covered everywhere instead of only where
an extra package happens to be present. Please do not swap them for a
skipif that needs urllib3-future installed.
"""

from concurrent.futures import TimeoutError as FutureTimeoutError
import contextlib
from http.client import HTTPResponse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import socket
import ssl
import threading
import time
from unittest import mock

import pytest
import requests
from urllib3.exceptions import ConnectTimeoutError, NewConnectionError

from apprise.utils import http
from apprise.utils.http import (
    ConnectionTracker,
    HTTPPolicy,
    HTTPPolicySession,
    _active_tracker,
    is_public_ip_address,
    is_secure_http_url,
    track_connections,
    tracked_session,
)


def test_public_ip_classification():
    """Only public unicast addresses pass the shared classifier."""
    assert is_public_ip_address("93.184.215.14")
    assert not is_public_ip_address("127.0.0.1")
    assert not is_public_ip_address("10.0.0.1")
    assert not is_public_ip_address("100.64.0.1")
    assert not is_public_ip_address("ff02::1")
    assert not is_public_ip_address("::ffff:127.0.0.1")
    assert not is_public_ip_address("64:ff9b::127.0.0.1")
    assert is_public_ip_address("64:ff9b::8.8.8.8")
    assert not is_public_ip_address("not-an-address")


@pytest.mark.parametrize(
    "address",
    (
        "169.254.1.1",
        "224.0.0.1",
        "240.0.0.1",
        "0.0.0.0",
        "fec0::1",
    ),
)
def test_non_public_address_categories(address):
    """Every special-use address category is rejected."""
    assert not is_public_ip_address(address)


def test_transition_address_categories():
    """IPv4 transition addresses inherit their embedded address safety."""
    assert is_public_ip_address("::ffff:8.8.8.8")

    # Simulate Python releases that mark the IPv6 wrapper as reserved. The
    # embedded IPv4 address must still decide whether the address is safe.
    with mock.patch.object(
        http.ipaddress.IPv6Address,
        "is_reserved",
        new_callable=mock.PropertyMock,
        return_value=True,
    ):
        assert is_public_ip_address("::ffff:8.8.8.8")
        assert not is_public_ip_address("::ffff:10.0.0.1")

    # Older Python releases do not classify these prefixes as private.
    with mock.patch.object(
        http.ipaddress.IPv6Address,
        "is_private",
        new_callable=mock.PropertyMock,
        return_value=False,
    ):
        assert not is_public_ip_address("2002:0a00:0001::1")
        assert not is_public_ip_address(
            "2001:0000:4136:e378:8000:63bf:f5ff:fffe"
        )

        # A Teredo address whose server and client are both public must
        # still be accepted once the embedded addresses are checked.
        assert is_public_ip_address("2001:0:4136:e378::f7f7:f7f7")


def test_secure_url_classification():
    """Secure URLs require HTTPS, a valid host, and no credentials."""
    # Well formed addresses we accept
    assert is_secure_http_url("https://example.com/key") is True
    assert is_secure_http_url("HTTPS://Example.com") is True
    assert is_secure_http_url("https://example.com:8443/path") is True
    assert is_secure_http_url("https://localhost") is True

    # Private and loopback addresses are fine for self hosted services
    assert is_secure_http_url("https://127.0.0.1:8080") is True
    assert is_secure_http_url("https://[2001:db8::1]:8443/p") is True

    # We must be given a string
    assert is_secure_http_url(None) is False
    assert is_secure_http_url(42) is False
    assert is_secure_http_url(b"https://example.com") is False

    # Only HTTPS gets through
    assert is_secure_http_url("http://example.com/key") is False
    assert is_secure_http_url("ftp://example.com") is False
    assert is_secure_http_url("example.com") is False

    # There has to be a host to talk to
    assert is_secure_http_url("https:///key") is False

    # Credentials are never accepted, not even empty ones
    assert is_secure_http_url("https://user:pass@example.com/key") is False
    assert is_secure_http_url("https://user@example.com") is False
    assert is_secure_http_url("https://@example.com") is False
    assert is_secure_http_url("https://:@example.com") is False

    # A port we cannot read, or cannot connect to, and an unterminated
    # IPv6 address
    assert is_secure_http_url("https://example.com:notaport") is False
    assert is_secure_http_url("https://example.com:65536") is False
    assert is_secure_http_url("https://example.com:0") is False
    assert is_secure_http_url("https://[broken/key") is False

    # The host itself still has to make sense
    assert is_secure_http_url("https://-bad-.example.com") is False
    assert is_secure_http_url("https://exa mple.com") is False

    # A fragment never reaches a server, so it is not a request target
    assert is_secure_http_url("https://example.com/base#frag") is False
    assert is_secure_http_url("https://example.com/#") is False


def test_policy_filters_and_preserves_dns_answers():
    """Approved resolver entries retain their original socket address."""
    answers = [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.5", 443)),
        (
            socket.AF_INET,
            socket.SOCK_STREAM,
            6,
            "",
            ("93.184.215.14", 443),
        ),
    ]
    policy = HTTPPolicy(address_filter=is_public_ip_address)

    with mock.patch("socket.getaddrinfo", return_value=answers) as resolver:
        assert policy.resolve("example.com", 443) == [answers[1]]

    resolver.assert_called_once()


def test_url_policy_callback_failure_is_closed():
    """An unexpected URL callback error becomes a normal request failure."""
    policy = HTTPPolicy(
        url_filter=mock.Mock(side_effect=RuntimeError("bad policy"))
    )

    with pytest.raises(requests.exceptions.InvalidURL) as error:
        policy.validate_url("https://example.com/")

    assert isinstance(error.value.__cause__, RuntimeError)


def test_empty_url_policy_allows_validation():
    """A policy without a URL callback leaves URL selection to its caller."""
    HTTPPolicy().validate_url("https://example.com/")


def test_policy_denies_unusable_dns_answers():
    """A lookup fails closed when no answer passes its policy."""
    answers = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.5", 443))]
    policy = HTTPPolicy(address_filter=is_public_ip_address)

    with (
        mock.patch("socket.getaddrinfo", return_value=answers),
        pytest.raises(socket.gaierror),
    ):
        policy.resolve("internal.example", 443)


def test_policy_rejects_work_when_resolver_is_full():
    """A saturated resolver rejects new work without queuing it."""
    slots = mock.Mock()
    slots.acquire.return_value = False
    with (
        mock.patch.object(http, "_DNS_SLOTS", slots),
        mock.patch.object(http, "_DNS_POOL") as pool,
        pytest.raises(socket.gaierror),
    ):
        HTTPPolicy().resolve("busy.example", 443)

    pool.submit.assert_not_called()


def test_policy_normalizes_executor_failure():
    """An unavailable executor becomes a normal DNS failure."""
    slots = mock.Mock()
    slots.acquire.return_value = True
    with (
        mock.patch.object(http, "_DNS_SLOTS", slots),
        mock.patch.object(http, "_DNS_POOL") as pool,
        pytest.raises(socket.gaierror),
    ):
        pool.submit.side_effect = RuntimeError("executor stopped")
        HTTPPolicy().resolve("example.com", 443)

    slots.release.assert_called_once_with()


def test_policy_normalizes_lookup_failure():
    """A resolver future exception becomes a normal DNS failure."""
    future = mock.Mock()
    future.result.side_effect = UnicodeError("bad hostname")
    with (
        mock.patch.object(http, "_DNS_POOL") as pool,
        pytest.raises(socket.gaierror),
    ):
        pool.submit.return_value = future
        HTTPPolicy().resolve("example.com", 443)


def test_socket_options_are_left_alone():
    """Nothing is configured when urllib3 asks for no options."""
    sock = mock.Mock()
    http._set_socket_options(sock, None)

    # An absent option list is not the same as an empty one.
    sock.setsockopt.assert_not_called()


def test_socket_options_urllib3_standard_form():
    """A standard urllib3 option reaches setsockopt untouched."""
    sock = mock.Mock()
    option = (socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    http._set_socket_options(sock, [option])

    sock.setsockopt.assert_called_once_with(*option)


def test_socket_options_urllib3_future_tcp_form():
    """An urllib3-future TCP option is applied to a stream socket.

    Apprise never requires urllib3-future, but a host can have it installed
    alongside Requests, and the option it hands us must still work.
    """
    sock = mock.Mock()
    sock.type = socket.SOCK_STREAM
    http._set_socket_options(
        sock, [(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1, "tcp")]
    )

    sock.setsockopt.assert_called_once_with(
        socket.IPPROTO_TCP, socket.TCP_NODELAY, 1
    )


def test_socket_options_skip_wrong_protocol():
    """An urllib3-future UDP option is skipped for a stream socket."""
    sock = mock.Mock()
    sock.type = socket.SOCK_STREAM
    http._set_socket_options(
        sock, [(socket.SOL_SOCKET, socket.SO_BROADCAST, 1, "udp")]
    )

    sock.setsockopt.assert_not_called()


def test_socket_options_native_length_form():
    """Python's native four-argument length form remains supported."""
    sock = mock.Mock()
    http._set_socket_options(
        sock, [(socket.SOL_SOCKET, socket.SO_RCVBUF, None, 8)]
    )

    sock.setsockopt.assert_called_once_with(
        socket.SOL_SOCKET, socket.SO_RCVBUF, None, 8
    )


def test_socket_options_applied_in_order():
    """Every option is configured, whatever mix of forms is supplied."""
    sock = mock.Mock()
    sock.type = socket.SOCK_STREAM
    http._set_socket_options(
        sock,
        [
            (socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1),
            (socket.IPPROTO_TCP, socket.TCP_NODELAY, 1, "tcp"),
            (socket.SOL_SOCKET, socket.SO_BROADCAST, 1, "udp"),
            (socket.SOL_SOCKET, socket.SO_RCVBUF, None, 8),
        ],
    )

    assert sock.setsockopt.call_args_list == [
        mock.call(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1),
        mock.call(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1),
        mock.call(socket.SOL_SOCKET, socket.SO_RCVBUF, None, 8),
    ]


def test_policy_skips_malformed_answer():
    """Malformed resolver entries do not hide a usable answer."""
    valid = (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))
    with mock.patch("socket.getaddrinfo", return_value=[None, valid]):
        assert HTTPPolicy().resolve("example.com", 443) == [valid]


def test_policy_callback_failure_is_closed():
    """An address callback exception cannot allow a destination."""
    answer = (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))
    policy = HTTPPolicy(address_filter=mock.Mock(side_effect=ValueError))
    with (
        mock.patch("socket.getaddrinfo", return_value=[answer]),
        pytest.raises(socket.gaierror),
    ):
        policy.resolve("example.com", 443)


def test_policy_timeout_retains_slot_until_lookup_stops():
    """Timed-out native DNS work keeps its slot until the worker exits."""
    future = mock.Mock()
    future.result.side_effect = FutureTimeoutError
    slots = mock.Mock()
    slots.acquire.return_value = True

    with (
        mock.patch.object(http, "_DNS_POOL") as pool,
        mock.patch.object(http, "_DNS_SLOTS", slots),
        pytest.raises(socket.gaierror),
    ):
        pool.submit.return_value = future
        HTTPPolicy(resolve_timeout=0.01).resolve("slow.example", 443)

    future.add_done_callback.assert_called_once_with(http._release_dns_slot)
    future.cancel.assert_called_once_with()
    slots.release.assert_not_called()


def test_connection_uses_pinned_sockaddr():
    """The socket connects to the approved answer without another lookup."""
    answer = (
        socket.AF_INET,
        socket.SOCK_STREAM,
        6,
        "",
        ("93.184.215.14", 443),
    )
    policy = HTTPPolicy()
    sock = mock.Mock()
    sock.getpeername.return_value = ("93.184.215.14", 443)

    with (
        mock.patch.object(
            policy,
            "resolve",
            return_value=[answer],
        ) as resolver,
        mock.patch("socket.socket", return_value=sock) as socket_factory,
    ):
        assert policy.create_connection("example.com", 443, timeout=4) is sock

    resolver.assert_called_once_with("example.com", 443)
    socket_factory.assert_called_once_with(
        socket.AF_INET,
        socket.SOCK_STREAM,
        6,
    )
    sock.connect.assert_called_once_with(("93.184.215.14", 443))


def test_connection_retries_approved_answers():
    """A failed approved address is closed before trying the next one."""
    answers = [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443)),
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.4.4", 443)),
    ]
    first = mock.Mock()
    first.connect.side_effect = OSError("unreachable")
    second = mock.Mock()
    second.getpeername.return_value = ("8.8.4.4", 443)
    policy = HTTPPolicy()

    with (
        mock.patch.object(policy, "resolve", return_value=answers),
        mock.patch("socket.socket", side_effect=(first, second)),
    ):
        result = policy.create_connection(
            "example.com",
            443,
            source_address=("0.0.0.0", 0),
        )

    assert result is second
    first.close.assert_called_once_with()
    second.bind.assert_called_once_with(("0.0.0.0", 0))
    second.settimeout.assert_not_called()


def test_connection_retries_peer_address_mismatch():
    """A socket reaching a different peer is closed and never returned."""
    answers = [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443)),
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.4.4", 443)),
    ]
    first = mock.Mock()
    first.getpeername.return_value = ("10.0.0.5", 443)
    second = mock.Mock()
    second.getpeername.return_value = ("8.8.4.4", 443)
    policy = HTTPPolicy()

    with (
        mock.patch.object(policy, "resolve", return_value=answers),
        mock.patch("socket.socket", side_effect=(first, second)),
    ):
        assert policy.create_connection("example.com", 443) is second

    first.close.assert_called_once_with()


def test_connection_normalizes_ipv6_peer_address():
    """Equivalent compressed and expanded IPv6 peers compare equally."""
    answer = (
        socket.AF_INET6,
        socket.SOCK_STREAM,
        6,
        "",
        ("2001:4860:4860::8888", 443, 0, 0),
    )
    sock = mock.Mock()
    sock.getpeername.return_value = (
        "2001:4860:4860:0:0:0:0:8888",
        443,
        0,
        0,
    )
    policy = HTTPPolicy()

    with (
        mock.patch.object(policy, "resolve", return_value=[answer]),
        mock.patch("socket.socket", return_value=sock),
    ):
        assert policy.create_connection("example.com", 443) is sock


def test_connection_rejects_invalid_peer_address():
    """An unusable peer address fails closed and releases its socket."""
    answer = (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))
    sock = mock.Mock()
    sock.getpeername.return_value = None
    policy = HTTPPolicy()

    with (
        mock.patch.object(policy, "resolve", return_value=[answer]),
        mock.patch("socket.socket", return_value=sock),
        pytest.raises(OSError, match="invalid peer address"),
    ):
        policy.create_connection("example.com", 443)

    sock.close.assert_called_once_with()


def test_connection_raises_last_socket_error():
    """The last connection error is returned after all answers fail."""
    answer = (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))
    policy = HTTPPolicy()
    with (
        mock.patch.object(policy, "resolve", return_value=[answer]),
        mock.patch("socket.socket", side_effect=OSError("socket failed")),
        pytest.raises(OSError, match="socket failed"),
    ):
        policy.create_connection("example.com", 443)


def test_connection_rejects_empty_resolver_result():
    """An unexpectedly empty resolver result fails closed."""
    policy = HTTPPolicy()
    with (
        mock.patch.object(policy, "resolve", return_value=[]),
        pytest.raises(OSError, match="no usable addresses"),
    ):
        policy.create_connection("example.com", 443)


@pytest.mark.parametrize(
    ("error", "expected"),
    (
        (socket.gaierror("denied"), NewConnectionError),
        (socket.timeout("timed out"), ConnectTimeoutError),
        (OSError("failed"), NewConnectionError),
    ),
)
def test_policy_connection_normalizes_socket_errors(error, expected):
    """urllib3 receives its normal connection exception categories."""
    policy = mock.Mock()
    policy.create_connection.side_effect = error
    connection_class = http._policy_pool_classes(policy)["http"].ConnectionCls
    connection = connection_class("example.com", 443)

    with pytest.raises(expected):
        connection._new_conn()


def test_policy_connection_returns_socket():
    """A successful policy connection is returned to urllib3."""
    policy = mock.Mock()
    sock = mock.Mock()
    policy.create_connection.return_value = sock
    connection_class = http._policy_pool_classes(policy)["http"].ConnectionCls
    connection = connection_class("example.com", 443)

    with mock.patch("sys.audit") as audit:
        assert connection._new_conn() is sock

    audit.assert_called_once_with(
        "http.client.connect",
        connection,
        "example.com",
        443,
    )


def test_failed_connection_closes_its_socket():
    """A connection that fails to open, such as a tunnel, closes its socket."""

    class Opening:
        def __init__(self, sock):
            self.raw = sock

        def _new_conn(self):
            return self.raw

        def connect(self):
            # The socket opens, then the tunnel through the proxy fails
            self._new_conn()
            raise OSError("tunnel failed")

    class Connection(http._TrackedConnectionMixin, Opening):
        pass

    left, right = socket.socketpair()
    try:
        connection = Connection(left)
        with pytest.raises(OSError, match="tunnel failed"):
            connection.connect()

        assert left.fileno() == -1
        assert connection.apprise_sock is None

        # Nothing opened is fine too
        connection.raw = None
        with pytest.raises(OSError, match="tunnel failed"):
            connection.connect()

    finally:
        left.close()
        right.close()


def test_connection_being_opened_can_be_cut_off():
    """A connection can be cut off while TLS takes its socket over.

    - Setting up TLS moves the socket into a new TLS socket, leaving the
      one opened empty until the handshake is done.
    - Once open, the copy used meanwhile is closed, whether it worked or not.
    """

    class Opening:
        def __init__(self, sock, fail):
            self.raw = sock
            self.fail = fail
            self.sock = None

        def _new_conn(self):
            return self.raw

        def connect(self):
            sock = self._new_conn()

            # As TLS does, the socket is taken over by a new one
            tls = socket.socket(fileno=sock.detach())

            # Time runs out part way through the handshake
            connection.copy = connection.apprise_sock
            http._shut_down(connection)
            if self.fail:
                tls.close()
                raise OSError("handshake failed")

            self.sock = tls

    class Connection(http._TrackedConnectionMixin, Opening):
        copy = None

    for fail in (False, True):
        left, right = socket.socketpair()
        try:
            connection = Connection(left, fail)
            if fail:
                with pytest.raises(OSError, match="handshake failed"):
                    connection.connect()

                assert connection.apprise_sock is None

            else:
                connection.connect()
                assert connection.apprise_sock is connection.sock

            # The cut off reached the connection, and the copy is gone
            assert _ended(right)
            assert connection.copy is not left
            assert connection.copy.fileno() == -1

        finally:
            left.close()
            right.close()
            if connection.sock is not None:
                connection.sock.close()


@pytest.mark.parametrize(
    "make_session, proxied",
    (
        (tracked_session, False),
        (tracked_session, True),
        # This test permits loopback only to exercise the transport locally.
        (
            lambda: HTTPPolicySession(
                HTTPPolicy(address_filter=lambda _address: True)
            ),
            False,
        ),
    ),
    ids=("requests", "proxy", "policy"),
)
def test_stalled_tls_handshake_is_cut_off(make_session, proxied):
    """A server that never answers the TLS handshake is cut off in time."""
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(4)
    port = server.getsockname()[1]
    accepted = []
    stopping = threading.Event()

    def serve():
        with contextlib.suppress(OSError):
            while True:
                conn, _ = server.accept()
                accepted.append(conn)
                if stopping.is_set():
                    return

                if proxied:
                    # The proxy opens the tunnel, then nothing answers
                    conn.recv(4096)
                    conn.sendall(
                        b"HTTP/1.1 200 Connection established\r\n\r\n"
                    )

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    proxies = {"https": f"http://127.0.0.1:{port}"} if proxied else None
    try:
        with make_session() as session:
            start = time.monotonic()
            with (
                pytest.raises(requests.RequestException),
                track_connections(ConnectionTracker(), time.monotonic() + 0.3),
            ):
                session.get(
                    f"https://127.0.0.1:{port}/", timeout=10, proxies=proxies
                )

            # Cut off by the time limit, well before the request's timeout
            assert time.monotonic() - start < 5

    finally:
        # One last connection wakes the server so it can stop
        stopping.set()
        with contextlib.suppress(OSError):
            socket.create_connection(("127.0.0.1", port), timeout=5).close()

        thread.join(5)
        server.close()
        for conn in accepted:
            conn.close()


def test_failed_tunnel_closes_the_proxy_reply():
    """A tunnel that fails part way closes the proxy's reply and its hold."""

    class Tunnel:
        response_class = HTTPResponse

        def __init__(self, sock, fail):
            self.sock = sock
            self.fail = fail

        def _tunnel(self):
            # As Python 3.11 and older do, the reply is left open on failure.
            # Kept here, the way the error's traceback keeps it in practice.
            response = self.reply = self.response_class(
                self.sock, method="CONNECT"
            )
            if self.fail:
                raise OSError("cut off")

            response.close()

    class Connection(http._TrackedConnectionMixin, Tunnel):
        pass

    for fail in (True, False):
        left, right = socket.socketpair()
        try:
            connection = Connection(left, fail)
            if fail:
                with pytest.raises(OSError, match="cut off"):
                    connection._tunnel()

            else:
                connection._tunnel()

            # Nothing else holds the socket, so closing it really closes it
            left.close()
            assert left.fileno() == -1
            assert connection.response_class is HTTPResponse

        finally:
            left.close()
            right.close()


def test_session_validates_every_prepared_request():
    """Each send, including redirect sends, receives a fresh URL check."""
    checked = []
    policy = HTTPPolicy(
        url_filter=lambda url: checked.append(url) or "safe" in url
    )
    session = HTTPPolicySession(policy)
    safe = requests.Request("GET", "https://safe.example/a").prepare()
    denied = requests.Request("GET", "https://blocked.example/b").prepare()

    with mock.patch.object(requests.Session, "send", return_value=mock.Mock()):
        session.send(safe)
        with pytest.raises(requests.exceptions.InvalidURL):
            session.send(denied)

    assert checked == [safe.url, denied.url]


def test_session_disables_proxies_by_default():
    """Checked requests cannot be silently rerouted through a proxy."""
    session = HTTPPolicySession(HTTPPolicy())
    assert session.trust_env is False

    adapter = session.get_adapter("https://example.com")
    with pytest.raises(requests.exceptions.ProxyError):
        adapter.proxy_manager_for("http://proxy.example")


def test_session_connects_through_policy_adapter():
    """The complete adapter can fetch through an approved pinned socket."""

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, _format, *args):
            # Keep the test server quiet.
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        # This test permits loopback only to exercise the transport locally.
        with HTTPPolicySession(
            HTTPPolicy(address_filter=lambda _address: True)
        ) as session:
            # Address the socket the server bound; "localhost" resolves to
            # ::1 first on a dual-stack host and has to fail over.
            response = session.get(
                f"http://127.0.0.1:{server.server_port}/",
                timeout=2,
            )
            assert response.status_code == requests.codes.ok
            assert response.content == b"ok"
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


@pytest.mark.parametrize(
    "make_session",
    (
        tracked_session,
        # This test permits loopback only to exercise the transport locally.
        lambda: HTTPPolicySession(
            HTTPPolicy(address_filter=lambda _address: True)
        ),
    ),
    ids=("requests", "policy"),
)
def test_track_connections(make_session):
    """A connection is tracked only while a tracked download uses it."""

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, _format, *args):
            # Keep the test server quiet.
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}/"
    try:
        tracker = ConnectionTracker()
        with make_session() as session:
            with track_connections(tracker):
                # Tracked while the reply is being read
                r = session.get(url, timeout=2, stream=True)
                assert len(tracker.connections) == 1
                conn = next(iter(tracker.connections))
                assert conn.apprise_tracker is tracker

                # Released once it goes back to the pool
                r.close()
                assert not tracker.connections
                assert conn.apprise_tracker is None

                # Tracked again when it is reused
                r = session.get(url, timeout=2, stream=True)
                assert tracker.connections == {conn}
                r.close()

            assert tracker.finished
            assert _active_tracker.get() is None

            # Nothing is tracked outside of track_connections()
            assert session.get(url, timeout=2).content == b"ok"
            assert conn.apprise_tracker is None

        # Tracking ends even after an error
        with pytest.raises(RuntimeError), track_connections(tracker):
            raise RuntimeError("boom")

        assert _active_tracker.get() is None

        # A tracked download inside another restores the outer one after
        outer, inner = ConnectionTracker(), ConnectionTracker()
        with track_connections(outer):
            with track_connections(inner):
                assert _active_tracker.get() is inner

            assert _active_tracker.get() is outer

    finally:
        server.shutdown()
        thread.join()
        server.server_close()


class _Connection:
    """A stand-in for a urllib3 connection."""

    def __init__(self, sock):
        self.apprise_sock = sock


def _ended(sock):
    """Return True once the other end of ``sock`` was shut down.

    The read has a time limit, so a connection that was never ended fails
    the test instead of hanging it.
    """
    sock.settimeout(5.0)
    return sock.recv(1) == b""


def test_connection_tracker_cut_off():
    """Cutting off ends every connection in use, and any used after."""
    pairs = [socket.socketpair() for _ in range(3)]
    try:
        tracker = ConnectionTracker()
        used = _Connection(pairs[0][0])
        released = _Connection(pairs[1][0])

        # One still being opened has no socket yet, and one already closed
        # is left alone
        opening = _Connection(None)
        closed = socket.socket()
        closed.close()
        for conn in (used, released, opening):
            tracker.add(conn)

        tracker.add(_Connection(closed))
        tracker.release(released)
        assert released.apprise_tracker is None

        tracker.cut_off()
        assert tracker.expired
        assert _ended(pairs[0][1])

        # A released connection belongs to someone else now
        pairs[1][1].setblocking(False)
        with pytest.raises(BlockingIOError):
            pairs[1][1].recv(1)

        # One used after time ran out is ended straight away, untracked
        late = _Connection(pairs[2][0])
        tracker.add(late)
        assert late not in tracker.connections
        assert _ended(pairs[2][1])

    finally:
        for pair in pairs:
            for sock in pair:
                sock.close()


def test_connection_tracker_finish():
    """A download that is over is never cut off afterwards."""
    left, right = socket.socketpair()
    try:
        tracker = ConnectionTracker()
        conn = _Connection(left)
        tracker.add(conn)
        tracker.finish()
        assert not tracker.connections
        assert conn.apprise_tracker is None

        tracker.cut_off()
        assert not tracker.expired
        right.setblocking(False)
        with pytest.raises(BlockingIOError):
            right.recv(1)

    finally:
        left.close()
        right.close()


def test_connection_tracker_tls():
    """A TLS connection is ended without touching its TLS state."""
    left, right = socket.socketpair()
    context = ssl.create_default_context()
    tls = context.wrap_socket(
        left, server_hostname="localhost", do_handshake_on_connect=False
    )
    try:
        tracker = ConnectionTracker()
        tracker.add(_Connection(tls))
        tracker.cut_off()
        assert _ended(right)

    finally:
        tls.close()
        right.close()


class _Wrapper:
    """A socket-like wrapper, such as PyOpenSSL's, around ``sock``."""

    def __init__(self, sock):
        self.socket = sock


def test_connection_tracker_wrapped_socket():
    """A socket inside a wrapper is ended, and anything unknown is skipped."""
    pairs = [socket.socketpair() for _ in range(2)]
    deep = socket.socket()
    try:
        tracker = ConnectionTracker()

        # One wrapper, and a wrapper around a wrapper
        tracker.add(_Connection(_Wrapper(pairs[0][0])))
        tracker.add(_Connection(_Wrapper(_Wrapper(pairs[1][0]))))

        # Nothing that can be ended, at the end of a wrapper or too deep
        tracker.add(_Connection(object()))
        tracker.add(_Connection(_Wrapper(_Wrapper(_Wrapper(deep)))))

        tracker.cut_off()
        assert tracker.expired
        assert _ended(pairs[0][1])
        assert _ended(pairs[1][1])

    finally:
        deep.close()
        for pair in pairs:
            for sock in pair:
                sock.close()


def test_watchdog_survives_errors():
    """One download failing to be cut off never stops the others."""

    class Broken(ConnectionTracker):
        def cut_off(self):
            raise TypeError()

    watchdog = http._Watchdog()
    tracker = ConnectionTracker()
    watchdog.watch(Broken(), time.monotonic())
    watchdog.watch(tracker, time.monotonic() + 0.1)

    until = time.monotonic() + 5.0
    while not tracker.expired:
        assert time.monotonic() < until
        time.sleep(0.01)

    assert watchdog._thread.is_alive()


def test_watchdog_order():
    """The soonest deadline is cut off first, whatever order it came in."""
    watchdog = http._Watchdog()
    later, sooner = ConnectionTracker(), ConnectionTracker()
    try:
        watchdog.watch(later, time.monotonic() + 60.0)
        watchdog.watch(sooner, time.monotonic() + 0.1)

        # Fifty times the deadline, so a slow machine still passes
        until = time.monotonic() + 5.0
        while not sooner.expired and time.monotonic() < until:
            time.sleep(0.01)

        assert sooner.expired
        assert not later.expired

    finally:
        # Let the thread go idle rather than cut off a tracker later
        later.finish()


def test_watchdog_without_thread():
    """A watchdog that cannot start a thread refuses the download."""
    watchdog = http._Watchdog()
    first, second = ConnectionTracker(), ConnectionTracker()
    with (
        mock.patch("threading.Thread.start", side_effect=RuntimeError),
        pytest.raises(http.WatchdogUnavailableError),
    ):
        watchdog.watch(first, time.monotonic())

    # Nothing was left behind
    assert watchdog._due == []

    # The next download starts it
    watchdog.watch(second, time.monotonic())
    until = time.monotonic() + 5.0
    while not second.expired:
        assert time.monotonic() < until
        time.sleep(0.01)

    assert not first.expired


def test_watchdog_forgets_finished_downloads():
    """Downloads that are over are not kept until their deadline."""
    watchdog = http._Watchdog()
    running = ConnectionTracker()
    with mock.patch.object(http, "_WATCHDOG", watchdog):
        watchdog.watch(running, time.monotonic() + 3600.0)

        # One over is left for now, since tidying up each time would be
        # slow with many downloads running
        with track_connections(ConnectionTracker(), time.monotonic() + 3600):
            pass

        assert len(watchdog._due) == 2

        # Once most of the schedule is over, only what still runs is kept
        with track_connections(ConnectionTracker(), time.monotonic() + 3600):
            pass

        assert [entry[2] for entry in watchdog._due] == [running]

        # Without a deadline it is never scheduled at all
        with track_connections(ConnectionTracker()):
            assert len(watchdog._due) == 1

    running.finish()


def test_tracked_pool():
    """Any kind of pool, such as a SOCKS proxy's, can be tracked."""

    class Connection(http.HTTPConnection):
        pass

    class Pool(http.HTTPConnectionPool):
        ConnectionCls = Connection

    tracked = http._tracked_pool(Pool)
    assert issubclass(tracked, Pool)
    assert issubclass(tracked.ConnectionCls, Connection)
    assert issubclass(tracked.ConnectionCls, http._TrackedConnectionMixin)

    # Made once, and a tracked pool is left as it is
    assert http._tracked_pool(Pool) is tracked
    assert http._tracked_pool(tracked) is tracked
    assert (
        http._tracked_pool(http.HTTPConnectionPool)
        is http._TrackedHTTPConnectionPool
    )


def test_tracked_session_proxy():
    """Connections through a proxy are tracked as well."""
    adapter = tracked_session().get_adapter("http://")
    manager = adapter.proxy_manager_for("http://127.0.0.1:3128")
    for pool_cls in manager.pool_classes_by_scheme.values():
        assert issubclass(pool_cls, http._TrackedPoolMixin)

    # The same manager is handed back next time, unchanged
    assert adapter.proxy_manager_for("http://127.0.0.1:3128") is manager


def test_policy_connects_with_urllib3_future_option():
    """A real socket accepts the protocol form urllib3-future supplies.

    The unit tests above use a mock, which tolerates any call signature.
    Only a real socket proves setsockopt itself is happy.
    """

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, _format, *args):
            # Keep the test server quiet.
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()

    # Describe the option the way urllib3-future does alongside Requests.
    options = [(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1, "tcp")]
    try:
        # This test permits loopback only to exercise the transport locally.
        policy = HTTPPolicy(address_filter=lambda _address: True)
        sock = policy.create_connection(
            "127.0.0.1",
            server.server_port,
            timeout=2,
            socket_options=options,
        )
        try:
            sock.sendall(b"GET / HTTP/1.0\r\nHost: 127.0.0.1\r\n\r\n")
            assert b"200 OK" in sock.recv(1024)

        finally:
            sock.close()

    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def test_session_validates_redirect_before_second_request():
    """A denied redirect target is rejected before it reaches the server."""

    class Handler(BaseHTTPRequestHandler):
        paths = []

        def do_GET(self):
            self.paths.append(self.path)
            if self.path == "/start":
                self.send_response(302)
                self.send_header(
                    "Location",
                    f"http://localhost:{self.server.server_port}/blocked",
                )
                self.end_headers()
                return

            self.send_response(200)
            self.end_headers()

        def log_message(self, _format, *args):
            # Keep the test server quiet.
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        policy = HTTPPolicy(
            url_filter=lambda url: not url.endswith("/blocked"),
            address_filter=lambda _address: True,
        )
        with (
            HTTPPolicySession(policy) as session,
            pytest.raises(requests.exceptions.InvalidURL),
        ):
            # Address the socket the server bound, as above
            session.get(
                f"http://127.0.0.1:{server.server_port}/start",
                timeout=2,
            )

        assert Handler.paths == ["/start"]
    finally:
        server.shutdown()
        thread.join()
        server.server_close()
