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

"""IRC templates used to auto-apply defaults based on known networks.

This mirrors the email template strategy, but is intentionally minimal.
Templates only apply defaults when the user has not explicitly specified the
value in their URL.

Each entry is a tuple of:
  (label, compiled_regex, defaults)

Supported defaults:
  - secure: bool
  - port: int
  - mode: str  (server|nickserv|none)
"""

from __future__ import annotations

import re

from .protocol import IRCAuthMode

IRC_TEMPLATES = (
    # SynIRC: NickServ common, TLS default 6697
    (
        "SynIRC",
        re.compile(r"^.+\.synirc\.net$", re.I),
        {
            "secure": True,
            "port": 6697,
            "mode": IRCAuthMode.NICKSERV,
        },
    ),

    # Libera.Chat: TLS default 6697, NickServ common (SASL also common but
    # not implemented here)
    (
        "Libera.Chat",
        re.compile(r"^.+\.libera\.chat$", re.I),
        {
            "secure": True,
            "port": 6697,
            "mode": IRCAuthMode.NICKSERV,
        },
    ),

    # EFnet: traditionally plain 6667, auth varies widely
    (
        "EFnet",
        re.compile(r"^.+\.efnet\.org$", re.I),
        {
            "secure": False,
            "port": 6667,
            "mode": IRCAuthMode.SERVER,
        },
    ),
)
