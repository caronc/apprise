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

from __future__ import annotations

import contextlib
import ipaddress
import select
import socket
import ssl
import time
from typing import Optional, Union

from ..exception import AppriseException, AppriseInvalidData
from ..logger import logger

TimeoutType = Optional[
    Union[float, tuple[Optional[float], Optional[float]]]
]


class AppriseSocketError(AppriseException):
    """Raised for socket or TLS related failures."""


class SocketTransport:
    """
    TCP client transport with optional TLS upgrade.

    Behaviour:
      - secure=False (default): plain TCP
      - secure=True: upgrade to TLS (immediately in connect(), or manually via
        start_tls())
      - verify=True (default): validate certificate chain and hostname using a
        certifi CA bundle
      - verify=False: accept invalid or self-signed certs

    Timeout behaviour (requests-compatible):
      - timeout=float => (connect, read) both set to float
      - timeout=(connect, read) => tuple form
      - None => no defaults (connect/read can block indefinitely)
    """

    def __init__(
        self,
        host: str,
        port: int,
        bind_addr: Optional[str] = None,
        bind_port: Optional[int] = None,
        secure: bool = False,
        verify: bool = True,
        timeout: TimeoutType = 10.0,
        retries: int = 0,
    ) -> None:
        self.host = host
        self.port = int(port)
        self.bind_addr = bind_addr
        self.bind_port = bind_port

        self.secure = bool(secure)
        self.verify = bool(verify)
        self.retries = retries

        self._connect_timeout, self._read_timeout = \
            self._coerce_timeout(timeout)

        self._sock: Optional[socket.socket] = None
        self._rfile = None
        self._wfile = None
        self._is_tls: bool = False

        # True once we have successfully read or written data since the last
        # connect(). Used to decide whether reconnect attempts are allowed.
        self._had_io: bool = False

        self.local_addr: Optional[tuple[str, int]] = None
        self.remote_addr: Optional[tuple[str, int]] = None

    @staticmethod
    def _coerce_timeout(
            timeout: TimeoutType) -> tuple[Optional[float], Optional[float]]:
        """
        Coerce requests-style timeout into (connect_timeout, read_timeout).
        """
        if timeout is None:
            return None, None

        if isinstance(timeout, (int, float)):
            t = float(timeout)
            if t < 0:
                raise AppriseInvalidData("timeout must be >= 0")
            return t, t

        if isinstance(timeout, tuple) and len(timeout) == 2:
            connect_t, read_t = timeout
            if connect_t is not None:
                connect_t = float(connect_t)
                if connect_t < 0:
                    raise AppriseInvalidData("connect timeout must be >= 0")
            if read_t is not None:
                read_t = float(read_t)
                if read_t < 0:
                    raise AppriseInvalidData("read timeout must be >= 0")
            return connect_t, read_t

        raise AppriseInvalidData(
            "timeout must be None, a float, or a (connect, read) tuple"
        )

    @property
    def connected(self) -> bool:
        return self._sock is not None

    @property
    def is_tls(self) -> bool:
        return self._is_tls

    def close(self) -> None:
        """Close the socket and associated file wrappers."""
        try:
            if self._wfile is not None:
                with contextlib.suppress(Exception):
                    self._wfile.flush()
                with contextlib.suppress(Exception):
                    self._wfile.close()
        finally:
            self._wfile = None

        try:
            if self._rfile is not None:
                with contextlib.suppress(Exception):
                    self._rfile.close()
        finally:
            self._rfile = None

        if self._sock is not None:
            try:
                with contextlib.suppress(Exception):
                    self._sock.shutdown(socket.SHUT_RDWR)

                self._sock.close()
            finally:
                self._sock = None

        self._is_tls = False
        self._had_io = False
        self.local_addr = None
        self.remote_addr = None

    def _refresh_wrappers(self) -> None:
        """Rebuild file wrappers, required after TLS upgrade."""

        if self._sock is None:
            self._rfile = None
            self._wfile = None
            return

        self._rfile = self._sock.makefile("rb", buffering=0)
        self._wfile = self._sock.makefile("wb", buffering=0)

    def can_read(self, timeout: float = 0.0) -> Optional[bool]:
        """Return True if readable, False if not, None if closed or error."""
        if self._sock is None:
            return None
        try:
            r, _, x = select.select(
                [self._sock], [], [self._sock], float(timeout))

        except OSError:
            self.close()
            return None

        if x:
            self.close()
            return None

        return bool(r)

    def can_write(self, timeout: float = 0.0) -> Optional[bool]:
        """Return True if writable, False if not, None if closed or error."""
        if self._sock is None:
            return None
        try:
            _, w, x = \
                select.select([], [self._sock], [self._sock], float(timeout))
        except OSError:
            self.close()
            return None
        if x:
            self.close()
            return None
        return bool(w)

    def connect(self) -> None:
        """
        Establish TCP connection, optionally upgrade to TLS immediately if
        secure=True.
        """
        logger.trace(
            "Socket connect IN: host=%s port=%d secure=%s verify=%s",
            self.host,
            self.port,
            self.secure,
            self.verify,
        )
        self.close()

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)

            if self.bind_addr is not None or self.bind_port is not None:
                sock.bind(
                    (self.bind_addr or "0.0.0.0", int(self.bind_port or 0)))

            if self._connect_timeout is not None:
                sock.settimeout(self._connect_timeout)

            # Establish our connection
            sock.connect((self.host, self.port))

            # We control I/O blocking explicitly with select()
            sock.settimeout(None)

            self._sock = sock
            self._is_tls = False
            self._had_io = False

            if self.secure:
                self.start_tls()

            self.local_addr = self._sock.getsockname()
            self.remote_addr = self._sock.getpeername()
            self._refresh_wrappers()

            logger.debug(
                "Socket connected: local=%s remote=%s tls=%s",
                self.local_addr,
                self.remote_addr,
                self._is_tls,
            )

        except Exception as e:
            with contextlib.suppress(Exception):
                sock.close()

            self._sock = None
            self._had_io = False
            logger.debug("Socket connect exception: %s", e)
            raise AppriseSocketError(str(e)) from e

    def _server_hostname_for_tls(self) -> str:
        """
        Determine hostname used for SNI and hostname verification.

        If verify=True and host is an IP address, attempt reverse DNS lookup.
        """
        host = self.host

        if not self.verify:
            return host

        try:
            ipaddress.ip_address(host)
        except ValueError:
            return host

        try:
            name, _, _ = socket.gethostbyaddr(host)
            return name.rstrip(".") if name else host
        except Exception:
            return host

    def _build_ssl_context(self) -> ssl.SSLContext:
        """Build SSL context using certifi bundle when verify=True."""
        if self.verify:
            import certifi

            ctx = ssl.create_default_context(cafile=certifi.where())
            ctx.check_hostname = True
            ctx.verify_mode = ssl.CERT_REQUIRED
            return ctx

        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx

    def start_tls(self) -> None:
        """Upgrade an existing TCP connection to TLS."""
        if self._sock is None:
            raise AppriseSocketError("No active connection to upgrade")

        if self._is_tls:
            return

        server_hostname = self._server_hostname_for_tls()
        logger.trace("Starting TLS upgrade: sni=%s", server_hostname)

        try:
            ctx = self._build_ssl_context()
            tls_sock = ctx.wrap_socket(
                self._sock,
                server_hostname=server_hostname,
            )

            tls_sock.setblocking(False)
            self._sock = tls_sock
            self._is_tls = True

            self.local_addr = self._sock.getsockname()
            self.remote_addr = self._sock.getpeername()
            self._refresh_wrappers()

            logger.trace(
                "TLS upgrade complete: local=%s remote=%s",
                self.local_addr,
                self.remote_addr,
            )

        except ssl.SSLError as e:
            self.close()
            logger.debug("TLS negotiation exception: %s", e)
            raise AppriseSocketError(f"TLS negotiation failed: {e}") from e
        except OSError as e:
            self.close()
            logger.debug("TLS negotiation exception: %s", e)
            raise AppriseSocketError(str(e)) from e

    def _attempt_reconnect(
        self,
        action: str,
        exc: Exception,
    ) -> bool:
        """
        Attempt to reconnect and allow the caller to retry once.

        Returns True if a reconnect was performed and the caller should retry.
        """
        # Only retry if we have previously completed useful I/O since the last
        # connect(). This prevents retrying the first failed read/write after
        # connect.
        if not self._had_io:
            return False

        logger.warning(
            "Socket %s failed, reconnecting and retrying", action
        )
        logger.debug("Socket %s exception: %s", action, exc)

        try:
            self.close()
            self.connect()
        except Exception as e:
            logger.debug("Socket reconnect exception: %s", e)
            return False

        return True

    def read(
        self,
        max_bytes: int = 32768,
        blocking: bool = False,
        timeout: Optional[float] = None,
        retries: Optional[int] = None,
    ) -> bytes:
        """
        Read up to max_bytes bytes.

        blocking=False:
          - returns immediately with available data, or b"" if none

        blocking=True:
          - waits up to timeout seconds (or instance read timeout if timeout is
            None), then reads once
          - if both are None, waits indefinitely

        retries:
          - number of reconnect attempts permitted if the socket goes stale
            after prior successful I/O. Defaults to None (which takes value
            globally passed into the class)
        """
        if self._sock is None:
            return b""

        # Compute retry attempts; treat retries=0 as explicit 0
        retry_count = self.retries if retries is None else int(retries)
        attempts = max(0, retry_count) + 1

        # Derive wait timeout (None means wait indefinitely)
        wait_timeout = \
            self._read_timeout if timeout is None else float(timeout)

        # We manage readiness via select, socket stays non-blocking
        self._sock.setblocking(False)

        while attempts:
            attempts -= 1

            try:
                if not blocking:
                    try:
                        data = self._sock.recv(int(max_bytes))
                        if data == b"":
                            raise AppriseSocketError(
                                "Connection lost during read")
                        self._had_io = True
                        return data
                    except (BlockingIOError, ssl.SSLWantReadError,
                            ssl.SSLWantWriteError):
                        return b""

                # blocking=True path: wait for readability, then recv
                if wait_timeout is None:
                    # Wait indefinitely but periodically confirm socket health
                    while True:
                        ready = self.can_read(0.5)
                        if ready is None:
                            raise AppriseSocketError("Socket closed")
                        if ready:
                            break
                else:
                    ready = self.can_read(wait_timeout)
                    if not ready:
                        return b""

                # Even after select says readable, TLS may still raise
                # WANT_READ/WRITE. Loop until we either receive data, timeout,
                # or the socket closes.
                while True:
                    try:
                        data = self._sock.recv(int(max_bytes))
                        if data == b"":
                            raise AppriseSocketError(
                                "Connection lost during read")
                        self._had_io = True
                        return data

                    except (ssl.SSLWantReadError, ssl.SSLWantWriteError,
                            BlockingIOError):

                        if wait_timeout is None:
                            continue

                        # Avoid busy loop
                        if not self.can_read(min(0.25, wait_timeout)):
                            return b""

            except (AppriseSocketError, OSError, ssl.SSLError) as e:
                # Normalise and log
                logger.warning("Socket read failed")
                logger.debug("Socket read exception: %s", e)

                # Only close on hard errors; WANT_READ/WRITE handled above
                if isinstance(e, OSError) \
                        and not isinstance(e, ssl.SSLWantReadError) \
                        and not isinstance(e, ssl.SSLWantWriteError):
                    self.close()

                err: Exception = e

                # Reconnect only if we've had prior useful I/O
                if attempts and self._attempt_reconnect(
                        action="read", exc=err):
                    continue

                if isinstance(err, AppriseSocketError):
                    raise err from None
                raise AppriseSocketError(str(err)) from err

        raise AppriseSocketError("Socket read failed")

    def write(
        self,
        data: bytes,
        flush: bool = True,
        timeout: Optional[float] = None,
        retries: Optional[int] = None,
    ) -> int:
        """
        Write bytes to the socket.

        timeout:
          - if None, uses instance read timeout
          - if both are None, blocks until complete

        retries:
          - number of reconnect attempts permitted if the socket goes stale
            after prior successful I/O. Defaults to None (which takes value
            globally passed into the class)
        """
        if self._sock is None:
            raise AppriseSocketError("No active connection")

        if not isinstance(data, (bytes, bytearray, memoryview)):
            raise AppriseInvalidData("write() expects bytes-like data")

        # Loop-based retry avoids recursion and keeps state obvious
        attempts = max(
            0, int(retries) if retries else self.retries) + 1

        while attempts:
            attempts -= 1

            view = memoryview(data)
            total_sent = 0

            op_timeout = (
                self._read_timeout if timeout is None else float(timeout)
            )
            deadline = (
                None
                if op_timeout is None
                else (time.monotonic() + op_timeout)
            )

            try:
                self._sock.setblocking(deadline is None)

                while total_sent < len(view):
                    if deadline is not None:
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            raise AppriseSocketError(
                                "Timed out during write"
                            )
                        writable = self.can_write(remaining)
                        if not writable:
                            raise AppriseSocketError(
                                "Timed out waiting for writable socket"
                            )

                    sent = self._sock.send(view[total_sent:])
                    if sent <= 0:
                        raise AppriseSocketError(
                            "Connection lost during write"
                        )
                    total_sent += sent

                if flush and self._wfile is not None:
                    self._wfile.flush()

                if total_sent > 0:
                    self._had_io = True

                return total_sent

            except (AppriseSocketError, OSError) as e:
                logger.warning("Socket write failed")
                logger.debug("Socket write exception: %s", e)

                # Normalise: any OSError implies the socket is toast
                if isinstance(e, OSError):
                    self.close()

                if self._attempt_reconnect(
                    retries=attempts,
                    action="write",
                    exc=e,
                ):
                    continue

                if isinstance(e, AppriseSocketError):
                    raise
                raise AppriseSocketError(str(e)) from e

        raise AppriseSocketError("Socket write failed")
