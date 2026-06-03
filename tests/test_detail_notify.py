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
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
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

Routing note: asset.async_mode=True  → _notify_parallel_threadpool_detailed
              asset.async_mode=False → _notify_sequential_detailed

Covers:
  - Return type and dict keys
  - Success / failure / exception per URL
  - Tag filtering (only matched URLs appear)
  - No-match / no-server returns empty list
  - Invalid call (TypeError) returns empty list (not False)
  - Backward-compat: detailed=False still returns bool/None
  - Log message captured in "detail" field
  - Sequential detailed: retry, wait, optional failure
  - Threadpool detailed (async_mode=True servers via sync notify())
  - Threadpool detailed: n_calls==0 and n_calls==1 fast paths
  - Threadpool detailed: TypeError, unhandled Exception, retry, wait, optional
  - Threadpool detailed: future.result() raising (outer exception handler)
  - Mixed sequential+threadpool batch with detailed=True
  - Async path: async_notify(detailed=True) success/failure/no-match/TypeError
  - Async path: empty servers, retry, wait, optional, gather exception
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
    """Return a minimal mock plugin accepted by Apprise._notify_*.

    async_mode=True  → routed to _notify_parallel_threadpool_detailed
    async_mode=False → routed to _notify_sequential_detailed
    """
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
    datetime.fromisoformat(ts)
    dt = datetime.fromisoformat(ts)
    assert dt.tzinfo is not None
    assert dt.utcoffset().total_seconds() == 0


# ---------------------------------------------------------------------------
# Success / failure / exception  (sequential path, async_mode=False)
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
        "x", "discord://wid/tok", False, raises=RuntimeError("SSL failed")
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
    """Body that triggers TypeError from _create_notify_gen returns []."""
    p = _make_plugin("x", "json://host/", True)
    a = _apprise_with(p)
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
# Mixed sequential + threadpool batch
# (async_mode=False → sequential, async_mode=True → threadpool)
# ---------------------------------------------------------------------------


def test_detailed_mixed_sequential_and_threadpool():
    """detailed=True with a mix of async_mode=False and async_mode=True
    servers routes through both sequential and threadpool detailed paths."""
    p_seq = _make_plugin("x", "slack://seq/ch", True, async_mode=False)
    p_par = _make_plugin("x", "discord://par/tok", False, async_mode=True)
    a = _apprise_with(p_seq, p_par)
    results = a.notify("body", tag="x", detailed=True)
    assert len(results) == 2
    result_map = {r["url"]: r for r in results}
    assert result_map["slack://seq/ch"]["success"] is True
    assert result_map["discord://par/tok"]["success"] is False


# ---------------------------------------------------------------------------
# Sequential detailed: retry / wait / optional
# (async_mode=False servers, sync notify())
# ---------------------------------------------------------------------------


def test_detailed_sequential_retry_on_failure_then_success():
    """Sequential detailed retries on failure and succeeds on second
    attempt."""
    call_count = {"n": 0}

    def flaky(**kw):
        call_count["n"] += 1
        return call_count["n"] >= 2

    p = _make_plugin("x", "slack://retry/seq", True, async_mode=False)
    p.notify.side_effect = flaky
    p.retry = 1

    a = _apprise_with(p)
    results = a.notify("body", tag="x", detailed=True)
    assert results[0]["success"] is True
    assert call_count["n"] == 2


def test_detailed_sequential_retry_with_wait():
    """Sequential detailed calls time.sleep when wait > 0 between retries."""
    p = _make_plugin("x", "slack://wait/seq", False, async_mode=False)
    p.notify.return_value = False
    p.retry = 1
    p.wait = 0.5

    a = _apprise_with(p)
    with mock.patch("apprise.apprise.time.sleep") as mock_sleep:
        a.notify("body", tag="x", detailed=True)
    mock_sleep.assert_called_once_with(0.5)


def test_detailed_sequential_optional_failure():
    """Optional server failure in sequential path does not raise."""
    p = _make_plugin("x", "slack://opt/seq", False, async_mode=False)
    p.optional = True
    a = _apprise_with(p)
    results = a.notify("body", tag="x", detailed=True)
    assert results[0]["success"] is False


# ---------------------------------------------------------------------------
# Parallel threadpool path
# (async_mode=True servers via sync notify() →
#  _notify_parallel_threadpool_detailed)
# ---------------------------------------------------------------------------


def test_detailed_parallel_all_attempted():
    """Threadpool path: all URLs attempted and results ordered correctly."""
    p1 = _make_plugin("x", "slack://t/ch", True, async_mode=True)
    p2 = _make_plugin("x", "tgram://b/c", False, async_mode=True)
    p3 = _make_plugin("x", "discord://w/t", True, async_mode=True)

    a = _apprise_with(p1, p2, p3)
    results = a.notify("body", tag="x", detailed=True)
    assert len(results) == 3
    result_map = {r["url"]: r["success"] for r in results}
    assert result_map["slack://t/ch"] is True
    assert result_map["tgram://b/c"] is False
    assert result_map["discord://w/t"] is True


def test_detailed_threadpool_zero_servers():
    """_notify_parallel_threadpool_detailed() with no args returns []."""
    result = Apprise._notify_parallel_threadpool_detailed()
    assert result == []


def test_detailed_threadpool_single_server_delegates_to_sequential():
    """With exactly one server, threadpool path delegates to sequential."""
    p = _make_plugin("x", "slack://t/ch", True, async_mode=True)
    with mock.patch.object(
        Apprise,
        "_notify_sequential_detailed",
        wraps=Apprise._notify_sequential_detailed,
    ) as spy:
        Apprise._notify_parallel_threadpool_detailed(
            (p, {"body": "hi", "title": ""})
        )
    spy.assert_called_once()


def test_detailed_threadpool_type_error_in_worker():
    """TypeError raised inside a threadpool worker is caught per-URL."""
    p1 = _make_plugin("x", "slack://t/ch", True, async_mode=True)
    p2 = _make_plugin("x", "discord://w/t", False, async_mode=True)
    p2.notify.side_effect = TypeError("bad kwarg")
    a = _apprise_with(p1, p2)
    results = a.notify("body", tag="x", detailed=True)
    result_map = {r["url"]: r for r in results}
    assert result_map["slack://t/ch"]["success"] is True
    assert result_map["discord://w/t"]["success"] is False
    assert "bad kwarg" in result_map["discord://w/t"]["detail"]


def test_detailed_threadpool_unhandled_exception_in_worker():
    """Unhandled Exception inside a threadpool worker is caught per-URL."""
    p1 = _make_plugin("x", "slack://t/ch", True, async_mode=True)
    p2 = _make_plugin("x", "tgram://b/c", False, raises=RuntimeError("boom"))
    p2.asset.async_mode = True
    a = _apprise_with(p1, p2)
    results = a.notify("body", tag="x", detailed=True)
    result_map = {r["url"]: r for r in results}
    assert result_map["tgram://b/c"]["success"] is False
    assert "boom" in result_map["tgram://b/c"]["detail"]


def test_detailed_threadpool_retry_on_failure_then_success():
    """Threadpool worker retries on failure and succeeds on second attempt."""
    call_count = {"n": 0}

    def flaky_notify(**kw):
        call_count["n"] += 1
        return call_count["n"] >= 2

    p = _make_plugin("x", "slack://retry/ch", True, async_mode=True)
    p.notify.side_effect = flaky_notify
    p.retry = 1

    a = _apprise_with(p)
    results = a.notify("body", tag="x", detailed=True)
    assert results[0]["success"] is True
    assert call_count["n"] == 2


def test_detailed_threadpool_retry_with_wait():
    """Threadpool worker calls time.sleep when wait > 0 between retries."""
    p = _make_plugin("x", "slack://wait/ch", False, async_mode=True)
    p.notify.return_value = False
    p.retry = 1
    p.wait = 0.5

    a = _apprise_with(p)
    with mock.patch("apprise.apprise.time.sleep") as mock_sleep:
        a.notify("body", tag="x", detailed=True)
    mock_sleep.assert_called_once_with(0.5)


def test_detailed_threadpool_optional_failure_is_silenced():
    """Optional server failure in threadpool path does not raise."""
    p = _make_plugin("x", "slack://opt/ch", False, async_mode=True)
    p.optional = True
    a = _apprise_with(p)
    results = a.notify("body", tag="x", detailed=True)
    assert results[0]["success"] is False
    assert isinstance(results[0]["detail"], str)


def test_detailed_threadpool_future_raises():
    """If future.result() raises, the outer handler builds an error dict."""
    import concurrent.futures as cf

    p1 = _make_plugin("x", "slack://t/ch", True, async_mode=True)
    p2 = _make_plugin("x", "discord://w/t", True, async_mode=True)

    # Patch as_completed to inject a pre-failed future for p2's slot.
    original_executor_cls = cf.ThreadPoolExecutor

    class PatchedExecutor:
        """Wraps ThreadPoolExecutor, replacing p2's future with a failing
        one."""

        def __init__(self, *a, **kw):
            self._real = original_executor_cls(*a, **kw)
            self._futures = {}  # future → (server, was_patched)

        def __enter__(self):
            self._real.__enter__()
            return self

        def __exit__(self, *args):
            return self._real.__exit__(*args)

        def submit(self, fn, server, kwargs):
            if server is p2:
                bad = cf.Future()
                bad.set_exception(RuntimeError("future exploded"))
                self._futures[bad] = server
                return bad
            fut = self._real.submit(fn, server, kwargs)
            self._futures[fut] = server
            return fut

    with mock.patch("apprise.apprise.cf.ThreadPoolExecutor", PatchedExecutor):
        a = _apprise_with(p1, p2)
        results = a.notify("body", tag="x", detailed=True)

    assert len(results) == 2
    result_map = {r["url"]: r for r in results}
    assert result_map["slack://t/ch"]["success"] is True
    assert result_map["discord://w/t"]["success"] is False
    assert "future exploded" in result_map["discord://w/t"]["detail"]


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
            async_mode = True  # → threadpool path
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
            async_mode = True  # → threadpool path
            abort_on_chain_failure = False

        def url(self, privacy=False):
            return "discord://parallel"

        def notify(self, **kw):
            self.logger.warning("Discord: invalid webhook 404")
            return False

    logging.disable(logging.NOTSET)
    try:
        a = _apprise_with(SlackPlugin(), DiscordPlugin())
        results = a.notify("body", tag="x", detailed=True)
    finally:
        logging.disable(logging.CRITICAL)

    result_map = {r["url"]: r for r in results}
    assert "429" in result_map["slack://parallel"]["detail"]
    assert "404" in result_map["discord://parallel"]["detail"]
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


def test_detailed_async_invalid_body_returns_empty_list():
    """async_notify(detailed=True): TypeError from _create_notify_gen → []."""
    p = _make_plugin("x", "json://host/", True)
    a = _apprise_with(p)
    with (
        mock.patch.object(a, "_create_notify_gen", side_effect=TypeError),
        OuterEventLoop() as loop,
    ):
        result = loop.run_until_complete(
            a.async_notify("body", tag="x", detailed=True)
        )
    assert result == []


def test_detailed_async_empty_servers():
    """_notify_parallel_asyncio_detailed() with no args returns []."""
    with OuterEventLoop() as loop:
        result = loop.run_until_complete(
            Apprise._notify_parallel_asyncio_detailed()
        )
    assert result == []


def test_detailed_async_type_error_in_coroutine():
    """TypeError from async_notify is caught and stored in detail."""
    p = _make_plugin("x", "slack://t/ch", False, async_mode=True)
    p.async_notify = mock.AsyncMock(side_effect=TypeError("async bad kwarg"))
    a = _apprise_with(p)

    with OuterEventLoop() as loop:
        results = loop.run_until_complete(
            a.async_notify("body", tag="x", detailed=True)
        )
    assert results[0]["success"] is False
    assert "async bad kwarg" in results[0]["detail"]


def test_detailed_async_failure_captures_message():
    """async_notify returning False captures a non-empty detail string."""
    p = _make_plugin("x", "discord://w/t", False, async_mode=True)
    a = _apprise_with(p)

    with OuterEventLoop() as loop:
        results = loop.run_until_complete(
            a.async_notify("body", tag="x", detailed=True)
        )
    assert results[0]["success"] is False
    assert results[0]["detail"] != ""


def test_detailed_async_retry_success():
    """Async detailed retries and succeeds on second attempt."""
    call_count = {"n": 0}

    async def flaky_async(**kw):
        call_count["n"] += 1
        return call_count["n"] >= 2

    p = _make_plugin("x", "slack://retry/async", True, async_mode=True)
    p.async_notify = flaky_async
    p.retry = 1

    a = _apprise_with(p)
    with OuterEventLoop() as loop:
        results = loop.run_until_complete(
            a.async_notify("body", tag="x", detailed=True)
        )
    assert results[0]["success"] is True
    assert call_count["n"] == 2


def test_detailed_async_retry_with_wait():
    """Async detailed calls asyncio.sleep when wait > 0 between retries."""
    p = _make_plugin("x", "slack://wait/async", False, async_mode=True)
    p.async_notify = mock.AsyncMock(return_value=False)
    p.retry = 1
    p.wait = 0.5

    a = _apprise_with(p)
    with (
        OuterEventLoop() as loop,
        mock.patch(
            "apprise.apprise.asyncio.sleep", new_callable=mock.AsyncMock
        ) as mock_sleep,
    ):
        loop.run_until_complete(a.async_notify("body", tag="x", detailed=True))
    mock_sleep.assert_called_once_with(0.5)


def test_detailed_async_optional_failure():
    """Optional server failure in async path does not raise."""
    p = _make_plugin("x", "slack://opt/async", False, async_mode=True)
    p.optional = True
    a = _apprise_with(p)

    with OuterEventLoop() as loop:
        results = loop.run_until_complete(
            a.async_notify("body", tag="x", detailed=True)
        )
    assert results[0]["success"] is False


def test_detailed_async_gather_exception():
    """If asyncio.gather returns an Exception item, it is caught and
    stored."""
    p = _make_plugin("x", "slack://t/ch", True, async_mode=True)
    a = _apprise_with(p)

    exc = RuntimeError("gather exploded")

    with (
        OuterEventLoop() as loop,
        mock.patch(
            "apprise.apprise.asyncio.gather", new_callable=mock.AsyncMock
        ) as mock_gather,
    ):
        mock_gather.return_value = [exc]
        results = loop.run_until_complete(
            a.async_notify("body", tag="x", detailed=True)
        )
    assert results[0]["success"] is False
    assert "gather exploded" in results[0]["detail"]


# ---------------------------------------------------------------------------
# _capture_server_logs does not break non-detailed notify
# ---------------------------------------------------------------------------


def test_capture_server_logs_does_not_affect_normal_notify():
    """_capture_server_logs must restore server.logger so subsequent
    non-detailed notify() calls work correctly."""
    p = _make_plugin("x", "json://host/", True)
    a = _apprise_with(p)

    a.notify("body", tag="x", detailed=True)

    p.notify.return_value = True
    result = a.notify("body", tag="x")
    assert result is True


def test_capture_server_logs_restores_class_logger():
    """After detailed notify, server.logger must not be an instance
    override."""
    p = _make_plugin("x", "json://host/", True)
    a = _apprise_with(p)
    a.notify("body", tag="x", detailed=True)
    assert "logger" not in p.__dict__
