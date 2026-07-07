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

# Disable logging for a cleaner testing output
from datetime import datetime, timezone
from json import loads
import logging

from apprise.common import AWARE_DATE_ISO_FORMAT
from apprise.logger import NotifyLogEntry
from apprise.result import (
    AppriseResult,
    AppriseResultStatus,
    NotifyAttempt,
    NotifyResult,
)

logging.disable(logging.CRITICAL)


def test_notify_log_entry():
    """NotifyLogEntry: attributes, asdict(), json(), __str__/__repr__."""

    entry = NotifyLogEntry(level="WARNING", message="HTTP 403 Forbidden")

    assert entry.level == "WARNING"
    assert entry.message == "HTTP 403 Forbidden"
    assert entry.time.tzinfo is not None
    assert entry.asdict() == {
        "level": "WARNING",
        "message": "HTTP 403 Forbidden",
        "time": entry.time.strftime(AWARE_DATE_ISO_FORMAT),
    }
    assert loads(entry.json()) == entry.asdict()
    # __str__ mirrors Python logging's own default format:
    # "%(asctime)s - %(levelname)s - %(message)s".
    expected_asctime = "{},{:03d}".format(
        entry.time.strftime("%Y-%m-%d %H:%M:%S"),
        entry.time.microsecond // 1000,
    )
    assert str(entry) == (f"{expected_asctime} - WARNING - HTTP 403 Forbidden")
    assert "WARNING" in repr(entry)
    assert "HTTP 403 Forbidden" in repr(entry)


def test_notify_log_entry_time_defaults_to_now():
    """NotifyLogEntry.time defaults to now() when constructed directly
    (e.g. in tests) without an explicit time= from a real LogRecord."""

    before = datetime.now(timezone.utc)
    entry = NotifyLogEntry(level="WARNING", message="test")
    after = datetime.now(timezone.utc)

    assert before <= entry.time <= after


def test_notify_log_entry_explicit_time():
    """NotifyLogEntry accepts an explicit time=, as _ServiceLogCapture.emit()
    does from the underlying LogRecord's own timestamp."""

    when = datetime(2026, 1, 1, tzinfo=timezone.utc)
    entry = NotifyLogEntry(level="ERROR", message="test", time=when)

    assert entry.time == when


def test_notify_attempt_defaults():
    """NotifyAttempt: default construction requires only status."""

    attempt = NotifyAttempt(status=AppriseResultStatus.SUCCESS)

    assert attempt.status == AppriseResultStatus.SUCCESS
    assert attempt.elapsed == 0.0
    assert attempt.logs == []
    assert bool(attempt) is True


def test_notify_attempt_bool_matches_status():
    """NotifyAttempt.__bool__ is True only for status=SUCCESS -- raw,
    never adjusted for optional=."""

    success = NotifyAttempt(status=AppriseResultStatus.SUCCESS)
    failure = NotifyAttempt(status=AppriseResultStatus.FAILURE)
    timeout = NotifyAttempt(status=AppriseResultStatus.TIMEOUT)

    assert bool(success) is True
    assert bool(failure) is False
    assert bool(timeout) is False


def test_notify_attempt_start_end_time_match_elapsed():
    """start_time/end_time are always populated and their difference is
    exactly elapsed -- by construction, not by measurement, so there is
    no separate clock to drift out of sync."""

    before = datetime.now(timezone.utc)
    attempt = NotifyAttempt(status=AppriseResultStatus.SUCCESS, elapsed=3.5)
    after = datetime.now(timezone.utc)

    assert attempt.start_time.tzinfo is not None
    assert attempt.end_time.tzinfo is not None
    assert (attempt.end_time - attempt.start_time).total_seconds() == 3.5
    assert before <= attempt.end_time <= after
    parsed = datetime.strptime(
        attempt.asdict()["start_time"], AWARE_DATE_ISO_FORMAT
    )
    assert parsed == attempt.start_time


def test_notify_attempt_iterates_logs():
    """NotifyAttempt iterates directly over its own captured log entries."""

    logs = [
        NotifyLogEntry(level="WARNING", message="rate limited"),
        NotifyLogEntry(level="ERROR", message="invalid token"),
    ]
    attempt = NotifyAttempt(
        status=AppriseResultStatus.FAILURE, elapsed=0.2, logs=logs
    )

    assert list(attempt) == logs
    messages = [str(entry) for entry in attempt]
    assert " - WARNING - rate limited" in messages[0]
    assert " - ERROR - invalid token" in messages[1]


def test_notify_attempt_asdict_and_json():
    """NotifyAttempt.asdict()/json() serialize every field, logs included."""

    logs = [NotifyLogEntry(level="WARNING", message="HTTP 429")]
    attempt = NotifyAttempt(
        status=AppriseResultStatus.FAILURE, elapsed=0.5, logs=logs
    )

    expected = {
        "status": "FAILURE",
        "elapsed": 0.5,
        "start_time": attempt.start_time.strftime(AWARE_DATE_ISO_FORMAT),
        "end_time": attempt.end_time.strftime(AWARE_DATE_ISO_FORMAT),
        "logs": [logs[0].asdict()],
    }
    assert attempt.asdict() == expected
    assert loads(attempt.json()) == expected
    assert ", " not in attempt.json()
    assert ": " not in attempt.json()


def test_notify_attempt_repr():
    """NotifyAttempt.__repr__ is a compact, informative one-liner."""

    attempt = NotifyAttempt(status=AppriseResultStatus.TIMEOUT, elapsed=1.2)
    text = repr(attempt)

    assert "TIMEOUT" in text
    assert "1.2" in text


def test_notify_result_defaults():
    """NotifyResult: default construction requires only name/url, and
    with no attempts given reports FAILURE (nothing ever succeeded)."""

    result = NotifyResult(name="Slack", url="slack://t/ch")

    assert result.name == "Slack"
    assert result.url == "slack://t/ch"
    assert result.url_id is None
    assert result.tag == ()
    assert result.status == AppriseResultStatus.FAILURE
    assert bool(result) is False
    assert result.optional is False
    assert result.weight == 1
    assert result.max_attempts == 1
    assert result.attempts == ()
    assert len(result) == 0
    assert result.elapsed == 0.0
    assert list(result.logs()) == []


def test_notify_result_status_reflects_any_success():
    """.status is SUCCESS if any attempt succeeded, regardless of earlier
    failed attempts."""

    result = NotifyResult(
        name="Slack",
        url="slack://t/ch",
        max_attempts=3,
        attempts=[
            NotifyAttempt(status=AppriseResultStatus.FAILURE),
            NotifyAttempt(status=AppriseResultStatus.SUCCESS),
        ],
    )

    assert result.status == AppriseResultStatus.SUCCESS
    assert bool(result) is True
    assert len(result) == 2


def test_notify_result_status_pure_timeout_no_failure():
    """.status is TIMEOUT when Apprise gave up waiting without ever
    seeing a confirmed failure from this service -- e.g. the deadline
    had already passed before any attempt could even start, or the one
    attempt made was abandoned mid-flight rather than completing."""

    result = NotifyResult(
        name="Slack",
        url="slack://t/ch",
        attempts=[NotifyAttempt(status=AppriseResultStatus.TIMEOUT)],
    )

    assert result.status == AppriseResultStatus.TIMEOUT
    assert bool(result) is False


def test_notify_result_status_failure_trumps_timeout():
    """.status is FAILURE, not TIMEOUT, when at least one attempt
    confirmed a real failure before Apprise later gave up waiting on a
    further retry -- a confirmed failure is more informative than "ran
    out of time" and takes priority over it."""

    result = NotifyResult(
        name="Slack",
        url="slack://t/ch",
        attempts=[
            NotifyAttempt(status=AppriseResultStatus.FAILURE),
            NotifyAttempt(status=AppriseResultStatus.TIMEOUT),
        ],
    )

    assert result.status == AppriseResultStatus.FAILURE
    assert bool(result) is False


def test_notify_result_status_failure_trumps_timeout_multiple_retries():
    """The same FAILURE-over-TIMEOUT priority holds regardless of how
    many failed retries preceded the eventual TIMEOUT."""

    result = NotifyResult(
        name="Slack",
        url="slack://t/ch",
        attempts=[
            NotifyAttempt(status=AppriseResultStatus.FAILURE),
            NotifyAttempt(status=AppriseResultStatus.FAILURE),
            NotifyAttempt(status=AppriseResultStatus.FAILURE),
            NotifyAttempt(status=AppriseResultStatus.TIMEOUT),
        ],
    )

    assert result.status == AppriseResultStatus.FAILURE


def test_notify_result_optional_absorbs_failure_trumping_timeout():
    """optional=True still absorbs a FAILURE-trumps-TIMEOUT outcome into
    SUCCESS, same as it would a plain FAILURE or a plain TIMEOUT."""

    result = NotifyResult(
        name="Slack",
        url="slack://t/ch",
        optional=True,
        attempts=[
            NotifyAttempt(status=AppriseResultStatus.FAILURE),
            NotifyAttempt(status=AppriseResultStatus.TIMEOUT),
        ],
    )

    assert result.status == AppriseResultStatus.SUCCESS


def test_notify_result_status_failure_when_no_timeout_no_success():
    """.status is FAILURE when every attempt failed outright (no
    TIMEOUT, no SUCCESS, no optional)."""

    result = NotifyResult(
        name="Slack",
        url="slack://t/ch",
        attempts=[NotifyAttempt(status=AppriseResultStatus.FAILURE)],
    )

    assert result.status == AppriseResultStatus.FAILURE


def test_notify_result_optional_absorbs_failure():
    """optional=True remaps a failed outcome's reflective .status to
    SUCCESS, even though the underlying NotifyAttempt stays raw."""

    result = NotifyResult(
        name="Slack",
        url="slack://t/ch",
        optional=True,
        attempts=[NotifyAttempt(status=AppriseResultStatus.FAILURE)],
    )

    assert result.status == AppriseResultStatus.SUCCESS
    assert bool(result) is True
    # The raw attempt itself is untouched by optional=.
    assert next(iter(result)).status == AppriseResultStatus.FAILURE


def test_notify_result_optional_absorbs_timeout():
    """optional=True also absorbs a TIMEOUT outcome the same way it
    absorbs a plain FAILURE."""

    result = NotifyResult(
        name="Slack",
        url="slack://t/ch",
        optional=True,
        attempts=[NotifyAttempt(status=AppriseResultStatus.TIMEOUT)],
    )

    assert result.status == AppriseResultStatus.SUCCESS
    assert next(iter(result)).status == AppriseResultStatus.TIMEOUT


def test_notify_result_optional_does_not_mask_success():
    """optional=True on an already-successful result is a no-op --
    .status is still simply SUCCESS."""

    result = NotifyResult(
        name="Slack",
        url="slack://t/ch",
        optional=True,
        attempts=[NotifyAttempt(status=AppriseResultStatus.SUCCESS)],
    )

    assert result.status == AppriseResultStatus.SUCCESS


def test_notify_result_weight():
    """.weight defaults to 1 and stores whatever value is given (e.g. a
    plugin's own target count via len(service))."""

    default = NotifyResult(name="Slack", url="slack://t/ch")
    fanned_out = NotifyResult(name="Twilio", url="twilio://x", weight=50)

    assert default.weight == 1
    assert fanned_out.weight == 50


def test_notify_result_max_attempts_ratio():
    """max_attempts is the configured ceiling; len(result)/.attempts show
    how many were actually used -- e.g. 1/3 means the first try
    succeeded."""

    result = NotifyResult(
        name="Telegram",
        url="tgram://bot/chat",
        url_id="abc123",
        max_attempts=3,
        attempts=[NotifyAttempt(status=AppriseResultStatus.SUCCESS)],
    )

    assert result.url_id == "abc123"
    assert result.max_attempts == 3
    assert len(result) == 1
    assert len(result.attempts) == 1


def test_notify_result_start_end_time_span_all_attempts():
    """start_time is the first attempt's start, end_time is the last
    attempt's end, and elapsed is the difference between them -- not the
    sum of each attempt's own elapsed."""

    first = NotifyAttempt(status=AppriseResultStatus.FAILURE, elapsed=1.0)
    second = NotifyAttempt(status=AppriseResultStatus.SUCCESS, elapsed=1.0)
    result = NotifyResult(
        name="Slack", url="slack://t/ch", attempts=[first, second]
    )

    assert result.start_time == first.start_time
    assert result.end_time == second.end_time
    assert result.elapsed == (
        (second.end_time - first.start_time).total_seconds()
    )


def test_notify_result_start_end_time_default_when_no_attempts():
    """With no attempts at all, start_time/end_time still coincide --
    never left unset."""

    result = NotifyResult(name="Slack", url="slack://t/ch")
    assert result.start_time == result.end_time


def test_notify_result_iterates_attempts():
    """NotifyResult iterates over its NotifyAttempt entries, not log
    lines directly -- use .logs() for a flattened log view."""

    a1 = NotifyAttempt(status=AppriseResultStatus.FAILURE)
    a2 = NotifyAttempt(status=AppriseResultStatus.SUCCESS)
    result = NotifyResult(
        name="Telegram", url="tgram://bot/chat", attempts=[a1, a2]
    )

    assert list(result) == [a1, a2]
    assert result.attempts == (a1, a2)


def test_notify_result_logs_flattens_every_attempt_in_order():
    """NotifyResult.logs() yields every log entry across every attempt,
    in call order."""

    logs1 = [NotifyLogEntry(level="WARNING", message="rate limited")]
    logs2 = [NotifyLogEntry(level="ERROR", message="invalid token")]
    result = NotifyResult(
        name="Telegram",
        url="tgram://bot/chat",
        attempts=[
            NotifyAttempt(status=AppriseResultStatus.FAILURE, logs=logs1),
            NotifyAttempt(status=AppriseResultStatus.SUCCESS, logs=logs2),
        ],
    )

    assert list(result.logs()) == logs1 + logs2


def test_notify_result_optional_and_tag():
    """NotifyResult carries the tag tuple and optional flag through."""

    result = NotifyResult(
        name="Discord",
        url="discord://w/t",
        tag=("devops", "alerts"),
        optional=True,
        attempts=[NotifyAttempt(status=AppriseResultStatus.FAILURE)],
    )

    assert result.tag == ("devops", "alerts")
    assert result.optional is True
    # Absorbed by optional=True.
    assert bool(result) is True


def test_notify_result_asdict_and_json():
    """NotifyResult.asdict()/json() serialize every field, with nested
    per-attempt detail (including each attempt's own logs)."""

    logs = [NotifyLogEntry(level="WARNING", message="HTTP 429")]
    attempt = NotifyAttempt(
        status=AppriseResultStatus.FAILURE, elapsed=0.5, logs=logs
    )
    result = NotifyResult(
        name="Telegram",
        url="tgram://bot/chat",
        url_id="abc123",
        tag=("alerts",),
        optional=False,
        weight=3,
        max_attempts=3,
        attempts=[attempt],
    )

    expected = {
        "name": "Telegram",
        "url": "tgram://bot/chat",
        "url_id": "abc123",
        "tag": ["alerts"],
        "status": "FAILURE",
        "optional": False,
        "weight": 3,
        "max_attempts": 3,
        "elapsed": result.elapsed,
        "start_time": result.start_time.strftime(AWARE_DATE_ISO_FORMAT),
        "end_time": result.end_time.strftime(AWARE_DATE_ISO_FORMAT),
        "attempts": [attempt.asdict()],
    }
    assert result.asdict() == expected
    assert loads(result.json()) == expected
    # json() is compact -- no space after "," or ":".
    assert ", " not in result.json()
    assert ": " not in result.json()


def test_notify_result_repr():
    """NotifyResult.__repr__ is a compact, informative one-liner."""

    result = NotifyResult(
        name="Slack",
        url="slack://t/ch",
        attempts=[NotifyAttempt(status=AppriseResultStatus.SUCCESS)],
    )
    text = repr(result)

    assert "Slack" in text
    assert "slack://t/ch" in text
    assert "SUCCESS" in text


def test_apprise_result_defaults():
    """AppriseResult: default construction is an empty NOMATCH result."""

    result = AppriseResult()

    assert result.status == AppriseResultStatus.NOMATCH
    assert len(result) == 0
    assert list(result) == []
    assert result.results == ()
    assert result.success_count == 0
    assert result.failed_count == 0
    assert result.timeout_count == 0
    assert result.elapsed == 0.0
    assert bool(result) is False


def test_apprise_result_elapsed_custom():
    """AppriseResult.elapsed stores the caller-supplied wall-clock time."""

    result = AppriseResult(status=AppriseResultStatus.SUCCESS, elapsed=2.5)
    assert result.elapsed == 2.5


def test_apprise_result_start_end_time_match_elapsed():
    """Same start_time/end_time-derived-from-elapsed guarantee as
    NotifyResult, at the whole-call level."""

    result = AppriseResult(status=AppriseResultStatus.SUCCESS, elapsed=4.0)

    assert result.start_time.tzinfo is not None
    assert result.end_time.tzinfo is not None
    assert (result.end_time - result.start_time).total_seconds() == 4.0
    parsed = datetime.strptime(
        result.asdict()["end_time"], AWARE_DATE_ISO_FORMAT
    )
    assert parsed == result.end_time


def test_apprise_result_bool_success():
    """AppriseResult.__bool__ is True only for SUCCESS."""

    result = AppriseResult(status=AppriseResultStatus.SUCCESS)
    assert bool(result) is True


def test_apprise_result_bool_failure():
    """AppriseResult.__bool__ is False for FAILURE."""

    result = AppriseResult(status=AppriseResultStatus.FAILURE)
    assert bool(result) is False


def test_apprise_result_bool_nomatch():
    """AppriseResult.__bool__ is False for NOMATCH."""

    result = AppriseResult(status=AppriseResultStatus.NOMATCH)
    assert bool(result) is False


def test_apprise_result_bool_timeout():
    """AppriseResult.__bool__ is False for TIMEOUT."""

    result = AppriseResult(status=AppriseResultStatus.TIMEOUT)
    assert bool(result) is False


def test_apprise_result_status_exit_code_alignment():
    """AppriseResultStatus values equal the CLI's historical exit codes."""

    assert int(AppriseResultStatus.SUCCESS) == 0
    assert int(AppriseResultStatus.FAILURE) == 1
    assert int(AppriseResultStatus.NOMATCH) == 3
    assert int(AppriseResultStatus.PARTIAL) == 4


def test_apprise_result_timeout_status_value():
    """TIMEOUT is the highest-numbered status value (5)."""

    assert int(AppriseResultStatus.TIMEOUT) == 5


def _notify_result(name, url, status):
    """Test helper: build a one-attempt NotifyResult with the given
    reflective status (SUCCESS/FAILURE/TIMEOUT), for tests that only
    care about the aggregate outcome, not attempt-level detail."""

    return NotifyResult(name=name, url=url, attempts=[NotifyAttempt(status)])


def test_apprise_result_len_and_iter():
    """AppriseResult.__len__/__iter__ walk the collected NotifyResults."""

    r1 = _notify_result("Slack", "slack://t/ch", AppriseResultStatus.SUCCESS)
    r2 = _notify_result(
        "Discord", "discord://w/t", AppriseResultStatus.FAILURE
    )
    result = AppriseResult(
        status=AppriseResultStatus.FAILURE, results=[r1, r2]
    )

    assert len(result) == 2
    assert list(result) == [r1, r2]
    assert result.results == (r1, r2)


def test_apprise_result_success_and_failed_counts():
    """success_count/failed_count are derived from each NotifyResult's
    reflective .status, and timeout_count narrows failed_count down to
    just TIMEOUT entries."""

    results = [
        _notify_result("Slack", "slack://t/ch", AppriseResultStatus.SUCCESS),
        _notify_result(
            "Discord", "discord://w/t", AppriseResultStatus.FAILURE
        ),
        _notify_result("Telegram", "tgram://b/c", AppriseResultStatus.SUCCESS),
        _notify_result("Twilio", "twilio://x", AppriseResultStatus.TIMEOUT),
    ]
    result = AppriseResult(status=AppriseResultStatus.FAILURE, results=results)

    assert result.success_count == 2
    assert result.failed_count == 2
    assert result.timeout_count == 1


def test_apprise_result_logs_merges_and_sorts_across_services():
    """AppriseResult.logs() combines every service's log entries into
    one chronological timeline -- not simply service by service, since
    services dispatched concurrently can log in any relative order to
    each other regardless of which NotifyResult they end up attached
    to."""

    early = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    middle = datetime(2026, 1, 1, 12, 0, 1, tzinfo=timezone.utc)
    late = datetime(2026, 1, 1, 12, 0, 2, tzinfo=timezone.utc)

    # Discord's own NotifyResult is built first, but its one log entry
    # actually happened AFTER Slack's -- e.g. two services notified
    # concurrently, with Discord simply finishing (and being appended
    # to the batch) first.
    discord = NotifyResult(
        name="Discord",
        url="discord://w/t",
        attempts=[
            NotifyAttempt(
                status=AppriseResultStatus.SUCCESS,
                logs=[
                    NotifyLogEntry(
                        level="WARNING", message="from discord", time=late
                    )
                ],
            )
        ],
    )
    slack = NotifyResult(
        name="Slack",
        url="slack://t/ch",
        attempts=[
            NotifyAttempt(
                status=AppriseResultStatus.SUCCESS,
                logs=[
                    NotifyLogEntry(
                        level="WARNING", message="from slack", time=early
                    ),
                    NotifyLogEntry(
                        level="ERROR", message="from slack, later", time=middle
                    ),
                ],
            )
        ],
    )

    result = AppriseResult(
        status=AppriseResultStatus.SUCCESS, results=[discord, slack]
    )

    messages = [entry.message for entry in result.logs()]
    assert messages == ["from slack", "from slack, later", "from discord"]


def test_apprise_result_asdict_and_json():
    """AppriseResult.asdict()/json() serialize status, counts, and every
    NotifyResult entry."""

    results = [
        _notify_result("Slack", "slack://t/ch", AppriseResultStatus.SUCCESS),
        _notify_result(
            "Discord", "discord://w/t", AppriseResultStatus.FAILURE
        ),
    ]
    result = AppriseResult(
        status=AppriseResultStatus.FAILURE, results=results, elapsed=0.75
    )

    expected = {
        "status": "FAILURE",
        "success_count": 1,
        "failed_count": 1,
        "elapsed": 0.75,
        "start_time": result.start_time.strftime(AWARE_DATE_ISO_FORMAT),
        "end_time": result.end_time.strftime(AWARE_DATE_ISO_FORMAT),
        "results": [r.asdict() for r in results],
    }
    assert result.asdict() == expected
    assert loads(result.json()) == expected
    assert ", " not in result.json()
    assert ": " not in result.json()


def test_apprise_result_repr():
    """AppriseResult.__repr__ reports status and entry count."""

    result = AppriseResult(
        status=AppriseResultStatus.SUCCESS,
        results=[
            _notify_result(
                "Slack", "slack://t/ch", AppriseResultStatus.SUCCESS
            )
        ],
    )
    text = repr(result)

    assert "SUCCESS" in text
    assert "1" in text


def test_apprise_result_results_is_read_only_view():
    """.results is a snapshot tuple; mutating the input list afterwards
    does not affect it."""

    source = [
        _notify_result("Slack", "slack://t/ch", AppriseResultStatus.SUCCESS)
    ]
    result = AppriseResult(status=AppriseResultStatus.SUCCESS, results=source)

    source.append(
        _notify_result("Discord", "discord://w/t", AppriseResultStatus.FAILURE)
    )

    assert len(result) == 1
    assert len(result.results) == 1
