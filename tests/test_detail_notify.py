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

"""Tests for Apprise.notify(detailed=True) / async_notify(detailed=True).

Covers:
  - Return type and dict keys
  - Success / failure / exception per URL
  - Tag filtering (only matched URLs appear)
  - No-match returns empty list
  - Invalid call returns empty list (not False)
  - Backward-compat: detailed=False still returns bool/None
  - Log message captured in "detail" field
  - Parallel threadpool path (_notify_parallel_threadpool_detailed)
  - Async path (async_notify with detailed=True)
  - Per-instance logger isolation under parallel execution
"""

import asyncio
import logging
from unittest import mock

from apprise import Apprise

try:
    from helpers import OuterEventLoop
except ImportError:
    import contextlib

    @contextlib.contextmanager
    def OuterEventLoop():
        loop = asyncio.new_event_loop()
        try:
            yield loop
        finally:
            loop.close()


# Keep test output clean
logging.disable(logging.CRITICAL)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
APPRISE_LOGGER = logging.getLogger("apprise")

REQUIRED_KEYS = {"url", "success", "timestamp", "detail"}


def _make_plugin(tag, url, notify_result, *, raises=None, async_mode=False):
    """Return a minimal mock plugin accepted by Apprise._notify_*."""
    p = mock.MagicMock()
    p.tags = {tag} if tag else set()
    p.asset.async_mode = async_mode
    p.asset.abort_on_chain_failure = False
    p.url.return_value = url
    p.notify_format = "text"
    p.title_maxlen = 100
    p.interpret_emojis = False
    p.retry = 0
    p.wait = 0
    p.optional = False
    p.service_name = url

    if raises:
        p.notify.side_effect = raises
        p.async_notify = mock.AsyncMock(side_effect=raises)
    else:
        p.notify.return_value = notify_result
        p.async_notify = mock.AsyncMock(return_value=notify_result)

    return p


def _apprise_with(*plugins):
    a = Apprise()
    a.servers = list(plugins)
    return a


# ---------------------------------------------------------------------------
# Return-type and key structure
# ---------------------------------------------------------------------------


def test_detailed_returns_list():
    """detailed=True must return a list, not a bool."""
    p = _make_plugin("x", "json://host/", True)
    a = _apprise_with(p)
    result = a.notify("body", tag="x", detailed=True)
    assert isinstance(result, list)


def test_detailed_result_keys():
    """Every element must contain exactly the required keys."""
    p = _make_plugin("x", "json://host/", True)
    a = _apprise_with(p)
    results = a.notify("body", tag="x", detailed=True)
    assert len(results) == 1
    assert set(results[0].keys()) == REQUIRED_KEYS


def test_detailed_timestamp_is_iso8601():
    """timestamp field must be a non-empty ISO-8601 string."""
    from datetime import datetime

    p = _make_plugin("x", "json://host/", True)
    a = _apprise_with(p)
    results = a.notify("body", tag="x", detailed=True)
    ts = results[0]["timestamp"]
    assert isinstance(ts, str) and ts
    # Must parse without error
    datetime.fromisoformat(ts)
    # Must be UTC-aware
    dt = datetime.fromisoformat(ts)
    assert dt.tzinfo is not None
    assert dt.utcoffset().total_seconds() == 0


# ---------------------------------------------------------------------------
# Success / failure / exception
# ---------------------------------------------------------------------------


def test_detailed_success():
    """Successful delivery: success=True, detail=''."""
    p = _make_plugin("x", "slack://token/ch", True)
    a = _apprise_with(p)
    results = a.notify("body", tag="x", detailed=True)
    assert results[0]["success"] is True
    assert results[0]["detail"] == ""


def test_detailed_failure_silent():
    """Plugin returns False without logging: success=False, detail
    non-empty."""
    p = _make_plugin("x", "tgram://bot/chat", False)
    a = _apprise_with(p)
    results = a.notify("body", tag="x", detailed=True)
    assert results[0]["success"] is False
    assert isinstance(results[0]["detail"], str)
    assert results[0]["detail"] != ""


def test_detailed_failure_with_log_message():
    """Plugin logs a warning then returns False: detail captures the message.

    Uses a real object (not MagicMock) so that the instance-level logger
    override set by _capture_server_logs is actually used by notify().
    """

    class FakePlugin:
        """Minimal real plugin whose notify() logs via self.logger."""

        tags = {"x"}
        retry = 0
        wait = 0
        optional = False
        service_name = "FakePlugin"
        notify_format = "text"
        title_maxlen = 100
        interpret_emojis = False
        logger = logging.getLogger("apprise")

        class asset:
            async_mode = False
            abort_on_chain_failure = False

        def url(self, privacy=False):
            return "fake://host/"

        def notify(self, **kw):
            self.logger.warning("HTTP 403 Forbidden")
            return False

    # Re-enable WARNING for this test so _capture_server_logs can receive it.
    logging.disable(logging.NOTSET)
    try:
        a = _apprise_with(FakePlugin())
        results = a.notify("body", tag="x", detailed=True)
    finally:
        logging.disable(logging.CRITICAL)

    assert results[0]["success"] is False
    assert "403" in results[0]["detail"]


def test_detailed_exception():
    """Unhandled exception from plugin: success=False, detail has exc info."""
    p = _make_plugin(
        "x",
        "discord://wid/tok",
        False,
        raises=RuntimeError("SSL failed"),
    )
    a = _apprise_with(p)
    results = a.notify("body", tag="x", detailed=True)
    assert results[0]["success"] is False
    assert "SSL failed" in results[0]["detail"]


def test_detailed_type_error():
    """TypeError from plugin surfaces in detail field."""
    p = _make_plugin("x", "json://host/", False)
    p.notify.side_effect = TypeError("bad argument")
    a = _apprise_with(p)
    results = a.notify("body", tag="x", detailed=True)
    assert results[0]["success"] is False
    assert "bad argument" in results[0]["detail"]


# ---------------------------------------------------------------------------
# Multiple URLs — all attempted
# ---------------------------------------------------------------------------


def test_detailed_all_urls_attempted():
    """detailed=True must attempt every matched URL, no early exit."""
    p1 = _make_plugin("x", "slack://t/ch", True)
    p2 = _make_plugin("x", "tgram://b/c", False)
    p3 = _make_plugin("x", "discord://w/t", True)
    a = _apprise_with(p1, p2, p3)
    results = a.notify("body", tag="x", detailed=True)
    assert len(results) == 3
    assert results[0]["success"] is True
    assert results[1]["success"] is False
    assert results[2]["success"] is True


# ---------------------------------------------------------------------------
# Tag filtering
# ---------------------------------------------------------------------------


def test_detailed_tag_filtering():
    """Only URLs matching the tag appear in the result list."""
    p_alerts = _make_plugin("alerts", "slack://t/ch", True)
    p_debug = _make_plugin("debug", "discord://w/t", True)
    a = _apprise_with(p_alerts, p_debug)
    results = a.notify("body", tag="alerts", detailed=True)
    assert len(results) == 1
    assert "slack" in results[0]["url"]
    # The debug plugin must not have been called
    p_debug.notify.assert_not_called()


def test_detailed_no_match_returns_empty_list():
    """Tag that matches nothing returns [] (not None or False)."""
    p = _make_plugin("alerts", "slack://t/ch", True)
    a = _apprise_with(p)
    result = a.notify("body", tag="nonexistent", detailed=True)
    assert result == []


def test_detailed_no_servers_returns_empty_list():
    """No servers at all: returns [] not None."""
    a = Apprise()
    result = a.notify("body", detailed=True)
    assert result == []


# ---------------------------------------------------------------------------
# Invalid call
# ---------------------------------------------------------------------------


def test_detailed_invalid_body_returns_empty_list():
    """Body that triggers TypeError returns [] instead of False."""
    p = _make_plugin("x", "json://host/", True)
    a = _apprise_with(p)
    # Patch _create_notify_gen to raise TypeError (simulates bad input)
    with mock.patch.object(a, "_create_notify_gen", side_effect=TypeError):
        result = a.notify("body", tag="x", detailed=True)
    assert result == []


# ---------------------------------------------------------------------------
# Backward compatibility
# ---------------------------------------------------------------------------


def test_detailed_false_returns_bool_on_success():
    """detailed=False (default): all succeed → True."""
    p = _make_plugin("x", "json://host/", True)
    a = _apprise_with(p)
    assert a.notify("body", tag="x") is True


def test_detailed_false_returns_bool_on_failure():
    """detailed=False (default): any failure → False."""
    p = _make_plugin("x", "json://host/", False)
    a = _apprise_with(p)
    assert a.notify("body", tag="x") is False


def test_detailed_false_returns_none_on_no_match():
    """detailed=False (default): no match → None."""
    p = _make_plugin("alerts", "json://host/", True)
    a = _apprise_with(p)
    assert a.notify("body", tag="nonexistent") is None


# ---------------------------------------------------------------------------
# Parallel threadpool path
# ---------------------------------------------------------------------------


def test_detailed_parallel_all_attempted():
    """Threadpool path: all URLs attempted and results ordered correctly."""
    p1 = _make_plugin("x", "slack://t/ch", True, async_mode=True)
    p2 = _make_plugin("x", "tgram://b/c", False, async_mode=True)
    p3 = _make_plugin("x", "discord://w/t", True, async_mode=True)

    # Force threadpool path by using async_mode=False (threadpool handles them)
    for p in (p1, p2, p3):
        p.asset.async_mode = False

    a = _apprise_with(p1, p2, p3)
    results = a.notify("body", tag="x", detailed=True)
    assert len(results) == 3
    urls = [r["url"] for r in results]
    assert "slack://t/ch" in urls
    assert "tgram://b/c" in urls
    assert "discord://w/t" in urls
    successes = {r["url"]: r["success"] for r in results}
    assert successes["slack://t/ch"] is True
    assert successes["tgram://b/c"] is False
    assert successes["discord://w/t"] is True


def test_detailed_parallel_log_isolation():
    """Each URL's log message must be attributed to the correct URL only.

    Two plugins run concurrently; each logs a distinct warning message.
    The detail field of each result must contain only that plugin's message.
    Uses real objects (not MagicMock) so instance-level logger override
    set by _capture_server_logs is actually used.
    """
    import time

    class SlackPlugin:
        tags = {"x"}
        retry = 0
        wait = 0
        optional = False
        service_name = "Slack"
        notify_format = "text"
        title_maxlen = 100
        interpret_emojis = False
        logger = logging.getLogger("apprise")

        class asset:
            async_mode = False
            abort_on_chain_failure = False

        def url(self, privacy=False):
            return "slack://parallel"

        def notify(self, **kw):
            time.sleep(0.05)
            self.logger.warning("Slack: rate limited 429")
            return False

    class DiscordPlugin:
        tags = {"x"}
        retry = 0
        wait = 0
        optional = False
        service_name = "Discord"
        notify_format = "text"
        title_maxlen = 100
        interpret_emojis = False
        logger = logging.getLogger("apprise")

        class asset:
            async_mode = False
            abort_on_chain_failure = False

        def url(self, privacy=False):
            return "discord://parallel"

        def notify(self, **kw):
            self.logger.warning("Discord: invalid webhook 404")
            return False

    # Re-enable WARNING for this test so _capture_server_logs can receive it.
    logging.disable(logging.NOTSET)
    try:
        a = _apprise_with(SlackPlugin(), DiscordPlugin())
        results = a.notify("body", tag="x", detailed=True)
    finally:
        logging.disable(logging.CRITICAL)

    result_map = {r["url"]: r for r in results}
    assert "429" in result_map["slack://parallel"]["detail"]
    assert "404" in result_map["discord://parallel"]["detail"]
    # Cross-contamination check
    assert "404" not in result_map["slack://parallel"]["detail"]
    assert "429" not in result_map["discord://parallel"]["detail"]


# ---------------------------------------------------------------------------
# Async path
# ---------------------------------------------------------------------------


def test_detailed_async_notify():
    """async_notify(detailed=True) returns the same structure as notify()."""
    p = _make_plugin("x", "slack://t/ch", True)
    a = _apprise_with(p)

    with OuterEventLoop() as loop:
        results = loop.run_until_complete(
            a.async_notify("body", tag="x", detailed=True)
        )
    assert isinstance(results, list)
    assert len(results) == 1
    assert set(results[0].keys()) == REQUIRED_KEYS
    assert results[0]["success"] is True
    assert results[0]["detail"] == ""


def test_detailed_async_notify_failure():
    """async_notify(detailed=True): failed plugin captured correctly."""
    p = _make_plugin("x", "discord://w/t", False)
    p.async_notify = mock.AsyncMock(
        side_effect=RuntimeError("async connection refused")
    )
    p.asset.async_mode = True
    a = _apprise_with(p)

    with OuterEventLoop() as loop:
        results = loop.run_until_complete(
            a.async_notify("body", tag="x", detailed=True)
        )
    assert results[0]["success"] is False
    assert "async connection refused" in results[0]["detail"]


def test_detailed_async_no_match_returns_empty_list():
    """async_notify(detailed=True): no match → []."""
    p = _make_plugin("alerts", "slack://t/ch", True)
    a = _apprise_with(p)

    with OuterEventLoop() as loop:
        result = loop.run_until_complete(
            a.async_notify("body", tag="nonexistent", detailed=True)
        )
    assert result == []


# ---------------------------------------------------------------------------
# _capture_server_logs does not break non-detailed notify
# ---------------------------------------------------------------------------


def test_capture_server_logs_does_not_affect_normal_notify():
    """_capture_server_logs context manager must restore server.logger
    so that subsequent non-detailed notify() calls work correctly."""
    p = _make_plugin("x", "json://host/", True)
    a = _apprise_with(p)

    # First call: detailed=True (attaches and detaches per-instance logger)
    a.notify("body", tag="x", detailed=True)

    # Second call: detailed=False must still work normally
    p.notify.return_value = True
    result = a.notify("body", tag="x")
    assert result is True


def test_capture_server_logs_restores_class_logger():
    """After detailed notify, server.logger must be the class-level logger
    again (not an instance override)."""

    p = _make_plugin("x", "json://host/", True)
    a = _apprise_with(p)
    a.notify("body", tag="x", detailed=True)

    # Instance __dict__ must not contain 'logger' after the call
    assert "logger" not in p.__dict__
