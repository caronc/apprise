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

"""Unit tests for Apprise IRC plugin and helper modules."""

from __future__ import annotations

import logging
import time
from typing import Any, Optional
from unittest import mock

import pytest

from apprise.plugins.irc import NotifyIRC
from apprise.plugins.irc.client import IRCClient
from apprise.plugins.irc.protocol import (
    IRCAuthMode,
    IRCMessage,
    extract_welcome_nick,
    is_ping,
    normalise_channel,
    parse_irc_line,
    ping_payload,
)
from apprise.plugins.irc.state import (
    IRCActionKind,
    IRCContext,
    IRCStateMachine,
)
from apprise.utils.socket import AppriseSocketError

# Disable logging for a cleaner testing output
logging.disable(logging.CRITICAL)


class _DummyTransport:
    """A lightweight SocketTransport stand-in for IRCClient tests."""

    def __init__(self) -> None:
        self.connected = False
        self.closed = False
        self.writes: list[bytes] = []
        self.reads: list[bytes] = []

    def connect(self) -> None:
        self.connected = True

    def close(self) -> None:
        self.closed = True

    def write(self, payload: bytes, *, flush: bool, timeout: float) -> None:
        self.writes.append(payload)

    def read(
        self,
        max_bytes: int,
        *,
        blocking: bool,
        timeout: Optional[float],
    ) -> bytes:
        if not self.reads:
            return b""
        chunk = self.reads.pop(0)
        return chunk[:max_bytes]


def test_plugin_irc_init_targets() -> None:
    """NotifyIRC parses targets."""
    with mock.patch.object(NotifyIRC, "apply_irc_defaults"):
        n = NotifyIRC(
            host="irc.example.com",
            targets=["#chan", "%23chan2:key", "@bob", "%40alice", "  bad# "],
        )

    assert "chan" in n.channels
    assert n.channels["chan"] is None
    assert "chan2" in n.channels
    assert n.channels["chan2"] == "key"
    assert "bob" in n.users
    assert "alice" in n.users


def test_plugin_irc_modes() -> None:
    """NotifyIRC auth mode tests."""
    with (
            mock.patch.object(NotifyIRC, "apply_irc_defaults"),
            pytest.raises(TypeError)):
        NotifyIRC(host="irc.example.com", targets=["#c"], mode="invalid")

    with mock.patch.object(NotifyIRC, "apply_irc_defaults"):
        # Case Insensitive
        result = NotifyIRC(
            host="irc.example.com", targets=["#c"], mode="NICKServ")
        assert "mode=nickserv" in result.url()

        # Case Insensitive
        result = NotifyIRC(
            host="irc.example.com", targets=["#c"], mode="server")
        assert "mode=" not in result.url()


def test_plugin_irc_defaults_port_noop() -> None:
    """NotifyIRC defaults are not applied when port is explicit."""
    n = NotifyIRC(host="irc.efnet.org", targets=["#c"], port=7000)
    n.apply_irc_defaults()
    assert n.port == 7000


def test_plugin_irc_defaults_template_match() -> None:
    """NotifyIRC defaults apply for known networks."""
    n = NotifyIRC(host="irc.synirc.net", targets=["#c"])
    assert n.secure is True
    assert n.port == 6697
    assert n.auth_mode == IRCAuthMode.NICKSERV


def test_plugin_irc_defaults_template_none() -> None:
    """NotifyIRC defaults do not force unknown networks."""
    n = NotifyIRC(host="irc.unknown.tld", targets=["#c"])
    assert n.secure is False


def test_plugin_irc_send_no_targets() -> None:
    """NotifyIRC send() rejects empty targets."""
    n = NotifyIRC(host="irc.example.com", targets=[])
    assert n.send("body") is False


def test_plugin_irc_send_ok() -> None:
    """NotifyIRC send() valid path."""
    n = NotifyIRC(
        host="irc.example.com",
        targets=["#chan:key", "@bob"],
        user="me",
        password="pw",
    )
    n.join = True

    client = mock.Mock(spec=IRCClient)
    client.nickname = "me"

    with mock.patch("apprise.plugins.irc.base.IRCClient", return_value=client):
        assert n.send("body", title="title") is True

    client.connect.assert_called_once()
    client.register.assert_called_once()
    client.join.assert_called_once()
    client.privmsg.assert_any_call(
        target="#chan",
        message="title body",
        timeout=mock.ANY,
    )
    client.privmsg.assert_any_call(
        target="bob",
        message="title body",
        timeout=mock.ANY,
    )
    client.quit.assert_called_once()
    client.close.assert_called_once()


def test_plugin_irc_send_no_join() -> None:
    """NotifyIRC avoids JOIN when join is false and no key is provided."""
    n = NotifyIRC(host="irc.example.com", targets=["#chan", "@bob"])
    n.join = False

    client = mock.Mock(spec=IRCClient)
    client.nickname = "x"

    with mock.patch("apprise.plugins.irc.base.IRCClient", return_value=client):
        assert n.send("body") is True

    client.join.assert_not_called()
    client.privmsg.assert_any_call(
        target="#chan",
        message="body",
        timeout=mock.ANY,
    )


def test_plugin_irc_send_error() -> None:
    """NotifyIRC returns False on connect errors."""
    n = NotifyIRC(host="irc.example.com", targets=["#chan"])
    client = mock.Mock(spec=IRCClient)
    client.connect.side_effect = AppriseSocketError("boom")

    with mock.patch("apprise.plugins.irc.base.IRCClient", return_value=client):
        assert n.send("body") is False

    client.close.assert_called_once()


def test_plugin_irc_url_id() -> None:
    """NotifyIRC url_identifier."""
    n = NotifyIRC(
        host="irc.example.com", targets=["#c"], user="me", password="pw")
    assert n.url_identifier == ("irc", "irc.example.com", "me", "pw")

    n.secure = True
    assert n.url_identifier[0] == "ircs"


def test_plugin_irc_url_format() -> None:
    """NotifyIRC url() basic rendering and privacy."""
    n = NotifyIRC(
        host="irc.example.com",
        targets=["#chan:key", "@bob"],
        user="me",
        password="pw",
        secure=False,
        port=IRCClient.default_insecure_port,
        nick="nick",
        name="Real Name",
        join=False,
        mode=IRCAuthMode.NICKSERV,
    )

    url = n.url(privacy=False)
    assert url.startswith("irc://me:pw@irc.example.com/")
    assert "#chan" in url
    assert "@bob" in url

    # Mode only appears when auth_mode is not SERVER.
    if n.auth_mode != IRCAuthMode.SERVER:
        assert "mode=nickserv" in url
    else:
        assert "mode=" not in url

    private = n.url(privacy=True)
    assert "pw" not in private
    assert "key" not in private

    n = NotifyIRC(
        host="irc.example.com",
        targets=["#chan", "@bob"],
        user="user2",
        secure=True,
        port=IRCClient.default_insecure_port,
        join=False,
        mode=IRCAuthMode.NICKSERV,
    )

    url = n.url(privacy=False)
    assert url.startswith("ircs://user2@irc.example.com:6667/")
    assert "#chan" in url
    assert "@bob" in url

    # Mode only appears when auth_mode is not SERVER.
    if n.auth_mode != IRCAuthMode.SERVER:
        assert "mode=nickserv" in url
    else:
        assert "mode=" not in url

    private = n.url(privacy=True)
    assert "pw" not in private
    assert "key" not in private


def test_plugin_irc_parse_url() -> None:
    """NotifyIRC parse_url() behaviour with host= query."""

    with mock.patch(
        "apprise.plugins.irc.base.NotifyBase.parse_url",
        return_value=None,
    ):
        results = NotifyIRC.parse_url("irc://%@@")
        assert results is None

    # host= indicates the URL host is a target, it does not override host.
    results = NotifyIRC.parse_url("irc://%23chan?host=irc.example.com")
    assert results is not None
    assert results["host"] == "%23chan"
    assert "#chan" in results["targets"]

    results = NotifyIRC.parse_url(
        "irc://irc.example.com/%23a/@b?to=%23c,@d"
        "&join=no&name=Z&nick=N&mode=none"
    )
    assert results is not None
    assert results["host"] == "irc.example.com"
    assert "#a" in results["targets"]
    assert "@b" in results["targets"]
    assert "#c" in results["targets"]
    assert "@d" in results["targets"]
    assert results["join"] is False
    assert results["name"] == "Z"
    assert results["nick"] == "N"
    assert results["mode"] == "none"


def test_plugin_irc_protocol() -> None:
    """Protocol helpers."""
    msg = parse_irc_line(":srv 001 nick :welcome")
    assert msg.numeric == 1
    assert extract_welcome_nick(msg) == "nick"

    ping = parse_irc_line("PING :abc")
    assert is_ping(ping) is True
    assert ping_payload(ping) == "abc"

    assert normalise_channel("chan") == "#chan"
    assert normalise_channel("#chan") == "#chan"
    assert normalise_channel("    ") == ""


def test_plugin_irc_state_machine() -> None:
    """State machine basics."""
    ctx = IRCContext(
        desired_nick="n", accepted_nick="n", fullname="f", password="pw")
    sm = IRCStateMachine(ctx)

    acts = sm.start_registration()
    assert any(
        a.kind == IRCActionKind.SEND and a.line and a.line.startswith("PASS ")
        for a in acts
    )

    sm.on_message(parse_irc_line(":srv 001 nick :welcome"))
    assert sm.ctx.registered is True
    assert sm.ctx.accepted_nick == "nick"

    ctx2 = IRCContext(
        desired_nick="n", accepted_nick="n", fullname="f", password="pw")
    sm2 = IRCStateMachine(ctx2)
    sm2.start_registration()
    fail = sm2.on_message(parse_irc_line(":srv 464 n :bad pass"))
    assert fail and fail[0].kind == IRCActionKind.FAIL

    ctx3 = IRCContext(desired_nick="n", accepted_nick="n", fullname="f")
    sm3 = IRCStateMachine(ctx3)
    sm3.start_registration()
    sm3.on_message(parse_irc_line(":srv 001 n :welcome"))
    sm3.request_join("#c", key=None)
    sm3.on_message(parse_irc_line(":srv 366 n #c :End of /NAMES list."))
    assert "#c" in sm3.ctx.joined


def test_plugin_irc_client_nick_handling() -> None:
    """IRCClient nickname handling."""
    nick0 = IRCClient.nick_generation(prefix="Apprise", length=9, collision=0)
    assert len(nick0) == 9

    nick1 = IRCClient.nick_generation(prefix="Apprise", length=9, collision=12)
    assert len(nick1) == 9
    assert nick1[-1].isdigit()

    client = IRCClient(
        host="irc.example.com",
        nickname="nick",
        fullname="full",
        nick_generator=None,
    )
    with pytest.raises(AppriseSocketError):
        client._nickname_collision_handler(prefix="x")

    def gen(prefix: str, length: int, collision: int) -> str:
        return f"{prefix}{collision}"

    client = IRCClient(
        host="irc.example.com",
        nickname="nick",
        fullname="full",
        nick_generator=gen,
    )
    client._nick_collision = int(client.nickname_collision_max)
    with pytest.raises(AppriseSocketError):
        client._nickname_collision_handler(prefix="x")


def test_plugin_irc_client_handshake() -> None:
    """IRCClient handshake error path."""
    def gen(prefix: str, length: int, collision: int) -> str:
        return "newnick"

    client = IRCClient(
        host="irc.example.com",
        nickname="nick",
        fullname="full",
        nick_generator=gen,
    )
    client.transport = _DummyTransport()

    # Put the state machine into REGISTERING so 464 triggers FAIL.
    client.sm.start_registration()

    lines = [
        "PING :abc",
        ":srv 433 nick :in use",
        ":srv 464 nick :bad pass",
        "",
    ]

    def _read(deadline: float) -> Optional[str]:
        return lines.pop(0)

    writes: list[str] = []

    def _write(line: Any, deadline: float) -> None:
        if isinstance(line, bytes):
            line = line.decode("utf-8", errors="replace")
        writes.append(str(line))

    with (
            mock.patch.object(client, "_read", side_effect=_read),
            mock.patch.object(client, "_write", side_effect=_write),
            pytest.raises(AppriseSocketError)):
        client._handshake(deadline=time.monotonic() + 1.0, prefix="ap")

    assert any(w.startswith("PONG") for w in writes)
    assert any(w.startswith("NICK ") for w in writes)


def test_plugin_irc_client_register() -> None:
    """IRCClient register timeout and success."""
    client = IRCClient(
        host="irc.example.com",
        nickname="nick",
        fullname="full",
        password="pw",
        auth_mode=IRCAuthMode.NICKSERV,
    )
    client.transport = _DummyTransport()

    with (mock.patch("time.monotonic", side_effect=[0.0, 1.0]),
          pytest.raises(TimeoutError)):
        client.register(timeout=0.01, prefix="ap")

    client2 = IRCClient(
        host="irc.example.com",
        nickname="nick",
        fullname="full",
        password="pw",
        auth_mode=IRCAuthMode.NICKSERV,
    )
    client2.transport = _DummyTransport()

    def _handshake(deadline: float, prefix: str) -> None:
        client2.sm.ctx.registered = True

    with (
        mock.patch.object(client2, "_flush"),
        mock.patch.object(client2, "_handshake", side_effect=_handshake),
        mock.patch.object(client2, "identify") as m_identify,
    ):
        client2.register(timeout=0.1, prefix="ap")
        m_identify.assert_called_once()


def test_plugin_irc_client_identify() -> None:
    """IRCClient identify early exits and send."""
    client = IRCClient(
        host="irc.example.com",
        nickname="nick",
        fullname="full",
        password=None,
        auth_mode=IRCAuthMode.NICKSERV,
    )
    client.transport = _DummyTransport()
    client.identify(timeout=0.1)

    client2 = IRCClient(
        host="irc.example.com",
        nickname="nick",
        fullname="full",
        password="pw",
        auth_mode=IRCAuthMode.SERVER,
    )
    client2.transport = _DummyTransport()
    client2.identify(timeout=0.1)

    client3 = IRCClient(
        host="irc.example.com",
        nickname="nick",
        fullname="full",
        password="pw",
        auth_mode=IRCAuthMode.NICKSERV,
    )
    client3.transport = _DummyTransport()
    with (
        mock.patch.object(client3, "_flush") as m_flush,
        mock.patch.object(client3, "_handshake") as m_hs,
    ):
        client3.identify(timeout=0.1)
        m_flush.assert_called_once()
        m_hs.assert_called_once()


def test_plugin_irc_client_join() -> None:
    """IRCClient join timeout path."""
    client = IRCClient(
        host="irc.example.com",
        nickname="nick",
        fullname="full",
    )
    client.transport = _DummyTransport()

    # join() calls monotonic frequently; use a callable so we never exhaust
    # a finite side_effect list.
    _calls = {"n": 0}

    def _mono() -> float:
        _calls["n"] += 1
        # Stay below deadline long enough to exercise the loop, then exceed it.
        return 0.0 if _calls["n"] < 2000 else 1.0

    with (
        mock.patch.object(client, "_flush") as m_flush,
        mock.patch.object(client, "_handshake") as m_hs,
        mock.patch("time.monotonic", side_effect=_mono),
    ):
        client.join(channel="#chan", timeout=0.01, prefix="ap", key=None)
        assert m_flush.called
        assert m_hs.called

    with mock.patch.object(client, "_write") as m_write:
        client.quit(message="bye", timeout=0.1)
        assert m_write.called


def test_plugin_irc_protocol_parse_blank_line() -> None:
    """Protocol parse blank input."""
    msg = parse_irc_line("   ")
    assert msg.command == ""
    assert msg.params == ()
    assert msg.trailing is None


def test_plugin_irc_protocol_parse_trailing_only() -> None:
    """Protocol parse trailing only."""
    msg = parse_irc_line(" :hello")
    assert msg.command == ""
    assert msg.params == ()
    assert msg.trailing == "hello"


def test_plugin_irc_message() -> None:
    """IRCMessage testing"""

    message = IRCMessage("raw", None, "not-a-number", ("a", "b"), None)
    assert message.numeric is None


def test_plugin_irc_protocol_ping_payload_from_params() -> None:
    """Ping payload from params."""
    msg = parse_irc_line("PING abc")
    assert msg.trailing is None
    assert msg.params == ("abc",)
    assert ping_payload(msg) == "abc"


def test_plugin_irc_protocol_extract_welcome_nick_non_welcome() -> None:
    """Welcome nick ignores non-001."""
    msg = parse_irc_line(":srv 002 nick :Your host is")
    assert msg.numeric == 2
    assert extract_welcome_nick(msg) is None


def test_plugin_irc_protocol_normalise_channel_empty() -> None:
    """Normalise empty channel."""
    assert normalise_channel("") == ""


def test_plugin_irc_client_props_and_io() -> None:
    """Client basics."""
    c = IRCClient(host="h", nickname="n", fullname="f")
    c.transport = mock.Mock()
    c.sm.ctx.accepted_nick = "nick"
    assert c.nickname == "nick"
    c.connect()
    c.close()
    c.transport.connect.assert_called_once()
    c.transport.close.assert_called_once()


def test_plugin_irc_client_write_timeout() -> None:
    """Write timeout."""
    c = IRCClient(host="h", nickname="n", fullname="f")
    c.transport = mock.Mock()
    with (mock.patch("time.monotonic", return_value=10.0),
          pytest.raises(TimeoutError)):
        c._write("X", deadline=9.0)


def test_plugin_irc_client_write_bytes_and_flush() -> None:
    """Write bytes and flush queue."""
    c = IRCClient(host="h", nickname="n", fullname="f")
    c.transport = mock.Mock()

    with mock.patch("time.monotonic", return_value=0.0):
        c._write(b"RAW", deadline=1.0)
        c.transport.write.assert_called_with(b"RAW", flush=True, timeout=1.0)

    c.transport.write.reset_mock()
    c._queue("A")
    c._queue("B")
    with mock.patch.object(c, "_write") as m_write:
        c._flush(deadline=1.0)
        assert m_write.call_count == 2
        assert len(c._out_queue) == 0


def test_plugin_irc_client_read_buffer_and_timeout() -> None:
    """Read buffer and timeout."""
    c = IRCClient(host="h", nickname="n", fullname="f")
    c.transport = mock.Mock()

    c._inbuf = bytearray(b"hello\r\n")
    assert c._read(deadline=time.monotonic() + 1.0) == "hello"

    c._inbuf = bytearray()
    with mock.patch("time.monotonic", return_value=10.0):
        assert c._read(deadline=9.0) is None


def test_plugin_irc_client_read_transport_paths() -> None:
    """Read from transport."""
    c = IRCClient(host="h", nickname="n", fullname="f")
    c.transport = mock.Mock()

    with mock.patch("time.monotonic", return_value=0.0):
        c.transport.read.return_value = b""
        assert c._read(deadline=1.0) is None

    c = IRCClient(host="h", nickname="n", fullname="f")
    c.transport = mock.Mock()
    with mock.patch("time.monotonic", side_effect=[0.0, 0.0, 0.0]):
        c.transport.read.side_effect = [b"he", b"llo\n"]
        assert c._read(deadline=1.0) == "hello"


def test_plugin_irc_client_tick() -> None:
    """Tick timing."""
    c = IRCClient(host="h", nickname="n", fullname="f")
    with mock.patch("time.monotonic", return_value=10.0):
        assert c._tick(deadline=9.0) == 9.0

    with mock.patch("time.monotonic", return_value=0.0):
        # remaining=0.5 -> 0.0 + 0.5
        assert c._tick(deadline=0.5) == 0.5


def test_plugin_irc_client_handshake_paths() -> None:
    """Handshake paths."""
    c = IRCClient(host="h", nickname="n", fullname="f")
    c.transport = mock.Mock()

    with mock.patch.object(c, "_read", return_value=None):
        c._handshake(deadline=time.monotonic() + 1.0, prefix="")

    lines = ["PING :abc", ""]
    with (
        mock.patch.object(
            c, "_read", side_effect=lambda deadline: lines.pop(0)),
        mock.patch.object(c, "_write") as m_write,
    ):
        c._handshake(deadline=time.monotonic() + 1.0, prefix="")
        m_write.assert_any_call("PONG :abc", deadline=mock.ANY)

    lines = [":srv 433 n :in use", ""]
    with (
        mock.patch.object(
            c, "_read", side_effect=lambda deadline: lines.pop(0)),
        mock.patch.object(
            c, "_nickname_collision_handler", return_value="new"),
        mock.patch.object(c, "_write") as m_write,
    ):
        c._handshake(deadline=time.monotonic() + 1.0, prefix="ap")
        m_write.assert_any_call("NICK new", deadline=mock.ANY)

    # FAIL action raises
    from apprise.plugins.irc.state import IRCAction, IRCActionKind
    lines = [":srv 464 n :bad pass", ""]
    with (
        mock.patch.object(
            c, "_read", side_effect=lambda deadline: lines.pop(0)),
        mock.patch.object(c.sm, "on_message", return_value=[
            IRCAction(IRCActionKind.FAIL, reason="boom")
        ]),
        pytest.raises(AppriseSocketError),
    ):
        c._handshake(deadline=time.monotonic() + 1.0, prefix="")

    # SEND action writes line
    lines = [":srv 001 n :welcome", ""]
    with (
        mock.patch.object(
            c, "_read", side_effect=lambda deadline: lines.pop(0)),
        mock.patch.object(c.sm, "on_message", return_value=[
            IRCAction(IRCActionKind.SEND, line="NICK x")
        ]),
        mock.patch.object(c, "_write") as m_write,
    ):
        c._handshake(deadline=time.monotonic() + 1.0, prefix="")
        m_write.assert_any_call("NICK x", deadline=mock.ANY)


def test_plugin_irc_client_register_auth_modes() -> None:
    """Register auth modes."""
    c = IRCClient(
        host="h",
        nickname="n",
        fullname="f",
        password="pw",
        auth_mode=IRCAuthMode.NICKSERV,
    )
    c.transport = mock.Mock()

    # Force loop to exit by setting registered in handshake
    def _hs(deadline: float, prefix: str) -> None:
        c.sm.ctx.registered = True

    with (
        mock.patch.object(c, "_flush"),
        mock.patch.object(c, "_handshake", side_effect=_hs),
        mock.patch.object(c, "identify") as m_ident,
        mock.patch("time.monotonic", return_value=0.0),
        mock.patch("time.time", side_effect=[0.0, 0.1, 0.2]),
    ):
        c.register(timeout=1.0, prefix="ap")
        # password cleared before registration when not SERVER
        assert c.sm.ctx.password is None
        m_ident.assert_called_once()

    c2 = IRCClient(
        host="h",
        nickname="n",
        fullname="f",
        password="pw",
        auth_mode=IRCAuthMode.SERVER,
    )
    c2.transport = mock.Mock()

    def _hs2(deadline: float, prefix: str) -> None:
        c2.sm.ctx.registered = True

    with (
        mock.patch.object(c2, "_flush"),
        mock.patch.object(c2, "_handshake", side_effect=_hs2),
        mock.patch.object(c2, "identify") as m_ident2,
        mock.patch("time.monotonic", return_value=0.0),
        mock.patch("time.time", side_effect=[0.0, 0.1, 0.2]),
    ):
        c2.register(timeout=1.0, prefix="ap")
        # identify not called for SERVER
        m_ident2.assert_not_called()


def test_plugin_irc_client_join_privmsg_identify_quit() -> None:
    """Join and message helpers."""
    c = IRCClient(
        host="h",
        nickname="n",
        fullname="f",
        password="pw",
        auth_mode=IRCAuthMode.NICKSERV,
    )
    c.transport = mock.Mock()

    _calls = {"n": 0}

    def _mono() -> float:
        _calls["n"] += 1
        # Return 0.0 long enough to enter the loop, then jump past deadline
        # to ensure join() exits.
        return 0.0 if _calls["n"] < 5000 else 1.0

    with (
        mock.patch.object(c, "_flush") as m_flush,
        mock.patch.object(c, "_handshake") as m_hs,
        mock.patch("time.monotonic", side_effect=_mono),
    ):
        # join never confirmed -> debug path
        with mock.patch("apprise.plugins.irc.client.logger.debug") as m_dbg:
            c.join(channel="#c", timeout=0.01, prefix="ap", key=None)
            m_dbg.assert_called()

        assert m_flush.called
        assert m_hs.called

    # privmsg() and identify() also call monotonic; keep them in a separate
    # context with a simple stable time.
    with (
        mock.patch.object(c, "_flush") as m_flush2,
        mock.patch.object(c, "_handshake") as m_hs2,
        mock.patch("time.monotonic", return_value=0.0),
    ):
        c.privmsg(target="#c", message="m", timeout=0.1)
        c.identify(timeout=0.1)
        assert m_flush2.called
        assert m_hs2.called

    # identify exits early
    c2 = IRCClient(
        host="h",
        nickname="n",
        fullname="f",
        password=None,
        auth_mode=IRCAuthMode.NICKSERV,
    )
    c2.transport = mock.Mock()
    with mock.patch.object(c2, "_flush") as m_flush3:
        c2.identify(timeout=0.1)
        m_flush3.assert_not_called()

    c3 = IRCClient(
        host="h",
        nickname="n",
        fullname="f",
        password="pw",
        auth_mode=IRCAuthMode.SERVER,
    )
    c3.transport = mock.Mock()
    with mock.patch.object(c3, "_flush") as m_flush4:
        c3.identify(timeout=0.1)
        m_flush4.assert_not_called()

    # quit queues and flushes
    c4 = IRCClient(host="h", nickname="n", fullname="f")
    c4.transport = mock.Mock()
    with mock.patch.object(c4, "_flush") as m_flush5:
        c4.quit(message="bye", timeout=0.1)
        m_flush5.assert_called_once()


def test_plugin_irc_client_nick_generation_default_length() -> None:
    """Nick generation defaults."""
    nick = IRCClient.nick_generation(prefix="Ap", length=None, collision=0)
    assert len(nick) == IRCClient.nickname_max_length


def test_plugin_irc_client_write_trace() -> None:
    """Write trace logging."""
    c = IRCClient(host="h", nickname="n", fullname="f")
    c.transport = mock.Mock()

    with (
        mock.patch("time.monotonic", return_value=0.0),
        mock.patch(
            "apprise.plugins.irc.client.logger.isEnabledFor",
            return_value=True),
        mock.patch(
            "apprise.plugins.irc.client.logger.trace") as m_trace,
    ):
        c._write("HELLO", deadline=1.0)
        m_trace.assert_called_once()
        # Ensure we wrote CRLF terminated bytes
        c.transport.write.assert_called_once()
        payload = c.transport.write.call_args.args[0]
        assert payload.endswith(b"\r\n")


def test_plugin_irc_client_handshake_send_without_line() -> None:
    """Handshake ignores empty SEND."""
    c = IRCClient(host="h", nickname="n", fullname="f")
    c.transport = mock.Mock()

    from apprise.plugins.irc.state import IRCAction, IRCActionKind

    # One message then stop the loop
    lines = [":srv 001 n :welcome", ""]
    with (
        mock.patch.object(
            c, "_read", side_effect=lambda deadline: lines.pop(0)),
        mock.patch.object(c.sm, "on_message", return_value=[
            IRCAction(IRCActionKind.SEND, line="")
        ]),
        mock.patch.object(c, "_write") as m_write,
    ):
        c._handshake(deadline=time.monotonic() + 1.0, prefix="")
        m_write.assert_not_called()


def test_plugin_irc_client_register_queue_ignores_empty_send() -> None:
    """Register ignores empty SEND."""
    c = IRCClient(
        host="h", nickname="n", fullname="f", auth_mode=IRCAuthMode.NONE)
    c.transport = mock.Mock()

    from apprise.plugins.irc.state import IRCAction, IRCActionKind

    with (
        mock.patch.object(c.sm, "start_registration", return_value=[
            IRCAction(IRCActionKind.SEND, line=None),
            IRCAction(IRCActionKind.SEND, line=""),
        ]),
        mock.patch.object(c, "_queue") as m_queue,
        mock.patch.object(c, "_flush"),
        mock.patch.object(c, "_handshake"),
        mock.patch("time.monotonic", return_value=0.0),
        mock.patch("time.time", return_value=0.0),
    ):
        # Make it "already registered" to avoid the while loop behaviour
        c.sm.ctx.registered = True
        c.register(timeout=0.1, prefix="ap")
        m_queue.assert_not_called()


def test_plugin_irc_client_join_queue_ignores_empty_send() -> None:
    """Join ignores empty SEND."""
    c = IRCClient(host="h", nickname="n", fullname="f")
    c.transport = mock.Mock()

    from apprise.plugins.irc.state import IRCAction, IRCActionKind

    with (
        mock.patch.object(c.sm, "request_join", return_value=[
            IRCAction(IRCActionKind.SEND, line=None),
            IRCAction(IRCActionKind.SEND, line=""),
        ]),
        mock.patch.object(c, "_queue") as m_queue,
        mock.patch.object(c, "_flush"),
        mock.patch.object(c, "_handshake"),
        mock.patch("time.monotonic", return_value=1.0),
    ):
        # deadline will be 1.0 + timeout, but we also ensure we do not enter
        # loop by setting joined to include channel.
        c.sm.ctx.joined.add("#c")
        c.join(channel="#c", timeout=0.1, prefix="ap", key=None)
        m_queue.assert_not_called()


def test_plugin_irc_client_quit_queue_ignores_empty_send() -> None:
    """Quit ignores empty SEND."""
    c = IRCClient(host="h", nickname="n", fullname="f")
    c.transport = mock.Mock()

    from apprise.plugins.irc.state import IRCAction, IRCActionKind

    with (
        mock.patch.object(c.sm, "request_quit", return_value=[
            IRCAction(IRCActionKind.SEND, line=None),
            IRCAction(IRCActionKind.SEND, line=""),
        ]),
        mock.patch.object(c, "_queue") as m_queue,
        mock.patch.object(c, "_flush") as m_flush,
        mock.patch("time.monotonic", return_value=0.0),
    ):
        c.quit(message="bye", timeout=0.1)
        m_queue.assert_not_called()
        m_flush.assert_called_once()
