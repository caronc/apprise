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

This module provides a wrapper to Slixmpp for Apprise.
"""

from __future__ import annotations

import contextlib
import logging
import re
import ssl
import threading
import time
from typing import Any, Callable, Optional

import certifi

from ...compat import dataclass_compat as dataclass
from .common import SECURE_MODES, SecureXMPPMode

# Default our global support flag
SLIXMPP_SUPPORT_AVAILABLE = False

try:
    import asyncio
    import concurrent.futures

    import slixmpp

    SLIXMPP_SUPPORT_AVAILABLE = True

except ImportError:
    # Slixmpp is not available if code reaches here
    slixmpp = None  # type: ignore[assignment]
    asyncio = None  # type: ignore[assignment]
    concurrent = None  # type: ignore[assignment]


@dataclass(frozen=True, slots=True)
class XMPPConfig:
    """Connection configuration."""

    host: str
    port: int
    jid: str
    password: str
    secure: str = SecureXMPPMode.STARTTLS
    verify_certificate: bool = True


# ---------------------------------------------------------------------------
# Logging Bridge
# ---------------------------------------------------------------------------
LOGGING_ID = "apprise.xmpp"
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


def _close_awaitable(obj: Any) -> None:
    """Best-effort close for coroutine-like objects.

    Some test patches raise before awaiting, leaving coroutines to be
    garbage collected and triggering runtime warnings.
    """
    close = getattr(obj, "close", None)
    if callable(close):
        with contextlib.suppress(Exception):
            close()
# ---------------------------------------------------------------------------
# Internal Slixmpp Client Factory
# ---------------------------------------------------------------------------

_CLIENT_SUBCLASS_CACHE: dict[int, type[Any]] = {}


def _get_client_subclass(base_cls: type[Any]) -> type[Any]:
    """Return (and cache) the internal client subclass for a given base class.

    The tests monkeypatch `xmpp_adapter.slixmpp.ClientXMPP`, so we must resolve
    the base class dynamically at runtime, not at import time. We still cache
    the derived subclass per base class identity to avoid repeated class
    creation overhead in production.
    """
    key = id(base_cls)
    cached = _CLIENT_SUBCLASS_CACHE.get(key)
    if cached is not None:
        return cached

    class _Client(base_cls):  # type: ignore[misc]
        """Internal Slixmpp client for both one-shot and keepalive flows."""

        def __init__(
            self,
            jid: str,
            password: str,
            *,
            oneshot: bool,
            targets: Optional[list[str]] = None,
            subject: str = "",
            body: str = "",
            before_message: Optional[Callable[[], None]] = None,
            want_roster: bool = False,
            roster_timeout: float = 0.0,
            session_started_evt: Optional[asyncio.Event] = None,
            # type: ignore[name-defined]
        ) -> None:
            super().__init__(jid, password)

            # Behaviour
            self._oneshot = bool(oneshot)

            # Send payload (only used in oneshot mode)
            self._targets = list(targets or [])
            self._subject = subject
            self._body = body
            self._before_message = before_message

            # Roster behaviour (both modes)
            self._want_roster = bool(want_roster)
            self._roster_timeout = float(roster_timeout)

            # Keepalive coordination (keepalive mode only)
            self._session_started_evt = session_started_evt

            # State
            self._auth_failed = False

            self.add_event_handler("session_start", self._on_session_start)
            self.add_event_handler("failed_auth", self._failed_auth)
            self.add_event_handler("disconnected", self._disconnected)

            # Keep behaviour predictable and close quickly.
            self.auto_reconnect = False

        async def _session_start(
            self, *args: object, **kwargs: object
        ) -> None:
            try:
                with contextlib.suppress(Exception):
                    self.send_presence()

                if self._want_roster and self._roster_timeout > 0:
                    roster_coro = self.get_roster()
                    try:
                        await asyncio.wait_for(
                            roster_coro,
                            timeout=self._roster_timeout,
                        )
                    except Exception:
                        _close_awaitable(roster_coro)

                # One-shot mode sends messages immediately on session_start and
                # then disconnects. Keepalive mode just signals readiness.
                if self._oneshot:
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
                if self._oneshot:
                    self.disconnect()

                elif self._session_started_evt is not None:
                    self._session_started_evt.set()

        def _failed_auth(self, *args: object, **kwargs: object) -> None:
            # Authentication failure is always a hard failure.
            self._auth_failed = True
            if self._session_started_evt is not None:
                self._session_started_evt.clear()
            self.disconnect()

        def _on_session_start(self, *args: object, **kwargs: object) -> Any:
            """Slixmpp event handler entrypoint.

            Must be synchronous. Also, we must never fall back to
            asyncio.create_task() because that can bind to the wrong
            loop, or no loop, and leak coroutines.
            """
            coro = self._session_start(*args, **kwargs)

            # One-shot mode: let Slixmpp schedule the coroutine itself.
            if self._oneshot:
                return coro

            # Keepalive mode: schedule on the assigned loop.
            loop = getattr(self, "loop", None)

            # If the loop is missing or already closing, we MUST close the
            # coroutine immediately to prevent "never awaited" warnings.
            if loop is None or not loop.is_running():
                with contextlib.suppress(Exception):
                    coro.close()
                return None

            try:
                task = loop.create_task(coro)
                task.add_done_callback(
                    lambda t: (
                        t.exception() if not t.cancelled() else None
                    )
                )

            except Exception:
                # Fallback closure if loop.create_task fails
                with contextlib.suppress(Exception):
                    coro.close()

            return None

        def _disconnected(self, *args: object, **kwargs: object) -> None:
            if self._session_started_evt is not None:
                self._session_started_evt.clear()

    _CLIENT_SUBCLASS_CACHE[key] = _Client
    return _Client


def _build_client(*args: Any, **kwargs: Any) -> Any:
    return _get_client_subclass(slixmpp.ClientXMPP)(*args, **kwargs)

# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------


class SlixmppAdapter:
    """Send a message to one or more targets.

    When keepalive is False, process() performs a one-shot connect, send,
    disconnect.

    When keepalive is True, send_message() keeps a session alive across calls.
    The connection is closed only when close() is called or the instance is
    garbage collected.
    """

    # Define a Slixmpp reference version to prevent this tool from working
    # under non-supported versions
    _supported_version = (1, 10, 0)

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
        roster: bool = False,
        before_message: Optional[Callable[[], None]] = None,
        keepalive: bool = False,
    ) -> None:
        self.config, self.targets, self.subject, self.body = \
            config, targets, subject, body

        self.timeout = max(5.0, float(timeout))
        self.roster, self.before_message, self.keepalive = \
            roster, before_message, keepalive

        global LOGGING_ID
        self.logger = logging.getLogger(LOGGING_ID)

        bridge_slixmpp_logging()

        # Keepalive internals (only used when keepalive=True)
        self._state_lock = threading.RLock()
        self._closing = False
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        # type: ignore[name-defined]
        self._client: Optional[slixmpp.ClientXMPP] = None
        # type: ignore[name-defined]
        self._loop_ready = threading.Event()

        # asyncio primitives created inside the loop thread
        self._connect_lock: Optional[asyncio.Lock] = None
        # type: ignore[name-defined]
        self._session_started: Optional[asyncio.Event] = None
        # type: ignore[name-defined]

    def __del__(self) -> None:
        """Best effort close for keepalive sessions."""
        with contextlib.suppress(Exception):
            self.close()

    @staticmethod
    def _ssl_context(verify: bool) -> ssl.SSLContext:
        ctx = ssl.create_default_context(cafile=certifi.where())
        if not verify:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        return ctx

    @staticmethod
    def _cancel_pending(
        loop: asyncio.AbstractEventLoop,
    ) -> None:  # type: ignore[name-defined]
        """Cleanup pending tasks."""
        pending = [t for t in asyncio.all_tasks(loop) if not t.done()]
        for task in pending:
            task.cancel()

        if pending:
            # We must run until the tasks actually complete (or acknowledge
            # cancellation) to prevent "coroutine was never awaited" warnings.
            with contextlib.suppress(Exception):
                loop.run_until_complete(
                    asyncio.gather(*pending, return_exceptions=True)
                )

    @staticmethod
    def _loop_tick(loop: asyncio.AbstractEventLoop) -> None:
        """Run one final loop tick, closing the coroutine on error."""
        tick = asyncio.sleep(0)
        try:
            loop.run_until_complete(tick)

        except Exception:
            _close_awaitable(tick)

    @staticmethod
    def _finalize_loop(loop: asyncio.AbstractEventLoop) -> None:
        """Best-effort loop shutdown to avoid resource warnings."""
        with contextlib.suppress(Exception):
            SlixmppAdapter._cancel_pending(loop)

        # Give the loop one final tick to process cancellations
        SlixmppAdapter._loop_tick(loop)

        with contextlib.suppress(Exception):
            loop.stop()

        # Detach loop from thread policy
        with contextlib.suppress(Exception):
            asyncio.set_event_loop(None)

        if not loop.is_closed():
            with contextlib.suppress(Exception):
                loop.close()

    def close(self) -> None:
        """Close any persistent connection and stop the keepalive worker."""
        with self._state_lock:
            self._closing = True

        loop, client, thread = self._loop, self._client, self._thread
        if loop is None or thread is None:
            return

        def _shutdown() -> None:
            try:
                if client is not None:
                    client.disconnect()
            finally:
                with contextlib.suppress(Exception):
                    loop.stop()

        with contextlib.suppress(Exception):
            loop.call_soon_threadsafe(_shutdown)

        # Give a moment to exit gracefully.
        thread.join(timeout=1.0)

        # If the worker is still alive, do not clear state.
        alive = getattr(thread, "is_alive", None)
        if callable(alive) and alive():
            return

        with self._state_lock:
            # Detach from any thread-local loop to avoid creating a new
            # loop implicitly (Python 3.12+ may warn about it).
            with contextlib.suppress(Exception):
                asyncio.set_event_loop(None)

            self._thread = None
            self._loop = None
            self._client = None
            self._connect_lock = None
            self._session_started = None

    # -----------------------------------------------------------------------
    # One-shot behaviour (no keepalive)
    # -----------------------------------------------------------------------

    def process(self) -> bool:
        """Send the message, always returning within timeout."""
        done = threading.Event()
        result: list[Optional[bool]] = [None]

        if not self._enabled:
            # We are not turned on
            return False

        shared: dict[str, Any] = {"loop": None, "client": None}

        def runner() -> None:
            loop: Optional[asyncio.AbstractEventLoop] = None
            # type: ignore[name-defined]
            start = time.monotonic()

            try:
                loop = asyncio.new_event_loop()  # type: ignore[union-attr]
                asyncio.set_event_loop(loop)  # type: ignore[union-attr]
                shared["loop"] = loop

                targets = (
                    list(self.targets) if self.targets else [self.config.jid])

                roster_timeout = (
                    max(2.0, min(10.0, self.timeout / 3.0))
                    if self.roster else 0.0
                )

                client = _build_client(
                    jid=self.config.jid,
                    password=self.config.password,
                    oneshot=True,
                    targets=targets,
                    subject=self.subject,
                    body=self.body,
                    before_message=self.before_message,
                    want_roster=self.roster,
                    roster_timeout=roster_timeout,
                    session_started_evt=None,
                )

                shared["client"] = client

                # Prevent Slixmpp from owning loop lifecycle
                with contextlib.suppress(Exception):
                    client.loop = loop  # type: ignore[assignment]

                # Resolve connection behaviour from secure mode
                mode_cfg = SECURE_MODES.get(self.config.secure)
                if not mode_cfg:
                    raise ValueError(
                        f"Unsupported XMPP secure mode: {self.config.secure}"
                    )

                client.enable_plaintext = bool(mode_cfg["enable_plaintext"])
                client.enable_starttls = bool(mode_cfg["enable_starttls"])
                client.enable_direct_tls = bool(mode_cfg["enable_direct_tls"])

                # Only attach an SSL context when TLS may be used
                if not client.enable_plaintext:
                    client.ssl_context = self._ssl_context(
                        self.config.verify_certificate
                    )

                # Slixmpp >= 1.10.0 connect() returns a Future.
                connect_timeout = max(3.0, min(15.0, self.timeout / 3.0))
                connect_fut = client.connect(
                    host=self.config.host,
                    port=self.config.port,
                )

                try:
                    ok = loop.run_until_complete(
                        asyncio.wait_for(
                            connect_fut,
                            timeout=connect_timeout,
                        )
                    )
                    if not ok:
                        self.logger.warning("XMPP connect failed.")
                        with contextlib.suppress(Exception):
                            client.disconnect()
                        result[0] = False
                        return

                except asyncio.TimeoutError:
                    self.logger.warning(
                        "XMPP connect timed out after %.2fs", connect_timeout
                    )
                    result[0] = False
                    return

                except Exception as e:
                    self.logger.debug("XMPP connect failed: %s", e)
                    result[0] = False
                    return

                # Run until disconnected, but still respect our overall
                # timeout.
                elapsed = time.monotonic() - start
                remaining = max(0.0, self.timeout - elapsed)
                run_timeout = max(1.0, remaining)

                try:
                    loop.run_until_complete(
                        asyncio.wait_for(  # type: ignore[arg-type]
                            client.disconnected, timeout=run_timeout
                        )
                    )
                except asyncio.TimeoutError:  # type: ignore[attr-defined]
                    self.logger.warning(
                        "XMPP session timed out after %.2fs", run_timeout
                    )
                    with contextlib.suppress(Exception):
                        client.disconnect()
                    result[0] = False
                    return

                # Disconnect happened, success depends on auth state
                result[0] = not bool(getattr(client, "_auth_failed", False))

            except Exception as e:  # pragma: no cover
                self.logger.warning("XMPP send failed.")
                self.logger.debug("XMPP Exception: %s", e)
                result[0] = False

            finally:
                loop = shared.get("loop")
                if loop is not None:
                    self._finalize_loop(loop)
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

    # -----------------------------------------------------------------------
    # Keepalive Behaviour
    # -----------------------------------------------------------------------

    def _ensure_keepalive_worker(self) -> bool:
        """Ensure the background loop and client exist."""
        if not self.keepalive:
            return False

        with self._state_lock:
            if self._closing:
                return False

            if self._thread is not None and self._thread.is_alive():
                return True

            if not self._enabled:
                return False

            self._loop_ready.clear()

            self._thread = threading.Thread(
                target=self._keepalive_runner,
                name="apprise-xmpp-keepalive",
                daemon=True,
            )
            self._thread.start()

        if not self._loop_ready.wait(timeout=self.timeout):
            self.logger.warning(
                "XMPP keepalive worker failed to start within %.2fs",
                self.timeout,
            )
            return False

        return True

    def _keepalive_runner(self) -> None:
        loop: Optional[asyncio.AbstractEventLoop] = None
        # type: ignore[name-defined]
        published = False

        try:
            loop = asyncio.new_event_loop()  # type: ignore[union-attr]
            asyncio.set_event_loop(loop)  # type: ignore[union-attr]

            session_started = asyncio.Event()  # type: ignore[union-attr]
            connect_lock = asyncio.Lock()  # type: ignore[union-attr]

            roster_timeout = (
                max(2.0, min(10.0, self.timeout / 3.0))
                if self.roster else 3.0
            )

            client = _build_client(
                jid=self.config.jid,
                password=self.config.password,
                oneshot=False,
                want_roster=self.roster,
                roster_timeout=roster_timeout,
                session_started_evt=session_started,
            )

            with contextlib.suppress(Exception):
                client.loop = loop  # type: ignore[assignment]

            mode_cfg = SECURE_MODES.get(self.config.secure)
            if not mode_cfg:
                raise ValueError(
                    f"Unsupported XMPP secure mode: {self.config.secure}"
                )

            client.enable_plaintext = bool(mode_cfg["enable_plaintext"])
            client.enable_starttls = bool(mode_cfg["enable_starttls"])
            client.enable_direct_tls = bool(mode_cfg["enable_direct_tls"])

            if not client.enable_plaintext:
                client.ssl_context = self._ssl_context(
                    self.config.verify_certificate
                )

            # keepalive=yes implies enabling XEP-0199 keepalive pings
            with contextlib.suppress(Exception):
                client.register_plugin("xep_0199", {"keepalive": True})

            with self._state_lock:
                if self._closing:
                    return

                self._loop = loop
                self._client = client
                self._connect_lock = connect_lock
                self._session_started = session_started
                published = True

            self._loop_ready.set()

            loop.run_forever()

        except Exception as e:  # pragma: no cover
            self.logger.warning("XMPP keepalive worker failed.")
            self.logger.debug("XMPP keepalive exception: %s", e)

        finally:
            if published:
                with self._state_lock:
                    if self._closing and self._loop is loop:
                        # Clear internal references if we are exiting the
                        # worker.
                        self._loop = None
                        self._client = None
                        self._connect_lock = None
                        self._session_started = None
                        self._thread = None

            if loop is not None:
                self._finalize_loop(loop)


    async def _connect_if_required(self) -> bool:
        if self._loop is None or self._client is None:
            return False
        if self._connect_lock is None or self._session_started is None:
            return False

        # If auth already failed, do not pretend a connection is ready.
        if bool(getattr(self._client, "_auth_failed", False)):
            return False

        async with self._connect_lock:
            if self._session_started.is_set():
                return True

            connect_timeout = max(3.0, min(15.0, self.timeout / 3.0))

            try:
                fut = self._client.connect(
                    host=self.config.host,
                    port=self.config.port,
                )
                connect_ok = await asyncio.wait_for(  # type: ignore[arg-type]
                    fut, timeout=connect_timeout
                )

                # honour boolean connect() result in keepalive.
                if not connect_ok:
                    self.logger.warning("XMPP connect failed.")
                    with contextlib.suppress(Exception):
                        self._client.disconnect()
                    return False

            except asyncio.TimeoutError:  # type: ignore[attr-defined]
                self.logger.warning(
                    "XMPP connect timed out after %.2fs", connect_timeout
                )
                return False

            except Exception as e:
                self.logger.debug("XMPP connect failed: %s", e)
                return False

            try:
                session_wait = self._session_started.wait()
                await asyncio.wait_for(
                    session_wait,
                    timeout=connect_timeout,
                )
            except asyncio.TimeoutError:  # type: ignore[attr-defined]
                _close_awaitable(session_wait)
                self.logger.warning(
                    "XMPP session did not start within %.2fs",
                    connect_timeout,
                )
                return False

            except Exception:
                _close_awaitable(session_wait)

                return False

            # If auth failed during startup, treat as failure.
            return not bool(getattr(self._client, "_auth_failed", False))

    async def _send_keepalive_async(
        self,
        targets: list[str],
        subject: str,
        body: str,
    ) -> bool:
        if self._client is None:
            return False

        ok = await self._connect_if_required()
        if not ok:
            return False

        # Auth failed after connect, do not send.
        if bool(getattr(self._client, "_auth_failed", False)):
            return False

        send_targets = targets if targets else [self.config.jid]

        try:
            for target in send_targets:
                self._client.send_message(
                    mto=target,
                    msubject=subject,
                    mbody=body,
                    mtype="chat",
                )
            return True

        except Exception as e:
            self.logger.debug("XMPP send failed: %s", e)
            if self._session_started is not None:
                self._session_started.clear()
            return False

    def send_message(
        self,
        targets: Optional[list[str]] = None,
        subject: Optional[str] = None,
        body: Optional[str] = None,
    ) -> bool:
        """Send a message, keeping the session alive if keepalive=True."""
        if not self.keepalive:
            # Fallback to one-shot behaviour using current stored attributes
            if targets is not None:
                self.targets = targets
            if subject is not None:
                self.subject = subject
            if body is not None:
                self.body = body
            return self.process()

        if not self._ensure_keepalive_worker():
            return False

        loop = self._loop
        if loop is None:
            return False

        targets = self.targets if targets is None else targets
        subject = self.subject if subject is None else subject
        body = self.body if body is None else body

        try:
            fut = asyncio.run_coroutine_threadsafe(  # type: ignore[union-attr]
                self._send_keepalive_async(
                    targets=targets,
                    subject=subject,
                    body=body,
                ),
                loop,
            )
            return bool(fut.result(timeout=self.timeout))

        except concurrent.futures.TimeoutError:  # type: ignore[union-attr]
            self.logger.warning(
                "XMPP keepalive send timed out after %.2fs", self.timeout
            )
            if self._session_started is not None:
                with contextlib.suppress(Exception):
                    loop.call_soon_threadsafe(self._session_started.clear)
            return False

        except Exception as e:
            self.logger.debug("XMPP keepalive send exception: %s", e)
            return False

    @staticmethod
    def package_dependency() -> str:
        """Defines our static dependency for this adapter to work."""
        version = ".".join([str(v) for v in SlixmppAdapter._supported_version])
        return f"slixmpp >= {version}"

    @staticmethod
    def supported_version(version: Optional[str] = None) -> bool:
        """Returns true if we currently have a version of Slixmpp supported.

        Provided string describes a version in format of major.minor.patch.
        """
        if SLIXMPP_SUPPORT_AVAILABLE:
            m = re.match(
                r"^(?P<major>\d+)(\.(?P<minor>\d+)(\.(?P<patch>\d+))?)?",
                version or getattr(slixmpp, "__version__", "") or "",
            )
            if not m:
                return False

            return (
                int(m.group("major")),
                int(m.group("minor") or 0),
                int(m.group("patch") or 0),
            ) >= SlixmppAdapter._supported_version

        return False
