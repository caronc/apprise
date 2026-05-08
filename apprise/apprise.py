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
import os
import time
from typing import Any, Optional, Union

from . import __version__, common, plugins
from .apprise_attachment import AppriseAttachment
from .apprise_config import AppriseConfig
from .asset import AppriseAsset
from .common import ContentLocation
from .config.base import ConfigBase
from .conversion import convert_between
from .emojis import apply_emojis
from .locale import AppriseLocale
from .logger import logger
from .manager_plugins import NotificationManager
from .plugins.base import NotifyBase
from .tag import AppriseTag
from .utils.cwe312 import cwe312_url
from .utils.json import AppriseJSONEncoder
from .utils.logic import is_exclusive_match
from .utils.parse import parse_list, parse_urls

# Grant access to our Notification Manager Singleton
N_MGR = NotificationManager()


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
    ) -> None:
        """Loads a set of server urls while applying the Asset() module to each
        if specified.

        If no asset is provided, then the default asset is used.

        Optionally specify a global ContentLocation for a more strict means of
        handling Attachments.
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
    ) -> Optional[bool]:
        """Send a notification to all the plugins previously loaded.

        If the body_format specified is NotifyFormat.MARKDOWN, it will be
        converted to HTML if the Notification type expects this.

        if the tag is specified (either a string or a set/list/tuple of
        strings), then only the notifications flagged with that tagged value
        are notified.  By default, all added services are notified
        (tag=MATCH_ALL_TAG)

        This function returns True if all notifications were successfully sent,
        False if even just one of them fails, and None if no notifications were
        sent at all as a result of tag filtering and/or simply having empty
        configuration files that were read.

        A filter tag may carry an optional priority prefix and/or retry suffix:

          "endpoint"       -> match all entries; escalate by priority
          "3:endpoint"     -> match ONLY priority-3 entries; flat dispatch
          "endpoint:2"     -> match all entries; retry each up to 2 times
          "3:endpoint:2"   -> exclusive priority-3 match with 2 retries

        When no priority prefix is given, matched services are grouped by
        their configured tag priority and dispatched in ascending order
        (lowest number = highest urgency).  If every service in the lowest
        priority group succeeds, Apprise returns True immediately without
        running higher-numbered priority groups (escalation chain).

        When an explicit priority prefix IS given (e.g. "3:endpoint"), only
        services whose matching tag carries that exact priority are notified,
        and all matched services are dispatched as a single flat batch.

        Attach can contain a list of attachment URLs.  attach can also be
        represented by an AttachBase() (or list of) object(s). This identifies
        the products you wish to notify

        Set interpret_escapes to True if you want to pre-escape a string such
        as turning a \n into an actual new line, etc.
        """

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
            return False

        if not all_calls:
            return None

        # Inject the per-service call-time retry override.  Each matched
        # service gets the retry from the first filter token that both matches
        # it and carries a retry suffix (e.g. "devops:3" applies retry=3 only
        # to devops-tagged services, not to management-tagged services).
        all_calls = Apprise._inject_per_service_retries(all_calls, tag)

        if Apprise._filter_has_explicit_priority(tag):
            # Tag filter carries an explicit priority prefix (e.g. "2:alerts").
            # Skip the escalation chain: dispatch all matched services as a
            # single flat batch regardless of their individual tag priorities.
            sequential = [
                (s, k) for s, k in all_calls if not s.asset.async_mode
            ]
            parallel = [(s, k) for s, k in all_calls if s.asset.async_mode]
            seq_ok = (
                Apprise._notify_sequential(*sequential) if sequential else True
            )
            par_ok = (
                Apprise._notify_parallel_threadpool(*parallel)
                if parallel
                else True
            )
            return seq_ok and par_ok

        # No explicit priority in the filter -- use per-tag escalation chains.
        #
        # Each distinct OR token forms an independent chain.  Within a chain,
        # services are grouped by their configured tag priority.  The lowest-
        # numbered group (highest urgency) runs first.  If every service in
        # that group succeeds the chain is done; any failure escalates to the
        # next priority group.  notify() returns True only when every chain
        # finds a fully-successful group.
        #
        # When multiple chains are active in the same round their current
        # priority-group batches run concurrently via a thread pool so that
        # one chain's services cannot delay another chain.
        chains = Apprise._build_tag_chains(all_calls, tag)

        def _run_batch(batch):
            """Dispatch one priority-group batch; True = all services ok."""
            seq = [(s, k) for s, k in batch if not s.asset.async_mode]
            par = [(s, k) for s, k in batch if s.asset.async_mode]
            seq_ok = Apprise._notify_sequential(*seq) if seq else True
            par_ok = Apprise._notify_parallel_threadpool(*par) if par else True
            return seq_ok and par_ok

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

        while True:
            # When abort_on_chain_failure is enabled, stop as soon as any
            # chain has exhausted all its priority groups without success.
            # With the default (False) all chains run to completion even if
            # one has already failed, so every defined URL gets an attempt.
            if self.asset.abort_on_chain_failure and any(
                not st["succeeded"] and st["idx"] >= len(st["priorities"])
                for st in chain_states.values()
            ):
                return False

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
                _, st = active[0]
                batch = st["groups"][st["priorities"][st["idx"]]]
                if _run_batch(batch):
                    st["succeeded"] = True
                else:
                    st["idx"] += 1  # escalate to next priority
            else:
                # Multiple active chains: run their current-priority batches
                # concurrently so independent chains don't block each other.
                with cf.ThreadPoolExecutor() as executor:
                    future_map = {
                        executor.submit(
                            _run_batch,
                            st["groups"][st["priorities"][st["idx"]]],
                        ): (key, st)
                        for key, st in active
                    }
                    for future in cf.as_completed(future_map):
                        _, st = future_map[future]
                        try:
                            ok = future.result()
                        except Exception:
                            logger.exception(
                                "Unhandled Notification Exception"
                            )
                            ok = False
                        if ok:
                            st["succeeded"] = True
                        else:
                            st["idx"] += 1  # escalate to next priority

        return all(st["succeeded"] for st in chain_states.values())

    async def async_notify(self, *args: Any, **kwargs: Any) -> Optional[bool]:
        """Send a notification to all the plugins previously loaded, for
        asynchronous callers.

        The arguments are identical to those of Apprise.notify().
        """
        tag = kwargs.get("tag", common.MATCH_ALL_TAG)

        try:
            all_calls = list(self._create_notify_gen(*args, **kwargs))

        except TypeError:
            return False

        if not all_calls:
            return None

        # Inject per-service call-time retry overrides (same logic as notify).
        all_calls = Apprise._inject_per_service_retries(all_calls, tag)

        if Apprise._filter_has_explicit_priority(tag):
            # Explicit priority prefix: flat dispatch, no escalation.
            sequential = [
                (s, k) for s, k in all_calls if not s.asset.async_mode
            ]
            parallel = [(s, k) for s, k in all_calls if s.asset.async_mode]
            seq_ok = (
                Apprise._notify_sequential(*sequential) if sequential else True
            )
            par_ok = (
                await Apprise._notify_parallel_asyncio(*parallel)
                if parallel
                else True
            )
            return seq_ok and par_ok

        # Per-tag independent escalation chains -- same semantics as notify().
        #
        # Each chain's current-priority batch is dispatched as a coroutine.
        # All active chains' batches run concurrently via asyncio.gather() so
        # async services across independent chains can make I/O progress
        # simultaneously.  Only chains whose current batch failed advance to
        # the next priority group (escalation).
        chains = Apprise._build_tag_chains(all_calls, tag)

        async def _run_batch_async(batch):
            """Dispatch one priority-group batch; True = all services ok."""
            seq = [(s, k) for s, k in batch if not s.asset.async_mode]
            par = [(s, k) for s, k in batch if s.asset.async_mode]
            # Sequential items (async_mode=False) run blocking in the caller;
            # async items are gathered concurrently.
            seq_ok = Apprise._notify_sequential(*seq) if seq else True
            par_ok = (
                await Apprise._notify_parallel_asyncio(*par) if par else True
            )
            return seq_ok and par_ok

        chain_states = {
            key: {
                "priorities": sorted(groups),
                "groups": groups,
                "idx": 0,
                "succeeded": False,
            }
            for key, groups in chains.items()
        }

        while True:
            # Same abort_on_chain_failure guard as notify().
            if self.asset.abort_on_chain_failure and any(
                not st["succeeded"] and st["idx"] >= len(st["priorities"])
                for st in chain_states.values()
            ):
                return False

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
            results = await asyncio.gather(
                *(
                    _run_batch_async(st["groups"][st["priorities"][st["idx"]]])
                    for _, st in active
                ),
                return_exceptions=True,
            )

            for (_, st), ok in zip(active, results):
                if isinstance(ok, Exception):
                    # Escaped exception -- safety net; treat as failure.
                    logger.exception("Unhandled Notification Exception")
                    st["idx"] += 1
                elif ok:
                    st["succeeded"] = True
                else:
                    st["idx"] += 1  # escalate to next priority group

        return all(st["succeeded"] for st in chain_states.values())

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
            # Nothing to notify
            msg = "There are no service(s) to notify"
            logger.error(msg)
            raise TypeError(msg)

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

            # First we need to generate a key we will use to determine if we
            # need to build our data out.  Entries without are merged with
            # the body at this stage.
            key = (
                server.notify_format
                if server.title_maxlen > 0
                else f"_{server.notify_format}"
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
                        server.notify_format,
                        content=conversion_title_map[key],
                    )

                # Our body is always converted no matter what
                conversion_body_map[key] = convert_between(
                    body_format, server.notify_format, content=body
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
                "body_format": body_format,
            }
            yield (server, kwargs)

    @staticmethod
    def _notify_sequential(*servers_kwargs):
        """Process a list of notify() calls sequentially and synchronously.

        Each server is attempted once and then retried up to server.retry
        additional times on failure before moving on.  When server.wait is
        greater than zero, the process sleeps that many seconds between
        each retry attempt.

        A per-call retry override may be injected into kwargs under the key
        ``_retry_override``; when present it takes precedence over the
        server's own retry attribute for this invocation only.

        Exceptions raised by a plugin's notify() -- including those from
        third-party @notify-decorated functions that are outside our control
        -- are caught here and treated as a delivery failure.  The retry
        logic still applies, so a plugin that raises on the first attempt
        will be retried the configured number of times before giving up.
        """

        success = True

        for server, kwargs in servers_kwargs:
            # Pop the per-call override before forwarding kwargs to the
            # plugin so it never sees the internal _retry_override key.
            retry = kwargs.pop("_retry_override", getattr(server, "retry", 0))
            wait = getattr(server, "wait", 0.0)

            result = False
            for attempt in range(retry + 1):
                # Attempt delivery.  TypeError comes from Apprise's own
                # validation; bare Exception guards against buggy or
                # third-party plugins (including @notify decorators) that
                # may raise unexpectedly.  Both are treated as failure so
                # the retry loop can continue.
                try:
                    result = server.notify(**kwargs)
                except TypeError:
                    result = False
                except Exception:
                    logger.exception("Unhandled Notification Exception")
                    result = False

                if result:
                    # Delivered successfully; no need to retry this server.
                    break

                if attempt < retry:
                    # Delivery failed and retries remain.  Log the attempt
                    # number and pause before the next try.
                    logger.warning(
                        "Retry %d/%d for %s",
                        attempt + 1,
                        retry,
                        server.service_name,
                    )
                    if wait > 0:
                        time.sleep(wait)

            # Optional-service check.
            #
            # At this point all retry attempts for 'server' have been
            # exhausted (the for-loop above has finished).  If the final
            # result is still False *and* the service is marked optional,
            # we overwrite result to True before folding it into the
            # running 'success' accumulator.  This silently absorbs the
            # failure: the caller will not see it as a delivery error.
            #
            # Interaction with retries:
            #   The retry loop above has already run.  optional= does not
            #   short-circuit or bypass retries -- it only changes the
            #   interpretation of the *final* result once all attempts
            #   are done.  A service with retry=3 and optional=True will
            #   still be attempted four times before the failure is
            #   absorbed here.
            if not result and getattr(server, "optional", False):
                logger.info(
                    "Optional service '%s' failed; ignoring failure.",
                    server.service_name,
                )
                result = True

            # Fold this service's result into the running batch outcome.
            # Boolean AND is used so that a single False from any required
            # (non-optional) service permanently taints 'success' for the
            # whole batch -- even if later services succeed.  Optional
            # failures are already re-mapped to True above, so they never
            # contribute a False here.
            success = success and result

        return success

    @staticmethod
    def _notify_parallel_threadpool(*servers_kwargs):
        """Process a list of notify() calls in parallel via a thread pool.

        Each server runs in its own thread.  Within each thread, the server
        is retried up to server.retry additional times on failure with an
        optional server.wait second sleep between each attempt.

        Falls back to _notify_sequential() when only a single server is
        given to avoid the overhead of spawning a thread pool for one call.

        Exceptions from a plugin's notify() -- including those from
        third-party @notify-decorated functions -- are caught inside each
        thread and treated as delivery failures so the retry logic can
        still run.
        """

        n_calls = len(servers_kwargs)

        if n_calls == 0:
            return True

        # Avoid thread-pool overhead for a single notification.
        if n_calls == 1:
            return Apprise._notify_sequential(servers_kwargs[0])

        logger.info(
            "Notifying %d service(s) with threads.", len(servers_kwargs)
        )

        def _call_with_retry(server, kwargs):
            """Execute one server's notify() with retry/wait logic.

            Runs inside a worker thread.  Pops ``_retry_override`` from
            kwargs so it is never forwarded to the plugin's notify() call.
            Exceptions are caught and treated as failures so the retry
            loop continues even when a plugin raises unexpectedly.
            """
            # Pop the per-call override so it stays internal.
            retry = kwargs.pop("_retry_override", getattr(server, "retry", 0))
            wait = getattr(server, "wait", 0.0)

            result = False
            for attempt in range(retry + 1):
                # Same exception handling as _notify_sequential: TypeError
                # from Apprise validation and bare Exception for buggy or
                # third-party plugins both map to a retriable failure.
                try:
                    result = server.notify(**kwargs)
                except TypeError:
                    result = False
                except Exception:
                    logger.exception("Unhandled Notification Exception")
                    result = False

                if result:
                    return True

                if attempt < retry:
                    logger.warning(
                        "Retry %d/%d for %s",
                        attempt + 1,
                        retry,
                        server.service_name,
                    )
                    if wait > 0:
                        time.sleep(wait)

            # Optional-service check (thread-pool path).
            #
            # All retry attempts for this server have been exhausted by the
            # loop above.  If the final result is still False and the service
            # is tagged as optional, return True from this worker function
            # instead of False.  The caller (_notify_parallel_threadpool)
            # collects each worker's return value via future.result() and
            # ANDs them together; returning True here prevents this worker's
            # failure from tainting the aggregate result.
            #
            # This is the thread-pool equivalent of the same check in
            # _notify_sequential.  See the comment there for a full
            # explanation of the getattr() guard and the retry interaction.
            if not result and getattr(server, "optional", False):
                logger.info(
                    "Optional service '%s' failed; ignoring failure.",
                    server.service_name,
                )
                # Return True so future.result() in the caller reports
                # success for this optional worker thread.
                return True

            # Every attempt for this service failed and it is not optional;
            # propagate the failure to the caller.
            return result

        # Submit all server calls to the thread pool and collect results.
        with cf.ThreadPoolExecutor() as executor:
            success = True
            futures = [
                executor.submit(_call_with_retry, server, kwargs)
                for (server, kwargs) in servers_kwargs
            ]

            for future in cf.as_completed(futures):
                # future.result() re-raises any exception that escaped
                # _call_with_retry (should not happen given the inner
                # try/except, but guard here as a safety net).
                try:
                    success = success and future.result()
                except Exception:
                    logger.exception("Unhandled Notification Exception")
                    success = False

            return success

    @staticmethod
    async def _notify_parallel_asyncio(*servers_kwargs):
        """Process a list of async_notify() calls concurrently via asyncio.

        All coroutines are gathered with asyncio.gather().  Each server is
        retried up to server.retry additional times on failure with an
        optional asyncio.sleep(server.wait) between attempts.

        Unlike the thread-pool path, there is no single-server optimisation
        here because asyncio can pipeline work across coroutines while one
        is awaiting I/O.

        Exceptions from a plugin's async_notify() -- including those from
        third-party @notify-decorated coroutines -- are caught inside each
        coroutine and treated as delivery failures so the retry loop can
        still run for that service.
        """

        n_calls = len(servers_kwargs)

        if n_calls == 0:
            return True

        logger.info(
            "Notifying %d service(s) asynchronously.", len(servers_kwargs)
        )

        async def do_call(server, kwargs):
            """Coroutine driving one server's async_notify() with retry/wait.

            Pops ``_retry_override`` from kwargs so it is never forwarded
            to the plugin.  Exceptions are caught and treated as failures
            so the retry loop continues even when a plugin raises
            unexpectedly (e.g. a third-party @notify-decorated coroutine).
            """
            # Pop the per-call override so it stays internal.
            retry = kwargs.pop("_retry_override", getattr(server, "retry", 0))
            wait = getattr(server, "wait", 0.0)

            result = False
            for attempt in range(retry + 1):
                # Mirror the exception handling from the synchronous paths:
                # TypeError from Apprise's own validation layer and bare
                # Exception for any plugin that raises unexpectedly are both
                # treated as retriable failures rather than hard crashes.
                try:
                    result = await server.async_notify(**kwargs)
                except TypeError:
                    result = False
                except Exception:
                    logger.exception("Unhandled Notification Exception")
                    result = False

                if result:
                    return True

                if attempt < retry:
                    logger.warning(
                        "Retry %d/%d for %s",
                        attempt + 1,
                        retry,
                        server.service_name,
                    )
                    if wait > 0:
                        await asyncio.sleep(wait)

            # Optional-service check (asyncio coroutine path).
            #
            # All retry attempts have been exhausted by the async loop
            # above.  If the final result is still False and the service
            # is tagged optional, return True from this coroutine so that
            # asyncio.gather() receives a truthy value for this task.
            # The caller inspects all gathered results with all(); a True
            # here ensures this coroutine does not lower the aggregate
            # result for the batch.
            #
            # This is the asyncio equivalent of the same check in
            # _notify_sequential and _call_with_retry.  See the comment
            # in _notify_sequential for a full explanation of the getattr()
            # guard and the interaction with the retry count.
            if not result and getattr(server, "optional", False):
                logger.info(
                    "Optional service '%s' failed; ignoring failure.",
                    server.service_name,
                )
                # Return True so asyncio.gather() sees a success value
                # for this optional coroutine.
                return True

            # Every attempt for this service failed and it is not optional;
            # propagate the failure to the caller.
            return result

        # Run all coroutines concurrently.  return_exceptions=True ensures
        # that one coroutine raising does not cancel the others; any escaped
        # exception (beyond what do_call already handles) is caught below.
        cors = (do_call(server, kwargs) for (server, kwargs) in servers_kwargs)
        results = await asyncio.gather(*cors, return_exceptions=True)

        if any(isinstance(status, Exception) for status in results):
            # Safety net: an exception escaped do_call's own try/except.
            # Log each one and treat the whole batch as failed.
            for status in results:
                if isinstance(status, Exception):
                    logger.error(
                        "Unhandled Notification Exception: %s", status
                    )
            return False

        return all(results)

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
                separators=(",", ":"),
                indent=indent,
                cls=AppriseJSONEncoder,
            )

        with open(path, "w") as fp:
            try:
                json.dump(
                    details,
                    fp,
                    separators=(",", ":"),
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
