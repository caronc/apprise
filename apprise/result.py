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

#
#  - AppriseResultStatus -- the outcome of one notify() call,
#                           as an IntEnum so it can double as a process
#                           exit code (see apprise/cli.py).
#  - NotifyAttempt       -- the raw outcome of exactly one call to a
#                           service's notify()/async_notify() -- one
#                           retry, or one escalation-chain re-dispatch.
#  - NotifyResult        -- the outcome of one service actually being
#                           notified this call (name, url, reflective
#                           status), wrapping an ordered collection of
#                           NotifyAttempt entries.
#  - AppriseResult       -- the overall outcome of one notify() call,
#                           wrapping an ordered collection of
#                           NotifyResult entries plus the status above.
"""Structured outcomes for notification calls, services, and attempts."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from datetime import datetime, timedelta, timezone
from enum import IntEnum
import heapq
import json
from typing import Optional, TextIO

from .common import AWARE_DATE_ISO_FORMAT, JSON_COMPACT_SEPARATORS
from .logger import NotifyLogEntry, _NotifyLogStore


def _write_json(stream: TextIO, chunks: Iterable[str]) -> None:
    """Write JSON chunks immediately without joining them in memory."""
    for chunk in chunks:
        stream.write(chunk)


class AppriseResultStatus(IntEnum):
    """The overall outcome of a single notify() / async_notify() call.

    Values line up with CLI exit codes, so they can be passed to exit().
    """

    # Every matched/escalated service accepted the notification.
    SUCCESS = 0

    # A required service failed, or notify() received invalid arguments.
    FAILURE = 1

    # NOTE: 2 is intentionally unused because Click reserves it for invalid
    # command-line arguments.

    # No service was attempted: no loaded services or no tag match.
    # Only AppriseResult.status uses NOMATCH.
    NOMATCH = 3

    # Mixed overall result: at least one real success and one non-delivery.
    # Only AppriseResult.status uses PARTIAL.
    PARTIAL = 4

    # The service did not finish before its service or call deadline.
    TIMEOUT = 5


class NotifyAttempt:
    """The raw outcome of one service call or retry.

    Optional handling belongs to ``NotifyResult``. TIMEOUT means Apprise
    stopped waiting or skipped an attempt after its deadline.
    """

    def __init__(
        self,
        status: AppriseResultStatus,
        elapsed: float = 0.0,
        logs: Optional[Iterable[NotifyLogEntry]] = None,
    ) -> None:
        """Initialize the outcome, duration, and logs for one attempt."""
        # The raw outcome of this one call: SUCCESS, FAILURE, or TIMEOUT.
        # Never NOMATCH -- see the class docstring.
        self.status = status

        # A zero-second TIMEOUT means the deadline prevented another attempt.
        self.elapsed = elapsed

        # Derive start_time from end_time and elapsed so they always agree.
        self.end_time = datetime.now(timezone.utc)
        self.start_time = self.end_time - timedelta(seconds=self.elapsed)

        # Read disk-backed logs as needed; copy ordinary iterables.
        self.logs = (
            logs
            if isinstance(logs, _NotifyLogStore)
            else list(logs)
            if logs is not None
            else []
        )

    def iter_json(self) -> Iterator[str]:
        """Yield this attempt as bounded JSON chunks.

        Logs are read one at a time, including entries retained on disk.
        """
        # Write the small fixed fields before walking captured logs.
        yield '{{"status":{}'.format(
            json.dumps(self.status.name, separators=JSON_COMPACT_SEPARATORS)
        )

        yield ',"elapsed":{}'.format(
            json.dumps(self.elapsed, separators=JSON_COMPACT_SEPARATORS)
        )

        yield ',"start_time":{}'.format(
            json.dumps(
                self.start_time.strftime(AWARE_DATE_ISO_FORMAT),
                separators=JSON_COMPACT_SEPARATORS,
            )
        )

        yield ',"end_time":{}'.format(
            json.dumps(
                self.end_time.strftime(AWARE_DATE_ISO_FORMAT),
                separators=JSON_COMPACT_SEPARATORS,
            )
        )

        # Open the log array without first copying its entries into a list.
        yield ',"logs":['

        separator = ""
        for entry in self.logs:
            # Prefix every entry after the first with the JSON separator.
            yield separator
            yield entry.json()
            separator = ","

        # Close both the log array and this attempt object.
        yield "]}"

    def write_json(self, stream: TextIO) -> None:
        """Write this attempt to a text stream without joining its logs."""
        _write_json(stream, self.iter_json())

    def __bool__(self) -> bool:
        """Return ``True`` only when this attempt succeeded."""
        return self.status == AppriseResultStatus.SUCCESS

    def __iter__(self) -> Iterator[NotifyLogEntry]:
        """Iterate over log entries captured during this attempt."""
        # Lets callers do `for line in attempt:` to walk this one call's
        # captured log entries directly.
        return iter(self.logs)

    def __repr__(self) -> str:
        """Return a concise representation of the attempt outcome."""
        return "<NotifyAttempt status={!r} elapsed={!r}>".format(
            self.status.name, self.elapsed
        )


class NotifyResult:
    """The outcome of one service actually being notified this call.

    Contains every NotifyAttempt made for that service in dispatch order.
    Services skipped by priority escalation do not get a result.
    """

    def __init__(
        self,
        name: str,
        url: str,
        url_id: Optional[str] = None,
        tag: tuple[str, ...] = (),
        optional: bool = False,
        weight: int = 1,
        max_attempts: int = 1,
        attempts: Optional[list[NotifyAttempt]] = None,
    ) -> None:
        """Initialize one service result from its ordered attempts."""
        # Human readable service name, e.g. "Slack", "Discord".
        self.name = name

        # The privacy-obfuscated URL that identifies which endpoint was
        # notified (service.url(privacy=True)); safe to log/print/store.
        self.url = url

        # Stable URL identifier, when the plugin provides one.
        self.url_id = url_id

        # The tag(s) (as plain strings) this service was matched under.
        self.tag = tuple(tag)

        # Whether this service tolerates a non-SUCCESS outcome.
        self.optional = bool(optional)

        # Number of weighted delivery targets represented by this service.
        self.weight = weight

        # Maximum attempts allowed for this service.
        self.max_attempts = max_attempts

        # Every call actually made for this service, in order.  See
        # NotifyAttempt's docstring for what a TIMEOUT entry here means.
        self._attempts = list(attempts) if attempts else []

        # SUCCESS and TIMEOUT are terminal, so the last attempt decides first.
        last_status = (
            self._attempts[-1].status
            if self._attempts
            else AppriseResultStatus.FAILURE
        )

        if last_status == AppriseResultStatus.SUCCESS or self.optional:
            self.status = AppriseResultStatus.SUCCESS

        elif last_status == AppriseResultStatus.TIMEOUT and not any(
            a.status == AppriseResultStatus.FAILURE for a in self._attempts
        ):
            # No confirmed failure happened before Apprise ran out of time.
            self.status = AppriseResultStatus.TIMEOUT

        else:
            # A confirmed failure is more useful than a later timeout.
            self.status = AppriseResultStatus.FAILURE

        #  - start_time = the first attempt's own
        #  - end_time   = the last attempt's own
        #  - elapsed    = end_time - start_time
        if self._attempts:
            self.start_time = self._attempts[0].start_time
            self.end_time = self._attempts[-1].end_time

        else:
            # Fall back to 'now'
            self.end_time = datetime.now(timezone.utc)
            self.start_time = self.end_time

        self.elapsed = (self.end_time - self.start_time).total_seconds()

    @property
    def attempts(self) -> tuple[NotifyAttempt, ...]:
        """Read-only view of every NotifyAttempt made for this service,
        in the order they were made."""
        return tuple(self._attempts)

    def logs(self) -> Iterator[NotifyLogEntry]:
        """Yield every log entry captured across every attempt made for
        this service, sequentially, in the order the calls were made."""
        for attempt in self._attempts:
            yield from attempt.logs

    def iter_json(self) -> Iterator[str]:
        """Yield this service result as bounded JSON chunks."""
        # Service details are small and safe to encode one field at a time.
        fields = (
            ("name", self.name),
            ("url", self.url),
            ("url_id", self.url_id),
            ("tag", list(self.tag)),
            ("status", self.status.name),
            ("optional", self.optional),
            ("weight", self.weight),
            ("max_attempts", self.max_attempts),
            ("elapsed", self.elapsed),
            ("start_time", self.start_time.strftime(AWARE_DATE_ISO_FORMAT)),
            ("end_time", self.end_time.strftime(AWARE_DATE_ISO_FORMAT)),
        )

        yield "{"

        separator = ""
        for name, value in fields:
            # Encode both names and values so escaping follows normal JSON.
            yield "{}{}:{}".format(
                separator,
                json.dumps(name, separators=JSON_COMPACT_SEPARATORS),
                json.dumps(value, separators=JSON_COMPACT_SEPARATORS),
            )
            separator = ","

        # Attempts can contain disk-backed logs, so stream each nested object.
        yield ',"attempts":['

        separator = ""
        for attempt in self._attempts:
            yield separator
            yield from attempt.iter_json()
            separator = ","

        # Close both the attempts array and this service object.
        yield "]}"

    def write_json(self, stream: TextIO) -> None:
        """Write this service result to a text stream in bounded chunks."""
        _write_json(stream, self.iter_json())

    def __bool__(self) -> bool:
        """Return ``True`` when this service result is successful."""
        return self.status == AppriseResultStatus.SUCCESS

    def __len__(self) -> int:
        """Return the number of attempts made for this service."""
        return len(self._attempts)

    def __iter__(self) -> Iterator[NotifyAttempt]:
        """Iterate over this service's attempts in dispatch order."""
        # Lets callers do `for attempt in service_result:` to walk every
        # call made for this service.
        return iter(self._attempts)

    def __repr__(self) -> str:
        """Return a concise representation of the service outcome."""
        return "<NotifyResult name={!r} url={!r} status={!r}>".format(
            self.name, self.url, self.status.name
        )

    def close(self) -> None:
        """Release temporary log storage held by this service result."""
        for attempt in self._attempts:
            # List-backed attempts have no temporary resource to release.
            if isinstance(attempt.logs, _NotifyLogStore):
                attempt.logs.close()


class AppriseResult:
    """The overall outcome of one Apprise.notify() / async_notify() call.

    Wraps an ordered collection of NotifyResult entries (one per service
    actually dispatched) along with the overall AppriseResultStatus.
    """

    def __init__(
        self,
        status: AppriseResultStatus = AppriseResultStatus.NOMATCH,
        results: Optional[list[NotifyResult]] = None,
        elapsed: float = 0.0,
        call_logs: Optional[Iterable[NotifyLogEntry]] = None,
    ) -> None:
        """Initialize the overall status and ordered service results."""
        # Dispatch computes this because priority escalation affects outcome.
        self.status = status

        # Ordered list of every service actually dispatched, in the order
        # Apprise attempted them.
        self._results = list(results) if results else []

        # Wall-clock seconds across the complete call, including every
        # priority group, escalation round, and chain.
        self.elapsed = elapsed

        # Read disk-backed call logs as needed; copy ordinary iterables.
        self._call_logs = (
            call_logs
            if isinstance(call_logs, _NotifyLogStore)
            else list(call_logs)
            if call_logs is not None
            else []
        )

        # Derive start_time from end_time and elapsed so they always agree.
        self.end_time = datetime.now(timezone.utc)
        self.start_time = self.end_time - timedelta(seconds=self.elapsed)

    @property
    def results(self) -> tuple[NotifyResult, ...]:
        """Read-only view of every NotifyResult collected this call."""
        return tuple(self._results)

    def call_logs(self) -> Iterator[NotifyLogEntry]:
        """Yield orchestration logs without loading disk entries at once."""
        yield from self._call_logs

    @property
    def success_count(self) -> int:
        """Number of dispatched services whose (reflective) status is
        SUCCESS."""
        return sum(
            1 for r in self._results if r.status == AppriseResultStatus.SUCCESS
        )

    @property
    def failed_count(self) -> int:
        """Number of dispatched services whose (reflective) status is not
        SUCCESS."""
        return sum(
            1 for r in self._results if r.status != AppriseResultStatus.SUCCESS
        )

    @property
    def timeout_count(self) -> int:
        """Number of dispatched services whose status is TIMEOUT."""
        return sum(
            1 for r in self._results if r.status == AppriseResultStatus.TIMEOUT
        )

    def logs(self) -> Iterator[NotifyLogEntry]:
        """Yield all service and call-level logs in chronological order.

        Each capture is already ordered, so merge them without copying every
        entry into a second list.
        """
        # Merge the already ordered sources without building another list.
        streams = [result.logs() for result in self._results]
        # Call entries belong in the same timeline as service entries.
        streams.append(iter(self._call_logs))
        yield from heapq.merge(*streams)

    def iter_json(self) -> Iterator[str]:
        """Yield the complete result as bounded JSON chunks.

        Service and call logs remain lazy while the iterator is consumed.
        Keep the result open until iteration finishes.
        """
        # Encode the fixed summary without touching any captured logs.
        fields = (
            ("status", self.status.name),
            ("success_count", self.success_count),
            ("failed_count", self.failed_count),
            ("elapsed", self.elapsed),
            ("start_time", self.start_time.strftime(AWARE_DATE_ISO_FORMAT)),
            ("end_time", self.end_time.strftime(AWARE_DATE_ISO_FORMAT)),
        )

        yield "{"

        separator = ""
        for name, value in fields:
            yield "{}{}:{}".format(
                separator,
                json.dumps(name, separators=JSON_COMPACT_SEPARATORS),
                json.dumps(value, separators=JSON_COMPACT_SEPARATORS),
            )
            separator = ","

        # Stream each service and its attempts before moving to call logs.
        yield ',"results":['

        separator = ""
        for result in self._results:
            yield separator
            yield from result.iter_json()
            separator = ","

        yield '],"call_logs":['

        separator = ""
        for entry in self._call_logs:
            yield separator
            yield entry.json()
            separator = ","

        # Close the call-log array and the overall result object.
        yield "]}"

    def write_json(self, stream: TextIO) -> None:
        """Write the complete result to a text stream in bounded chunks."""
        _write_json(stream, self.iter_json())

    def __bool__(self) -> bool:
        """Return ``True`` only when the overall notification succeeded."""
        # Preserve the old boolean contract: only SUCCESS is truthy.
        return self.status == AppriseResultStatus.SUCCESS

    def __len__(self) -> int:
        """Return the number of services that were dispatched."""
        return len(self._results)

    def __iter__(self) -> Iterator[NotifyResult]:
        """Iterate over service results in dispatch order."""
        return iter(self._results)

    def __repr__(self) -> str:
        """Return a concise representation of the overall outcome."""
        return "<AppriseResult status={!r} count={}>".format(
            self.status.name, len(self._results)
        )

    def close(self) -> None:
        """Release temporary files used by captured result logs."""
        # Each service closes the stores owned by its attempts.
        for result in self._results:
            result.close()
        # The call capture can share the same temporary file.
        if isinstance(self._call_logs, _NotifyLogStore):
            self._call_logs.close()

    def __enter__(self) -> AppriseResult:
        """Return this result for use as a context manager."""
        return self

    def __exit__(self, *_: object) -> None:
        """Release temporary result-log files on context exit."""
        self.close()
