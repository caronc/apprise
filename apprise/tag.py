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

import re

# Matches: [priority:]tagname[:retry]
# - priority is a non-negative integer prefix (e.g. "2:endpoint")
# - tagname is a-z, 0-9, underscore, hyphen
# - retry is a non-negative integer suffix (e.g. "endpoint:3", CLI only)
_RE_TAG = re.compile(
    r"^(?:(?P<priority>[0-9]+):)?(?P<tag>[a-z0-9][a-z0-9_-]*)(?::(?P<retry>[0-9]+))?$",
    re.IGNORECASE,
)


class AppriseTag:
    """Wraps a tag string and carries optional priority and retry metadata.

    The tag name is the canonical identity; two AppriseTag objects (or an
    AppriseTag and a plain str) are considered equal when their tag names
    match, regardless of priority or retry.  Hash is likewise based solely
    on the tag name so that set intersection and membership tests work
    transparently against sets that contain plain strings.

    Supported string formats:
      tagname          -> priority=0, retry=None
      priority:tagname -> priority=N, retry=None  (config / YAML)
      tagname:retry    -> priority=0, retry=N     (CLI runtime override)
      priority:tagname:retry -> priority=N, retry=N
    """

    __slots__ = ("_tag", "has_priority", "priority", "retry")

    def __init__(self, tag, priority=0, retry=None, has_priority=False):
        """Initialise an AppriseTag directly from its constituent parts.

        Prefer AppriseTag.parse() when constructing from a raw string because
        it handles the "priority:tag:retry" tokenisation automatically.

        Args:
            tag (str): The bare tag name.  Always stored lowercased.
            priority (int, optional): Numeric dispatch priority.  Lower numbers
                are dispatched first (0 = highest urgency).  Defaults to 0.
            retry (int or None, optional): Call-level retry count carried by
                this tag token, or None when none was specified.
            has_priority (bool, optional): True when the priority was
                explicitly written in the source string (e.g. "0:endpoint"),
                False when it was absent and the default of 0 was assumed.
                This flag drives the exclusive-vs-escalation dispatch decision.
        """
        self._tag = str(tag).lower().strip()
        self.priority = max(0, int(priority)) if priority is not None else 0
        self.retry = int(retry) if retry is not None else None
        self.has_priority = bool(has_priority)

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------

    @classmethod
    def parse(cls, value):
        """Return an AppriseTag parsed from a string (or the same object
        if already an AppriseTag).

        Unrecognised strings fall back to a zero-priority, no-retry tag
        whose name is the entire input lowercased.
        """
        if isinstance(value, cls):
            return value
        m = _RE_TAG.match(str(value).strip())
        if m:
            return cls(
                tag=m.group("tag"),
                priority=int(m.group("priority") or 0),
                retry=(
                    int(m.group("retry"))
                    if m.group("retry") is not None
                    else None
                ),
                has_priority=m.group("priority") is not None,
            )
        # Fallback: store raw value as name (no priority/retry)
        return cls(tag=str(value).strip().lower())

    # ------------------------------------------------------------------
    # String representation
    # ------------------------------------------------------------------

    def __str__(self):
        """Return the bare lowercase tag name."""
        return self._tag

    def __repr__(self):
        """Return a developer-readable representation including non-default
        priority and retry values so they are visible in tracebacks."""
        parts = [repr(self._tag)]
        if self.priority:
            parts.append(f"priority={self.priority}")
        if self.retry is not None:
            parts.append(f"retry={self.retry}")
        return "AppriseTag({})".format(", ".join(parts))

    # ------------------------------------------------------------------
    # Identity (tag-name only -- priority/retry are metadata, not identity)
    # ------------------------------------------------------------------

    def __hash__(self):
        """Hash based solely on the lowercased tag name.

        This must equal hash(tag_name_string) so that AppriseTag objects
        can be mixed with plain strings inside sets and dictionaries without
        any special handling in is_exclusive_match or elsewhere.
        """
        return hash(self._tag)

    def __eq__(self, other):
        """Compare identity by tag name only.

        An AppriseTag is considered equal to a plain string when their
        lowercased tag names match, enabling transparent membership tests
        such as ``"endpoint" in {AppriseTag("endpoint")}``.
        """
        if isinstance(other, AppriseTag):
            return self._tag == other._tag
        if isinstance(other, str):
            return self._tag == other.lower()
        return NotImplemented

    def __lt__(self, other):
        """Compare tag names lexicographically to allow sorting.

        Used when a deterministic ordering of tags is needed (e.g. for
        reproducible log output).
        """
        if isinstance(other, AppriseTag):
            return self._tag < other._tag
        if isinstance(other, str):
            return self._tag < other.lower()
        return NotImplemented

    def __bool__(self):
        """Return False for an empty tag name, True otherwise."""
        return bool(self._tag)
