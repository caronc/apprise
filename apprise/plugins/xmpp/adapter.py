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

"""A minimal, self-contained Slixmpp adapter.

This module provides a wrapper to Slixmpp for Apprise
"""

from __future__ import annotations

import contextlib
import logging
import ssl
import threading
from typing import Callable, Optional

import certifi

from ...compat import dataclass_compat as dataclass

# Default our global support flag
SLIXMPP_SUPPORT_AVAILABLE = False

try:
    import asyncio

    import slixmpp

    SLIXMPP_SUPPORT_AVAILABLE = True

except ImportError:  # pragma: no cover
    slixmpp = None  # type: ignore[assignment]
    asyncio = None  # type: ignore[assignment]


@dataclass(frozen=True, slots=True)
class XMPPConfig:
    """Connection configuration."""

    host: str
    port: int
    jid: str
    password: str
    secure: bool = False
    verify_certificate: bool = True


# ---------------------------------------------------------------------------
# Logging Bridge
# ---------------------------------------------------------------------------

_LOG_BRIDGE_LOCK = threading.Lock()
_LOG_BRIDGED = False


def bridge_slixmpp_logging() -> None:
    """Bridge Slixmpp logging into Apprise logging handlers.

    This is intentionally idempotent to prevent handler duplication when many
    notifications are sent within the same process.
    """
    global _LOG_BRIDGED

    if _LOG_BRIDGED:
        return

    with _LOG_BRIDGE_LOCK:
        if _LOG_BRIDGED:
            return

        apprise_logger = logging.getLogger("apprise")
        slix_logger = logging.getLogger("slixmpp")

        existing = {id(h) for h in slix_logger.handlers}
        for handler in apprise_logger.handlers:
            if id(handler) not in existing:
                slix_logger.addHandler(handler)
                existing.add(id(handler))

        slix_logger.setLevel(apprise_logger.getEffectiveLevel())

        # Prevent duplicates via propagation chains.
        slix_logger.propagate = False

        _LOG_BRIDGED = True


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------


class SlixmppAdapter:
    """Send a message to one or more targets, then disconnect."""

    # Flag to control if we are enabled or not
    # effectively.. .is the dependent slixmpp library available to us
    # or not
    _enabled = SLIXMPP_SUPPORT_AVAILABLE

    def __init__(
        self,
        config: XMPPConfig,
        targets: list[str],
        subject: str,
        body: str,
        timeout: float = 30.0,
        before_message: Optional[Callable[[], None]] = None,
    ) -> None:
        self.config = config
        self.targets = targets
        self.subject = subject
        self.body = body
        self.timeout = max(5.0, float(timeout))
        self.before_message = before_message

        self.logger = logging.getLogger("apprise.xmpp")

        bridge_slixmpp_logging()

    @staticmethod
    def _ssl_context(verify_certificate: bool) -> ssl.SSLContext:
        ctx = ssl.create_default_context(cafile=certifi.where())
        if not verify_certificate:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        return ctx

    @staticmethod
    def _cancel_pending(loop: asyncio.AbstractEventLoop) -> None:
        pending = [t for t in asyncio.all_tasks(loop) if not t.done()]
        for task in pending:
            task.cancel()
        if pending:
            loop.run_until_complete(
                asyncio.gather(*pending, return_exceptions=True)
            )

    def process(self) -> bool:
        """Send the message, always returning within timeout."""
        done = threading.Event()
        result: list[Optional[bool]] = [None]

        if not self._enabled:
            # We are not turned on
            return False

        shared: dict[str, object] = {"loop": None, "client": None}

        def runner() -> None:
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                shared["loop"] = loop

                class _Client(slixmpp.ClientXMPP):  # type: ignore[misc]
                    def __init__(
                        self,
                        jid: str,
                        password: str,
                        targets: list[str],
                        subject: str,
                        body: str,
                        before_message: Optional[Callable[[], None]],
                        roster_timeout: float,
                    ) -> None:
                        super().__init__(jid, password)
                        self._targets = targets
                        self._subject = subject
                        self._body = body
                        self._before_message = before_message
                        self._roster_timeout = roster_timeout

                        self.add_event_handler(
                            "session_start", self._session_start)
                        self.add_event_handler(
                            "failed_auth", self._failed_auth)

                        # Keep behaviour predictable and close quickly.
                        self.auto_reconnect = False

                    async def _session_start(
                            self, *args: object, **kwargs: object) -> None:
                        try:
                            self.send_presence()

                            with contextlib.suppress(Exception):
                                await asyncio.wait_for(
                                    self.get_roster(),
                                    timeout=self._roster_timeout,
                                )

                            for target in self._targets:
                                if self._before_message:
                                    self._before_message()

                                self.send_message(
                                    mto=target,
                                    msubject=self._subject,
                                    mbody=self._body,
                                    mtype="chat",
                                )

                        finally:
                            self.disconnect()

                    def _failed_auth(
                            self, *args: object, **kwargs: object) -> None:
                        self.disconnect()

                targets = (
                    list(self.targets) if self.targets else [self.config.jid])
                roster_timeout = max(2.0, min(10.0, self.timeout / 3.0))

                client = _Client(
                    self.config.jid,
                    self.config.password,
                    targets,
                    self.subject,
                    self.body,
                    self.before_message,
                    roster_timeout,
                )
                shared["client"] = client

                ssl_ctx = (
                    self._ssl_context(self.config.verify_certificate)
                    if self.config.secure
                    else None
                )

                # connect() returns False if connection could not be started.
                if not client.connect(
                    address=(self.config.host, self.config.port),
                    use_ssl=self.config.secure,
                    use_tls=False,
                    ssl_context=ssl_ctx,
                ):
                    self.logger.warning(
                        "XMPP connection could not be established.")
                    result[0] = False
                    return

                # process() blocks until disconnected.
                client.process(forever=False)

                # If we got this far, we consider it an OK send attempt.
                # Slixmpp does not provide an explicit delivery receipt.
                result[0] = True

            except Exception as e:  # pragma: no cover
                self.logger.warning("XMPP send failed.")
                self.logger.debug("XMPP Exception: %s", e)
                result[0] = False

            finally:
                loop_obj = shared.get("loop")
                if loop_obj is not None:
                    loop = loop_obj  # type: ignore[assignment]
                    with contextlib.suppress(Exception):
                        self._cancel_pending(loop)
                    with contextlib.suppress(Exception):
                        loop.stop()
                    with contextlib.suppress(Exception):
                        loop.close()

                done.set()

        t = threading.Thread(target=runner, name="apprise-xmpp", daemon=True)
        t.start()

        if not done.wait(timeout=self.timeout):
            self.logger.warning(
                "XMPP send timed out after %.2fs.", self.timeout)
            result[0] = False

            loop_obj = shared.get("loop")
            client_obj = shared.get("client")

            if loop_obj is not None:
                loop = loop_obj  # type: ignore[assignment]
                try:
                    if client_obj is not None:
                        client = client_obj  # type: ignore[assignment]
                        loop.call_soon_threadsafe(client.disconnect)
                except Exception:
                    pass

                with contextlib.suppress(Exception):
                    loop.call_soon_threadsafe(loop.stop)

            t.join(timeout=0.25)

        return bool(result[0])
