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

"""Utilities that make payloads safe to *print* in debug and trace logs.

This module is intentionally scoped to log presentation only.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Optional

# Keys that commonly contain large binary-like values.
#
# This list is used as a *hint* to enable a more aggressive summarization mode
# for values underneath matching keys. The structure is still walked, only the
# leaf string/bytes values are summarized more aggressively.
#
# Keep this list conservative. Very generic tokens may cause false positives.
_BLOB_KEYWORDS = (
    "base64",
    "attachment",
    "attachments",
    "base64_attachments",
    "contentbytes",
    "blob",
    "file",
    "data",
    "image",
    "media",
    "document",
)


@dataclass(frozen=True)
class SanitizeOptions:
    """Options controlling payload sanitization for debug logging.

    The defaults are deliberately conservative and tuned for logging, not for
    data processing. When in doubt, prefer smaller values to keep logging
    cheap.

    Attributes:
        max_depth: Maximum recursion depth before truncation markers appear.
        max_items: Global upper bound on visited items, across the whole walk.
        max_str_len: Strings longer than this are summarized with a preview.
        preview: Number of characters to show at the start and end of
                 summaries.
        hash_sample_size: Maximum bytes hashed when generating a sha256
                          preview.
        aggressive_blob_keys: If True, summarize values under blob-like keys
            even when they are not huge, because these values are often encoded
            attachments (for example, base64).
    """

    # How many recursive lists/sets/tuples/dicts to delve into before
    # aborting
    max_depth: int = 10

    # The max amount of fields to process before we just abort (too many)
    max_items: int = 100

    # Strings longer than this are summarized
    max_str_len: int = 512

    # Preview size for summarized strings
    preview: int = 32

    # Bound hashing work
    # Strings longer than this (usually large attachments) include
    # sha256 hash value of it in response
    hash_sample_size: int = 8192

    # If True, summarize values under blob-like keys even if they are smaller
    # than the defined max_str_len.
    aggressive_blob_keys: bool = True


def sanitize_payload(
        value: Any, *, options: Optional[SanitizeOptions] = None) -> Any:
    """
    This function is intended for DEBUG and TRACE logging only.

    can add i/o to generate the printed copy, but the output is much
    better then just printing what could be a massive payload (with
    attachments).

    The ideal setup for this function is when you need to print what
    could be a very large object such as in the send() of a Apprise
    service, you would structure it like this:

        # check for at least the DEBUG level... you can also set
        # logging.TRACE if you wanted as well:
        if self.logger.isEnabledFor(logging.DEBUG):

            # Then safely wrap the output using this function:
            self.logger.debug(
                "Service Payload: %s", sanitize_payload(payload))
    """
    opts = options or SanitizeOptions()

    # Track already-seen objects to prevent infinite loops on recursive graphs.
    seen_ids: set[int] = set()

    # Global counter that enforces opts.max_items across the entire traversal.
    items_seen = 0

    def _hash_bytes(b: bytes) -> str:
        """Return a short sha256 prefix for bytes, bounded by
        hash_sample_size."""
        if len(b) > opts.hash_sample_size:
            b = b[: opts.hash_sample_size]
        return sha256(b).hexdigest()[:12]

    def _summarize_str(s: str) -> str:
        """Summarize strings longer than opts.max_str_len with a preview."""
        nonlocal items_seen
        items_seen += 1

        length = len(s)
        if length <= opts.max_str_len:
            return s

        head = s[: opts.preview]
        tail = s[-opts.preview :] if length >= opts.preview else s
        return f"<string len={length} head={head!r} tail={tail!r}>"

    def _summarize_bytes(b: bytes) -> str:
        """Summarize bytes with length and a short bounded sha256 prefix."""
        nonlocal items_seen
        items_seen += 1
        return f"<bytes len={len(b)} sha256={_hash_bytes(b)}>"

    def _is_blob_key(k: str) -> bool:
        """Return True if a key name indicates blob-like content.

        This keeps behaviour predictable while avoiding heavy scanning of
        values. Add items to _BLOB_KEYWORDS (not case sensitive) if required
        to optimize speed of parsing.
        """
        lk = k.lower()
        return lk in _BLOB_KEYWORDS

    def _summarize_key(k: Any) -> Any:
        """Summarize keys where needed, preserving readability in logs."""
        if isinstance(k, str):
            # Keys are usually short. Only summarize if they are unexpectedly
            # large to avoid log pollution.
            return _summarize_str(k)
        if isinstance(k, bytes):
            return _summarize_bytes(k)
        return k

    def _walk(obj: Any, depth: int, *, blob_mode: bool = False) -> Any:
        """Recursively walk payload structures and summarize leaf values."""
        nonlocal items_seen

        # Global safety limits first, so we can exit cheaply.
        if items_seen >= opts.max_items:
            return "<truncated: global item limit reached>"
        if depth > opts.max_depth:
            return "<truncated: max depth reached>"

        # Pass-through primitives.
        if obj is None or isinstance(obj, (bool, int, float)):
            items_seen += 1
            return obj

        # Strings: optionally apply blob-mode summaries.
        if isinstance(obj, str):
            if blob_mode and opts.aggressive_blob_keys:
                # Always summarize blob fields, even if not huge
                length = len(obj)
                head = obj[: opts.preview]
                tail = obj[-opts.preview :] if length >= opts.preview else obj
                items_seen += 1
                return (
                    f"<string len={length} blob "
                    f"head={head!r} tail={tail!r}>")
            return _summarize_str(obj)

        # Bytes: always summarize.
        if isinstance(obj, bytes):
            return _summarize_bytes(obj)

        # Prevent recursion loops on self-referential objects.
        obj_id = id(obj)
        if obj_id in seen_ids:
            return "<recursive>"
        seen_ids.add(obj_id)

        # Dict: walk values. Keys may be summarized for readability.
        if isinstance(obj, dict):
            out: dict[Any, Any] = {}
            for k, v in obj.items():
                if items_seen >= opts.max_items:
                    out["<truncated>"] = "..."
                    break

                sk = _summarize_key(k)

                # Enable blob mode for suspicious keys. We still walk the
                # structure, but leaf values are summarized aggressively.
                child_blob_mode = blob_mode
                if isinstance(k, str) and _is_blob_key(k):
                    child_blob_mode = True

                out[sk] = _walk(v, depth + 1, blob_mode=child_blob_mode)
            return out

        # Sequences: walk each entry. Sets are returned as lists for
        #            readability.
        if isinstance(obj, (list, tuple, set, frozenset)):
            out_list: list[Any] = []
            for entry in obj:
                if items_seen >= opts.max_items:
                    out_list.append("<truncated: limit reached>")
                    break
                out_list.append(_walk(entry, depth + 1, blob_mode=blob_mode))

            if isinstance(obj, tuple):
                return tuple(out_list)
            return out_list

        # Unknown objects: fall back to repr().
        items_seen += 1
        return repr(obj)

    # Recursively walk all elements of the object passed
    return _walk(value, 0)
