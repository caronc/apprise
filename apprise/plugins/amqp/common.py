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


"""Shared AMQP configuration."""

from __future__ import annotations

from typing import Optional

from ...common import NotifyFormat
from ...compat.py39 import dataclass_compat as dataclass
from ...exception import AppriseException


class AMQPVersion:
    """The AMQP protocol versions a notification can be published with."""

    # AMQP 0-9-1 is what most brokers (such as RabbitMQ) speak by default
    V091 = "0.9.1"

    # AMQP 1.0 is the OASIS standard and a very different protocol
    V10 = "1.0"


# All of our supported versions, in the order they are preferred
AMQP_VERSIONS = (
    AMQPVersion.V091,
    AMQPVersion.V10,
)

# Accept common spellings by matching only the version digits
AMQP_VERSION_MAP = {
    "0": AMQPVersion.V091,
    "09": AMQPVersion.V091,
    "091": AMQPVersion.V091,
    "1": AMQPVersion.V10,
    "10": AMQPVersion.V10,
}

# Options that select a version when ?version= is omitted
AMQP_VERSION_OPTIONS = {
    "exchange": AMQPVersion.V091,
    "mandatory": AMQPVersion.V091,
}

# Content types used to label each supported body format
AMQP_CONTENT_TYPES = {
    NotifyFormat.TEXT: "text/plain; charset=utf-8",
    NotifyFormat.MARKDOWN: "text/markdown; charset=utf-8",
    NotifyFormat.HTML: "text/html; charset=utf-8",
}

# Maximum byte length of AMQP 0-9-1 short strings
AMQP_SHORTSTR_MAX = 255


class AMQPError(AppriseException):
    """Raised by an adapter when it cannot connect or publish."""


@dataclass(frozen=True, slots=True)
class AMQPConfig:
    """How to reach and log into the AMQP broker."""

    # Where the broker lives, and whether TLS is used to reach it
    host: str
    port: int
    secure: bool = False
    verify_certificate: bool = True

    # Our login; no user means the protocol's default/anonymous login
    user: Optional[str] = None
    password: Optional[str] = None

    # The virtual host to use; None leaves it to the broker
    vhost: Optional[str] = None

    # How long to wait to connect, and then for each reply (seconds)
    connect_timeout: float = 4.0
    read_timeout: float = 4.0

    # AMQP 0-9-1 exchange and unroutable-message handling
    exchange: str = ""
    mandatory: bool = True


@dataclass(frozen=True, slots=True)
class AMQPMessage:
    """One message, built once and published to every target."""

    # The encoded body and how to read it
    body: bytes
    content_type: str

    # Who sent it and when (seconds since the epoch)
    app_id: str
    timestamp: int

    # Storage, priority, and queue expiry in milliseconds
    persistent: bool = True
    priority: Optional[int] = None
    ttl: Optional[int] = None

    # Extra application headers to attach
    headers: Optional[dict[str, str]] = None
