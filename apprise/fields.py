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

import re
from typing import Any, Optional

from .logger import logger
from .manager_plugins import NotificationManager
from .plugins import details
from .url import PrivacyMode, URLBase
from .utils.parse import (
    GET_SCHEMA_RE,
    URL_SEGMENT_SAFE_CHARS,
    is_email,
    is_ipaddr,
    parse_bool,
)

# Grant access to our Notification Manager Singleton
N_MGR = NotificationManager()

# A {name} placeholder inside a URL template
TEMPLATE_TOKEN_RE = re.compile(r"\{(?P<name>[^}]+)\}")

# Placeholders still in an assembled URL have no value, so they are
# removed along with the separators around them; the rest are left alone.
EMPTY_PLACEHOLDERS = (
    # {user}:{password}@
    (re.compile(r"\{[^}]+\}:\{[^}]+\}@"), ""),
    # user:{password}@
    (re.compile(r":\{[^}]+\}@"), "@"),
    # {user}@
    (re.compile(r"\{[^}]+\}@"), ""),
    # :{port}
    (re.compile(r":\{[^}]+\}"), ""),
    # /{targets}, but never the second slash of schema://
    (re.compile(r"(?<!:/)/\{[^}]+\}"), ""),
    # Anything left over
    (re.compile(r"\{[^}]+\}"), ""),
)


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
    """
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
        meta = (
            tokens.get(name)
            or info["args"].get(name)
            or info["kwargs"].get(name)
            or {}
        )
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


def _value_for(name: str, given: dict[str, Any], tokens: dict) -> Any:
    """Return the token value that fills a template placeholder.

    A list placeholder also takes the values of every token that adds to
    the same list, such as ``target_user`` for ``targets``.
    """
    # Other tokens may set the same value (a list token and its members)
    meta = tokens.get(name, {})
    key = meta.get("map_to", name)
    found = [
        value
        for other, value in given.items()
        if tokens[other]["map_to"] == key
    ]
    if not found:
        # Nothing was given for this placeholder
        return None

    if not meta.get("type", "").startswith("list"):
        # One value fills it; the token the template names comes first
        return given.get(name, found[0])

    # Every value given is kept, so none is lost from the list
    merged: list[Any] = []
    for value in found:
        merged.extend(value if isinstance(value, (list, tuple)) else [value])

    return merged


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


def _encoded(value: Any, meta: dict[str, Any], path: bool = False) -> str:
    """Return a token value quoted for its place in a URL template.

    ``path`` keeps the slashes of a value that is a path of its own.
    """
    kind = meta.get("type", "string")
    if isinstance(value, (list, tuple, set)):
        # List entries are joined by the list's own delimiter
        delim = (meta.get("delim") or ("/",))[0]
        item = {"type": "email" if kind == "list:email" else "string"}
        return delim.join(
            _encoded(entry, item) for entry in value if not _empty(entry)
        )

    text = _text(value)
    if path:
        # A path keeps its slashes, and each part is encoded the way
        # parse_url() does it: escapes such as %20 are kept, while a space
        # or a lone % typed by a person is encoded
        return "/".join(
            URLBase.quote(URLBase.unquote(part), safe=URL_SEGMENT_SAFE_CHARS)
            for part in text.split("/")
        )

    if meta.get("map_to") == "host" and is_ipaddr(text, ipv4=False):
        # An IPv6 host keeps its brackets and colons
        return is_ipaddr(text, ipv4=False)

    quoted = URLBase.quote(text, safe="")
    if kind == "email" and text.count("@") == 1 and is_email(text):
        # One valid address keeps its @, as plugins write it (a name around
        # it is fine); a second @ is quoted so it can't move the address
        return quoted.replace("%40", "@")

    return quoted


def fields_to_url(fields: dict[str, Any]) -> Optional[str]:
    """Assemble a URL from fields named the way details() does.

    - ``fields`` must name the ``schema`` of an enabled service; any name
      the plugin does not define is refused.
    - The template that holds the given tokens best is filled in; the
      arguments and key/value options go into its query string.
    - Returns ``None`` when the URL cannot be assembled. The URL is not
      checked here; load it to find out whether it works.
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
    info = details(N_MGR[schema])
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
            logger.warning("The %s:// field %s is not supported", schema, name)
            return None

        entry = tokens.get(name) or args.get(name) or {}
        if "alias_of" in entry:
            # An alias has the shape of the item it stands for
            targets = entry["alias_of"]
            targets = (targets,) if isinstance(targets, str) else targets
            listed = any(
                (tokens.get(t) or args.get(t) or {})
                .get("type", "")
                .startswith("list")
                for t in targets
            )
            entry = {"type": "list:string" if listed else "string"}

        if not _fits(value, entry, kwarg=name in kwargs and name not in args):
            logger.warning(
                "The %s:// field %s has a value of the wrong type",
                schema,
                name,
            )
            return None

    # Tokens are written into the URL template itself
    placeable = {
        name: value
        for name, value in given.items()
        if name in tokens and "alias_of" not in tokens[name]
    }

    # Pick the template that places the most tokens, then the one missing
    # the fewest required ones, then the shortest
    chosen, best, placed = "", None, set()
    for template in info["templates"]:
        names = [
            name
            for name in TEMPLATE_TOKEN_RE.findall(template)
            if name != "schema"
        ]
        keys = {tokens.get(name, {}).get("map_to", name) for name in names}
        holds = {name for name in placeable if tokens[name]["map_to"] in keys}
        missing = sum(
            1
            for name in names
            if tokens.get(name, {}).get("required")
            and _value_for(name, placeable, tokens) is None
        )
        score = (len(placeable) - len(holds), missing, len(names))
        if best is None or score < best:
            chosen, best, placed = template, score, holds

    url = chosen.replace("{schema}", schema)
    for name in TEMPLATE_TOKEN_RE.findall(chosen):
        value = _value_for(name, placeable, tokens)
        if name != "schema" and value is not None:
            meta = tokens.get(name, {})
            path = name == "path" or meta.get("map_to", "").endswith("path")
            text = _encoded(value, meta, path=path)
            if path and "}{" + name + "}" in chosen:
                # A path straight after the host starts with a slash
                text = "/" + text.lstrip("/")

            if path and "{" + name + "}{" in chosen:
                # Another token follows the path directly
                text = text.rstrip("/") + "/"

            url = url.replace("{" + name + "}", text)

    for pattern, replacement in EMPTY_PLACEHOLDERS:
        url = pattern.sub(replacement, url)

    # Keep the slash after the host even when there is no path, the way
    # plugins write their own URLs
    base, mark, rest = url.partition("?")
    if "/" not in base.split("://", 1)[-1]:
        url = base + "/" + mark + rest

    # Everything the template did not take goes into the query string
    query = []
    for name, value in given.items():
        if name in placed:
            continue

        if name in kwargs and name not in args:
            prefix = kwargs[name].get("prefix", "+")
            query.extend((prefix + str(k), _text(v)) for k, v in value.items())
            continue

        if (
            name in args
            and args[name].get("type") in ("int", "float")
            and value == args[name].get("default")
        ):
            # A number left at its default is filled in by the service the
            # way it writes it (cto=15 rather than cto=15.0)
            continue

        query.append((_query_name(name, args, tokens), _text(value)))

    if query:
        # A template may hold a query string of its own already
        url += ("&" if "?" in url else "?") + "&".join(
            "{}={}".format(
                URLBase.quote(key, safe=""), URLBase.quote(text, safe="")
            )
            for key, text in query
        )

    return url


def _query_name(name: str, args: dict, tokens: dict) -> str:
    """Return the query string name a field is written under."""
    if name in args or name not in tokens:
        return name

    # A token the template has no place for is set by the argument that
    # stands in for it, such as ?token= for a session token
    key = tokens[name]["map_to"]
    for arg, meta in args.items():
        if meta.get("alias_of") == name or meta.get("map_to") == key:
            return arg

    return name
