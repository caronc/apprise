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

import logging
import ssl
from unittest import mock

import pytest

from apprise.exception import AppriseException, AppriseInvalidData
from apprise.utils.socket import AppriseSocketError, SocketTransport

# Disable logging for a cleaner testing output
logging.disable(logging.CRITICAL)


class _DummyFile:
    def __init__(self) -> None:
        self.flushed = 0
        self.closed = 0

    def flush(self) -> None:
        self.flushed += 1

    def close(self) -> None:
        self.closed += 1


class _DummySocket:
    """
    Minimal fake socket object, supports the subset used by SocketTransport.
    """

    def __init__(self) -> None:
        self.blocking = True
        self.timeout = None
        self.closed = False
        self.shutdown_called = 0

        self._recv_side_effect = None
        self._send_side_effect = None

    def setsockopt(self, *_args, **_kwargs) -> None:
        return None

    def bind(self, *_args, **_kwargs) -> None:
        return None

    def fileno(self) -> int:
        return 1

    def settimeout(self, value):
        self.timeout = value

    def setblocking(self, value):
        self.blocking = bool(value)

    def connect(self, *_args, **_kwargs) -> None:
        return None

    def shutdown(self, *_args, **_kwargs) -> None:
        self.shutdown_called += 1

    def close(self) -> None:
        self.closed = True

    def getsockname(self):
        return ("127.0.0.1", 12345)

    def getpeername(self):
        return ("203.0.113.10", 6667)

    def makefile(self, *_args, **_kwargs):
        return _DummyFile()

    def recv(self, *_args, **_kwargs):
        if self._recv_side_effect is not None:
            raise self._recv_side_effect
        return b"data"

    def send(self, *_args, **_kwargs):
        if self._send_side_effect is not None:
            raise self._send_side_effect
        return 4


def test_utils_socket_timeout_coerce():
    """SocketTransport() Timeout Coercion."""
    # None => None, None
    s = SocketTransport("example.com", 1, timeout=None)
    assert s._connect_timeout is None
    assert s._read_timeout is None

    # float => both
    s = SocketTransport("example.com", 1, timeout=2.5)
    assert s._connect_timeout == 2.5
    assert s._read_timeout == 2.5

    # tuple => (connect, read)
    s = SocketTransport("example.com", 1, timeout=(1.0, 3.0))
    assert s._connect_timeout == 1.0
    assert s._read_timeout == 3.0

    # tuple with None is allowed
    s = SocketTransport("example.com", 1, timeout=(None, 3.0))
    assert s._connect_timeout is None
    assert s._read_timeout == 3.0

    # invalid types
    with pytest.raises(AppriseInvalidData):
        SocketTransport("example.com", 1, timeout="bad")

    with pytest.raises(AppriseInvalidData):
        SocketTransport("example.com", 1, timeout=(1.0, 2.0, 3.0))

    with pytest.raises(AppriseInvalidData):
        SocketTransport("example.com", 1, timeout=-1.0)


def test_utils_socket_properties_and_close_paths():
    """SocketTransport() Properties And Close Paths."""
    s = SocketTransport("example.com", 1)
    assert s.connected is False
    assert s.is_tls is False

    # Seed with dummy socket + wrappers
    s._sock = _DummySocket()
    s._rfile = _DummyFile()
    s._wfile = _DummyFile()
    s._is_tls = True
    s.local_addr = ("1.1.1.1", 1)
    s.remote_addr = ("2.2.2.2", 2)

    s.close()
    assert s._sock is None
    assert s._rfile is None
    assert s._wfile is None
    assert s._is_tls is False
    assert s.local_addr is None
    assert s.remote_addr is None


def test_utils_socket_read_write_no_socket():
    """SocketTransport() Can Read/Write - No Socket."""
    s = SocketTransport("example.com", 1)
    assert s.can_read() is None
    assert s.can_write() is None


def test_utils_socket_can_read_write_select_error():
    """SocketTransport() Can Read/Write - select() Error."""
    s = SocketTransport("example.com", 1)
    s._sock = _DummySocket()

    with mock.patch("select.select", side_effect=OSError()):
        assert s.can_read() is None
        assert s._sock is None

    s._sock = _DummySocket()
    with mock.patch("select.select", side_effect=OSError()):
        assert s.can_write() is None
        assert s._sock is None


def test_utils_socket_can_read_write_socket_close():
    """SocketTransport() Can Read/Write - Socket Close."""
    s = SocketTransport("example.com", 1)
    s._sock = _DummySocket()

    # Exceptional socket list returned triggers close()
    with mock.patch("select.select", return_value=([], [], [s._sock])):
        assert s.can_read() is None
        assert s._sock is None

    s._sock = _DummySocket()
    with mock.patch("select.select", return_value=([], [], [s._sock])):
        assert s.can_write() is None
        assert s._sock is None


def test_utils_socket_server_hostname_for_tls():
    """SocketTransport() Server Hostname For TLS."""
    s = SocketTransport("irc.example.com", 1, verify=True)
    assert s._server_hostname_for_tls() == "irc.example.com"

    s = SocketTransport("irc.example.com", 1, verify=False)
    assert s._server_hostname_for_tls() == "irc.example.com"


def test_utils_socket_server_hostname_for_tls_ip_reverse():
    """SocketTransport() Server Hostname For TLS IP Reverse DNS"""
    s = SocketTransport("203.0.113.10", 1, verify=True)

    with mock.patch(
            "socket.gethostbyaddr",
            return_value=("irc.example.com.", [], [])):
        assert s._server_hostname_for_tls() == "irc.example.com"

    with mock.patch("socket.gethostbyaddr", side_effect=OSError()):
        assert s._server_hostname_for_tls() == "203.0.113.10"

    # verify=False => no lookup
    s = SocketTransport("203.0.113.10", 1, verify=False)
    with mock.patch("socket.gethostbyaddr") as m:
        assert s._server_hostname_for_tls() == "203.0.113.10"
        m.assert_not_called()


def test_utils_socket_build_ssl_context():
    """SocketTransport() Build SSL Context."""
    s = SocketTransport("example.com", 1, verify=True)
    with mock.patch("certifi.where", return_value="/tmp/ca.pem"), mock.patch(
        "ssl.create_default_context"
    ) as m:
        ctx = mock.Mock()
        m.return_value = ctx
        result = s._build_ssl_context()
        assert result is ctx
        assert ctx.check_hostname is True
        assert ctx.verify_mode == ssl.CERT_REQUIRED

    s = SocketTransport("example.com", 1, verify=False)
    with mock.patch("ssl.create_default_context") as m:
        ctx = mock.Mock()
        m.return_value = ctx
        result = s._build_ssl_context()
        assert result is ctx
        assert ctx.check_hostname is False
        assert ctx.verify_mode == ssl.CERT_NONE


def test_utils_socket_start_tls_no_socket_raises():
    """SocketTransport() Start TLS No Socket Raises."""
    s = SocketTransport("example.com", 1, secure=True)
    with pytest.raises(AppriseSocketError):
        s.start_tls()


def test_utils_socket_start_tls_already_tls_noop():
    """SocketTransport() Start TLS Already TLS Noop."""
    s = SocketTransport("example.com", 1, secure=True)
    s._sock = _DummySocket()
    s._is_tls = True
    s.start_tls()
    assert s._sock is not None
    assert s._is_tls is True


def test_utils_socket_tls_ssl_init_errors():
    """SocketTransport() Start TLS/SSL Initialization Errors."""
    s = SocketTransport("example.com", 1, secure=True)
    s._sock = _DummySocket()

    with mock.patch.object(s, "_build_ssl_context") as mctx:
        ctx = mock.Mock()
        ctx.wrap_socket.side_effect = ssl.SSLError("boom")
        mctx.return_value = ctx

        with pytest.raises(AppriseSocketError):
            s.start_tls()
        assert s._sock is None

    s._sock = _DummySocket()
    with mock.patch.object(s, "_build_ssl_context") as mctx:
        ctx = mock.Mock()
        ctx.wrap_socket.side_effect = OSError("boom")
        mctx.return_value = ctx

        with pytest.raises(AppriseSocketError):
            s.start_tls()
        assert s._sock is None


def test_utils_socket_tls_tests():
    """SocketTransport() TLS Coverage"""
    s = SocketTransport("example.com", 1, secure=True)
    base_sock = _DummySocket()
    s._sock = base_sock

    tls_sock = _DummySocket()
    ctx = mock.Mock()
    ctx.wrap_socket.return_value = tls_sock

    with mock.patch.object(
            s, "_build_ssl_context",
            return_value=ctx), mock.patch.object(
        s, "_server_hostname_for_tls", return_value="example.com"
    ):
        s.start_tls()

    assert s._sock is tls_sock
    assert s.is_tls is True
    assert s.local_addr == ("127.0.0.1", 12345)
    assert s.remote_addr == ("203.0.113.10", 6667)
    assert s._rfile is not None
    assert s._wfile is not None


def test_utils_socket_connect():
    """SocketTransport() Connect() Coverage."""
    s = SocketTransport("example.com", 6667, secure=False, timeout=(1.0, 2.0))

    dummy = _DummySocket()

    with mock.patch("socket.socket", return_value=dummy):
        s.connect()
        assert s.connected is True
        assert s.is_tls is False
        assert s.local_addr == ("127.0.0.1", 12345)
        assert s.remote_addr == ("203.0.113.10", 6667)

    # Failure path: connect raises
    s = SocketTransport("example.com", 6667, secure=False, timeout=(1.0, 2.0))
    dummy = _DummySocket()
    dummy.connect = mock.Mock(side_effect=OSError("fail"))

    with mock.patch("socket.socket", return_value=dummy):
        with pytest.raises(AppriseSocketError):
            s.connect()
        assert s.connected is False


def test_utils_socket_read_nonblocking():
    """SocketTransport() Read Nonblocking."""
    s = SocketTransport("example.com", 1)
    sock = _DummySocket()
    s._sock = sock

    # Non-blocking success
    assert s.read(blocking=False) == b"data"

    # Non-blocking no data
    sock._recv_side_effect = BlockingIOError()
    assert s.read(blocking=False) == b""

    # Non-blocking OSError -> close + raise
    sock._recv_side_effect = OSError("boom")
    with pytest.raises(AppriseSocketError):
        s.read(blocking=False)
    assert s._sock is None


def test_utils_socket_read_blocking_timeout():
    """SocketTransport() Read Blocking Timeout."""
    s = SocketTransport("example.com", 1, timeout=(1.0, 0.1))
    sock = _DummySocket()
    s._sock = sock

    # Timeout path: can_read returns False => b""
    with mock.patch.object(s, "can_read", return_value=False):
        assert s.read(blocking=True) == b""

    # Indefinite path: wait_timeout=None, loop until can_read True
    s = SocketTransport("example.com", 1, timeout=None)
    sock = _DummySocket()
    s._sock = sock

    side_effect = [False, False, True]
    with mock.patch.object(s, "can_read", side_effect=side_effect):
        assert s.read(blocking=True) == b"data"


def test_utils_socket_read_blocking_edge_cases() -> None:
    """SocketTransport() Read Blocking Edge Cases
    """
    s = SocketTransport("example.com", 1, timeout=None)

    bad_sock = _DummySocket()
    good_sock = _DummySocket()
    good_sock.recv = mock.Mock(return_value=b"data")

    s._sock = bad_sock
    s._had_io = True

    def _close_side_effect() -> None:
        # emulate closing the socket
        if s._sock is not None:
            s._sock = None
        s._rfile = None
        s._wfile = None
        s._is_tls = False
        s.local_addr = None
        s.remote_addr = None

    def _connect_side_effect() -> None:
        s._sock = good_sock
        s._refresh_wrappers()

    with (
        mock.patch.object(s, "close", side_effect=_close_side_effect),
        mock.patch.object(s, "connect", side_effect=_connect_side_effect),
        mock.patch.object(s, "can_read", return_value=None),
    ):
        # can_read(None) triggers reconnect branch, then recv() on new socket
        assert s.read(blocking=True, retries=1) == b"data"


def test_utils_socket_write_with_no_socket():
    """SocketTransport() write() - No Socket."""
    s = SocketTransport("example.com", 1)
    with pytest.raises(AppriseSocketError):
        s.write(b"hi")

    s._sock = _DummySocket()
    with pytest.raises(AppriseInvalidData):
        s.write("hi")  # type: ignore[arg-type]


def test_utils_socket_write_flush():
    """SocketTransport() write() - Flush."""
    s = SocketTransport("example.com", 1, timeout=(1.0, 0.2))
    sock = _DummySocket()
    s._sock = sock
    s._wfile = _DummyFile()

    # Normal send, flush=True
    assert s.write(b"test", flush=True) == 4
    assert s._wfile.flushed >= 1

    # send returning 0 triggers connection lost
    sock = _DummySocket()
    sock.send = mock.Mock(return_value=0)
    s._sock = sock
    with pytest.raises(AppriseSocketError):
        s.write(b"test", timeout=0.1)

    # Timeout path: can_write returns False
    sock = _DummySocket()
    s._sock = sock
    with (mock.patch.object(s, "can_write",
                            return_value=False),
            pytest.raises(AppriseSocketError)):
        s.write(b"test", timeout=0.1)

    # OSError triggers close
    sock = _DummySocket()
    sock._send_side_effect = OSError("boom")
    s._sock = sock
    with pytest.raises(AppriseSocketError):
        s.write(b"test", timeout=0.1)
    assert s._sock is None


def test_utils_socket_read_timeouts():
    """SocketTransport() Read Timeouts"""
    # Negative connect timeout
    with pytest.raises(AppriseInvalidData):
        SocketTransport("example.com", 1, timeout=(-0.1, 1.0))

    # Negative read timeout
    with pytest.raises(AppriseInvalidData):
        SocketTransport("example.com", 1, timeout=(1.0, -0.1))

    # Force the read_t is None branch
    s = SocketTransport("example.com", 1, timeout=(1.0, None))
    assert s._connect_timeout == 1.0
    assert s._read_timeout is None


def test_utils_socket_exceptions():
    """SocketTransport() Exception Testing."""
    assert issubclass(AppriseSocketError, AppriseException)


def test_utils_socket_close_exceptions():

    """SocketTransport() Close Exceptions."""
    class _BadShutdownSocket(_DummySocket):
        def shutdown(self, *_args, **_kwargs) -> None:
            raise Exception("shutdown fail")

    class _BadFile(_DummyFile):
        def flush(self) -> None:
            raise Exception("flush fail")

        def close(self) -> None:
            raise Exception("close fail")

    s = SocketTransport("example.com", 1)
    s._sock = _BadShutdownSocket()
    s._wfile = _BadFile()
    s._rfile = _BadFile()

    # Should not raise, despite flush/close/shutdown throwing
    s.close()

    assert s._sock is None
    assert s._wfile is None
    assert s._rfile is None


def test_utils_socket_refresh():
    """SocketTransport() Refresh."""
    s = SocketTransport("example.com", 1)
    s._sock = None
    s._rfile = _DummyFile()
    s._wfile = _DummyFile()

    s._refresh_wrappers()

    assert s._rfile is None
    assert s._wfile is None


def test_utils_socket_can_read_returns_bool():
    """SocketTransport() Can Read Returns Bool."""
    s = SocketTransport("example.com", 1)
    s._sock = _DummySocket()

    with mock.patch("select.select", return_value=([s._sock], [], [])):
        assert s.can_read(0.01) is True

    with mock.patch("select.select", return_value=([], [], [])):
        assert s.can_read(0.01) is False


def test_utils_socket_connect_bind():
    """SocketTransport() bind() tests"""
    s = SocketTransport(
        "example.com", 6667, bind_addr="127.0.0.1", bind_port=0)
    dummy = _DummySocket()
    dummy.bind = mock.Mock()

    with mock.patch("socket.socket", return_value=dummy):
        s.connect()

    dummy.bind.assert_called_once()


def test_utils_socket_connect_settimeout_handling():
    """SocketTransport() Connect settimeout() handling."""
    s = SocketTransport("example.com", 6667, timeout=None)
    dummy = _DummySocket()
    dummy.settimeout = mock.Mock()

    with mock.patch("socket.socket", return_value=dummy):
        s.connect()

    # called once with None after connect() (sock.settimeout(None))
    # but NOT called with a float connect timeout prior to connect.
    assert dummy.settimeout.call_args_list == [mock.call(None)]


def test_utils_socket_secure_connect():
    """SocketTransport() Secure connect()."""
    s = SocketTransport("example.com", 6667, secure=True)
    dummy = _DummySocket()

    with mock.patch("socket.socket", return_value=dummy), mock.patch.object(
        s, "start_tls", autospec=True
    ) as m:
        s.connect()
        m.assert_called_once()


def test_utils_socket_connect_exceptions():
    """SocketTransport() Connect Exceptions."""
    class _BadCloseSocket(_DummySocket):
        def connect(self, *_args, **_kwargs) -> None:
            raise OSError("connect fail")

        def close(self) -> None:
            raise Exception("close fail")

    s = SocketTransport("example.com", 6667, secure=False)
    dummy = _BadCloseSocket()

    with (mock.patch("socket.socket", return_value=dummy),
          pytest.raises(AppriseSocketError)):
        s.connect()

    # transport should not keep the socket
    assert s.connected is False


def test_utils_socket_write_deadline():
    """SocketTransport() Write Deadline."""
    s = SocketTransport("example.com", 1, timeout=(1.0, 0.2))
    sock = _DummySocket()
    s._sock = sock

    with mock.patch.object(s, "can_write", return_value=True) as m_can_write:
        assert s.write(b"test", timeout=0.1, flush=False) == 4
        assert m_can_write.called


def test_utils_socket_write_timeout():
    """SocketTransport() write() timeout."""
    s = SocketTransport("example.com", 1, timeout=(1.0, 0.2))
    s._sock = _DummySocket()

    # First monotonic call sets deadline, second call makes remaining <= 0
    with mock.patch("time.monotonic", side_effect=[1000.0, 1000.5]):
        with pytest.raises(AppriseSocketError) as e:
            s.write(b"test", timeout=0.1, flush=False)
        assert "Timed out during write" in str(e.value)

    s = SocketTransport("example.com", 1, timeout=None)
    sock = _DummySocket()
    s._sock = sock
    s._wfile = _DummyFile()

    # If deadline is None, can_write should never be called
    with mock.patch.object(s, "can_write") as m_can_write:
        assert s.write(b"test", flush=True, timeout=None) == 4
        m_can_write.assert_not_called()


def test_utils_socket_write_flush_edge_cases():
    """SocketTransport() write() flush() edge cases."""
    s = SocketTransport("example.com", 1, timeout=(1.0, 0.2))
    s._sock = _DummySocket()
    s._wfile = _DummyFile()

    with mock.patch.object(s._wfile, "flush") as m:
        assert s.write(b"test", flush=False, timeout=0.1) == 4
        m.assert_not_called()

    s = SocketTransport("example.com", 1, timeout=(1.0, 0.2))
    s._sock = _DummySocket()
    s._wfile = None

    # Should succeed and simply skip flush
    assert s.write(b"test", flush=True, timeout=0.1) == 4


def test_utils_socket_recv_error():
    """SocketTransport() recv() errors

    Covers blocking read() OSError handling after readiness check.
    """
    s = SocketTransport("example.com", 1, timeout=(1.0, 0.5))
    sock = _DummySocket()
    sock._recv_side_effect = OSError("recv failed")
    s._sock = sock

    with (mock.patch.object(s, "can_read", return_value=True),
          pytest.raises(AppriseSocketError) as e):
        s.read(blocking=True)

    assert "recv failed" in str(e.value)
    assert s._sock is None


def test_utils_socket_write_empty_payload_does_not_set_had_io() -> None:
    """SocketTransport() Write Empty Payload Does Not Set Had Io.

    Covers the branch where total_sent == 0, so _had_io is not updated.
    """
    s = SocketTransport("example.com", 1, timeout=None)
    s._sock = _DummySocket()
    s._wfile = _DummyFile()

    # Empty payload performs no send() calls
    sent = s.write(b"", flush=False, timeout=None)
    assert sent == 0
    assert s._had_io is False


def test_utils_socket_write_handling() -> None:
    """SocketTransport() Write handling

    """
    s = SocketTransport("example.com", 1, timeout=None)
    s._sock = _DummySocket()

    # Mark prior I/O so reconnect is considered eligible in real logic, but we
    # patch _attempt_reconnect to force the continue path deterministically.
    s._had_io = True

    # Force the send to fail with an AppriseSocketError
    s._sock.send = mock.Mock(side_effect=AppriseSocketError("boom"))

    # retries=0 => attempts == 1; we force _attempt_reconnect to return True,
    # which triggers `continue` and immediately exhausts the loop.
    with (
        mock.patch.object(s, "_attempt_reconnect", return_value=True),
        pytest.raises(AppriseSocketError) as e,
    ):
        s.write(b"test", timeout=None, retries=0)

    assert "Socket write failed" in str(e.value)


def test_utils_socket_write_reconnect_continue_path_is_reached() -> None:
    """SocketTransport() Write Reconnect Continue Path Is Reached.

    Covers the `continue` path in write() when _attempt_reconnect returns True.
    Trigger AppriseSocketError (not OSError) so we do not reset _had_io via.
    close() before reconnect eligibility is checked.
    """
    s = SocketTransport("example.com", 1, timeout=None)

    bad_sock = _DummySocket()
    # send returning 0 triggers "Connection lost during write"
    bad_sock.send = mock.Mock(return_value=0)

    good_sock = _DummySocket()
    good_sock.send = mock.Mock(return_value=4)

    s._sock = bad_sock
    s._had_io = True

    def _connect_side_effect() -> None:
        s._sock = good_sock
        s._refresh_wrappers()

    with mock.patch.object(s, "connect", side_effect=_connect_side_effect):
        assert s.write(b"test", timeout=None, retries=1, flush=False) == 4


def test_utils_socket_read_reconnect_continue_path_is_reached() -> None:
    """SocketTransport() Read Reconnect Continue Path Is Reached.

    Covers the `continue` path in read() when _attempt_reconnect returns True.
    Trigger AppriseSocketError (not OSError) so we do not reset _had_io via.
    close() before reconnect eligibility is checked.
    """
    s = SocketTransport("example.com", 1, timeout=None)

    bad_sock = _DummySocket()
    # recv returning b"" triggers "Connection lost during read"
    bad_sock.recv = mock.Mock(return_value=b"")

    good_sock = _DummySocket()
    good_sock.recv = mock.Mock(return_value=b"data")

    s._sock = bad_sock
    s._had_io = True

    def _connect_side_effect() -> None:
        s._sock = good_sock
        s._refresh_wrappers()

    with mock.patch.object(s, "connect", side_effect=_connect_side_effect):
        assert s.read(blocking=False, retries=1) == b"data"


def test_utils_socket_attempt_reconnect_retries_zero_returns_false() -> None:
    """SocketTransport() Attempt Reconnect Retries Zero Returns False.

    Covers _attempt_reconnect() early return when retries <= 0.
    """
    s = SocketTransport("example.com", 1, timeout=None)
    s._had_io = True
    assert (
        s._attempt_reconnect(
            retries=0,
            action="read",
            exc=Exception("boom"),
        )
        is False
    )


def test_utils_socket_read_blocking_connection() -> None:
    """SocketTransport() Read Blocking Connection."""
    s = SocketTransport("example.com", 1, timeout=(1.0, 0.5))
    sock = _DummySocket()
    sock.recv = mock.Mock(return_value=b"")
    s._sock = sock

    # Mark prior I/O, but retries=0 means reconnect is not allowed anyway
    s._had_io = True

    with (
        mock.patch.object(s, "can_read", return_value=True),
        pytest.raises(AppriseSocketError) as e,
    ):
        s.read(blocking=True, retries=0)

    assert "Connection lost during read" in str(e.value)


def test_utils_socket_read_blocking() -> None:
    """SocketTransport() Read Blocking
    """
    s = SocketTransport("example.com", 1, timeout=(1.0, 0.5))

    bad_sock = _DummySocket()
    bad_sock.recv = mock.Mock(return_value=b"")
    good_sock = _DummySocket()
    good_sock.recv = mock.Mock(return_value=b"data")

    s._sock = bad_sock
    s._had_io = True

    def _connect_side_effect() -> None:
        s._sock = good_sock
        s._refresh_wrappers()

    with (
        mock.patch.object(s, "can_read", return_value=True),
        mock.patch.object(s, "connect", side_effect=_connect_side_effect),
    ):
        assert s.read(blocking=True, retries=1) == b"data"

    s = SocketTransport("example.com", 1, timeout=(1.0, 0.5))
    sock = _DummySocket()
    s._sock = sock

    with mock.patch.object(s, "can_read", return_value=True):
        assert s.read(blocking=True) == b"data"

    s = SocketTransport("example.com", 1, timeout=None)
    s._sock = _DummySocket()

    with mock.patch.object(s, "can_read", return_value=None):
        with pytest.raises(AppriseSocketError) as e:
            s.read(blocking=True)
        assert "Socket closed" in str(e.value)

    s = SocketTransport("example.com", 1, timeout=(1.0, 0.5))
    s._sock = _DummySocket()

    with mock.patch.object(s, "can_read", return_value=False):
        assert s.read(blocking=True) == b""


def test_utils_socket_read_edge_cases():
    """SocketTransport() read() edge case tests."""
    s = SocketTransport("example.com", 1)
    s._sock = None
    assert s.read() == b""

    s = SocketTransport("example.com", 1, timeout=None)

    sock = _DummySocket()
    sock.recv = mock.Mock(return_value=b"")  # triggers AppriseSocketError path
    s._sock = sock
    s._had_io = True

    with (
        mock.patch.object(s, "_attempt_reconnect", return_value=True),
        pytest.raises(AppriseSocketError) as e,
    ):
        # retries=0 => attempts starts at 1, decremented to 0 in-loop
        s.read(blocking=False, retries=0)

    assert "Socket read failed" in str(e.value)
