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

"""Tests for IRC state machine."""

from __future__ import annotations

from apprise.plugins.irc.protocol import parse_irc_line
from apprise.plugins.irc.state import (
    IRCActionKind,
    IRCContext,
    IRCState,
    IRCStateMachine,
    _err,
)


def test_plugin_irc_state_err_trailing() -> None:
    """Error text from trailing."""
    msg = parse_irc_line(":srv 464 nick :bad pass")
    assert _err(msg) == "bad pass"


def test_plugin_irc_state_err_params() -> None:
    """Error text from params."""
    msg = parse_irc_line(":srv 471 nick #c")
    # no trailing, params join
    assert _err(msg) == "nick #c"


def test_plugin_irc_state_err_default() -> None:
    """Error text default."""
    msg = parse_irc_line(":srv 471")
    assert _err(msg) == "IRC error"


def test_plugin_irc_state_ignore_when_error_or_quitting() -> None:
    """Ignore messages when exiting."""
    ctx = IRCContext(desired_nick="n", accepted_nick="n", fullname="f")
    sm = IRCStateMachine(ctx)

    sm.state = IRCState.ERROR
    assert sm.on_message(parse_irc_line("PING :x")) == []

    sm.state = IRCState.QUITTING
    assert sm.on_message(parse_irc_line(":srv 001 n :welcome")) == []


def test_plugin_irc_state_register_error_sets_last_error() -> None:
    """Register errors fail."""
    ctx = IRCContext(desired_nick="n", accepted_nick="n", fullname="f")
    sm = IRCStateMachine(ctx)
    sm.start_registration()

    actions = sm.on_message(parse_irc_line(":srv 464 n :bad pass"))
    assert sm.state == IRCState.ERROR
    assert ctx.last_error is not None
    assert actions and actions[0].kind == IRCActionKind.FAIL
    assert "Password incorrect" in (actions[0].reason or "")


def test_plugin_irc_state_register_collision_433_sends_new_nick() -> None:
    """Nick collision 433."""
    ctx = IRCContext(desired_nick="new", accepted_nick="old", fullname="f")
    sm = IRCStateMachine(ctx)
    sm.start_registration()

    actions = sm.on_message(parse_irc_line(":srv 433 old :in use"))
    assert actions and actions[0].kind == IRCActionKind.SEND
    assert actions[0].line == "NICK new"


def test_plugin_irc_state_register_collision_432_sends_new_nick() -> None:
    """Nick collision 432."""
    ctx = IRCContext(desired_nick="new", accepted_nick="old", fullname="f")
    sm = IRCStateMachine(ctx)
    sm.start_registration()

    actions = sm.on_message(parse_irc_line(":srv 432 old :bad nick"))
    assert actions and actions[0].kind == IRCActionKind.SEND
    assert actions[0].line == "NICK new"


def test_plugin_irc_state_register_welcome_sets_accepted() -> None:
    """Welcome sets accepted nick."""
    ctx = IRCContext(desired_nick="n", accepted_nick="n", fullname="f")
    sm = IRCStateMachine(ctx)
    sm.start_registration()

    sm.on_message(parse_irc_line(":srv 001 nick :welcome"))
    assert ctx.accepted_nick == "nick"
    assert ctx.registered is True
    assert sm.state == IRCState.READY


def test_plugin_irc_state_register_welcome() -> None:
    """Welcome without nick keeps accepted."""
    ctx = IRCContext(desired_nick="n", accepted_nick="keep", fullname="f")
    sm = IRCStateMachine(ctx)
    sm.start_registration()

    # No nick in params, extract_welcome_nick() returns empty/None.
    sm.on_message(parse_irc_line(":srv 001 :welcome"))
    assert ctx.accepted_nick == "keep"
    assert ctx.registered is True
    assert sm.state == IRCState.READY


def test_plugin_irc_state_register_motd_done_before_registered() -> None:
    """MOTD sets motd_done."""
    ctx = IRCContext(desired_nick="n", accepted_nick="n", fullname="f")
    sm = IRCStateMachine(ctx)
    sm.start_registration()

    sm.on_message(parse_irc_line(":srv 422 n :MOTD missing"))
    assert ctx.motd_done is True
    assert sm.state == IRCState.REGISTERING


def test_plugin_irc_state_register_motd_done_376_before_registered() -> None:
    """MOTD 376 sets motd_done."""
    ctx = IRCContext(desired_nick="n", accepted_nick="n", fullname="f")
    sm = IRCStateMachine(ctx)
    sm.start_registration()

    sm.on_message(parse_irc_line(":srv 376 n :End of MOTD"))
    assert ctx.motd_done is True
    assert ctx.registered is False
    assert sm.state == IRCState.REGISTERING


def test_plugin_irc_state_register_motd_done_after_registered() -> None:
    """MOTD sets ready when registered."""
    ctx = IRCContext(desired_nick="n", accepted_nick="n", fullname="f")
    sm = IRCStateMachine(ctx)
    sm.start_registration()

    # This branch requires REGISTERING when 376/422 arrives.
    ctx.registered = True
    sm.state = IRCState.REGISTERING

    sm.on_message(parse_irc_line(":srv 376 n :End of MOTD"))
    assert ctx.motd_done is True
    assert sm.state == IRCState.READY


def test_plugin_irc_state_join_error_sets_last_error() -> None:
    """Join errors fail."""
    ctx = IRCContext(desired_nick="n", accepted_nick="n", fullname="f")
    sm = IRCStateMachine(ctx)
    sm.request_join("#c", key=None)

    actions = sm.on_message(parse_irc_line(":srv 475 n #c :Bad key"))
    assert sm.state == IRCState.ERROR
    assert ctx.last_error is not None
    assert actions and actions[0].kind == IRCActionKind.FAIL
    assert "Bad channel key" in (actions[0].reason or "")


def test_plugin_irc_state_join_numeric_366_adds_channel() -> None:
    """Join complete 366."""
    ctx = IRCContext(desired_nick="n", accepted_nick="n", fullname="f")
    sm = IRCStateMachine(ctx)
    sm.request_join("#c", key=None)

    sm.on_message(parse_irc_line(":srv 366 n #c :End of /NAMES list."))
    assert "#c" in ctx.joined
    assert sm.state == IRCState.READY


def test_plugin_irc_state_join_command_trailing() -> None:
    """Join complete JOIN trailing."""
    ctx = IRCContext(desired_nick="n", accepted_nick="n", fullname="f")
    sm = IRCStateMachine(ctx)
    sm.request_join("#c", key=None)

    sm.on_message(parse_irc_line(":nick!u@h JOIN :#c"))
    assert "#c" in ctx.joined
    assert sm.state == IRCState.READY


def test_plugin_irc_state_join_command_params() -> None:
    """Join complete JOIN params."""
    ctx = IRCContext(desired_nick="n", accepted_nick="n", fullname="f")
    sm = IRCStateMachine(ctx)
    sm.request_join("#c", key=None)

    sm.on_message(parse_irc_line(":nick!u@h JOIN #d"))
    assert "#d" in ctx.joined
    assert sm.state == IRCState.READY


def test_plugin_irc_state_request_join_key_and_no_key() -> None:
    """Join requests render."""
    ctx = IRCContext(desired_nick="n", accepted_nick="n", fullname="f")
    sm = IRCStateMachine(ctx)

    a1 = sm.request_join("#c", key=None)
    assert sm.state == IRCState.JOINING
    assert a1 and a1[0].line == "JOIN #c"

    a2 = sm.request_join("#c", key="k")
    assert a2 and a2[0].line == "JOIN #c k"


def test_plugin_irc_state_request_quit() -> None:
    """Quit request renders."""
    ctx = IRCContext(desired_nick="n", accepted_nick="n", fullname="f")
    sm = IRCStateMachine(ctx)

    actions = sm.request_quit("bye")
    assert sm.state == IRCState.QUITTING
    assert actions and actions[0].line == "QUIT :bye"


def test_plugin_irc_state_register_unhandled_numeric() -> None:
    """Register ignores unhandled numerics."""
    ctx = IRCContext(desired_nick="n", accepted_nick="n", fullname="f")
    sm = IRCStateMachine(ctx)
    sm.start_registration()

    # Numeric 2 is not handled by REGISTERING logic
    actions = sm.on_message(parse_irc_line(":srv 002 n :Your host is"))
    assert actions == []
    assert sm.state == IRCState.REGISTERING
    assert ctx.registered is False
    assert ctx.motd_done is False


def test_plugin_irc_state_join_command_empty_channel() -> None:
    """Join ignores empty JOIN channel."""
    ctx = IRCContext(desired_nick="n", accepted_nick="n", fullname="f")
    sm = IRCStateMachine(ctx)
    sm.request_join("#c", key=None)

    # JOIN with no params and no trailing yields empty channel
    actions = sm.on_message(parse_irc_line("JOIN"))
    assert actions == []
    assert ctx.joined == set()
    assert sm.state == IRCState.JOINING


def test_plugin_irc_state_ready_falls_through() -> None:
    """Ready falls through to default return."""
    ctx = IRCContext(desired_nick="n", accepted_nick="n", fullname="f")
    sm = IRCStateMachine(ctx)
    sm.state = IRCState.READY

    # Not handled in READY state, should return empty actions via final return
    actions = sm.on_message(parse_irc_line(":nick!u@h PRIVMSG #c :hi"))
    assert actions == []
    assert sm.state == IRCState.READY


def test_plugin_irc_state_join_non_join_command() -> None:
    """Join ignores non-JOIN commands."""
    ctx = IRCContext(desired_nick="n", accepted_nick="n", fullname="f")
    sm = IRCStateMachine(ctx)
    sm.request_join("#c", key=None)

    # Not a JOIN command, not a join numeric, and not an error
    actions = sm.on_message(parse_irc_line(":nick!u@h PRIVMSG #c :hi"))
    assert actions == []
    assert sm.state == IRCState.JOINING
    assert ctx.joined == set()
