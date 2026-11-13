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

"""Opt-in HTTP destination checks for callers that fetch untrusted URLs.

Apprise API imports HTTPPolicy, HTTPPolicySession and is_public_ip_address
from here, so this module is shared between the two projects rather than
being internal to Apprise. Anything in it that looks unused from inside
Apprise alone is most likely there for that caller; check apprise-api
before removing it.

Requests and urllib3 are the only HTTP libraries involved, and nothing here
needs, or should grow, another one. urllib3 is not held at arm's length
though: pinning a connection to an address we already approved is not
something its public interface can express, so this module subclasses its
connection and pool classes and hooks two protected details.

- ``_new_conn()`` is overridden to open our own pinned socket.
- ``_dns_host`` is read rather than ``host``, because it is the name urllib3
  itself resolves; ``host`` may have been normalized by then.
- ``_put_conn()`` is extended to learn when a download is done with a
  connection, so its time limit never cuts one another download now uses.

All three have been present unchanged through urllib3 1.26 and 2.x. What is
deliberately avoided is *importing* underscore-prefixed names out of
urllib3, since those do move between releases and several are missing from
1.26 altogether; ``_DEFAULT_TIMEOUT`` below is defined locally for exactly
that reason.

Because of that coupling, the tests for this module are a compatibility
gate rather than plain unit tests. Run them against the oldest urllib3 that
Apprise supports (the 1.26 series, which RHEL and Rocky Linux ship) as well
as the current one before accepting a change here.
"""

from collections.abc import Iterator
from concurrent.futures import (
    ThreadPoolExecutor,
    TimeoutError as FutureTimeoutError,
)
import contextlib
from contextlib import contextmanager
import contextvars
import heapq
import ipaddress
import itertools
import socket
from socket import timeout as SocketTimeout
import sys
import threading
import time
from typing import Any, Optional
from urllib.parse import urlsplit

import requests
from requests.adapters import HTTPAdapter
from urllib3.connection import HTTPConnection, HTTPSConnection
from urllib3.connectionpool import HTTPConnectionPool, HTTPSConnectionPool
from urllib3.exceptions import (
    ConnectTimeoutError,
    NewConnectionError,
)
from urllib3.poolmanager import PoolManager
from urllib3.util.connection import allowed_gai_family

from .parse import is_hostname

# Keep this sentinel local because urllib3's private equivalent varies by
# version and is absent from the widely used 1.26.x series.
_DEFAULT_TIMEOUT = object()

# DNS work is shared so many policies cannot create unbounded thread pools.
_DNS_POOL = ThreadPoolExecutor(
    max_workers=8,
    thread_name_prefix="apprise-http-resolve",
)
_DNS_SLOTS = threading.BoundedSemaphore(16)

# The download in progress, so the connections it uses can be cut off at
# any point by track_connections(). Left unset, nothing is tracked.
_active_tracker: contextvars.ContextVar[Optional["ConnectionTracker"]] = (
    contextvars.ContextVar("apprise_connection_tracker", default=None)
)

# RFC 6598 shared space is neither private nor generally Internet-routable.
_CGN_SHARED_V4 = ipaddress.ip_network("100.64.0.0/10")

# Standard NAT64 prefixes carry an IPv4 destination in their final 32 bits.
_NAT64_NETWORKS = (
    ipaddress.ip_network("64:ff9b::/96"),
    ipaddress.ip_network("64:ff9b:1::/48"),
)


def is_public_ip_address(value):
    """Return true for an ordinary public unicast IP address."""
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False

    if isinstance(address, ipaddress.IPv6Address):
        # NAT64 inherits the safety classification of its embedded IPv4.
        for network in _NAT64_NETWORKS:
            if address in network:
                embedded = ipaddress.IPv4Address(int(address) & 0xFFFFFFFF)
                return is_public_ip_address(embedded)

        # Judge IPv4-mapped addresses by their embedded IPv4 address because
        # some Python releases misclassify the IPv6 wrapper as reserved.
        if address.ipv4_mapped is not None:
            return is_public_ip_address(address.ipv4_mapped)

    # Reject any address that is not a public unicast address.
    blocked = (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or (
            isinstance(address, ipaddress.IPv6Address)
            and address.is_site_local
        )
        or address.is_reserved
        or address.is_unspecified
        or address.is_multicast
        or (
            isinstance(address, ipaddress.IPv4Address)
            and address in _CGN_SHARED_V4
        )
    )
    if blocked:
        return False

    if isinstance(address, ipaddress.IPv6Address):
        # IPv4-mapped addresses returned above; validate 6to4 addresses here.
        if address.sixtofour and not is_public_ip_address(address.sixtofour):
            return False

        # Teredo addresses embed an IPv4 address in their last 32 bits.
        if address.teredo and not all(
            is_public_ip_address(item) for item in address.teredo
        ):
            return False

    return True


def is_secure_http_url(url):
    """Validate a URL before it is used as a request target.

    A valid URL:
     - uses HTTPS
     - points at a valid hostname or IP address
     - carries no username or password, even an empty one
     - has a usable port
     - has no fragment, which would not reach the server

    Private hosts remain valid for self-hosted services. Returns ``True``
    when all checks pass and ``False`` otherwise.
    """

    if not isinstance(url, str):
        return False

    try:
        parsed = urlsplit(url)

        # Reading an invalid port, or a malformed IPv6 address, raises a
        # ValueError here.
        port = parsed.port

    except ValueError:
        return False

    # Port zero cannot be connected to.
    if port == 0:
        return False

    # A fragment is never sent to a server. An empty one still counts, so
    # the character itself is what we look for.
    if "#" in url:
        return False

    # Anything that is not HTTPS is refused.
    if parsed.scheme.lower() != "https":
        return False

    # A URL with no destination host is of no use to us.
    hostname = parsed.hostname
    if not hostname:
        return False

    # Reject credentials embedded in the URL. The comparison is against
    # None so that an empty https://@example.com is caught too.
    if parsed.username is not None or parsed.password is not None:
        return False

    # Confirm the host itself is sane. This covers hostnames, IPv4 and
    # IPv6 alike; only the yes or no answer is needed here.
    return bool(is_hostname(hostname))


def read_bounded_response(r, max_bytes, chunk_size=65536):
    """Read and close a streamed response.

    Return ``None`` if the response exceeds ``max_bytes``; otherwise,
    return the bytes read.
    """
    chunks = []
    total = 0
    try:
        for chunk in r.iter_content(chunk_size=chunk_size):
            if not chunk:
                continue

            total += len(chunk)
            if total > max_bytes:
                return None

            chunks.append(chunk)

        return b"".join(chunks)

    finally:
        r.close()


def _release_dns_slot(_future):
    """Release a DNS slot only after its lookup has actually stopped."""
    _DNS_SLOTS.release()


def _set_socket_options(sock, options):
    """Apply the same socket options urllib3 would normally configure.

    Three shapes of option arrive here, and all three are supported on
    purpose:

    - ``(level, option, value)``, which is what urllib3 itself supplies.
    - ``(level, option, value, "tcp"|"udp")``, which urllib3-future adds so
      one option list can describe both transports. Apprise never requires
      urllib3-future, but a host may well have it installed, and an option
      it supplies must not raise here.
    - ``(level, option, None, length)``, Python's own form for an option
      given by length rather than by value.

    The tests build each shape by hand instead of installing anything, so
    they also pass on systems that ship the older urllib3 1.26 series.
    """
    if options is None:
        return

    for opt in options:
        # A fourth item that is text names the transport the option belongs
        # to, so an option meant for UDP is not pushed onto a TCP socket.
        if len(opt) == 4 and isinstance(opt[3], str):
            socket_type = {
                "tcp": socket.SOCK_STREAM,
                "udp": socket.SOCK_DGRAM,
            }.get(opt[3].lower())
            if socket_type == sock.type:
                sock.setsockopt(*opt[:3])

            continue

        # This also preserves Python's (level, option, None, length) form.
        sock.setsockopt(*opt)


class HTTPPolicy:
    """Validate URLs and pin connections to approved DNS answers.

    ``url_filter`` and ``address_filter`` return true for allowed values.
    They are optional so applications can enforce only the rules they need.
    """

    def __init__(
        self,
        url_filter=None,
        address_filter=None,
        resolve_timeout=5.0,
    ):
        self.url_filter = url_filter
        self.address_filter = address_filter
        self.resolve_timeout = resolve_timeout

    def validate_url(self, url):
        """Raise InvalidURL when a request URL is not approved."""
        if not self.url_filter:
            return

        try:
            allowed = self.url_filter(url)
        except Exception as exc:
            # A broken application policy must fail closed as a request error.
            raise requests.exceptions.InvalidURL(
                "Outbound HTTP URL policy failed"
            ) from exc

        if not allowed:
            # A policy that returns false must fail closed as a request error.
            raise requests.exceptions.InvalidURL(
                "URL denied by outbound HTTP policy"
            )

    def resolve(self, host, port):
        """Resolve once and return approved connection addresses."""
        # Refuse new work when slow DNS has consumed the bounded capacity.
        if not _DNS_SLOTS.acquire(blocking=False):
            raise socket.gaierror(
                socket.EAI_AGAIN,
                "DNS resolver capacity exhausted",
            )

        try:
            # Submit a DNS lookup to the shared thread pool so it cannot block
            # the caller.
            future = _DNS_POOL.submit(
                socket.getaddrinfo,
                host,
                port,
                allowed_gai_family(),
                socket.SOCK_STREAM,
            )
        except Exception as exc:
            _DNS_SLOTS.release()
            raise socket.gaierror(
                socket.EAI_AGAIN,
                "DNS resolver is unavailable",
            ) from exc

        # Timed-out native lookups retain their slot until the worker exits.
        future.add_done_callback(_release_dns_slot)
        try:
            answers = future.result(timeout=self.resolve_timeout)
        except FutureTimeoutError as exc:
            future.cancel()
            raise socket.gaierror(
                socket.EAI_AGAIN,
                "DNS resolution timed out",
            ) from exc
        except Exception as exc:
            # Normalize resolver failures for urllib3's connection handling.
            raise socket.gaierror(
                socket.EAI_NONAME,
                "DNS resolution failed",
            ) from exc

        # Preserve each full sockaddr so connecting cannot trigger new DNS.
        approved = []
        for answer in answers:
            try:
                address = answer[4][0]
            except (IndexError, TypeError):
                # An unrecognizable resolver result cannot be trusted.
                continue

            if self.address_filter:
                try:
                    if not self.address_filter(address):
                        continue
                except Exception as exc:
                    # A broken policy callback must fail closed.
                    raise socket.gaierror(
                        socket.EAI_NONAME,
                        "Address policy failed",
                    ) from exc

            approved.append(answer)

        if not approved:
            raise socket.gaierror(
                socket.EAI_NONAME,
                "No DNS address passed the outbound HTTP policy",
            )

        return approved

    def create_connection(
        self,
        host,
        port,
        timeout=_DEFAULT_TIMEOUT,
        source_address=None,
        socket_options=None,
    ):
        """Connect to a previously validated DNS answer."""
        error = None
        for family, socktype, proto, _canonname, sockaddr in self.resolve(
            host,
            port,
        ):
            sock = None
            try:
                # Apply the same socket settings urllib3 normally uses.
                sock = socket.socket(family, socktype, proto)
                _set_socket_options(sock, socket_options)
                if timeout is not _DEFAULT_TIMEOUT:
                    sock.settimeout(timeout)
                if source_address:
                    sock.bind(source_address)

                sock.connect(sockaddr)

                # Confirm the socket reached the exact address DNS approved.
                try:
                    expected_address = ipaddress.ip_address(sockaddr[0])
                    peer_address = ipaddress.ip_address(sock.getpeername()[0])
                except (IndexError, TypeError, ValueError) as exc:
                    raise OSError(
                        "Connected socket returned an invalid peer address"
                    ) from exc

                if peer_address != expected_address:
                    raise OSError(
                        "Connected peer did not match the approved DNS address"
                    )

                return sock

            except OSError as exc:
                error = exc
                if sock is not None:
                    sock.close()

        if error is not None:
            raise error

        raise OSError("getaddrinfo returned no usable addresses")


class _PolicyConnectionMixin:
    """Route urllib3 connections through an HTTPPolicy."""

    policy = None

    def _new_conn(self):
        """Open a pinned socket while retaining the original TLS hostname."""
        try:
            sock = self.policy.create_connection(
                self._dns_host,
                self.port,
                timeout=self.timeout,
                source_address=self.source_address,
                socket_options=self.socket_options,
            )
        except socket.gaierror as exc:
            # This exception exists across supported urllib3 releases.
            raise NewConnectionError(
                self,
                "Failed to resolve an approved address for "
                f"{self.host}: {exc}",
            ) from exc
        except SocketTimeout as exc:
            raise ConnectTimeoutError(
                self,
                f"Connection to {self.host} timed out. "
                f"(connect timeout={self.timeout})",
            ) from exc
        except OSError as exc:
            raise NewConnectionError(
                self,
                f"Failed to establish a new connection: {exc}",
            ) from exc

        sys.audit("http.client.connect", self, self.host, self.port)
        return sock


def _shut_down(conn: Any) -> None:
    """End a connection, waking any read still waiting on it."""
    # A connection still being opened has no socket to end yet
    sock = getattr(conn, "apprise_sock", None)

    # Wrappers such as PyOpenSSL's, or TLS sent inside a TLS tunnel, keep
    # the socket they wrap as .socket
    for _ in range(3):
        if isinstance(sock, socket.socket):
            break

        sock = getattr(sock, "socket", None)

    else:
        # Nothing here we know how to end
        return

    # Best effort, since the connection may already be gone
    with contextlib.suppress(Exception):
        # The plain socket call is used so a TLS socket's own shutdown()
        # does not reset TLS state the download's thread is still reading
        socket.socket.shutdown(sock, socket.SHUT_RDWR)


class ConnectionTracker:
    """The connections one download is using, so they can be cut off.

    Once cut off, a connection the download uses afterwards is ended
    straight away, so one opened just as time runs out cannot slip through.
    """

    __slots__ = ("_lock", "connections", "expired", "finished")

    def __init__(self) -> None:
        """Start with no connections."""
        # The download's thread adds and releases while the watchdog cuts off
        self._lock = threading.Lock()

        # The connections the download is using right now
        self.connections: set[Any] = set()

        # Set once time ran out, and once the download is over
        self.expired = False
        self.finished = False

    def add(self, conn: Any) -> None:
        """Track a connection the download is about to use."""
        with self._lock:
            if not self.expired:
                conn.apprise_tracker = self
                self.connections.add(conn)
                return

        # Too late: time ran out, so end it before it is used
        _shut_down(conn)

    def release(self, conn: Any) -> None:
        """Stop tracking a connection that goes back to its pool."""
        # Waits for a cut off in progress, so a connection is always ended
        # before another download can take it from the pool
        with self._lock:
            conn.apprise_tracker = None
            self.connections.discard(conn)

    def cut_off(self) -> None:
        """End every connection in use, and any the download uses later."""
        with self._lock:
            if self.finished:
                # The download ended before its time was up
                return

            self.expired = True

            # Ended while holding the lock, so none can go back to its pool
            # and on to another download part way through
            for conn in self.connections:
                _shut_down(conn)

    def finish(self) -> None:
        """Mark the download over, so a late cut off changes nothing."""
        with self._lock:
            self.finished = True

            # Forget anything left behind, such as a connection closed
            # after an error instead of going back to its pool
            for conn in self.connections:
                conn.apprise_tracker = None

            self.connections.clear()


class WatchdogUnavailableError(RuntimeError):
    """No thread could be started to keep a download's time limit."""


class _Watchdog:
    """One thread that cuts off each tracked download once its time is up."""

    def __init__(self) -> None:
        """Start with nothing to watch and no thread yet."""
        # Guards the schedule, and wakes the thread whenever it changes
        self._wake = threading.Condition()

        # Downloads waiting on their deadline, soonest first. A tie is
        # settled by the order added, so trackers are never compared.
        self._due: list[tuple[float, int, ConnectionTracker]] = []
        self._order = itertools.count()

        # Downloads over since the schedule was last tidied up
        self._stale = 0

        # Started on first use, and again if it is ever gone (after a fork)
        self._thread: Optional[threading.Thread] = None

    def watch(self, tracker: ConnectionTracker, deadline: float) -> None:
        """Cut off ``tracker`` once ``time.monotonic()`` passes ``deadline``.

        Raises WatchdogUnavailableError if no thread can be started to
        watch it, so a download never runs without its time limit.
        """
        with self._wake:
            if self._thread is None or not self._thread.is_alive():
                # Started before the download is added, so a failure leaves
                # nothing behind
                thread = threading.Thread(
                    target=self._run, name="apprise-http-watchdog", daemon=True
                )
                try:
                    thread.start()

                except RuntimeError as exc:
                    raise WatchdogUnavailableError(
                        "No thread could be started to keep the time limit"
                    ) from exc

                self._thread = thread

            # Add the download, and wake the thread if it is now the soonest
            heapq.heappush(self._due, (deadline, next(self._order), tracker))
            self._wake.notify()

    def forget(self) -> None:
        """Note that one of the downloads being watched is over."""
        with self._wake:
            self._stale += 1

            # Tidied up only once most of the schedule is downloads already
            # over, so each one costs little however many run at once
            if self._stale * 2 > len(self._due):
                self._due = [
                    entry for entry in self._due if not entry[2].finished
                ]
                heapq.heapify(self._due)
                self._stale = 0

    def _run(self) -> None:
        """Cut off each download in turn as its time runs out."""
        while True:
            with self._wake:
                # Sleep until the soonest deadline, or until one is added
                while not self._due or self._due[0][0] > time.monotonic():
                    self._wake.wait(
                        self._due[0][0] - time.monotonic()
                        if self._due
                        else None
                    )

                tracker = heapq.heappop(self._due)[2]

            # Cut off outside the schedule lock so new downloads never wait.
            # One odd connection must never stop the thread, or every other
            # download would lose its time limit with it.
            with contextlib.suppress(Exception):
                tracker.cut_off()


# Shared by every download, so each one does not need its own thread
_WATCHDOG = _Watchdog()


@contextmanager
def track_connections(
    tracker: ConnectionTracker, deadline: Optional[float] = None
) -> Iterator[None]:
    """Track the connections used meanwhile, and cut them off in time.

    - ``tracker``: each connection used in this thread is added to it.
    - ``deadline``: a ``time.monotonic()`` value to cut them off at, or
      ``None`` for no limit.
    - Raises WatchdogUnavailableError if no thread can be started to keep
      the time.
    - Only tracked_session() and HTTPPolicySession connections can be
      reached; other transports keep theirs out of reach.
    """
    token = _active_tracker.set(tracker)
    try:
        if deadline is not None:
            # Cut the download off once its time is up
            _WATCHDOG.watch(tracker, deadline)

        yield

    finally:
        _active_tracker.reset(token)

        # The download is over, so a late cut off must not touch connections
        # that have since gone back to their pool
        tracker.finish()

        if deadline is not None:
            # Nothing is left to cut off
            _WATCHDOG.forget()


def _track(conn: Any) -> None:
    """Add a connection to the download in progress, if one is tracked."""
    # Nothing is tracked outside track_connections()
    tracker = _active_tracker.get()
    if tracker is not None:
        tracker.add(conn)


class _TrackedConnectionMixin:
    """Let the download using a connection cut it off at any time."""

    # The tracker of the download using this connection right now
    apprise_tracker: Optional[ConnectionTracker] = None

    # The socket a cut off ends, kept because a reply that closes the
    # connection when done takes the socket over and empties sock
    apprise_sock: Optional[socket.socket] = None

    # The socket being opened, until connect() is done with it
    apprise_opening: Optional[socket.socket] = None

    def _new_conn(self) -> socket.socket:
        """Open the socket, and let the download reach it straight away."""
        sock = super()._new_conn()

        # A copy of the socket is what gets cut off while connecting.
        # Setting up TLS moves the socket into a new TLS socket that only
        # shows up once its handshake is done, but the copy still reaches
        # the same connection, so a server that stalls the handshake (or a
        # proxy slow to open a tunnel) can be cut off too.
        copy = sock
        if isinstance(sock, socket.socket):
            # Without a copy (such as when out of file descriptors), the
            # socket itself still covers a proxy that is slow to answer
            with contextlib.suppress(OSError):
                copy = sock.dup()

        self.apprise_opening = sock
        self.apprise_sock = copy
        _track(self)
        return sock

    def connect(self) -> None:
        """Open the connection, then let the download reach it."""
        try:
            super().connect()

        except BaseException:
            # A connection that failed to open never reaches a pool, and
            # some urllib3 releases leave its socket open (such as a proxy
            # tunnel cut off part way), so close it now
            self._opened(None)
            raise

        # Kept once opened, so for HTTPS this is the TLS socket
        self._opened(self.sock)

        # Added again after opening, so time that ran out while the TLS
        # socket was being set up (or just as the copy was closed) still
        # ends it
        _track(self)

    def _opened(self, sock: Optional[socket.socket]) -> None:
        """Swap the copy used while connecting for the finished socket.

        - ``sock``: the connection's socket, or ``None`` if it failed to
          open, in which case the socket being opened is closed too.
        """
        copy, opening = self.apprise_sock, self.apprise_opening

        # Swapped first, so a cut off from now on reaches the new socket
        self.apprise_sock, self.apprise_opening = sock, None

        closing = [copy] if copy is not opening else []
        if sock is None:
            closing.append(opening)

        for old in closing:
            if old is not None:
                with contextlib.suppress(Exception):
                    old.close()

    def _tunnel(self) -> None:
        """Open a tunnel through a proxy, closing its reply if that fails."""
        # Python 3.11 and older leave the proxy's reply open when reading it
        # fails (such as when cut off), and that reply keeps the socket open
        # after connect() closes it, so each reply made here is noted
        replies: list[Any] = []
        make = self.response_class

        def reply(*args: Any, **kwargs: Any) -> Any:
            response = make(*args, **kwargs)
            replies.append(response)
            return response

        self.response_class = reply
        try:
            super()._tunnel()

        except Exception:
            for response in replies:
                with contextlib.suppress(Exception):
                    response.close()

            raise

        finally:
            # The request itself reads its reply the usual way
            self.response_class = make

    def request(self, *args: Any, **kwargs: Any) -> Any:
        """Send a request, new connection or reused, as a tracked one."""
        # Added first, so a wait for the reply can be cut off
        _track(self)
        return super().request(*args, **kwargs)


class _TrackedPoolMixin:
    """Stop tracking a connection once it goes back to its pool."""

    def _put_conn(self, conn: Any) -> None:
        """Release a connection from its download before pooling it."""
        # urllib3 passes None in place of a connection it already closed
        tracker = getattr(conn, "apprise_tracker", None)
        if tracker is not None:
            tracker.release(conn)

        super()._put_conn(conn)


class _TrackedHTTPConnection(_TrackedConnectionMixin, HTTPConnection):
    """An HTTP connection a download can cut off."""


class _TrackedHTTPSConnection(_TrackedConnectionMixin, HTTPSConnection):
    """An HTTPS connection a download can cut off."""


class _TrackedHTTPConnectionPool(_TrackedPoolMixin, HTTPConnectionPool):
    """Use connections a download can cut off for HTTP."""

    ConnectionCls = _TrackedHTTPConnection


class _TrackedHTTPSConnectionPool(_TrackedPoolMixin, HTTPSConnectionPool):
    """Use connections a download can cut off for HTTPS."""

    ConnectionCls = _TrackedHTTPSConnection


# The pool a download can cut off, for each kind of pool urllib3 uses
_TRACKED_POOLS: dict[type, type] = {
    HTTPConnectionPool: _TrackedHTTPConnectionPool,
    HTTPSConnectionPool: _TrackedHTTPSConnectionPool,
}


def _tracked_pool(pool_cls: type) -> type:
    """Return a pool like ``pool_cls`` whose connections can be cut off."""
    if issubclass(pool_cls, _TrackedPoolMixin):
        # Already one
        return pool_cls

    tracked = _TRACKED_POOLS.get(pool_cls)
    if tracked is None:
        # Made the first time a new kind of pool is seen, such as the ones
        # a SOCKS proxy uses
        connection_cls = type(
            pool_cls.ConnectionCls.__name__,
            (_TrackedConnectionMixin, pool_cls.ConnectionCls),
            {},
        )
        tracked = type(
            pool_cls.__name__,
            (_TrackedPoolMixin, pool_cls),
            {"ConnectionCls": connection_cls},
        )
        _TRACKED_POOLS[pool_cls] = tracked

    return tracked


def _track_pools(manager: PoolManager) -> None:
    """Make every pool ``manager`` creates from now on a tracked one."""
    manager.pool_classes_by_scheme = {
        scheme: _tracked_pool(pool_cls)
        for scheme, pool_cls in manager.pool_classes_by_scheme.items()
    }


class _TrackedHTTPAdapter(HTTPAdapter):
    """Install connection pools a download can cut off into Requests."""

    def init_poolmanager(
        self,
        connections: int,
        maxsize: int,
        block: bool = False,
        **pool_kwargs: Any,
    ) -> None:
        """Create the normal manager, then replace its pool classes."""
        super().init_poolmanager(
            connections, maxsize, block=block, **pool_kwargs
        )
        _track_pools(self.poolmanager)

    def proxy_manager_for(self, proxy: str, **proxy_kwargs: Any) -> Any:
        """Create the normal proxy manager, then replace its pool classes."""
        manager = super().proxy_manager_for(proxy, **proxy_kwargs)

        # Requests keeps one manager per proxy, so this mostly finds the
        # pools already replaced
        _track_pools(manager)
        return manager


def tracked_session() -> requests.Session:
    """Return a plain Requests session that track_connections() can reach.

    Connections through a proxy are tracked too.
    """
    # Behaves like requests.get() otherwise, proxies and all
    session = requests.Session()
    adapter = _TrackedHTTPAdapter()
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def _policy_pool_classes(policy):
    """Build connection pools bound to one request policy."""

    # The tracking comes first, so it wraps the socket the policy opens
    class PolicyHTTPConnection(
        _TrackedConnectionMixin, _PolicyConnectionMixin, HTTPConnection
    ):
        pass

    class PolicyHTTPSConnection(
        _TrackedConnectionMixin, _PolicyConnectionMixin, HTTPSConnection
    ):
        pass

    # Class attributes avoid leaking policy objects into urllib3 pool keys.
    PolicyHTTPConnection.policy = policy
    PolicyHTTPSConnection.policy = policy

    class PolicyHTTPConnectionPool(_TrackedHTTPConnectionPool):
        """Use a policy-aware connection class for HTTP."""

        ConnectionCls = PolicyHTTPConnection

    class PolicyHTTPSConnectionPool(_TrackedHTTPSConnectionPool):
        """Use a policy-aware connection class for HTTPS."""

        ConnectionCls = PolicyHTTPSConnection

    return {
        "http": PolicyHTTPConnectionPool,
        "https": PolicyHTTPSConnectionPool,
    }


class _PolicyHTTPAdapter(HTTPAdapter):
    """Install policy-aware connection pools into Requests."""

    def __init__(self, policy, *args, **kwargs):
        self.policy = policy
        super().__init__(*args, **kwargs)

    def init_poolmanager(
        self,
        connections,
        maxsize,
        block=False,
        **pool_kwargs,
    ):
        """Create the normal manager, then replace its pool classes."""
        # These three belong to Requests' own adapter rather than to urllib3.
        # They are part of what it pickles, so an adapter that overrides this
        # method still has to set them.
        self._pool_connections = connections
        self._pool_maxsize = maxsize
        self._pool_block = block
        self.poolmanager = PoolManager(
            num_pools=connections,
            maxsize=maxsize,
            block=block,
            **pool_kwargs,
        )
        self.poolmanager.pool_classes_by_scheme = _policy_pool_classes(
            self.policy
        )

    def proxy_manager_for(self, proxy, **proxy_kwargs):
        """Reject proxies because they resolve targets outside this policy."""
        raise requests.exceptions.ProxyError(
            "Proxies are disabled by outbound HTTP policy"
        )


class HTTPPolicySession(requests.Session):
    """A Requests session that validates every hop and pins its DNS result."""

    def __init__(self, policy):
        """Create a session that enforces the given HTTPPolicy."""
        super().__init__()
        self.policy = policy

        # Environment proxies must not reroute a checked destination.
        self.trust_env = False

        # Install a policy-aware adapter for all HTTP and HTTPS requests.
        adapter = _PolicyHTTPAdapter(policy)
        self.mount("http://", adapter)
        self.mount("https://", adapter)

    def send(self, request, **kwargs):
        """Validate the initial URL and every redirect before transmission."""
        self.policy.validate_url(request.url)
        return super().send(request, **kwargs)
