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


def test_plugin_irc_init_mode_blank() -> None:
    """NotifyIRC rejects blank mode."""
    with (
            mock.patch.object(NotifyIRC, "apply_irc_defaults"),
            pytest.raises(TypeError)):
        NotifyIRC(host="irc.example.com", targets=["#c"], mode="   ")


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


def test_plugin_irc_parse_url() -> None:
    """NotifyIRC parse_url() behaviour with host= query."""
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
        host="irc.example.com", nickname="nick", fullname="full")
    client.transport = _DummyTransport()

    # join() and _tick() call monotonic frequently, provide lots of values.
    mono_values = [0.0] * 25 + [1.0]

    with (
        mock.patch.object(client, "_flush") as m_flush,
        mock.patch.object(client, "_handshake") as m_hs,
        mock.patch("time.monotonic", side_effect=mono_values),
    ):
        client.join(channel="#chan", timeout=0.01, prefix="ap", key=None)
        assert m_flush.called
        assert m_hs.called

    with mock.patch.object(client, "_write") as m_write:
        client.quit(message="bye", timeout=0.1)
        assert m_write.called


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
