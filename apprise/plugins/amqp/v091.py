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


"""AMQP 0-9-1 publishing with pika.

Pika documentation: https://pika.readthedocs.io/
Publishes use broker confirmation: https://www.rabbitmq.com/docs/confirms
"""

from __future__ import annotations

import math
import ssl
from typing import Any, Optional

import certifi

from .common import AMQPConfig, AMQPError, AMQPMessage

# Default our global support flag
PIKA_SUPPORT_AVAILABLE = False

try:
    import pika
    from pika.exceptions import AMQPError as PikaError

    # We're good to go!
    PIKA_SUPPORT_AVAILABLE = True

except ImportError:
    # AMQP 0-9-1 cannot be used without pika
    pika = None
    PikaError = AMQPError


# Everything that can go wrong while talking to the broker.  OSError covers
# socket and TLS failures, while ValueError and TypeError cover values pika
# refuses to encode.
PIKA_FAILURES = (PikaError, OSError, ValueError, TypeError)


class AMQP091Adapter:
    """Publish messages over AMQP 0-9-1."""

    # Only usable when pika could be imported
    enabled = PIKA_SUPPORT_AVAILABLE

    # The package to install to use this version
    package = "pika"

    def __init__(self, config: AMQPConfig) -> None:
        """Prepare an adapter that is not connected yet."""
        # How to reach the broker
        self.config = config

        # Our connection, and the channel opened on it when publishing
        self.connection: Optional[Any] = None
        self.channel: Optional[Any] = None

    def connect(self) -> None:
        """Connect and log into the broker, or raise ``AMQPError``."""
        cfg = self.config

        try:
            # Prepare TLS when amqps:// is used
            ssl_options = None
            if cfg.secure:
                context = ssl.create_default_context(cafile=certifi.where())
                if not cfg.verify_certificate:
                    # Accept self-signed or otherwise unverified servers
                    context.check_hostname = False
                    context.verify_mode = ssl.CERT_NONE

                ssl_options = pika.SSLOptions(
                    context, server_hostname=cfg.host
                )

            # Prepare our connection details
            params = {
                "host": cfg.host,
                "port": cfg.port,
                "virtual_host": cfg.vhost or "/",
                "ssl_options": ssl_options,
                # Fail fast; Apprise already handles retries itself
                "connection_attempts": 1,
                # Bound the time spent on the socket and the login
                "socket_timeout": cfg.connect_timeout,
                "stack_timeout": cfg.connect_timeout + cfg.read_timeout,
                # A broker that is low on memory or disk blocks publishers.
                # Give up instead of waiting forever.
                "blocked_connection_timeout": cfg.read_timeout,
                # Heartbeats are how pika notices a broker that stopped
                # answering.  The broker's own proposal is often 60 seconds,
                # which can stall a send for minutes, so ask for one close
                # to our read timeout instead.
                "heartbeat": max(1, math.ceil(cfg.read_timeout)),
            }

            if cfg.user:
                # Otherwise pika logs in with its default guest account
                params["credentials"] = pika.PlainCredentials(
                    cfg.user, cfg.password or ""
                )

            # Establish our connection
            self.connection = pika.BlockingConnection(
                pika.ConnectionParameters(**params)
            )

        except PIKA_FAILURES as e:
            # Leave nothing half open behind us
            self.close()
            raise AMQPError(str(e) or type(e).__name__) from None

    def publish(self, target: str, message: AMQPMessage) -> None:
        """Publish ``message`` using ``target`` as the routing key."""
        cfg = self.config

        try:
            if self.channel is None or not self.channel.is_open:
                # The broker closes a channel after some errors (such as a
                # missing exchange), so open a new one when we need to.
                self.channel = self.connection.channel()

                # Have the broker confirm every message it accepts
                self.channel.confirm_delivery()

            # Publish our message and wait for the broker to confirm it.
            # A mandatory message nobody can receive raises an error.
            self.channel.basic_publish(
                exchange=cfg.exchange,
                routing_key=target,
                body=message.body,
                properties=pika.BasicProperties(
                    content_type=message.content_type,
                    # 2 asks the broker to write the message to disk
                    delivery_mode=2 if message.persistent else 1,
                    priority=message.priority,
                    # AMQP 0-9-1 carries the expiry as text (milliseconds)
                    expiration=(
                        None if message.ttl is None else str(message.ttl)
                    ),
                    timestamp=message.timestamp,
                    app_id=message.app_id,
                    headers=message.headers,
                ),
                mandatory=cfg.mandatory,
            )

        except PIKA_FAILURES as e:
            # The message was refused, or the connection was lost
            raise AMQPError(str(e) or type(e).__name__) from None

    def close(self) -> None:
        """Close our connection; this never raises."""
        # Forget our connection first so close() is safe to call twice
        connection, self.connection, self.channel = (
            self.connection,
            None,
            None,
        )

        try:
            if connection is not None and connection.is_open:
                # Let the broker know we are leaving
                connection.close()

        except Exception:
            # The connection is already broken; there is nothing to clean
            pass
