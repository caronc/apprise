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

"""Tests for opt-in HTTP destination policy."""

from concurrent.futures import TimeoutError as FutureTimeoutError
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import socket
import threading
from unittest import mock

import pytest
import requests
from urllib3.exceptions import ConnectTimeoutError, NewConnectionError

from apprise.utils import http
from apprise.utils.http import (
    HTTPPolicy,
    HTTPPolicySession,
    is_public_ip_address,
    is_secure_http_url,
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
    """Secure URLs require HTTPS, a host, and no credentials."""
    assert is_secure_http_url("https://example.com/key")
    assert not is_secure_http_url("http://example.com/key")
    assert not is_secure_http_url("https:///key")
    assert not is_secure_http_url("https://user:pass@example.com/key")
    assert not is_secure_http_url("https://[broken/key")


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
            response = session.get(
                f"http://localhost:{server.server_port}/",
                timeout=2,
            )
            assert response.status_code == requests.codes.ok
            assert response.content == b"ok"
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
            session.get(
                f"http://localhost:{server.server_port}/start",
                timeout=2,
            )

        assert Handler.paths == ["/start"]
    finally:
        server.shutdown()
        thread.join()
        server.server_close()
