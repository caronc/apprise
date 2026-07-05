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

import asyncio
import concurrent.futures as cf
from datetime import datetime, timezone
import os
import re
import sys
import time
from unittest import mock

import pytest
import requests

from apprise import Apprise, AppriseAsset, URLBase

# Disable logging for a cleaner testing output
from apprise.logger import (
    LogCapture,
    NotifyLogEntry,
    _ServiceLogCapture,
    logger,
    logging,
)
from apprise.plugins import NotifyBase


def test_apprise_logger():
    """
    API: Apprise() Logger

    """

    # Ensure we're not running in a disabled state
    logging.disable(logging.NOTSET)

    # Set our log level
    URLBase.logger.setLevel(logging.DEPRECATE + 1)

    # Deprication will definitely not trigger
    URLBase.logger.deprecate("test")

    # Verbose Debugging is not on at this point
    URLBase.logger.trace("test")

    # Set both logging entries on
    URLBase.logger.setLevel(logging.TRACE)

    # Deprication will definitely trigger
    URLBase.logger.deprecate("test")

    # Verbose Debugging will activate
    URLBase.logger.trace("test")

    # Disable Logging
    logging.disable(logging.CRITICAL)


def test_apprise_log_memory_captures():
    """
    API: Apprise() Log Memory Captures

    """

    # Ensure we're not running in a disabled state
    logging.disable(logging.NOTSET)

    logger.setLevel(logging.CRITICAL)
    with LogCapture(level=logging.TRACE) as stream:
        logger.trace("trace")
        logger.debug("debug")
        logger.info("info")
        logger.warning("warning")
        logger.error("error")
        logger.deprecate("deprecate")

        logs = re.split(r"\r*\n", stream.getvalue().rstrip())

        # We have a log entry for each of the 6 logs we generated above
        assert "trace" in stream.getvalue()
        assert "debug" in stream.getvalue()
        assert "info" in stream.getvalue()
        assert "warning" in stream.getvalue()
        assert "error" in stream.getvalue()
        assert "deprecate" in stream.getvalue()
        assert len(logs) == 6

    # Verify that we did not lose our effective log level even though
    # the above steps the level up for the duration of the capture
    assert logger.getEffectiveLevel() == logging.CRITICAL

    logger.setLevel(logging.TRACE)
    with LogCapture(level=logging.DEBUG) as stream:
        logger.trace("trace")
        logger.debug("debug")
        logger.info("info")
        logger.warning("warning")
        logger.error("error")
        logger.deprecate("deprecate")

        # We have a log entry for 5 of the log entries we generated above
        # There will be no 'trace' entry
        assert "trace" not in stream.getvalue()
        assert "debug" in stream.getvalue()
        assert "info" in stream.getvalue()
        assert "warning" in stream.getvalue()
        assert "error" in stream.getvalue()
        assert "deprecate" in stream.getvalue()

        logs = re.split(r"\r*\n", stream.getvalue().rstrip())
        assert len(logs) == 5

    # Verify that we did not lose our effective log level even though
    # the above steps the level up for the duration of the capture
    assert logger.getEffectiveLevel() == logging.TRACE

    logger.setLevel(logging.ERROR)
    with LogCapture(level=logging.WARNING) as stream:
        logger.trace("trace")
        logger.debug("debug")
        logger.info("info")
        logger.warning("warning")
        logger.error("error")
        logger.deprecate("deprecate")

        # We have a log entry for 3 of the log entries we generated above
        # There will be no 'trace', 'debug', or 'info' entry
        assert "trace" not in stream.getvalue()
        assert "debug" not in stream.getvalue()
        assert "info" not in stream.getvalue()
        assert "warning" in stream.getvalue()
        assert "error" in stream.getvalue()
        assert "deprecate" in stream.getvalue()

        logs = re.split(r"\r*\n", stream.getvalue().rstrip())
        assert len(logs) == 3

    # Set a global level of ERROR
    logger.setLevel(logging.ERROR)

    # Use the default level of None (by not specifying one); we then
    # use whatever has been defined globally
    with LogCapture() as stream:
        logger.trace("trace")
        logger.debug("debug")
        logger.info("info")
        logger.warning("warning")
        logger.error("error")
        logger.deprecate("deprecate")

        assert "trace" not in stream.getvalue()
        assert "debug" not in stream.getvalue()
        assert "info" not in stream.getvalue()
        assert "warning" not in stream.getvalue()
        assert "error" in stream.getvalue()
        assert "deprecate" in stream.getvalue()

        logs = re.split(r"\r*\n", stream.getvalue().rstrip())
        assert len(logs) == 2

    # Verify that we did not lose our effective log level
    assert logger.getEffectiveLevel() == logging.ERROR

    with LogCapture(level=logging.TRACE) as stream:
        logger.trace("trace")
        logger.debug("debug")
        logger.info("info")
        logger.warning("warning")
        logger.error("error")
        logger.deprecate("deprecate")

        # We have a log entry for each of the 6 logs we generated above
        assert "trace" in stream.getvalue()
        assert "debug" in stream.getvalue()
        assert "info" in stream.getvalue()
        assert "warning" in stream.getvalue()
        assert "error" in stream.getvalue()
        assert "deprecate" in stream.getvalue()

        logs = re.split(r"\r*\n", stream.getvalue().rstrip())
        assert len(logs) == 6

    # Verify that we did not lose our effective log level even though
    # the above steps the level up for the duration of the capture
    assert logger.getEffectiveLevel() == logging.ERROR

    # Test capture where our notification throws an unhandled exception
    obj = Apprise.instantiate("json://user:password@example.com")
    with (
        mock.patch("requests.request", side_effect=NotImplementedError()),
        pytest.raises(NotImplementedError),
        # Our exception gets caught in side our with() block
        # and although raised, all graceful handling of the log
        # is reverted as it was
        LogCapture(level=logging.TRACE) as stream,
    ):
        obj.send("hello world")

    # Disable Logging
    logging.disable(logging.CRITICAL)


def test_apprise_log_file_captures(tmpdir):
    """
    API: Apprise() Log File Captures

    """

    # Ensure we're not running in a disabled state
    logging.disable(logging.NOTSET)

    log_file = tmpdir.join("capture.log")
    assert not os.path.isfile(str(log_file))

    logger.setLevel(logging.CRITICAL)
    with LogCapture(path=str(log_file), level=logging.TRACE) as fp:
        # The file will exit now
        assert os.path.isfile(str(log_file))

        logger.trace("trace")
        logger.debug("debug")
        logger.info("info")
        logger.warning("warning")
        logger.error("error")
        logger.deprecate("deprecate")

        content = fp.read().rstrip()
        logs = re.split(r"\r*\n", content)

        # We have a log entry for each of the 6 logs we generated above
        assert "trace" in content
        assert "debug" in content
        assert "info" in content
        assert "warning" in content
        assert "error" in content
        assert "deprecate" in content
        assert len(logs) == 6

    # The file is automatically cleaned up afterwards
    assert not os.path.isfile(str(log_file))

    # Verify that we did not lose our effective log level even though
    # the above steps the level up for the duration of the capture
    assert logger.getEffectiveLevel() == logging.CRITICAL

    logger.setLevel(logging.TRACE)
    with LogCapture(path=str(log_file), level=logging.DEBUG) as fp:
        # The file will exit now
        assert os.path.isfile(str(log_file))

        logger.trace("trace")
        logger.debug("debug")
        logger.info("info")
        logger.warning("warning")
        logger.error("error")
        logger.deprecate("deprecate")

        content = fp.read().rstrip()
        logs = re.split(r"\r*\n", content)

        # We have a log entry for 5 of the log entries we generated above
        # There will be no 'trace' entry
        assert "trace" not in content
        assert "debug" in content
        assert "info" in content
        assert "warning" in content
        assert "error" in content
        assert "deprecate" in content

        assert len(logs) == 5

        # Concurrent file access is not possible on Windows.
        # PermissionError: [WinError 32] The process cannot access the file
        # because it is being used by another process.
        if sys.platform != "win32":
            # Remove our file before we exit the with clause
            # this causes our delete() call to throw gracefully inside
            os.unlink(str(log_file))

            # Verify file is gone
            assert not os.path.isfile(str(log_file))

    # Verify that we did not lose our effective log level even though
    # the above steps the level up for the duration of the capture
    assert logger.getEffectiveLevel() == logging.TRACE

    logger.setLevel(logging.ERROR)
    with LogCapture(
        path=str(log_file), delete=False, level=logging.WARNING
    ) as fp:
        # Verify exists
        assert os.path.isfile(str(log_file))

        logger.trace("trace")
        logger.debug("debug")
        logger.info("info")
        logger.warning("warning")
        logger.error("error")
        logger.deprecate("deprecate")

        content = fp.read().rstrip()
        logs = re.split(r"\r*\n", content)

        # We have a log entry for 3 of the log entries we generated above
        # There will be no 'trace', 'debug', or 'info' entry
        assert "trace" not in content
        assert "debug" not in content
        assert "info" not in content
        assert "warning" in content
        assert "error" in content
        assert "deprecate" in content

        assert len(logs) == 3

    # Verify the file still exists (because delete was set to False)
    assert os.path.isfile(str(log_file))

    # remove it now
    os.unlink(str(log_file))

    # Enure it's been removed
    assert not os.path.isfile(str(log_file))

    # Set a global level of ERROR
    logger.setLevel(logging.ERROR)

    # Test case where we can't open the file
    with (
        mock.patch("builtins.open", side_effect=OSError()),
        # Use the default level of None (by not specifying one); we then
        # use whatever has been defined globally
        pytest.raises(OSError),
        LogCapture(path=str(log_file)) as fp,
    ):
        # we'll never get here because we'll fail to open the file
        pass

    # Disable Logging
    logging.disable(logging.CRITICAL)


@mock.patch("requests.request")
def test_apprise_secure_logging(mock_request):
    """
    API: Apprise() secure logging tests
    """

    # Ensure we're not running in a disabled state
    logging.disable(logging.NOTSET)

    logger.setLevel(logging.CRITICAL)

    # Prepare Mock
    mock_request.return_value = requests.Request()
    mock_request.return_value.status_code = requests.codes.ok

    # Default Secure Logging is set to enabled
    asset = AppriseAsset()
    assert asset.secure_logging is True

    # Load our asset
    a = Apprise(asset=asset)

    with LogCapture(level=logging.DEBUG) as stream:
        # add a test server
        assert a.add("json://user:pass1$-3!@localhost") is True

        # Our servers should carry this flag
        assert a[0].asset.secure_logging is True

        logs = re.split(r"\r*\n", stream.getvalue().rstrip())
        assert len(logs) == 1
        entry = re.split(r"\s-\s", logs[0])
        assert len(entry) == 3
        assert entry[1] == "DEBUG"
        assert entry[2].startswith(
            "Loaded JSON URL: json://user:****@localhost/"
        )

    # Send notification
    assert bool(a.notify("test")) is True

    # Test our call count
    assert mock_request.call_count == 1

    # Reset
    mock_request.reset_mock()

    # Now we test the reverse configuration and turn off
    # secure logging.

    # Default Secure Logging is set to disable
    asset = AppriseAsset(secure_logging=False)
    assert asset.secure_logging is False

    # Load our asset
    a = Apprise(asset=asset)

    with LogCapture(level=logging.DEBUG) as stream:
        # add a test server
        assert a.add("json://user:pass1$-3!@localhost") is True

        # Our servers should carry this flag
        assert a[0].asset.secure_logging is False

        logs = re.split(r"\r*\n", stream.getvalue().rstrip())
        assert len(logs) == 1
        entry = re.split(r"\s-\s", logs[0])
        assert len(entry) == 3
        assert entry[1] == "DEBUG"

        # Note that our password is no longer escaped (it is however
        # url encoded)
        assert entry[2].startswith(
            "Loaded JSON URL: json://user:pass1%24-3%21@localhost/"
        )

    # Disable Logging
    logging.disable(logging.CRITICAL)


class _DummyNotify(NotifyBase):
    """Minimal plugin used to exercise _ServiceLogCapture directly."""

    service_name = "dummy"

    def url(self, privacy=False, *args, **kwargs):
        """Return a stable URL for assertions that only need an identity."""
        return "dummy://"

    def send(self, *args, **kwargs):
        """Pretend the notification was delivered successfully."""
        return True


def test_notify_log_entry_equality_and_hash():
    """Two entries are equal (and hash equally) only when their time,
    level, and message all match."""
    t = datetime(2026, 1, 1, tzinfo=timezone.utc)

    a = NotifyLogEntry(level="WARNING", message="hi", time=t)
    b = NotifyLogEntry(level="WARNING", message="hi", time=t)
    diff_level = NotifyLogEntry(level="ERROR", message="hi", time=t)
    diff_message = NotifyLogEntry(level="WARNING", message="bye", time=t)

    assert a == b
    assert hash(a) == hash(b)
    assert a != diff_level
    assert a != diff_message
    assert a != "not a NotifyLogEntry"


def test_notify_log_entry_ordering_by_time():
    """Entries sort by time alone -- every relational operator is
    defined directly against time (see the class docstring)."""
    early = NotifyLogEntry(
        level="WARNING",
        message="first",
        time=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    late = NotifyLogEntry(
        level="ERROR",
        message="second",
        time=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )

    assert early < late
    assert late > early
    assert early <= late
    assert late >= early
    assert sorted([late, early]) == [early, late]


def test_notify_log_entry_equal_time_ordering():
    """Two different (unequal) entries sharing the same timestamp must
    never both compare greater than each other.

    Equality compares the full entry; ordering compares timestamps only.
    """
    t = datetime(2026, 1, 1, tzinfo=timezone.utc)
    a = NotifyLogEntry(level="WARNING", message="alpha", time=t)
    b = NotifyLogEntry(level="ERROR", message="beta", time=t)

    assert a != b
    assert not (a > b and b > a)
    assert not (a < b)
    assert not (b < a)
    assert a <= b
    assert b <= a
    assert a >= b
    assert b >= a


def test_notify_log_entry_combine_and_sort_across_calls():
    """Entries captured across separate notify() calls (potentially for
    different plugins) can be combined into one set and replayed back
    in chronological order -- the scenario this supports directly."""
    call_a = [
        NotifyLogEntry(
            level="WARNING",
            message="from service A",
            time=datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        )
    ]
    call_b = [
        NotifyLogEntry(
            level="ERROR",
            message="from service B",
            time=datetime(2026, 1, 1, 11, 0, 0, tzinfo=timezone.utc),
        ),
        # A duplicate of call_a's entry -- should collapse in a set.
        NotifyLogEntry(
            level="WARNING",
            message="from service A",
            time=datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        ),
    ]

    combined = sorted(set(call_a) | set(call_b))

    assert len(combined) == 2
    assert combined[0].message == "from service B"
    assert combined[1].message == "from service A"


def test_service_log_capture_bad_format():
    """A plugin's own malformed logging call must not escape capture."""
    service = _DummyNotify()
    with _ServiceLogCapture(service) as cap:
        # Only one arg supplied for two required by the format string --
        # this must not raise back out of handle().
        cap.handle(
            logging.LogRecord(
                name="apprise",
                level=logging.WARNING,
                pathname=__file__,
                lineno=1,
                msg="missing %s %s",
                args=("one",),
                exc_info=None,
            )
        )
        cap.handle(
            logging.LogRecord(
                name="apprise",
                level=logging.WARNING,
                pathname=__file__,
                lineno=2,
                msg="a real one: %s",
                args=("fine",),
                exc_info=None,
            )
        )

    assert len(cap.entries) == 1
    assert cap.entries[0].message == "a real one: fine"


def test_service_log_capture_async_send_warning():
    """The default async_notify() path captures warnings logged in send()."""
    logging.disable(logging.NOTSET)

    class _WarnOnSend(_DummyNotify):
        """Dummy service that logs during send()."""

        def send(self, *args, **kwargs):
            """Emit one warning before reporting success."""
            self.logger.warning("a warning from send()")
            return True

    async def _run():
        """Run async_notify() under a capture context."""
        service = _WarnOnSend()
        with _ServiceLogCapture(service) as cap:
            result = await service.async_notify(body="x")
        return result, cap.entries

    try:
        result, entries = asyncio.run(_run())
    finally:
        logging.disable(logging.CRITICAL)

    assert result is True
    assert len(entries) == 1
    assert entries[0].message == "a warning from send()"


def test_service_log_capture_async_concurrent_isolation():
    """Concurrent async captures keep each service's logs separate."""
    logging.disable(logging.NOTSET)

    class _WarnOnSend(_DummyNotify):
        """Dummy service that can stagger warning emission."""

        def __init__(self, tag_message, delay=0.0, **kwargs):
            """Store the warning message and optional delay."""
            super().__init__(**kwargs)
            self._tag_message = tag_message
            self._delay = delay

        def send(self, *args, **kwargs):
            """Emit this service's distinct warning."""
            if self._delay:
                time.sleep(self._delay)
            self.logger.warning(self._tag_message)
            return True

    async def _run_one(service):
        """Capture one async service call."""
        with _ServiceLogCapture(service) as cap:
            await service.async_notify(body="x")
        return [e.message for e in cap.entries]

    async def _run():
        """Run two captures at the same time."""
        a = _WarnOnSend("warning from A")
        b = _WarnOnSend("warning from B", delay=0.05)
        return await asyncio.gather(_run_one(a), _run_one(b))

    try:
        results = asyncio.run(_run())
    finally:
        logging.disable(logging.CRITICAL)

    assert results == [["warning from A"], ["warning from B"]]


def test_service_log_capture_thread_isolation():
    """Threaded captures keep each service's logs separate."""
    logging.disable(logging.NOTSET)

    class _WarnOnSend(_DummyNotify):
        """Dummy service that can stagger warning emission in threads."""

        def __init__(self, tag_message, delay=0.0, **kwargs):
            """Store the warning message and optional delay."""
            super().__init__(**kwargs)
            self._tag_message = tag_message
            self._delay = delay

        def send(self, *args, **kwargs):
            """Emit this service's distinct warning."""
            if self._delay:
                time.sleep(self._delay)
            self.logger.warning(self._tag_message)
            return True

    def _run_one(service):
        """Capture one threaded service call."""
        with _ServiceLogCapture(service) as cap:
            service.notify(body="x")
        return [e.message for e in cap.entries]

    try:
        a = _WarnOnSend("warning from A")
        b = _WarnOnSend("warning from B", delay=0.05)
        with cf.ThreadPoolExecutor() as ex:
            fut_a = ex.submit(_run_one, a)
            fut_b = ex.submit(_run_one, b)
            result_a, result_b = fut_a.result(), fut_b.result()
    finally:
        logging.disable(logging.CRITICAL)

    assert result_a == ["warning from A"]
    assert result_b == ["warning from B"]


def test_service_log_capture_sync_log_callback():
    """A plain log_callback receives each captured entry live."""
    logging.disable(logging.NOTSET)
    received = []

    def _cb(entry, service):
        """Record callback delivery in the order entries are emitted."""
        received.append((service.service_name, entry.message))

    try:
        service = _DummyNotify()
        with _ServiceLogCapture(service, log_callback=_cb) as cap:
            service.logger.warning("first")
            service.logger.warning("second")
    finally:
        logging.disable(logging.CRITICAL)

    assert received == [
        ("dummy", "first"),
        ("dummy", "second"),
    ]
    assert [e.message for e in cap.entries] == ["first", "second"]


def test_service_log_capture_callback_error():
    """A raising log_callback must not break capture."""
    logging.disable(logging.NOTSET)

    def _broken_cb(entry, service):
        """Raise from the callback."""
        raise ValueError("boom")

    try:
        service = _DummyNotify()
        with _ServiceLogCapture(service, log_callback=_broken_cb) as cap:
            # Must not raise back out to the caller.
            service.logger.warning("still captured")
    finally:
        logging.disable(logging.CRITICAL)

    assert [e.message for e in cap.entries] == ["still captured"]


def test_service_log_capture_async_callback_loop():
    """An async log_callback is scheduled on the active event loop."""
    logging.disable(logging.NOTSET)
    received = []

    async def _cb(entry, service):
        """Record after yielding to the event loop."""
        await asyncio.sleep(0.01)
        received.append((service.service_name, entry.message))

    async def _run():
        """Schedule one async callback."""
        service = _DummyNotify()
        with _ServiceLogCapture(service, log_callback=_cb) as cap:
            service.logger.warning("async entry")
        # emit() schedules the callback but cannot await it.
        await asyncio.sleep(0.1)
        return cap

    try:
        cap = asyncio.run(_run())
    finally:
        logging.disable(logging.CRITICAL)

    assert received == [("dummy", "async entry")]
    assert [e.message for e in cap.entries] == ["async entry"]


def test_service_log_capture_async_callback_no_loop():
    """An async log_callback without an event loop is closed cleanly."""
    logging.disable(logging.NOTSET)

    async def _cb(entry, service):
        """Callback that should be closed before it can run."""
        pass  # pragma: no cover -- never actually runs

    try:
        service = _DummyNotify()
        with _ServiceLogCapture(service, log_callback=_cb) as cap:
            service.logger.warning("no loop available")
    finally:
        logging.disable(logging.CRITICAL)

    assert [e.message for e in cap.entries] == ["no loop available"]


def test_service_log_capture_async_callback_error():
    """A scheduled async log_callback exception is logged."""
    logging.disable(logging.NOTSET)

    async def _broken_cb(entry, service):
        """Raise inside the scheduled task."""
        raise ValueError("boom from async callback")

    async def _run():
        """Schedule the failing callback and allow it to finish."""
        service = _DummyNotify()
        with _ServiceLogCapture(service, log_callback=_broken_cb) as cap:
            service.logger.warning("still captured despite async error")
        await asyncio.sleep(0.1)
        return cap

    try:
        with mock.patch("apprise.logger.logger.debug") as mock_debug:
            cap = asyncio.run(_run())
    finally:
        logging.disable(logging.CRITICAL)

    assert [e.message for e in cap.entries] == [
        "still captured despite async error"
    ]
    assert mock_debug.called
    assert "boom from async callback" in str(mock_debug.call_args)


def test_service_log_capture_cancelled_callback_future():
    """_log_callback_done must swallow a cancelled callback future."""
    future = cf.Future()
    future.cancel()
    assert future.cancelled()

    with (
        mock.patch("apprise.logger.logger.warning") as mock_warning,
        mock.patch("apprise.logger.logger.debug") as mock_debug,
    ):
        # Must not raise.
        _ServiceLogCapture._log_callback_done(future)

    assert mock_warning.called
    assert "cancelled" in str(mock_warning.call_args).lower()
    assert not mock_debug.called


def test_service_log_capture_loop_shutdown_cancel():
    """A pending async log_callback can be cancelled at loop shutdown."""
    logging.disable(logging.NOTSET)

    async def _cb(entry, service):
        """Remain pending until asyncio.run() teardown."""
        # Long enough to still be pending when _run() returns.
        await asyncio.sleep(0.2)

    async def _run():
        """Schedule one callback without waiting for it to finish."""
        service = _DummyNotify()
        with _ServiceLogCapture(service, log_callback=_cb) as cap:
            service.logger.warning("cancelled before callback finishes")
        return cap

    try:
        # No callback cancellation should propagate out of asyncio.run().
        cap = asyncio.run(_run())
    finally:
        logging.disable(logging.CRITICAL)

    assert [e.message for e in cap.entries] == [
        "cancelled before callback finishes"
    ]
