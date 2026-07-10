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
import concurrent.futures as cf
from itertools import chain
import json
import math
import os
import threading
import time
from typing import Any, Callable, Optional, Union

from . import __version__, common, plugins
from .apprise_attachment import AppriseAttachment
from .apprise_config import AppriseConfig
from .asset import AppriseAsset
from .common import JSON_COMPACT_SEPARATORS, ContentLocation
from .config.base import ConfigBase
from .conversion import convert_between
from .emojis import apply_emojis
from .locale import AppriseLocale
from .logger import NotifyLogEntry, _ServiceLogCapture, logger
from .manager_plugins import NotificationManager
from .plugins.base import NotifyBase
from .result import (
    AppriseResult,
    AppriseResultStatus,
    NotifyAttempt,
    NotifyResult,
)
from .tag import AppriseTag
from .utils.cwe312 import cwe312_url
from .utils.json import AppriseJSONEncoder
from .utils.logic import is_exclusive_match
from .utils.parse import parse_list, parse_urls

# Grant access to our Notification Manager Singleton
N_MGR = NotificationManager()

# One (server, notify()-kwargs) pair as produced by _create_notify_gen()
# and threaded through every dispatch primitive below.
ServerCall = tuple[NotifyBase, dict[str, Any]]

# Extra seconds of patience for notify() calls.
_ABANDON_GRACE_SECONDS = 0.1

# Shared thread pool for _notify_sequential() and
# _notify_parallel_threadpool(). One pool for the whole process -- a
# fresh one per call would leak a thread every time a service hangs.
_shared_executor: Optional[cf.ThreadPoolExecutor] = None
_shared_executor_lock = threading.Lock()


def _get_shared_executor() -> cf.ThreadPoolExecutor:
    """Return the shared thread pool, creating it on first use."""
    global _shared_executor
    if _shared_executor is None:
        with _shared_executor_lock:
            if _shared_executor is None:
                _shared_executor = cf.ThreadPoolExecutor()
    return _shared_executor


# Services abandoned on timeout that are still genuinely running. Lets
# cli.py poll instead of just sleeping out its whole grace window.
_abandoned_futures: list[tuple[cf.Future, str, str]] = []
_abandoned_futures_lock = threading.Lock()


def _track_abandoned_future(future: cf.Future, name: str, url: str) -> None:
    """Record one abandoned-but-still-running service call."""
    with _abandoned_futures_lock:
        _abandoned_futures[:] = [
            entry for entry in _abandoned_futures if not entry[0].done()
        ]
        _abandoned_futures.append((future, name, url))


def _any_abandoned_calls_still_running() -> bool:
    """True if any abandoned service call is still actually running."""
    with _abandoned_futures_lock:
        _abandoned_futures[:] = [
            entry for entry in _abandoned_futures if not entry[0].done()
        ]
        return bool(_abandoned_futures)


def _abandoned_call_descriptions() -> list[str]:
    """Return "name (url)" for each still-running abandoned call."""
    with _abandoned_futures_lock:
        _abandoned_futures[:] = [
            entry for entry in _abandoned_futures if not entry[0].done()
        ]
        return [f"{name} ({url})" for _, name, url in _abandoned_futures]


def _service_metadata(
    server: NotifyBase,
) -> tuple[str, str, Optional[str], tuple[str, ...], int]:
    """Safely gather one service's identifying metadata.

    Plugin metadata helpers can raise. This helper keeps result-building
    defensive and returns (name, url, url_id, tag, weight).
    """
    name = getattr(server, "service_name", "Unknown")

    try:
        url = server.url(privacy=True)

    except Exception:
        url = "unknown://"

    try:
        url_id = server.url_id()

    except Exception:
        url_id = None

    try:
        weight = len(server)

    except Exception:
        weight = 1

    # tags is a set -- sort so output order is stable.
    tag = tuple(sorted(str(t) for t in getattr(server, "tags", ())))

    return name, url, url_id, tag, weight


def _safe_error_result(server: NotifyBase) -> NotifyResult:
    """Build a best-effort result when a plugin fails outside dispatch."""
    name, url, url_id, tag, weight = _service_metadata(server)

    return NotifyResult(
        name=name,
        url=url,
        url_id=url_id,
        tag=tag,
        optional=getattr(server, "optional", False),
        weight=weight,
        max_attempts=1,
        # No real attempt data exists here, so keep one synthetic failure.
        # NotifyResult still applies the service's optional flag.
        attempts=[NotifyAttempt(status=AppriseResultStatus.FAILURE)],
    )


def _compute_deadline(
    server: NotifyBase, call_deadline: Optional[float]
) -> Optional[float]:
    """Return the monotonic deadline for one service dispatch.

    The earlier of these independent limits wins:

      - The service's own AppriseAsset._service_timeout (default 60s,
        where 0 disables the limit).
      - *call_deadline*, the shared notify(timeout=...) ceiling for the
        entire call.

    The service budget begins when dispatch starts, so time spent waiting
    for a worker does not consume it. ``None`` means the service is unbounded.
    """
    service_timeout = getattr(
        server.asset,
        "_service_timeout",
        AppriseAsset._service_timeout,
    )
    deadline = time.monotonic() + service_timeout if service_timeout else None
    if call_deadline is not None:
        deadline = (
            call_deadline if deadline is None else min(deadline, call_deadline)
        )

    # TRACE keeps large batches from spamming normal DEBUG output.
    logger.trace(
        "Deadline for '%s': %s",
        getattr(server, "service_name", "Unknown"),
        "none"
        if deadline is None
        else "{:.3f}s from now".format(deadline - time.monotonic()),
    )
    return deadline


def _timeout_result(server: NotifyBase, elapsed: float) -> NotifyResult:
    """Build the result for a service that exceeded the outer wait.

    The worker may still be running. Record only what Apprise knows here:
    it stopped waiting, and optional handling still belongs to NotifyResult.
    """
    name, url, url_id, tag, weight = _service_metadata(server)

    return NotifyResult(
        name=name,
        url=url,
        url_id=url_id,
        tag=tag,
        optional=getattr(server, "optional", False),
        weight=weight,
        max_attempts=1,
        attempts=[
            NotifyAttempt(
                status=AppriseResultStatus.TIMEOUT,
                elapsed=elapsed,
                logs=[_timeout_log_entry(name, elapsed)],
            )
        ],
    )


def _timeout_log_entry(name: str, elapsed: float) -> NotifyLogEntry:
    """Log and return the error entry describing a service timeout.

    All timeout paths use this helper so every TIMEOUT attempt carries the
    same useful diagnostic instead of only a status value.
    """
    message = f"Service '{name}' did not finish within {elapsed:.3f}s."
    logger.error(message)
    return NotifyLogEntry(level="ERROR", message=message)


def _validate_timeout(value: Union[int, float]) -> float:
    """Validate a timeout value shared by notify()/async_notify()."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise TypeError("timeout must be an int or float.")

    # inf/nan rejected: use 0 to mean "unbounded" instead.
    if not math.isfinite(value) or value < 0:
        raise ValueError("timeout must be >= 0 and finite.")

    return float(value)


def _aggregate_status(
    ok: bool, results: list[NotifyResult]
) -> AppriseResultStatus:
    """Roll a batch's per-service results up into one overall status.

    All succeeded -> SUCCESS. Some genuinely delivered, some didn't ->
    PARTIAL. Nothing delivered -> FAILURE beats TIMEOUT.
    """
    if ok:
        return AppriseResultStatus.SUCCESS

    # Real success only -- ignores optional=yes services being forgiven.
    if any(
        attempt.status == AppriseResultStatus.SUCCESS
        for result in results
        for attempt in result.attempts
    ):
        return AppriseResultStatus.PARTIAL

    if any(r.status == AppriseResultStatus.FAILURE for r in results):
        return AppriseResultStatus.FAILURE

    if any(r.status == AppriseResultStatus.TIMEOUT for r in results):
        return AppriseResultStatus.TIMEOUT

    return AppriseResultStatus.FAILURE


def _attempt_status(success: bool) -> AppriseResultStatus:
    """Map one attempt's plain success/failure into the shared enum."""
    return (
        AppriseResultStatus.SUCCESS if success else AppriseResultStatus.FAILURE
    )


def _call_with_retry(
    service: NotifyBase,
    kwargs: dict[str, Any],
    call_deadline: Optional[float],
) -> tuple[bool, NotifyResult]:
    """Run one service with retries, waits, logging, and deadlines.

    Shared by sequential and thread-pool dispatch so both paths report
    the same NotifyResult shape.
    """
    # Pop the per-call overrides so they stay internal.
    retry = kwargs.pop("_retry_override", getattr(service, "retry", 0))
    wait = getattr(service, "wait", 0.0)
    log_callback = kwargs.pop("_log_callback", None)

    # Start the service budget when work actually begins.
    deadline = _compute_deadline(service, call_deadline)
    attempts: list[NotifyAttempt] = []
    for attempt in range(retry + 1):
        if deadline is not None and time.monotonic() >= deadline:
            # Record that no further attempt was started.
            logger.trace(
                "Deadline already passed for '%s'; skipping attempt %d/%d.",
                service.service_name,
                attempt + 1,
                retry + 1,
            )
            attempts.append(
                NotifyAttempt(
                    status=AppriseResultStatus.TIMEOUT,
                    logs=[_timeout_log_entry(service.service_name, 0.0)],
                )
            )
            break

        attempt_start = time.monotonic()
        logger.trace(
            "Starting attempt %d/%d for '%s'.",
            attempt + 1,
            retry + 1,
            service.service_name,
        )
        # Treat validation errors and plugin crashes as retriable failures.
        with _ServiceLogCapture(service, log_callback=log_callback) as capture:
            try:
                result = service.notify(**kwargs)
            except TypeError:
                result = False
            except Exception as e:
                logger.warning(
                    "Notification service '%s' raised an exception.",
                    service.service_name,
                )
                logger.debug("Notification Exception: %s", str(e))
                result = False

        attempt_elapsed = time.monotonic() - attempt_start
        logger.trace(
            "Attempt %d/%d for '%s' finished in %.3fs: %s.",
            attempt + 1,
            retry + 1,
            service.service_name,
            attempt_elapsed,
            "success" if result else "failure",
        )
        attempts.append(
            NotifyAttempt(
                status=_attempt_status(result),
                elapsed=attempt_elapsed,
                logs=capture.entries,
            )
        )

        if result:
            break

        if attempt < retry:
            logger.warning(
                "Attempt %d/%d for '%s' failed; trying again.",
                attempt + 1,
                retry,
                service.service_name,
            )
            if wait > 0:
                sleep_for = wait
                if deadline is not None:
                    sleep_for = min(
                        wait, max(0.0, deadline - time.monotonic())
                    )
                if sleep_for > 0:
                    time.sleep(sleep_for)

    # Optional services can fail quietly, but keep a log breadcrumb.
    optional = getattr(service, "optional", False)
    succeeded = any(a.status == AppriseResultStatus.SUCCESS for a in attempts)
    if not succeeded and optional:
        logger.info(
            "Optional service '%s' did not send successfully; continuing.",
            service.service_name,
        )

    # Metadata helpers belong to plugins and may raise.
    name, url, url_id, tag, weight = _service_metadata(service)
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

    return bool(notify_result), notify_result


class Apprise:
    """Our Notification Manager."""

    def __init__(
        self,
        servers: Optional[
            Union[
                str,
                dict,
                NotifyBase,
                AppriseConfig,
                ConfigBase,
                list[Union[str, dict, NotifyBase, AppriseConfig, ConfigBase]],
            ]
        ] = None,
        asset: Optional[AppriseAsset] = None,
        location: Optional[ContentLocation] = None,
        debug: bool = False,
        log_callback: Optional[
            Callable[[NotifyLogEntry, NotifyBase], Any]
        ] = None,
    ) -> None:
        """Loads a set of server urls while applying the Asset() module to each
        if specified.

        If no asset is provided, then the default asset is used.

        Optionally specify a global ContentLocation for a more strict means of
        handling Attachments.

        log_callback, when given, fires on every warning/error a service
        logs. Applies to every notify() call unless overridden per-call.
        """

        # Initialize a server list of URLs
        self.servers = []

        # Assigns an central asset object that will be later passed into each
        # notification plugin.  Assets contain information such as the local
        # directory images can be found in. It can also identify remote
        # URL paths that contain the images you want to present to the end
        # user. If no asset is specified, then the default one is used.
        self.asset = (
            asset if isinstance(asset, AppriseAsset) else AppriseAsset()
        )

        if servers:
            self.add(servers)

        # Initialize our locale object
        self.locale = AppriseLocale()

        # Set our debug flag
        self.debug = debug

        # Store our hosting location for optional strict rule handling
        # of Attachments.  Setting this to None removes any attachment
        # restrictions.
        self.location = location

        # Default log_callback for every notify()/async_notify() call made
        # with this instance, unless overridden per-call.
        self._log_callback = log_callback

    @staticmethod
    def instantiate(
        url: Union[str, dict],
        asset: Optional[AppriseAsset] = None,
        tag: Optional[Union[str, list[str]]] = None,
        suppress_exceptions: bool = True,
    ) -> Optional[NotifyBase]:
        """Returns the instance of a instantiated plugin based on the provided
        Server URL.  If the url fails to be parsed, then None is returned.

        The specified url can be either a string (the URL itself) or a
        dictionary containing all of the components needed to istantiate
        the notification service.  If identifying a dictionary, at the bare
        minimum, one must specify the schema.

        An example of a url dictionary object might look like:
          {
            schema: 'mailto',
            host: 'google.com',
            user: 'myuser',
            password: 'mypassword',
          }

        Alternatively the string is much easier to specify:
          mailto://user:mypassword@google.com

        The dictionary works well for people who are calling details() to
        extract the components they need to build the URL manually.
        """

        # Initialize our result set
        results = None

        # Prepare our Asset Object
        asset = asset if isinstance(asset, AppriseAsset) else AppriseAsset()

        if isinstance(url, str):
            # Acquire our url tokens
            results = plugins.url_to_dict(
                url, secure_logging=asset.secure_logging
            )

            if results is None:
                # Failed to parse the server URL; detailed logging handled
                # inside url_to_dict - nothing to report here.
                return None

        elif isinstance(url, dict):
            # We already have our result set
            results = url

            if results.get("schema") not in N_MGR:
                # schema is a mandatory dictionary item as it is the only way
                # we can index into our loaded plugins
                logger.error('Dictionary does not include a "schema" entry.')
                logger.trace(
                    "Invalid dictionary unpacked as:{}{}".format(
                        os.linesep,
                        os.linesep.join(
                            [f'{k}="{v}"' for k, v in results.items()]
                        ),
                    )
                )
                return None

            logger.trace(
                "Dictionary unpacked as:{}{}".format(
                    os.linesep,
                    os.linesep.join(
                        [f'{k}="{v}"' for k, v in results.items()]
                    ),
                )
            )

        # Otherwise we handle the invalid input specified
        else:
            logger.error(
                "An invalid URL type (%s) was specified for instantiation",
                type(url),
            )
            return None

        if not N_MGR[results["schema"]].enabled:
            #
            # First Plugin Enable Check (Pre Initialization)
            #

            # Plugin has been disabled at a global level
            logger.error(
                "%s:// is disabled on this system.", results["schema"]
            )
            return None

        # Build a list of tags to associate with the newly added notifications
        results["tag"] = set(parse_list(tag))

        # Set our Asset Object
        results["asset"] = asset

        if suppress_exceptions:
            try:
                # Attempt to create an instance of our plugin using the parsed
                # URL information
                plugin = N_MGR[results["schema"]](**results)

                # Create log entry of loaded URL
                logger.debug(
                    "Loaded {} URL: {}".format(
                        N_MGR[results["schema"]].service_name,
                        plugin.url(privacy=asset.secure_logging),
                    )
                )

            except Exception:
                # CWE-312 (Secure Logging) Handling
                loggable_url = (
                    url if not asset.secure_logging else cwe312_url(url)
                )

                # the arguments are invalid or can not be used.
                logger.error(
                    "Could not load {} URL: {}".format(
                        N_MGR[results["schema"]].service_name, loggable_url
                    )
                )
                return None

        else:
            # Attempt to create an instance of our plugin using the parsed
            # URL information but don't wrap it in a try catch
            plugin = N_MGR[results["schema"]](**results)

        if not plugin.enabled:
            #
            # Second Plugin Enable Check (Post Initialization)
            #

            # Service/Plugin is disabled (on a more local level).  This is a
            # case where the plugin was initially enabled but then after the
            # __init__() was called under the hood something pre-determined
            # that it could no longer be used.

            # The only downside to doing it this way is services are
            # initialized prior to returning the details() if 3rd party tools
            # are polling what is available. These services that become
            # disabled thereafter are shown initially that they can be used.
            logger.error(
                "%s:// has become disabled on this system.", results["schema"]
            )
            return None

        return plugin

    def add(
        self,
        servers: Union[
            str,
            dict,
            NotifyBase,
            AppriseConfig,
            ConfigBase,
            list[Union[str, dict, NotifyBase, AppriseConfig, ConfigBase]],
        ],
        asset: Optional[AppriseAsset] = None,
        tag: Optional[Union[str, list[str]]] = None,
    ) -> bool:
        """Adds one or more server URLs into our list.

        You can override the global asset if you wish by including it with the
        server(s) that you add.

        The tag allows you to associate 1 or more tag values to the server(s)
        being added. tagging a service allows you to exclusively access them
        when calling the notify() function.
        """

        # Initialize our return status
        return_status = True

        if asset is None:
            # prepare default asset
            asset = self.asset

        if isinstance(servers, str):
            # build our server list
            servers = parse_urls(servers)
            if len(servers) == 0:
                return False

        elif isinstance(servers, dict):
            # no problem, we support kwargs, convert it to a list
            servers = [servers]

        elif isinstance(servers, (ConfigBase, NotifyBase, AppriseConfig)):
            # Go ahead and just add our plugin into our list
            self.servers.append(servers)
            return True

        elif not isinstance(servers, (tuple, set, list)):
            logger.error(
                f"An invalid notification (type={type(servers)}) was"
                " specified."
            )
            return False

        for server in servers:
            if isinstance(server, (ConfigBase, NotifyBase, AppriseConfig)):
                # Go ahead and just add our plugin into our list
                self.servers.append(server)
                continue

            elif not isinstance(server, (str, dict)):
                logger.error(
                    f"An invalid notification (type={type(server)}) was"
                    " specified."
                )
                return_status = False
                continue

            # Instantiate ourselves an object, this function throws or
            # returns None if it fails
            instance = Apprise.instantiate(server, asset=asset, tag=tag)
            if not isinstance(instance, NotifyBase):
                # No logging is required as instantiate() handles failure
                # and/or success reasons for us
                return_status = False
                continue

            # Add our initialized plugin to our server listings
            self.servers.append(instance)

        # Return our status
        return return_status

    def clear(self) -> None:
        """Empties our server list."""
        self.servers[:] = []

    def find(
        self,
        tag: Any = common.MATCH_ALL_TAG,
        match_always: bool = True,
    ) -> Iterator[NotifyBase]:
        """Returns a list of all servers matching against the tag specified."""

        # Build our tag setup
        #   - top level entries are treated as an 'or'
        #   - second level (or more) entries are treated as 'and'
        #
        #   examples:
        #     tag="tagA, tagB"                = tagA or tagB
        #     tag=['tagA', 'tagB']            = tagA or tagB
        #     tag=[('tagA', 'tagC'), 'tagB']  = (tagA and tagC) or tagB
        #     tag=[('tagB', 'tagC')]          = tagB and tagC

        # A match_always flag allows us to pick up on our 'any' keyword
        # and notify these services under all circumstances
        match_always = common.MATCH_ALWAYS_TAG if match_always else None

        # Iterate over our loaded plugins
        for entry in self.servers:
            if isinstance(entry, (ConfigBase, AppriseConfig)):
                # load our servers
                servers = entry.servers()

            else:
                servers = [
                    entry,
                ]

            for server in servers:
                # Apply our tag matching based on our defined logic
                if is_exclusive_match(
                    logic=tag,
                    data=server.tags,
                    match_all=common.MATCH_ALL_TAG,
                    match_always=match_always,
                ):
                    yield server
        return

    @staticmethod
    def _extract_filter_retry(tag):
        """Return the retry override embedded in a filter tag, or None.

        A filter like "3:endpoint:2" or "endpoint:2" carries ":2" as the
        call-level retry count.  When present it overrides each matched
        server's configured retry for this single notify() call.
        """
        if tag is None or tag == common.MATCH_ALL_TAG:
            return None
        for entry in (
            [tag] if isinstance(tag, (str, AppriseTag)) else list(tag)
        ):
            if isinstance(entry, (list, tuple, set)):
                for tok in parse_list(entry):
                    ft = AppriseTag.parse(tok)
                    if ft.retry is not None:
                        return ft.retry

            else:
                ft = AppriseTag.parse(str(entry))
                if ft.retry is not None:
                    return ft.retry
        return None

    @staticmethod
    def _filter_has_explicit_priority(tag):
        """Return True if any token in *tag* carries an explicit priority
        prefix.

        When True, notify() dispatches matched servers as a flat batch
        (no escalation) because the caller selected an exact priority level.
        When False, matched servers are grouped by their own tag priorities
        and dispatched in ascending order with early-True exit.
        """
        if tag is None or tag == common.MATCH_ALL_TAG:
            return False

        for entry in (
            [tag] if isinstance(tag, (str, AppriseTag)) else list(tag)
        ):
            if isinstance(entry, (list, tuple, set)):
                for tok in parse_list(entry):
                    if AppriseTag.parse(tok).has_priority:
                        return True
            else:
                for tok in parse_list(str(entry)):
                    if AppriseTag.parse(tok).has_priority:
                        return True
        return False

    @staticmethod
    def _server_priority_for_tag_name(server, tag_name):
        """Return the dispatch priority stored on *server* for *tag_name*.

        Looks up the AppriseTag in server.tags whose bare name equals
        *tag_name* and returns its priority.  Returns 0 when the tag is
        absent or stored as a plain string (no explicit priority).
        """
        for stag in server.tags:
            if str(stag) == tag_name:
                return stag.priority if isinstance(stag, AppriseTag) else 0
        return 0

    @staticmethod
    def _match_service_retry(server, tag):
        """Return the call-time retry override for *server* given *tag*.

        Iterates the OR tokens in *tag* in order.  The first token that
        both carries a retry suffix AND matches *server* determines the
        override.  Returns None when no such token exists.

        Matching follows the same rules as _token_matches_data:
          - no priority prefix  -> name-only match
          - explicit priority   -> name + priority-exact match
        """
        if tag is None or tag == common.MATCH_ALL_TAG:
            return None
        for entry in (
            [tag] if isinstance(tag, (str, AppriseTag)) else list(tag)
        ):
            tokens = (
                parse_list(entry)
                if isinstance(entry, (list, tuple, set))
                else parse_list(str(entry))
            )

            for tok in tokens:
                ft = AppriseTag.parse(tok)
                if ft.retry is None:
                    continue

                tag_name = str(ft)
                if not ft.has_priority:
                    if tag_name in server.tags:
                        return ft.retry

                else:
                    for stag in server.tags:
                        if isinstance(stag, AppriseTag):
                            if (
                                str(stag) == tag_name
                                and stag.priority == ft.priority
                            ):
                                return ft.retry
                        else:
                            if str(stag).lower() == tag_name:
                                return ft.retry
        return None

    @staticmethod
    def _inject_per_service_retries(all_calls, tag):
        """Return *all_calls* with per-service _retry_override injected.

        For each (server, kwargs) pair, finds the first filter token in
        *tag* that matches the service and carries a retry suffix.  When
        found, injects that value as _retry_override so that all dispatch
        paths (sequential, threadpool, asyncio) pick it up automatically.
        Services with no matching retry token are left unchanged.
        """
        result = []
        for server, kwargs in all_calls:
            retry = Apprise._match_service_retry(server, tag)
            if retry is not None:
                kwargs = dict(kwargs, _retry_override=retry)
            result.append((server, kwargs))
        return result

    @staticmethod
    def _inject_log_callback(all_calls, log_callback):
        """Inject _log_callback into every call's kwargs. No-op if
        log_callback is None."""
        if log_callback is None:
            return all_calls
        return [
            (service, dict(kwargs, _log_callback=log_callback))
            for service, kwargs in all_calls
        ]

    @staticmethod
    def _build_tag_chains(all_calls, tag):
        """Group *all_calls* into per-OR-token escalation chains.

        Returns {chain_key: {priority: [(server, kwargs)]}}.

        Each service is assigned to the chain of the first OR token whose
        bare tag name appears in the service's own tags.  The chain key is
        that bare tag name.  Services that don't match any token by name
        fall into a catch-all chain keyed as "".

        When *tag* is MATCH_ALL_TAG or None, a single chain "" is built
        using the existing _server_priority_for_filter logic.
        """
        if tag is None or tag == common.MATCH_ALL_TAG:
            chain: dict[int, list] = {}
            for server, kwargs in all_calls:
                p = Apprise._server_priority_for_filter(server, tag)
                chain.setdefault(p, []).append((server, kwargs))
            return {"": chain}

        # Flatten OR tokens; AND groups are kept as a single opaque entry
        # that falls through to the catch-all chain.
        #
        # The CLI wraps each --tag value in a list via parse_list(), so a
        # single --tag flag produces a single-element inner list such as
        # [["alerts:3"]].  A single-element list is always a plain OR token
        # (there is nothing to AND against), so we treat it the same as a
        # bare string.  A multi-element inner list is a genuine AND condition
        # (the server must carry every tag in the group) and falls through to
        # the catch-all chain instead of getting its own independent chain.
        or_tag_names: list[str] = []
        for entry in (
            [tag] if isinstance(tag, (str, AppriseTag)) else list(tag)
        ):
            if isinstance(entry, (list, tuple, set)):
                flat = parse_list(*entry) if entry else []
                if len(flat) == 1:
                    # single OR token wrapped in a list (CLI convention)
                    or_tag_names.append(str(AppriseTag.parse(flat[0])))

                else:
                    or_tag_names.append("")  # AND group placeholder

            else:
                for tok in parse_list(str(entry)):
                    or_tag_names.append(str(AppriseTag.parse(tok)))

        chains: dict[str, dict[int, list]] = {}
        for server, kwargs in all_calls:
            for chain_key in or_tag_names:
                if chain_key and chain_key in server.tags:
                    p = Apprise._server_priority_for_tag_name(
                        server, chain_key
                    )
                    chains.setdefault(chain_key, {}).setdefault(p, []).append(
                        (server, kwargs)
                    )
                    break
            else:
                # fallback: use global priority
                p = Apprise._server_priority_for_filter(server, tag)
                chains.setdefault("", {}).setdefault(p, []).append(
                    (server, kwargs)
                )

        return chains

    @staticmethod
    def _server_priority_for_filter(server, tag):
        """Return the effective dispatch priority for *server* given *tag*.

        The priority comes from the AppriseTag stored on the server whose
        name matches one of the tag-filter names.  When multiple server tags
        match, the minimum (highest-precedence) priority is returned.
        Returns 0 when no matching priority tag is found.
        """
        if tag is None or tag == common.MATCH_ALL_TAG:
            return 0

        # Flatten the filter to a set of bare lowercase tag names.
        filter_names = set()
        for entry in (
            [tag] if isinstance(tag, (str, AppriseTag)) else list(tag)
        ):
            if isinstance(entry, (list, tuple, set)):
                for t in parse_list(entry):
                    filter_names.add(str(AppriseTag.parse(t)))
            else:
                for t in parse_list(str(entry)):
                    filter_names.add(str(AppriseTag.parse(t)))

        priorities = [
            stag.priority if isinstance(stag, AppriseTag) else 0
            for stag in server.tags
            if str(stag) in filter_names
        ]
        return min(priorities) if priorities else 0

    @staticmethod
    def _split_and_dispatch(
        batch: list[ServerCall], call_deadline: Optional[float] = None
    ) -> tuple[bool, list[NotifyResult]]:
        """Dispatch sequential and parallel subsets of ``batch``.

        Results keep the caller's original order. ``call_deadline`` is passed
        through to the dispatch helpers.
        """
        # Tag each entry with its position in *batch* before splitting so
        # the two dispatched subsets can be recombined in original order.
        indexed = list(enumerate(batch))
        sequential = [
            (i, s, k) for i, (s, k) in indexed if not s.asset.async_mode
        ]
        parallel = [(i, s, k) for i, (s, k) in indexed if s.asset.async_mode]

        seq_ok, seq_results = (
            Apprise._notify_sequential(
                *[(s, k) for _, s, k in sequential],
                call_deadline=call_deadline,
            )
            if sequential
            else (True, [])
        )
        par_ok, par_results = (
            Apprise._notify_parallel_threadpool(
                *[(s, k) for _, s, k in parallel], call_deadline=call_deadline
            )
            if parallel
            else (True, [])
        )

        # Recombine by original index so the returned list matches the
        # order entries appeared in *batch*, regardless of which subset
        # (sequential/parallel) each one was dispatched through.
        indexed_results = list(zip((i for i, _, _ in sequential), seq_results))
        indexed_results += list(zip((i for i, _, _ in parallel), par_results))
        indexed_results.sort(key=lambda entry: entry[0])

        return seq_ok and par_ok, [r for _, r in indexed_results]

    @staticmethod
    async def _split_and_dispatch_async(
        batch: list[ServerCall], call_deadline: Optional[float] = None
    ) -> tuple[bool, list[NotifyResult]]:
        """Dispatch sequential and asynchronous subsets of ``batch``.

        Blocking entries still use _notify_sequential(); async entries use
        _notify_parallel_asyncio(). Results keep the original order.
        """
        # Preserve each entry's original position before dividing the work.
        indexed = list(enumerate(batch))
        sequential = [
            (i, s, k) for i, (s, k) in indexed if not s.asset.async_mode
        ]
        parallel = [(i, s, k) for i, (s, k) in indexed if s.asset.async_mode]

        seq_ok, seq_results = (
            Apprise._notify_sequential(
                *[(s, k) for _, s, k in sequential],
                call_deadline=call_deadline,
            )
            if sequential
            else (True, [])
        )
        par_ok, par_results = (
            await Apprise._notify_parallel_asyncio(
                *[(s, k) for _, s, k in parallel], call_deadline=call_deadline
            )
            if parallel
            else (True, [])
        )

        # Merge both result streams back into the caller's batch order.
        indexed_results = list(zip((i for i, _, _ in sequential), seq_results))
        indexed_results += list(zip((i for i, _, _ in parallel), par_results))
        indexed_results.sort(key=lambda entry: entry[0])

        return seq_ok and par_ok, [r for _, r in indexed_results]

    def notify(
        self,
        body: Union[str, bytes],
        title: Union[str, bytes] = "",
        notify_type: Union[str, common.NotifyType] = common.NotifyType.INFO,
        body_format: Optional[str] = None,
        tag: Any = common.MATCH_ALL_TAG,
        match_always: bool = True,
        attach: Any = None,
        interpret_escapes: Optional[bool] = None,
        timeout: Union[int, float] = 0,
        log_callback: Optional[
            Callable[[NotifyLogEntry, NotifyBase], Any]
        ] = None,
    ) -> AppriseResult:
        """Send a notification to all the plugins previously loaded.

        If the body_format specified is NotifyFormat.MARKDOWN, it will be
        converted to HTML if the Notification type expects this.

        if the tag is specified (either a string or a set/list/tuple of
        strings), then only the notifications flagged with that tagged value
        are notified.  By default, all added services are notified
        (tag=MATCH_ALL_TAG)

        This function always returns an AppriseResult. bool(result) preserves
        the previous True/False behavior. result.status distinguishes success,
        failure (including invalid arguments), no match, and timeout (see
        timeout= below). Iterate the result to inspect each service actually
        dispatched:

            result = apobj.notify(body="hello")
            for service_result in result:
                print(service_result.name, bool(service_result))

        A filter tag may carry an optional priority prefix and/or retry suffix:

          "endpoint"       -> match all entries; escalate by priority
          "3:endpoint"     -> match ONLY priority-3 entries; flat dispatch
          "endpoint:2"     -> match all entries; retry each up to 2 times
          "3:endpoint:2"   -> exclusive priority-3 match with 2 retries

        When no priority prefix is given, matched services are grouped by
        their configured tag priority and dispatched in ascending order
        (lowest number = highest urgency).  If every service in the lowest
        priority group succeeds, Apprise returns success immediately without
        running higher-numbered priority groups (escalation chain).

        When an explicit priority prefix IS given (e.g. "3:endpoint"), only
        services whose matching tag carries that exact priority are notified,
        and all matched services are dispatched as a single flat batch.

        Attach can contain a list of attachment URLs.  attach can also be
        represented by an AttachBase() (or list of) object(s). This identifies
        the products you wish to notify

        Set interpret_escapes to True if you want to pre-escape a string such
        as turning a \n into an actual new line, etc.

        timeout, when given (as a non-zero int or float), is a ceiling in
        seconds on how long this entire notify() call is allowed to run.
        Any service not finished by then is reported with
        AppriseResultStatus.TIMEOUT instead of being waited on further.
        Each service is independently also bounded by its own
        AppriseAsset._service_timeout (default 60s, set via
        AppriseAsset(service_timeout=...); 0 disables it) -- whichever of
        the two limits is sooner applies to a given service.  timeout
        defaults to 0 (no call-level override at all), deliberately
        leaving AppriseAsset._service_timeout as the only thing that
        controls the default behaviour; negative values raise ValueError,
        non-numeric values raise TypeError, exactly like
        AppriseAsset(service_timeout=...) itself.

        log_callback overrides the instance default for this call only.
        """
        timeout = _validate_timeout(timeout)
        effective_log_callback = (
            log_callback if log_callback is not None else self._log_callback
        )

        # Wall-clock start for AppriseResult.elapsed -- covers the entire
        # call, including argument validation, not just service dispatch.
        start = time.monotonic()

        # An absolute time.monotonic() ceiling for the whole call, or None
        # when no override was given (each service still has its own
        # AppriseAsset._service_timeout budget -- see _compute_deadline()).
        call_deadline: Optional[float] = (
            time.monotonic() + timeout if timeout else None
        )

        try:
            all_calls = list(
                self._create_notify_gen(
                    body,
                    title,
                    notify_type=notify_type,
                    body_format=body_format,
                    tag=tag,
                    match_always=match_always,
                    attach=attach,
                    interpret_escapes=interpret_escapes,
                )
            )

        except TypeError:
            # Invalid notify() arguments -- no service was ever attempted.
            return AppriseResult(
                status=AppriseResultStatus.FAILURE,
                results=[],
                elapsed=time.monotonic() - start,
            )

        if not all_calls:
            # Tag filter matched nothing, or no servers are loaded at all.
            return AppriseResult(
                status=AppriseResultStatus.NOMATCH,
                results=[],
                elapsed=time.monotonic() - start,
            )

        # Inject the per-service call-time retry override.  Each matched
        # service gets the retry from the first filter token that both matches
        # it and carries a retry suffix (e.g. "devops:3" applies retry=3 only
        # to devops-tagged services, not to management-tagged services).
        all_calls = Apprise._inject_per_service_retries(all_calls, tag)
        all_calls = Apprise._inject_log_callback(
            all_calls, effective_log_callback
        )

        if Apprise._filter_has_explicit_priority(tag):
            # Tag filter carries an explicit priority prefix (e.g. "2:alerts").
            # Skip the escalation chain: dispatch all matched services as a
            # single flat batch regardless of their individual tag priorities.
            ok, results = Apprise._split_and_dispatch(
                all_calls, call_deadline=call_deadline
            )
            return AppriseResult(
                status=_aggregate_status(ok, results),
                results=results,
                elapsed=time.monotonic() - start,
            )

        # No explicit priority in the filter -- use per-tag escalation chains.
        #
        # Each distinct OR token forms an independent chain.  Within a chain,
        # services are grouped by their configured tag priority.  The lowest-
        # numbered group (highest urgency) runs first.  If every service in
        # that group succeeds the chain is done; any failure escalates to the
        # next priority group.  notify() only reports overall success when
        # every chain finds a fully-successful group.
        #
        # When multiple chains are active in the same round their current
        # priority-group batches run concurrently via a thread pool so that
        # one chain's services cannot delay another chain.
        chains = Apprise._build_tag_chains(all_calls, tag)

        # Per-chain state: priorities (sorted), groups dict, current index,
        # and a flag marking whether a successful group has been found.
        chain_states = {
            key: {
                "priorities": sorted(groups),
                "groups": groups,
                "idx": 0,
                "succeeded": False,
            }
            for key, groups in chains.items()
        }

        # Every NotifyResult actually dispatched across every chain and
        # every priority-group attempt, in the order each batch was run.
        all_results = []

        while True:
            # When abort_on_chain_failure is enabled, stop as soon as any
            # chain has exhausted all its priority groups without success.
            # With the default (False) all chains run to completion even if
            # one has already failed, so every defined URL gets an attempt.
            if self.asset.abort_on_chain_failure and any(
                not st["succeeded"] and st["idx"] >= len(st["priorities"])
                for st in chain_states.values()
            ):
                return AppriseResult(
                    status=_aggregate_status(False, all_results),
                    results=all_results,
                    elapsed=time.monotonic() - start,
                )

            # Collect chains that still need to try their next priority group.
            active = [
                (key, st)
                for key, st in chain_states.items()
                if not st["succeeded"] and st["idx"] < len(st["priorities"])
            ]
            if not active:
                break  # every chain has either succeeded or been exhausted

            if len(active) == 1:
                # Single active chain: dispatch directly, no thread overhead.
                key, st = active[0]
                priority = st["priorities"][st["idx"]]
                batch = st["groups"][priority]
                ok, batch_results = Apprise._split_and_dispatch(
                    batch, call_deadline=call_deadline
                )
                all_results.extend(batch_results)
                if ok:
                    logger.trace(
                        "Chain '%s' priority group %s succeeded.",
                        key,
                        priority,
                    )
                    st["succeeded"] = True
                else:
                    logger.trace(
                        "Chain '%s' priority group %s failed; escalating.",
                        key,
                        priority,
                    )
                    st["idx"] += 1  # escalate to next priority
            else:
                # Multiple active chains: run their current-priority batches
                # concurrently so independent chains don't block each other.
                # Per-service deadlines are enforced inside
                # _split_and_dispatch.
                with cf.ThreadPoolExecutor() as executor:
                    future_map = {
                        executor.submit(
                            Apprise._split_and_dispatch,
                            st["groups"][st["priorities"][st["idx"]]],
                            call_deadline,
                        ): (key, st)
                        for key, st in active
                    }
                    # Collect in submission order so results are stable even
                    # when chains finish in a different order.
                    for future, (key, st) in future_map.items():
                        try:
                            ok, batch_results = future.result()
                        except Exception as e:
                            logger.warning(
                                "Notification chain '%s' priority group %s "
                                "raised an exception.",
                                key,
                                st["priorities"][st["idx"]],
                            )
                            logger.debug("Notification Exception: %s", str(e))
                            ok, batch_results = False, []
                        all_results.extend(batch_results)
                        if ok:
                            logger.trace(
                                "Chain '%s' priority group %s succeeded.",
                                key,
                                st["priorities"][st["idx"]],
                            )
                            st["succeeded"] = True
                        else:
                            logger.trace(
                                "Chain '%s' priority group %s failed; "
                                "escalating.",
                                key,
                                st["priorities"][st["idx"]],
                            )
                            st["idx"] += 1  # escalate to next priority

        success = all(st["succeeded"] for st in chain_states.values())
        return AppriseResult(
            status=_aggregate_status(success, all_results),
            results=all_results,
            elapsed=time.monotonic() - start,
        )

    async def async_notify(self, *args: Any, **kwargs: Any) -> AppriseResult:
        """Send a notification to all the plugins previously loaded, for
        asynchronous callers.

        The arguments and return value are identical to those of
        Apprise.notify() -- see its docstring for the full AppriseResult
        contract, including the timeout= and log_callback= parameters.
        """
        tag = kwargs.get("tag", common.MATCH_ALL_TAG)

        # Pop both -- neither is a _create_notify_gen() parameter.
        timeout: Union[int, float] = _validate_timeout(
            kwargs.pop("timeout", 0)
        )
        log_callback: Optional[Callable[[NotifyLogEntry, NotifyBase], Any]] = (
            kwargs.pop("log_callback", None)
        )
        effective_log_callback = (
            log_callback if log_callback is not None else self._log_callback
        )

        # Wall-clock start for AppriseResult.elapsed -- see notify().
        start = time.monotonic()

        # See notify() for what this is.
        call_deadline: Optional[float] = (
            time.monotonic() + timeout if timeout else None
        )

        try:
            all_calls = list(self._create_notify_gen(*args, **kwargs))

        except TypeError:
            # Invalid notify() arguments -- no service was ever attempted.
            return AppriseResult(
                status=AppriseResultStatus.FAILURE,
                results=[],
                elapsed=time.monotonic() - start,
            )

        if not all_calls:
            # Tag filter matched nothing, or no servers are loaded at all.
            return AppriseResult(
                status=AppriseResultStatus.NOMATCH,
                results=[],
                elapsed=time.monotonic() - start,
            )

        # Inject per-service call-time retry overrides (same logic as notify).
        all_calls = Apprise._inject_per_service_retries(all_calls, tag)
        all_calls = Apprise._inject_log_callback(
            all_calls, effective_log_callback
        )

        if Apprise._filter_has_explicit_priority(tag):
            # Explicit priority prefix: flat dispatch, no escalation.
            ok, results = await Apprise._split_and_dispatch_async(
                all_calls, call_deadline=call_deadline
            )
            return AppriseResult(
                status=_aggregate_status(ok, results),
                results=results,
                elapsed=time.monotonic() - start,
            )

        # Per-tag independent escalation chains -- same semantics as notify().
        #
        # Each chain's current-priority batch is dispatched as a coroutine.
        # All active chains' batches run concurrently via asyncio.gather() so
        # async services across independent chains can make I/O progress
        # simultaneously.  Only chains whose current batch failed advance to
        # the next priority group (escalation).
        chains = Apprise._build_tag_chains(all_calls, tag)

        chain_states = {
            key: {
                "priorities": sorted(groups),
                "groups": groups,
                "idx": 0,
                "succeeded": False,
            }
            for key, groups in chains.items()
        }

        # Every NotifyResult actually dispatched across every chain and
        # every priority-group attempt, in the order each batch was run.
        all_results = []

        while True:
            # Same abort_on_chain_failure guard as notify().
            if self.asset.abort_on_chain_failure and any(
                not st["succeeded"] and st["idx"] >= len(st["priorities"])
                for st in chain_states.values()
            ):
                return AppriseResult(
                    status=_aggregate_status(False, all_results),
                    results=all_results,
                    elapsed=time.monotonic() - start,
                )

            active = [
                (key, st)
                for key, st in chain_states.items()
                if not st["succeeded"] and st["idx"] < len(st["priorities"])
            ]
            if not active:
                break  # every chain has either succeeded or been exhausted

            # Run all active chains' current-priority batches concurrently.
            # asyncio.gather() interleaves coroutines so async services across
            # different chains can pipeline their I/O simultaneously.
            # return_exceptions=True prevents one failing batch from cancelling
            # the others; exceptions are treated as delivery failures below.
            gathered = await asyncio.gather(
                *(
                    Apprise._split_and_dispatch_async(
                        st["groups"][st["priorities"][st["idx"]]],
                        call_deadline=call_deadline,
                    )
                    for _, st in active
                ),
                return_exceptions=True,
            )

            for (key, st), item in zip(active, gathered):
                if isinstance(item, Exception):
                    # Escaped exception -- safety net; treat as failure.
                    logger.warning(
                        "Notification chain '%s' priority group %s raised "
                        "an exception.",
                        key,
                        st["priorities"][st["idx"]],
                    )
                    logger.debug("Notification Exception: %s", str(item))
                    st["idx"] += 1
                else:
                    ok, batch_results = item
                    all_results.extend(batch_results)
                    if ok:
                        logger.trace(
                            "Chain '%s' priority group %s succeeded.",
                            key,
                            st["priorities"][st["idx"]],
                        )
                        st["succeeded"] = True
                    else:
                        logger.trace(
                            "Chain '%s' priority group %s failed; escalating.",
                            key,
                            st["priorities"][st["idx"]],
                        )
                        st["idx"] += 1  # escalate to next priority group

        success = all(st["succeeded"] for st in chain_states.values())
        return AppriseResult(
            status=_aggregate_status(success, all_results),
            results=all_results,
            elapsed=time.monotonic() - start,
        )

    def _create_notify_calls(self, *args, **kwargs):
        """Creates notifications for all the plugins loaded.

        Returns a list of (server, notify() kwargs) tuples for plugins with
        parallelism disabled and another list for plugins with parallelism
        enabled.
        """

        all_calls = list(self._create_notify_gen(*args, **kwargs))

        # Split into sequential and parallel notify() calls.
        sequential, parallel = [], []
        for server, notify_kwargs in all_calls:
            if server.asset.async_mode:
                parallel.append((server, notify_kwargs))
            else:
                sequential.append((server, notify_kwargs))

        return sequential, parallel

    def _create_notify_gen(
        self,
        body,
        title="",
        notify_type=common.NotifyType.INFO,
        body_format=None,
        tag=common.MATCH_ALL_TAG,
        match_always=True,
        attach=None,
        interpret_escapes=None,
    ):
        """Internal generator function for _create_notify_calls()."""

        if len(self) == 0:
            # Nothing loaded -- same as an empty tag match: NOMATCH, not
            # FAILURE.
            logger.warning("There are no service(s) to notify")
            return

        if not (title or body or attach):
            msg = "No message content specified to deliver"
            logger.error(msg)
            raise TypeError(msg)

        try:
            notify_type = (
                notify_type
                if isinstance(notify_type, common.NotifyType)
                else common.NotifyType(notify_type.lower())
            )

        except (AttributeError, ValueError, TypeError):
            err = (
                f"An invalid notification type ({notify_type}) was specified."
            )
            raise TypeError(err) from None

        try:
            if title and isinstance(title, bytes):
                title = title.decode(self.asset.encoding)

            if body and isinstance(body, bytes):
                body = body.decode(self.asset.encoding)

        except UnicodeDecodeError:
            msg = (
                "The content passed into Apprise was not of encoding "
                f"type: {self.asset.encoding}"
            )
            logger.error(msg)
            raise TypeError(msg) from None

        # Tracks conversions
        conversion_body_map = {}
        conversion_title_map = {}

        # Prepare attachments if required
        if attach is not None and not isinstance(attach, AppriseAttachment):
            attach = AppriseAttachment(
                attach, asset=self.asset, location=self.location
            )

        # Allow Asset default value
        body_format = (
            self.asset.body_format if body_format is None else body_format
        )

        # Allow Asset default value
        interpret_escapes = (
            self.asset.interpret_escapes
            if interpret_escapes is None
            else interpret_escapes
        )

        # Iterate over our loaded plugins
        for server in self.find(tag, match_always=match_always):
            # If our code reaches here, we either did not define a tag (it
            # was set to None), or we did define a tag and the logic above
            # determined we need to notify the service it's associated with

            # Resolve this server's actual per-call rendering target.
            # Single-format servers always resolve to their one declared
            # format. Multi-format servers may resolve differently per
            # call depending on ?format= or this notify() call's
            # body_format.
            target_format = server.resolve_format(body_format)

            # First we need to generate a key we will use to determine if we
            # need to build our data out.  Entries without are merged with
            # the body at this stage. Keying off the resolved target
            # keeps conversion caching about the actual rendered format,
            # not the plugin's raw notify_format declaration. Two
            # servers that both resolve to HTML still share one converted
            # body even if one of them declared multiple supported
            # formats.
            key = (
                target_format
                if server.title_maxlen > 0
                else f"_{target_format}"
            )

            if server.interpret_emojis:
                # alter our key slightly to handle emojis since their value is
                # pulled out of the notification
                key += "-emojis"

            if key not in conversion_title_map:
                # Prepare our title
                conversion_title_map[key] = title if title else ""

                # Conversion of title only occurs for services where the title
                # is blended with the body (title_maxlen <= 0)
                if conversion_title_map[key] and server.title_maxlen <= 0:
                    conversion_title_map[key] = convert_between(
                        body_format,
                        target_format,
                        content=conversion_title_map[key],
                    )

                # Our body is always converted no matter what
                conversion_body_map[key] = convert_between(
                    body_format, target_format, content=body
                )

                if interpret_escapes:
                    #
                    # Escape our content
                    #

                    try:
                        # Added overhead required due to Python 3 Encoding Bug
                        # identified here: https://bugs.python.org/issue21331
                        conversion_body_map[key] = (
                            conversion_body_map[key]
                            .encode("ascii", "backslashreplace")
                            .decode("unicode-escape")
                        )

                        conversion_title_map[key] = (
                            conversion_title_map[key]
                            .encode("ascii", "backslashreplace")
                            .decode("unicode-escape")
                        )

                    except AttributeError:
                        # Must be of string type
                        msg = "Failed to escape message body"
                        logger.error(msg)
                        raise TypeError(msg) from None

                if server.interpret_emojis:
                    #
                    # Convert our :emoji: definitions
                    #

                    conversion_body_map[key] = apply_emojis(
                        conversion_body_map[key]
                    )
                    conversion_title_map[key] = apply_emojis(
                        conversion_title_map[key]
                    )

            kwargs = {
                "body": conversion_body_map[key],
                "title": conversion_title_map[key],
                "notify_type": notify_type,
                "attach": attach,
                # Pass the resolved target format; downstream notify()
                # calls use it directly without resolving again.
                # Preserve whether the caller declared a source format.
                "body_format": target_format,
                "format_controlled": body_format is not None,
            }
            yield (server, kwargs)

    @staticmethod
    def _notify_sequential(
        *services_kwargs: ServerCall, call_deadline: Optional[float] = None
    ) -> tuple[bool, list[NotifyResult]]:
        """Process a list of notify() calls one at a time, in order.

        Calls with deadlines use the shared executor so Apprise can stop
        waiting on a blocked service while preserving result order.
        """

        success = True
        results: list[NotifyResult] = []

        for service, kwargs in services_kwargs:
            # The outer wait needs a deadline before submission.
            deadline = _compute_deadline(service, call_deadline)

            if deadline is None:
                ok, notify_result = _call_with_retry(
                    service, kwargs, call_deadline
                )
                success = success and ok
                results.append(notify_result)
                continue

            # Allow a small grace window before abandoning the wait.
            abandon_at = deadline + _ABANDON_GRACE_SECONDS
            wait_start = time.monotonic()
            wait_for = max(0.0, abandon_at - wait_start)

            logger.trace(
                "Waiting up to %.3fs for '%s'.",
                wait_for,
                service.service_name,
            )

            executor = _get_shared_executor()
            future = executor.submit(
                _call_with_retry, service, kwargs, call_deadline
            )
            try:
                # Keep a final guard for unexpected executor failures.
                ok, notify_result = future.result(timeout=wait_for)
                logger.trace(
                    "'%s' finished after %.3fs: %s.",
                    service.service_name,
                    time.monotonic() - wait_start,
                    "success" if ok else "failure",
                )

            except cf.TimeoutError:
                # The service took too long; report TIMEOUT and move on.
                wait_elapsed = time.monotonic() - wait_start

                # Track only work that already started and cannot be cancelled.
                cancelled = future.cancel()
                if not cancelled:
                    name, url, _, _, _ = _service_metadata(service)
                    _track_abandoned_future(future, name, url)
                logger.trace(
                    "Stopped waiting for '%s' after %.3fs (%s).",
                    service.service_name,
                    wait_elapsed,
                    "it was still queued and has been cancelled"
                    if cancelled
                    else "its worker thread may still be running in the "
                    "background",
                )
                notify_result = _timeout_result(service, wait_elapsed)
                ok = bool(notify_result)

            except Exception as e:
                logger.warning(
                    "Notification service '%s' raised an exception.",
                    service.service_name,
                )
                logger.debug("Notification Exception: %s", str(e))
                notify_result = _safe_error_result(service)
                ok = bool(notify_result)

            # One required failure means the whole batch cannot succeed.
            # Optional failures already count as SUCCESS in NotifyResult.
            success = success and ok
            results.append(notify_result)

        return success, results

    @staticmethod
    def _notify_parallel_threadpool(
        *services_kwargs: ServerCall, call_deadline: Optional[float] = None
    ) -> tuple[bool, list[NotifyResult]]:
        """Process a list of notify() calls in parallel via a thread pool.

        Each worker handles retries and deadlines for one service. Timed-out
        workers may keep running, but Apprise stops waiting.
        """

        n_calls = len(services_kwargs)

        if n_calls == 0:
            return True, []

        if n_calls == 1:
            service, _ = services_kwargs[0]
            # Only take the no-thread-pool shortcut when this service has
            # no deadline whatsoever -- there is nothing to abandon, so a
            # plain blocking call is strictly cheaper and behaves
            # identically. Otherwise fall through to the thread-pool path
            # below so the deadline can actually be enforced.
            if _compute_deadline(service, call_deadline) is None:
                return Apprise._notify_sequential(
                    services_kwargs[0], call_deadline=call_deadline
                )

        logger.info(
            "Notifying %d service(s) with threads.", len(services_kwargs)
        )

        # Keep output ordered by input, though threads finish out of order.
        # This is the shared, process-wide pool (see _get_shared_executor()),
        # not a fresh one per call -- never shut down here, it persists for
        # the life of the process so a chronically hanging endpoint cannot
        # leak one more permanently-running thread with every call.
        executor = _get_shared_executor()
        success = True
        results: list[Optional[NotifyResult]] = [None] * n_calls

        # Snapshot every service's deadline once, right at submission
        # time (they all start at essentially the same instant here).
        deadlines: list[Optional[float]] = [
            _compute_deadline(service, call_deadline)
            for service, kwargs in services_kwargs
        ]
        future_to_idx: dict[cf.Future, int] = {
            executor.submit(
                _call_with_retry, service, kwargs, call_deadline
            ): i
            for i, (service, kwargs) in enumerate(services_kwargs)
        }

        for future, idx in future_to_idx.items():
            service = services_kwargs[idx][0]
            # Give each expired service one grace window, not one per loop.
            abandon_at = (
                deadlines[idx] + _ABANDON_GRACE_SECONDS
                if deadlines[idx] is not None
                else None
            )
            wait_start = time.monotonic()
            wait_for = (
                max(0.0, abandon_at - wait_start)
                if abandon_at is not None
                else None
            )
            logger.trace(
                "Waiting up to %s for '%s'.",
                "no limit" if wait_for is None else f"{wait_for:.3f}s",
                service.service_name,
            )
            try:
                # future.result() re-raises any exception that escaped
                # _call_with_retry (should not happen given the inner
                # try/except, but guard here as a safety net).
                ok, notify_result = future.result(timeout=wait_for)
                logger.trace(
                    "'%s' finished after %.3fs: %s.",
                    service.service_name,
                    time.monotonic() - wait_start,
                    "success" if ok else "failure",
                )

            except cf.TimeoutError:
                # Stop waiting once this service's grace window is spent.
                # NotifyResult keeps optional services successful.
                wait_elapsed = time.monotonic() - wait_start

                # Still queued -> cancel() succeeds, nothing to track.
                # Already running -> cancel() fails, so track it instead.
                cancelled = future.cancel()
                if not cancelled:
                    name, url, _, _, _ = _service_metadata(service)
                    _track_abandoned_future(future, name, url)
                logger.trace(
                    "Stopped waiting for '%s' after %.3fs (%s).",
                    service.service_name,
                    wait_elapsed,
                    "it was still queued and has been cancelled"
                    if cancelled
                    else "its worker thread may still be running in the "
                    "background",
                )
                notify_result = _timeout_result(service, wait_elapsed)
                ok = bool(notify_result)

            except Exception as e:
                logger.warning(
                    "Notification service '%s' raised an exception.",
                    service.service_name,
                )
                logger.debug("Notification Exception: %s", str(e))
                notify_result = _safe_error_result(service)
                ok = bool(notify_result)

            success = success and ok
            results[idx] = notify_result

        return success, results

    @staticmethod
    async def _notify_parallel_asyncio(
        *services_kwargs: ServerCall, call_deadline: Optional[float] = None
    ) -> tuple[bool, list[NotifyResult]]:
        """Process a list of async_notify() calls concurrently via asyncio.

        Each coroutine handles one service, including retry and wait logic.
        The outer wait_for() keeps one stuck service from blocking its peers.

        A timeout means Apprise stops waiting and reports TIMEOUT. If the
        plugin is running sync work in a worker thread, that work may still
        finish later.
        """

        n_calls = len(services_kwargs)

        if n_calls == 0:
            return True, []

        logger.info(
            "Notifying %d service(s) asynchronously.", len(services_kwargs)
        )

        async def do_call(
            service: NotifyBase, kwargs: dict[str, Any]
        ) -> tuple[bool, NotifyResult]:
            """Coroutine driving one service's async_notify() with retry/wait.

            Pops ``_retry_override`` from kwargs so it is never forwarded
            to the plugin.  Exceptions are caught and treated as failures
            so the retry loop continues even when a plugin raises
            unexpectedly (e.g. a third-party @notify-decorated coroutine).

            Returns (bool, NotifyResult) -- see the module-level
            _call_with_retry() for the equivalent contract used by the
            sequential and thread-pool dispatch styles.
            """
            # Pop the per-call overrides so they stay internal.
            retry = kwargs.pop("_retry_override", getattr(service, "retry", 0))
            wait = getattr(service, "wait", 0.0)
            log_callback = kwargs.pop("_log_callback", None)

            # Computed fresh as this coroutine actually starts running,
            # same rationale as the module-level _call_with_retry().
            deadline = _compute_deadline(service, call_deadline)
            attempts: list[NotifyAttempt] = []
            for attempt in range(retry + 1):
                if deadline is not None and time.monotonic() >= deadline:
                    # Out of time -- record a zero-elapsed TIMEOUT attempt
                    # marking the decision to stop, and do not start
                    # another one.
                    logger.trace(
                        "Deadline already passed for '%s'; skipping "
                        "attempt %d/%d.",
                        service.service_name,
                        attempt + 1,
                        retry + 1,
                    )
                    attempts.append(
                        NotifyAttempt(
                            status=AppriseResultStatus.TIMEOUT,
                            logs=[
                                _timeout_log_entry(service.service_name, 0.0)
                            ],
                        )
                    )
                    break

                attempt_start = time.monotonic()
                logger.trace(
                    "Starting attempt %d/%d for '%s'.",
                    attempt + 1,
                    retry + 1,
                    service.service_name,
                )
                # Mirror the exception handling from the synchronous paths:
                # Treat validation and plugin exceptions as failed attempts.
                # The retry loop can still continue for this service.
                with _ServiceLogCapture(
                    service, log_callback=log_callback
                ) as capture:
                    try:
                        result = await service.async_notify(**kwargs)

                    except TypeError:
                        result = False

                    except Exception as e:
                        logger.warning(
                            "Notification service '%s' raised an exception.",
                            service.service_name,
                        )
                        logger.debug("Notification Exception: %s", str(e))
                        result = False

                attempt_elapsed = time.monotonic() - attempt_start
                logger.trace(
                    "Attempt %d/%d for '%s' finished in %.3fs: %s.",
                    attempt + 1,
                    retry + 1,
                    service.service_name,
                    attempt_elapsed,
                    "success" if result else "failure",
                )
                attempts.append(
                    NotifyAttempt(
                        status=_attempt_status(result),
                        elapsed=attempt_elapsed,
                        logs=capture.entries,
                    )
                )

                if result:
                    break

                if attempt < retry:
                    logger.warning(
                        "Attempt %d/%d for '%s' failed; trying again.",
                        attempt + 1,
                        retry,
                        service.service_name,
                    )
                    if wait > 0:
                        sleep_for = wait
                        if deadline is not None:
                            sleep_for = min(
                                wait, max(0.0, deadline - time.monotonic())
                            )
                        if sleep_for > 0:
                            await asyncio.sleep(sleep_for)

            # Optional services can fail quietly, but keep a log breadcrumb.
            optional = getattr(service, "optional", False)
            succeeded = any(
                a.status == AppriseResultStatus.SUCCESS for a in attempts
            )
            if not succeeded and optional:
                logger.info(
                    "Optional service '%s' did not send successfully; "
                    "continuing.",
                    service.service_name,
                )

            # Build result metadata defensively; plugin helpers may raise.
            name, url, url_id, tag, weight = _service_metadata(service)
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

            return bool(notify_result), notify_result

        async def do_call_bounded(
            service: NotifyBase,
            kwargs: dict[str, Any],
            deadline: Optional[float],
        ) -> tuple[bool, NotifyResult]:
            """Apply an outer asyncio timeout to one service call.

            The service still owns its normal retry deadline inside do_call().
            This wrapper limits how long this batch waits for the result.
            """
            remaining = (
                max(0.0, deadline - time.monotonic())
                if deadline is not None
                else None
            )
            # Add one small grace window so a nearly-finished service can
            # settle before it is reported as abandoned.
            wait_for = (
                remaining + _ABANDON_GRACE_SECONDS
                if remaining is not None
                else None
            )
            logger.trace(
                "Waiting up to %s for '%s'.",
                "no limit" if wait_for is None else f"{wait_for:.3f}s",
                service.service_name,
            )
            wait_start = time.monotonic()
            try:
                # timeout=None makes wait_for() behave like a plain await.
                # This keeps the bounded and unbounded paths together.
                ok, notify_result = await asyncio.wait_for(
                    do_call(service, kwargs), timeout=wait_for
                )
                logger.trace(
                    "'%s' finished after %.3fs: %s.",
                    service.service_name,
                    time.monotonic() - wait_start,
                    "success" if ok else "failure",
                )
                return ok, notify_result

            except asyncio.TimeoutError:
                # Derive the outcome from NotifyResult so an optional timeout
                # remains successful.
                # Apprise stops waiting here; it does not promise delivery
                # work has stopped underneath.
                logger.trace(
                    "Stopped waiting for '%s' after %.3fs; it may still "
                    "be finishing in the background.",
                    service.service_name,
                    time.monotonic() - wait_start,
                )
                notify_result = _timeout_result(service, remaining or 0.0)
                return bool(notify_result), notify_result

        # Snapshot outer wait deadlines before launching the async workers.
        # do_call() still computes its own deadline once it starts running.
        deadlines: list[Optional[float]] = [
            _compute_deadline(service, call_deadline)
            for service, kwargs in services_kwargs
        ]

        # Run all coroutines concurrently.  return_exceptions=True ensures
        # one escaped exception is reported without cancelling other services.
        cors = (
            do_call_bounded(service, kwargs, deadlines[i])
            for i, (service, kwargs) in enumerate(services_kwargs)
        )
        gathered = await asyncio.gather(*cors, return_exceptions=True)

        success = True
        results: list[NotifyResult] = []
        for idx, item in enumerate(gathered):
            service = services_kwargs[idx][0]
            if isinstance(item, Exception):
                # Safety net: an exception escaped do_call's own try/except.
                logger.warning(
                    "Notification service '%s' raised an exception.",
                    service.service_name,
                )
                logger.debug("Notification Exception: %s", str(item))
                notify_result = _safe_error_result(service)
                success = success and bool(notify_result)
                results.append(notify_result)

            else:
                ok, notify_result = item
                success = success and ok
                results.append(notify_result)

        return success, results

    def json(
        self,
        lang: Optional[str] = None,
        show_requirements: bool = False,
        show_disabled: bool = False,
        indent: Optional[int] = None,
        path: Optional[str] = None,
    ) -> Union[str, bool]:
        """Returns a json response associated with the Apprise object."""
        details = self.details(
            lang=lang,
            show_requirements=show_requirements,
            show_disabled=show_disabled,
        )

        if not path:
            return json.dumps(
                details,
                separators=JSON_COMPACT_SEPARATORS,
                indent=indent,
                cls=AppriseJSONEncoder,
            )

        with open(path, "w") as fp:
            try:
                json.dump(
                    details,
                    fp,
                    separators=JSON_COMPACT_SEPARATORS,
                    indent=indent,
                    cls=AppriseJSONEncoder,
                    ensure_ascii=False,
                )

            except (OSError, EOFError) as e:
                logger.error("Apprise details dumpfile inaccessible: %s", path)
                logger.debug("Apprise details dump Exception: %s", e)

                # Early Exit
                return False

            finally:
                # Reduce memory
                del details

        return True

    def details(
        self,
        lang: Optional[str] = None,
        show_requirements: bool = False,
        show_disabled: bool = False,
    ) -> dict[str, Any]:
        """Returns the details associated with the Apprise object."""

        # general object returned
        response = {
            # Defines the current version of Apprise
            "version": __version__,
            # Lists all of the currently supported Notifications
            "schemas": [],
            # Includes the configured asset details
            "asset": self.asset.details(),
        }

        for plugin in N_MGR.plugins():
            # Iterate over our hashed plugins and dynamically build details on
            # their status:

            content = {
                "service_name": getattr(plugin, "service_name", None),
                "service_url": getattr(plugin, "service_url", None),
                "setup_url": getattr(plugin, "setup_url", None),
                # Placeholder - populated below
                "details": None,
                # Let upstream service know of the plugins that support
                # attachments
                "attachment_support": getattr(
                    plugin, "attachment_support", False
                ),
                # Differentiat between what is a custom loaded plugin and
                # which is native.
                "category": getattr(plugin, "category", None),
            }

            # Standard protocol(s) should be None or a tuple
            enabled = getattr(plugin, "enabled", True)
            if not show_disabled and not enabled:
                # Do not show inactive plugins
                continue

            elif show_disabled:
                # Add current state to response
                content["enabled"] = enabled

            # Standard protocol(s) should be None or a tuple
            protocols = getattr(plugin, "protocol", None)
            if isinstance(protocols, str):
                protocols = (protocols,)

            # Secure protocol(s) should be None or a tuple
            secure_protocols = getattr(plugin, "secure_protocol", None)
            if isinstance(secure_protocols, str):
                secure_protocols = (secure_protocols,)

            # Add our protocol details to our content
            content.update(
                {
                    "protocols": protocols,
                    "secure_protocols": secure_protocols,
                }
            )

            if not lang:
                # Simply return our results
                content["details"] = plugins.details(plugin)
                if show_requirements:
                    content["requirements"] = plugins.requirements(plugin)

            else:
                # Emulate the specified language when returning our results
                with self.locale.lang_at(lang):
                    content["details"] = plugins.details(plugin)
                    if show_requirements:
                        content["requirements"] = plugins.requirements(plugin)

            # Build our response object
            response["schemas"].append(content)

        return response

    def urls(self, privacy: bool = False) -> list[str]:
        """Returns all of the loaded URLs defined in this apprise object."""
        urls = []
        for s in self.servers:
            if isinstance(s, (ConfigBase, AppriseConfig)):
                for s_ in s.servers():
                    urls.append(s_.url(privacy=privacy))
            else:
                urls.append(s.url(privacy=privacy))
        return urls

    def pop(self, index: int) -> NotifyBase:
        """Removes an indexed Notification Service from the stack and returns
        it.

        The thing is we can never pop AppriseConfig() entries, only what was
        loaded within them. So pop needs to carefully iterate over our list and
        only track actual entries.
        """

        # Tracking variables
        prev_offset = -1
        offset = prev_offset

        for idx, s in enumerate(self.servers):
            if isinstance(s, (ConfigBase, AppriseConfig)):
                servers = s.servers()
                if len(servers) > 0:
                    # Acquire a new maximum offset to work with
                    offset = prev_offset + len(servers)

                    if offset >= index:
                        # we can pop an element from our config stack
                        fn = (
                            s.pop
                            if isinstance(s, ConfigBase)
                            else s.server_pop
                        )

                        return fn(
                            index
                            if prev_offset == -1
                            else (index - prev_offset - 1)
                        )

            else:
                offset = prev_offset + 1
                if offset == index:
                    return self.servers.pop(idx)

            # Update our old offset
            prev_offset = offset

        # If we reach here, then we indexed out of range
        raise IndexError("list index out of range")

    def __getitem__(self, index: int) -> NotifyBase:
        """Returns the indexed server entry of a loaded notification server."""
        # Tracking variables
        prev_offset = -1
        offset = prev_offset

        for idx, s in enumerate(self.servers):
            if isinstance(s, (ConfigBase, AppriseConfig)):
                # Get our list of servers associate with our config object
                servers = s.servers()
                if len(servers) > 0:
                    # Acquire a new maximum offset to work with
                    offset = prev_offset + len(servers)

                    if offset >= index:
                        return servers[
                            (
                                index
                                if prev_offset == -1
                                else (index - prev_offset - 1)
                            )
                        ]

            else:
                offset = prev_offset + 1
                if offset == index:
                    return self.servers[idx]

            # Update our old offset
            prev_offset = offset

        # If we reach here, then we indexed out of range
        raise IndexError("list index out of range")

    def __getstate__(self) -> dict[str, object]:
        """Pickle Support dumps()"""
        attributes = {
            "asset": self.asset,
            # Prepare our URL list as we need to extract the associated tags
            # and asset details associated with it
            "urls": [
                {
                    "url": server.url(privacy=False),
                    "tag": server.tags if server.tags else None,
                    "asset": server.asset,
                }
                for server in self.servers
            ],
            "locale": self.locale,
            "debug": self.debug,
            "location": self.location.value if self.location else None,
        }

        return attributes

    def __setstate__(self, state: dict[str, object]) -> None:
        """Pickle Support loads()"""
        self.servers = []
        self.asset = state["asset"]
        self.locale = state["locale"]

        location = state.get("location")
        self.location = (
            location
            if isinstance(location, ContentLocation)
            else ContentLocation(location)
            if location is not None
            else None
        )

        for entry in state["urls"]:
            self.add(entry["url"], asset=entry["asset"], tag=entry["tag"])

    def __bool__(self) -> bool:
        """Allows the Apprise object to be wrapped in an 'if statement'.

        True is returned if at least one service has been loaded.
        """
        return len(self) > 0

    def __iter__(self) -> Iterator[NotifyBase]:
        """Returns an iterator to each of our servers loaded.

        This includes those found inside configuration.
        """
        return chain(
            *[
                (
                    [s]
                    if not isinstance(s, (ConfigBase, AppriseConfig))
                    else iter(s.servers())
                )
                for s in self.servers
            ]
        )

    def __len__(self) -> int:
        """Returns the number of servers loaded; this includes those found
        within loaded configuration.

        This funtion nnever actually counts the Config entry themselves (if
        they exist), only what they contain.
        """
        return sum(
            (
                1
                if not isinstance(s, (ConfigBase, AppriseConfig))
                else len(s.servers())
            )
            for s in self.servers
        )
