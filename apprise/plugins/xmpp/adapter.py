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

Design goals:
- Do not touch the caller's event loop.
- Connect, send, disconnect.
- Clean up pending tasks so the loop can be closed safely.

This module intentionally avoids exposing XEP/plugin toggles through the
Apprise URL. Keep the surface area small, and expand only when needed.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
import logging
import ssl
import threading
from typing import Optional

import certifi

# Default our global support flag
SLIXMPP_SUPPORT_AVAILABLE = False

try:
    import asyncio

    import slixmpp

    SLIXMPP_SUPPORT_AVAILABLE = True

except ImportError:  # pragma: no cover
    # slixmpp is optional; Apprise can still run without it.
    slixmpp = None  # type: ignore[assignment]
    asyncio = None  # type: ignore[assignment]


@dataclass
class XMPPConfig:
    """Configuration used by the adapter."""

    jid: str
    password: str
    host: str
    port: int
    secure: bool
    verify_certificate: bool


class SlixmppSendOnceAdapter:
    """Connects, sends a message (to one or more JIDs), and disconnects."""

    # This entry allows unit-testing in environments that do not have slixmpp.
    _enabled = SLIXMPP_SUPPORT_AVAILABLE

    def __init__(
        self,
        config: XMPPConfig,
        targets: list[str],
        body: str,
        subject: str,
        timeout: float,
        before_message: Optional[callable] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.config = config
        self.targets = targets
        self.body = body
        self.subject = subject
        self.timeout = float(timeout) if timeout else 30.0
        self.before_message = before_message
        self.logger = logger or logging.getLogger(__name__)

        # Use the Apprise log handlers for configuring the slixmpp logger.
        apprise_logger = logging.getLogger("apprise")
        sli_logger = logging.getLogger("slixmpp")
        for handler in apprise_logger.handlers:
            sli_logger.addHandler(handler)
        sli_logger.setLevel(apprise_logger.level)

        self._ok = False

    @staticmethod
    def _ssl_context(verify: bool) -> ssl.SSLContext:
        ctx = ssl.create_default_context(cafile=certifi.where())
        if not verify:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        return ctx

    @staticmethod
    def _cancel_pending(loop: asyncio.AbstractEventLoop) -> None:
        """Cancel and drain pending tasks on the loop."""
        pending = [t for t in asyncio.all_tasks(loop) if not t.done()]
        if not pending:
            return

        for task in pending:
            task.cancel()

        # Drain cancellations; ignore exceptions.
        loop.run_until_complete(
            asyncio.gather(*pending, return_exceptions=True)
        )

    def process(self) -> bool:
        """Run the send operation in an isolated thread and event loop."""

        if not self._enabled:
            return False

        result: list[bool] = [False]
        done = threading.Event()

        def runner() -> None:
            loop = asyncio.new_event_loop()
            try:
                asyncio.set_event_loop(loop)

                class _Client(slixmpp.ClientXMPP):
                    def __init__(
                        self,
                        jid: str,
                        password: str,
                        targets: list[str],
                        subject: str,
                        body: str,
                        before_message: Optional[callable],
                    ) -> None:
                        super().__init__(jid, password, loop=loop)
                        self._targets = targets
                        self._subject = subject
                        self._body = body
                        self._before_message = before_message

                        self.add_event_handler(
                            "session_start", self._session_start
                        )
                        self.add_event_handler(
                            "failed_auth", self._failed_auth
                        )

                        # Keep behaviour predictable and close quickly.
                        self.auto_reconnect = False

                    async def _session_start(self, *args, **kwargs) -> None:
                        try:
                            self.send_presence()
                            await self.get_roster()

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

                    def _failed_auth(self, *args, **kwargs) -> None:
                        # Authentication failures still trigger disconnect.
                        self.disconnect()

                targets = list(self.targets)
                if not targets:
                    # Default to notifying ourselves.
                    targets = [self.config.jid]

                client = _Client(
                    self.config.jid,
                    self.config.password,
                    targets,
                    self.subject,
                    self.body,
                    self.before_message,
                )

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
                        "XMPP connection could not be established."
                    )
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
                with contextlib.suppress(Exception):
                    self._cancel_pending(loop)

                with contextlib.suppress(Exception):
                    loop.stop()

                with contextlib.suppress(Exception):
                    loop.close()

                done.set()

        t = threading.Thread(target=runner, name="apprise-xmpp", daemon=True)
        t.start()

        # Bound the wait. If slixmpp hangs, we want a predictable timeout.
        # Use Apprise's request_timeout as a rough ceiling (in seconds).
        done.wait(timeout=max(5.0, self.timeout))
        self._ok = bool(result[0])
        return self._ok
