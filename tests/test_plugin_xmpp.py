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
from types import SimpleNamespace
from typing import Any

import pytest

from apprise import Apprise, NotifyType
from apprise.plugins.xmpp import adapter as xmpp_adapter, base as xmpp_base
from apprise.plugins.xmpp.base import NotifyXMPP

# ---------------------------------------------------------------------------
# slixmpp availability handling (mirrors SMPP test pattern)
# ---------------------------------------------------------------------------

try:
    import slixmpp  # noqa: F401
    SLIXMPP_AVAILABLE = True
except Exception:
    SLIXMPP_AVAILABLE = False


# ---------------------------------------------------------------------------
# Fake slixmpp client
# ---------------------------------------------------------------------------

class FakeClientXMPP:
    def __init__(
        self, jid: str, password: str, loop: asyncio.AbstractEventLoop
    ) -> None:
        self.jid = jid
        self.password = password
        self.loop = loop
        self.handlers = {}
        self.auto_reconnect = True

    def add_event_handler(self, name: str, handler: Any) -> None:
        self.handlers[name] = handler

    def send_presence(self) -> None:
        pass

    async def get_roster(self) -> None:
        return None

    def send_message(self, **kwargs: Any) -> None:
        pass

    def disconnect(self) -> None:
        pass

    def connect(self, **kwargs: Any) -> bool:
        return True

    def process(self, forever: bool = False) -> None:
        handler = self.handlers.get("session_start")
        if handler:
            self.loop.run_until_complete(handler())


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
        xmpp_adapter.SlixmppSendOnceAdapter,
        "_enabled",
        True,
        raising=False,
    )


# ---------------------------------------------------------------------------
# NotifyXMPP tests
# ---------------------------------------------------------------------------

@pytest.mark.skipif(SLIXMPP_AVAILABLE, reason="Requires slixmpp NOT installed")
def test_xmpp_import_error() -> None:
    with pytest.raises(TypeError):
        NotifyXMPP(host="example.com", user="me@example.com", password="x")


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
        targets=["ok@example.com", " bad jid ", "", "also@example.net"],
    )

    # parse_list() tokenises on whitespace, so "bad jid" becomes two targets.
    # Empty values are dropped before they reach the validation loop, so no
    # warning is guaranteed for the empty string.
    assert sorted(n.targets) == [
        "also@example.net",
        "bad",
        "jid",
        "ok@example.com",
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
    assert len(n2) == 2


@pytest.mark.skipif(not SLIXMPP_AVAILABLE, reason="Requires slixmpp")
def test_xmpp_url_privacy() -> None:
    n = NotifyXMPP(
        host="example.com",
        user="me@example.com",
        password="secret",
        targets=["a@example.com"],
        verify_certificate=False,
    )
    u = n.url(privacy=True)
    assert "secret" not in u
    assert "verify=" in u


@pytest.mark.skipif(not SLIXMPP_AVAILABLE, reason="Requires slixmpp")
def test_xmpp_parse_url() -> None:
    r = NotifyXMPP.parse_url(
        "xmpps://me:pass@example.com/a@example.com?verify=no"
    )
    assert r["verify_certificate"] is False
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

    caplog.set_level(logging.WARNING)

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
def test_xmpp_url_no_targets_branch() -> None:
    """url() must not append a path when there are no targets."""
    apobj = Apprise()
    apobj.add("xmpp://me:secret@example.com?verify=no")

    assert len(apobj) == 1
    plugin = apobj[0]

    # Ensure we hit the url() branch where targets is empty.
    u = plugin.url(privacy=False)
    assert "example.com/" not in u
    assert "example.com?" in u


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
            body: str,
            subject: str,
            timeout: float,
            before_message: Any,
            logger: logging.Logger,
        ) -> None:
            captured["targets"] = targets
            captured["body"] = body
            captured["subject"] = subject

        def process(self) -> bool:
            return True

    monkeypatch.setattr(
        xmpp_base, "SlixmppSendOnceAdapter", _Adapter, raising=True)

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
    ctx = xmpp_adapter.SlixmppSendOnceAdapter._ssl_context(True)
    assert ctx.verify_mode != ssl.CERT_NONE

    ctx2 = xmpp_adapter.SlixmppSendOnceAdapter._ssl_context(False)
    assert ctx2.verify_mode == ssl.CERT_NONE
    assert ctx2.check_hostname is False


@pytest.mark.skipif(not SLIXMPP_AVAILABLE, reason="Requires slixmpp")
def test_xmpp_cancel_pending_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    loop = asyncio.new_event_loop()
    try:
        monkeypatch.setattr(
            asyncio, "all_tasks", lambda _: set(), raising=True)
        xmpp_adapter.SlixmppSendOnceAdapter._cancel_pending(loop)
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

        xmpp_adapter.SlixmppSendOnceAdapter._cancel_pending(loop)
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
    cfg = xmpp_adapter.XMPPConfig(
        jid="me@example.com",
        password="x",
        host="example.com",
        port=5223,
        secure=True,
        verify_certificate=True,
    )
    a = xmpp_adapter.SlixmppSendOnceAdapter(cfg, [], "b", "s", 1)
    monkeypatch.setattr(a, "_enabled", False, raising=True)
    assert a.process() is False


@pytest.mark.skipif(not SLIXMPP_AVAILABLE, reason="Requires slixmpp")
def test_xmpp_process_fail(
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture) -> None:
    install_fake_slixmpp(monkeypatch)
    caplog.set_level(logging.WARNING)

    def bad_connect(self: FakeClientXMPP, **kw: Any) -> bool:
        return False

    monkeypatch.setattr(FakeClientXMPP, "connect", bad_connect, raising=True)

    cfg = xmpp_adapter.XMPPConfig(
        jid="me@example.com",
        password="x",
        host="example.com",
        port=5223,
        secure=True,
        verify_certificate=True,
    )
    a = xmpp_adapter.SlixmppSendOnceAdapter(
        cfg, ["a@example.com"], "b", "s", 1)
    assert a.process() is False


@pytest.mark.skipif(not SLIXMPP_AVAILABLE, reason="Requires slixmpp")
def test_xmpp_process_success(monkeypatch: pytest.MonkeyPatch) -> None:
    install_fake_slixmpp(monkeypatch)
    cfg = xmpp_adapter.XMPPConfig(
        jid="me@example.com",
        password="x",
        host="example.com",
        port=5223,
        secure=True,
        verify_certificate=False,
    )
    a = xmpp_adapter.SlixmppSendOnceAdapter(
        cfg, ["a@example.com"], "b", "s", 1)
    assert a.process() is True


@pytest.mark.skipif(not SLIXMPP_AVAILABLE, reason="Requires slixmpp")
def test_xmpp_process_default_target(monkeypatch: pytest.MonkeyPatch) -> None:
    install_fake_slixmpp(monkeypatch)
    cfg = xmpp_adapter.XMPPConfig(
        jid="me@example.com",
        password="x",
        host="example.com",
        port=5223,
        secure=True,
        verify_certificate=False,
    )
    a = xmpp_adapter.SlixmppSendOnceAdapter(cfg, [], "b", "s", 1)
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

    cfg = xmpp_adapter.XMPPConfig(
        jid="me@example.com",
        password="x",
        host="example.com",
        port=5223,
        secure=True,
        verify_certificate=True,
    )
    a = xmpp_adapter.SlixmppSendOnceAdapter(
        cfg, ["a@example.com"], "b", "s", 1)
    assert a.process() is False


@pytest.mark.skipif(not SLIXMPP_AVAILABLE, reason="Requires slixmpp")
def test_xmpp_process_before_message(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure before_message callback is invoked for each target."""
    install_fake_slixmpp(monkeypatch)

    called: list[int] = []

    def before_message() -> None:
        called.append(1)

    cfg = xmpp_adapter.XMPPConfig(
        jid="me@example.com",
        password="x",
        host="example.com",
        port=5223,
        secure=True,
        verify_certificate=False,
    )
    a = xmpp_adapter.SlixmppSendOnceAdapter(
        cfg,
        ["a@example.com", "b@example.com"],
        "b",
        "s",
        1,
        before_message=before_message,
    )
    assert a.process() is True
    assert len(called) == 2


@pytest.mark.skipif(not SLIXMPP_AVAILABLE, reason="Requires slixmpp")
def test_xmpp_process_failed_auth_disconnect(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Authentication failure path must still call disconnect()."""
    install_fake_slixmpp(monkeypatch)

    # Force the FakeClientXMPP.process() method to trigger the failed_auth
    # handler.
    def process_failed_auth(
            self: FakeClientXMPP, forever: bool = False) -> None:
        handler = self.handlers.get("failed_auth")
        if handler:
            handler()

    monkeypatch.setattr(
        FakeClientXMPP, "process", process_failed_auth, raising=True)

    disconnected = {"called": False}

    def disconnect(self: FakeClientXMPP) -> None:
        disconnected["called"] = True

    monkeypatch.setattr(FakeClientXMPP, "disconnect", disconnect, raising=True)

    cfg = xmpp_adapter.XMPPConfig(
        jid="me@example.com",
        password="x",
        host="example.com",
        port=5223,
        secure=True,
        verify_certificate=False,
    )
    a = xmpp_adapter.SlixmppSendOnceAdapter(
        cfg, ["a@example.com"], "b", "s", 1)
    assert a.process() is True
    assert disconnected["called"] is True
