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

"""IRC protocol parsing helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


class IRCAuthMode:
    """IRC authentication mode."""

    # No authentication
    NONE = "none"

    # PASS <password> during registration
    SERVER = "server"

    # NickServ IDENTIFY after registration
    NICKSERV = "nickserv"

    # ZNC bouncer mode - connects to bouncer only - presumes registration
    ZNC = "znc"

IRC_AUTH_MODES = (
    IRCAuthMode.ZNC,
    IRCAuthMode.SERVER,
    IRCAuthMode.NICKSERV,
    IRCAuthMode.NONE,
)


@dataclass(frozen=True, slots=True)
class IRCMessage:
    """A parsed IRC line."""

    raw: str
    prefix: Optional[str]
    command: str
    params: tuple[str, ...]
    trailing: Optional[str]

    @property
    def numeric(self) -> Optional[int]:
        if self.command.isdigit() and len(self.command) == 3:
            return int(self.command)
        return None


def parse_irc_line(line: str) -> IRCMessage:
    """Parse an IRC line per RFC 1459-ish rules (sufficient for numerics)."""
    raw = line.rstrip("\r\n")
    prefix: Optional[str] = None
    trailing: Optional[str] = None

    s = raw
    if s.startswith(":"):
        parts = s[1:].split(" ", 1)
        prefix = parts[0] if parts else None
        s = parts[1] if len(parts) > 1 else ""

    if " :" in s:
        before, after = s.split(" :", 1)
        trailing = after
        s = before

    s = s.strip()
    if not s:
        return IRCMessage(
            raw=raw, prefix=prefix, command="", params=(), trailing=trailing)

    bits = s.split()
    command = bits[0]
    params = tuple(bits[1:]) if len(bits) > 1 else ()
    return IRCMessage(
        raw=raw, prefix=prefix, command=command, params=params,
        trailing=trailing)


def is_ping(msg: IRCMessage) -> bool:
    return msg.command.upper() == "PING"


def ping_payload(msg: IRCMessage) -> str:
    if msg.trailing is not None:
        return msg.trailing
    return msg.params[0] if msg.params else ""


def extract_welcome_nick(msg: IRCMessage) -> Optional[str]:
    """Extract the nickname from 001 welcome message."""
    if msg.numeric != 1:
        return None
    if msg.params:
        return msg.params[0]
    return None


def normalise_channel(name: str) -> str:
    name = name.strip()
    if not name:
        return name
    return name if name.startswith("#") else f"#{name}"
