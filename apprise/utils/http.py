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

"""Opt-in HTTP destination checks for callers that fetch untrusted URLs."""

from concurrent.futures import (
    ThreadPoolExecutor,
    TimeoutError as FutureTimeoutError,
)
import ipaddress
import socket
from socket import timeout as SocketTimeout
import sys
import threading
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

# Keep this sentinel local because urllib3's private equivalent varies by
# version and is absent from the widely used 1.26.x series.
_DEFAULT_TIMEOUT = object()

# DNS work is shared so many policies cannot create unbounded thread pools.
_DNS_POOL = ThreadPoolExecutor(
    max_workers=8,
    thread_name_prefix="apprise-http-resolve",
)
_DNS_SLOTS = threading.BoundedSemaphore(16)

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

        if address.teredo and not all(
            is_public_ip_address(item) for item in address.teredo
        ):
            return False

    return True


def is_secure_http_url(url):
    """Return true for an HTTPS URL with a host and no embedded credentials."""
    try:
        parsed = urlsplit(url)
        credentials = (parsed.username, parsed.password)
        return bool(
            parsed.scheme.lower() == "https"
            and parsed.hostname
            and credentials == (None, None)
        )
    except (TypeError, ValueError):
        return False


def _release_dns_slot(_future):
    """Release a DNS slot only after its lookup has actually stopped."""
    _DNS_SLOTS.release()


def _set_socket_options(sock, options):
    """Apply the same socket options urllib3 would normally configure."""
    if options is None:
        return

    for opt in options:
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


def _policy_pool_classes(policy):
    """Build connection pools bound to one request policy."""

    class PolicyHTTPConnection(_PolicyConnectionMixin, HTTPConnection):
        pass

    class PolicyHTTPSConnection(_PolicyConnectionMixin, HTTPSConnection):
        pass

    # Class attributes avoid leaking policy objects into urllib3 pool keys.
    PolicyHTTPConnection.policy = policy
    PolicyHTTPSConnection.policy = policy

    class PolicyHTTPConnectionPool(HTTPConnectionPool):
        ConnectionCls = PolicyHTTPConnection

    class PolicyHTTPSConnectionPool(HTTPSConnectionPool):
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
        super().__init__()
        self.policy = policy

        # Environment proxies must not reroute a checked destination.
        self.trust_env = False

        adapter = _PolicyHTTPAdapter(policy)
        self.mount("http://", adapter)
        self.mount("https://", adapter)

    def send(self, request, **kwargs):
        """Validate the initial URL and every redirect before transmission."""
        self.policy.validate_url(request.url)
        return super().send(request, **kwargs)
