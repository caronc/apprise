# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2025, Chris Caron <lead2gold@gmail.com>
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
import os
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
from .utils.cwe312 import cwe312_url
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

        for _server in servers:

            if isinstance(_server, (ConfigBase, NotifyBase, AppriseConfig)):
                # Go ahead and just add our plugin into our list
                self.servers.append(_server)
                continue

            elif not isinstance(_server, (str, dict)):
                logger.error(
                    f"An invalid notification (type={type(_server)}) was"
                    " specified."
                )
                return_status = False
                continue

            # Instantiate ourselves an object, this function throws or
            # returns None if it fails
            instance = Apprise.instantiate(_server, asset=asset, tag=tag)
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

        Attach can contain a list of attachment URLs.  attach can also be
        represented by an AttachBase() (or list of) object(s). This identifies
        the products you wish to notify

        Set interpret_escapes to True if you want to pre-escape a string such
        as turning a \n into an actual new line, etc.
        """

        try:
            # Process arguments and build synchronous and asynchronous calls
            # (this step can throw internal errors).
            sequential_calls, parallel_calls = self._create_notify_calls(
                body,
                title,
                notify_type=notify_type,
                body_format=body_format,
                tag=tag,
                match_always=match_always,
                attach=attach,
                interpret_escapes=interpret_escapes,
            )

        except TypeError:
            # No notifications sent, and there was an internal error.
            return False

        if not sequential_calls and not parallel_calls:
            # Nothing to send
            return None

        sequential_result = Apprise._notify_sequential(*sequential_calls)
        parallel_result = Apprise._notify_parallel_threadpool(*parallel_calls)
        return sequential_result and parallel_result

    async def async_notify(
        self,
        *args: Any,
        **kwargs: Any
    ) -> Optional[bool]:
        """Send a notification to all the plugins previously loaded, for
        asynchronous callers.

        The arguments are identical to those of Apprise.notify().
        """
        try:
            # Process arguments and build synchronous and asynchronous calls
            # (this step can throw internal errors).
            sequential_calls, parallel_calls = self._create_notify_calls(
                *args, **kwargs
            )

        except TypeError:
            # No notifications sent, and there was an internal error.
            return False

        if not sequential_calls and not parallel_calls:
            # Nothing to send
            return None

        sequential_result = Apprise._notify_sequential(*sequential_calls)
        parallel_result = await Apprise._notify_parallel_asyncio(
            *parallel_calls
        )
        return sequential_result and parallel_result

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
                notify_type if isinstance(notify_type, common.NotifyType)
                else common.NotifyType(notify_type.lower())
            )

        except (AttributeError, ValueError, TypeError):
            err = (
                f"An invalid notification type ({notify_type}) was "
                "specified.")
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
        """Process a list of notify() calls sequentially and synchronously."""

        success = True

        for server, kwargs in servers_kwargs:
            try:
                # Send notification
                result = server.notify(**kwargs)
                success = success and result

            except TypeError:
                # These are our internally thrown notifications.
                success = False

            except Exception:
                # A catch all so we don't have to abort early
                # just because one of our plugins has a bug in it.
                logger.exception("Unhandled Notification Exception")
                success = False

        return success

    @staticmethod
    def _notify_parallel_threadpool(*servers_kwargs):
        """Process a list of notify() calls in parallel and synchronously."""

        n_calls = len(servers_kwargs)

        # 0-length case
        if n_calls == 0:
            return True

        # There's no need to use a thread pool for just a single notification
        if n_calls == 1:
            return Apprise._notify_sequential(servers_kwargs[0])

        # Create log entry
        logger.info(
            "Notifying %d service(s) with threads.", len(servers_kwargs)
        )

        with cf.ThreadPoolExecutor() as executor:
            success = True
            futures = [
                executor.submit(server.notify, **kwargs)
                for (server, kwargs) in servers_kwargs
            ]

            for future in cf.as_completed(futures):
                try:
                    result = future.result()
                    success = success and result

                except TypeError:
                    # These are our internally thrown notifications.
                    success = False

                except Exception:
                    # A catch all so we don't have to abort early
                    # just because one of our plugins has a bug in it.
                    logger.exception("Unhandled Notification Exception")
                    success = False

            return success

    @staticmethod
    async def _notify_parallel_asyncio(*servers_kwargs):
        """Process a list of async_notify() calls in parallel and
        asynchronously."""

        n_calls = len(servers_kwargs)

        # 0-length case
        if n_calls == 0:
            return True

        # (Unlike with the thread pool, we don't optimize for the single-
        # notification case because asyncio can do useful work while waiting
        # for that thread to complete)

        # Create log entry
        logger.info(
            "Notifying %d service(s) asynchronously.", len(servers_kwargs)
        )

        async def do_call(server, kwargs):
            return await server.async_notify(**kwargs)

        cors = (do_call(server, kwargs) for (server, kwargs) in servers_kwargs)
        results = await asyncio.gather(*cors, return_exceptions=True)

        if any(
            isinstance(status, Exception) and not isinstance(status, TypeError)
            for status in results
        ):
            # A catch all so we don't have to abort early just because
            # one of our plugins has a bug in it.
            logger.exception("Unhandled Notification Exception")
            return False

        if any(isinstance(status, TypeError) for status in results):
            # These are our internally thrown notifications.
            return False

        return all(results)

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
            content.update({
                "protocols": protocols,
                "secure_protocols": secure_protocols,
            })

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
                for _s in s.servers():
                    urls.append(_s.url(privacy=privacy))
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
                        return servers[(
                            index
                            if prev_offset == -1
                            else (index - prev_offset - 1)
                        )]

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
            location if isinstance(location, ContentLocation)
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
        return chain(*[
            (
                [s]
                if not isinstance(s, (ConfigBase, AppriseConfig))
                else iter(s.servers())
            )
            for s in self.servers
        ])

    def __len__(self) -> int:
        """Returns the number of servers loaded; this includes those found
        within loaded configuration.

        This funtion nnever actually counts the Config entry themselves (if
        they exist), only what they contain.
        """
        return sum([
            (
                1
                if not isinstance(s, (ConfigBase, AppriseConfig))
                else len(s.servers())
            )
            for s in self.servers
        ])
