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
    TemplatePlaceholderMap,
    TemplateSchema,
)

# Grab a pointer to our Notification Manager Singleton
N_MGR = NotificationManager()

# Assembling a URL escapes the ${NAME} markers along with everything
# else.  This puts them back so they stay readable on screen.
ESCAPED_VAR_RE = re.compile(
    r"%24%7B(?P<name>[A-Za-z0-9_]{1,32})%7D",
    re.IGNORECASE,
)

# Reuse up to this many built services while keeping cache growth bounded.
MAX_RESOLVE_CACHE = 32


def _readable_var(match: re.Match) -> str:
    """Turn an escaped ``%24%7BNAME%7D`` back into ``${NAME}``."""
    # Keep the spelling captured from the assembled URL.
    return "${{{}}}".format(match.group("name"))


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
        """The ones with no default, so they must be supplied."""
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

    def url(self, privacy: bool = False, *args, **kwargs) -> str:
        """Show the pending URL, masking possible secrets when requested."""

        # Read the stable parsed fields without changing the pending entry.
        results = self.results
        schema = results.get("schema", "")
        http = schema.startswith("http")

        # Track which placeholders the URL itself already shows, so the
        # same one is not listed twice.
        shown = set()
        for key in ("user", "password", "host", "fullpath"):
            value = results.get(key)
            if isinstance(value, str):
                shown.update(self.placeholders.pattern.findall(value))

        # Prepare the query values already present in the source URL.
        qsd = {}
        for key, value in (results.get("qsd") or {}).items():
            qsd[key] = self._present(
                value, privacy, force=key in self.SECRET_KEYS
            )
            # A query value always arrives as text from the URL parser.
            shown.update(self.placeholders.pattern.findall(value))

        # Add templated YAML settings that are not already visible in the URL.
        for key, value in sorted(results.items()):
            if key in self.STRUCTURAL_KEYS or key in qsd:
                continue

            if not isinstance(value, str):
                continue

            found = self.placeholders.pattern.findall(value)
            if found and not set(found).issubset(shown):
                shown.update(found)
                qsd[key] = self._present(
                    value, privacy, force=key in self.SECRET_KEYS
                )

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
            _readable_var,
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
                port=results.get("port"),
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

        Returns the service, or None when it could not be built.  The
        reason is logged locally.
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
