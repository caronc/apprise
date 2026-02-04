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

"""
Unit tests for the XMPP plugin.

"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import ssl
import threading
import time
from types import SimpleNamespace
from typing import Any

import pytest

from apprise import LOGGER_NAME, Apprise, NotifyType
from apprise.plugins.xmpp import adapter as xmpp_adapter, base as xmpp_base
from apprise.plugins.xmpp.base import NotifyXMPP

# ---------------------------------------------------------------------------
# Slixmpp Availability Handling
# ---------------------------------------------------------------------------

try:
    # Enforce slixmpp >= Minimum Supported Version
    SLIXMPP_AVAILABLE = xmpp_adapter.SlixmppAdapter.supported_version()

except Exception:
    SLIXMPP_AVAILABLE = False


# ---------------------------------------------------------------------------
# Fake Slixmpp Client
# ---------------------------------------------------------------------------

class FakeClientXMPP:
    def __init__(self, jid: str, password: str) -> None:
        self.jid = jid
        self.password = password
        # Loop is assigned by adapter via `client.loop = loop`, but we default
        # to the current event loop for safety in tests.
        self.loop = asyncio.get_event_loop()
        self.handlers: dict[str, Any] = {}
        self.auto_reconnect = True

        # Slixmpp >= 1.10.0: adapter waits on this Future
        self.disconnected: asyncio.Future[bool] = self.loop.create_future()

        # Slixmpp toggles used by adapter
        self.enable_plaintext = True
        self.enable_starttls = True
        self.enable_direct_tls = False
        self.ssl_context = None

    def add_event_handler(self, name: str, handler: Any) -> None:
        self.handlers[name] = handler

    def send_presence(self) -> None:
        return None

    async def get_roster(self) -> None:
        return None

    def send_message(self, **kwargs: Any) -> None:
        return None

    def disconnect(self) -> None:
        # Complete the disconnected Future if it is not already done.
        if not self.disconnected.done():
            self.disconnected.set_result(True)

    def connect(self, **kwargs: Any) -> asyncio.Future[bool]:
        # Slixmpp >= 1.10.0 connect() returns a Future. Our adapter awaits it.
        fut: asyncio.Future[bool] = self.loop.create_future()
        fut.set_result(True)

        # Simulate a successful session start shortly after connect.
        handler = self.handlers.get("session_start")
        if handler:
            async def _run() -> None:
                await handler()
                # Ensure disconnect occurs even if handler forgets.
                self.disconnect()

            # Schedule on the current loop
            self.loop.create_task(_run())

        return fut


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def install_fake_slixmpp(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(xmpp_adapter, "asyncio", asyncio, raising=False)
    monkeypatch.setattr(
        xmpp_adapter,
        "slixmpp",
        SimpleNamespace(ClientXMPP=FakeClientXMPP),
        raising=False,
    )
    monkeypatch.setattr(
        xmpp_adapter, "SLIXMPP_SUPPORT_AVAILABLE", True, raising=False)
    monkeypatch.setattr(
        xmpp_adapter.SlixmppAdapter,
        "_enabled",
        True,
        raising=False,
    )


# ---------------------------------------------------------------------------
# NotifyXMPP tests
# ---------------------------------------------------------------------------

@pytest.mark.skipif(SLIXMPP_AVAILABLE, reason="Requires slixmpp NOT installed")
def test_slixmpp_unavailable() -> None:
    obj=NotifyXMPP(host="example.com", user="me@example.com", password="x")
    assert obj.send("will fail") is False


@pytest.mark.skipif(not SLIXMPP_AVAILABLE, reason="Requires slixmpp")
def test_xmpp_invalid_jid() -> None:
    with pytest.raises(TypeError):
        NotifyXMPP(host="example.com", user="bad jid", password="x")


@pytest.mark.skipif(not SLIXMPP_AVAILABLE, reason="Requires slixmpp")
def test_xmpp_targets_filtered() -> None:
    n = NotifyXMPP(
        host="example.com",
        user="me@example.com",
        password="x",
        targets=["ok@example.com", " user1 user2 ", "", "also@example.net"],
    )

    # parse_list() tokenises on whitespace, so "bad jid" becomes two targets.
    # Empty values are dropped before they reach the validation loop, so no
    # warning is guaranteed for the empty string.
    assert sorted(n.targets) == [
        "also@example.net",
        "ok@example.com",
        "user1@example.com",
        "user2@example.com",
    ]


@pytest.mark.skipif(not SLIXMPP_AVAILABLE, reason="Requires slixmpp")
def test_xmpp_len() -> None:
    n1 = NotifyXMPP(host="example.com", user="me@example.com", password="x")
    assert len(n1) == 1

    n2 = NotifyXMPP(
        host="example.com",
        user="me@example.com",
        password="x",
        targets=["a@example.com", "b@example.com"],
    )
    # still just one upstream message
    assert len(n2) == 1


@pytest.mark.skipif(not SLIXMPP_AVAILABLE, reason="Requires slixmpp")
def test_xmpp_url_privacy() -> None:
    n = NotifyXMPP(
        host="example.com",
        user="me@example.com",
        password="secret",
        targets=["a@example.com"],
        verify=False,
    )
    u = n.url(privacy=True)
    assert "secret" not in u
    assert "verify=" in u


@pytest.mark.skipif(not SLIXMPP_AVAILABLE, reason="Requires slixmpp")
def test_xmpp_parse_url() -> None:
    r = NotifyXMPP.parse_url(
        "xmpps://me:pass@example.com/a@example.com?verify=no"
    )
    assert r["verify"] is False
    assert r["targets"] == ["a@example.com"]


@pytest.mark.skipif(not SLIXMPP_AVAILABLE, reason="Requires slixmpp")
def test_xmpp_parse_url_to() -> None:
    r = NotifyXMPP.parse_url(
        "xmpp://me:pass@example.com?to=a@example.com,b@example.net"
    )
    assert sorted(r["targets"]) == ["a@example.com", "b@example.net"]

@pytest.mark.skipif(not SLIXMPP_AVAILABLE, reason="Requires slixmpp")
def test_xmpp_invalid_targets_logged(
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture) -> None:
    """Invalid XMPP targets are dropped with a warning."""

    caplog.set_level(logging.WARNING, logger=LOGGER_NAME)
    caplog.set_level(logging.WARNING, logger=xmpp_base.__name__)

    # parse_list() tokenises on whitespace, so it is difficult to naturally
    # feed a whitespace-containing value through.  Patch parse_list() to
    # return a value that will fail IS_JID validation.
    monkeypatch.setattr(
        xmpp_base,
        "parse_list",
        lambda _v: ["bad jid", "ok@example.com"],
        raising=True,
    )

    n = NotifyXMPP(
        host="example.com",
        user="me@example.com",
        password="x",
        targets=["ignored"],
    )

    assert n.targets == ["ok@example.com"]
    assert "Dropped invalid XMPP target" in caplog.text


@pytest.mark.skipif(not SLIXMPP_AVAILABLE, reason="Requires slixmpp")
def test_xmpp_url_identifier_is_accessible() -> None:
    """url_identifier property should be accessible and stable."""
    n = NotifyXMPP(
        host="example.com", user="me@example.com", password="secret")
    schema, host, user, password, port = n.url_identifier
    assert schema == "xmpp"
    assert host == "example.com"
    assert user == "me@example.com"
    assert password == "secret"
    assert port is None


@pytest.mark.skipif(not SLIXMPP_AVAILABLE, reason="Requires slixmpp")
def test_xmpp_url_handling() -> None:
    """url() must not append a path when there are no targets."""
    apobj = Apprise()
    assert apobj.add("xmpp://me:secret@example.com?verify=no") is True

    assert len(apobj) == 1
    plugin = apobj[0]

    u = plugin.url(privacy=False)
    assert "example.com/?" in u
    assert "mode=none" in u

    apobj = Apprise()
    assert apobj.add("xmpps://me:secret@example.com?mode=tls") is True

    assert len(apobj) == 1
    plugin = apobj[0]

    u = plugin.url(privacy=False)
    assert "mode=tls" in u

    # invalid Mode
    apobj = Apprise()
    assert apobj.add("xmpps://me:secret@example.com?mode=invalid") is False

    # Ambiguous secure=true (xmpps://) and mode = none
    apobj = Apprise()
    assert apobj.add("xmpps://me:secret@example.com?mode=none") is True

    assert len(apobj) == 1
    plugin = apobj[0]

    u = plugin.url(privacy=False)
    # starttls (upgraded from none - most secure path)
    assert "mode=starttls" in u

    # Ambiguous secure=False (xmpp://) and mode != none
    apobj = Apprise()
    assert apobj.add("xmpp://me:secret@example.com?mode=tls") is True

    assert len(apobj) == 1
    plugin = apobj[0]

    u = plugin.url(privacy=False)
    # most secure path prevails
    assert "mode=tls" in u


@pytest.mark.skipif(not SLIXMPP_AVAILABLE, reason="Requires slixmpp")
def test_xmpp_parse_url_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    """parse_url() returns None when NotifyBase.parse_url() fails."""

    monkeypatch.setattr(
        xmpp_base.NotifyBase,
        "parse_url",
        lambda *_args, **_kwargs: None,
        raising=True,
    )
    assert NotifyXMPP.parse_url("xmpp://bad") is None


@pytest.mark.skipif(not SLIXMPP_AVAILABLE, reason="Requires slixmpp")
def test_xmpp_apprise_notify_invokes_adapter(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Exercise the Apprise.notify() workflow while mocking network I/O."""

    captured: dict[str, Any] = {}

    class _Adapter:
        def __init__(
            self,
            config: xmpp_adapter.XMPPConfig,
            targets: list[str],
            subject: str,
            body: str,
            timeout: float = 0.0,
            before_message: Any = None,
            logger: logging.Logger | None = None,
        ) -> None:
            captured["targets"] = targets
            captured["body"] = body
            captured["subject"] = subject

        def process(self) -> bool:
            return True

    monkeypatch.setattr(
        xmpp_base, "SlixmppAdapter", _Adapter, raising=True)

    apobj = Apprise()
    apobj.add("xmpp://me:secret@example.com/a@example.com")

    assert apobj.notify(
        "hello", title="subject", notify_type=NotifyType.INFO) is True
    assert captured["targets"] == ["a@example.com"]
    assert captured["subject"] == "subject"
    assert "hello" in captured["body"]



# ---------------------------------------------------------------------------
# Adapter tests
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not SLIXMPP_AVAILABLE, reason="Requires slixmpp")
def test_xmpp_ssl_context() -> None:
    ctx = xmpp_adapter.SlixmppAdapter._ssl_context(True)
    assert ctx.verify_mode != ssl.CERT_NONE

    ctx2 = xmpp_adapter.SlixmppAdapter._ssl_context(False)
    assert ctx2.verify_mode == ssl.CERT_NONE
    assert ctx2.check_hostname is False


@pytest.mark.skipif(not SLIXMPP_AVAILABLE, reason="Requires slixmpp")
def test_xmpp_cancel_pending_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    loop = asyncio.new_event_loop()
    try:
        monkeypatch.setattr(
            asyncio, "all_tasks", lambda _: set(), raising=True)
        xmpp_adapter.SlixmppAdapter._cancel_pending(loop)
    finally:
        loop.close()


@pytest.mark.skipif(not SLIXMPP_AVAILABLE, reason="Requires slixmpp")
def test_xmpp_cancel_pending_tasks(monkeypatch: pytest.MonkeyPatch) -> None:
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)

        async def _noop() -> None:
            await asyncio.sleep(0)

        t1 = loop.create_task(_noop())
        t2 = loop.create_task(_noop())

        monkeypatch.setattr(
            asyncio, "all_tasks", lambda _: {t1, t2}, raising=True)

        xmpp_adapter.SlixmppAdapter._cancel_pending(loop)
        assert t1.cancelled()
        assert t2.cancelled()

    finally:
        # Avoid asyncio.get_event_loop() here to prevent DeprecationWarning on
        # newer Python versions.  Setting to None is sufficient for isolation.
        with contextlib.suppress(Exception):
            asyncio.set_event_loop(None)
        loop.close()


@pytest.mark.skipif(not SLIXMPP_AVAILABLE, reason="Requires slixmpp")
def test_xmpp_process_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    install_fake_slixmpp(monkeypatch)
    config = xmpp_adapter.XMPPConfig(
        jid="me@example.com",
        password="x",
        host="example.com",
        port=5223,
        secure=xmpp_adapter.SecureXMPPMode.TLS,
        verify_certificate=True,
    )
    a = xmpp_adapter.SlixmppAdapter(
        config=config,
        targets=[],
        subject="s",
        body="b",
        timeout=1,
    )
    monkeypatch.setattr(a, "_enabled", False, raising=True)
    assert a.process() is False


@pytest.mark.skipif(not SLIXMPP_AVAILABLE, reason="Requires slixmpp")
def test_xmpp_process_fail(
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture) -> None:
    install_fake_slixmpp(monkeypatch)
    caplog.set_level(logging.WARNING)

    def bad_connect(self: FakeClientXMPP, **kw: Any) -> asyncio.Future[bool]:
        fut: asyncio.Future[bool] = self.loop.create_future()
        fut.set_result(False)
        return fut

    monkeypatch.setattr(FakeClientXMPP, "connect", bad_connect, raising=True)

    config = xmpp_adapter.XMPPConfig(
        jid="me@example.com",
        password="x",
        host="example.com",
        port=5223,
        secure=xmpp_adapter.SecureXMPPMode.STARTTLS,
        verify_certificate=True,
    )
    a = xmpp_adapter.SlixmppAdapter(
        config=config,
        targets=["a@example.com"],
        subject="s",
        body="b",
        timeout=1,
    )
    assert a.process() is False


@pytest.mark.skipif(not SLIXMPP_AVAILABLE, reason="Requires slixmpp")
def test_xmpp_process_success(monkeypatch: pytest.MonkeyPatch) -> None:
    install_fake_slixmpp(monkeypatch)
    config = xmpp_adapter.XMPPConfig(
        jid="me@example.com",
        password="x",
        host="example.com",
        port=5223,
        secure=xmpp_adapter.SecureXMPPMode.TLS,
        verify_certificate=False,
    )

    a = xmpp_adapter.SlixmppAdapter(
        config=config,
        targets=["a@example.com"],
        subject="s",
        body="b",
        timeout=1.0,
    )
    assert a.process() is True


@pytest.mark.skipif(not SLIXMPP_AVAILABLE, reason="Requires slixmpp")
def test_xmpp_process_default_target(monkeypatch: pytest.MonkeyPatch) -> None:
    install_fake_slixmpp(monkeypatch)
    config = xmpp_adapter.XMPPConfig(
        jid="me@example.com",
        password="x",
        host="example.com",
        port=5223,
        secure=xmpp_adapter.SecureXMPPMode.STARTTLS,
        verify_certificate=False,
    )

    a = xmpp_adapter.SlixmppAdapter(
        config=config,
        targets=[],
        subject="s",
        body="b",
        timeout=1.0,
    )
    assert a.process() is True


@pytest.mark.skipif(not SLIXMPP_AVAILABLE, reason="Requires slixmpp")
def test_xmpp_process_exception(
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture) -> None:
    install_fake_slixmpp(monkeypatch)
    caplog.set_level(logging.DEBUG)

    def explode(self: FakeClientXMPP, **kw: Any) -> bool:
        raise RuntimeError("boom")

    monkeypatch.setattr(FakeClientXMPP, "connect", explode, raising=True)

    config = xmpp_adapter.XMPPConfig(
        jid="me@example.com",
        password="x",
        host="example.com",
        port=5223,
        secure=xmpp_adapter.SecureXMPPMode.TLS,
        verify_certificate=True,
    )
    a = xmpp_adapter.SlixmppAdapter(
        config=config,
        targets=["a@example.com"],
        subject="s",
        body="b",
        timeout=1,
    )
    assert a.process() is False


@pytest.mark.skipif(not SLIXMPP_AVAILABLE, reason="Requires slixmpp")
def test_xmpp_process_before_message(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure before_message callback is invoked for each target."""
    install_fake_slixmpp(monkeypatch)

    called: list[int] = []

    def before_message() -> None:
        called.append(1)

    config = xmpp_adapter.XMPPConfig(
        jid="me@example.com",
        password="x",
        host="example.com",
        port=5223,
        secure=xmpp_adapter.SecureXMPPMode.STARTTLS,
        verify_certificate=False,
    )
    a = xmpp_adapter.SlixmppAdapter(
        config=config,
        targets=["a@example.com", "b@example.com"],
        subject="s",
        body="b",
        timeout=1,
        before_message=before_message,
    )
    assert a.process() is True
    assert len(called) == 2


@pytest.mark.skipif(not SLIXMPP_AVAILABLE, reason="Requires slixmpp")
def test_xmpp_process_failed_auth_disconnect(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Authentication failure path must still call disconnect()."""
    install_fake_slixmpp(monkeypatch)

    # Force the connect() path to trigger the failed_auth handler.
    def connect_failed_auth(
            self: FakeClientXMPP, **kw: Any) -> asyncio.Future[bool]:
        fut: asyncio.Future[bool] = self.loop.create_future()
        fut.set_result(True)

        handler = self.handlers.get("failed_auth")
        if handler:
            def _run() -> None:
                handler()
                self.disconnect()
            self.loop.call_soon(_run)
        return fut

    monkeypatch.setattr(
        FakeClientXMPP, "connect", connect_failed_auth, raising=True)

    disconnected = {"called": False}

    def disconnect(self: FakeClientXMPP) -> None:
        disconnected["called"] = True
        if not self.disconnected.done():
            self.disconnected.set_result(True)

    monkeypatch.setattr(FakeClientXMPP, "disconnect", disconnect, raising=True)

    config = xmpp_adapter.XMPPConfig(
        jid="me@example.com",
        password="x",
        host="example.com",
        port=5223,
        secure=xmpp_adapter.SecureXMPPMode.TLS,
        verify_certificate=False,
    )
    a = xmpp_adapter.SlixmppAdapter(
        config=config,
        targets=["a@example.com"],
        subject="s",
        body="b",
        timeout=1,
    )
    assert a.process() is True
    assert disconnected["called"] is True


@pytest.mark.skipif(not SLIXMPP_AVAILABLE, reason="Requires slixmpp")
def test_xmpp_normalize_jid() -> None:
    """Tests normalize_jid()"""
    assert NotifyXMPP.normalize_jid("user", "example.ca") == "user@example.ca"
    assert NotifyXMPP.normalize_jid(
        "user/resource", "example.ca") == "user@example.ca/resource"
    assert NotifyXMPP.normalize_jid(
        "user/resource/extra/crap", "example.ca") == "user@example.ca/resource"
    assert NotifyXMPP.normalize_jid(
        "user@example.com/r1", "example.ca") == "user@example.com/r1"

    with pytest.raises(ValueError):
        # Bad entry
        NotifyXMPP.normalize_jid("", "example.ca")



@pytest.mark.skipif(not SLIXMPP_AVAILABLE, reason="Requires slixmpp")
def test_xmpp_bridge_logging_safe_lock(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """tests bridge logging on multiple attempts"""
    # Reset module globals
    monkeypatch.setattr(xmpp_adapter, "_LOG_BRIDGED", False, raising=True)

    # Acquire the lock so the worker blocks inside bridge_slixmpp_logging()
    xmpp_adapter._LOG_BRIDGE_LOCK.acquire()

    done = {"ok": False}

    def worker() -> None:
        try:
            xmpp_adapter.bridge_slixmpp_logging()
            done["ok"] = True
        finally:
            pass

    t = threading.Thread(target=worker, daemon=True)
    t.start()

    # Give worker a moment to pass the outer if and block on the lock
    time.sleep(0.02)

    # Now flip the flag while the lock is still held; when released, worker
    # will acquire the lock and hit the *inner* early-return.
    monkeypatch.setattr(xmpp_adapter, "_LOG_BRIDGED", True, raising=True)

    xmpp_adapter._LOG_BRIDGE_LOCK.release()
    t.join(timeout=1.0)

    assert done["ok"] is True


@pytest.mark.skipif(not SLIXMPP_AVAILABLE, reason="Requires slixmpp")
def test_xmpp_multi_logging_bridge_handling(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Handles multiple logging attempts made by multiple xmpp instances"""

    # Reset module globals
    monkeypatch.setattr(xmpp_adapter, "_LOG_BRIDGED", False, raising=True)

    apprise_logger = logging.getLogger("apprise")
    slix_logger = logging.getLogger("slixmpp")

    # Preserve existing handlers
    old_apprise = list(apprise_logger.handlers)
    old_slix = list(slix_logger.handlers)

    try:
        handler = logging.NullHandler()

        # Arrange for slix to already have the handler
        apprise_logger.handlers = [handler]
        slix_logger.handlers = [handler]

        xmpp_adapter.bridge_slixmpp_logging()

        # Handler should not be duplicated
        assert slix_logger.handlers.count(handler) == 1

    finally:
        apprise_logger.handlers = old_apprise
        slix_logger.handlers = old_slix


@pytest.mark.skipif(not SLIXMPP_AVAILABLE, reason="Requires slixmpp")
def test_xmpp_process_failure_cleanup(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests edge cases for failures that require cleanup"""

    install_fake_slixmpp(monkeypatch)

    # Ensure adapter is enabled
    monkeypatch.setattr(
        xmpp_adapter.SlixmppAdapter, "_enabled", True, raising=True)

    # Make new_event_loop fail before shared['loop'] is assigned
    def raise_new_event_loop() -> Any:
        raise RuntimeError("poof")

    monkeypatch.setattr(
        xmpp_adapter.asyncio,
        "new_event_loop", raise_new_event_loop, raising=True)

    config = xmpp_adapter.XMPPConfig(
        jid="me@example.com",
        password="x",
        host="example.com",
        port=5223,
        secure=xmpp_adapter.SecureXMPPMode.STARTTLS,
        verify_certificate=False,
    )

    a = xmpp_adapter.SlixmppAdapter(
        config=config,
        targets=["a@example.com"],
        subject="s",
        body="b",
        timeout=5.0,
    )

    # Should return False
    assert a.process() is False


@pytest.mark.skipif(not SLIXMPP_AVAILABLE, reason="Requires slixmpp")
def test_xmpp_timeout_cleanup_disconnect_exception_suppressed(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Cover timeout cleanup: loop_obj != None"""
    install_fake_slixmpp(monkeypatch)

    # Ensure adapter is enabled
    monkeypatch.setattr(
        xmpp_adapter.SlixmppAdapter, "_enabled", True, raising=True)

    client_created = threading.Event()

    # Let us know when _Client() has been constructed (super().__init__ call)
    orig_init = FakeClientXMPP.__init__

    def init_signal(
            self: FakeClientXMPP,
            jid: str,
            password: str,
            *args: Any,
            **kwargs: Any) -> None:
        orig_init(self, jid, password, *args, **kwargs)
        client_created.set()

    monkeypatch.setattr(
        FakeClientXMPP, "__init__", init_signal, raising=True)

    # Block connect so runner cannot complete before the timeout branch.
    def connect_blocks(
            self: FakeClientXMPP, **kw: Any) -> asyncio.Future[bool]:
        fut: asyncio.Future[bool] = self.loop.create_future()
        # Never resolve.
        return fut

    monkeypatch.setattr(
        FakeClientXMPP, "connect", connect_blocks, raising=True)

    # Make done.wait deterministic without touching real threading.Event used
    # by Thread internals
    import threading as _real_threading

    class _FakeDoneEvent:
        def __init__(self) -> None:
            self._set = False
            self._wait_calls = 0

        def set(self) -> None:
            self._set = True

        def wait(self, timeout: float | None = None) -> bool:
            self._wait_calls += 1
            if self._wait_calls == 1:
                # Ensure the client exists before we force the timeout branch
                client_created.wait(timeout=1.0)
                return False
            return self._set

    class _ThreadingProxy:
        Event = _FakeDoneEvent
        Thread = _real_threading.Thread

        def __getattr__(self, name: str) -> Any:
            return getattr(_real_threading, name)

    monkeypatch.setattr(
        xmpp_adapter, "threading", _ThreadingProxy(), raising=True)

    # Capture and control loop.call_soon_threadsafe behaviour
    import asyncio as _real_asyncio
    orig_new_event_loop = _real_asyncio.new_event_loop

    calls: list[str] = []

    def new_event_loop_wrapped() -> _real_asyncio.AbstractEventLoop:
        loop = orig_new_event_loop()
        orig_csts = loop.call_soon_threadsafe

        def csts(cb: Any, *a: Any) -> Any:
            # Identify which callback is being scheduled
            name = getattr(cb, "__name__", repr(cb))
            calls.append(name)

            # Raise only for disconnect callback to hit try/except
            if name == "disconnect":
                raise RuntimeError("boom")

            return orig_csts(cb, *a)

        monkeypatch.setattr(loop, "call_soon_threadsafe", csts, raising=True)
        return loop

    monkeypatch.setattr(
        xmpp_adapter.asyncio, "new_event_loop",
        new_event_loop_wrapped, raising=True)

    config = xmpp_adapter.XMPPConfig(
        jid="me@example.com",
        password="x",
        host="example.com",
        port=5223,
        secure=xmpp_adapter.SecureXMPPMode.TLS,
        verify_certificate=False,
    )

    a = xmpp_adapter.SlixmppAdapter(
        config=config,
        targets=["a@example.com"],
        subject="s",
        body="b",
        timeout=5.0,
    )

    assert a.process() is False

    # We should have attempted both disconnect and loop.stop scheduling
    assert "disconnect" in calls
    assert "stop" in calls


@pytest.mark.skipif(not SLIXMPP_AVAILABLE, reason="Requires slixmpp")
def test_xmpp_timeout_cleanup_no_client_stop_exception_suppressed(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Cover timeout cleanup: loop_obj != None"""
    install_fake_slixmpp(monkeypatch)

    monkeypatch.setattr(
        xmpp_adapter.SlixmppAdapter, "_enabled", True, raising=True)

    loop_created = threading.Event()
    allow_client_create = threading.Event()

    # Block FakeClientXMPP.__init__ so shared['client'] never gets set before
    # timeout
    orig_init = FakeClientXMPP.__init__

    def init_block(
            self: FakeClientXMPP,
            jid: str,
            password: str,
            *args: Any,
            **kwargs: Any) -> None:
        # Wait until main thread has already taken the timeout path
        allow_client_create.wait(timeout=1.0)
        orig_init(self, jid, password, *args, **kwargs)

    monkeypatch.setattr(FakeClientXMPP, "__init__", init_block, raising=True)

    # Deterministic done.wait: wait until loop exists, then force timeout
    import threading as _real_threading

    class _FakeDoneEvent:
        def __init__(self) -> None:
            self._set = False
            self._wait_calls = 0

        def set(self) -> None:
            self._set = True

        def wait(self, timeout: float | None = None) -> bool:
            self._wait_calls += 1
            if self._wait_calls == 1:
                loop_created.wait(timeout=1.0)
                return False
            return self._set

    class _ThreadingProxy:
        Event = _FakeDoneEvent
        Thread = _real_threading.Thread

        def __getattr__(self, name: str) -> Any:
            return getattr(_real_threading, name)

    monkeypatch.setattr(
        xmpp_adapter, "threading", _ThreadingProxy(), raising=True)

    # Wrap new_event_loop so we can (a) signal loop exists and (b) make stop
    # raise
    import asyncio as _real_asyncio
    orig_new_event_loop = _real_asyncio.new_event_loop

    calls: list[str] = []

    def new_event_loop_wrapped() -> _real_asyncio.AbstractEventLoop:
        loop = orig_new_event_loop()
        loop_created.set()

        def csts(cb: Any, *a: Any) -> Any:
            name = getattr(cb, "__name__", repr(cb))
            calls.append(name)
            if name == "stop":
                raise RuntimeError("boom-stop")
            return None

        monkeypatch.setattr(loop, "call_soon_threadsafe", csts, raising=True)
        return loop

    monkeypatch.setattr(
        xmpp_adapter.asyncio, "new_event_loop",
        new_event_loop_wrapped, raising=True)

    config = xmpp_adapter.XMPPConfig(
        jid="me@example.com",
        password="x",
        host="example.com",
        port=5223,
        secure=xmpp_adapter.SecureXMPPMode.NONE,
        verify_certificate=False,
    )

    a = xmpp_adapter.SlixmppAdapter(
        config=config,
        targets=["a@example.com"],
        subject="s",
        body="b",
        timeout=5.0,
    )

    try:
        assert a.process() is False
        # client_obj is None, so no disconnect scheduling attempt should occur
        assert "disconnect" not in calls
        # stop scheduling attempted and exception suppressed
        assert "stop" in calls
    finally:
        # Unblock the runner thread so it does not linger
        allow_client_create.set()


@pytest.mark.skipif(not SLIXMPP_AVAILABLE, reason="Requires slixmpp")
def test_xmpp_timeout_cleanup_loop_none_skips_disconnect_and_stop(
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture) -> None:
    """Cover timeout clean-up branch where shared['loop'] is still None."""
    install_fake_slixmpp(monkeypatch)

    caplog.set_level(logging.WARNING, logger="apprise.xmpp")

    # Ensure adapter is enabled
    monkeypatch.setattr(
        xmpp_adapter.SlixmppAdapter, "_enabled", True, raising=True)

    # Gate used to block runner before it can assign shared["loop"].
    gate = threading.Event()

    # Patch asyncio.new_event_loop to block until we allow it, so
    # shared["loop"] remains None when the timeout clean-up executes.
    import asyncio as _real_asyncio
    orig_new_event_loop = _real_asyncio.new_event_loop

    def new_event_loop_blocking() -> _real_asyncio.AbstractEventLoop:
        gate.wait(timeout=1.0)
        return orig_new_event_loop()

    monkeypatch.setattr(
        xmpp_adapter.asyncio, "new_event_loop",
        new_event_loop_blocking, raising=True)

    # Make done.wait deterministic without touching real threading.Event used
    # by Thread internals.
    import threading as _real_threading

    class _FakeDoneEvent:
        def __init__(self) -> None:
            self._set = False
            self._wait_calls = 0

        def set(self) -> None:
            self._set = True

        def wait(self, timeout: float | None = None) -> bool:
            self._wait_calls += 1
            # Force timeout branch immediately on the first wait
            if self._wait_calls == 1:
                return False
            return self._set

    class _ThreadingProxy:
        Event = _FakeDoneEvent
        Thread = _real_threading.Thread

        def __getattr__(self, name: str) -> Any:
            return getattr(_real_threading, name)

    monkeypatch.setattr(
        xmpp_adapter, "threading", _ThreadingProxy(), raising=True)

    # Track whether any loop clean-up scheduling occurs.
    # It must NOT when loop_obj is None.
    called = {"disconnect": 0, "stop": 0}

    # Block connect so runner cannot complete before the timeout branch.
    def connect_blocks(
            self: FakeClientXMPP, **kw: Any) -> asyncio.Future[bool]:
        fut: asyncio.Future[bool] = self.loop.create_future()
        # Never resolve.
        return fut

    monkeypatch.setattr(
        FakeClientXMPP, "connect", connect_blocks, raising=True)

    # As an extra guard, if loop.call_soon_threadsafe were somehow reached,
    # we'd see it via this patch. Since loop_obj is None, it must not.
    def fake_disconnect(self: FakeClientXMPP) -> None:
        called["disconnect"] += 1

    monkeypatch.setattr(
        FakeClientXMPP, "disconnect", fake_disconnect, raising=True)

    config = xmpp_adapter.XMPPConfig(
        jid="me@example.com",
        password="x",
        host="example.com",
        port=5223,
        secure=xmpp_adapter.SecureXMPPMode.TLS,
        verify_certificate=False,
    )

    a = xmpp_adapter.SlixmppAdapter(
        config=config,
        targets=["a@example.com"],
        subject="s",
        body="b",
        timeout=5.0,
    )

    try:
        # done.wait is forced False immediately, and runner is blocked at
        # new_event_loop(), so shared['loop'] is None in the timeout clean-up.
        assert a.process() is False
        assert "XMPP send timed out" in caplog.text

        # No disconnect should have been scheduled because loop_obj was None.
        assert called["disconnect"] == 0

    finally:
        # Let the runner proceed and exit
        gate.set()


@pytest.mark.skipif(not SLIXMPP_AVAILABLE, reason="Requires slixmpp")
def test_xmpp_process_unsupported_secure_mode(
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture) -> None:
    """Cover unsupported secure mode path (ValueError inside runner)."""
    install_fake_slixmpp(monkeypatch)
    caplog.set_level(logging.WARNING, logger="apprise.xmpp")

    config = xmpp_adapter.XMPPConfig(
        jid="me@example.com",
        password="x",
        host="example.com",
        port=5222,
        secure="invalid",
        verify_certificate=False,
    )

    a = xmpp_adapter.SlixmppAdapter(
        config=config,
        targets=["a@example.com"],
        subject="s",
        body="b",
        timeout=5.0,
    )

    assert a.process() is False
    assert "XMPP send failed" in caplog.text


@pytest.mark.skipif(not SLIXMPP_AVAILABLE, reason="Requires slixmpp")
def test_xmpp_process_connect_timeout(
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture) -> None:
    """Cover connect timeout branch (asyncio.TimeoutError)."""
    install_fake_slixmpp(monkeypatch)
    caplog.set_level(logging.WARNING, logger="apprise.xmpp")

    # Return a Future that never resolves.
    connect_future: dict[str, Any] = {"fut": None}

    def connect_never(
            self: FakeClientXMPP, **kw: Any) -> asyncio.Future[bool]:
        fut: asyncio.Future[bool] = self.loop.create_future()
        connect_future["fut"] = fut
        return fut

    monkeypatch.setattr(
        FakeClientXMPP, "connect", connect_never, raising=True)

    # Force wait_for() to raise TimeoutError immediately for this connect
    # future.
    real_wait_for = xmpp_adapter.asyncio.wait_for

    def wait_for_patched(aw: Any, timeout: float | None = None) -> Any:
        if aw is connect_future["fut"]:
            raise asyncio.TimeoutError()
        return real_wait_for(aw, timeout=timeout)

    monkeypatch.setattr(
        xmpp_adapter.asyncio, "wait_for", wait_for_patched, raising=True)

    config = xmpp_adapter.XMPPConfig(
        jid="me@example.com",
        password="x",
        host="example.com",
        port=5222,
        secure=xmpp_adapter.SecureXMPPMode.STARTTLS,
        verify_certificate=False,
    )

    a = xmpp_adapter.SlixmppAdapter(
        config=config,
        targets=["a@example.com"],
        subject="s",
        body="b",
        timeout=5.0,
    )

    assert a.process() is False
    assert "XMPP connect timed out" in caplog.text


@pytest.mark.skipif(not SLIXMPP_AVAILABLE, reason="Requires slixmpp")
def test_xmpp_process_session_timeout(
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture) -> None:
    """Cover session timeout branch when waiting on client.disconnected."""
    install_fake_slixmpp(monkeypatch)
    caplog.set_level(logging.WARNING, logger="apprise.xmpp")

    # Ensure disconnect does not complete the disconnected Future.
    def disconnect_no_complete(self: FakeClientXMPP) -> None:
        return None

    monkeypatch.setattr(
        FakeClientXMPP, "disconnect", disconnect_no_complete, raising=True)

    # Capture the disconnected future created on the client
    real_init = FakeClientXMPP.__init__
    disconnected_future: dict[str, Any] = {"fut": None}

    def init_capture(self: FakeClientXMPP, jid: str, password: str) -> None:
        real_init(self, jid, password)
        disconnected_future["fut"] = self.disconnected

    monkeypatch.setattr(
        FakeClientXMPP, "__init__", init_capture, raising=True)

    # Force wait_for() to raise TimeoutError immediately for this disconnected
    # future.
    real_wait_for = xmpp_adapter.asyncio.wait_for

    def wait_for_patched(aw: Any, timeout: float | None = None) -> Any:
        if aw is disconnected_future["fut"]:
            raise asyncio.TimeoutError()
        return real_wait_for(aw, timeout=timeout)

    monkeypatch.setattr(
        xmpp_adapter.asyncio, "wait_for", wait_for_patched, raising=True)

    config = xmpp_adapter.XMPPConfig(
        jid="me@example.com",
        password="x",
        host="example.com",
        port=5222,
        secure=xmpp_adapter.SecureXMPPMode.STARTTLS,
        verify_certificate=False,
    )

    a = xmpp_adapter.SlixmppAdapter(
        config=config,
        targets=["a@example.com"],
        subject="s",
        body="b",
        timeout=5.0,
    )

    assert a.process() is False
    assert "XMPP session timed out" in caplog.text


def test_xmpp_slixmpp_versioning(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Simple checks to verify versioning works correctly
    """
    # Garbage in... garbage out
    assert xmpp_adapter.SlixmppAdapter.supported_version("garbage") is False
    # This version is too old
    assert xmpp_adapter.SlixmppAdapter.supported_version("1.0.0") is False

    # Good version checks
    assert xmpp_adapter.SlixmppAdapter.supported_version("1.10.0") is True
    assert xmpp_adapter.SlixmppAdapter.supported_version("1.10") is True
    assert xmpp_adapter.SlixmppAdapter.supported_version("1.10.1") is True
    assert xmpp_adapter.SlixmppAdapter.supported_version("1.10.100") is True
    assert xmpp_adapter.SlixmppAdapter.supported_version("1.11.0") is True

    # This version is too old
    assert xmpp_adapter.SlixmppAdapter.supported_version("1") is False

    # This version is good
    assert xmpp_adapter.SlixmppAdapter.supported_version("3") is True
    assert xmpp_adapter.SlixmppAdapter.supported_version("3.2") is True

    monkeypatch.setattr(
        xmpp_adapter, "SLIXMPP_SUPPORT_AVAILABLE", False, raising=False)
    monkeypatch.setattr(
        xmpp_adapter.SlixmppAdapter,
        "_enabled",
        False,
        raising=False,
    )
    assert xmpp_adapter.SlixmppAdapter.supported_version("3.2") is False

