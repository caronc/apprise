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
import concurrent.futures as cf
import contextlib
import contextvars
from datetime import datetime, timezone
from io import StringIO
import json
import logging
import os
from typing import TYPE_CHECKING, Any, Callable, Optional

from .common import AWARE_DATE_ISO_FORMAT, JSON_COMPACT_SEPARATORS

if TYPE_CHECKING:
    # Import NotifyBase only for static analysis. Importing it at runtime
    # would create a cycle through apprise.url and this logger module.
    from .plugins.base import NotifyBase

# The root identifier needed to monitor 'apprise' logging
LOGGER_NAME = "apprise"

# Upper bound on WARNING+ entries captured for one attempt.
# This caps memory use if a plugin logs repeatedly in a large batch.
_MAX_CAPTURED_LOG_ENTRIES = 5000

# Tracks which capture owns logs from the current execution context.
# ContextVar also survives async-to-thread handoffs when copied explicitly.
_active_capture: contextvars.ContextVar[Optional[_ServiceLogCapture]] = (
    contextvars.ContextVar("apprise_active_log_capture", default=None)
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


class NotifyLogEntry:
    """A single log line captured while one service was being notified."""

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


class _ServiceLogCapture(logging.Handler):
    """Capture one service's warning and error messages in isolation.

    It attaches one extra handler for a single attempt. ``log_callback``,
    when provided, receives each captured (entry, service) live.
    """

    def __init__(
        self,
        service: NotifyBase,
        log_callback: Optional[
            Callable[[NotifyLogEntry, NotifyBase], Any]
        ] = None,
    ) -> None:
        """Prepare an isolated WARNING-level handler for ``service``."""
        # Only capture WARNING and above -- this mirrors the level at
        # which plugins themselves report delivery failures (HTTP errors,
        # rate limits, etc.); INFO/DEBUG chatter is not useful here.
        super().__init__(level=logging.WARNING)
        self._entries: list[NotifyLogEntry] = []

        # Reuse the service's logger; this capture is just another listener.
        self._logger = getattr(service, "logger", logger)

        # Kept only so log_callback can identify the service.
        self._service = service
        self._log_callback = log_callback

        # support for async log_callback.
        try:
            self._loop: Optional[asyncio.AbstractEventLoop] = (
                asyncio.get_running_loop()
            )
        except RuntimeError:
            self._loop = None

        # Set on __enter__, used to restore _active_capture on __exit__.
        self._token: Optional[contextvars.Token] = None

        # prevent reoccurrance of emit() calls from the same thread.
        self._in_emit = False

    def emit(self, record: logging.LogRecord) -> None:
        """Wrap and store one captured logging.LogRecord.

        Ignores any record produced on behalf of another service
        dispatched concurrently -- see _active_capture's own docstring.
        """
        if self._in_emit:
            return
        self._in_emit = True
        try:
            self._emit(record)
        finally:
            self._in_emit = False

    def _emit(self, record: logging.LogRecord) -> None:
        """The actual body of emit(), guarded against re-entrancy by the
        wrapper above."""
        try:
            if _active_capture.get() is not self:
                return

            if len(self._entries) >= _MAX_CAPTURED_LOG_ENTRIES:
                # A plugin can log once per item while processing a large
                # or malformed batch (bulk recipients, malformed config
                # entries, etc.) -- cap growth instead of buffering an
                # unbounded number of entries for the lifetime of the
                # result.
                return

            entry = NotifyLogEntry(
                level=record.levelname,
                # record.getMessage() re-applies %-style formatting
                # (msg % args) every time it's called, so a plugin's
                # own malformed logging call (e.g. too few args for
                # its format string) raises here, exactly as it would
                # for any other handler -- self.handleError() is the
                # standard library's own convention for this (see
                # logging.StreamHandler.emit()), so the caller's
                # original self.logger.warning(...) call still
                # returns normally instead of raising through it.
                message=record.getMessage(),
                # record.created is a Unix timestamp (seconds since
                # the epoch); logging itself is timezone-agnostic,
                # but every other timestamp Apprise reports is an
                # aware UTC datetime, so this is converted to match.
                time=datetime.fromtimestamp(record.created, tz=timezone.utc),
            )
            self._entries.append(entry)

            callback = self._log_callback
            if callback is not None:
                self._invoke_log_callback(entry, callback)

        except Exception:
            self.handleError(record)

    def _invoke_log_callback(
        self,
        entry: NotifyLogEntry,
        callback: Callable[[NotifyLogEntry, NotifyBase], Any],
    ) -> None:
        """Call log_callback(entry, service) for one captured entry.

        The returned value tells us whether it was plain sync work or an
        async coroutine that still needs scheduling.
        """
        try:
            result = callback(entry, self._service)

        except Exception as e:
            logger.warning("The log_callback function raised an exception.")
            logger.debug("log_callback Exception: %s", str(e))
            return

        if not asyncio.iscoroutine(result):
            return

        if self._loop is None:
            # No loop is available; close the coroutine to avoid a warning.
            result.close()
            logger.warning(
                "The log_callback returned async work, but no asyncio event "
                "loop is running; this live log update was skipped: %s",
                entry,
            )
            return

        # This is safe from worker threads and the loop's own thread.
        future = asyncio.run_coroutine_threadsafe(result, self._loop)
        future.add_done_callback(self._log_callback_done)

    @staticmethod
    def _log_callback_done(future: cf.Future[Any]) -> None:
        """Surface any exception from a scheduled async log_callback."""
        if future.cancelled():
            logger.warning(
                "A log_callback update was cancelled before it completed. "
                "The log entry was still saved normally."
            )
            return

        exc = future.exception()
        if exc is not None:
            logger.warning("The log_callback function raised an exception.")
            logger.debug("log_callback Exception: %s", str(exc))

    @property
    def entries(self) -> list[NotifyLogEntry]:
        """Return every WARNING+ entry captured during this attempt."""
        return self._entries

    def __enter__(self) -> _ServiceLogCapture:
        """Attach as an extra handler without disturbing existing ones."""
        self._logger.addHandler(self)
        self._token = _active_capture.set(self)
        return self

    def __exit__(self, *_: object) -> None:
        """Detach the handler."""
        self._logger.removeHandler(self)
        if self._token is not None:
            _active_capture.reset(self._token)


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
