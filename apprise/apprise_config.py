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

from typing import TYPE_CHECKING, Any

from . import common
from .asset import AppriseAsset
from .config.base import ConfigBase
from .logger import logger
from .manager_config import ConfigurationManager
from .url import URLBase
from .utils.cwe312 import cwe312_url
from .utils.logic import is_exclusive_match
from .utils.parse import GET_SCHEMA_RE, parse_list

if TYPE_CHECKING:
    from .plugins.base import NotifyBase

# Grant access to our Configuration Manager Singleton
C_MGR = ConfigurationManager()


class AppriseConfig:
    """Manage the configuration sources from which services are discovered.

    Apprise supports a simple text format containing service URLs and a richer
    YAML format. Sources may be local files, remote URLs, in-memory content, or
    any other registered configuration plugin.

    See https://appriseit.com/getting-started/configuration/ for the supported
    file formats and examples.
    """

    def __init__(
        self,
        paths: str | list[str] | None = None,
        asset: AppriseAsset | None = None,
        cache: bool | int = True,
        recursion: int = 0,
        insecure_includes: bool = False,
        **kwargs: Any,
    ) -> None:
        """Initialize the manager and optionally add configuration sources.

        ``paths`` may be one source string or a list of source strings. A
        source can be an explicit configuration URL such as ``file://`` or
        ``https://``; a path without a scheme is treated as a local file. If
        ``paths`` is omitted, the manager starts empty. Default configuration
        locations are selected by higher-level callers such as the CLI, not by
        this class.

        ``asset`` is shared with configuration plugins and with the services
        they create. ``cache`` controls whether a source is read again: true
        retains parsed results, false reloads on each request, and an integer
        gives the cache lifetime in seconds. Caching matters most for remote
        sources, where reloading requires another network request.

        ``recursion`` is the number of nested ``include`` levels to follow.
        Zero disables includes, one loads sources named by the top-level
        configuration, and larger values allow the included sources to include
        others. Keep this value low when loading content you do not control.

        Configuration plugins declare whether they may be included from other
        source types. In strict mode, a local ``file://`` source may include
        another local file, but a remote ``http://`` or ``https://`` source may
        not reach into the local filesystem. ``insecure_includes=True`` relaxes
        this strict same-type boundary; it does not override sources that
        prohibit inclusion entirely. This option is also required when trusted
        in-memory configuration must include local files.

        See https://appriseit.com/getting-started/configuration/ for the
        configuration syntax and include examples.
        """

        # Store the configuration sources used to discover services.
        self.configs = []

        # Prepare our Asset Object
        self.asset = (
            asset if isinstance(asset, AppriseAsset) else AppriseAsset()
        )

        # Set our cache flag
        self.cache = cache

        # Initialize our recursion value
        self.recursion = recursion

        # Initialize our insecure_includes flag
        self.insecure_includes = insecure_includes

        if paths is not None:
            # Store our path(s)
            self.add(paths)

        return

    def add(
        self,
        configs: str | ConfigBase | list[str | ConfigBase],
        asset: AppriseAsset | None = None,
        tag: str | list[str] | None = None,
        cache: bool | int = True,
        recursion: int | None = None,
        insecure_includes: bool | None = None,
    ) -> bool:
        """Add one or more configuration sources to the manager.

        ``configs`` accepts a source string, an instantiated
        :class:`ConfigBase`, or a collection containing either. Strings without
        a URL scheme are treated as local file paths. ``tag`` is attached to
        newly created configuration sources and can later select which sources
        :meth:`services` reads; it does not tag each service found inside.

        ``asset``, ``cache``, ``recursion``, and ``insecure_includes`` are
        passed to sources created from strings. ``asset``, ``recursion``, and
        ``insecure_includes`` fall back to this manager's values when omitted.
        An already instantiated :class:`ConfigBase` retains all of its own
        settings because it is stored directly.

        The cache setting may be true to retain parsed results, false to reload
        whenever services are requested, or a non-negative integer cache
        lifetime in seconds. ``recursion`` limits nested ``include`` entries.
        ``insecure_includes`` relaxes strict cross-source inclusion rules; use
        it only for trusted configuration.

        The return value is true only when every supplied item was accepted.
        Valid sources remain loaded when another item in the same collection
        is invalid.
        """

        # Initialize our return status
        return_status = True

        # Initialize our default cache value
        cache = cache if cache is not None else self.cache

        # Initialize our default recursion value
        recursion = recursion if recursion is not None else self.recursion

        # Initialize our default insecure_includes value
        insecure_includes = (
            insecure_includes
            if insecure_includes is not None
            else self.insecure_includes
        )

        if asset is None:
            # prepare default asset
            asset = self.asset

        if isinstance(configs, ConfigBase):
            # Go ahead and just add our configuration into our list
            self.configs.append(configs)
            return True

        elif isinstance(configs, str):
            # Save our path
            configs = (configs,)

        elif not isinstance(configs, (tuple, set, list)):
            logger.error(
                f"An invalid configuration path (type={type(configs)}) was "
                "specified."
            )
            return False

        # Iterate over our configuration
        for config in configs:
            if isinstance(config, ConfigBase):
                # Go ahead and just add our configuration into our list
                self.configs.append(config)
                continue

            elif not isinstance(config, str):
                logger.warning(
                    f"An invalid configuration (type={type(config)}) was"
                    " specified."
                )
                return_status = False
                continue

            logger.debug(f"Loading configuration: {config}")

            # Instantiate ourselves an object, this function throws or
            # returns None if it fails
            instance = AppriseConfig.instantiate(
                config,
                asset=asset,
                tag=tag,
                cache=cache,
                recursion=recursion,
                insecure_includes=insecure_includes,
            )
            if not isinstance(instance, ConfigBase):
                return_status = False
                continue

            # Keep the initialized configuration source.
            self.configs.append(instance)

        # Return our status
        return return_status

    def add_config(
        self,
        content: str,
        asset: AppriseAsset | None = None,
        tag: str | list[str] | None = None,
        format: str | None = None,
        recursion: int | None = None,
        insecure_includes: bool | None = None,
    ) -> bool:
        """Add raw configuration text as an in-memory source.

        The content exists only for the lifetime of the resulting in-memory
        configuration object. Set ``format`` to ``yaml`` or ``text`` when it is
        known; otherwise Apprise detects the format. The method returns false
        when ``content`` is not a string or its format cannot be determined.

        ``asset`` is passed to services created from the content, while ``tag``
        labels the in-memory configuration source for filtering by
        :meth:`services`. ``recursion`` and ``insecure_includes`` fall back to
        this manager's defaults when omitted. Enable insecure includes only
        when trusted in-memory content must include a source, such as a local
        ``file://`` configuration, that the normal security boundary rejects.
        """

        # Initialize our default recursion value
        recursion = recursion if recursion is not None else self.recursion

        # Initialize our default insecure_includes value
        insecure_includes = (
            insecure_includes
            if insecure_includes is not None
            else self.insecure_includes
        )

        if asset is None:
            # prepare default asset
            asset = self.asset

        if not isinstance(content, str):
            logger.warning(
                f"An invalid configuration (type={type(content)}) was"
                " specified."
            )
            return False

        logger.debug(f"Loading raw configuration: {content}")

        # Create ourselves a ConfigMemory Object to store our configuration
        instance = C_MGR["memory"](
            content=content,
            format=format,
            asset=asset,
            tag=tag,
            recursion=recursion,
            insecure_includes=insecure_includes,
        )

        if not (
            instance.config_format
            and instance.config_format.value in common.CONFIG_FORMATS
        ):
            logger.warning(
                "The format of the configuration could not be detected."
            )
            return False

        # Keep the initialized in-memory configuration source.
        self.configs.append(instance)

        # Return our status
        return True

    def services(
        self,
        tag: str | list[str] = common.MATCH_ALL_TAG,
        match_always: bool = True,
        *args: Any,
        **kwargs: Any,
    ) -> list[NotifyBase]:
        """Read matching configuration sources and return their services.

        ``tag`` is matched against tags on the configuration sources
        themselves, not tags on the services defined inside those sources.
        This lets a caller choose which files or remote locations to poll.
        Top-level tag entries are alternatives (OR), while nested collections
        are intersections (AND).

        When ``match_always`` is true, configuration sources carrying the
        reserved ``always`` tag are read even if the requested filter would not
        otherwise select them. Each matching source applies its own cache,
        recursion, and include-security policy as it builds the returned list.
        """

        # A match_always flag allows us to pick up on our 'any' keyword
        # and notify these services under all circumstances
        match_always = common.MATCH_ALWAYS_TAG if match_always else None

        # Build our tag setup
        #   - top level entries are treated as an 'or'
        #   - second level (or more) entries are treated as 'and'
        #
        #   examples:
        #     tag="tagA, tagB"                = tagA or tagB
        #     tag=['tagA', 'tagB']            = tagA or tagB
        #     tag=[('tagA', 'tagC'), 'tagB']  = (tagA and tagC) or tagB
        #     tag=[('tagB', 'tagC')]          = tagB and tagC

        response = []

        for entry in self.configs:
            # Apply our tag matching based on our defined logic
            if is_exclusive_match(
                logic=tag,
                data=entry.tags,
                match_all=common.MATCH_ALL_TAG,
                match_always=match_always,
            ):
                # Add services discovered in this configuration source.
                response.extend(entry.services())

        return response

    @staticmethod
    def instantiate(
        url: str,
        asset: AppriseAsset | None = None,
        tag: str | list[str] | None = None,
        cache: bool | int | None = None,
        recursion: int = 0,
        insecure_includes: bool = False,
        suppress_exceptions: bool = True,
    ) -> ConfigBase | None:
        """Returns the instance of a instantiated configuration plugin based on
        the provided Config URL.

        If the url fails to be parsed, then None is returned.
        """
        # Attempt to acquire the schema at the very least to allow our
        # configuration based urls.
        schema = GET_SCHEMA_RE.match(url)
        if schema is None:
            # Plan B is to assume we're dealing with a file
            schema = "file"
            url = f"{schema}://{URLBase.quote(url)}"

        else:
            # Ensure our schema is always in lower case
            schema = schema.group("schema").lower()

            # Some basic validation
            if schema not in C_MGR:
                logger.error(f"Unsupported schema {schema}.")
                return None

        # Parse the configuration URL into constructor arguments.
        results = C_MGR[schema].parse_url(url)

        if not results:
            # The configuration URL could not be parsed.
            # CWE-312 (Secure Logging) Handling
            secure_logging = (
                asset.secure_logging
                if isinstance(asset, AppriseAsset)
                else True
            )
            loggable_url = url if not secure_logging else cwe312_url(url)
            logger.error(f"Unparseable URL {loggable_url}.")
            return None

        # Build a list of tags to associate with the newly added notifications
        results["tag"] = set(parse_list(tag))

        # Prepare our Asset Object
        results["asset"] = (
            asset if isinstance(asset, AppriseAsset) else AppriseAsset()
        )

        if cache is not None:
            # Force an over-ride of the cache value to what we have specified
            results["cache"] = cache

        # Recursion can never be parsed from the URL
        results["recursion"] = recursion

        # Insecure includes flag can never be parsed from the URL
        results["insecure_includes"] = insecure_includes

        if suppress_exceptions:
            try:
                # Attempt to create an instance of our plugin using the parsed
                # URL information
                cfg_plugin = C_MGR[results["schema"]](**results)

            except Exception:
                # the arguments are invalid or can not be used.
                # CWE-312 (Secure Logging) Handling
                loggable_url = (
                    url
                    if not results["asset"].secure_logging
                    else cwe312_url(url)
                )
                logger.error(f"Could not load URL: {loggable_url}")
                return None

        else:
            # Attempt to create an instance of our plugin using the parsed
            # URL information but don't wrap it in a try catch
            cfg_plugin = C_MGR[results["schema"]](**results)

        return cfg_plugin

    def clear(self) -> None:
        """Empties our configuration list."""
        self.configs[:] = []

    def service_pop(self, index: int) -> NotifyBase:
        """Remove and return a service from the flattened configuration view.

        The configuration sources remain loaded. ``index`` addresses the
        services discovered across them as one continuous sequence, and an
        out-of-range index raises :class:`IndexError`.
        """

        # Tracking variables
        prev_offset = -1
        offset = prev_offset

        for entry in self.configs:
            services = entry.services(cache=True)
            if len(services) > 0:
                # Acquire a new maximum offset to work with
                offset = prev_offset + len(services)

                if offset >= index:
                    # we can pop an notification from our config stack
                    return entry.pop(
                        index
                        if prev_offset == -1
                        else (index - prev_offset - 1)
                    )

                # Update our old offset
                prev_offset = offset

        # If we reach here, then we indexed out of range
        raise IndexError("list index out of range")

    def pop(self, index: int = -1) -> ConfigBase:
        """Removes an indexed Apprise Configuration from the stack and returns
        it.

        By default, the last element is removed from the list
        """
        # Remove our entry
        return self.configs.pop(index)

    def __getitem__(self, index: int) -> ConfigBase:
        """Returns the indexed config entry of a loaded apprise
        configuration."""
        return self.configs[index]

    def __bool__(self) -> bool:
        """Allows the Apprise object to be wrapped in an 'if statement'.

        True is returned if at least one service has been loaded.
        """
        return bool(self.configs)

    def __iter__(self):  # type: () -> Iterator[ConfigBase]
        """Returns an iterator to our config list."""
        return iter(self.configs)

    def __len__(self) -> int:
        """Returns the number of config entries loaded."""
        return len(self.configs)
