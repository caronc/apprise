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


# A small websocket client that speaks the Nostr relay protocol.
#
# Relays are websocket servers.  A client sends JSON arrays such as
# ["EVENT", {...}] or ["REQ", "<id>", {...}] and the relay answers with
# ["OK", ...], ["EVENT", ...], ["EOSE", ...] and so on.  Some relays ask
# the client to prove who it is first (NIP-42) by sending ["AUTH", ...].
#
# Resources:
# - https://github.com/nostr-protocol/nips/blob/master/01.md
# - https://github.com/nostr-protocol/nips/blob/master/42.md
# - https://datatracker.ietf.org/doc/html/rfc6455

from __future__ import annotations

from base64 import b64encode
import contextlib
import hashlib
from json import dumps, loads
import os
import time
from typing import Any, Optional
from urllib.parse import urlsplit

from ...logger import logger
from ...utils.http import HTTPPolicy, is_public_ip_address
from ...utils.socket import AppriseSocketError, SocketTransport
from .crypto import NostrKey

# Used to confirm the server really agreed to a websocket upgrade
WS_ACCEPT_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

# Websocket frame types (opcodes)
WS_CONTINUATION = 0x0
WS_TEXT = 0x1
WS_CLOSE = 0x8
WS_PING = 0x9
WS_PONG = 0xA

# The most we read for the server's handshake reply (in bytes)
WS_MAX_HEADER = 16384

# The most we accept for one message from a relay (in bytes); the events
# we ask for are small, so anything bigger is refused straight away
WS_MAX_MESSAGE = 1048576

# The most events kept from one query when it gives no limit of its own
RELAY_MAX_EVENTS = 10

# The most addresses tried for a relay found in someone else's list
RELAY_MAX_ADDRESSES = 4


class RelayTransport(SocketTransport):
    """A socket that checks TLS against the relay's name.

    This lets us connect to an address we looked up and checked ourselves
    while still confirming the relay's certificate by its own name.
    """

    def __init__(
        self, server_hostname: str, *args: Any, **kwargs: Any
    ) -> None:
        """Remember the relay's own name for TLS."""
        super().__init__(*args, **kwargs)
        self.server_hostname = server_hostname

    def _server_hostname_for_tls(self) -> str:
        """Always use the relay's own name, never a reverse lookup."""
        return self.server_hostname

    def connect(self, timeout: Optional[float] = None) -> None:
        """Connect, optionally allowing less time than usual."""
        if timeout is not None:
            self._connect_timeout = timeout

        super().connect()


class NostrRelay:
    """One websocket connection to a Nostr relay."""

    def __init__(
        self,
        url: str,
        key: NostrKey,
        verify: bool = True,
        timeout: tuple[float, float] = (4.0, 4.0),
        user_agent: str = "Apprise",
        public_only: bool = False,
    ) -> None:
        """Prepare a connection to the relay at ``url``.

        Set ``public_only`` for relays that someone else told us about, so
        we never connect to a private address.
        """
        # Break the relay URL into the pieces the connection needs.
        parsed = urlsplit(url)
        self.url = url
        self.secure = parsed.scheme.lower() == "wss"
        self.host = parsed.hostname or ""
        self.port = parsed.port or (443 if self.secure else 80)
        self.path = (parsed.path or "/") + (
            "?" + parsed.query if parsed.query else ""
        )

        # Keep the default port out of the Host header.
        self.host_header = (
            self.host
            if parsed.port is None
            else "{}:{}".format(self.host, parsed.port)
        )

        # The key used when the relay asks us to authenticate.
        self.key = key
        self.user_agent = user_agent
        self.public_only = public_only

        # How long to wait to connect, and for each reply from the relay.
        self.connect_timeout = timeout[0]
        self.timeout = timeout[1]

        # The underlying (optionally TLS) socket.
        self.transport = RelayTransport(
            self.host,
            self.host,
            self.port,
            secure=self.secure,
            verify=verify,
            timeout=timeout,
        )

        # Bytes received but not yet turned into frames.
        self._buffer = bytearray()

        # The latest NIP-42 challenge, kept until we answer it.
        self._challenge: Optional[str] = None

    def __enter__(self) -> NostrRelay:
        """Connect when used in a ``with`` block."""
        # Open the socket and upgrade it to a websocket.
        self.connect()
        return self

    def __exit__(self, *args: Any) -> None:
        """Disconnect when leaving a ``with`` block."""
        # Always release the socket, even after an error.
        self.close()

    def connect(self) -> None:
        """Open the connection and perform the websocket handshake."""
        # Open the TCP (and TLS) connection; relays found in someone else's
        # list may only reach public addresses.
        if self.public_only:
            self._connect_public()

        else:
            self.transport.connect()

        # Ask the server to switch this connection over to a websocket.
        ws_key = b64encode(os.urandom(16)).decode()
        request = (
            "GET {path} HTTP/1.1\r\n"
            "Host: {host}\r\n"
            "User-Agent: {agent}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            "Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        ).format(
            path=self.path,
            host=self.host_header,
            agent=self.user_agent,
            key=ws_key,
        )
        self.transport.write(request.encode(), timeout=self.timeout)

        # Read until the end of the response headers.
        deadline = time.monotonic() + self.timeout
        while b"\r\n\r\n" not in self._buffer:
            if len(self._buffer) > WS_MAX_HEADER:
                raise AppriseSocketError(
                    "Relay sent an oversized websocket handshake."
                )

            self._fill(deadline)

        # Anything after the headers already belongs to the websocket.
        head, _, rest = bytes(self._buffer).partition(b"\r\n\r\n")
        if len(head) > WS_MAX_HEADER:
            # A single read can bring in more than the limit at once
            raise AppriseSocketError(
                "Relay sent an oversized websocket handshake."
            )

        self._buffer = bytearray(rest)
        lines = head.decode("latin-1").split("\r\n")

        # A successful upgrade always answers with status 101.
        if lines[0].split(" ")[1:2] != ["101"]:
            raise AppriseSocketError(
                "Relay refused the websocket upgrade: {}".format(lines[0])
            )

        # The server must prove it understood our websocket request.
        headers = {
            name.strip().lower(): value.strip()
            for name, _, value in (line.partition(":") for line in lines[1:])
        }
        expected = b64encode(
            hashlib.sha1((ws_key + WS_ACCEPT_GUID).encode()).digest()
        ).decode()
        if headers.get("sec-websocket-accept") != expected:
            raise AppriseSocketError(
                "Relay returned an invalid websocket handshake."
            )

        logger.trace("Nostr relay connected: %s", self.url)

    def _connect_public(self) -> None:
        """Connect to one of the relay's public addresses, in turn."""
        # Look the name up once, within our timeout, keeping only public
        # addresses; we then connect to those exact addresses
        policy = HTTPPolicy(
            address_filter=is_public_ip_address,
            resolve_timeout=self.connect_timeout,
        )
        try:
            found = policy.resolve(self.host, self.port)

        except OSError as e:
            raise AppriseSocketError(
                "Relay {} has no usable public address: {}".format(self.url, e)
            ) from e

        # Each address is only tried once, and only the first few are kept
        addresses: list[str] = []
        seen: set[str] = set()
        for *_, address in found:
            if address[0] not in seen:
                seen.add(address[0])
                addresses.append(address[0])
                if len(addresses) >= RELAY_MAX_ADDRESSES:
                    break

        # A few addresses share one connection timeout, so a long list of
        # dead addresses can not hold us up
        deadline = time.monotonic() + self.connect_timeout
        error = AppriseSocketError(
            "Relay {} has no public address.".format(self.url)
        )
        for address in addresses:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                error = AppriseSocketError(
                    "Timed out connecting to relay {}.".format(self.url)
                )
                break

            try:
                self.transport.host = address
                self.transport.connect(timeout=remaining)
                return

            except AppriseSocketError as e:
                # Try the next address
                error = e

        raise error

    def close(self) -> None:
        """Say goodbye to the relay and close the socket."""
        # A polite close frame is nice to have but never required.
        with contextlib.suppress(Exception):
            self._write_frame(WS_CLOSE, b"\x03\xe8")

        self.transport.close()

    def publish(self, event: dict[str, Any]) -> tuple[bool, str]:
        """Send ``event`` and return whether the relay accepted it."""
        # Send the event and wait for the relay's verdict.
        self._send(["EVENT", event])
        accepted, reason = self._wait_ok(event["id"])

        # Relays that need us to log in first get one more try.
        if (
            not accepted
            and reason.startswith("auth-required")
            and self._authenticate()
        ):
            self._send(["EVENT", event])
            accepted, reason = self._wait_ok(event["id"])

        return (accepted, reason)

    def query(self, filters: dict[str, Any]) -> list[dict[str, Any]]:
        """Return the stored events that match ``filters``."""
        # A random subscription id keeps replies apart.
        sub_id = os.urandom(8).hex()
        events: list[dict[str, Any]] = []
        reason = self._subscribe(sub_id, filters, events)

        # Relays that need us to log in first get one more try.
        if (
            reason is not None
            and reason.startswith("auth-required")
            and self._authenticate()
        ):
            self._subscribe(sub_id, filters, events)

        return events

    def _subscribe(
        self,
        sub_id: str,
        filters: dict[str, Any],
        events: list[dict[str, Any]],
    ) -> Optional[str]:
        """Collect events into ``events``; return why it closed, if it did."""
        # Ask for the events.
        self._send(["REQ", sub_id, filters])
        deadline = time.monotonic() + self.timeout

        # Never keep more events than we asked for.
        limit = filters.get("limit", RELAY_MAX_EVENTS)
        while True:
            message = self._recv(deadline)
            if len(message) < 2 or message[1] != sub_id:
                # Not about our subscription.
                continue

            if (
                message[0] == "EVENT"
                and len(message) > 2
                and isinstance(message[2], dict)
            ):
                # Keep each matching event.
                events.append(message[2])
                if len(events) >= limit:
                    # We have all we asked for, so stop listening.
                    self._send(["CLOSE", sub_id])
                    return None

            elif message[0] == "EOSE":
                # Every stored event was sent, so we can stop listening.
                self._send(["CLOSE", sub_id])
                return None

            elif message[0] == "CLOSED":
                # The relay refused or ended the subscription.
                return str(message[2]) if len(message) > 2 else ""

    def _authenticate(self) -> bool:
        """Answer the relay's NIP-42 challenge; return True if accepted."""
        # Each challenge is only answered once, so a refusal is final.
        challenge, self._challenge = self._challenge, None
        if not challenge:
            return False

        # Sign a short lived event that names this relay and challenge.
        auth = self.key.sign(
            22242, "", [["relay", self.url], ["challenge", challenge]]
        )
        self._send(["AUTH", auth])
        accepted, reason = self._wait_ok(auth["id"])
        if not accepted:
            logger.debug(
                "Nostr relay %s rejected authentication: %s",
                self.url,
                reason,
            )

        return accepted

    def _wait_ok(self, event_id: str) -> tuple[bool, str]:
        """Wait for the relay's OK reply about ``event_id``."""
        deadline = time.monotonic() + self.timeout
        while True:
            # The reply is ["OK", <id>, <accepted>, <reason>].
            message = self._recv(deadline)
            if (
                len(message) > 2
                and message[0] == "OK"
                and (message[1] == event_id)
            ):
                return (
                    message[2] is True,
                    str(message[3]) if len(message) > 3 else "",
                )

    def _send(self, message: list[Any]) -> None:
        """Send one protocol message as a websocket text frame."""
        # Messages are compact JSON arrays.
        data = dumps(message, separators=(",", ":"), ensure_ascii=False)
        logger.trace("Nostr relay %s send: %s", self.url, data)
        self._write_frame(WS_TEXT, data.encode("utf-8"))

    def _recv(self, deadline: float) -> list[Any]:
        """Return the next protocol message from the relay."""
        message = bytearray()
        while True:
            # Read frames until a complete text message arrives.
            header, payload = self._read_frame(deadline)
            opcode = header & 0x0F
            if opcode == WS_PING:
                # Relays check that we are still here.
                self._write_frame(WS_PONG, payload)

            elif opcode == WS_CLOSE:
                raise AppriseSocketError("The relay closed the connection.")

            elif opcode in (WS_TEXT, WS_CONTINUATION):
                # Long messages can arrive split across several frames.
                message.extend(payload)
                if len(message) > WS_MAX_MESSAGE:
                    raise AppriseSocketError(
                        "Relay sent an oversized message."
                    )

                if header & 0x80:
                    break

        logger.trace("Nostr relay %s recv: %s", self.url, message)
        try:
            data = loads(message.decode("utf-8"))

        except (RecursionError, ValueError):
            # Something that is not JSON is simply ignored.
            return []

        if not isinstance(data, list) or not data:
            # Every protocol message is a non-empty JSON array.
            return []

        if data[0] == "AUTH" and len(data) > 1:
            # Remember the challenge in case we need to log in later.
            self._challenge = str(data[1])

        elif data[0] == "NOTICE":
            # Notices are human readable messages from the relay.
            logger.debug("Nostr relay %s notice: %s", self.url, data[1:])

        return data

    def _read_frame(self, deadline: float) -> tuple[int, bytes]:
        """Return the first header byte and payload of the next frame."""
        while True:
            # The second byte holds the payload length, or says that a
            # longer 2 or 8 byte length follows it.
            buf = self._buffer
            length = buf[1] & 0x7F if len(buf) >= 2 else 0
            offset = {126: 4, 127: 10}.get(length, 2)
            if len(buf) >= offset:
                if offset > 2:
                    length = int.from_bytes(buf[2:offset], "big")

                # Refuse an oversized frame before waiting for all of it.
                if length > WS_MAX_MESSAGE:
                    raise AppriseSocketError("Relay sent an oversized frame.")

                if len(buf) >= offset + length:
                    # The whole frame has arrived.
                    header = buf[0]
                    payload = bytes(buf[offset : offset + length])
                    del buf[: offset + length]
                    return (header, payload)

            # Wait for more data.
            self._fill(deadline)

    def _write_frame(self, opcode: int, payload: bytes) -> None:
        """Send one masked websocket frame."""
        # Mark this as the final frame of its message.
        header = bytearray([0x80 | opcode])

        # Client frames are always masked (0x80) and give their length.
        size = len(payload)
        if size < 126:
            header.append(0x80 | size)

        elif size < 65536:
            header.append(0x80 | 126)
            header += size.to_bytes(2, "big")

        else:
            header.append(0x80 | 127)
            header += size.to_bytes(8, "big")

        # XOR the payload with a random 4 byte mask.
        mask = os.urandom(4)
        header += mask
        repeated = (mask * (size // 4 + 1))[:size]
        masked = (
            int.from_bytes(payload, "big") ^ int.from_bytes(repeated, "big")
        ).to_bytes(size, "big")
        self.transport.write(bytes(header) + masked, timeout=self.timeout)

    def _fill(self, deadline: float) -> None:
        """Read more data from the relay into our buffer."""
        # Give up once we have waited long enough.
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise AppriseSocketError("Timed out waiting for the relay.")

        self._buffer.extend(
            self.transport.read(65536, blocking=True, timeout=remaining)
        )
