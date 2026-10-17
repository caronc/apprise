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


"""AMQP 1.0 publishing with Apache Qpid Proton.

Qpid Proton documentation: https://qpid.apache.org/proton/
A publish succeeds only after the broker accepts the message.
"""

from __future__ import annotations

import contextlib
from typing import Any, Optional

import certifi

from .common import AMQPConfig, AMQPError, AMQPMessage

# Default our global support flag
PROTON_SUPPORT_AVAILABLE = False

try:
    from proton import Endpoint, Message, ProtonException, SSLDomain
    from proton.utils import BlockingConnection

    # We're good to go!
    PROTON_SUPPORT_AVAILABLE = True

except ImportError:
    # AMQP 1.0 cannot be used without python-qpid-proton
    Endpoint = None
    Message = None
    SSLDomain = None
    BlockingConnection = None
    ProtonException = AMQPError


# Everything that can go wrong while talking to the broker.  OSError covers
# socket failures, while the rest cover values proton refuses to encode.
PROTON_FAILURES = (ProtonException, OSError, KeyError, ValueError, TypeError)


class AMQP10Adapter:
    """Publish messages over AMQP 1.0."""

    # Only usable when python-qpid-proton could be imported
    enabled = PROTON_SUPPORT_AVAILABLE

    # The package to install to use this version
    package = "python-qpid-proton"

    def __init__(self, config: AMQPConfig) -> None:
        """Prepare an adapter that is not connected yet."""
        # How to reach the broker
        self.config = config

        # Our connection once we are connected
        self.connection: Optional[Any] = None

    def connect(self) -> None:
        """Connect and log into the broker, or raise ``AMQPError``."""
        cfg = self.config

        try:
            # Prepare TLS when amqps:// is used
            ssl_domain = None
            if cfg.secure:
                ssl_domain = SSLDomain(SSLDomain.MODE_CLIENT)
                if cfg.verify_certificate:
                    # Check the server certificate and its host name
                    ssl_domain.set_trusted_ca_db(certifi.where())
                    ssl_domain.set_peer_authentication(
                        SSLDomain.VERIFY_PEER_NAME
                    )

                else:
                    # Accept self-signed or otherwise unverified servers
                    ssl_domain.set_peer_authentication(
                        SSLDomain.ANONYMOUS_PEER
                    )

            # Log in with our user when we have one; otherwise anonymously
            options = (
                {
                    "user": cfg.user,
                    "password": cfg.password or "",
                    "allowed_mechs": "PLAIN",
                }
                if cfg.user
                else {"allowed_mechs": "ANONYMOUS"}
            )

            if cfg.vhost:
                # Proton would otherwise check the TLS certificate against
                # the virtual host instead of the server we connect to
                options["virtual_host"] = cfg.vhost
                options["sni"] = cfg.host

            # Wrap IPv6 addresses in brackets so the port stays separate
            host = f"[{cfg.host}]" if ":" in cfg.host else cfg.host

            # Establish our connection.  Proton turns a 0 timeout into 60
            # seconds, so never hand it anything smaller than a tick.
            self.connection = BlockingConnection(
                "{schema}://{host}:{port}".format(
                    schema="amqps" if cfg.secure else "amqp",
                    host=host,
                    port=cfg.port,
                ),
                timeout=max(cfg.connect_timeout, 0.1),
                ssl_domain=ssl_domain,
                # Fail fast; Apprise already handles retries itself
                reconnect=False,
                **options,
            )

            # Every wait from here on is for a reply to something we sent
            self.connection.timeout = max(cfg.read_timeout, 0.1)

        except PROTON_FAILURES as e:
            # Leave nothing half open behind us
            self.close()
            raise AMQPError(str(e) or type(e).__name__) from None

    def publish(self, target: str, message: AMQPMessage) -> None:
        """Publish ``message`` to the ``target`` address."""
        try:
            # Prepare our message.  The body is sent as raw bytes so that
            # any client (including an AMQP 0-9-1 one) reads exactly the
            # text we sent.
            msg = Message(
                body=message.body,
                content_type=message.content_type,
                durable=message.persistent,
                creation_time=message.timestamp,
                properties=message.headers,
            )

            # Send the bytes as a plain data section; otherwise proton
            # wraps them in an AMQP typed value
            msg.inferred = True

            if message.priority is not None:
                # Otherwise the AMQP 1.0 default priority (4) applies
                msg.priority = message.priority

            if message.ttl is not None:
                # Proton takes the expiry in seconds
                msg.ttl = message.ttl / 1000

            # Open a link to the address we are publishing to
            sender = self.connection.create_sender(target)

            try:
                # Send our message and wait for the broker to accept it
                sender.send(msg)

            finally:
                # Release our link; the connection stays open.  Any error
                # means the broker already closed it for us.
                with contextlib.suppress(Exception):
                    sender.close()

        except PROTON_FAILURES as e:
            # The address or the message was refused, or the connection
            # was lost
            raise AMQPError(str(e) or type(e).__name__) from None

    def close(self) -> None:
        """Close our connection within our read timeout; this never raises."""
        # Forget our connection first so close() is safe to call twice
        connection, self.connection = self.connection, None
        if connection is None:
            # We never connected
            return

        # The AMQP connection proton's blocking wrapper drives
        conn = connection.conn

        with contextlib.suppress(Exception):
            # Let the broker know we are leaving, and give it until our read
            # timeout to say goodbye
            conn.close()
            connection.wait(
                lambda: not (conn.state & Endpoint.REMOTE_ACTIVE),
                timeout=max(self.config.read_timeout, 0.1),
                msg="Closing connection",
            )

        with contextlib.suppress(Exception):
            # Shut the socket ourselves.  Proton would otherwise wait forever
            # on a broker that stopped answering.
            conn.transport.close_tail()
            conn.transport.close_head()

        with contextlib.suppress(Exception):
            # Free what is left.  The goodbye was already waited for above,
            # so do not wait for it a second time.
            connection.timeout = 0.1
            connection.close()
