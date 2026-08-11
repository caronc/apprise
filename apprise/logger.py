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

from __future__ import annotations

import asyncio
from collections.abc import Iterator
import contextlib
import contextvars
from datetime import datetime, timezone
from io import StringIO
import json
import logging
import os
import struct
import tempfile
import threading
from typing import TYPE_CHECKING, Any, Callable, Optional, Union

from .common import AWARE_DATE_ISO_FORMAT, JSON_COMPACT_SEPARATORS

if TYPE_CHECKING:
    # Import NotifyBase only for static analysis. Importing it at runtime
    # would create a cycle through apprise.url and this logger module.
    from .plugins.base import NotifyBase

# The root identifier needed to monitor 'apprise' logging
LOGGER_NAME = "apprise"

# Tracks the service capture active in the current execution context.
_active_capture: contextvars.ContextVar[Optional[_ServiceLogCapture]] = (
    contextvars.ContextVar("apprise_active_log_capture", default=None)
)

# Keeps call-level logs isolated when notifications run concurrently.
_active_call_capture: contextvars.ContextVar[Optional[_ServiceLogCapture]] = (
    contextvars.ContextVar("apprise_active_call_log_capture", default=None)
)


# Define a verbosity level that is a noisier then debug mode
logging.TRACE = logging.DEBUG - 1

# Define a verbosity level that is always used even when no verbosity is set
# from the command line.  The idea here is to allow for deprecation notices
logging.DEPRECATE = logging.ERROR + 1

# Assign our Levels into our logging object
logging.addLevelName(logging.DEPRECATE, "DEPRECATION WARNING")
logging.addLevelName(logging.TRACE, "TRACE")


def trace(self, message, *args, **kwargs):
    """
    Verbose Debug Logging - Trace
    """
    if self.isEnabledFor(logging.TRACE):
        self._log(logging.TRACE, message, args, **kwargs)


def deprecate(self, message, *args, **kwargs):
    """Deprication Warning Logging."""
    if self.isEnabledFor(logging.DEPRECATE):
        self._log(logging.DEPRECATE, message, args, **kwargs)


# Assign our Loggers for use in Apprise
logging.Logger.trace = trace
logging.Logger.deprecate = deprecate

# Create ourselve a generic (singleton) logging reference
logger = logging.getLogger(LOGGER_NAME)


def _safe_internal_log(level: int, message: str, *args: Any) -> None:
    """Report a capture problem without letting logging handlers raise."""
    # Logging is best-effort while the original notification continues.
    with contextlib.suppress(Exception):
        # Capture handlers already block their own re-entry. This guard also
        # contains failures raised by application-provided handlers.
        logger.log(level, message, *args)


class NotifyLogEntry:
    """A log entry captured during notification processing."""

    def __init__(
        self, level: str, message: str, time: Optional[datetime] = None
    ) -> None:
        """Initialize a captured message and its UTC timestamp."""

        # The already-formatted log message
        self.message = message

        # The log level name (e.g. "WARNING", "ERROR")
        self.level = level

        # The log time
        self.time = time if time is not None else datetime.now(timezone.utc)

    def __eq__(self, other: object) -> bool:
        """Check equality of two entries by their (time, level, message)."""
        if not isinstance(other, NotifyLogEntry):
            return NotImplemented
        return (self.time, self.level, self.message) == (
            other.time,
            other.level,
            other.message,
        )

    def __hash__(self) -> int:
        """Hash on the same (time, level, message) for __eq__ uses."""
        return hash((self.time, self.level, self.message))

    def __lt__(self, other: NotifyLogEntry) -> bool:
        """Order by time alone, for chronological playback"""
        if not isinstance(other, NotifyLogEntry):
            return NotImplemented
        return self.time < other.time

    def __le__(self, other: NotifyLogEntry) -> bool:
        """Order by time alone, for chronological playback"""
        if not isinstance(other, NotifyLogEntry):
            return NotImplemented
        return self.time <= other.time

    def __gt__(self, other: NotifyLogEntry) -> bool:
        """See __lt__."""
        if not isinstance(other, NotifyLogEntry):
            return NotImplemented
        return self.time > other.time

    def __ge__(self, other: NotifyLogEntry) -> bool:
        """See __lt__."""
        if not isinstance(other, NotifyLogEntry):
            return NotImplemented
        return self.time >= other.time

    def asdict(self) -> dict[str, Any]:
        """Return this entry as a plain, JSON-serializable dict."""
        return {
            "level": self.level,
            "message": self.message,
            "time": self.time.strftime(AWARE_DATE_ISO_FORMAT),
        }

    def json(self) -> str:
        """Return this entry as a JSON string."""
        return json.dumps(self.asdict(), separators=JSON_COMPACT_SEPARATORS)

    def __str__(self) -> str:
        """Format the entry like a conventional Python log line."""
        # Match Python logging's familiar default-style output.
        asctime = "{},{:03d}".format(
            self.time.strftime("%Y-%m-%d %H:%M:%S"),
            self.time.microsecond // 1000,
        )
        return "{} - {} - {}".format(asctime, self.level, self.message)

    def __repr__(self) -> str:
        """Return an unambiguous representation of this entry."""
        return "<NotifyLogEntry level={!r} message={!r} time={!r}>".format(
            self.level, self.message, self.time
        )


class _LogCaptureBudget:
    """Share result-log memory and disk limits across one notify call."""

    # Store each entry's size and the next entry in this capture.
    _HEADER = struct.Struct("!QQ")

    # Update only the next-entry location when linking records.
    _LINK = struct.Struct("!Q")

    # This value marks the last record in one capture's disk chain.
    _END = (1 << 64) - 1

    # This message is retained when the configured disk allowance is full.
    _LIMIT_MESSAGE = (
        "Result log storage is full; additional entries were not retained."
    )

    # This message is retained when temporary storage stops working.
    _DISK_MESSAGE = (
        "Result log disk storage failed; additional entries may be missing."
    )

    def __init__(self, memory_size: int = 0, disk_size: int = 0) -> None:
        """Set byte limits; a zero disk limit keeps memory unbounded."""
        # Maximum memory shared by all captures in this notification call.
        self.memory_size = memory_size

        # Maximum temporary disk space shared by the same captures.
        self.disk_size = disk_size

        # Memory currently reserved by captured entries.
        self.memory_used = 0

        # Disk space currently reserved by captured entries.
        self.disk_used = 0

        # Stop further writes after the first disk error.
        self.disk_failed = False

        # Open the temporary file only when an entry spills to disk.
        self._disk: Optional[Any] = None

        # The final store to close releases the shared temporary file.
        self._store_count = 0

        # Report each storage problem once per notification call.
        self._reported_warnings: set[str] = set()

        # Protect shared limits and disk access across service threads.
        self._lock = threading.RLock()

    def register_store(self) -> None:
        """Keep shared disk storage open for one capture store."""
        with self._lock:
            # Every active store receives one ownership count.
            self._store_count += 1

    def reserve_memory(self, size: int) -> bool:
        """Reserve memory for one entry before it spills to disk."""
        with self._lock:
            # No disk allowance preserves the original all-memory behavior.
            if not self.disk_size:
                return True

            # Spill the complete entry rather than splitting it across stores.
            if self.memory_used + size > self.memory_size:
                return False

            # Reserve the entry's bytes before another thread can claim them.
            self.memory_used += size

            return True

    def claim_warning(self, message: str) -> bool:
        """Return true once for each storage warning in this notify call."""
        with self._lock:
            # A warning already claimed by another capture is not repeated.
            if message in self._reported_warnings:
                return False

            # Remember the warning before its caller writes to the logger.
            self._reported_warnings.add(message)

            return True

    def write(
        self, payload: bytes, previous: Optional[int]
    ) -> tuple[Optional[int], Optional[str]]:
        """Write one entry and return its offset or a safe warning."""
        # Disk accounting includes the record header and its log content.
        size = self._HEADER.size + len(payload)

        with self._lock:
            # A failed or full disk store cannot accept another record.
            if self.disk_failed or self.disk_used + size > self.disk_size:
                return (
                    None,
                    self._DISK_MESSAGE
                    if self.disk_failed
                    else self._LIMIT_MESSAGE,
                )

            # Reserve space first so parallel captures cannot exceed the cap.
            self.disk_used += size

            try:
                if self._disk is None:
                    # Share one anonymous file across this notification.
                    self._disk = tempfile.TemporaryFile(  # noqa: SIM115
                        mode="w+b"
                    )

                # Append new content without disturbing earlier records.
                self._disk.seek(0, os.SEEK_END)

                # New records always begin at the current end of the file.
                offset = self._disk.tell()

                # New records begin as the final item in their capture.
                header = self._HEADER.pack(len(payload), self._END)

                # A short write means the record cannot be trusted later.
                if self._disk.write(header) != len(header):
                    raise OSError("short result log header write")

                # Write the complete log entry immediately after its header.
                if self._disk.write(payload) != len(payload):
                    raise OSError("short result log entry write")

                if previous is not None:
                    # Link this capture's entries across the shared file.
                    self._disk.seek(previous + self._LINK.size)

                    # Point the prior record at the new record's location.
                    link = self._LINK.pack(offset)

                    if self._disk.write(link) != len(link):
                        raise OSError("short result log link write")

                # Make completed writes available to result readers.
                self._disk.flush()

                return offset, None

            except Exception as e:
                # Return unused space after a failed write.
                self.disk_used -= size

                if self.claim_warning(self._DISK_MESSAGE):
                    # Keep the main warning concise and details at debug level.
                    _safe_internal_log(logging.WARNING, self._DISK_MESSAGE)
                    _safe_internal_log(
                        logging.DEBUG,
                        "Result log storage exception: %s",
                        str(e),
                    )

                # Future entries skip disk instead of repeating the failure.
                self.disk_failed = True

                return None, self._DISK_MESSAGE

    def read(self, offset: int) -> tuple[bytes, int]:
        """Read and validate one serialized entry at an owned offset."""
        with self._lock:
            # A closed result no longer has disk content to replay.
            if self._disk is None:
                raise OSError("result log storage is closed")

            # Move directly to the record owned by this capture.
            self._disk.seek(offset)

            # Read the fixed-size details that describe the stored entry.
            header = self._disk.read(self._HEADER.size)

            # Reject partial records before decoding their content.
            if len(header) != self._HEADER.size:
                raise OSError("truncated result log header")

            # Recover the content length and the next record location.
            size, next_offset = self._HEADER.unpack(header)

            # A record cannot be larger than the complete disk allowance.
            if size > self.disk_size:
                raise OSError("invalid result log entry size")

            # Read only the number of bytes declared by this record.
            payload = self._disk.read(size)

            # Do not pass incomplete content to the JSON decoder.
            if len(payload) != size:
                raise OSError("truncated result log entry")

            return payload, next_offset

    def release_store(self) -> None:
        """Close shared disk storage after its final capture is released."""
        with self._lock:
            # This store no longer needs access to the shared file.
            self._store_count -= 1

            # Another store still needs the file, or no file was opened.
            if self._store_count or self._disk is None:
                return

            try:
                # The last store owns final cleanup of temporary storage.
                self._disk.close()

            except Exception as e:
                # Report cleanup errors while still clearing the file below.
                _safe_internal_log(
                    logging.WARNING,
                    "Result log storage could not be closed.",
                )
                _safe_internal_log(
                    logging.DEBUG,
                    "Result log close exception: %s",
                    str(e),
                )

            finally:
                # Never leave a closed or failed handle available for reuse.
                self._disk = None


class _NotifyLogStore:
    """Keep captured entries in memory, spilling later entries to disk."""

    # Reuse the shared message when the configured allowance is full.
    _LIMIT_MESSAGE = _LogCaptureBudget._LIMIT_MESSAGE

    # Reuse the shared message when temporary storage stops working.
    _DISK_MESSAGE = _LogCaptureBudget._DISK_MESSAGE

    # Return a safe entry when retained disk content cannot be replayed.
    _READ_MESSAGE = "Stored result logs could not be read."

    def __init__(self, budget: _LogCaptureBudget) -> None:
        """Create an empty store using the call's shared byte budget."""
        # Register first so the shared file stays open for this store.
        self._budget = budget
        self._budget.register_store()

        # Memory always holds the oldest retained entries.
        self._memory: list[NotifyLogEntry] = []

        # This is where the first disk-backed entry can be found.
        self._first_offset: Optional[int] = None

        # This is where the newest disk-backed entry can be found.
        self._last_offset: Optional[int] = None

        # Count the disk entries this store can read.
        self._disk_count = 0

        # A final notice explains why later entries are missing.
        self._notice: Optional[NotifyLogEntry] = None

        # Closed stores ignore late entries and no longer read from disk.
        self._closed = False

        # Iteration and appends can occur from different worker threads.
        self._lock = threading.RLock()

    @staticmethod
    def _encode(entry: NotifyLogEntry) -> bytes:
        """Serialize an entry for length-prefixed disk storage."""
        return entry.json().encode("utf-8")

    @staticmethod
    def _decode(payload: bytes) -> NotifyLogEntry:
        """Restore an entry read from disk."""
        # Convert the stored JSON text back into its plain fields.
        data = json.loads(payload.decode("utf-8"))

        # Rebuild the same public entry type used by in-memory logs.
        return NotifyLogEntry(
            level=data["level"],
            message=data["message"],
            time=datetime.strptime(data["time"], AWARE_DATE_ISO_FORMAT),
        )

    def append(self, entry: NotifyLogEntry) -> None:
        """Append an entry without allowing storage errors to escape."""
        # Measure the encoded entry before choosing memory or disk.
        payload = self._encode(entry)

        # Include the small disk header in all shared byte accounting.
        size = self._budget._HEADER.size + len(payload)

        with self._lock:
            # Late messages cannot reopen a completed result.
            if self._closed:
                return

            # After data is lost, keep its warning as the final entry.
            if self._notice is not None:
                return

            if self._budget.reserve_memory(size):
                # Fill memory before using slower disk storage.
                self._memory.append(entry)

                return

            # The last offset joins this entry to only this store's chain.
            offset, warning = self._budget.write(payload, self._last_offset)

            if offset is None:
                # Keep a readable explanation in place of discarded entries.
                self._set_notice(
                    warning or self._DISK_MESSAGE,
                    log=self._budget.claim_warning(
                        warning or self._DISK_MESSAGE
                    ),
                )

                return

            if self._first_offset is None:
                # Remember where replay for this store begins.
                self._first_offset = offset

            # This entry is now the final item in this store's disk chain.
            self._last_offset = offset

            # Count only entries that completed their disk write.
            self._disk_count += 1

    def _set_notice(self, message: str, log: bool = True) -> None:
        """Retain one bounded warning when entries must be discarded."""
        if self._notice is None:
            # The notice becomes the final entry returned to the caller.
            self._notice = NotifyLogEntry("WARNING", message)

            if log:
                # Also tell the application when this warning is first owned.
                _safe_internal_log(logging.WARNING, message)

    def __iter__(self) -> Iterator[NotifyLogEntry]:
        """Yield retained entries in capture order."""
        with self._lock:
            # Memory comes first because it contains the oldest entries.
            yield from self._memory

            if self._first_offset is not None:
                try:
                    # Follow only this store's entries in the shared file.
                    offset = self._first_offset

                    for index in range(self._disk_count):
                        # Read and restore one entry at its known location.
                        payload, next_offset = self._budget.read(offset)
                        yield self._decode(payload)

                        if (
                            next_offset == self._budget._END
                            and index + 1 < self._disk_count
                        ):
                            # The entry chain ended sooner than expected.
                            raise OSError("truncated result log chain")

                        # Continue from the location saved in this record.
                        offset = next_offset

                except Exception as e:
                    # Replace unreadable content with one useful warning.
                    _safe_internal_log(logging.WARNING, self._READ_MESSAGE)
                    _safe_internal_log(
                        logging.DEBUG,
                        "Result log read exception: %s",
                        str(e),
                    )
                    yield NotifyLogEntry("WARNING", self._READ_MESSAGE)

            if self._notice is not None:
                # This stays last because later entries were discarded.
                yield self._notice

    def __len__(self) -> int:
        """Return the number of retained entries and any storage warning."""
        with self._lock:
            return (
                len(self._memory)
                + self._disk_count
                + (self._notice is not None)
            )

    def __getitem__(
        self, index: Union[int, slice]
    ) -> Union[NotifyLogEntry, list[NotifyLogEntry]]:
        """Return an entry or slice using normal sequence behavior."""
        return list(self)[index]

    def __eq__(self, other: object) -> bool:
        """Compare retained entries with another iterable."""
        if isinstance(other, _NotifyLogStore):
            return list(self) == list(other)

        if isinstance(other, (list, tuple)):
            return list(self) == list(other)

        return NotImplemented

    def close(self) -> None:
        """Release any temporary file owned by this store."""
        with self._lock:
            if not self._closed:
                # Clear locations so a closed store cannot replay disk data.
                self._closed = True

                self._first_offset = None

                self._last_offset = None

                self._disk_count = 0

                # Release this store's ownership of shared temporary storage.
                self._budget.release_store()

    def __del__(self) -> None:
        """Best-effort cleanup when callers do not close the result."""
        with contextlib.suppress(Exception):
            # Interpreter shutdown may already have cleared module globals.
            self.close()


class _ServiceLogCapture(logging.Handler):
    """Capture logs for one service or one notification call.

    The capture mode depends on ``service``:

    - A service captures entries from its current notification attempt.
    - ``service=None`` captures orchestration entries for the whole call.

    ``log_callback`` receives entries live and should return promptly.
    """

    def __init__(
        self,
        service: Optional[NotifyBase] = None,
        log_callback: Optional[
            Callable[[NotifyLogEntry, Optional[NotifyBase]], None]
        ] = None,
        level: int = logging.WARNING,
        memory_size: int = 0,
        disk_size: int = 0,
    ) -> None:
        """Prepare a service-level or call-level log handler."""
        super().__init__(level=level)

        # A service capture can reuse the budget owned by its enclosing call.
        call_capture = _active_call_capture.get()

        # Standalone and call-level captures create their own shared budget.
        self._budget = (
            call_capture._budget
            if service is not None and call_capture is not None
            else _LogCaptureBudget(memory_size, disk_size)
        )

        # Each handler owns one ordered view into that shared budget.
        self._entries = _NotifyLogStore(self._budget)

        # Call-level orchestration messages use the shared logger.
        self._logger = getattr(service, "logger", logger)

        # None identifies a call-level entry to the callback.
        self._service = service

        # The optional callback receives entries as they are captured.
        self._log_callback = log_callback

        # This token restores an enclosing service capture on exit.
        self._token: Optional[contextvars.Token] = None

        # This token restores an enclosing call capture on exit.
        self._call_token: Optional[contextvars.Token] = None

        # Prevent a callback from logging recursively through this handler.
        self._in_emit = False

    def emit(self, record: logging.LogRecord) -> None:
        """Store a record owned by this capture."""
        # Ignore logging triggered by this handler's own callback or warnings.
        if self._in_emit:
            return

        # Set the guard before formatting or invoking user callback code.
        self._in_emit = True

        try:
            self._emit(record)

        finally:
            # Always allow the next independent record through.
            self._in_emit = False

    def _emit(self, record: logging.LogRecord) -> None:
        """Process a record after the reentrancy check."""
        try:
            if self._service is not None:
                # Per-service: only the exact active capture accepts.
                if _active_capture.get() is not self:
                    return

            else:
                # Accept only unclaimed records from this notification call.
                if (
                    _active_call_capture.get() is not self
                    or _active_capture.get() is not None
                ):
                    return

            entry = NotifyLogEntry(
                level=record.levelname,
                # Preserve normal logging behavior for formatted messages.
                # The outer handler catches malformed format strings.
                message=record.getMessage(),
                # Match the UTC-aware timestamps used by other results.
                time=datetime.fromtimestamp(record.created, tz=timezone.utc),
            )

            # Retain the entry before notifying a live callback.
            self._entries.append(entry)

            # Copy the reference in case application code later replaces it.
            callback = self._log_callback

            if callback is not None:
                self._invoke_log_callback(entry, callback)

        except Exception:
            # Use logging's normal error path for formatting or storage errors.
            self.handleError(record)

    def _invoke_log_callback(
        self,
        entry: NotifyLogEntry,
        callback: Callable[[NotifyLogEntry, Optional[NotifyBase]], None],
    ) -> None:
        """Call ``log_callback(entry, service)``.

        ``service`` is ``None`` for call-level entries. The return value is
        ignored.
        """
        try:
            result = callback(entry, self._service)

        except Exception as e:
            _safe_internal_log(
                logging.WARNING,
                "The log_callback function raised an exception.",
            )
            _safe_internal_log(
                logging.DEBUG,
                "log_callback Exception: %s",
                str(e),
            )
            return

        if asyncio.iscoroutine(result):
            # Close unsupported async callbacks without leaking a warning.
            result.close()

            _safe_internal_log(
                logging.WARNING,
                "The log_callback function must be synchronous; its "
                "returned coroutine was ignored. Schedule async work "
                "from inside the callback instead.",
            )

    @property
    def entries(self) -> _NotifyLogStore:
        """Return entries captured at or above this handler's level."""
        return self._entries

    def __enter__(self) -> _ServiceLogCapture:
        """Attach the handler and mark its capture context."""
        # Begin receiving records from the logger owned by this capture.
        self._logger.addHandler(self)

        if self._service is not None:
            # Mark this as the active capture for one service attempt.
            self._token = _active_capture.set(self)

        else:
            # Mark this as the active capture for the complete notify call.
            self._call_token = _active_call_capture.set(self)

        return self

    def __exit__(self, *_: object) -> None:
        """Detach the handler and restore the enclosing capture."""
        # Stop receiving records before changing the active context.
        self._logger.removeHandler(self)

        if self._token is not None:
            # Restore any service capture that surrounded this one.
            _active_capture.reset(self._token)

        if self._call_token is not None:
            # Restore any call capture that surrounded this one.
            _active_call_capture.reset(self._call_token)


class LogCapture:
    """A class used to allow one to instantiate loggers that write to memory
    for temporary purposes. e.g.:

    1.  with LogCapture() as captured:
    2.
    3.      # Send our notification(s)
    4.      aobj.notify("hello world")
    5.
    6.      # retrieve our logs produced by the above call via our
    7.      # `captured` StringIO object we have access to within the `with`
    8.      # block here:
    9.      print(captured.getvalue())
    """

    def __init__(
        self,
        path=None,
        level=None,
        name=LOGGER_NAME,
        delete=True,
        fmt="%(asctime)s - %(levelname)s - %(message)s",
    ):
        """Instantiate a temporary log capture object.

        If a path is specified, then log content is sent to that file instead
        of a StringIO object.

        You can optionally specify a logging level such as logging.INFO if you
        wish, otherwise by default the script uses whatever logging has been
        set globally. If you set delete to `False` then when using log files,
        they are not automatically cleaned up afterwards.

        Optionally over-ride the fmt as well if you wish.
        """
        # Our memory buffer placeholder
        self.__buffer_ptr = StringIO()

        # Store our file path as it will determine whether or not we write to
        # memory and a file
        self.__path = path
        self.__delete = delete

        # Our logging level tracking
        self.__level = level
        self.__restore_level = None

        # Acquire a pointer to our logger
        self.__logger = logging.getLogger(name)

        # Prepare our handler
        self.__handler = (
            logging.StreamHandler(self.__buffer_ptr)
            if not self.__path
            else logging.FileHandler(self.__path, mode="a", encoding="utf-8")
        )

        # Use the specified level, otherwise take on the already
        # effective level of our logger
        self.__handler.setLevel(
            self.__level
            if self.__level is not None
            else self.__logger.getEffectiveLevel()
        )

        # Prepare our formatter
        self.__handler.setFormatter(logging.Formatter(fmt))

    def __enter__(self):
        """Allows logger manipulation within a 'with' block."""

        if self.__level is not None:
            # Temporary adjust our log level if required
            self.__restore_level = self.__logger.getEffectiveLevel()
            if self.__restore_level > self.__level:
                # Bump our log level up for the duration of our `with`
                self.__logger.setLevel(self.__level)

            else:
                # No restoration required
                self.__restore_level = None

        else:
            # Do nothing but enforce that we have nothing to restore to
            self.__restore_level = None

        if self.__path:
            # If a path has been identified, ensure we can write to the path
            # and that the file exists
            with open(self.__path, "a"):
                os.utime(self.__path, None)

            # Update our buffer pointer
            self.__buffer_ptr = open(self.__path)

        # Add our handler
        self.__logger.addHandler(self.__handler)

        # return our memory pointer
        return self.__buffer_ptr

    def __exit__(self, exc_type, exc_value, tb):
        """Removes the handler gracefully when the with block has completed."""

        # Flush our content
        self.__handler.flush()
        self.__buffer_ptr.flush()

        # Drop our handler
        self.__logger.removeHandler(self.__handler)

        if self.__restore_level is not None:
            # Restore level
            self.__logger.setLevel(self.__restore_level)

        if self.__path:
            # Close our file pointer
            self.__buffer_ptr.close()
            self.__handler.close()
            if self.__delete:
                with contextlib.suppress(OSError):
                    # Always remove file afterwards
                    os.unlink(self.__path)

        return exc_type is None
