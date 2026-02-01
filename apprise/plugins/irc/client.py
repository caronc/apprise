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

"""A minimal IRC client for notification delivery."""

from __future__ import annotations

from collections import deque
import logging
import random
import string
import time
from typing import Callable, Optional, Union

from ...logger import logger
from ...utils.socket import AppriseSocketError, SocketTransport
from .protocol import (
    IRCAuthMode,
    is_ping,
    normalise_channel,
    parse_irc_line,
    ping_payload,
)
from .state import IRCActionKind, IRCContext, IRCStateMachine

NickGenerator = Callable[[str, int, int], str]


class IRCClient:
    """Socket-driven IRC Client."""

    # IRC Default Ports
    default_insecure_port = 6667
    default_secure_port = 6697

    # When we're blocking and awaiting the server, we increase the
    # frequency to poll for an update.
    pump_interval = 0.75

    # EFNet only allows nicknames to be 9 characters, default to that.
    nickname_max_length = 9

    # How many times we retry on 432/433 before failing.
    nickname_collision_max = 3

    def __init__(
        self,
        host: str,
        nickname: str,
        fullname: str,
        port: Optional[int] = None,
        secure: bool = False,
        verify: bool = True,
        timeout: Optional[float] = None,
        password: Optional[str] = None,
        auth_mode: str = IRCAuthMode.SERVER,
        nick_generator: Optional[NickGenerator] = None,
        nick_length: Optional[int] = None,
    ) -> None:

        # Detect port if not set
        port = port if port is not None else (
            self.default_secure_port
            if secure else self.default_insecure_port
        )

        self.transport = SocketTransport(
            host,
            port,
            secure=secure,
            verify=verify,
            timeout=timeout,
        )

        self._nick_generator = nick_generator
        self._nick_length = (
            int(nick_length)
            if nick_length else int(self.nickname_max_length)
        )
        self._nick_collision = 0

        self.auth_mode = auth_mode

        ctx = IRCContext(
            desired_nick=nickname,
            accepted_nick=nickname,
            fullname=fullname,
            password=password,
        )
        self.sm = IRCStateMachine(ctx)
        self._out_queue = deque()  # type: Deque[bytes]
        self._inbuf = bytearray()

    @property
    def nickname(self) -> str:
        """Returns the accepted nickname."""
        return self.sm.ctx.accepted_nick

    def connect(self) -> None:
        self.transport.connect()

    def close(self) -> None:
        self.transport.close()

    def _queue(self, line: str) -> None:
        """
        Queues message for outbound delivery to the IRC Server
        """
        payload = (line + "\r\n").encode("utf-8", errors="replace")
        self._out_queue.append(payload)

    def _write(self, line: Union[str, bytes], deadline: float) -> None:
        """Write content directly to IRC."""
        remaining = max(0.0, deadline - time.monotonic())
        if remaining <= 0.0:
            raise TimeoutError("timeout while writing IRC commands")

        payload = (line + "\r\n").encode("utf-8", errors="replace") \
            if isinstance(line, str) else line
        self.transport.write(payload, flush=True, timeout=remaining)
        if logger.isEnabledFor(logging.TRACE):
            logger.trace(
                "IRC write: %s", payload.rstrip(b"\r")
                .decode("utf-8", errors="replace").rstrip())

    def _flush(self, deadline: float) -> None:
        """Flush all queued information to the IRC server."""
        while self._out_queue:
            self._write(self._out_queue[0], deadline=deadline)
            self._out_queue.popleft()

    def _read(self, deadline: float) -> Optional[str]:
        """
        Read incoming content from IRC Server
        """
        while True:
            if b"\n" in self._inbuf:
                line, _, rest = self._inbuf.partition(b"\n")
                self._inbuf = bytearray(rest)
                response = line.rstrip(b"\r").decode("utf-8", errors="replace")
                logger.trace("IRC read: %s", response)
                return response

            remaining = max(0.0, deadline - time.monotonic())
            if remaining <= 0.0:
                logger.trace(
                    "IRC read timeout - deadline=%.2fs", deadline)
                return None

            chunk = self.transport.read(4096, blocking=True, timeout=remaining)
            if not chunk:
                return None
            self._inbuf.extend(chunk)

    def _nickname_collision_handler(self, prefix: str) -> str:
        if not self._nick_generator:
            raise AppriseSocketError("Nickname collision and no generator")

        if self._nick_collision >= int(self.nickname_collision_max):
            raise AppriseSocketError("Nickname is already in use")

        self._nick_collision += 1
        self.sm.ctx.desired_nick = self._nick_generator(
            prefix,
            self._nick_length,
            self._nick_collision,
        )
        return self.sm.ctx.desired_nick

    def _tick(self, deadline: float) -> float:
        remaining = max(0.0, deadline - time.monotonic())
        if remaining <= 0.0:
            return deadline
        return time.monotonic() + min(self.pump_interval, remaining)

    def _handshake(self, deadline: float, prefix: str) -> None:
        while True:
            line = self._read(deadline=deadline)
            if not line:
                # We've completed
                return

            msg = parse_irc_line(line)  # type: IRCMessage

            if is_ping(msg):
                self._write(f"PONG :{ping_payload(msg)}", deadline=deadline)
                continue

            if msg.numeric in (432, 433):
                new_nick = self._nickname_collision_handler(prefix)
                # Send immediately, do not queue.
                self._write("NICK {}".format(new_nick), deadline=deadline)
                continue

            for act in self.sm.on_message(msg):
                if act.kind == IRCActionKind.FAIL and act.reason:
                    raise AppriseSocketError(act.reason)
                if act.kind == IRCActionKind.SEND and act.line:
                    self._write(act.line, deadline=deadline)

    def register(self, timeout: float, prefix: str) -> None:
        """Register with the IRC server, and optionally NickServ identify.

        - SERVER mode: sends PASS during registration (if password provided)
        - NICKSERV mode: does not send PASS, performs NickServ IDENTIFY after
          registration completes
        - NONE mode: no authentication is performed
        """
        tl_start = time.time()
        deadline = time.monotonic() + float(timeout)

        # PASS during registration is only used for SERVER and ZNC.
        if self.auth_mode not in (IRCAuthMode.SERVER, IRCAuthMode.ZNC):
            self.sm.ctx.password = None

        logger.trace("IRC registration started")
        for act in self.sm.start_registration():
            if act.kind == IRCActionKind.SEND and act.line:
                self._queue(act.line)

        while time.monotonic() < deadline and not self.sm.ctx.registered:
            self._flush(deadline)
            self._handshake(self._tick(deadline), prefix=prefix)

        if not self.sm.ctx.registered:
            logger.trace(
                "IRC registration timeout - %.6fs elapsed",
                time.time() - tl_start,
            )
            raise TimeoutError("IRC registration timeout")

        logger.trace(
            "IRC registration completed in %.6fs",
            time.time() - tl_start,
        )

        # NickServ identify is only performed after we are registered, and only
        # when explicitly requested via auth_mode.
        if self.auth_mode == IRCAuthMode.NICKSERV:
            self.identify(timeout=timeout)

    def check_connection(self, timeout: float) -> bool:
        """Verify we can talk to the server by completing a PING/PONG."""
        deadline = time.monotonic() + float(timeout)
        token = "apprise"

        # Send a ping and wait until we observe a PONG carrying our token.
        self._write(f"PING :{token}", deadline=deadline)

        while time.monotonic() < deadline:
            line = self._read(deadline=deadline)
            if not line:
                continue

            msg = parse_irc_line(line)
            if msg.command.upper() == "PONG":
                # Some IRC servers/bouncers do not echo our token back reliably.
                # Observing any PONG after issuing our PING is sufficient.
                return True

        return False

    def join(
        self,
        channel: str,
        timeout: float,
        prefix: str,
        key: Optional[str] = None,
    ) -> None:

        chan = normalise_channel(channel)
        if chan in self.sm.ctx.joined:
            # Nothing to do, we are already there.
            return
        deadline = time.monotonic() + float(timeout)

        for act in self.sm.request_join(chan, key=key):
            if act.kind == IRCActionKind.SEND and act.line:
                self._queue(act.line)

        while time.monotonic() < deadline and chan not in self.sm.ctx.joined:
            self._flush(deadline)
            self._handshake(self._tick(deadline), prefix=prefix)

        if chan not in self.sm.ctx.joined:
            logger.debug("IRC join confirmation not observed for %s", chan)

    def privmsg(self, target: str, message: str, timeout: float) -> None:
        """Handle the sending of private messages."""
        deadline = time.monotonic() + float(timeout)
        self._queue(f"PRIVMSG {target} :{message}")
        self._flush(deadline)
        self._handshake(self._tick(deadline), prefix="")

    def identify(self, timeout: float) -> None:
        """Identify with NickServ after registration."""
        if not self.sm.ctx.password:
            return

        if self.auth_mode != IRCAuthMode.NICKSERV:
            return

        deadline = time.monotonic() + float(timeout)
        self._queue(
            "PRIVMSG NickServ :IDENTIFY {}".format(
                self.sm.ctx.password
            )
        )
        self._flush(deadline)
        self._handshake(
            self._tick(deadline),
            prefix="",
        )

    def quit(self, message: str, timeout: float) -> None:
        deadline = time.monotonic() + float(timeout)
        for act in self.sm.request_quit(message):
            if act.kind == IRCActionKind.SEND and act.line:
                self._queue(act.line)
        self._flush(deadline)

    @staticmethod
    def nick_generation(
            prefix: str, length: Optional[int] = None,
            collision: int = 0) -> str:
        """Generate a nickname suitable for retry after collision."""
        if length is None:
            # Default Assignment
            length = IRCClient.nickname_max_length

        base = "{}".format(prefix)[:length-3].strip().lower()
        charset = string.ascii_lowercase + string.digits + "_"
        suffix = "".join(random.choice(charset) for _ in range(max(1, length)))
        nick = "{}{}".format(base, suffix)
        if collision:
            nick = "{}{}".format(nick[: max(0, length - 1)], collision % 10)
        return nick[:length]
