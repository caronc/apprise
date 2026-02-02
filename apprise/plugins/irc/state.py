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

"""IRC State Machine.

This is intentionally small: it focuses on registration, nickname collision
handling, join completion, and keeping the connection alive (PING/PONG).
"""

from __future__ import annotations

from dataclasses import field
from enum import Enum, auto
from typing import Optional

from ...compat import dataclass_compat as dataclass
from .protocol import IRCMessage, extract_welcome_nick


class IRCState(Enum):
    DISCONNECTED = auto()
    REGISTERING = auto()
    READY = auto()
    JOINING = auto()
    QUITTING = auto()
    ERROR = auto()


class IRCActionKind(Enum):
    SEND = auto()
    FAIL = auto()
    NOOP = auto()


@dataclass(frozen=True, slots=True)
class IRCAction:
    kind: IRCActionKind
    line: Optional[str] = None
    reason: Optional[str] = None


@dataclass(slots=True)
class IRCContext:
    desired_nick: str
    accepted_nick: str
    fullname: str
    password: Optional[str] = None
    registered: bool = False
    motd_done: bool = False
    joined: set[str] = field(default_factory=set)
    last_error: Optional[str] = None


def _err(msg: IRCMessage) -> str:
    if msg.trailing:
        return msg.trailing
    return " ".join(msg.params) if msg.params else "IRC error"


REGISTER_ERRORS = {
    464: "Password incorrect",
    465: "Banned from server",
    468: "Only registered users allowed",
}

JOIN_ERRORS = {
    403: "No such channel",
    471: "Channel is full",
    473: "Invite only channel",
    474: "Banned from channel",
    475: "Bad channel key",
    476: "Bad channel mask",
    477: "Need to be registered",
    489: "Cannot join channel",
}


class IRCStateMachine:
    """State machine driven by inbound IRC messages."""

    def __init__(self, ctx: IRCContext) -> None:
        self.ctx = ctx
        self.state: IRCState = IRCState.DISCONNECTED

    def start_registration(self) -> list[IRCAction]:
        self.state = IRCState.REGISTERING
        out: list[IRCAction] = []
        if self.ctx.password:
            out.append(IRCAction(
                IRCActionKind.SEND, line=f"PASS {self.ctx.password}"))
        out.append(IRCAction(
            IRCActionKind.SEND, line=f"NICK {self.ctx.desired_nick}"))
        out.append(
            IRCAction(
                IRCActionKind.SEND,
                line=f"USER {self.ctx.desired_nick} 0 * :{self.ctx.fullname}",
            ),
        )
        return out

    def on_message(self, msg: IRCMessage) -> list[IRCAction]:
        if self.state in (IRCState.ERROR, IRCState.QUITTING):
            return []

        actions: list[IRCAction] = []
        n = msg.numeric

        if self.state == IRCState.REGISTERING:
            if n in REGISTER_ERRORS:
                self.ctx.last_error = f"{REGISTER_ERRORS[n]}: {_err(msg)}"
                self.state = IRCState.ERROR
                return [IRCAction(
                    IRCActionKind.FAIL, reason=self.ctx.last_error)]

            if n in (432, 433):
                actions.append(IRCAction(
                    IRCActionKind.SEND, line=f"NICK {self.ctx.desired_nick}"))
                return actions

            if n == 1:
                nick = extract_welcome_nick(msg)
                if nick:
                    self.ctx.accepted_nick = nick
                self.ctx.registered = True
                self.state = IRCState.READY
                return actions

            if n in (376, 422):
                self.ctx.motd_done = True
                if self.ctx.registered:
                    self.state = IRCState.READY
                return actions

        if self.state == IRCState.JOINING:
            if n in JOIN_ERRORS:
                self.ctx.last_error = f"{JOIN_ERRORS[n]}: {_err(msg)}"
                self.state = IRCState.ERROR
                return [IRCAction(
                    IRCActionKind.FAIL, reason=self.ctx.last_error)]

            if n == 443 and len(msg.params) >= 2:
                chan = msg.params[1]
                self.ctx.joined.add(chan)
                self.state = IRCState.READY
                return actions

            if n == 366 and len(msg.params) >= 2:
                chan = msg.params[1]
                self.ctx.joined.add(chan)
                self.state = IRCState.READY
                return actions

            if msg.command.upper() == "JOIN":
                chan = msg.trailing or (msg.params[0] if msg.params else "")
                if chan:
                    self.ctx.joined.add(chan)
                    self.state = IRCState.READY
                return actions

        return actions

    def request_join(
            self, channel: str, key: Optional[str] = None) -> list[IRCAction]:
        self.state = IRCState.JOINING

        if key:
            return [IRCAction(
                IRCActionKind.SEND, line=f"JOIN {channel} {key}")]
        return [IRCAction(IRCActionKind.SEND, line=f"JOIN {channel}")]

    def request_quit(self, message: str) -> list[IRCAction]:
        self.state = IRCState.QUITTING
        return [IRCAction(IRCActionKind.SEND, line=f"QUIT :{message}")]
