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
"""Turn a notification URL into its fields, and fields back into a URL.

Fields are named after the tokens, arguments and key/value options a
plugin's ``details()`` lists, the same names a URL builder shows. This
lets a form show one URL as separate entries and assemble it again.
"""

from __future__ import annotations

from enum import Enum
import inspect
import re
from typing import Any, Optional

from .asset import AppriseAsset
from .exception import AppriseImproperlyConfigured
from .logger import logger, quiet_logs
from .manager_plugins import NotificationManager
from .plugins import details
from .url import PrivacyMode, URLBase
from .utils.parse import (
    GET_SCHEMA_RE,
    parse_bool,
)

# Grant access to our Notification Manager Singleton
N_MGR = NotificationManager()

# A {name} placeholder inside a URL template
TEMPLATE_TOKEN_RE = re.compile(r"\{(?P<name>[^}]+)\}")


def _empty(value: Any) -> bool:
    """Return whether a value holds nothing worth keeping."""
    # Empty text and empty collections count as nothing, while 0 and
    # False are real values
    return (
        value is None
        or value == ""
        or (isinstance(value, (list, tuple, set, dict)) and not value)
    )


def _typed(value: Any, meta: dict[str, Any]) -> Any:
    """Return a value as the type its template entry describes.

    - Lists come back as lists; text is split on commas.
    - ``None`` comes back for anything that is not plain data.
    - A choice a plugin keeps as an Enum (such as ``NotifyFormat.MARKDOWN``)
      comes back as its plain value (``markdown``), the way a URL writes it.
    """
    if isinstance(value, Enum):
        value = value.value

    kind = meta.get("type", "string")
    if kind.startswith("list"):
        if isinstance(value, set):
            # A set has no order of its own
            value = sorted(value, key=str)

        elif isinstance(value, str):
            value = value.split(",")

        elif not isinstance(value, (list, tuple)):
            # Objects a plugin keeps for itself are not fields
            return None

        # Each entry is read as the list's own type
        item = {"type": kind.split(":", 1)[1] if ":" in kind else "string"}
        found = [_typed(entry, item) for entry in value]
        return [
            entry
            for entry in found
            if not _empty(entry)
            and not (isinstance(entry, str) and not entry.strip())
        ]

    if isinstance(value, (list, tuple, set)):
        # A list read for a text entry is written the way a URL writes it
        value = _text(sorted(value) if isinstance(value, set) else value)

    if not isinstance(value, (str, int, float)):
        # Objects a plugin keeps for itself are not fields
        return None

    if kind.endswith("bool"):
        return parse_bool(value)

    for convert, suffix in ((int, "int"), (float, "float")):
        if kind.endswith(suffix) and not isinstance(value, bool):
            try:
                return convert(value)

            except ValueError:
                # Keep what was written when it is not a number
                return value

    return value if isinstance(value, str) else str(value)


def _fits(value: Any, meta: dict[str, Any], kwarg: bool = False) -> bool:
    """Return whether a field value has the shape its template entry allows.

    - A key/value option is a map of names to plain values.
    - A list is one plain value or a flat list of them.
    - Anything else is one plain value: text, a number or True/False.
    """
    # True/False count as numbers here, so they are plain values too
    plain = (str, int, float)
    if kwarg:
        return isinstance(value, dict) and all(
            isinstance(key, str) and isinstance(entry, plain)
            for key, entry in value.items()
        )

    listed = meta.get("type", "").startswith("list")
    if listed and isinstance(value, (list, tuple)):
        return all(isinstance(entry, plain) for entry in value)

    return isinstance(value, plain)


def _hidden(value: Any) -> Any:
    """Return a value with its text masked."""
    if isinstance(value, list):
        return [_hidden(entry) for entry in value]

    if isinstance(value, dict):
        # A key/value map keeps its keys
        return {key: _hidden(entry) for key, entry in value.items()}

    # Numbers and on/off switches hold no secrets
    return (
        URLBase.pprint(value, privacy=True, mode=PrivacyMode.Secret)
        if isinstance(value, str)
        else value
    )


def url_fields(plugin: Any, privacy: bool = False) -> dict[str, Any]:
    """Return a loaded plugin's URL as fields named the way details() does.

    - ``schema`` is always given; empty values are left out.
    - An argument that is only another name for an entry (``alias_of``) is
      folded into that entry, such as ``to`` into ``targets``.
    - Key/value options come back as one map each, such as ``headers``.
    - ``privacy`` masks every entry marked private, and any other text
      that ``url(privacy=True)`` does not show.
    """
    # Read our own URL back; aliases and defaults are folded in by now
    results = plugin.parse_url(plugin.url().replace("/#", "/%23")) or {}
    fields = _fields(type(plugin), results)
    return hide_fields(plugin, fields) if privacy else fields


def hide_fields(plugin: Any, fields: dict[str, Any]) -> dict[str, Any]:
    """Return a masked copy of the fields url_fields(plugin) gave.

    - The result is what ``url_fields(plugin, privacy=True)`` returns.
    - Entries marked private are always masked.
    - Any other text that ``plugin.url(privacy=True)`` does not show is
      masked too, including entries in lists and key/value maps.
    - ``schema``, numbers and on/off switches are never masked.
    """
    info = details(type(plugin))
    tokens = info["tokens"]
    shown = plugin.url(privacy=True)
    shown = (shown, URLBase.unquote(shown))

    def hide(value: Any) -> Any:
        """Return a value masked wherever the privacy URL hides it."""
        # Each entry of a list or key/value map is checked on its own
        if isinstance(value, list):
            return [hide(entry) for entry in value]

        if isinstance(value, dict):
            return {key: hide(entry) for key, entry in value.items()}

        # Text the privacy URL shows (as is or quoted) is kept
        if not isinstance(value, str) or any(
            text in url
            for url in shown
            for text in (value, URLBase.quote(value, safe=""))
        ):
            return value

        return _hidden(value)

    # A value is private when any token that sets it is (a private
    # channel token makes the list of targets it belongs to private)
    secret = {
        meta["map_to"]
        for meta in tokens.values()
        if meta.get("private") and "map_to" in meta
    }

    hidden: dict[str, Any] = {}
    for name, value in fields.items():
        meta = _entry(name, info)
        if name == "schema":
            hidden[name] = value

        elif meta.get("private") or meta.get("map_to") in secret:
            hidden[name] = _hidden(value)

        else:
            hidden[name] = hide(value)

    return hidden


def parse_fields(url: str, privacy: bool = False) -> dict[str, Any]:
    """Return the fields a URL holds, even one its service would not load.

    - Useful for showing what was typed so far, such as ``mailto://`` with
      nothing after it.
    - Returns an empty dict when the schema is unknown or disabled, or the
      URL can't be read at all.
    - ``privacy`` masks all text but the schema and values picked from a
      list of choices, since such a URL has no privacy URL to compare to.
    """
    # Only a known service that is turned on can read the URL
    found = GET_SCHEMA_RE.match(url) if isinstance(url, str) else None
    schema = found.group("schema").lower() if found else ""
    if schema not in N_MGR or not N_MGR[schema].enabled:
        return {}

    results = N_MGR[schema].parse_url(url.replace("/#", "/%23")) or {}
    return _fields(N_MGR[schema], results, privacy)


def _fields(
    plugin: Any, results: dict, privacy: bool = False
) -> dict[str, Any]:
    """Return parse_url() results as fields named the way details() does."""
    if not results.get("schema"):
        # The URL could not be read at all
        return {}

    info = details(plugin)
    tokens, args, kwargs = info["tokens"], info["args"], info["kwargs"]

    # The user and password are still quoted; plugins unquote them later
    for key in ("user", "password"):
        if isinstance(results.get(key), str):
            results[key] = URLBase.unquote(results[key])

    # Several tokens can set the same value (target_user and target_channel
    # both feed targets); the list that groups them speaks for all of them
    owners: dict[str, str] = {}
    for name, meta in tokens.items():
        if name == "schema" or "alias_of" in meta:
            continue

        owner = owners.get(meta["map_to"])
        if owner is None or ("group" in meta and "group" not in tokens[owner]):
            owners[meta["map_to"]] = name

    fields: dict[str, Any] = {"schema": results["schema"]}

    # The template entry each field was read from
    entries: dict[str, dict] = {}
    for key, name in owners.items():
        meta = tokens[name]
        value = results.get(key)
        if (
            _empty(value)
            and meta["type"] == "email"
            and results.get("user")
            and results.get("host")
        ):
            # An email written in front of the path is read as user@host
            value = "{}@{}".format(results["user"], results["host"])

        if key == "fullpath" and not str(value).strip("/"):
            # A lone slash is no path at all
            value = None

        value = _typed(value, meta)
        if not _empty(value):
            fields[name], entries[name] = value, meta

    # The values the tokens above already hold
    held = {tokens[name]["map_to"] for name in fields if name in tokens}

    # Arguments are read from what parse_url() made of them
    for name, meta in args.items():
        if "alias_of" in meta or name in fields or meta["map_to"] in held:
            continue

        value = _typed(results.get(meta["map_to"]), meta)
        if not _empty(value):
            fields[name], entries[name] = value, meta
            held.add(meta["map_to"])

    # Key/value options each have their own prefix (+, - or :)
    for name, meta in kwargs.items():
        found = results.get("qsd" + meta.get("prefix", "+"))
        if found:
            fields[name], entries[name] = dict(found), meta

    if privacy:
        # Only a value picked from a fixed list of choices is safe to show
        for name, meta in entries.items():
            if not meta.get("type", "").startswith("choice"):
                fields[name] = _hidden(fields[name])

    return fields


def _text(value: Any) -> str:
    """Return a value as it is written in a URL, before quoting."""
    if isinstance(value, bool):
        return "yes" if value else "no"

    if isinstance(value, float) and value.is_integer():
        # 15.0 is written 15, the way it is usually typed
        return str(int(value))

    if isinstance(value, (list, tuple, set)):
        return ",".join(_text(entry) for entry in value)

    return str(value)


def _alias_targets(entry: dict[str, Any]) -> tuple[str, ...]:
    """Return the names referenced by an alias entry."""
    targets = entry.get("alias_of")
    if isinstance(targets, str):
        # An alias for one entry, such as ?to= for targets
        return (targets,)

    if isinstance(targets, (list, tuple)):
        # An alias for several entries; the plugin decides which one a
        # value belongs to
        return tuple(target for target in targets if isinstance(target, str))

    # Not an alias at all
    return ()


def _entry(name: str, info: dict[str, Any]) -> dict[str, Any]:
    """Return a field's metadata."""
    # A name is looked up as a token first, then an argument, then a
    # key/value option; an unknown name has no metadata at all
    return (
        info["tokens"].get(name)
        or info["args"].get(name)
        or info["kwargs"].get(name)
        or {}
    )


def _parsed(
    plugin: Any, schema: str, options: list[tuple[str, Any]]
) -> dict[str, Any]:
    """Return what the plugin reads from a URL holding only these options."""
    # Each option is written as name=value, both quoted, just as a person
    # would type them after the ?
    query = "&".join(
        "{}={}".format(
            URLBase.quote(name, safe=""), URLBase.quote(_text(value), safe="")
        )
        for name, value in options
    )
    # The plugin may warn about values it doesn't like; those warnings are
    # not meant for whoever is filling in the fields
    with quiet_logs():
        return plugin.parse_url("{}://?{}".format(schema, query)) or {}


def _aliased(
    name: str, value: Any, plugin: Any, schema: str, info: dict[str, Any]
) -> dict[str, Any]:
    """Map a field value to its destination names.

    - Direct fields and single aliases map without parsing.
    - The plugin parser resolves aliases with several destinations.
    """
    targets = _alias_targets(_entry(name, info))
    if not targets:
        # Not an alias; the value stays under its own name
        return {name: value}

    if len(targets) == 1:
        # An alias for one entry passes its value straight to it
        return {targets[0]: value}

    # An alias for several entries: let the plugin read it, then keep each
    # entry the plugin filled in
    results = _parsed(plugin, schema, [(name, value)])
    filled = {}
    for target in targets:
        found = results.get(_entry(target, info).get("map_to", target))
        if not _empty(found):
            filled[target] = found

    # When the plugin could not read it, the first entry takes the value
    return filled or {targets[0]: value}


def _as_list(value: Any) -> list[Any]:
    """Return a value as a list of entries (text is split on commas)."""
    if isinstance(value, str):
        # Empty entries (such as from "a,,b" or a trailing comma) are dropped
        return [entry for entry in value.split(",") if entry.strip()]

    if isinstance(value, (list, tuple, set)):
        # Already several entries
        return list(value)

    # A single value becomes a list of one
    return [value]


def _defaults(plugin: Any) -> dict[str, None]:
    """Return required constructor arguments initialized to ``None``.

    - A plugin may require an argument its URL always provides; giving it
      ``None`` lets the plugin refuse it the usual way instead of Python
      failing on the missing argument.
    """
    # Every plugin is a NotifyBase class with an __init__() of its own,
    # so its signature can always be read
    parameters = inspect.signature(plugin.__init__).parameters.values()

    # Keep the arguments that have no default value of their own
    return {
        parameter.name: None
        for parameter in parameters
        if parameter.name != "self"
        and parameter.default is parameter.empty
        and parameter.kind is parameter.POSITIONAL_OR_KEYWORD
    }


def fields_to_url(fields: dict[str, Any]) -> Optional[str]:
    """Build a plugin URL from its described fields.

    - Reject unknown schemas, fields, and value shapes.
    - Let the plugin validate and serialize the values.
    - Suppress Apprise validation logs and managed file writes.
    - Return ``None`` when the plugin rejects the values.
    """
    schema = fields.get("schema") if isinstance(fields, dict) else None
    if (
        not isinstance(schema, str)
        or schema.lower() not in N_MGR
        or not N_MGR[schema.lower()].enabled
    ):
        logger.warning("Fields must name a supported schema")
        return None

    schema = schema.lower()
    plugin = N_MGR[schema]
    info = details(plugin)
    tokens, args, kwargs = info["tokens"], info["args"], info["kwargs"]

    given = {
        name: value
        for name, value in fields.items()
        if name != "schema" and not _empty(value)
    }
    for name, value in given.items():
        if not isinstance(name, str) or (
            name not in tokens and name not in args and name not in kwargs
        ):
            # The name is shown quoted (%r) so a name holding a line break
            # can't pass itself off as a log entry of its own
            logger.warning("The %s:// field %r is not supported", schema, name)
            return None

        entry = _entry(name, info)
        targets = _alias_targets(entry)
        if targets:
            # An alias has the shape of the item it stands for
            listed = any(
                _entry(target, info).get("type", "").startswith("list")
                for target in targets
            )
            entry = {"type": "list:string" if listed else "string"}

        if not _fits(value, entry, kwarg=name in kwargs and name not in args):
            logger.warning(
                "The %s:// field %s has a value of the wrong type",
                schema,
                name,
            )
            return None

    # The values that gather every entry given for them (such as targets)
    lists = {
        entry.get("map_to", name)
        for name, entry in list(tokens.items()) + list(args.items())
        if entry.get("type", "").startswith("list")
    }

    # Fields are read the way a URL is read, left to right: its path values
    # first, then its query options in the order given. A list gathers every
    # value, and for a single value the later field wins (sender=A then its
    # alias from=B gives B; a query option always wins over a path value).
    # The plugin works out whether the schema is the secure one by itself
    arguments: dict[str, Any] = {"schema": schema}

    # Separate query options that together make one value
    # (?from=me@example.com&name=Me can make "Me <me@example.com>"),
    # combined below by the plugin
    combined: dict[str, list[tuple[str, Any]]] = {}
    in_path = [item for item in given.items() if item[0] not in args]
    in_query = [item for item in given.items() if item[0] in args]
    for name, value in in_path + in_query:
        for target, part in _aliased(
            name, value, plugin, schema, info
        ).items():
            entry = _entry(target, info)
            key = entry.get("map_to", target)
            if name not in kwargs or name in args:
                # Give the plugin the type its entry declares, the way
                # parse_url() would: text for text and True/False for a
                # switch (a form may send "no", or a number for text)
                part = _typed(part, entry)

            prefix = entry.get("prefix")
            if (
                prefix
                and key in lists
                and not entry.get("type", "").startswith("list")
            ):
                # Keep the prefix that marks which kind of list member this
                # is (such as # for a channel)
                part = [
                    text if text.startswith(prefix) else prefix + text
                    for text in map(str, _as_list(part))
                ]

            if key in lists and key in arguments:
                # A list gathers this value along with those before it
                arguments[key] = _as_list(arguments[key]) + _as_list(part)
                continue

            # A single value; a later field replaces an earlier one
            arguments[key] = part
            if name in args and name == target:
                combined.setdefault(key, []).append((name, value))

    for key, options in combined.items():
        if len(options) > 1:
            # Several options make up this one value; the plugin puts them
            # together the way it does when reading a URL
            found = _parsed(plugin, schema, options).get(key)
            if not _empty(found):
                arguments[key] = found

    # Arguments the plugin can't do without, but nobody filled in
    for name, empty in _defaults(plugin).items():
        arguments.setdefault(name, empty)

    # Keep validation quiet, and keep anything Apprise would store in
    # memory so building a URL never writes a file
    arguments["asset"] = AppriseAsset(
        pem_autogen=False, pgp_autogen=False, storage_mode="memory"
    )
    try:
        with quiet_logs():
            obj = plugin(**arguments)

    except AppriseImproperlyConfigured:
        # The plugin refused the values, so there is no URL to give
        logger.debug("The %s:// fields could not be loaded", schema)
        return None

    # The plugin writes its own URL, the same one it gives when loaded
    return obj.url()


def missing_fields(fields: dict[str, Any]) -> list[str]:
    """Return fields missing from the closest matching URL template.

    - Aliases and list members satisfy their shared destination.
    - A field the template can't do without counts, even when it is not
      marked required (see ``needed`` below).
    - Return an empty list for unknown or disabled schemas, or complete
      fields.
    """
    # Only a known service that is turned on can be filled in
    schema = fields.get("schema") if isinstance(fields, dict) else None
    if (
        not isinstance(schema, str)
        or schema.lower() not in N_MGR
        or not N_MGR[schema.lower()].enabled
    ):
        return []

    schema = schema.lower()
    plugin = N_MGR[schema]
    info = details(plugin)
    tokens = info["tokens"]

    # The values the fields already fill in
    given = set()
    for name, value in fields.items():
        if name == "schema" or not isinstance(name, str) or _empty(value):
            # Nothing to fill in (or not a field name at all)
            continue

        # An alias fills in the value it stands for
        for target in _aliased(name, value, plugin, schema, info):
            given.add(_entry(target, info).get("map_to", target))

    # The fields of each template, so a template can be compared with others
    slots = [
        [
            name
            for name in dict.fromkeys(TEMPLATE_TOKEN_RE.findall(template))
            if name != "schema"
        ]
        for template in info["templates"]
    ]
    shapes = {frozenset(names) for names in slots}

    def needed(name: str, names: list[str]) -> bool:
        """Whether a template can't do without a field.

        - A required field with no default is always needed.
        - Another field is needed unless it has a default, or the service
          lists the same template without it (``:{port}``, ``/{targets}``).
          A service listing ``{apikey}@`` or ``{user}:{password}@`` in every
          template needs one of them, although neither is marked required.
        """
        entry = tokens.get(name, {})
        if entry.get("default") is not None:
            # The plugin fills it in by itself
            return False

        if entry.get("required"):
            return True

        # Needed unless the same template is listed without it
        return frozenset(names) - {name} not in shapes

    # The best template so far, as (score, the fields it is missing)
    best = None
    for names in slots:
        values = [tokens.get(name, {}).get("map_to", name) for name in names]
        missing = [
            name
            for name, value in zip(names, values)
            if value not in given and needed(name, names)
        ]
        # How many of the given values this template has a place for
        placed = sum(value in given for value in values)
        if not placed:
            # A template none of the fields fit still needs all of them
            missing = names

        # A lower score is better: a template the fields fit, missing the
        # fewest fields, holding the most values, then the shortest one
        score = (placed == 0, len(missing), -placed, len(names))
        if best is None or score < best[0]:
            best = (score, missing)

    # A service with no templates has nothing to be missing
    return best[1] if best else []
