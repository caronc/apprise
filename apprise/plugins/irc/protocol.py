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

"""IRC protocol parsing helpers.

This module contains *pure* helpers used by the IRC client/state machine.

Design goals:
- Be conservative: parse only what we need for reliability.
- Avoid RFC rabbit holes: implement RFC 1459-ish behaviour for numerics,
  PING/PONG, JOIN detection, and channel normalisation.
- Keep parsing side-effect free: no state mutations happen here.

Terminology refresher (IRC line shape, simplified):
    [":" <prefix> <SPACE>] <command> <params> [":" <trailing>]

Examples:
    :server.example 001 nick :Welcome to the network
    PING :123456
    :nick!user@host JOIN :#channel
    :server 366 nick #channel :End of /NAMES list.
"""

from __future__ import annotations

from typing import Optional

from ...compat import dataclass_compat as dataclass


class IRCAuthMode:
    """IRC authentication mode.

    The IRC plugin uses a small set of authentication strategies, selected
    by URL parsing logic. These values are treated as constants and are used
    by the client (connection setup) rather than by the parsing/state code.

    NONE
        No authentication.
    SERVER
        Use PASS <password> during registration.
    NICKSERV
        Authenticate after registration via NickServ IDENTIFY.
    ZNC
        Connect to a ZNC bouncer and presume registration is already handled.
        In this mode, the client generally avoids emitting registration flows.
    """

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
    """A parsed IRC line.

    raw
        The line as received (minus CRLF).
    prefix
        Optional prefix (nick/server). Examples:
            server.example
            nick!user@host
    command
        The IRC command, for example: PRIVMSG, JOIN, PING, or a numeric string.
    params
        A tuple of middle parameters (space separated).
    trailing
        The trailing parameter (after ' :'), which may contain spaces.

    Notes on numerics:
        Numeric replies are three digits as a string. This helper provides
        a .numeric property that returns an int, or None when not numeric.
    """

    raw: str
    prefix: Optional[str]
    command: str
    params: tuple[str, ...]
    trailing: Optional[str]

    @property
    def numeric(self) -> Optional[int]:
        """Return numeric reply code as int when command is a 3-digit
        string."""
        if self.command.isdigit() and len(self.command) == 3:
            return int(self.command)
        return None


def parse_irc_line(line: str) -> IRCMessage:
    """Parse an IRC line into its components.

    This is intentionally tolerant and small, but sufficient for:
    - detecting PINGs (command == 'PING')
    - reading common numeric replies (001, 376/422, 366, error codes)
    - identifying JOIN completion
    - extracting the welcome nick from 001

    The parser follows the usual IRC split rules:
    - prefix is optional and begins with ':' at the start of the line
    - trailing is optional and begins with ' :' and consumes the remainder
    - params are any remaining space-delimited tokens after command
    """
    raw = line.rstrip("\r\n")
    prefix: Optional[str] = None
    trailing: Optional[str] = None

    s = raw

    # Prefix is only present at the beginning of the message.
    if s.startswith(":"):
        parts = s[1:].split(" ", 1)
        prefix = parts[0] if parts else None
        s = parts[1] if len(parts) > 1 else ""

    # Trailing is indicated by " :"; it may contain spaces and consumes the
    # rest.
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
    """True when message is a PING request."""
    return msg.command.upper() == "PING"


def ping_payload(msg: IRCMessage) -> str:
    """Extract the payload to use when responding to a PING."""
    if msg.trailing is not None:
        return msg.trailing
    return msg.params[0] if msg.params else ""


def extract_welcome_nick(msg: IRCMessage) -> Optional[str]:
    """Extract the nickname from the numeric 001 (welcome) message."""
    if msg.numeric != 1:
        return None
    if msg.params:
        return msg.params[0]
    return None


def normalise_channel(name: str) -> str:
    """Normalise a channel name to include '#'."""
    name = name.strip()
    if not name:
        return name
    return name if name.startswith("#") else f"#{name}"
