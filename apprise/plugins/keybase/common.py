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

"""Shared constants and validation patterns for the Keybase plugin."""

import os
import re
import sys


class KeybaseMode:
    """Tracks the operating mode for the Keybase plugin."""

    # Connect via Unix domain socket (auto-detected path).
    # This is the default mode and requires no port number.
    SOCKET = "socket"

    # Connect via HTTP to a locally running keybase service.
    # Requires host and port (e.g. localhost:3000).
    TCP = "tcp"


# All supported connection modes
KEYBASE_MODES = (
    KeybaseMode.SOCKET,
    KeybaseMode.TCP,
)

# Default connection mode
KEYBASE_DEFAULT_MODE = KeybaseMode.SOCKET

# Default host and port used when TCP mode is active
KEYBASE_DEFAULT_HOST = "localhost"
KEYBASE_DEFAULT_PORT = 3000

# Default team channel when none is specified in the target
KEYBASE_DEFAULT_CHANNEL = "general"

# Valid Keybase username:
#   lowercase letters, digits, underscores; 2-16 characters total.
#   Leading @ is stripped by the caller before matching.
IS_USER_TARGET = re.compile(r"^@(?P<name>[a-z0-9][a-z0-9_]{0,14}[a-z0-9])$")

# Valid Keybase team name (optionally followed by #channel_name):
#   - Team:    lowercase letters, digits, dots, underscores; 2-40 chars
#   - Channel: lowercase letters, digits, underscores; 2-20 chars
IS_TEAM_TARGET = re.compile(
    r"^(?P<team>[a-z0-9][a-z0-9_.]{0,38}[a-z0-9])"
    r"(?:#(?P<channel>[a-z0-9][a-z0-9_]{0,18}[a-z0-9]))?$"
)

# Ed25519 signing key seed: exactly 64 lowercase or uppercase hex characters
IS_VALID_SIGKEY = re.compile(r"^[0-9a-fA-F]{64}$")

# Socket path safety guard: the path must contain the word "keybase"
# (case-insensitive).  This prevents ?socket= from being aimed at
# unrelated system sockets such as /var/run/docker.sock or
# /run/containerd/containerd.sock.  All legitimate Keybase socket
# paths -- platform defaults and custom installs alike -- contain
# the word "keybase".
IS_KEYBASE_SOCKET_PATH = re.compile(r"(?i)keybase")


def keybase_default_socket():
    """Return the platform-default keybase service socket path."""

    # Windows: keybase exposes a named pipe
    if sys.platform == "win32":
        return r"\\.\pipe\keybase.service"

    # macOS: socket lives inside Library/Group Containers
    if sys.platform == "darwin":
        return os.path.join(
            os.path.expanduser("~"),
            "Library",
            "Group Containers",
            "keybase",
            "Library",
            "keybased.sock",
        )

    # Linux / other Unix: honour XDG_RUNTIME_DIR; fall back to /run/user
    uid = os.getuid() if hasattr(os, "getuid") else 1000
    runtime_dir = os.environ.get(
        "XDG_RUNTIME_DIR",
        "/run/user/{}".format(uid),
    )
    return os.path.join(runtime_dir, "keybase", "keybased.sock")
