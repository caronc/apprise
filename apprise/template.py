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
"""Represent a YAML configuration entry awaiting template values.

The entry keeps its parsed fields and tags until caller, environment, or
default values are available. It can then build the notification service.
"""

from __future__ import annotations

from collections import OrderedDict
import hashlib
import re
import threading
from typing import Any, Optional

from .logger import logger
from .manager_plugins import NotificationManager
from .tag import AppriseTag
from .utils.cwe312 import cwe312_word
from .utils.parse import parse_list, url_assembly
from .utils.template import (
    MAX_RESOLVED_URL_LEN,
    TEMPLATE_NAME_PATTERN,
    TemplatePlaceholderMap,
    TemplateSchema,
)

# Grab a pointer to our Notification Manager Singleton
N_MGR = NotificationManager()

# Assembling a URL escapes the ${NAME} markers along with everything
# else. Restore the markers so callers can see and replace them.
ESCAPED_VAR_RE = re.compile(
    r"%24%7B(?P<name>" + TEMPLATE_NAME_PATTERN + r")%7D",
    re.IGNORECASE,
)

# How far a nested list setting is followed before it is left alone.
# This limits nesting; it does not cap the total number of list members.
MAX_LIST_DEPTH = 8

# Reuse up to this many built services while keeping cache growth bounded.
MAX_RESOLVE_CACHE = 32

# One reverse lookup per service, built the first time it is needed.
URL_ARGS_CACHE = {}


def _flatten(value: Any, depth: int = 0) -> Optional[list]:
    """Read a nested list, tuple, or set as one list of text members.

    YAML may wrap a service setting in extra lists; the URL needs its members
    together. ``depth`` tracks nesting. Return ``None`` for non-text members
    or when the nesting limit is exceeded.
    """

    if depth > MAX_LIST_DEPTH:
        # Stop at the depth limit, including for lists that contain themselves.
        return None

    # A set has no stable order. Its members are sorted at the end,
    # once each one is known to be text. Mixed types cannot be compared.
    members = []
    for member in value:
        if isinstance(member, (list, tuple, set)):
            # Fold each nested collection into this same list.
            nested = _flatten(member, depth + 1)
            if nested is None:
                # One unusable member makes the whole URL setting unusable.
                return None

            members.extend(nested)
            continue

        if not isinstance(member, str):
            # Numbers and flags cannot contain a template marker.
            return None

        # Keep ordinary text too; a list may mix fixed and templated values.
        members.append(member)

    # Now that every member is text, a set can be ordered safely.
    return sorted(members) if isinstance(value, set) else members


def _destination(details: dict, arg: str) -> str:
    """Find the service field set by a URL argument or one of its aliases.

    For example, ``smtp=`` in a URL sets the service's ``smtp_host`` field.
    """

    # The plugin describes both its URL arguments and its constructor fields.
    meta = details["args"][arg]
    map_to = meta.get("alias_of", meta.get("map_to", ""))
    if not map_to or map_to == arg:
        # The argument fills in the field of the same name.
        return arg

    # Follow aliases to the field they ultimately set.
    if map_to in details["tokens"]:
        # A token entry can provide another mapping for the same argument.
        target = details["tokens"][map_to]

    else:
        # Otherwise, follow the destination through the argument list.
        target = details["args"].get(map_to, meta)

    return target.get("map_to", map_to)


def _url_args(plugin: Any) -> tuple:
    """Relate a service's fields and the URL arguments that set them.

    YAML may store a field as ``smtp_host`` while its URL uses ``smtp=``.
    Returns two lookups: one from a field to the argument that sets it, and
    one from an argument back to the field it fills.  Several arguments can
    share a field, so the second is needed to spot a query entry the
    configuration has since overridden.
    """

    if plugin is None:
        # No plugin means there are no service-specific URL arguments.
        return {}, {}

    if plugin in URL_ARGS_CACHE:
        # Plugin argument names do not change between entries.
        return URL_ARGS_CACHE[plugin]

    # Imported here because the plugin package loads this module.
    from . import plugins

    to_arg, to_field = {}, {}
    try:
        # Describe each argument once in both directions.
        details = plugins.details(plugin)
        for arg in details["args"]:
            field = _destination(details, arg)
            # This direction identifies old query spellings to replace.
            to_field[arg] = field
            if field == arg:
                # Prefer the field's own argument over an alias.
                to_arg[arg] = arg

            else:
                # Keep the first usable alias unless the field's own name wins.
                to_arg.setdefault(field, arg)

    except Exception:
        # A service we cannot describe simply gets no translation.
        to_arg, to_field = {}, {}

    # Reuse the completed pair for every entry of this service.
    URL_ARGS_CACHE[plugin] = (to_arg, to_field)
    return to_arg, to_field


class NotifyTemplate:
    """A configuration entry awaiting one or more template values."""

    # Parts of a parsed URL that are rebuilt directly, plus internal
    # bookkeeping.  Anything else holding a placeholder came from a
    # YAML setting and is shown as a query parameter instead.
    STRUCTURAL_KEYS = frozenset(
        (
            "asset",
            "fullpath",
            "host",
            "password",
            "path",
            "port",
            "qsd",
            "qsd+",
            "qsd-",
            "qsd:",
            "query",
            "schema",
            "secure",
            "tag",
            "url",
            "user",
            "verify",
        )
    )

    # Query string names whose value is always treated as a secret.
    # Kept in step with the masking done for regular URLs.
    SECRET_KEYS = (
        "password",
        "secret",
        "pass",
        "token",
        "key",
        "id",
        "apikey",
        "to",
    )

    def __init__(
        self,
        results: dict,
        placeholders: TemplatePlaceholderMap,
        schema: TemplateSchema,
        names: set,
        settings: Optional[dict] = None,
        asset: Any = None,
        entry: Optional[int] = None,
        item: Optional[int] = None,
    ):
        """Keep one parsed entry ready for its missing template values."""
        # Keep the parsed URL with placeholders still sitting in it.
        self.results = results

        # Retain the map that swaps placeholders for supplied values.
        self.placeholders = placeholders

        # Keep every variable declared by this configuration.
        self.template_schema = schema

        # Narrow that declaration list to the names used by this entry.
        self.names = set(names)

        # Remember YAML names before aliases map them to parsed fields;
        # both from and name can feed from_addr.
        self.settings = dict(settings) if settings else {}

        # Share the caller's asset settings with the eventual service.
        self.asset = asset

        # Remember the YAML location for useful log messages.
        self.entry = entry
        self.item = item

        # Store tags in the same form used by a fully built service.
        self.tags = {
            AppriseTag.parse(t) for t in parse_list(results.get("tag"))
        }

        # Cache a small number of resolved services for repeated sends.
        self._cache = OrderedDict()

        # Protect cache reads and writes when notifications run in parallel.
        self._lock = threading.Lock()

    @property
    def schema(self) -> str:
        """Return the notification service schema."""
        return self.results.get("schema", "")

    @property
    def _plugin(self) -> Any:
        """The service class behind this entry, if we know it."""
        if self.schema not in N_MGR:
            return None

        return N_MGR[self.schema]

    @property
    def service_name(self) -> Optional[str]:
        """Return the friendly service name when the plugin is known."""
        return getattr(self._plugin, "service_name", None)

    @property
    def enabled(self) -> bool:
        """Report whether the underlying plugin is available."""
        return getattr(self._plugin, "enabled", True)

    @property
    def retry(self) -> Any:
        """Expose the pending entry's retry setting."""
        return self.results.get("retry", 0)

    @property
    def optional(self) -> Any:
        """Expose whether a failed notification may be ignored."""
        return self.results.get("optional")

    @property
    def template_names(self) -> tuple:
        """The variables this entry needs, in a stable order."""
        return tuple(sorted(self.names))

    @property
    def template_required(self) -> tuple:
        """Names with no default; the call or environment fills them."""
        return tuple(
            sorted(
                name
                for name in self.names
                if self.template_schema.variables[name].required
            )
        )

    def url_id(self, *args, **kwargs) -> None:
        """No identifier exists until the real service is built."""
        return None

    def _present(self, value: Any, privacy: bool, **kwargs) -> Any:
        """Restore variable names for display and mask nearby real values."""

        if not isinstance(value, str) or not value:
            return value

        if not privacy:
            return self.placeholders.display(value)

        # Build a display value one literal and placeholder at a time.
        parts = []
        position = 0
        for match in self.placeholders.pattern.finditer(value):
            literal = value[position : match.start()]
            if literal:
                # Text next to a placeholder could be anything, so it
                # is always masked.
                parts.append(cwe312_word(literal, force=True))

            # Variable names are safe to show and help explain what is needed.
            parts.append(self.placeholders.display(match.group(0)))
            position = match.end()

        if not parts:
            # Nothing templated here; mask it the usual way
            return cwe312_word(value, **kwargs)

        # Mask any literal text left after the final placeholder.
        literal = value[position:]
        if literal:
            parts.append(cwe312_word(literal, force=True))

        return "".join(parts)

    def _query_value(
        self, value: Any, privacy: bool, secret: bool
    ) -> Optional[str]:
        """Render a YAML setting as the text a URL argument carries.

        Every setting is written out, not only the ones holding a marker,
        so the listed URL reloads into the configuration it came from.
        ``privacy`` masks stored text; ``secret`` forces masking around a
        marker. Return ``None`` for a value no URL argument can carry.
        """

        if isinstance(value, bool):
            # Checked before int, which bool is a kind of.
            return "yes" if value else "no"

        if isinstance(value, str):
            # Plain text needs no list handling.
            return self._present(value, privacy, force=secret)

        if isinstance(value, (int, float)):
            # A number holds no marker, but the URL still has to carry it.
            return str(value)

        if isinstance(value, (list, tuple, set)):
            # A field the service reads as a list is written back the way a
            # URL supplies one: a single separated value.
            members = _flatten(value)
            if not members:
                # An empty or unusable list has nothing to say.
                return None

            # Keep fixed members beside any marker in the same argument.
            # Return a comma separated list
            return ",".join(
                [
                    self._present(member, privacy, force=secret)
                    for member in members
                ]
            )

        # A grouped dictionary is handled separately, and nothing else fits.
        return None

    def _grouped_query(self, privacy: bool, qsd: dict) -> None:
        """Show grouped settings, such as headers, with their URL prefixes.

        A header written under the URL replaces the one the URL itself
        carried, matching the order the configuration applies them in.
        Each stored member keeps the prefix the URL uses for its group.
        """

        groups = getattr(self._plugin, "template_kwargs", None) or {}

        for field, meta in groups.items():
            # A plugin may collect headers or payload fields into a dictionary.
            entries = self.results.get(field)
            if not isinstance(entries, dict) or not entries:
                # This group holds nothing, so the URL's own entries are
                # left exactly as they were.
                continue

            # Writing any of these under a URL replaces the whole group
            # rather than adding to it, so the stored group is the
            # complete list and the URL's spellings give way to it.
            prefix = meta.get("prefix", "+")
            for spelling in [k for k in qsd if k.startswith(prefix)]:
                # Remove URL members of the replaced group.
                del qsd[spelling]

            for name, value in entries.items():
                if isinstance(name, str):
                    # Put each stored member back under its URL prefix.
                    qsd[prefix + name] = self._present(value, privacy)

    def _settable(self, key: str) -> bool:
        """Report whether a URL can carry a setting of this name.

        Only options accepted by the service's URL arguments or grouped
        options belong in a listed URL. Unsupported YAML settings were
        ignored before and would be ignored when that URL reloads.
        """

        plugin = self._plugin
        if plugin is None:
            return False

        groups = getattr(plugin, "template_kwargs", None) or {}
        for meta in groups.values():
            # Grouped URL options, such as headers, use a shared prefix.
            if key.startswith(meta.get("prefix", "+")):
                return True

        # Ordinary options must have their own URL argument.
        return key in (getattr(plugin, "template_args", None) or {})

    def _readable_var(self, match: re.Match) -> str:
        """Turn an escaped ``%24%7BNAME%7D`` back into ``${NAME}``.

        Declared names can be filled; undeclared ones stay literal. Showing
        both helps an author spot a missing declaration. The URL reads the
        same either way because URL parsing decodes the escaped marker.
        """

        # Keep the spelling captured from the assembled URL.
        return "${{{}}}".format(match.group("name"))

    def url(self, privacy: bool = False, *args, **kwargs) -> str:
        """Show the pending URL with every unresolved marker in place.

        ``privacy`` masks stored secrets, while ``${NAME}`` stays readable so
        callers can supply the missing values. YAML settings appear under
        the URL arguments that the service actually accepts.
        """

        # Read the stable parsed fields without changing the pending entry.
        results = self.results
        schema = results.get("schema", "")
        http = schema.startswith("http")

        # Prepare the query values already present in the source URL.
        qsd = {}
        for key, value in (results.get("qsd") or {}).items():
            # Preserve URL query entries unless a YAML setting replaces them.
            qsd[key] = self._present(
                value, privacy, force=key in self.SECRET_KEYS
            )

        # Settings gathered into a group, such as headers, come next.
        self._grouped_query(privacy, qsd)

        # List the YAML settings under their written names; two names can
        # feed one field, so the parsed field name is not enough.  The
        # second lookup relates each name to the field it fills.
        _, to_field = _url_args(self._plugin)

        def field_of(name: str) -> str:
            """The field a name fills, or the name when nothing maps it."""
            return to_field.get(name) or name

        # Several names can fill one field, and the configuration applies
        # them in the order they are written, so the last one wins.
        winner = {}
        for key in self.settings:
            if self._settable(key):
                # A later name for this field replaces the earlier one.
                winner[field_of(key)] = key

        for key, value in sorted(self.settings.items()):
            if not self._settable(key):
                # Not something a URL can say, so writing it would invent
                # a parameter the service never reads back.
                continue

            field = field_of(key)
            if winner[field] != key:
                # A later setting fills this field instead of this one.
                continue

            rendered = self._query_value(
                value, privacy, secret=key in self.SECRET_KEYS
            )
            if rendered is None:
                # Nothing a URL argument can carry, so leave it out.
                continue

            # A setting written under the URL wins over the URL's own query
            # string, so drop every spelling of the field the URL carried
            # and list the winner once.
            for spelling in [
                name for name in qsd if name != key and field_of(name) == field
            ]:
                # The YAML value wins over this alias in the URL.
                del qsd[spelling]

            qsd[key] = rendered

        # Present each path segment separately so URL assembly stays valid.
        fullpath = results.get("fullpath") or ""
        if fullpath:
            fullpath = "/" + "/".join(
                [
                    self._present(segment, privacy)
                    for segment in fullpath.lstrip("/").split("/")
                ]
            )

        # Assemble the familiar URL form, then restore readable markers.
        return ESCAPED_VAR_RE.sub(
            self._readable_var,
            url_assembly(
                schema=schema,
                user=self._present(
                    results.get("user"), privacy, advanced=not http
                ),
                password=self._present(
                    results.get("password"), privacy, force=True
                ),
                host=self._present(
                    results.get("host"), privacy, advanced=not http
                ),
                # A port can be waiting on a value too; show the marker
                # rather than the internal token standing in for it.
                port=self._present(results.get("port"), privacy),
                fullpath=fullpath,
                qsd=qsd,
            ),
        )

    def __str__(self) -> str:
        """Show a privacy-safe version of the pending URL."""
        return self.url(privacy=True)

    def __repr__(self) -> str:
        """Summarize the service and values it still needs."""
        return "<NotifyTemplate {} needs={}>".format(
            self.schema, ",".join(self.template_names)
        )

    def _cache_key(self, values: dict) -> str:
        """Hash resolved values so cache keys never expose secrets."""
        # Include both names and values in a stable, unambiguous order.
        engine = hashlib.sha256()
        for name in sorted(values):
            engine.update(name.encode("utf-8"))
            engine.update(b"\0")
            engine.update(values[name].encode("utf-8"))
            engine.update(b"\0")

        return engine.hexdigest()

    def resolve(self, values: dict) -> Any:
        """Build the real service using the values handed in.

        Returns the service, or ``None`` after logging why it could not be
        built.
        """

        # Reuse a previously built service when all supplied values match.
        key = self._cache_key(values)
        with self._lock:
            if key in self._cache:
                # Hand back the same object as last time so anything it
                # remembers between calls is kept
                self._cache.move_to_end(key)
                return self._cache[key]

        # Work on a shallow copy so the pending template remains reusable.
        results = dict(self.results)

        # Share the asset and tags so persistent storage continues to work.
        asset = results.pop("asset", None)
        tag = results.pop("tag", None)

        # Replace every placeholder before handing fields to the plugin.
        try:
            results = self.placeholders.substitute(results, values)

        except Exception as e:
            logger.error(
                "Could not apply template variables to %s://", self.schema
            )
            logger.debug("Template Exception: %s", e)
            return None

        # Put non-templated shared objects back into the constructor fields.
        results["asset"] = asset
        results["tag"] = tag

        # Refuse unusually large assembled URLs before building a service.
        url = results.get("url")
        if isinstance(url, str) and len(url) > MAX_RESOLVED_URL_LEN:
            logger.error(
                "A template built an over-sized %s:// URL", self.schema
            )
            return None

        # Let the normal plugin constructor perform service-specific checks.
        try:
            plugin = N_MGR[results["schema"]](**results)

        except Exception as e:
            logger.error(
                "Could not load %s:// once template variables were applied",
                self.schema,
            )
            logger.debug("Loading Exception: %s", e)
            return None

        # Remember the service and discard the oldest when the cache fills.
        with self._lock:
            self._cache[key] = plugin
            self._cache.move_to_end(key)
            while len(self._cache) > MAX_RESOLVE_CACHE:
                self._cache.popitem(last=False)

        return plugin
