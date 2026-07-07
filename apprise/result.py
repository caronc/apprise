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

from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from enum import IntEnum
import json
from typing import Any, Optional

from .common import AWARE_DATE_ISO_FORMAT, JSON_COMPACT_SEPARATORS
from .logger import NotifyLogEntry


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

    # No service was attempted: no loaded servers or no tag match.
    # Only AppriseResult.status uses NOMATCH.
    NOMATCH = 3

    # Mixed overall result: at least one real success and one non-delivery.
    # Only AppriseResult.status uses PARTIAL.
    PARTIAL = 4

    # The service did not finish before its service or call deadline.
    TIMEOUT = 5


class NotifyAttempt:
    """The raw outcome of exactly one call to a service's notify()/
    async_notify() -- one retry within a dispatch, or one escalation-chain
    re-dispatch of the same service in a later priority tier.

    Optional-service forgiveness happens later at NotifyResult. TIMEOUT means
    Apprise stopped waiting, or skipped the next attempt after a deadline.
    """

    def __init__(
        self,
        status: AppriseResultStatus,
        elapsed: float = 0.0,
        logs: Optional[list[NotifyLogEntry]] = None,
    ) -> None:
        """Initialize the outcome, duration, and logs for one attempt."""
        # The raw outcome of this one call: SUCCESS, FAILURE, or TIMEOUT.
        # Never NOMATCH -- see the class docstring.
        self.status = status

        # Wall-clock seconds this one call took.  0.0 for a TIMEOUT entry
        # that represents a decision not to start a new call at all (as
        # opposed to one that was abandoned mid-flight).
        self.elapsed = elapsed

        # Derive start_time from end_time and elapsed so they always agree.
        self.end_time = datetime.now(timezone.utc)
        self.start_time = self.end_time - timedelta(seconds=self.elapsed)

        # Every WARNING+ message the plugin logged during this one call.
        self.logs = list(logs) if logs else []

    def asdict(self) -> dict[str, Any]:
        """Return this attempt as a plain, JSON-serializable dict."""
        return {
            "status": self.status.name,
            "elapsed": self.elapsed,
            "start_time": self.start_time.strftime(AWARE_DATE_ISO_FORMAT),
            "end_time": self.end_time.strftime(AWARE_DATE_ISO_FORMAT),
            "logs": [entry.asdict() for entry in self.logs],
        }

    def json(self) -> str:
        """Return this attempt as a JSON string."""
        return json.dumps(self.asdict(), separators=JSON_COMPACT_SEPARATORS)

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

    def asdict(self) -> dict[str, Any]:
        """Return this result as a plain, JSON-serializable dict."""
        return {
            "name": self.name,
            "url": self.url,
            "url_id": self.url_id,
            "tag": list(self.tag),
            "status": self.status.name,
            "optional": self.optional,
            "weight": self.weight,
            "max_attempts": self.max_attempts,
            "elapsed": self.elapsed,
            "start_time": self.start_time.strftime(AWARE_DATE_ISO_FORMAT),
            "end_time": self.end_time.strftime(AWARE_DATE_ISO_FORMAT),
            "attempts": [a.asdict() for a in self._attempts],
        }

    def json(self) -> str:
        """Return this result as a JSON string."""
        return json.dumps(self.asdict(), separators=JSON_COMPACT_SEPARATORS)

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

        # Derive start_time from end_time and elapsed so they always agree.
        self.end_time = datetime.now(timezone.utc)
        self.start_time = self.end_time - timedelta(seconds=self.elapsed)

    @property
    def results(self) -> tuple[NotifyResult, ...]:
        """Read-only view of every NotifyResult collected this call."""
        return tuple(self._results)

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
        """Yield every log entry captured across every service and every
        attempt made this call, in chronological order.

        Concurrent service logs are sorted back into one timeline.
        """
        all_entries = (
            entry for result in self._results for entry in result.logs()
        )
        yield from sorted(all_entries)

    def asdict(self) -> dict[str, Any]:
        """Return this result as a plain, JSON-serializable dict."""
        return {
            "status": self.status.name,
            "success_count": self.success_count,
            "failed_count": self.failed_count,
            "elapsed": self.elapsed,
            "start_time": self.start_time.strftime(AWARE_DATE_ISO_FORMAT),
            "end_time": self.end_time.strftime(AWARE_DATE_ISO_FORMAT),
            "results": [r.asdict() for r in self._results],
        }

    def json(self) -> str:
        """Return this result as a JSON string."""
        return json.dumps(self.asdict(), separators=JSON_COMPACT_SEPARATORS)

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
