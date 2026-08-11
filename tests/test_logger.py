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
import contextvars
from datetime import datetime, timezone
from importlib import import_module
import io
import json
import os
import re
import sys
import threading
import time
from unittest import mock

import pytest
import requests

from apprise import Apprise, AppriseAsset, URLBase
from apprise.common import AWARE_DATE_ISO_FORMAT

# Disable logging for a cleaner testing output
from apprise.logger import (
    LogCapture,
    NotifyLogEntry,
    _active_call_capture,
    _active_capture,
    _LogCaptureBudget,
    _NotifyLogStore,
    _ServiceLogCapture,
    logger,
    logging,
)
from apprise.plugins import NotifyBase

# Import the module directly because ``apprise.logger`` is also a public
# package attribute containing the shared Logger instance.
_LOGGER_MODULE = import_module("apprise.logger")


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


def test_notify_log_entry_ordering_notimplemented():
    """Comparing to a non-NotifyLogEntry returns NotImplemented for
    every relational operator."""
    entry = NotifyLogEntry(level="WARNING", message="hi")

    assert entry.__lt__("nope") is NotImplemented
    assert entry.__le__("nope") is NotImplemented
    assert entry.__gt__("nope") is NotImplemented
    assert entry.__ge__("nope") is NotImplemented


def test_notify_log_entry_asdict_json_repr():
    """asdict(), json(), and repr() all render the entry consistently."""
    t = datetime(2026, 1, 1, 12, 30, 0, tzinfo=timezone.utc)
    entry = NotifyLogEntry(level="WARNING", message="hi", time=t)

    d = entry.asdict()
    assert d == {
        "level": "WARNING",
        "message": "hi",
        "time": t.strftime(AWARE_DATE_ISO_FORMAT),
    }

    assert json.loads(entry.json()) == d

    assert repr(entry) == (
        f"<NotifyLogEntry level='WARNING' message='hi' time={t!r}>"
    )


def test_service_log_capture_keeps_all_entries():
    """Captures remain complete beyond the former 5,000-entry boundary."""
    service = _DummyNotify()
    with _ServiceLogCapture(service) as cap:
        for index in range(5001):
            record = logging.LogRecord(
                "apprise",
                logging.WARNING,
                __file__,
                0,
                "entry %d",
                (index,),
                None,
            )
            cap.handle(record)

    assert len(cap.entries) == 5001
    assert cap.entries[-1].message == "entry 5000"


def test_result_log_store_spills_to_disk_in_order():
    """A bounded capture reads disk-backed entries in their original order."""
    budget = _LogCaptureBudget(memory_size=1, disk_size=4096)
    store = _NotifyLogStore(budget)
    entries = [
        NotifyLogEntry("WARNING", "first"),
        NotifyLogEntry("ERROR", "second"),
    ]

    for entry in entries:
        store.append(entry)

    assert store._memory == []
    assert store._disk_count == 2
    assert len(store) == 2
    assert store == entries
    assert store[0] == entries[0]
    assert store[:] == entries
    store.close()
    assert budget._disk is None


def test_result_log_store_stays_on_disk_after_large_entry():
    """A smaller entry cannot move ahead of one already stored on disk."""
    entries = [
        NotifyLogEntry("WARNING", "first " + ("x" * 256)),
        NotifyLogEntry("ERROR", "second"),
    ]

    # Only the second entry fits in memory when considered by itself.
    memory_size = _LogCaptureBudget._HEADER.size + len(
        entries[1].json().encode("utf-8")
    )
    budget = _LogCaptureBudget(memory_size=memory_size, disk_size=4096)
    store = _NotifyLogStore(budget)

    for entry in entries:
        store.append(entry)

    # Once the first entry spills, later entries remain behind it on disk.
    assert store._memory == []
    assert store._disk_count == 2
    assert list(store) == entries
    store.close()
    assert budget._disk is None


def test_result_log_store_uses_unbounded_memory_without_disk():
    """The library default retains all logs in memory without a temp file."""
    store = _NotifyLogStore(_LogCaptureBudget(memory_size=1, disk_size=0))
    entry = NotifyLogEntry("WARNING", "kept in memory")

    store.append(entry)

    assert list(store) == [entry]
    assert store._budget._disk is None


def test_result_log_stores_share_one_temporary_file():
    """All captures in one notification share a single temporary file."""
    budget = _LogCaptureBudget(memory_size=4096, disk_size=4096)
    memory_store = _NotifyLogStore(budget)
    disk_store = _NotifyLogStore(budget)

    memory_store.append(NotifyLogEntry("WARNING", "memory"))
    budget.memory_used = budget.memory_size
    disk_store.append(NotifyLogEntry("WARNING", "disk"))

    assert len(memory_store._memory) == 1
    assert disk_store._disk_count == 1
    disk = budget._disk
    memory_store.close()
    assert budget._disk is disk
    disk_store.close()
    assert budget._disk is None


def test_result_log_store_reports_capacity_once(caplog):
    """A full store adds one warning while live callbacks remain unaffected."""
    logging.disable(logging.NOTSET)
    caplog.set_level(logging.WARNING, logger=logger.name)
    received = []

    try:
        with _ServiceLogCapture(
            service=None,
            log_callback=lambda entry, service: received.append(entry),
            memory_size=0,
            disk_size=1,
        ) as cap:
            logger.warning("first")
            logger.warning("second")
    finally:
        logging.disable(logging.CRITICAL)

    assert [entry.message for entry in received] == ["first", "second"]
    assert [entry.message for entry in cap.entries] == [
        _NotifyLogStore._LIMIT_MESSAGE
    ]
    assert caplog.text.count(_NotifyLogStore._LIMIT_MESSAGE) == 1


def test_result_log_store_handles_disk_failure(caplog):
    """Temporary-file failures are logged and contained."""
    logging.disable(logging.NOTSET)
    caplog.set_level(logging.DEBUG, logger=logger.name)
    store = _NotifyLogStore(_LogCaptureBudget(memory_size=0, disk_size=1024))

    try:
        with mock.patch.object(
            _LOGGER_MODULE.tempfile,
            "TemporaryFile",
            side_effect=OSError("no space"),
        ):
            store.append(NotifyLogEntry("ERROR", "delivery failed"))
    finally:
        logging.disable(logging.CRITICAL)

    assert [entry.message for entry in store] == [
        _NotifyLogStore._DISK_MESSAGE
    ]
    assert "no space" in caplog.text


def test_result_log_store_contains_logging_failure_on_write():
    """A broken handler cannot expose a result-log write failure."""
    store = _NotifyLogStore(_LogCaptureBudget(memory_size=0, disk_size=1024))

    with (
        mock.patch.object(
            _LOGGER_MODULE.tempfile,
            "TemporaryFile",
            side_effect=OSError("no space"),
        ),
        mock.patch.object(
            logger,
            "log",
            side_effect=RuntimeError("broken handler"),
        ),
    ):
        # The storage warning remains available even when it cannot be logged.
        store.append(NotifyLogEntry("ERROR", "delivery failed"))

    assert [entry.message for entry in store] == [
        _NotifyLogStore._DISK_MESSAGE
    ]
    store.close()


@pytest.mark.parametrize("failed_write", (1, 2, 5))
def test_result_log_store_handles_short_writes(failed_write):
    """Short header, entry, and link writes are contained."""

    class ShortWriteFile(io.BytesIO):
        """Return one short write at the requested call."""

        def __init__(self):
            super().__init__()
            self.calls = 0

        def write(self, value):
            self.calls += 1
            if self.calls == failed_write:
                super().write(value[:-1])
                return len(value) - 1
            return super().write(value)

    budget = _LogCaptureBudget(memory_size=0, disk_size=4096)
    store = _NotifyLogStore(budget)
    with mock.patch.object(
        _LOGGER_MODULE.tempfile,
        "TemporaryFile",
        return_value=ShortWriteFile(),
    ):
        # The first record covers header and payload writes.
        store.append(NotifyLogEntry("WARNING", "first"))
        if failed_write == 5:
            # A second record reaches the write that links both records.
            store.append(NotifyLogEntry("WARNING", "second"))

    assert store._notice.message == _NotifyLogStore._DISK_MESSAGE
    assert budget.disk_failed is True
    store.close()


@pytest.mark.parametrize("corruption", ("header", "size", "payload", "chain"))
def test_result_log_store_handles_unreadable_data(corruption, caplog):
    """Corrupt temporary data is logged instead of escaping iteration."""
    logging.disable(logging.NOTSET)
    caplog.set_level(logging.WARNING, logger=logger.name)
    budget = _LogCaptureBudget(memory_size=0, disk_size=4096)
    store = _NotifyLogStore(budget)
    store.append(NotifyLogEntry("WARNING", "first"))
    if corruption == "chain":
        store.append(NotifyLogEntry("WARNING", "second"))

    disk = budget._disk
    if corruption == "header":
        # Leave too few bytes to form a complete record header.
        disk.seek(0)
        disk.truncate(1)
    elif corruption == "size":
        # Claim a size that can never fit within this capture's limit.
        disk.seek(0)
        disk.write(budget._HEADER.pack(budget.disk_size + 1, budget._END))
    elif corruption == "payload":
        # Keep the header but remove most of the promised content.
        disk.seek(0)
        disk.truncate(budget._HEADER.size + 1)
    else:
        # End the chain while the store still expects another record.
        disk.seek(budget._LINK.size)
        disk.write(budget._LINK.pack(budget._END))

    try:
        list(store)
    finally:
        logging.disable(logging.CRITICAL)
        store.close()

    assert "could not be read" in caplog.text


def test_result_log_store_contains_logging_failure_on_read():
    """A broken handler cannot expose a result-log read failure."""
    budget = _LogCaptureBudget(memory_size=0, disk_size=4096)
    store = _NotifyLogStore(budget)
    store.append(NotifyLogEntry("WARNING", "first"))

    # Leave too little data for a complete disk record.
    budget._disk.seek(0)
    budget._disk.truncate(1)

    with mock.patch.object(
        logger,
        "log",
        side_effect=RuntimeError("broken handler"),
    ):
        entries = list(store)

    # Iteration still returns a useful warning to the caller.
    assert [entry.message for entry in entries] == [
        _NotifyLogStore._READ_MESSAGE
    ]
    store.close()


def test_result_log_store_handles_close_failure(caplog):
    """Temporary-file close failures are logged and contained."""

    class CloseFailFile(io.BytesIO):
        """Raise when temporary storage is closed."""

        failed = False

        def close(self):
            if not self.failed:
                self.failed = True
                raise OSError("close failed")
            super().close()

    logging.disable(logging.NOTSET)
    caplog.set_level(logging.DEBUG, logger=logger.name)
    budget = _LogCaptureBudget(memory_size=0, disk_size=4096)
    store = _NotifyLogStore(budget)
    with mock.patch.object(
        _LOGGER_MODULE.tempfile,
        "TemporaryFile",
        return_value=CloseFailFile(),
    ):
        store.append(NotifyLogEntry("WARNING", "entry"))

    try:
        store.close()
        store.append(NotifyLogEntry("WARNING", "ignored after close"))
        with pytest.raises(OSError):
            budget.read(0)
    finally:
        logging.disable(logging.CRITICAL)

    assert "close failed" in caplog.text


def test_result_log_store_contains_logging_failure_on_close():
    """A broken handler cannot expose a result-log cleanup failure."""

    class CloseFailFile(io.BytesIO):
        """Fail the first close request, like a temporary-file error."""

        failed = False

        def close(self):
            if not self.failed:
                self.failed = True
                raise OSError("close failed")

            super().close()

    budget = _LogCaptureBudget(memory_size=0, disk_size=4096)
    store = _NotifyLogStore(budget)

    with mock.patch.object(
        _LOGGER_MODULE.tempfile,
        "TemporaryFile",
        return_value=CloseFailFile(),
    ):
        store.append(NotifyLogEntry("WARNING", "entry"))

    with mock.patch.object(
        logger,
        "log",
        side_effect=RuntimeError("broken handler"),
    ):
        # Cleanup remains safe even when its warning cannot be logged.
        store.close()

    assert budget._disk is None


def test_result_log_store_sequence_and_repeat_failure_paths():
    """Sequence comparisons and repeated storage failures stay safe."""
    budget = _LogCaptureBudget(memory_size=0, disk_size=4096)
    first = _NotifyLogStore(budget)
    second = _NotifyLogStore(budget)
    entry = NotifyLogEntry("WARNING", "entry")
    first.append(entry)
    second.append(entry)

    assert budget.claim_warning("one warning") is True
    assert budget.claim_warning("one warning") is False
    assert first == second
    assert first.__eq__(object()) is NotImplemented
    first._set_notice("first warning", log=False)
    first._set_notice("ignored warning", log=False)
    assert first._notice.message == "first warning"
    first.close()
    second.close()

    class ConcurrentFailFile(io.BytesIO):
        """Simulate another writer reporting the same disk failure first."""

        def write(self, value):
            budget.disk_failed = True
            raise OSError("shared failure")

    budget = _LogCaptureBudget(memory_size=0, disk_size=4096)
    store = _NotifyLogStore(budget)
    budget.claim_warning(_NotifyLogStore._DISK_MESSAGE)
    with mock.patch.object(
        _LOGGER_MODULE.tempfile,
        "TemporaryFile",
        return_value=ConcurrentFailFile(),
    ):
        store.append(entry)
    assert store._notice.message == _NotifyLogStore._DISK_MESSAGE
    store.close()


def test_service_captures_share_call_log_budget():
    """Service captures draw from their enclosing call's storage budget."""
    service = _DummyNotify()
    with (
        _ServiceLogCapture(
            service=None, memory_size=0, disk_size=4096
        ) as call_cap,
        _ServiceLogCapture(service) as service_cap,
    ):
        assert service_cap._budget is call_cap._budget


def test_notify_uses_asset_result_log_limits():
    """Sync and async notifications apply their asset's shared log limits."""
    logging.disable(logging.NOTSET)

    class _WarnNotify(_DummyNotify):
        """Emit one retained warning during delivery."""

        def send(self, *args, **kwargs):
            """Log a warning and report success."""
            self.logger.warning("stored on disk")
            return True

    try:
        for use_async in (False, True):
            asset = AppriseAsset(
                result_log_memory_size=0, result_log_disk_size=4096
            )
            instance = Apprise(asset=asset)
            assert instance.add(_WarnNotify(asset=asset))

            result = (
                asyncio.run(instance.async_notify("body"))
                if use_async
                else instance.notify("body")
            )
            attempt_logs = result.results[0].attempts[0].logs
            assert attempt_logs._disk_count == 1
            assert [entry.message for entry in result.logs()] == [
                "stored on disk"
            ]
            result.close()
    finally:
        logging.disable(logging.CRITICAL)


def test_service_log_capture_exit_without_enter():
    """__exit__ tolerates being called when __enter__ never ran, and
    skips the contextvar reset since there is no token to restore."""
    service = _DummyNotify()
    cap = _ServiceLogCapture(service)
    assert cap._token is None

    # Must not raise even though __enter__ was never called.
    cap.__exit__(None, None, None)


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


def test_call_capture_uses_separate_context():
    """Call and service captures use separate context markers."""
    with _ServiceLogCapture(service=None) as cap:
        assert _active_capture.get() is None
        assert _active_call_capture.get() is cap
        assert cap._token is None


def test_call_capture_records_shared_logs():
    """A call capture stores unclaimed shared-logger records."""
    logging.disable(logging.NOTSET)

    try:
        with _ServiceLogCapture(service=None) as cap:
            logger.warning("no services to notify")
    finally:
        logging.disable(logging.CRITICAL)

    assert [e.message for e in cap.entries] == ["no services to notify"]


def test_call_capture_defers_to_service():
    """A call capture ignores records owned by a service capture."""
    logging.disable(logging.NOTSET)
    service = _DummyNotify()

    try:
        with _ServiceLogCapture(service=None) as call_cap:
            logger.warning("before service window")

            with _ServiceLogCapture(service) as svc_cap:
                service.logger.warning("during service window")

            logger.warning("after service window")
    finally:
        logging.disable(logging.CRITICAL)

    assert [e.message for e in call_cap.entries] == [
        "before service window",
        "after service window",
    ]
    assert [e.message for e in svc_cap.entries] == ["during service window"]


def test_call_capture_callback_has_no_service():
    """Call-level callbacks receive ``service=None``."""
    logging.disable(logging.NOTSET)
    received = []

    def _cb(entry, service):
        """Record the (message, service) pair delivered live."""
        received.append((entry.message, service))

    try:
        with _ServiceLogCapture(service=None, log_callback=_cb) as cap:
            logger.warning("orchestration message")
    finally:
        logging.disable(logging.CRITICAL)

    assert received == [("orchestration message", None)]
    assert [e.message for e in cap.entries] == ["orchestration message"]


def test_call_capture_keeps_concurrent_logs():
    """A call capture keeps concurrent entries without loss."""
    logging.disable(logging.NOTSET)

    n_per_thread = 200
    barrier = threading.Barrier(4)

    def _hammer(tag):
        """Log many messages from one thread, all starting together."""
        barrier.wait()
        for i in range(n_per_thread):
            logger.warning("%s-%d", tag, i)

    try:
        with (
            _ServiceLogCapture(service=None) as cap,
            cf.ThreadPoolExecutor(max_workers=4) as ex,
        ):
            futures = [
                ex.submit(contextvars.copy_context().run, _hammer, tag)
                for tag in ("A", "B", "C", "D")
            ]
            for future in futures:
                future.result()
    finally:
        logging.disable(logging.CRITICAL)

    messages = sorted(e.message for e in cap.entries)
    expected = sorted(
        f"{tag}-{i}"
        for tag in ("A", "B", "C", "D")
        for i in range(n_per_thread)
    )
    assert messages == expected


def test_call_capture_blocks_recursive_callback():
    """A callback cannot recursively capture its own log message."""
    logging.disable(logging.NOTSET)
    received = []

    def _reentrant_cb(entry, service):
        """Try to log again through the same handler while still
        inside the first entry's own callback."""
        received.append(entry.message)
        if entry.message == "first":
            logger.warning("triggered from callback")

    try:
        with _ServiceLogCapture(
            service=None, log_callback=_reentrant_cb
        ) as cap:
            logger.warning("first")
    finally:
        logging.disable(logging.CRITICAL)

    # The reentrant call is swallowed by _in_emit, not processed as a
    # second entry or a second callback invocation.
    assert [e.message for e in cap.entries] == ["first"]
    assert received == ["first"]


def test_callback_error_contains_logging_failure():
    """A broken handler cannot expose a callback failure."""
    logging.disable(logging.NOTSET)

    def _broken_callback(_entry, _service):
        """Represent application callback code that unexpectedly fails."""
        raise RuntimeError("callback failed")

    try:
        with (
            mock.patch.object(
                logger,
                "log",
                side_effect=RuntimeError("broken handler"),
            ),
            _ServiceLogCapture(
                service=None,
                log_callback=_broken_callback,
            ) as cap,
        ):
            # The original log call and notification flow both continue.
            logger.warning("first")

    finally:
        logging.disable(logging.CRITICAL)

    assert [entry.message for entry in cap.entries] == ["first"]


def test_call_captures_are_thread_isolated():
    """Concurrent call captures do not receive each other's entries."""
    logging.disable(logging.NOTSET)
    barrier = threading.Barrier(2)

    def _capture(message):
        with _ServiceLogCapture(service=None) as cap:
            barrier.wait()
            logger.warning(message)
            return [entry.message for entry in cap.entries]

    try:
        with cf.ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(_capture, "first")
            second = executor.submit(_capture, "second")
            assert first.result() == ["first"]
            assert second.result() == ["second"]
    finally:
        logging.disable(logging.CRITICAL)


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


def test_service_log_capture_rejects_async_callback(caplog):
    """Reject an async callback without losing the captured warning."""
    # Older pytest releases may leave logging disabled after another test.
    logging.disable(logging.NOTSET)
    caplog.set_level(logging.WARNING, logger=logger.name)

    async def _cb(entry, service):
        """A callback mistakenly defined as async; body never runs."""
        pass  # pragma: no cover -- the coroutine is closed, not awaited

    try:
        service = _DummyNotify()
        with _ServiceLogCapture(service, log_callback=_cb) as cap:
            service.logger.warning("service warning")
    finally:
        logging.disable(logging.CRITICAL)

    assert [e.message for e in cap.entries] == ["service warning"]
    assert "must be synchronous" in caplog.text
