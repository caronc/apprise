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

"""Run notification attempts and build their results.

This module handles retries, priority groups, time limits, and failures.
"""

from __future__ import annotations

import logging
import math
import time
from typing import Any, Optional, Union

from .asset import AppriseAsset
from .common import APPRISE_MAX_SERVICE_RETRY
from .exception import AppriseImproperlyConfigured
from .logger import NotifyLogEntry, _ServiceLogCapture, logger
from .plugins.base import (
    NotifyBase,
    _delivery_memo,
    _delivery_tracker,
)
from .result import AppriseResultStatus, NotifyAttempt, NotifyResult


def safe_attr(service: NotifyBase, name: str, default: Any) -> Any:
    """Read a plugin attribute, returning ``default`` if it raises.

    This also protects callers when a plugin property fails while being read.
    """
    try:
        return getattr(service, name, default)

    except Exception:
        # Use the backup value instead of hiding the original plugin failure.
        return default


def service_metadata(
    service: NotifyBase,
) -> tuple[str, str, Optional[str], tuple[str, ...], int]:
    """Return ``(name, url, url_id, tags, weight)`` with safe defaults.

    A plugin may fail while providing these details, so each value has a
    simple backup.
    """
    # Each of these is plugin-supplied, so read it defensively.
    name = safe_attr(service, "service_name", "Unknown")

    try:
        # Hide private URL values before placing the URL in a result.
        url = service.url(privacy=True)

    except Exception:
        # A result still needs a usable URL-shaped value.
        url = "unknown://"

    try:
        # The short ID helps callers match this result to a service.
        url_id = service.url_id()

    except Exception:
        # Not every malformed or custom service can create an ID.
        url_id = None

    try:
        # Weight normally says how many targets the service represents.
        weight = len(service)

    except Exception:
        # Count an unknown service as one target.
        weight = 1

    try:
        # Sort tags for stable output; custom tags may fail to become text.
        tag = tuple(sorted(str(t) for t in safe_attr(service, "tags", ())))

    except Exception:
        # Bad custom tags should not stop the result from being returned.
        tag = ()

    # Always return the same five fields, even when some use backups.
    return name, url, url_id, tag, weight


def service_crashed(service: NotifyBase, e: BaseException) -> NotifyResult:
    """Log an unexpected dispatch error and return a failed result.

    Service details use safe defaults so a broken plugin cannot hide the
    original failure or stop the rest of the batch.
    """
    # Gather as many safe service details as the plugin can provide.
    name, url, url_id, tag, weight = service_metadata(service)

    # Report the failure using the safe name rather than re-reading it.
    logger.warning("Notification service '%s' raised an exception.", name)
    logger.debug("Notification Exception: %s", str(e))

    # Keep the usual result shape even though no normal attempt completed.
    return NotifyResult(
        name=name,
        url=url,
        url_id=url_id,
        tag=tag,
        # A raising optional property is treated as "not optional".
        optional=safe_attr(service, "optional", False),
        weight=weight,
        max_attempts=1,
        # Add one failure because no normal attempt details are available.
        attempts=[NotifyAttempt(status=AppriseResultStatus.FAILURE)],
    )


def dispatch_crashed(e: BaseException) -> None:
    """Log a batch failure that escaped normal service handling.

    With no later priority group to try, the caller receives a failed result
    instead of the exception.
    """
    # Keep the normal message short and place details at debug level.
    logger.warning("Notification dispatch raised an exception.")
    logger.debug("Notification Exception: %s", str(e))


def compute_deadline(
    service: NotifyBase, call_deadline: Optional[float]
) -> Optional[float]:
    """Return the time when Apprise must stop waiting for one service.

    The earlier of these limits wins:

    - The service's ``service_timeout`` setting.
    - The shared deadline created by ``notify(timeout=...)`` for the call.

    The worker receives the same deadline, so time spent in a queue still
    counts. ``None`` means that neither limit is enabled.
    """
    # Read the service limit, using the normal asset default if needed.
    service_timeout = getattr(
        service.asset,
        "_service_timeout",
        AppriseAsset._service_timeout,
    )
    # Turn the number of seconds into one fixed end time.
    deadline = time.monotonic() + service_timeout if service_timeout else None
    if call_deadline is not None:
        # The first limit reached always wins.
        deadline = (
            call_deadline if deadline is None else min(deadline, call_deadline)
        )

    # TRACE keeps large batches from spamming normal DEBUG output.
    logger.trace(
        "Deadline for '%s': %s",
        safe_attr(service, "service_name", "Unknown"),
        "none"
        if deadline is None
        else "{:.3f}s from now".format(deadline - time.monotonic()),
    )
    return deadline


def timeout_result(
    service: NotifyBase,
    elapsed: float,
    max_attempts: int,
) -> NotifyResult:
    """Build a timeout result after Apprise stops waiting for a service.

    The worker may still be running. ``NotifyResult`` handles optional
    services.
    """
    # Preserve normal service details in the timeout response.
    name, url, url_id, tag, weight = service_metadata(service)

    # Record the timeout as the only attempt known to this caller.
    return NotifyResult(
        name=name,
        url=url,
        url_id=url_id,
        tag=tag,
        optional=safe_attr(service, "optional", False),
        weight=weight,
        # Preserve the configured retry count even when the outer wait wins.
        max_attempts=max_attempts,
        attempts=[
            NotifyAttempt(
                status=AppriseResultStatus.TIMEOUT,
                elapsed=elapsed,
                logs=[timeout_log_entry(name, elapsed)],
            )
        ],
    )


def timeout_log_entry(name: str, elapsed: float) -> NotifyLogEntry:
    """Log and return a consistent error entry for a service timeout."""
    # Use the same readable message in application logs and the result.
    message = f"Service '{name}' did not finish within {elapsed:.3f}s."

    # Keep this out of the call-level capture.  The caller stores the entry
    # below on the attempt itself, so capturing it too would list the same
    # timeout twice in the merged result logs.
    logger.error(message, extra={"apprise_capture": False})

    # Store the level as text because NotifyLogEntry is public result data.
    return NotifyLogEntry(level="ERROR", message=message)


def validate_timeout(value: Union[int, float]) -> float:
    """Validate a timeout value shared by notify()/async_notify()."""
    # Booleans are numbers in Python, but are not useful time limits.
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise AppriseImproperlyConfigured("timeout must be an int or float.")

    # Reject negative or infinite values; zero means no call-wide limit.
    if not math.isfinite(value) or value < 0:
        raise AppriseImproperlyConfigured("timeout must be >= 0 and finite.")

    return float(value)


def aggregate_status(
    ok: bool, results: list[NotifyResult]
) -> AppriseResultStatus:
    """Combine service results into SUCCESS, PARTIAL, FAILURE, or TIMEOUT.

    A real success makes a mixed batch PARTIAL; otherwise FAILURE beats
    TIMEOUT.
    """
    if ok:
        # The dispatcher confirmed that every required service succeeded.
        return AppriseResultStatus.SUCCESS

    # Count actual deliveries, not optional services that were allowed to fail.
    if any(
        attempt.status == AppriseResultStatus.SUCCESS
        for result in results
        for attempt in result.attempts
    ):
        # At least one real delivery worked, so the batch partly succeeded.
        return AppriseResultStatus.PARTIAL

    if any(r.status == AppriseResultStatus.FAILURE for r in results):
        # A normal failure is more useful to report than a timeout.
        return AppriseResultStatus.FAILURE

    if any(r.status == AppriseResultStatus.TIMEOUT for r in results):
        # Nothing succeeded normally, but at least one service timed out.
        return AppriseResultStatus.TIMEOUT

    # Use failure when no more specific result explains the call.
    return AppriseResultStatus.FAILURE


def template_status(
    status: AppriseResultStatus,
    skipped: list,
) -> AppriseResultStatus:
    """Prevent skipped template entries from reporting a clean success."""
    if not skipped:
        # Nothing was skipped, so the original status is complete.
        return status

    if status == AppriseResultStatus.SUCCESS:
        # Delivered entries succeeded, but the full request was incomplete.
        return AppriseResultStatus.PARTIAL

    if status == AppriseResultStatus.NOMATCH:
        # Every matching template entry was skipped before dispatch.
        return AppriseResultStatus.FAILURE

    return status


def resolve_retry_count(service: NotifyBase, kwargs: dict[str, Any]) -> int:
    """Consume a retry override and clamp it to the plugin URL limit."""
    # Pop first so a valid override does not read a broken plugin property.
    retry = kwargs.pop("_retry_override", None)
    if retry is None:
        # No override, so fall back to the service's normal retry count.
        retry = safe_attr(service, "retry", 0)

    try:
        # Accept numeric text. Infinity raises OverflowError during conversion.
        retry = int(retry)

    except (TypeError, ValueError, OverflowError):
        # If the override is invalid, try the service's configured value.
        try:
            retry = int(safe_attr(service, "retry", 0))

        except (TypeError, ValueError, OverflowError):
            # Neither value is a number; fall back to no retries at all.
            retry = 0
    # Never allow a negative or unexpectedly large retry loop.
    return max(0, min(retry, APPRISE_MAX_SERVICE_RETRY))


def configured_max_attempts(
    service: NotifyBase, kwargs: dict[str, Any]
) -> int:
    """Return the attempt limit without consuming the worker's override."""
    # Resolve a copy so the worker receives the original private override.
    return resolve_retry_count(service, dict(kwargs)) + 1


def finalize_service_result(
    service: NotifyBase,
    retry: int,
    attempts: list[NotifyAttempt],
) -> tuple[bool, NotifyResult]:
    """Build one service result from its completed delivery attempts."""
    # Optional services can fail quietly, but keep a log breadcrumb.
    optional = safe_attr(service, "optional", False)
    succeeded = any(a.status == AppriseResultStatus.SUCCESS for a in attempts)

    # Read plugin details only after every attempt has finished.
    name, url, url_id, tag, weight = service_metadata(service)

    if not succeeded and optional:
        logger.info(
            "Optional service '%s' did not send successfully; continuing.",
            name,
        )

    # Combine service details with the ordered list of attempts.
    notify_result = NotifyResult(
        name=name,
        url=url,
        url_id=url_id,
        tag=tag,
        optional=optional,
        weight=weight,
        max_attempts=retry + 1,
        attempts=attempts,
    )

    # Return both the convenient boolean and the detailed result.
    return bool(notify_result), notify_result


class TagChain:
    """Track service groups as they move through a priority chain.

    The chain stops after its first successful group.
    """

    __slots__ = ("groups", "index", "key", "priorities", "succeeded")

    def __init__(self, key: str, groups: dict[int, list]) -> None:
        """Prepare one chain from its priority groups."""
        # The OR tag this chain covers. "" represents the catch-all chain.
        self.key = key

        # Its service groups, and those group priorities in order.
        self.groups = groups
        self.priorities = sorted(groups)

        # Where the chain sits now, and whether it is finished.
        self.index = 0
        self.succeeded = False

    @property
    def exhausted(self) -> bool:
        """True once every priority group has been tried."""
        # The index moves forward once for every failed group.
        return self.index >= len(self.priorities)

    @property
    def pending(self) -> bool:
        """True while this chain still has a group left to try."""
        # A successful or exhausted chain has no more work.
        return not self.succeeded and not self.exhausted

    @property
    def priority(self) -> int:
        """Priority of the group this chain will try next."""
        # Priorities were sorted when the chain was created.
        return self.priorities[self.index]

    @property
    def batch(self) -> list:
        """Services in the group this chain will try next."""
        # Look up the group selected by the current priority.
        return self.groups[self.priority]

    def settle(self, ok: bool) -> None:
        """Record how the current group did.

        A success finishes the chain.  A failure moves it on to the next,
        less urgent, priority group.
        """
        if ok:
            # A successful group completes this chain immediately.
            logger.trace(
                "Chain '%s' priority group %s succeeded.",
                self.key,
                self.priority,
            )
            self.succeeded = True
            return

        # A failed group allows the next, less urgent group to run.
        logger.trace(
            "Chain '%s' priority group %s failed; escalating.",
            self.key,
            self.priority,
        )
        self.index += 1

    def crashed(self, e: BaseException) -> None:
        """Record a group that raised, and move the chain along."""
        # Treat an unexpected error like a failed priority group.
        logger.warning(
            "Notification chain '%s' priority group %s raised an exception.",
            self.key,
            self.priority,
        )
        logger.debug("Notification Exception: %s", str(e))
        self.index += 1


class RetryRunner:
    """Track one service's attempts for both delivery modes.

    The caller runs the service and waits between attempts.
    """

    def __init__(
        self,
        service: NotifyBase,
        kwargs: dict[str, Any],
        deadline: Optional[float],
    ) -> None:
        """Prepare the retry options for one service call."""
        # The service being notified, and the caller's absolute time limit.
        self.service = service
        self.deadline = deadline

        # Read the name once so a failing plugin property cannot break later
        # log messages.
        self.name = safe_attr(service, "service_name", "Unknown")

        # How many extra tries are allowed, and the pause between them.
        self.retry = resolve_retry_count(service, kwargs)
        self.wait = safe_attr(service, "wait", 0.0)

        # Pop the per-call overrides so they stay internal.
        self.log_callback = kwargs.pop("_log_callback", None)
        self.log_level = kwargs.pop("_log_level", None)

        # Every call actually made, in order.
        self.attempts: list[NotifyAttempt] = []

        # Remember successful targets only while retries are active.
        self._token = _delivery_tracker.set(set()) if self.retry else None

        # Somewhere for a plugin to park work its own retries can reuse.
        self._memo_token = _delivery_memo.set({}) if self.retry else None

    @property
    def total(self) -> int:
        """Total attempts allowed, counting the first one."""
        # retry counts only extra tries, so include the original call.
        return self.retry + 1

    def begin(self, attempt: int) -> Optional[float]:
        """Start an attempt, or record TIMEOUT and return ``None`` if late."""
        # Do not start new delivery work after the caller's time limit.
        if self.deadline is not None and time.monotonic() >= self.deadline:
            logger.trace(
                "Deadline already passed for '%s'; skipping attempt %d/%d.",
                self.name,
                attempt + 1,
                self.total,
            )
            # No call began, so there is no delivery time to record.
            self.attempts.append(
                NotifyAttempt(
                    status=AppriseResultStatus.TIMEOUT,
                    logs=[timeout_log_entry(self.name, 0.0)],
                )
            )
            return None

        # Save a start time so the result can report the attempt's duration.
        logger.trace(
            "Starting attempt %d/%d for '%s'.",
            attempt + 1,
            self.total,
            self.name,
        )
        return time.monotonic()

    def capture(self) -> _ServiceLogCapture:
        """Build the log capture that wraps a single attempt."""
        # Use WARNING unless the caller requested another capture level.
        return _ServiceLogCapture(
            self.service,
            log_callback=self.log_callback,
            level=(
                self.log_level
                if self.log_level is not None
                else logging.WARNING
            ),
        )

    def crashed(self, e: Exception) -> None:
        """Log a plugin that raised, so it counts as a failed attempt."""
        # Keep the main message short and the exception detail at DEBUG.
        logger.warning(
            "Notification service '%s' raised an exception.",
            self.name,
        )
        logger.debug("Notification Exception: %s", str(e))

    def record(
        self,
        attempt: int,
        result: bool,
        started: float,
        capture: _ServiceLogCapture,
    ) -> bool:
        """Store an attempt and return whether the caller can stop early."""
        # Measure the service call without including the earlier retry wait.
        elapsed = time.monotonic() - started
        logger.trace(
            "Attempt %d/%d for '%s' finished in %.3fs: %s.",
            attempt + 1,
            self.total,
            self.name,
            elapsed,
            "success" if result else "failure",
        )
        # Keep the outcome and any logs captured while this attempt ran.
        self.attempts.append(
            NotifyAttempt(
                # Convert the plugin's True/False answer to a result status.
                status=(
                    AppriseResultStatus.SUCCESS
                    if result
                    else AppriseResultStatus.FAILURE
                ),
                elapsed=elapsed,
                logs=capture.entries,
            )
        )

        # True tells the retry loop that no more attempts are needed.
        return bool(result)

    def delay(self, attempt: int) -> float:
        """Return the retry delay without waiting past the deadline.

        Zero means no wait, including after the final attempt.
        """
        if attempt >= self.retry:
            # That was the last try, so there is nothing to announce.
            return 0.0

        logger.warning(
            "Attempt %d/%d for '%s' failed; trying again.",
            attempt + 1,
            self.total,
            self.name,
        )

        if self.wait <= 0:
            # A zero wait starts the next attempt immediately.
            return 0.0

        if self.deadline is None:
            # With no time limit, use the full configured wait.
            return self.wait

        # Shorten the wait when the deadline will arrive first.
        return min(self.wait, max(0.0, self.deadline - time.monotonic()))

    def close(self) -> None:
        """Drop the delivery tracker so it cannot outlive this call."""
        if self._token is not None:
            # Restore the previous tracking state for this thread or task.
            _delivery_tracker.reset(self._token)

        if self._memo_token is not None:
            # The notification is over; its working state goes with it.
            _delivery_memo.reset(self._memo_token)

    def result(self) -> tuple[bool, NotifyResult]:
        """Return the finished (success, NotifyResult) pair."""
        # All attempts are now complete and ready for the public result.
        return finalize_service_result(self.service, self.retry, self.attempts)


def call_with_retry(
    service: NotifyBase,
    kwargs: dict[str, Any],
    deadline: Optional[float],
) -> tuple[bool, NotifyResult]:
    """Run one service with retries, logging, and a fixed end time.

    Ordered and worker-thread delivery share this path.
    """
    # Keep shared retry state in one small helper object.
    runner = RetryRunner(service, kwargs, deadline)
    try:
        # The first pass is normal delivery; later passes are retries.
        for attempt in range(runner.total):
            started = runner.begin(attempt)
            if started is None:
                break

            # Treat validation errors and plugin crashes as retriable
            # failures so the next attempt still gets a turn.
            with runner.capture() as capture:
                try:
                    result = service.notify(**kwargs)

                except TypeError:
                    result = False

                except Exception as e:
                    runner.crashed(e)
                    result = False

            if runner.record(attempt, result, started, capture):
                # A successful delivery ends the retry loop.
                break

            # Wait only when another attempt remains and time allows it.
            delay = runner.delay(attempt)
            if delay > 0:
                time.sleep(delay)

    finally:
        # Always clean up tracking, even after an unexpected exception.
        runner.close()

    # Build the public result from every attempt made above.
    return runner.result()
