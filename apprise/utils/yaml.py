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

"""YAML-specific support for template variables.

PyYAML remains responsible for parsing and constructing configuration data.
These helpers only inspect the resulting ``urls`` values so template handling
does not require a custom loader or depend on PyYAML's internal constructors.
"""

from collections.abc import Collection
from typing import Any, Optional

from .parse import QSD_FULL_MODE_KEYS
from .template import (
    TEMPLATE_VAR_RE,
    TemplatePlaceholderMap,
    normalize_name,
)

# These values are assembled by ConfigBase rather than treated as ordinary
# plugin settings during the final YAML re-apply:
#
# - ``tag`` and ``tags`` have already been parsed and combined with global
#   tags. Reapplying the original string or list would discard that set.
# - ``asset`` is always the caller's AppriseAsset. A YAML option with the same
#   name must never replace that trusted object with configuration data.
#
# Keeping this list beside the other YAML rules makes the unusual second-pass
# behavior explicit without adding YAML details back to config/base.py.
YAML_REAPPLY_SKIP = frozenset(("tag", "tags", "asset"))


def template_references(value: Any) -> set[str]:
    """Return normalized ``${NAME}`` references from YAML URL values.

    URL mapping keys are inspected because Apprise permits a URL to introduce
    settings below it. Other mapping keys are literal YAML/plugin setting names
    and must never become variables; only their values are searched.

    Traversal is iterative and visits aliased containers once. This handles
    YAML anchors and cycles without recursion growth while the bounded template
    expression keeps each string scan linear.
    """
    references = set()
    visited = set()
    pending = [value]

    while pending:
        current = pending.pop()
        if isinstance(current, str):
            references.update(
                normalize_name(match.group("name"))
                for match in TEMPLATE_VAR_RE.finditer(current)
            )
            continue

        if not isinstance(current, (dict, list, tuple, set)):
            # Numbers, flags, nulls, and other scalar values cannot contain a
            # template marker and need no further inspection.
            continue

        marker = id(current)
        if marker in visited:
            # YAML aliases can reuse a container or form a loop. Neither case
            # should duplicate diagnostics or make this debug scan unbounded.
            continue
        visited.add(marker)

        if isinstance(current, dict):
            for key, item in current.items():
                # Only URL-shaped keys carry configurable text. A key such as
                # ``+X-${NAME}`` is a literal setting name by design.
                if isinstance(key, str) and "://" in key:
                    pending.append(key)
                pending.append(item)
        else:
            pending.extend(current)

    return references


def template_in_schema(url: Any, declared: Collection[str]) -> Optional[str]:
    """Return a declared variable used before a URL's ``://`` separator.

    The schema chooses the temporary parser before template values are known,
    so it can never be variable. Marker-like text that was not declared remains
    ordinary text and follows Apprise's normal invalid-URL handling.
    """
    if not isinstance(url, str):
        return None

    # Use the first literal separator. A later URL in a path/query cannot move
    # the schema boundary past a marker, and a preceding backslash does not
    # escape ``://`` or make a variable schema valid.
    separator = url.find("://")
    declared = set(declared)
    for match in TEMPLATE_VAR_RE.finditer(url):
        name = normalize_name(match.group("name"))
        if name in declared and (separator < 0 or match.start() < separator):
            return name

    return None


def dropped_template(
    url: str,
    results: dict,
    placeholders: Optional[TemplatePlaceholderMap],
) -> Optional[str]:
    """Return a declared marker discarded by a service URL parser.

    Some URL positions are type-sensitive. A parser may appear to accept a
    placeholder while dropping it or damaging a nearby field. Rejecting that
    entry is safer than later constructing a service from incomplete values.
    """
    if not placeholders:
        return None

    # The saved source URL still contains every marker, so compare only the
    # fields that the plugin parser actually retained.
    parsed = placeholders.used(
        {key: value for key, value in results.items() if key != "url"}
    )
    missing = placeholders.used(url) - parsed

    # Stable selection keeps logs and tests deterministic if several markers
    # were lost by the same parser.
    return sorted(missing)[0] if missing else None


def templated_tag(
    results: Any, placeholders: Optional[TemplatePlaceholderMap]
) -> bool:
    """Return whether a parsed entry makes ``tag`` or ``tags`` variable.

    Tags control Apprise routing and therefore must be known before a pending
    notification service is resolved. The check covers URL query modifiers,
    YAML settings encoded as placeholders, and unencoded global YAML tags.
    """
    if not placeholders or not isinstance(results, dict):
        return False

    # URL parsing stores ordinary query arguments in qsd and the three custom
    # forms in the shared QSD_FULL_MODE_KEYS definition. A static tag name with
    # a templated value is invalid in every bucket.
    for bucket in ("qsd", *QSD_FULL_MODE_KEYS):
        values = results.get(bucket)
        if isinstance(values, dict) and any(
            placeholders.used(values.get(key)) for key in ("tag", "tags")
        ):
            return True

    tags = results.get("tag", ())
    if placeholders.used(tags):
        # Per-service YAML tag values have already been encoded.
        return True

    # Global tags are deliberately not encoded with plugin arguments. Inspect
    # their original marker text and reject only names declared as variables.
    return bool(template_references(tags) & set(placeholders.schema.names))
